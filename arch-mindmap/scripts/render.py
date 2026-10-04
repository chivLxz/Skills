#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — 把 Markdown 大纲渲染成 SVG / PNG / PDF（可选交互式 HTML）。

三个脚本的分工:
    md2xmind.py  出 .xmind   —— 给人「编辑」用
    md2svg.py    出 .svg     —— 矢量源文件，可编辑、可放大
    render.py    出 .png/.pdf/.html —— 给人「查看、贴文档、分发」用

渲染路线说明:
    PNG/PDF 走的是「自己算好坐标的静态 SVG + 无头浏览器栅格化」，
    不用 markmap 那种浏览器端现算布局的方式 —— 后者在无头环境下
    时序不稳，经常截出白图。静态 SVG 没有 JS，结果可复现。

依赖:
    - Chrome / Edge / Chromium（必需，用于栅格化与打印 PDF）
    - Pillow（可选，用于把 PNG 裁到紧致边缘）
    - markmap-cli（可选，只有要交互式 HTML 时才需要）

用法:
    python3 render.py input.md [--outdir DIR] [--only svg,png,pdf,html]
        [--scale auto|1|2|3] [--title 标题]
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2xmind import parse, build_tree           # noqa: E402
from md2svg import render as svg_render          # noqa: E402


def log(msg):
    print(msg, flush=True)


def find_browser():
    env = os.environ.get('CHROME_PATH') or os.environ.get('BROWSER')
    if env and os.path.isfile(env):
        return env
    cands = []
    if sys.platform == 'darwin':
        cands = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
        ]
    elif sys.platform.startswith('win'):
        cands = [
            os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
            os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
        ]
    else:
        for name in ('google-chrome', 'google-chrome-stable', 'chromium',
                     'chromium-browser', 'microsoft-edge', 'brave-browser'):
            w = shutil.which(name)
            if w:
                return w
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def auto_scale(w, h):
    """按画布尺寸选超采样倍率。

    目标是让最小的字在成品图里也有足够物理像素 —— 深层级字号只有 11~12px，
    1x 采样下贴进文档会糊。同时不把 PNG 撑到离谱的大小。
    """
    m = max(w, h)
    if m >= 5000:
        return 1
    if m >= 2500:
        return 2
    if m >= 1000:
        return 3
    return 4


def run(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def svg_to_png(browser, svg_path, png_path, w, h, scale):
    cmd = [browser, '--headless', '--disable-gpu', '--no-sandbox',
           '--hide-scrollbars', '--disable-extensions',
           '--force-device-scale-factor=%d' % scale,
           '--window-size=%d,%d' % (int(w), int(h)),
           '--virtual-time-budget=10000',
           '--screenshot=' + png_path,
           'file://' + os.path.abspath(svg_path)]
    try:
        r = run(cmd)
    except subprocess.TimeoutExpired:
        log('  截图超时')
        return False
    if not os.path.isfile(png_path):
        log('  截图失败: %s' % (r.stderr or r.stdout or '').strip()[:300])
        return False
    return True


def svg_to_pdf(browser, svg_path, pdf_path, w, h):
    """把 SVG 内联进一个精确尺寸的页面再打印，得到单页矢量 PDF。"""
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg = f.read()
    wrap = ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
            '@page{size:%dpx %dpx;margin:0}'
            'html,body{margin:0;padding:0;background:#fff;overflow:hidden}'
            'svg{display:block}'
            '</style></head><body>%s</body></html>' % (int(w), int(h), svg))
    tmp = pdf_path + '.wrap.html'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(wrap)
    cmd = [browser, '--headless', '--disable-gpu', '--no-sandbox',
           '--no-pdf-header-footer', '--disable-extensions',
           '--window-size=%d,%d' % (int(w), int(h)),
           '--virtual-time-budget=10000',
           '--print-to-pdf=' + pdf_path,
           'file://' + os.path.abspath(tmp)]
    try:
        r = run(cmd)
    except subprocess.TimeoutExpired:
        log('  PDF 生成超时')
        os.path.isfile(tmp) and os.remove(tmp)
        return False
    os.path.isfile(tmp) and os.remove(tmp)
    if not os.path.isfile(pdf_path):
        log('  PDF 失败: %s' % (r.stderr or r.stdout or '').strip()[:300])
        return False
    return True


