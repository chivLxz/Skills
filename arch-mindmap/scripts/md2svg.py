#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2svg.py — 把 Markdown 大纲渲染成思维导图 SVG（矢量、可编辑）。

为什么不用 markmap：
    markmap 靠浏览器端 JS 现算布局，在无头环境下渲染时序不稳定，
    时常截出白图。这里改成纯 Python 算好坐标再吐静态 SVG——
    没有 JS、没有网络、结果逐像素可复现，而且 SVG 本身就能编辑。

布局:
    默认单侧向右展开（逻辑图）。当节点多、图会变成长条时，
    自动切成「两翼」——一级分支按高度均衡地分到中心主题左右两侧，
    避免出现 500 x 3000 这种没法看的比例。

用法:
    python3 md2svg.py input.md [output.svg]
        [--title 标题] [--layout auto|right|wing] [--font-scale 1.0]
"""
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2xmind import parse, build_tree  # noqa: E402

FONT_FAMILY = ('"PingFang SC","Hiragino Sans GB","Microsoft YaHei",'
               '"Noto Sans CJK SC","Source Han Sans SC",system-ui,'
               '-apple-system,"Segoe UI",sans-serif')

FS = {0: 21.0, 1: 17.0, 2: 15.0}      # 各层级字号
LH = {0: 38.0, 1: 30.0, 2: 25.0}      # 各层级行高（节点高度）
PILL_PAD = 14.0                        # 药丸型节点的水平内边距
GAP_X = 46.0                           # 层级之间横向间距
GAP_Y = 9.0                            # 兄弟节点之间纵向间距
MARGIN = 44.0                          # 画布留白
MAX_FS_LEVEL = 2                       # 超过该层级沿用最后一档字号
WING_TRIGGER = 2.2                     # 高宽比超过这个值就切两翼布局


def fs_of(depth):
    return FS.get(depth, FS[MAX_FS_LEVEL])


def lh_of(depth):
    return LH.get(depth, LH[MAX_FS_LEVEL])


def text_width(s, fs):
    """估算文字宽度。中日韩按 1 个字宽算，其余按比例。"""
    w = 0.0
    for ch in s:
        o = ord(ch)
        if o > 0x2E7F:                    # CJK / 全角
            w += fs * 1.02
        elif ch in 'iljI.,:;!|\'"`[]()':
            w += fs * 0.32
        elif ch.isupper():
            w += fs * 0.68
        elif ch.isdigit():
            w += fs * 0.58
        elif ch == ' ':
            w += fs * 0.30
        else:
            w += fs * 0.55
    return w


def is_pill(depth):
    """根节点与一级分支用实心药丸，其余用文字 + 下划线。"""
    return depth <= 1


def measure(node, depth):
    node['depth'] = depth
    node['fs'] = fs_of(depth)
    node['lh'] = lh_of(depth)
    node['tw'] = text_width(node['title'], node['fs'])
    node['w'] = (node['tw'] + PILL_PAD * 2) if is_pill(depth) else node['tw']
    for c in node['children']:
        measure(c, depth + 1)
    if node['children']:
        inner = (sum(c['sub_h'] for c in node['children'])
                 + GAP_Y * (len(node['children']) - 1))
        node['sub_h'] = max(inner, node['lh'])
    else:
        node['sub_h'] = node['lh']


def place(node, x, top, direction):
    """direction = 1 向右展开，-1 向左镜像展开。"""
    node['dir'] = direction
    node['x'] = x if direction > 0 else x - node['w']
    if not node['children']:
        node['y'] = top + (node['sub_h'] - node['lh']) / 2.0
        return
    cy = top
    for c in node['children']:
        if direction > 0:
            place(c, node['x'] + node['w'] + GAP_X, cy, 1)
        else:
            place(c, node['x'] - GAP_X, cy, -1)
        cy += c['sub_h'] + GAP_Y
    first, last = node['children'][0], node['children'][-1]
    mid = (first['y'] + first['lh'] / 2.0 + last['y'] + last['lh'] / 2.0) / 2.0
    node['y'] = mid - node['lh'] / 2.0


def group_height(group):
    return sum(c['sub_h'] for c in group) + GAP_Y * max(len(group) - 1, 0)


def balanced_split(tops):
    """按子树高度把一级分支均衡分到左右两侧，同时保持原有先后顺序。"""
    order = sorted(range(len(tops)), key=lambda i: -tops[i]['sub_h'])
    right_ids, hr, hl = set(), 0.0, 0.0
    for i in order:
        add = tops[i]['sub_h'] + GAP_Y
        if hr <= hl:
            right_ids.add(id(tops[i]))
            hr += add
        else:
            hl += add
    right = [t for t in tops if id(t) in right_ids]
    left = [t for t in tops if id(t) not in right_ids]
    return right, left


def place_wing(root):
    """两翼布局：中心主题居中，一级分支向左右分开。"""
    tops = root['children']
    right, left = balanced_split(tops)
    root['dir'] = 0
    root['x'] = 0.0
    root['y'] = -root['lh'] / 2.0

    cy = -group_height(right) / 2.0
    for c in right:
        place(c, root['w'] + GAP_X, cy, 1)
        cy += c['sub_h'] + GAP_Y

    cy = -group_height(left) / 2.0
    for c in left:
        place(c, -GAP_X, cy, -1)
        cy += c['sub_h'] + GAP_Y


def place_right(root):
    root['dir'] = 1
    place(root, 0.0, 0.0, 1)


def collect(node, acc):
    acc.append(node)
    for c in node['children']:
        collect(c, acc)


def branch_color(idx, total):
    hue = (idx * 360.0 / max(total, 1) + 12.0) % 360.0
    return hue


def esc(s):
    return html.escape(s, quote=True)


def bbox(nodes):
    minx = min(n['x'] for n in nodes)
    miny = min(n['y'] for n in nodes)
    maxx = max(n['x'] + n['w'] for n in nodes)
    maxy = max(n['y'] + n['lh'] for n in nodes)
    return minx, miny, maxx, maxy


def render(root, font_scale=1.0, layout='auto'):
    measure(root, 0)
    tops = root['children']

    # 先按单侧布局试算，太高就切两翼
    place_right(root)
    nodes = []
    collect(root, nodes)
    used = 'right'
    if layout == 'wing' or (layout == 'auto' and len(tops) >= 2):
        minx, miny, maxx, maxy = bbox(nodes)
        w0, h0 = maxx - minx, maxy - miny
        want_wing = (layout == 'wing') or (h0 > WING_TRIGGER * max(w0, 1.0))
        if want_wing:
            place_wing(root)
            nodes = []
            collect(root, nodes)
            used = 'wing'

    # 标记每个节点归属哪个一级分支（取色用）
    for i, t in enumerate(tops):
        t['bi'] = i
        stack = list(t['children'])
        while stack:
            cur = stack.pop()
            cur['bi'] = i
            stack.extend(cur['children'])
    root['bi'] = -1

    minx, miny, maxx, maxy = bbox(nodes)
    total_w = (maxx - minx) + MARGIN * 2
    total_h = (maxy - miny) + MARGIN * 2
    for n in nodes:
        n['x'] -= minx - MARGIN
        n['y'] -= miny - MARGIN

    def color_of(n, sat=62, light=46):
        if n['bi'] < 0:
            return 'hsl(215, 12%, 24%)'
        h = branch_color(n['bi'], max(len(tops), 1))
        return 'hsl(%.1f, %.0f%%, %.0f%%)' % (h, sat, light)

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" '
               'viewBox="0 0 %.0f %.0f" font-family=\'%s\'>'
               % (total_w, total_h, total_w, total_h, FONT_FAMILY))
    out.append('<rect width="100%" height="100%" fill="#ffffff"/>')

    # 先连线，后画节点，保证线被节点压住
    def edges(n):
        cy_n = n['y'] + n['lh'] / 2.0
        for c in n['children']:
            cy_c = c['y'] + c['lh'] / 2.0
            if c['dir'] > 0:
                x1, x2 = n['x'] + n['w'], c['x']
                dx = max((x2 - x1) * 0.5, 8.0)
                d = ('M %.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f'
                     % (x1, cy_n, x1 + dx, cy_n, x2 - dx, cy_c, x2, cy_c))
            else:
                x1, x2 = n['x'], c['x'] + c['w']
                dx = max((x1 - x2) * 0.5, 8.0)
                d = ('M %.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f'
                     % (x1, cy_n, x1 - dx, cy_n, x2 + dx, cy_c, x2, cy_c))
            sw = 2.6 if n['depth'] == 0 else 2.0
            out.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" '
                       'stroke-linecap="round"/>' % (d, color_of(c, 58, 62), sw))
            edges(c)
    edges(root)

    for n in nodes:
        d = n['depth']
        fs = n['fs'] * font_scale
        lh = n['lh'] * font_scale
        if is_pill(d):
            fill = color_of(n, 62, 44 if d else 24)
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" '
                       'ry="%.1f" fill="%s"/>'
                       % (n['x'], n['y'], n['w'], lh, lh / 2.0, lh / 2.0, fill))
            out.append('<text x="%.1f" y="%.1f" font-size="%.1f" font-weight="600" '
                       'fill="#ffffff" dominant-baseline="central">%s</text>'
                       % (n['x'] + PILL_PAD, n['y'] + lh / 2.0, fs, esc(n['title'])))
        else:
            tc = '#1f2328' if d == 2 else '#3c4148'
            fw = '600' if d == 2 else '400'
            out.append('<text x="%.1f" y="%.1f" font-size="%.1f" font-weight="%s" '
                       'fill="%s" dominant-baseline="central">%s</text>'
                       % (n['x'], n['y'] + lh / 2.0, fs, fw, tc, esc(n['title'])))
            uy = n['y'] + lh / 2.0 + fs * 0.62
            uw = n['tw'] * font_scale
            if n['flag']:
                out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                           'stroke="#e07b1f" stroke-width="2.6" stroke-linecap="round"/>'
                           % (n['x'], uy, n['x'] + uw, uy))
            else:
                out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                           'stroke="%s" stroke-width="1.6" stroke-linecap="round"/>'
                           % (n['x'], uy, n['x'] + uw, uy,
                              color_of(n, 52, 60) if d <= 3 else '#d8dde3'))
    out.append('</svg>')
    return '\n'.join(out), total_w, total_h, used


def main():
    args = sys.argv[1:]
    title = None
    font_scale = 1.0
    layout = 'auto'
    pos = []
    i = 0
    while i < len(args):
        if args[i] in ('--title', '--font-scale', '--layout') and i + 1 < len(args):
            val = args[i + 1]
            if args[i] == '--title':
                title = val
            elif args[i] == '--font-scale':
                font_scale = float(val)
            else:
                layout = val
            i += 2
        else:
            pos.append(args[i])
            i += 1
    if not pos:
        print('usage: md2svg.py input.md [output.svg] '
              '[--title T] [--layout auto|right|wing] [--font-scale 1.0]', file=sys.stderr)
        return 1
    src = pos[0]
    if not os.path.isfile(src):
        print('error: 找不到 %s' % src, file=sys.stderr)
        return 2
    dst = pos[1] if len(pos) > 1 else os.path.splitext(src)[0] + '.svg'

    center, cnotes, cflag, items = parse(src)
    if title:
        center = title
    if not items:
        print('error: %s 里没有找到任何标题' % src, file=sys.stderr)
        return 3

    root = build_tree(center, cnotes, cflag, items)
    svg, w, h, used = render(root, font_scale, layout)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(svg)
    print('中心主题 : %s' % center)
    print('布局     : %s' % ('两翼（左右展开）' if used == 'wing' else '单侧向右'))
    print('画布     : %.0f x %.0f px' % (w, h))
    print('节点总数 : %d' % len(items))
    print('产物     : %s (%.1f KB)' % (dst, os.path.getsize(dst) / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
