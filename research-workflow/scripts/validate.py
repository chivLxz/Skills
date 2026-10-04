#!/usr/bin/env python3
"""Validate a research data.json before building artifacts.

Usage:
    python validate.py data.json [--today YYYY-MM-DD] [--strict-unknown]

Checks (ERROR = must fix, WARN = fix or justify):
  1. schema: required fields present
  2. status is one of the five valid values
  3. verified date present and not in the future
  4. DEADLINE GUARD: a past deadline may not carry status "open"/"upcoming"
  5. "ongoing" entries carry no deadline; dated statuses carry one
  6. "unknown" status has a recorded reason
  7. source URL present and well-formed
  8. required fields non-empty (precise empties allowed)
  9. entries carry both fields and doc blocks (so Excel and Word correspond)
 10. per-entry coverage against the required-field matrix

Exit codes: 0 clean (WARN allowed), 1 errors present, 2 bad input.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime

VALID_STATUS = {"open", "upcoming", "closed", "ongoing", "unknown"}
DATED_STATUS = {"open", "upcoming", "closed"}

# Precise empties are acceptable; a blank cell is not.
PRECISE_EMPTIES = {
    "未查到", "未公开", "需联系主办方", "待定", "不适用", "N/A", "-",
    "需联系厂商", "未获取",
}

REQUIRED_SHEET_FIELDS = ["name"]
REQUIRED_ENTRY_FIELDS = ["name", "status", "verified", "source"]

errors = []
warnings = []
info = []


def err(where, msg):
    errors.append(f"[ERROR] {where}: {msg}")


def warn(where, msg):
    warnings.append(f"[WARN ] {where}: {msg}")


def note(where, msg):
    info.append(f"[INFO ] {where}: {msg}")


def parse_date(value):
    if not value or not isinstance(value, str):
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value.strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        return s == "" or s in PRECISE_EMPTIES
    return False


def looks_like_url(value):
    return isinstance(value, str) and value.strip().startswith("http")


def main():
    ap = argparse.ArgumentParser(description="Validate research data before build")
    ap.add_argument("data")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    ap.add_argument("--strict-unknown", action="store_true",
                    help="treat status=unknown as an error")
    args = ap.parse_args()

    try:
        with open(args.data, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read data file: {exc}", file=sys.stderr)
        return 2

    today = parse_date(args.today) or date.today()

    collected = parse_date((data.get("meta") or {}).get("collected_at"))
    if collected and collected != today:
        warn("meta", f"collected_at={collected} 与校验日期 {today} 不一致，"
                    f"状态结论可能已过期，请确认来源后更新")

    entries = data.get("entries")
    if entries is None:
        err("schema", "缺少 entries 数组。Excel 与 Word 必须共用同一份 entries 数据，"
                      "否则两份内容会不一致")
        report()
        return 1

    if not isinstance(entries, list) or not entries:
        err("schema", "entries 为空或不是数组")
        report()
        return 1

    seen_ids = set()
    status_counts = {}

    for i, entry in enumerate(entries):
        label = f"entries[{i}]"
        if not isinstance(entry, dict):
            err(label, "不是对象")
            continue

        eid = entry.get("id")
        name = entry.get("name") or f"id={eid}"
        where = f"{label}[{name}]"

        if eid:
            if eid in seen_ids:
                err(where, f"id 重复: {eid}")
            seen_ids.add(eid)
        else:
            err(where, "缺少 id（用于稳定引用）")

        for f in REQUIRED_ENTRY_FIELDS:
            if is_empty(entry.get(f)):
                err(where, f"缺少必填字段 {f}")

        # ---- status legality ----
        status = entry.get("status")
        deadline = parse_date(entry.get("deadline"))
        raw_deadline = entry.get("deadline")
        verified = parse_date(entry.get("verified"))

        if status is not None and status not in VALID_STATUS:
            err(where, f"非法 status: {status!r}，只允许 {sorted(VALID_STATUS)}")
        else:
            status_counts[status] = status_counts.get(status, 0) + 1

        if status == "unknown":
            reason = entry.get("unknown_reason") or (entry.get("doc") or {}).get("unknown_reason")
            if not reason:
                (err if args.strict_unknown else warn)(
                    where, "status=unknown 但未记录 unknown_reason（为何查不到）")
            elif args.strict_unknown:
                err(where, "status=unknown 且启用了 --strict-unknown")

        if verified and verified > today:
            err(where, f"verified={verified} 晚于今天 {today}，无法作为核验依据")

        if raw_deadline not in (None, "") and deadline is None:
            err(where, f"deadline 格式错误: {raw_deadline!r}，应为 YYYY-MM-DD 或 null")

        # ---- the deadline guard: defect #1 ----
        if status in ("open", "upcoming"):
            if deadline is None:
                if status == "upcoming":
                    warn(where, "status=upcoming 但无 deadline，应补充开放时间")
            elif deadline < today:
                err(where, f"截止日期 {deadline} 已早于今天 {today}，"
                           f"但 status={status} —— 应为 closed。"
                           f"若官方确认延期，请补official延期公告URL")
            elif (today - deadline).days <= 14:
                warn(where, f"距截止仅 {(today - deadline).days * -1} 天，确认是否仍开放")
        if status == "closed" and deadline and deadline > today:
            warn(where, f"status=closed 但 deadline={deadline} 尚未到期，"
                        f"确认是否官方提前关闭（需官方说明佐证）")
        if status == "ongoing" and deadline is not None:
            err(where, "status=ongoing 应配合 deadline=null（滚动招领，无固定截止）")
        if status in DATED_STATUS and deadline is None and entry.get("deadline") is not None:
            warn(where, f"status={status} 需要明确 deadline")

        # ---- source ----
        src = entry.get("source")
        if not is_empty(src) and not looks_like_url(src):
            err(where, f"source 不是URL: {src!r}")

        # ---- spreadsheet / document correspondence ----
        fields = entry.get("fields")
        doc = entry.get("doc")
        if not isinstance(fields, dict) or not fields:
            err(where, "缺少 fields（Excel 行数据）—— Excel 与 Word 将无法对应")
        if not isinstance(doc, dict) or not doc.get("blocks"):
            err(where, "缺少 doc.blocks（Word 段落）—— Excel 与 Word 将无法对应")

        # field name must match the entry name, else rows misalign
        if isinstance(fields, dict) and not is_empty(fields.get("name")) \
                and not is_empty(name) and fields["name"] != name:
            warn(where, f"fields.name({fields['name']!r}) 与 name({name!r}) 不一致")

        # ---- required-field coverage on the sheet row ----
        if isinstance(fields, dict):
            for key, val in fields.items():
                if key in ("url", "url_1", "url_2") and looks_like_url(val):
                    continue
                if is_empty(val):
                    warn(where, f"字段 {key} 为空或为占位空值——"
                                f"请用精确空值（未查到/未公开/需联系主办方）")

    # ---- column definitions ----
    columns = data.get("columns")
    if not columns:
        err("schema", "缺少 columns 定义")
    else:
        keys = {c.get("key") for c in columns if isinstance(c, dict)}
        for i, entry in enumerate(entries):
            if isinstance(entry, dict) and isinstance(entry.get("fields"), dict):
                extra = set(entry["fields"].keys()) - keys
                if extra:
                    warn(f"entries[{i}]", f"fields 中有未在 columns 声明的键: {sorted(extra)}")

    # ---- report ----
    report()

    if status_counts:
        summary = ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
        print(f"[STATUS] 状态分布: {summary}")

    # Only claim health when the deadline guard actually passed
    guard_errors = [e for e in errors if "应为 closed" in e or "status=ongoing" in e]
    if not guard_errors:
        n = status_counts.get("open", 0)
        if n:
            print(f"[OK    ] {n} 项标记为 open，截止日期均未过期（对照 {today}）")

    if errors:
        print(f"\n结论: 不可交付 — {len(errors)} 个错误必须修复")
        return 1
    print(f"\n结论: 可交付（{len(warnings)} 条警告建议处理）")
    return 0


def report():
    for line in info:
        print(line)
    for line in warnings:
        print(line)
    for line in errors:
        print(line)


if __name__ == "__main__":
    sys.exit(main())
