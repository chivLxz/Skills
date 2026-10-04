#!/usr/bin/env python3
"""Render BOTH Excel and Word from one data.json, guaranteeing they correspond.

Usage:
    python build_all.py data.json -o out.xlsx --docx out.docx
    python build_all.py data.json -o out.xlsx                    # Excel only
    python build_all.py data.json --docx out.docx                # Word only

Schema (see references/status-and-completeness.md):
    {
      "meta": {"title": "...", "subtitle": "...", "collected_at": "2026-10-03"},
      "columns": [{"key": "name", "title": "名称", "width": 30, "wrap": false}],
      "entries": [
        {
          "id": "slug",
          "name": "...",
          "status": "open|upcoming|closed|ongoing|unknown",
          "deadline": "2026-11-02" | null,
          "verified": "2026-10-03",
          "source": "https://...",
          "fields": {"name": "...", "status": "open"},   # Excel row
          "doc": {"intro": "...", "blocks": [...]}
        }
      ],
      "extra_sheets": [ ... ],
      "status_summary": true
    }

Both artifacts are rendered from the SAME entries array in one pass, so they
cannot disagree about what exists or what it contains. The status column is
injected automatically from the entry status so it is never hand-typed wrong.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_xlsx import build as build_xlsx            # noqa: E402
from build_docx import build as build_docx            # noqa: E402

STATUS_LABEL = {
    "open": "可报名",
    "upcoming": "未开放",
    "closed": "已截止",
    "ongoing": "长期有效",
    "unknown": "未核实",
}
STATUS_ORDER = ["open", "ongoing", "upcoming", "unknown", "closed"]


def to_xlsx_spec(data):
    """Entries -> the main sheet. Status column is injected from entry.status."""
    columns = data.get("columns") or []
    cols = [{"title": c["title"], "width": c.get("width", 18),
             "wrap": c.get("wrap", False)} for c in columns]
    # Auto-inject a status column right after the name
    if not any(c["title"] == "状态" for c in cols) and "status" in [
            c.get("key") for c in columns]:
        cols.insert(1, {"title": "状态", "width": 11, "wrap": False})

    rows, urls = [], []
    for e in data.get("entries", []):
        f = dict(e.get("fields") or {})
        f["status"] = STATUS_LABEL.get(e.get("status"), e.get("status", ""))
        rows.append([f.get(c.get("key")) for c in columns])
        urls.append(e.get("source", ""))

    sheets = [{
        "name": data.get("main_sheet_name", "主表"),
        "columns": cols,
        "rows": rows,
        "urls": urls,
        "notes": data.get("main_notes", ""),
    }]

    if data.get("status_summary", True):
        summary_rows = []
        for st in STATUS_ORDER:
            n = sum(1 for e in data.get("entries", []) if e.get("status") == st)
            if n:
                summary_rows.append([STATUS_LABEL[st], n])
        meta = data.get("meta", {})
        sheets.append({
            "name": "状态汇总",
            "columns": [{"title": "状态", "width": 14},
                        {"title": "数量", "width": 10}],
            "rows": summary_rows,
            "notes": f"统计口径：截至 {meta.get('collected_at', '未知')}。"
                      f"「可报名」= 已与当日比较且截止日期未过。",
        })

    sheets.extend(data.get("extra_sheets", []))
    return {"sheets": sheets}


def to_docx_spec(data):
    """Entries -> one document section per entry, so Word mirrors Excel rows."""
    meta = data.get("meta", {})
    doc = {
        "title": meta.get("title", ""),
        "subtitle": meta.get("subtitle", ""),
        "meta": data.get("document_meta", []),
        "sections": [],
    }

    for e in data.get("entries", []):
        d = e.get("doc") or {}
        heading = e.get("doc_heading") or e.get("name", "")
        blocks = list(d.get("blocks", []))
        src = e.get("source")
        if src:
            blocks = blocks + [{
                "type": "para",
                "text": f"来源：{src}（状态核验日期 {e.get('verified', '未知')}）",
            }]
        doc["sections"].append({
            "heading": heading,
            "intro": d.get("intro", ""),
            "blocks": blocks,
        })

    doc["sources"] = data.get("sources", [])
    return doc


def main():
    ap = argparse.ArgumentParser(
        description="Render Excel and Word from one dataset")
    ap.add_argument("data")
    ap.add_argument("-o", "--out", help="output .xlsx path")
    ap.add_argument("--docx", help="output .docx path")
    args = ap.parse_args()

    if not args.out and not args.docx:
        print("need at least one of -o/--out or --docx", file=sys.stderr)
        return 2

    try:
        with open(args.data, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read data file: {exc}", file=sys.stderr)
        return 2

    base = os.path.dirname(os.path.abspath(args.data))

    if args.out:
        build_xlsx(to_xlsx_spec(data), args.out)
        print(f"wrote {args.out}")

    if args.docx:
        build_docx(to_docx_spec(data), args.docx, base)
        print(f"wrote {args.docx}")

    n = len(data.get("entries", []))
    print(f"rendered {n} entries into both artifacts from one source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
