---
name: research-workflow
description: >
  Structured research delivery with two output modes: text findings become a clean Excel
  workbook, visual/UI/product findings become a Word document with screenshots of every section.
  Use this skill whenever the user asks to research, survey, compare, investigate, map out,
  or produce a 调研/竞品调研/选型对比/市场调研 on any topic — products, technologies, vendors,
  competitors, SDKs, hardware, policies, or news. Also use it when the user says "调研一下",
  "对比一下这几家", "帮我看看有哪些", "做个竞品分析", "整理一份资料", "搜集一下资料",
  or asks for research to be delivered as Excel / Word / 表格 / 文档. Trigger even when the
  request sounds casual or underspecified — this skill is the right way to structure any
  multi-source research task. Covers: 竞品对比, 产品选型, 技术方案调研, 供应商筛选,
  行业扫描, 新闻时间线梳理, 硬件参数对比.
---

# Research Workflow

Turn a research request into a delivered artifact — a workbook or a screenshot document —
with every source URL traceable and no filler text.

## The core problem this solves

Research fails in three predictable ways, and this workflow is structured against each:

| Failure | Countermeasure |
|---|---|
| Anchoring on the first few search hits | Phase 1 mandates broad discovery *before* any deep read |
| Findings dumped as prose nobody can use | Phase 3 forces a format decision: Excel or Word, never "just markdown" |
| Sources lost, claims unverifiable | Every row and every section carries its URL |

---

## Phase 0: Scope lock

Before searching, pin down three things. Ask only if genuinely unclear — do not interrogate.

1. **The question** — one sentence, in the user's own framing.
2. **Comparison axis** — what dimension the output is organized around (price, latency, vendor, capability…). This becomes the Excel column headers or the Word section titles. Getting this wrong means rebuilding the whole deliverable.
3. **Depth &time window** — quick scan vs. thorough; and whether recency matters (most product/tech research does).

If the request is broad ("帮我调研一下 X 行业"), default to: top 8–12 players, 6-month window, comparison axis = whatever the user cares about most. State these defaults in one line and proceed — do not wait for confirmation on obvious defaults.

## Phase 1: Breadth sweep — find *all* candidate pages first

This is the step most workflows skip, and skipping it is why results feel shallow. Do not read anything deeply yet. Your only goal is to build the **candidate pool**.

Run search frommultiple angles, because each angle surfaces different pages:

- **Entity angle** — the leading vendors/products, plus "alternatives to X", "X vs", "best X tools"
- **Category angle** — how the industry names the thing (jargon differs from marketing names)
- **Chinese angle** — search in Chinese too; for domestic-adjacent topics the Chinese web often has fresher and more specific coverage
- **Recency angle** — "X 2026", "X 发布", "X 更新", "X 评测" to catch what changed
- **Negative angle** — "X 缺点", "X 踩坑", "X 吐槽", "X limitations" surfaces what marketing pages hide

For each promising result, capture into a working table (see `references/search-strategy.md` for the full query matrix and how to record candidates):

| entity | url | source type | date | angle found | notes |
|---|---|---|---|---|---|

Rules:
- Aim for **≥ 20 candidate pages** before narrowing. If the pool is smaller, the sweep is too narrow.
- Prefer primary sources: official sites, official docs, official pricing pages, changelogs, filings, spec sheets. These outrank blog listicles for factual claims.
- Mark each candidate as `read` / `skip` with a reason. Skipping without recording means you'll re-find it later and wonder why you dropped it.

## Phase 1.5: Pin the status of every dated subject

**Skip this phase and your deliverable will contain expired items presented as open.** This is the single most common failure in time-sensitive research, and it is entirely mechanical — which means a script can catch it.

If any subject has a deadline (competitions, tenders, product launches, conferences, price changes), every entry needs four fields: `status`, `deadline`, `verified` (the date you personally checked), and `source`.

| status | when | deadline |
|---|---|---|
| `open` | you verified entries are accepted right now | a future date |
| `upcoming` | announced, not yet accepting | a future date |
| `closed` | deadline passed, or page states it ended | past date |
| `ongoing` | rolling intake, no fixed deadline | `null` |
| `unknown` | could not verify — say so, never guess | `null` |

The rule that matters: **compare today's date against `deadline` before writing any status.** A past deadline means `closed`, regardless of how the source is worded — unless an official source explicitly confirms an extension. Read status from the official page, not from news coverage or an aggregator, which go stale.

Read `references/status-and-completeness.md` for the full rules, the required-field matrix, and the precise-empty vocabulary (`未查到` / `未公开` / `需联系主办方`).

## Phase 2: Triage the pool → decide the output format

Now decide what the material *actually is*, because this determines the artifact.

**Output Excel when the findings are textual and comparable** — parameters, prices, features, vendors, versions, dates, spec comparisons. If you can put it in a table with one entity per row, it is an Excel job.

**Output Word with screenshots when the findings are visual or experiential** — UI/UX, product appearance, device hardware, dashboards, architecture diagrams, web pages as delivered, packaging, physical form factor. The user needs to *see* it, because text description loses the evidence.

