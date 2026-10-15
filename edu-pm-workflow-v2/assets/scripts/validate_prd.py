#!/usr/bin/env python3
"""PRD 格式校验（v2.9 工作流 §5.2 的第一步）。

用法：
    python3 validate_prd.py [需求名/需求文档/需求名-PRD.html ...]
    py -3 validate_prd.py …            # Windows 上没有 python3 命令
    py -3 validate_prd.py … --allow-uninstalled   # 临时校验不属于本项目的 PRD

不带参数时，从当前目录向下查找所有 *-PRD.html 逐个校验。
退出码 0 = 全部通过；1 = 有文件未通过；2 = 没找到文件。

校验的是「机械可判定」的部分：章节独立性、固定表头与列数、
埋点命名、描述列分块与逐条换行、data-preview 覆盖、
文档级 style 位置、章节编号连续性、
原型图的溯源与新鲜度（§3.9）、滚动联动的级别（§2.6 ⑧ / §3.4.3）、
原型里有没有「评审专用」内容（§3.10）。
视觉类检查（遮挡、字号、配色统一）仍需人工按 §4.3 / §4.6 核对。
"""
import sys
import os
import re
import json
from pathlib import Path
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}

CORE_SECTIONS = ["项目信息", "版本记录", "需求背景", "需求目标", "详细方案"]

SCHEMAS = {
    "version-table":  ["版本", "日期", "修订人", "修订说明"],
    "scheme-table":   ["一级模块", "二级功能", "原型", "描述"],
    "overview-table": ["模块", "一级功能", "说明"],
    "tracking-table": ["序号", "埋点名", "埋点中文名", "埋点类型", "埋点参数", "参数值"],
}

CN_NUM = "一二三四五六七八九十"


class Node:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def text(self):
        return "".join(x.text() if isinstance(x, Node) else x for x in self.children)

    def find(self, tag=None, css_class=None):
        result = []
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if (tag is None or child.tag == tag) and (
                css_class is None or css_class in child.attrs.get("class", "").split()
            ):
                result.append(child)
            result.extend(child.find(tag, css_class))
        return result

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()


