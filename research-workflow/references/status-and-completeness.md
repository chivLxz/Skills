# Status determination and completeness

Two failure modes kill a time-sensitive deliverable:

1. **Stale status** — an event that closed last month is presented as open. The user finds out later and loses trust in every other row.
2. **Silent incompleteness** — a row is missing fields, and nothing prompts you to notice.

Both are mechanical problems. They need a field-level spec and a validation gate, not careful judgment.

---

## Every dated subject needs a `status`

Any research subject with a deadline (competitions, tenders, product launches, conferences, price changes) must carry these four fields:

| Field | Format | Meaning |
|---|---|---|
| `status` | one of five values (below) | Verified state **as of `verified`** |
| `deadline` | `YYYY-MM-DD` or `null` | Last date to enter/submit |
| `verified` | `YYYY-MM-DD` | When you personally checked the source |
| `source` | full URL | Where the status was read |

The `verified` date is what makes a status claim auditable. Without it, a stale row looks identical to a fresh one.

### The five valid status values

| Value | Use when | Deadline expectation |
|---|---|---|
| `open` | You verified registration/submission is accepted right now | A future `deadline` exists |
| `upcoming` | Announced but not yet accepting entries | A future `deadline` exists |
| `closed` | Deadline passed, or the page states it ended | `deadline` is past or explicitly ended |
| `ongoing` | No fixed deadline — rolling intake (annual funds, quarterly rounds) | `deadline` is `null` |
| `unknown` | Could not verify. Say so; never guess | `null` |

**`unknown` is a legitimate answer.** Writing `open` because the page didn't say otherwise is the exact error this spec exists to prevent.

### Status determination rules

1. **Never infer status from a secondary source.** News articles, aggregator pages, and search snippets go stale. Read the official page, or an official announcement, or record `unknown`.
2. **The official page's own words win.** "Registration closed", "已截止", "ended", "registration is closed" → `closed`, even if the deadline date hasn't passed (they often close early).
3. **A past deadline with no contrary evidence → `closed`.** Not `open`, not `unknown`. This is the default that prevents defect 1.
4. **Multiple sources conflict → `unknown`**, and record the conflict in the gaps sheet. Do not pick the more convenient one.
5. **A rolling program with a yearly fund and quarterly rounds → `ongoing`**, `deadline: null`. This is materially different from `open` and the reader needs to know they can join in a later round.

### The rule that prevents defect 1

> Before writing any row, compute the comparison explicitly:
> **today vs `deadline`**. If `deadline` is in the past, the row is `closed` — regardless of how the page is worded, unless an official source explicitly states the deadline was extended.
>
> Never write a status you have not compared against today's date. If you cannot state the comparison, the status is `unknown`.

---

## Completeness: the required-field matrix

A "recommended" row missing a field the reader needs to act is a defect, not a partial result. Before delivery, every row in a recommendation table must have:

| Field group | Required for | If genuinely unavailable |
|---|---|---|
| Identity (name, organizer) | all | cannot be blank |
| **Status + deadline + verified** | all dated subjects | `unknown` / `null` / verification date |
| **How to enter** (URL, app, email, contact) | all actionable rows | `需联系主办方` + why |
| Eligibility (who may enter) | all | `未查到` + why |
| Time window (start ~ end) | all | `未公开` + why |
| Reward or outcome, if any | all | `未公开` + why |
| Source URL per claim | all rows | — |
| Why it matters *to this user* | recommendation tables | drop the row instead |

Two habits close most gaps:

- **Check the primary source for these fields, not the aggregator.** The aggregator's table is where the empty cells come from.
- **When a required field is empty, say which kind of empty it is.** `未查到` (searched, nothing public) / `未公开` (vendor does not disclose) / `需联系主办方` (obtainable only by asking) / `待定` (announced but not fixed). A precise empty is information; a blank cell is a bug.

---

## Structural requirement: one dataset, two renderings

**Never maintain two separate data files for Excel and Word.** They will drift — a row added to one, a figure changed in the other, and the user ends up with two documents that contradict each other.

Instead, keep **one `data.json`** with a single `entries` array, where each entry carries both its spreadsheet fields and its narrative blocks:

```json
{
  "meta": { "title": "...", "collected_at": "YYYY-MM-DD" },
  "columns": [{ "key": "name", "title": "名称", "width": 30 }],
  "entries": [
    {
      "id": "stable-slug",
      "name": "...",
      "status": "open",
      "deadline": "2026-11-02",
      "verified": "2026-10-03",
      "source": "https://...",
      "fields": { "name": "...", "status": "open", "deadline": "..." },
      "doc": { "intro": "...", "blocks": [ { "type": "para", "text": "..." } ] }
    }
  ],
  "extra_sheets": [ ... ],
  "document_meta": [ ... ]
}
```

Then run:

```bash
python scripts/build_all.py data.json -o out.xlsx --docx out.docx
```

`build_all.py` renders Excel from `entries[].fields` and Word from `entries[].doc` in one pass, so the two artifacts cannot disagree about what entries exist or what they contain. **Correspondence becomes structural rather than a thing you remember to check.**

---

## Validation gate

Run before delivery, every time:

```bash
python scripts/validate.py data.json
```

It mechanically checks:

- every entry has `status` from the valid set, and a `verified` date
- **`deadline` in the past never carries `status: open`** ← the defect-1 guard
- `ongoing` entries have no deadline; dated statuses have one
- required fields are non-empty, with precise empties instead of blanks
- each entry has a source URL
- every entry appears in both the spreadsheet and the document
- `status: unknown` entries have a recorded reason

Treat any `ERROR` as blocking. Fix the data, re-run, then deliver.
