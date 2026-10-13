#!/usr/bin/env python3
"""PRD 格式校验（v2.9 工作流 §5.2 的第一步）。

用法：
    python3 validate_prd.py [需求名/需求文档/需求名-PRD.html ...]
    py -3 validate_prd.py …            # Windows 上没有 python3 命令

不带参数时，从当前目录向下查找所有 *-PRD.html 逐个校验。
退出码 0 = 全部通过；1 = 有文件未通过；2 = 没找到文件。

校验的是「机械可判定」的部分：章节独立性、固定表头与列数、
埋点命名、描述列分块与逐条换行、data-preview 覆盖、
文档级 style 位置、章节编号连续性、原型图的溯源与新鲜度（§3.9）。
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
        from urllib.parse import unquote
        bases = [prd_path.parent, prd_path.parent.parent, Path.cwd()]
        prefixes = [m.group(2) for m in
                    re.finditer(r"""(\w+)\s*=\s*['"]([^'"]*/)['"]""", text)]
        prefixes = [unquote(p) for p in prefixes]
        for m in re.finditer(r"""PRD_REPO\s*=\s*['"]([^'"]+)['"]""", text):
            rp = _resolve_local(m.group(1), bases)
            if rp:
                bases.insert(0, rp)

        names = {unquote(n) for n in re.findall(r"""['"]([^'"]+\.html)['"]""", text)}
        proto_files = {}
        for n in sorted(names):
            p = _resolve_local(n, bases)
            if p and p.is_file():
                proto_files[p] = True
                continue
            for pre in prefixes:
                p = _resolve_local(pre + n, bases)
                if p and p.is_file():
                    proto_files[p] = True
                    break
        found = {}
        for p in proto_files:
            if p == prd_path:
                continue
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


def main(argv):
    if len(argv) > 1:
        files = [Path(p) for p in argv[1:]]
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
            validate_prd(path.read_text(encoding="utf-8"))
            provenance = validate_provenance(path)
            if provenance:
                raise ValueError("原型图溯源检查未通过（§3.9）：\n" + "\n".join(dict.fromkeys(provenance)))
            sync = validate_scroll_sync(path)
            if sync["errors"]:
                raise ValueError("滚动联动检查未通过（§2.6 ⑧ / §3.4.3）：\n"
                                 + "\n".join(dict.fromkeys(sync["errors"])))
            line = "PASS  " + str(path)
            s = sync["stats"]
            if s:
                line += ("\n      [滚动联动] %d 行 / %d 页 / state %d 个 / focus %d 个 / 注册表：%s"
                         % (s["rows"], s["pages"], s["states"], s["focus"], s["registry"]))
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
