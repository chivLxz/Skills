# Excel output spec

Excel is the right artifact when findings are textual and comparable: one entity per row, one attribute per column.

## When Excel is correct

Use Excel when the material can be organized as a table with entities down the left axis and attributes across the top. Typical: vendor comparison, spec sheet, pricing tiers, feature matrix, version/date timeline, changelog.

Do **not** use Excel for: UI/UX descriptions, product appearance, anything needing a picture, anything where the "cell" is a paragraph of interpretation. Those are Word-with-screenshots cases.

## Preferred: let build_all.py render it

When the deliverable also includes a Word document, **do not write a separate Excel data file.** Keep one `data.json` with an `entries` array and run:

```bash
python scripts/validate.py data.json          # gate first
python scripts/build_all.py data.json -o out.xlsx --docx out.docx
```

`build_all.py` renders the spreadsheet from `entries[].fields` and injects the status column from `entry.status`, so the status can never be hand-typed wrong and the two artifacts cannot disagree. Schema in `references/status-and-completeness.md`; a fill-in template is in `assets/unified-template.json`.

Use the standalone `build_xlsx.py` only when the deliverable is Excel alone.

## Manual schema (standalone mode only)

`build_xlsx.py` consumes a `sheets` array. Field reference:

```json
{
  "sheets": [
    {
      "name": "核心对比",
      "columns": [
        { "title": "产品", "width": 22 },
        { "title": "厂商", "width": 14 },
        { "title": "定价", "width": 16 },
        { "title": "关键能力", "width": 46, "wrap": true }
      ],
      "rows": [
        ["产品A", "厂商A", "$20/月", "支持多语言字幕; 本地部署"],
        ["产品B", "厂商B", "未查到", "仅云端, 无私有化选项"]
      ],
      "notes": "定价均为官网公开标准价, 2026-10采集"
    },
    {
      "name": "来源清单",
      "columns": [
        { "title": "产品", "width": 18 },
        { "title": "字段", "width": 16 },
        { "title": "URL", "width": 58 },
        { "title": "采集时间", "width": 14 }
      ],
      "rows": [
        ["产品A", "定价", "https://example.com/pricing", "2026-10-03"]
      ]
    }
  ]
}
```

Field rules:

- `name` — sheet tab name. Excel limit is 31 chars; avoid `:` `/` `?` `*` `[` `]`.
- `columns[].title` — required. `width` in Excel units (roughly one unit ≈ one ASCII char). `wrap` enables multi-line wrap for long cells.
- `rows` — arrays of values, positionally matched to `columns`. Short rows are padded automatically; extra values are dropped.
- `notes` — optional string rendered as a merged, italic footnote line under the table. Use it for the collection date, pricing basis, or caveats. This is where "所有定价为标准版, 不含企业版" belongs.
- `urls` — optional array of URLs. When present, they render as blue underlined hyperlinks in a `URL` column appended to the right. Use this for the source column so readers can click through.

## Required sheets

A complete deliverable has at least:

1. **核心对比 / 主表** — the actual findings, one row per entity.
2. **来源清单** — every URL used, with what it supported and when it was accessed. This is what makes the workbook auditable; do not skip it even if it feels redundant.

Optional but valuable:
3. **说明** — scope, time window, method, and explicit gaps. Can also be a `notes` line if short.
4. **未获取** — entities or fields that could not be sourced, with the reason. This is a strength, not an admission: it tells the reader where the research hit a wall.

## Formatting conventions

The script applies these; do not fight them.

- **Header row** — bold, filled, frozen at top, autofilter enabled.
- **Text vs numbers** — write numbers as numbers (`200`, `3.5`) so they can be sorted and compared. Write `"约 200"` or `"200ms"` as text. Mixed types in a column are fine but note the unit in the header: `延迟(ms)`, not `延迟`.
- **Missing data** — use the literal string `未查到`, `未公开`, or `需联系厂商`. Never leave a cell silently blank, because a blank reads as "zero" or "not applicable" and both are wrong.
- **Units go in the header** — `价格(USD/月)`, `体积(mm)`, `首Token延迟(ms)`. This keeps cells clean and sortable.
- **Numbers that mean order** — for ranges like `10-20`, write `10–20` with an en dash so Excel treats it as text and left-aligns predictably.

## Source discipline

Every data point needs a traceable origin. Two workable patterns:

- **Per-row source** — a `来源` column with the URL for the whole row. Good when one page covers all attributes of an entity.
- **Per-cell source** — a URL column per attribute, or a cell comment. Necessary when facts come from different pages (e.g. pricing from one page, spec from another). More accurate, more work; use it when facts genuinely diverge.

`未查到` cells need no source. Their absence is the information.

## Construction

```bash
python scripts/build_xlsx.py data.json -o 调研结果.xlsx
```

Verify after building: reopen and confirm header row is frozen, column widths fit content, no cell shows `###` (column too narrow for a number), and the notes line rendered.

## Anti-patterns

- **A single sheet with mixed content** — comparison table, prose analysis, and source list crammed into one tab. Split into sheets.
- **Merged cells in the data grid** — breaks sorting and filtering. The script only merges for the notes line.
- **Merged vertical cells in column A** — looks tidy, breaks every sort. Write the entity name in every row.
- **Color as the only signal of meaning** — if a cell is red because it is bad, also say why in text; the deliverable will be read in grayscale and by people who cannot distinguish the color.
- **Row per source instead of row per entity** — that is the source list, it belongs in its own sheet.