class Tree(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.current = self.root
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent and node.tag != tag:
            node = node.parent
        if node.parent:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def _section_of(root):
    """Return a function mapping a node to the nearest preceding h2/h3 heading text."""
    heads = [(n, n.text().strip()) for n in root.walk() if n.tag in ("h2", "h3")]

    def lookup(node):
        found = ""
        for n, txt in heads:
            if n is node:
                break
            if n.tag == "h2":
                found = txt
        return found

    return lookup


def validate_prd(content):
    root = Tree(content).root
    h2 = [n.text().strip() for n in root.find("h2")]
    errors = []

    # ---- 1. 核心章节与独立性 ----
    for name in CORE_SECTIONS:
        if not any(h.endswith(name) for h in h2):
            errors.append("缺少独立章节：" + name)
    if any("项目信息" in h and "版本记录" in h for h in h2):
        errors.append("项目信息和版本记录必须分开成两张表/两个章节")
    if any(("边界" in h or "异常处理" in h) for h in h2):
        errors.append("不设独立的异常/边界章节；边界情况写进详细方案描述列的【边界说明】")

    # ---- 2. 章节编号连续性 ----
    numbered = []
    for h in h2:
        m = re.match(r"^([一二三四五六七八九十]+)、", h)
        if m:
            numbered.append((m.group(1), h))
    expected = list(CN_NUM[: len(numbered)])
    actual = [n for n, _ in numbered]
    if actual and actual != expected:
        errors.append("章节编号不连续（应从 一 开始顺排）：实际为 " + "、".join(actual))

    # ---- 3. 固定表头与列数 ----
    for css, expect in SCHEMAS.items():
        tables = root.find("table", css)
        required = css in {"version-table", "scheme-table"} or any(
            ("数据埋点" in h if css == "tracking-table"
             else "需求概述" in h if css == "overview-table" else False)
            for h in h2
        )
        if required and not tables:
            errors.append("缺少规范表格：" + css)
        for table in tables:
            rows = table.find("tr")
            if not rows:
                errors.append(css + " 没有表头行")
                continue
            heads = [c.text().strip() for c in rows[0].children
                     if isinstance(c, Node) and c.tag == "th"]
            if heads != expect:
                errors.append(css + " 表头必须为：" + "、".join(expect) + "（实际：" + "、".join(heads) + "）")

    # ---- 4. 项目信息必须独立双列表 ----
    meta = root.find("table", "meta-table")
    if not meta:
        errors.append("项目信息应使用独立 meta-table")
    else:
        for table in meta:
            for row in table.find("tr"):
                cells = [c for c in row.children if isinstance(c, Node) and c.tag in ("td", "th")]
                if len(cells) != 2:
                    errors.append("项目信息应为双列（字段 | 值）")
                    break

    # ---- 5. 详细方案：data-preview / 原型列 / 描述列 ----
    for table in root.find("table", "scheme-table"):
        rows = table.find("tr")
        for row in rows[1:]:
            cells = [c for c in row.children if isinstance(c, Node) and c.tag == "td"]
            if not cells:
                continue
            if "data-preview" not in row.attrs:
                errors.append("详细方案每行必须带 data-preview（供双栏滚动联动）")
            if len(cells) >= 3:
                proto = cells[-2]
                has_media = bool(proto.find("img") or proto.find("iframe"))
                if not has_media:
                    errors.append("原型列必须有内容（img.proto-shot 或可交互 iframe）")
            if "desc" not in cells[-1].attrs.get("class", "").split():
                errors.append("功能行末列应为 desc 描述单元格")
        for cell in table.find("td", "desc"):
            text = cell.text()
            if not all(label in text for label in ("【页面元素】", "【交互说明】")):
                errors.append("每个描述单元格必须包含【页面元素】和【交互说明】")
            if not cell.find(css_class="desc-block"):
                errors.append("描述应使用 desc-block 分块并逐条换行（不要用 <br> 硬换行）")
            for block in cell.find(css_class="desc-block"):
                items = [n for n in block.children
                         if isinstance(n, Node) and n.tag in ("p", "ol", "ul")]
                if not items:
                    errors.append("描述分块需要独立段落或列表")
            for line in cell.find("p") + cell.find("li"):
                if len(re.findall(r"(?:^|\s|[；;])\d+[、．.]", line.text())) > 1:
                    errors.append("每个元素或交互必须独立成段（多个编号不能挤在一句里）")
            if cell.find("br"):
                errors.append("描述列不要用 <br> 硬换行，改用独立 <p>")

    # ---- 6. 埋点命名与列数 ----
    for table in root.find("table", "tracking-table"):
        rows = table.find("tr")
        for row in rows[1:]:
            cells = [c for c in row.children if isinstance(c, Node) and c.tag == "td"]
            if not cells:
                continue
            if len(cells) != 6:
                errors.append("埋点表每行必须有六列（缺的格写「待确认（用户提供参考）」，不要留空）")
                continue
            event = cells[1].text().strip()
            if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", event) or len(event) > 48:
                errors.append("埋点名需要简短英文 snake_case：" + event)

    # ---- 7. 文档级 style 必须在 #prdContent 内（一键复制全文才带得走样式）----
    # 只做"存在性"判定：<head> 放公共骨架样式、正文样式放 <main> 内是正常分工，
    # 但 #prdContent 内必须至少有一份正文样式，否则复制出去的正文会掉格式。
    main_nodes = [m for m in root.find("main") if m.attrs.get("id") == "prdContent"]
    if not main_nodes:
        errors.append("缺少 <main id=\"prdContent\"> 正文容器")
    elif not any(m.find("style") for m in main_nodes):
        errors.append("#prdContent 内没有正文 <style>；一键复制全文会丢掉正文排版样式")

    # ---- 7b. 骨架三件套（v2.8）----
    # 只有"存在 style"这一条判据是不够的：v2.7 给骨架补的那三条样式，实测被一份
    # 号称"用最新 skill 做的" PRD 全数抄漏——它照抄了上一版 PRD 的结构，而不是
    # 从 scripts/prd-content.html 复制骨架。结果流程图 iframe 掉回浏览器默认的
    # 300×150（实测渲染高度 154px），而校验器一条都没报。现在逐条点名。
    # 只在文档真的用到对应元素时才查，避免误报没画流程图的需求。
    m_region = re.search(r'<main[^>]*\bid\s*=\s*["\']prdContent["\'][^>]*>(.*?)</main>',
                         content, re.S)
    if m_region:
        css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", m_region.group(1), re.S))
        if re.search(r"table-layout\s*:\s*fixed", css) is None:
            errors.append("正文样式里没有 `table-layout: fixed`——骨架三件套之一（§2.2）。"
                          "缺它时 `colgroup` 只算建议值，任何宽内容都能把表格撑破："
                          "实测 `<img width=\"1600\">` 包 3200px 的 PNG 把四列表格撑到 "
                          "`scrollWidth 1811 > 视口 1500`。从 scripts/prd-content.html 复制骨架，别照抄旧 PRD")
        if re.search(r'class\s*=\s*["\'][^"\']*\bproto-shot\b', content) and \
           re.search(r"\.proto-shot\s*\{[^}]*max-width", css) is None:
            errors.append("正文样式里 `.proto-shot` 没有 `max-width: 100%`——骨架三件套之一（§2.2）。"
                          "原型图会按 PNG 真实宽度撑开表格；另检查 `<img class=\"proto-shot\">` "
                          "上有没有写死 `width=`/`height=`（写死就绕过 CSS）")
        if re.search(r'class\s*=\s*["\'][^"\']*\bflow-frame\b', content) and \
           re.search(r"\.flow-frame\s*\{[^}]*height", css) is None:
            errors.append("正文样式里 `.flow-frame` 没有 height——骨架三件套之一（§2.2）。"
                          "不给尺寸的 iframe 会掉回浏览器默认的 300×150（实测渲染出来只有 154px），"
                          "整章流程图缩成一条。骨架给的是 `height: 800px`，`.screen-frame` 给 1150px")

    # ---- 8. 需求目标不应是任务清单 ----
    goal_tables = root.find("table", "goal-table")
    for tbl in goal_tables:
        rows = tbl.find("tr")
        heads = [c.text().strip() for c in rows[0].children
                 if isinstance(c, Node) and c.tag == "th"] if rows else []
        if heads != ["用户结果", "衡量指标", "统计口径", "预期方向", "目标值"]:
            errors.append("goal-table 表头必须为：用户结果、衡量指标、统计口径、预期方向、目标值")

    if errors:
        raise ValueError("PRD 格式检查未通过：\n" + "\n".join(dict.fromkeys(errors)))
    return True


def validate_provenance(prd_path):
    """§3.9 PRD ↔ 原型代码 强绑定里「机械可判定」的那部分。

    查两件必真的事：
      ① PRD 里 <img class="proto-shot"> 引用的图文件**必须真实存在**；
      ② 该图的 mtime **不得早于**本次原型代码的 mtime（图比代码旧 = 忘了重渲染）。

    判不了的情况一律**跳过、不报错**，避免假阳性：
      · 落点 A/C —— 原型代码在宿主产品库里，不在需求目录下；
      · 整份 PRD 都用 iframe（没有静态图）；
      · 需求目录下找不到任何原型 HTML 可比。
    §3.9 的其余部分（图是不是本次真渲染的、代码有没有被改）仍需人工按自证清单走。
    """
    errors = []
    text = prd_path.read_text(encoding="utf-8")
    req_dir = prd_path.parent.parent          # [需求名]/需求文档/x-PRD.html → [需求名]/

    shots = re.findall(r'<img[^>]*\bclass="[^"]*\bproto-shot\b[^"]*"[^>]*>', text)
    shots += re.findall(r'<img[^>]*\bsrc="([^"]+)"[^>]*\bclass="[^"]*\bproto-shot\b[^"]*"', text)
    srcs = []
    for tag in shots:
        m = re.search(r'\bsrc="([^"]+)"', tag) if tag.startswith("<img") else None
        srcs.append(m.group(1) if m else tag)
    if not srcs:
        return errors

    # 原型代码候选（落点 B）：优先 [需求名]/原型/ 下的 HTML；
    # 退一步用需求目录下的 HTML，但排除 PRD 自身与流程图（流程图有自己的截图与校验）。
    proto_root = req_dir / "原型"
    code_files = sorted(proto_root.rglob("*.html")) if proto_root.is_dir() else []
    if not code_files:
        code_files = [p for p in sorted(req_dir.rglob("*.html"))
                      if "流程图" not in p.parts and "需求文档" not in p.parts]
    newest = max((p.stat().st_mtime for p in code_files), default=None)

    for src in srcs:
        if src.startswith(("http:", "https:", "data:", "//")):
            continue
        img = (prd_path.parent / src).resolve()
        if not img.exists():
            errors.append("原型图文件不存在：" + src
                          + "（§3.9 铁律 2：图必须由原型代码渲染产出；缺图往往是路径改了没重出图）")
            continue
        if newest is not None and img.stat().st_mtime < newest:
            errors.append("原型图比原型代码旧、需要重渲染：" + src
                          + "（图 mtime < 原型代码 [" + str(code_files[0].name) + " …] 的 mtime，§3.9 铁律 2）")
    return errors


def _resolve_local(url, bases):
    """把 PRD 里出现的原型 URL 尽力解析成本地路径；解析不出来就返回 None（不报错）。"""
    if not url:
        return None
    from urllib.parse import unquote
    u = unquote(url.strip().strip("'\""))
    if u.startswith("file:///"):
        raw = u[len("file:///"):]
        if re.match(r"^[A-Za-z]:", raw):
            return Path(raw)
        return Path("/" + raw)
    if u.startswith(("http://", "https://", "//", "data:")):
        return None
    try:
        p = Path(u)
        if p.is_absolute() and p.is_file():
            return p
    except (OSError, ValueError):
        pass
    for b in bases:
        try:
            p = (b / u).resolve()
        except (OSError, ValueError):
            continue
        if p.is_file():
            return p
    return None


def _registry_keys(proto_html):
    """读原型 HTML 里的机器可读注册表 #pm-preview-registry（§3.4.3）。没有就返回 None。"""
    m = re.search(
        r'<script[^>]*id=["\']pm-preview-registry["\'][^>]*>(.*?)</script>',
        proto_html, re.S | re.I)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    states, focus = set(), set()
    for page in (data.get("pages") or []):
        if isinstance(page, dict):
            states.update(page.get("states") or [])
            focus.update(page.get("focus") or [])
    states.update(data.get("states") or [])
    focus.update(data.get("focus") or [])
    return {"states": states, "focus": focus}


def _prototype_files(prd_path, text):
    """尽力解析出这份 PRD 引用的**原型 HTML 的本地路径**（§3.4.3 / §3.10 共用）。

    认三种写法：`PRD_REPO` 常量拼出的绝对路径、`CATALOG.url` / `XXX_DIR` 之类前缀、
    以及 PRD 里出现的任意 `*.html` 字符串字面量。解析不出来就返回空列表——
    调用方一律**跳过、不报错**，避免在"原型在别的盘 / 整份 PRD 全用 iframe"时制造假阳性。
    """
    from urllib.parse import unquote
    bases = [prd_path.parent, prd_path.parent.parent, Path.cwd()]
    prefixes = [unquote(m.group(2)) for m in
                re.finditer(r"""(\w+)\s*=\s*['"]([^'"]*/)['"]""", text)]
    for m in re.finditer(r"""PRD_REPO\s*=\s*['"]([^'"]+)['"]""", text):
        rp = _resolve_local(m.group(1), bases)
        if rp:
            bases.insert(0, rp)

    names = {unquote(n) for n in re.findall(r"""['"]([^'"]+\.html)['"]""", text)}
    found = []
    for n in sorted(names):
        p = _resolve_local(n, bases)
        if p is None:
            for pre in prefixes:
                p = _resolve_local(pre + n, bases)
                if p is not None:
                    break
        if p is not None and p.is_file() and p != prd_path and p not in found:
            found.append(p)
    return found


def validate_scroll_sync(prd_path):
    """§2.6 ⑧ / §3.4.3 里「机械可判定」的那部分：滚动联动到底做到第几级。

    查两件事：
      ① 同一 data-preview 取值下，若有多行在 (state, focus) 上**完全相同**，这些行在右侧
         预览里互相不可区分 —— 滚过去什么都不会变，就是"只做到页面级"的典型症状。
      ② 若能从原型 HTML 里读到 #pm-preview-registry，则逐个对账 PRD 引用的
         data-preview-state / data-preview-focus 是否真的存在。
    查不了的一律跳过不报错（原型在别的盘、PRD 全用 iframe、没写注册表等）。
    """
    errors = []
    text = prd_path.read_text(encoding="utf-8")

    rows = []
    for tr in re.findall(r"<tr\b[^>]*>", text, re.I):
        m = re.search(r'\bdata-preview="([^"]*)"', tr)
        if m is None:
            continue
        st = re.search(r'\bdata-preview-state="([^"]*)"', tr)
        fo = re.search(r'\bdata-preview-focus="([^"]*)"', tr)
        rows.append((m.group(1), st.group(1) if st else "", fo.group(1) if fo else ""))
    if not rows:
        return {"errors": errors, "stats": None}

    # ---- ① 同页多行不可区分 ----
    seen = {}
    for page, state, focus in rows:
        seen.setdefault(page, []).append((state, focus))
    for page, combos in seen.items():
        dup = {c for c in combos if combos.count(c) > 1}
        for state, focus in sorted(dup):
            if not state and not focus:
                errors.append(
                    "滚动联动只到页面级：%s 下有 %d 行没有任何 data-preview-state / "
                    "-focus，滚过这些行右侧预览完全不变（§2.6 ⑧）"
                    % (page, combos.count((state, focus))))
            else:
                errors.append(
                    "滚动联动的 %s 下有 %d 行 state/focus 完全相同（%s），右侧不可区分"
                    % (page, combos.count((state, focus)), state or focus))

    # ---- ② 与原型注册表对账（best effort）----
    used_states = {r[1] for r in rows if r[1]}
    used_focus = {r[2] for r in rows if r[2]}
    stats = {"rows": len(rows), "pages": len(seen),
             "states": len(used_states), "focus": len(used_focus), "registry": "未找到"}

    if used_states or used_focus:
        found = {}
        for p in _prototype_files(prd_path, text):
            try:
                reg = _registry_keys(p.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            if reg is not None:
                found[p.name] = reg

        if found:
            stats["registry"] = "、".join(sorted(found)) + "（%d 个）" % len(found)
            all_states = set().union(*[r["states"] for r in found.values()])
            all_focus = set().union(*[r["focus"] for r in found.values()])
            for s in sorted(used_states - all_states):
                errors.append("PRD 引用的 data-preview-state 在原型注册表里不存在：" + s + "（§3.4.3）")
            for f in sorted(used_focus - all_focus):
                errors.append("PRD 引用的 data-preview-focus 在原型注册表里不存在：" + f + "（§3.4.3）")
        else:
            errors.append(
                "PRD 用了 data-preview-state / -focus，但解析不到任何原型注册表（#pm-preview-registry）"
                "——无法确认这些 key 真实存在，滚动联动可能静默失效（§3.4.3）")
    return {"errors": errors, "stats": stats}


# §3.10：「评审专用」内容的字样。只收**无歧义**的——出现即说明原型在自我声明"这是假数据/仅供参考"。
REVIEW_MARKERS = [
    "非客户真实使用", "用于产品评审", "仅供评审", "评审专用", "交互评审",
    "此原型", "本原型", "演示数据",
]


def _strip_comments(src):
    """去掉 HTML / JS / CSS 注释，只留下**真正会被渲染或被执行**的文本。

    「演示数据」这类词写在注释里是合法用法（实测：`/* 首次进入时的演示数据。真实环境由服务端下发。 */`），
    只有出现在会被渲染出来的字符串里才算「评审专用内容」。
    替换成等量换行，保证报出来的行号仍对应原文件。
    """
    src = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    src = re.sub(r"(?m)^[ \t]*//.*$", "", src)
    return src


def _surface_files(prd_path, text):
    """§3.10 要扫的文件集合 = 原型 HTML 本身 + 它们**本地**引用的脚本 / 样式表。

    反例里的「演示数据」横幅是宿主页 `ResourcePanel.html` 引的 `resource-panel.js` 注入的——
    只扫 HTML 会漏掉，所以要把 `<script src>` / `<link rel=stylesheet href>` 里能解析成本地
    文件的一并纳入（远程 CDN / `data:` 一律跳过，`?v=…` 这类缓存串先剥掉）。
    """
    out = list(_prototype_files(prd_path, text))
    for html in list(out):
        try:
            src = html.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        refs = re.findall(r'<script[^>]*\bsrc=["\']([^"\']+)["\']', src, re.I)
        refs += re.findall(r'<link[^>]*\bhref=["\']([^"\']+)["\']', src, re.I)
        for r in refs:
            p = _resolve_local(r.split("?")[0], [html.parent])
            if p is not None and p.is_file() and p not in out:
                out.append(p)
    return out


def validate_surface(prd_path):
    """§3.10：原型里不许出现「评审专用」内容（免责横幅 / 角标 / 导航栏评审标签 …）。

    做法：解析出本次的原型 HTML 及其本地引用的脚本/样式（见 `_surface_files`），
    **去掉注释后**逐行扫 REVIEW_MARKERS，命中就报「文件:行号 + 命中词」，让人能直接定位到那行代码。

    只扫得到"写死在原型里的字样"这一层；"某个元素虽然不叫演示数据、但产品上线后根本不会有"
    这类仍需人工按 §3.10 的 30 秒自检逐屏过。解析不出原型文件时一律跳过。
    """
    errors = []
    files = _surface_files(prd_path, prd_path.read_text(encoding="utf-8"))
    for p in files:
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(_strip_comments(raw).splitlines(), 1):
            hit = next((mk for mk in REVIEW_MARKERS if mk in line), None)
            if hit:
                errors.append("原型里出现「评审专用」内容：%s:%d 命中「%s」"
                              "——产品真上线后不会出现的东西不要写进原型（§3.10）"
                              % (p.name, lineno, hit))
    return {"errors": errors, "stats": {"files": len(files)}}


# §2.10：顶栏六个固定导航。**顺序也是约定的一部分**（双栏预览 / 编辑 / 撤销 / 保存 / 交互原型 / 静态图册）。
TOPBAR_NAV_ORDER = ["dual-pane", "edit", "undo", "save", "prototype", "gallery"]
NAV_LABEL = {"dual-pane": "双栏预览", "edit": "编辑", "undo": "撤销",
             "save": "保存", "prototype": "交互原型", "gallery": "静态图册"}


def _pm_navs(text):
    """按出现顺序取 `data-pm-nav` 的取值。"""
    return re.findall(r'data-pm-nav\s*=\s*["\']([^"\']+)["\']', text)


def _pm_tb_text(text):
    """标题栏三段文案（mark / name / ver），用来核对图册页与 PRD 页是否统一。"""
    return [re.sub(r"\s+", " ", t).strip() for t in
            re.findall(r'class\s*=\s*["\'][^"\']*\btb-(?:mark|name|ver)\b[^"\']*["\'][^>]*>([^<]*)<', text)]


def _pm_links(prd_path, text):
    """尽力解出 `window.PM_LINKS = { gallery:'…', prototype:'…' }`，并以 PRD 所在目录为基准转成路径。"""
    block = re.search(r"PM_LINKS\s*=\s*\{(.*?)\}", text, re.S)
    if not block:
        return {}
    out = {}
    for key, val in re.findall(r"(gallery|prototype)\s*:\s*[\"']([^\"']*)[\"']", block.group(1)):
        val = val.strip()
        if not val:
            continue
        p = (prd_path.parent / val.split("#")[0].split("?")[0]).resolve()
        out[key] = p
    return out


def validate_topbar(prd_path):
    """§2.10：PRD 顶栏六个固定导航 + 编辑门禁外壳 + 图册页统一 + 交互原型页无导航。

    能机械判定的只有"外壳在不在、结构对不对"这一层：
      * 六个 `data-pm-nav` 齐不齐、顺序对不对、顶栏在不在 `#prdContent` 之外；
      * 有没有残留的右下角 `.fab-group` / `.save-btn-container`（会出现两个保存按钮）；
      * 静态图册页的导航与标题栏是否与 PRD 页逐项一致；
      * 交互原型页有没有被加上我方顶栏；项目里有没有残留 `*-prototype-flow.html` 薄外壳。

    **"游客态是不是真的一个 contenteditable 都没挂""保存后记录四列是不是都填上了"要人工实测**
    （见 §5.2 对应两条）——那需要跑浏览器，脚本这一层做不到。
    """
    errors = []
    text = prd_path.read_text(encoding="utf-8")
    navs = _pm_navs(text)

    # ① 六个导航
    if not navs:
        errors.append("PRD 里没有找到顶栏导航（data-pm-nav）——v2.5 起每份 PRD 都要有右上角六个固定入口（§2.10 ①）")
    elif navs != TOPBAR_NAV_ORDER:
        missing = [n for n in TOPBAR_NAV_ORDER if n not in navs]
        extra = [n for n in navs if n not in TOPBAR_NAV_ORDER]
        detail = []
        if missing:
            detail.append("缺：" + "、".join(NAV_LABEL[n] for n in missing))
        if extra:
            detail.append("多出：" + "、".join(extra))
        if not detail:
            detail.append("顺序是 " + " → ".join(navs))
        errors.append("顶栏六个导航不齐或顺序不对（§2.10 ①）：%s；应为 %s"
                      % ("；".join(detail), " → ".join(NAV_LABEL[n] for n in TOPBAR_NAV_ORDER)))

    # ② 顶栏必须在 #prdContent 之外
    m_top = re.search(r'data-pm-topbar\s*=', text)
    m_main = re.search(r'id\s*=\s*["\']prdContent["\']', text)
    if m_top and m_main and m_top.start() > m_main.start():
        errors.append("顶栏出现在 #prdContent 之内——它会被「一键复制全文」一起复制出去，"
                      "必须放在 <body> 下、#prdContent 之前（§2.10 ⑤）")

    # ③ 不许残留右下角悬浮区（v2.5 起动作入口全部收口到顶栏）
    for cls, label in (("fab-group", "双栏预览/保存悬浮组"), ("save-btn-container", "保存按钮容器")):
        if re.search(r'class\s*=\s*["\'][^"\']*\b%s\b' % cls, text):
            errors.append("页面里仍残留 `.%s`（%s）——v2.5 起这两个动作已并入顶栏，"
                          "留着会出现两个保存按钮且状态不同步（§2.10 ⑤）" % (cls, label))

    # ③b v2.6：六个导航右侧要有工具区，「重新出图」不许带 data-pm-nav（§2.11 ③）
    if m_top:
        if not re.search(r'class\s*=\s*["\'][^"\']*\btopbar-tools\b', text):
            errors.append("顶栏没有 `.topbar-tools` 工具区——v2.6 起「重新出图」（§2.11）"
                          "长在六个固定导航右侧、用一道竖线与导航分隔，别塞进 `.topbar-actions`")
        elif not re.search(r'id\s*=\s*["\']navRefigure["\']', text):
            errors.append("`.topbar-tools` 里没有 `#navRefigure`（「重新出图」按钮，§2.11 ③）")
        m_rf = re.search(r'<button[^>]*id\s*=\s*["\']navRefigure["\'][^>]*>', text)
        if m_rf and re.search(r'data-pm-nav\s*=', m_rf.group(0)):
            errors.append("「重新出图」按钮带了 `data-pm-nav`——它会变成第七个固定导航，"
                          "破坏 §2.10 ① 的「不增不减」；它是「工具」不是「导航」（§2.11 ③）")

    # ③c v2.7：「重新出图」不能只是个摆设。
    #   实测交付过一份 PRD：顶栏外壳、`#navRefigure` 按钮全都在，validate 全绿——
    #   但按钮**一点反应都没有**，因为配套的 JS 压根没写。这类"结构合规、功能缺失"
    #   是机器以前唯一查不出、而用户最容易踩的坑（点了没反应只会以为服务坏了）。
    if m_top and re.search(r'id\s*=\s*["\']navRefigure["\']', text):
        m_rf2 = re.search(r'<button[^>]*id\s*=\s*["\']navRefigure["\'][^>]*>', text)
        if m_rf2 and not re.search(r'\bhidden\b', m_rf2.group(0)):
            errors.append("「重新出图」按钮没有 `hidden` 属性——规范要求它**初始隐藏**，"
                          "登录且可写时才由前端放出来；游客看到一个用不了的按钮只会以为文档坏了（§2.11 ③）")
        has_status = re.search(r'(PMService\s*\.\s*figureStatus|loadFigureStatus)', text)
        has_action = re.search(r'(PMService\s*\.\s*refigure|refigureAll)', text)
        if not (has_status and has_action):
            miss = []
            if not has_status:
                miss.append("拉状态（`PMService.figureStatus` 或 `loadFigureStatus`）")
            if not has_action:
                miss.append("触发重出（`PMService.refigure` 或 `refigureAll`）")
            errors.append("「重新出图」按钮在，但前端没接服务端，缺 %s——"
                          "光有按钮点下去不会发出任何请求。§2.11 ⑤ 要求前端至少做两件事："
                          "拉 `/api/figure-status` 给落后的图描边、点按钮调 `/api/refigure`"
                          % "、".join(miss))
    
    # ④ 静态图册页：导航与标题栏必须与 PRD 页逐项一致
    links = _pm_links(prd_path, text)
    stats = {"navs": len(navs), "gallery": 0, "prototype": 0}
    gallery = links.get("gallery")
    if gallery is not None:
        if not gallery.is_file():
            errors.append("顶栏「静态图册」指向的文件不存在：%s（要么补上，要么把这个入口去掉，"
                          "不要留死链——§2.10 ①）" % gallery)
        else:
            gtext = gallery.read_text(encoding="utf-8", errors="ignore")
            gnavs = _pm_navs(gtext)
            stats["gallery"] = 1
            if gnavs != navs:
                errors.append("静态图册页的顶栏导航与 PRD 页不一致（§2.10 ⑥）：%s；PRD 页是 %s"
                              % (" → ".join(gnavs) or "（没有顶栏）", " → ".join(navs)))
            if _pm_tb_text(gtext) != _pm_tb_text(text) and _pm_tb_text(text):
                errors.append("静态图册页的标题栏文案与 PRD 页不一致（§2.10 ⑥）：%s；PRD 页是 %s"
                              % (_pm_tb_text(gtext) or "（没有标题栏）", _pm_tb_text(text)))
            # v2.6：图册页要照抄同一套外壳（含工具区），差异交给模块按 data-pm-topbar 自判；
            # 缺了工具区说明是"又抄了一版"，两页并排就会露馅（§2.10 ⑥）
            if re.search(r'\btopbar-tools\b', text) and not re.search(r'\btopbar-tools\b', gtext):
                errors.append("静态图册页缺少 `.topbar-tools`（PRD 页有）——图册页要复用同一套"
                              "顶栏外壳，「重新出图」按钮由模块按 data-pm-topbar 自动隐藏，"
                              "不要在两页里各写一版（§2.10 ⑥）")
            # v2.7：「重新出图」是"对这份 PRD 重出图"的动作，图册页里它没有对象。
            # 实测图册页把它原样显示出来了——点下去要么没反应、要么重出了别的文档。
            g_rf = re.search(r'<button[^>]*id\s*=\s*["\']navRefigure["\'][^>]*>', gtext)
            if g_rf and not re.search(r'\bhidden\b', g_rf.group(0)):
                errors.append("静态图册页的「重新出图」按钮没有 `hidden`——图册页复用同一套顶栏外壳，"
                              "但这个按钮在图册页没有作用对象，必须隐藏（§2.11 ③）")

    # ⑤ 交互原型页：不许加本流程的导航外壳
    proto = links.get("prototype")
    if proto is not None:
        if not proto.is_file():
            errors.append("顶栏「交互原型」指向的文件不存在：%s（没产出就把该入口去掉或置灰，§2.10 ①）" % proto)
        else:
            ptext = proto.read_text(encoding="utf-8", errors="ignore")
            stats["prototype"] = 1
            if re.search(r'data-pm-topbar\s*=', ptext) or _pm_navs(ptext):
                errors.append("交互原型页 %s 里出现了本流程的顶栏（data-pm-topbar / data-pm-nav）"
                              "——按 §2.10 ⑦ 它要保持原功能代码的展示，不加导航" % proto.name)

    # ⑥ 薄外壳（v2.5 明令不许）
    demand_dir = prd_path.parent.parent
    try:
        shells = sorted(p.name for p in demand_dir.rglob("*prototype-flow*.html"))
    except OSError:
        shells = []
    if shells:
        errors.append("发现「可交互原型薄外壳」文件：%s ——v2.5 起不许单独写 -prototype-flow.html，"
                      "直接在宿主代码上改（§3.8 / §2.10 ⑦）" % "、".join(shells[:3]))

    return {"errors": errors, "stats": stats}


def _project_root(prd):
    """PRD 所在的项目根：向上找带 .pm-workflow / .agents/workflows / scripts 的那一层。"""
    p = prd.resolve().parent
    for _ in range(8):
        if (p / ".pm-workflow").is_dir() or (p / ".agents" / "workflows").is_dir() \
           or (p / "scripts" / "validate_prd.py").is_file():
            return p
        p = p.parent
    return None


def _installer_path():
    """找 initialize.py：可能在 skill 源目录，也可能在项目里的 skill 副本。"""
    p = Path(__file__).resolve().parent
    for _ in range(6):
        for cand in (p / "scripts" / "initialize.py",
                     p / "initialize.py",
                     p / ".agents" / "skills" / "edu-pm-workflow-v2" / "scripts" / "initialize.py"):
            if cand.is_file():
                return cand
        p = p.parent
    return None


def _not_installed_msg(prd):
    """v2.8 硬门禁：项目没装 skill 就交付 PRD，等于交一份「图一定取不到」的文档。

    实测（2026-10-15）：一个从没跑过安装器的项目目录，PRD / 原型 / 截图一应俱全，
    但连 `.pm-workflow/` 都没有 —— 没有 runtime.json（没有端口）、没有 users.json，
    本地导出服务根本起不来，打开就是黄框「N 张原型截图未加载」。而在此之前
    skill 对"项目装没装"完全不校验：它只在"安装那一刻"存在。
    """
    root = _project_root(prd)
    if root is not None and (root / ".pm-workflow" / "runtime.json").is_file():
        return None
    init = _installer_path()
    # 没找到项目根时按标准结构回退：`<项目根>/<需求名>/需求文档/x-PRD.html`
    # → parents[0]=需求文档、[1]=<需求名>、[2]=项目根。直接拿 parent 会把项目根
    # 指成"需求文档"目录，安装命令就装错地方了。
    ps = prd.resolve().parents
    target = root or (ps[2] if len(ps) >= 3 else prd.resolve().parent)
    cmd = ('python "%s" --project "%s"' % (init, target)) if init else \
          ('python <skill目录>/scripts/initialize.py --project "%s"' % target)
    return ("这个项目目录没有 `.pm-workflow/runtime.json` —— **本项目没装 skill**（§5.2 硬门禁）。\n"
            "没装就没有 runtime.json（没有端口）、没有 users.json，本地导出服务起不来，\n"
            "PRD 里的原型图与流程图一律取不到：实测打开后顶部黄框报「N 张原型截图未加载」。\n"
            "先装一次（装完再重跑本脚本）：" + cmd + "\n"
            "只是临时校验一份不属于本项目的 PRD 时，加 `--allow-uninstalled` 跳过这一条。")


def main(argv):
    args = argv[1:]
    allow_uninstalled = "--allow-uninstalled" in args
    paths = [a for a in args if not a.startswith("--")]
    if paths:
        files = [Path(p) for p in paths]
    else:
        # 默认只扫 `[需求名]/需求文档/*-PRD.html`——项目里的历史 PRD / 分享源文件 /
        # 需求挖掘目录下的旧稿不按本规范撰写，扫进来只会制造噪音。
        files = sorted(Path.cwd().glob("*/需求文档/*-PRD.html"))
        if not files:
            files = sorted(Path.cwd().glob("*-PRD.html"))
    if not files:
        print("没有找到 *-PRD.html（可显式传入路径，或在本项目根目录运行）")
        return 2

    failed = 0
    for path in files:
        try:
            if not allow_uninstalled:
                miss = _not_installed_msg(path)
                if miss:
                    raise ValueError(miss)
            validate_prd(path.read_text(encoding="utf-8"))
            provenance = validate_provenance(path)
            if provenance:
                raise ValueError("原型图溯源检查未通过（§3.9）：\n" + "\n".join(dict.fromkeys(provenance)))
            sync = validate_scroll_sync(path)
            if sync["errors"]:
                raise ValueError("滚动联动检查未通过（§2.6 ⑧ / §3.4.3）：\n"
                                 + "\n".join(dict.fromkeys(sync["errors"])))
            surface = validate_surface(path)
            if surface["errors"]:
                raise ValueError("原型「评审专用」内容检查未通过（§3.10）：\n"
                                 + "\n".join(dict.fromkeys(surface["errors"])))
            topbar = validate_topbar(path)
            if topbar["errors"]:
                raise ValueError("顶栏 / 登录门禁检查未通过（§2.10）：\n"
                                 + "\n".join(dict.fromkeys(topbar["errors"])))
            line = "PASS  " + str(path)
            s = sync["stats"]
            if s:
                line += ("\n      [滚动联动] %d 行 / %d 页 / state %d 个 / focus %d 个 / 注册表：%s"
                         % (s["rows"], s["pages"], s["states"], s["focus"], s["registry"]))
            if surface["stats"]["files"]:
                line += ("\n      [原型洁净度] 扫描 %d 个原型文件，未发现「评审专用」内容（§3.10）"
                         % surface["stats"]["files"])
            t = topbar["stats"]
            if t.get("navs"):
                line += ("\n      [顶栏门禁] %d 个固定导航齐全；静态图册 %s / 交互原型 %s（§2.10）"
                         % (t["navs"], "已核对" if t.get("gallery") else "未引用",
                            "已核对（未加导航）" if t.get("prototype") else "未引用"))
            print(line)
        except ValueError as exc:
            failed += 1
            print("FAIL  " + str(path))
            for line in str(exc).splitlines()[1:]:
                print("      " + line)
        except OSError as exc:
            failed += 1
            print("ERROR " + str(path) + " —— " + str(exc))
    print("\n共 %d 个文件，%d 个未通过。" % (len(files), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
