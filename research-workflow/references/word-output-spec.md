# Word output spec

Word-with-screenshots is the right artifact when the evidence is visual: UI, product appearance, hardware, dashboards, page layout, architecture diagrams. The screenshot is the evidence; the text only points at what is visible.

## When Word is correct

Use it when a reader must *see* the thing:

- 产品界面 / App 截图 / 控制台
- 硬件外观、接口、尺寸、安装形态
- 官网首页与关键页面布局
- 架构图、流程图、拓扑图
- 实物照片、包装、配件

**If a screenshot could be replaced by a table cell without loss, it belongs in Excel instead.** Do not pad a Word doc with decorative screenshots — each image must be the reason the section exists.

## Screenshot rules

**Capture the real page.** Never substitute a text description for an image; the whole value is that this is what the product actually looks like.

Use the bundled script:

```bash
python scripts/shoot.py urls.txt -o images/ --width 1440 --height 900 --full-page
```

`urls.txt` is one URL per line, `#` starts a comment line. The script runs headless Chrome, crops scrollbars, and names files by domain plus index so they stay traceable.

**Width choice matters.** `--width 1440` suits desktop UI. Use `--width 768` for mobile screenshots. Very tall `--full-page` captures of long pages produce images that are unreadable once scaled into a Word page — prefer capturing the top section (`--height 900`, no `--full-page`) unless the whole page is genuinely the point.

**Handle failures explicitly:**
- Login wall or paywall → this entity's material is unavailable. Record it in the Word doc as a note, and in the未获取 list. Do not substitute a stock photo.
- Blank render (JS-heavy SPA, headless timeout) → retry once with a longer `--wait`. Still blank → say so in the output.
- Cookie/consent modal covering content → note it. A screenshot of a consent dialog is not evidence, and the reader will know something is wrong.

**Screenshot hygiene:** no cookie banners, no personal account data, no notification badges with the user's name in them. Blur or crop before embedding.

## Data JSON schema

`build_docx.py` consumes this file:

```json
{
  "title": "AI 会议一体机产品调研",
  "subtitle": "5 款产品的形态与界面对比",
  "meta": [
    { "label": "调研范围", "value": "5 款主流产品" },
    { "label": "采集时间", "value": "2026-10-03" },
    { "label": "候选网页", "value": "24 个, 精读 17 个" }
  ],
  "sections": [
    {
      "heading": "一、产品形态",
      "intro": "5 款产品中 3 款为桌面一体机, 2 款为会议室主机。",
      "blocks": [
        { "type": "image", "src": "images/a-com-01.png", "caption": "产品A 官网首页, 一体机形态为桌面放置", "source": "https://example.com" },
        { "type": "para", "text": "产品A 的接口集中在机身背面, 走线不外露。" },
        { "type": "kv", "items": [["尺寸", "320×180×45 mm"], ["重量", "4.2 kg"], ["安装", "桌面放置"]] },
        { "type": "table", "columns": ["产品", "形态", "接口位置"], "rows": [["A", "桌面一体机", "背面"], ["B", "桌面一体机", "背面"], ["C", "会议室主机", "机架式"]] },
        { "type": "bullets", "items": ["3 款支持壁挂", "仅 1 款支持 PoE 供电"] }
      ]
    }
  ],
  "sources": [
    { "label": "产品A 官网", "url": "https://example.com", "accessed": "2026-10-03" }
  ]
}
```

Block types:

| `type` | Fields | Use |
|---|---|---|
| `para` | `text` | One finding, 1–3 sentences |
| `bullets` | `items` | Genuinely list-like content only. Never a paragraph chopped into bullets |
| `image` | `src`, `caption`, `source` | The core of this format. `caption` describes what is visible, not what it implies |
| `kv` | `items` (2-element arrays) | 2–6 label/value pairs. Renders as a clean two-column table |
| `table` | `columns`, `rows` | 3+ entities × 3+ attributes. For 2–3 attributes use `kv` |

## Structure requirements

1. **Title + subtitle + meta block** — scope, date, and how many pages were swept. The reader needs to know the denominator of the research.
2. **One section per comparison axis** — the axes decided in Phase 0 become the section headings. Consistency between the plan and the document is what makes it navigable.
3. **Every section opens with the finding, not the setup.** First sentence after the heading = the conclusion. The screenshot then shows the evidence. Reference material comes after.
4. **Image + caption + source as one unit** — never an image without a caption, never a caption without a source URL.
5. **来源清单 at the end** — every URL, with what it supported and when it was accessed.

## Screenshot captions

A caption describes **what is visible**, and lets the reader locate it later.

| Bad | Good |
|---|---|
| 产品界面截图 | 产品A 会议主界面, 顶部为会议信息栏, 右侧为转写面板 |
| 展示后台 | 管理员后台的用户列表页, 可按部门筛选 |
| 硬件 | 机身背面接口: HDMI×2, USB-C×1, 千兆网口×1 |

The bad captions say nothing a reader could act on. The good ones tell the reader what to look for and let them match it against their own use case.

## Writing rules

Governed by `references/no-filler-rules.md` — read it. In short: no preamble, no "值得注意的是", numbers with sources, uncertainty named precisely (`未查到` / `未公开` / `需联系厂商`).

For Word specifically:
- Paragraphs are 1–3 sentences. Long paragraphs are where filler hides.
- Prefer a table over a paragraph that lists the same values.
- Do not describe a screenshot in prose if the caption already says it. That is duplication, and the reader sees both.

## Construction

**Preferred:** when a spreadsheet accompanies this document, render both from one dataset so they cannot contradict each other:

```bash
python scripts/validate.py data.json
python scripts/build_all.py data.json -o out.xlsx --docx out.docx
```

Each entry's `doc.intro` and `doc.blocks` become one Word section, and `build_all.py` appends the source URL plus verification date to every section automatically.

**Standalone Word only:**

```bash
python scripts/build_docx.py data.json -o out.docx
```

Image paths are resolved relative to the JSON file's directory, so keep `data.json` and `images/` side by side. A missing image degrades to a visible `[截图缺失: 路径]` marker rather than crashing the build — check for that marker after generating, since it means a capture failed.

Verify after building: open the file and check (a) images are not stretched or cropped oddly, (b) no image overflows the page margin, (c) headings appear in the navigation pane, (d) source URLs are present under each image, (e) no `[截图缺失]` markers remain.

## Anti-patterns

- **Decorative screenshots** — an image per section that adds no information. Cut it.
- **Full-page captures of a long page** scaled to page width — text becomes unreadable. Capture the viewport.
- **A Word doc that should have been Excel** — if there are no images, use the Excel path.
- **Screenshot without a date** — a UI screenshot without a capture date becomes misleading within a few months. The `meta` block carries the collection date for the whole document.
- **Splitting the same entity across sections** so the reader must scroll back and forth. One entity, one contiguous subsection.