**If a topic is mixed** (e.g. comparing five AI meeting products: specs → Excel, but each product's UI → Word), produce both, with the Excel as the comparison backbone and the Word as the visual appendix. Say this split explicitly in the output.

When both are needed, **they must come from one dataset.** Two hand-maintained files will drift — a row added to one, a figure changed in the other — and the user ends up with two documents that contradict each other. Put every entry in one `entries` array with both its `fields` (the spreadsheet row) and its `doc` (the narrative blocks), then render both with `build_all.py`. Correspondence becomes structural instead of something you remember to check.

Before building either artifact, read the matching spec file — it carries the exact structure, column conventions, and formatting rules:
- Excel path → `references/excel-output-spec.md`
- Word path → `references/word-output-spec.md`
- Dated subjects, or a deliverable that must be complete → `references/status-and-completeness.md`

All specs share `references/no-filler-rules.md`, which governs wording. Read it before writing any content — it is the difference between a deliverable and a wall of padding.

## Phase 3: Build the artifact

Use the bundled scripts rather than writing code from scratch each time. They exist because every research run repeats the same formatting work.

### Preferred: one dataset, both artifacts

```bash
# validate first — this is the gate, not a formality
python scripts/validate.py data.json

# then render both from that single dataset
python scripts/build_all.py data.json -o out.xlsx --docx out.docx
```

`validate.py` mechanically enforces the Phase 1.5 rules — above all, it rejects a past deadline carrying `status: open` — and checks required-field coverage. **Treat any `[ERROR]` as blocking.** `build_all.py` renders the spreadsheet and the document from the same `entries` array in one pass, so they cannot disagree.

Word artifacts usually need screenshots first:

```bash
python scripts/shoot.py <urls.txt> -o <image_dir> --width 1440 --height 900
```

# 2. build the document from a JSON spec
The Word spec embeds images inline at the point of discussion, with a caption and the source URL under each — so the reader never wonders what they're looking at or where it came from.

**On screenshots — this matters:** capture the actual page, never a text summary of the page. A screenshot of a product page is evidence; a paragraph describing it is a claim. Use `shoot.py` (Chrome headless). If a page fails to render, note it rather than silently substituting a placeholder.

## Phase 4: Self-check before delivery

Do not skip this. Run the validator first — it catches what the eye reliably misses — then read the artifact yourself.

```bash
python scripts/validate.py data.json     # must report 0 errors
```

- [ ] **Validator reports 0 errors** — especially no past deadline marked `open`, no blank required field, no entry missing its spreadsheet row or document blocks.
- [ ] **Excel and Word correspond** — the same entries appear in both, with consistent status and figures. If you maintained two data files, that is the defect: rebuild from one dataset with `build_all.py`.
- [ ] **Every dated subject was compared against today** — not inferred from a headline or a stale article.
- [ ] **Table names match their contents** — a sheet called "recommended/open" must not contain an expired entry. This is the most embarrassing defect because the table title itself makes the claim.
- [ ] **URL completeness** — every data row and every section carries a source URL. No exceptions.
- [ ] **Format matches content** — text → Excel, visual → Word+截图. If you delivered a different format than Phase 2 decided, that decision was wrong; revisit it.
- [ ] **Pool was genuinely broad** — check `sources` count is ≥ 20, and that the discovery included at least 3 different search angles.
- [ ] **No filler** — read `references/no-filler-rules.md` and self-audit against it. Delete every sentence that restates the header or pads the count.
- [ ] **No invented facts** — any cell you could not source is marked `未查到`, never guessed. A blank with a reason is honest; an invented value destroys the deliverable's trust.
- [ ] **Required fields present per the matrix** — actionability fields (how to enter, eligibility, time window) are filled or carry a precise empty.
- [ ] **Artifact opens cleanly** — open the xlsx/docx and confirm the layout is not broken (merged cells, truncated headers, oversized images). Also confirm row counts per sheet match what the titles imply.
- [ ] **File is presented** — finish by calling `present_files` with the artifact path, and state in one line which format you chose and why.

---

## Reference files

Read these as needed — each carries detail that would bloat this file.

| File | Contents | When to read |
|---|---|---|
| `references/search-strategy.md` | Query matrix, candidate-pool format, source tiering, anti-anchor tactics | Phase 1, always |
| `references/status-and-completeness.md` | The five status values, deadline comparison rules, required-field matrix, precise-empty vocabulary, single-dataset schema | Phase 1.5 and Phase 4, whenever subjects have deadlines |
| `references/excel-output-spec.md` | JSON schema for `build_xlsx.py`, column conventions, sheet layout | Excel path |
| `references/word-output-spec.md` | JSON schema for `build_docx.py`, screenshot rules, section structure | Word path |
| `references/no-filler-rules.md` | Banned phrasings, compression rules, before/after examples | Before writing any content |

## Bundled scripts

Start here:

- `scripts/validate.py` — **run before building.** Enforces status/deadline consistency, required fields, and Excel↔Word correspondence. Exit 1 blocks delivery.
- `scripts/build_all.py` — **preferred renderer.** One `data.json` → both `.xlsx` and `.docx`, so they cannot disagree.

Single-artifact renderers, when you only need one:

- `scripts/build_xlsx.py` — data.json → styled Excel workbook
- `scripts/build_docx.py` — data.json → Word document with inline screenshots
- `scripts/shoot.py` — batch URL → PNG via headless Chrome

## Common failure modes

- **Presenting an expired item as open** — the default failure when status is judged by eye. Mechanical fix: `validate.py` compares every deadline against today.
- **Two artifacts that disagree** — the default failure when Excel and Word are built from separate data. Structural fix: one `entries` array, rendered by `build_all.py`.
- **A table whose contents contradict its title** — a "recommended" sheet holding a closed entry. Check the contents against the sheet name before delivering.
- **Drifting into a single narrative** — the user asked to *survey*, not to conclude. If the material does not support a recommendation, present the landscape and stop.
- **Uniform rows that hide gaps** — if an entity lacks a capability, leave the cell `未查到` rather than copying a neighbor. Uniform data is the tell of fabricated research.
- **Ignoring the review UI** — some pages need a real browser. If headless returns a blank or a login wall, say so in the output instead of quietly dropping the candidate.
- **Screenshotting a cookie banner** — if a modal covers the content, note it or crop. A screenshot of a consent dialog is not evidence.