def trim_png(png_path, scale=1):
    """把 PNG 四周的空白裁到紧致，只留一点呼吸空间。

    这一步同时起校验作用：SVG 里文字宽度是按字符估算的，
    万一估窄了导致文字超出画布，这里能立刻看出来。
    """
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return None
    im = Image.open(png_path).convert('RGB')
    bg = Image.new('RGB', im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg).convert('L').point(lambda p: 255 if p > 10 else 0)
    bb = diff.getbbox()
    if not bb:
        return False
    pad = max(24, int(14 * scale))     # 14 逻辑像素的边距，按超采样倍率放大
    box = (max(0, bb[0] - pad), max(0, bb[1] - pad),
           min(im.width, bb[2] + pad), min(im.height, bb[3] + pad))
    out = im.crop(box)
    out.save(png_path)
    return out.size


def find_markmap():
    exe = shutil.which('markmap')
    if exe:
        return [exe]
    npx = shutil.which('npx')
    if npx:
        return [npx, '-y', 'markmap-cli']
    return None


def build_interactive_html(md_path, html_path, w, h):
    """可选：markmap 交互版。它靠浏览器端 JS 渲染，用户自己打开时没问题。"""
    mm = find_markmap()
    if not mm:
        log('  html   : 跳过（没装 markmap-cli，装了可再跑一次）')
        return False
    cmd = list(mm) + [md_path, '-o', html_path, '--no-open', '--offline', '--no-toolbar']
    try:
        r = run(cmd)
    except subprocess.TimeoutExpired:
        log('  html   : markmap 超时')
        return False
    if not os.path.isfile(html_path):
        log('  html   : markmap 失败 %s' % (r.stderr or '')[:200])
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('--outdir', default=None)
    ap.add_argument('--only', default='svg,png,pdf')
    ap.add_argument('--scale', default='auto')
    ap.add_argument('--title', default=None)
    ap.add_argument('--name', default=None)
    ap.add_argument('--font-scale', type=float, default=1.0)
    ap.add_argument('--layout', default='auto', choices=['auto', 'right', 'wing'])
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        log('error: 找不到 %s' % args.input)
        return 2

    want = set(x.strip() for x in args.only.split(',') if x.strip())
    base = args.name or os.path.splitext(os.path.basename(args.input))[0]
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.input)) or '.'
    os.makedirs(outdir, exist_ok=True)
    svg_path = os.path.join(outdir, base + '.svg')
    png_path = os.path.join(outdir, base + '.png')
    pdf_path = os.path.join(outdir, base + '.pdf')
    html_path = os.path.join(outdir, base + '.html')

    center, cnotes, cflag, items = parse(args.input)
    if args.title:
        center = args.title
    if not items:
        log('error: %s 里没有找到任何标题（至少需要一个 ## 二级标题）' % args.input)
        return 3

    root = build_tree(center, cnotes, cflag, items)
    svg, w, h, used = svg_render(root, args.font_scale, args.layout)
    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    log('  svg    : %s（%.0f x %.0f px，%s）'
        % (svg_path, w, h, '两翼布局' if used == 'wing' else '单侧向右'))

    if not want & {'png', 'pdf'}:
        if 'html' in want and build_interactive_html(args.input, html_path, w, h):
            log('  html   : %s' % html_path)
        return 0

    browser = find_browser()
    if not browser:
        log('error: 没找到 Chrome/Edge/Chromium，无法生成 PNG/PDF。')
        log('       可用 CHROME_PATH 环境变量指定浏览器可执行文件。')
        log('       SVG 已经生成好了，用浏览器或 Illustrator/Figma 打开也能导出。')
        return 4

    if 'png' in want:
        scale = auto_scale(w, h) if args.scale == 'auto' else int(args.scale)
        if not svg_to_png(browser, svg_path, png_path, w, h, scale):
            return 5
        size = trim_png(png_path, scale)
        if size is False:
            log('  png    : 截出来是空白，请检查 Chrome 是否正常')
            return 6
        if size:
            log('  png    : %s（%dx%d px，%dx 超采样后裁边）'
                % (png_path, size[0], size[1], scale))
        else:
            log('  png    : %s（%dx 超采样，未裁边）' % (png_path, scale))

    if 'pdf' in want:
        if not svg_to_pdf(browser, svg_path, pdf_path, w, h):
            return 7
        kb = os.path.getsize(pdf_path) / 1024.0
        log('  pdf    : %s（矢量，单页 %.0f x %.0f px，%.0f KB）'
            % (pdf_path, w, h, kb))

    if 'html' in want and build_interactive_html(args.input, html_path, w, h):
        log('  html   : %s' % html_path)

    if 'svg' not in want and os.path.isfile(svg_path):
        os.remove(svg_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
