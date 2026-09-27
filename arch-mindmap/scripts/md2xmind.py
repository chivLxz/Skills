#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2xmind.py — 把 Markdown 大纲转成 .xmind（Xmind Zen 格式）。

特性:
  * 零第三方依赖（只用标准库 zipfile / json / uuid），不联网
  * 输出严格对齐 Xmind 官方 SDK（xmindltd/xmind-generator）的序列化结构，
    因此产物可被 Xmind 桌面版 / 移动版 / 网页版直接打开并继续编辑
  * 节点里的 `反引号内容` 自动收纳进「备注」，标题保持干净
  * 带 ⚠ 的节点自动打上「待复核」标签

用法:
    python3 md2xmind.py input.md [output.xmind]
        [--title 中心标题] [--sheet 画布名]
        [--structure unbalanced|logic-right|logic-left|tree-right|org-chart|timeline]

Markdown 约定:
    #      -> 中心主题（取第一个一级标题）
    ## 及以下 -> 各级分支（层级 = 标题级数 - 1）
"""
import sys
import os
import re
import json
import uuid
import zipfile

MAX_DEPTH = 6
HEADER_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
CODE_RE = re.compile(r'`([^`]+)`')

STRUCTURES = {
    'unbalanced': 'org.xmind.ui.map.unbalanced',      # 经典思维导图（两侧发散，默认）
    'logic-right': 'org.xmind.ui.logic.right',        # 逻辑图，向右
    'logic-left': 'org.xmind.ui.logic.left',          # 逻辑图，向左
    'tree-right': 'org.xmind.ui.tree.right',          # 树形图
    'org-chart': 'org.xmind.ui.org-chart.down',       # 组织架构图
    'timeline': 'org.xmind.ui.timeline.horizontal',   # 时间轴
}


def new_id():
    return str(uuid.uuid4())


def clean(text):
    """拆出 (干净标题, 备注列表, 是否待复核)。"""
    flagged = '\u26a0' in text or '\u2757' in text
    text = text.replace('\u26a0', ' ').replace('\u2757', ' ')

    notes = [s.strip() for s in CODE_RE.findall(text) if s.strip()]
    text = CODE_RE.sub('', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\s{2,}', ' ', text).strip(' -–—·:：,，')
    return text, notes, flagged


def parse(md_path):
    """返回 (中心主题, [(层级, 标题, 备注, 待复核), ...])，层级从 1 开始。"""
    center = None
    items = []
    with open(md_path, 'r', encoding='utf-8') as f:
        in_fence = False
        for line in f:
            if line.strip().startswith('```'):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = HEADER_RE.match(line.rstrip('\n'))
            if not m:
                continue
            level = len(m.group(1))
            title, notes, flagged = clean(m.group(2))
            if not title:
                continue
            if center is None:
                center, center_notes, center_flag = title, notes, flagged
                continue
            items.append((max(1, min(level - 1, MAX_DEPTH)), title, notes, flagged))
    if center is None:
        center, center_notes, center_flag = os.path.splitext(os.path.basename(md_path))[0], [], False
    return center, center_notes, center_flag, items


def build_tree(center, center_notes, center_flag, items):
    """按层级构造中间树。"""
    root = {'title': center, 'notes': list(center_notes), 'flag': center_flag, 'children': []}
    stack = [root]
    for level, title, notes, flagged in items:
        while len(stack) > level:
            stack.pop()
        node = {'title': title, 'notes': notes, 'flag': flagged, 'children': []}
        stack[-1]['children'].append(node)
        stack.append(node)
    return root


def ser_topic(node):
    """单个节点 -> Xmind topic 对象（字段对齐官方 SDK）。"""
    obj = {'id': new_id(), 'class': 'topic', 'title': node['title']}
    if node['notes']:
        obj['notes'] = {'plain': {'content': '\n'.join(node['notes']) + '\n'}}
    if node['flag']:
        obj['labels'] = ['待复核']
    if node['children']:
        obj['children'] = {'attached': [ser_topic(c) for c in node['children']]}
    return obj


def build_content(root, sheet_title, structure):
    root_topic = ser_topic(root)
    root_topic['structureClass'] = STRUCTURES.get(structure, STRUCTURES['unbalanced'])
    sheet = {
        'id': new_id(),
        'class': 'sheet',
        'title': sheet_title,
        'rootTopic': root_topic,
    }
    return [sheet]


def archive(sheets, dst):
    """写成 zip（STORE 压缩，与官方 SDK 一致）。"""
    dumps = lambda o: json.dumps(o, ensure_ascii=False, separators=(',', ':'))
    content = dumps(sheets)
    metadata = dumps({
        'creator': {'name': 'arch-mindmap'},
        'dataStructureVersion': '2',
    })
    manifest = dumps({'file-entries': {'content.json': {}, 'metadata.json': {}}})
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_STORED) as z:
        z.writestr('content.json', content)
        z.writestr('metadata.json', metadata)
        z.writestr('manifest.json', manifest)


def stats(root):
    """返回 (各层节点数, 总数)。"""
    counts = {}
    total = [0]

    def walk(n, depth):
        if depth > 0:
            counts[depth] = counts.get(depth, 0) + 1
            total[0] += 1
        for c in n['children']:
            walk(c, depth + 1)

    walk(root, 0)
    return counts, total[0]


def main():
    args = [a for a in sys.argv[1:]]
    opts = {'--title': None, '--sheet': None, '--structure': 'unbalanced'}
    pos = []
    i = 0
    while i < len(args):
        if args[i] in opts:
            if i + 1 >= len(args):
                print('error: %s 缺少值' % args[i], file=sys.stderr)
                return 1
            opts[args[i]] = args[i + 1]
            i += 2
        else:
            pos.append(args[i])
            i += 1

    if not pos:
        print(__doc__.strip().split('\n\n')[1], file=sys.stderr)
        return 1
    src = pos[0]
    if not os.path.isfile(src):
        print('error: 找不到文件 %s' % src, file=sys.stderr)
        return 2
    if opts['--structure'] not in STRUCTURES:
        print('error: 未知布局 %s，可选: %s' % (opts['--structure'], ', '.join(STRUCTURES)), file=sys.stderr)
        return 1

    dst = pos[1] if len(pos) > 1 else os.path.splitext(src)[0] + '.xmind'

    center, cnotes, cflag, items = parse(src)
    if opts['--title']:
        center = opts['--title']
    if not items:
        print('error: %s 里没有找到任何标题（至少需要一个 ## 二级标题）' % src, file=sys.stderr)
        return 3

    root = build_tree(center, cnotes, cflag, items)
    sheets = build_content(root, opts['--sheet'] or center, opts['--structure'])
    archive(sheets, dst)

    counts, total = stats(root)
    print('中心主题 : %s' % center)
    print('布局     : %s (%s)' % (opts['--structure'], STRUCTURES[opts['--structure']]))
    print('节点总数 : %d' % total)
    for d in sorted(counts):
        print('  L%d     : %d' % (d, counts[d]))
    size = os.path.getsize(dst)
    print('产物     : %s (%s)' % (dst, ('%.1f KB' % (size / 1024.0)) if size < 1024 * 1024 else ('%.1f MB' % (size / 1048576.0))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
