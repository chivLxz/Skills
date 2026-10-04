# No-filler rules

A research deliverable is judged by how fast the reader gets to a decision. Filler is the tax. These rules apply to both Excel cell text and Word prose.

## The test

Read the output line by line and ask: **does this line carry information not already implied by its surroundings?**

If removing a sentence leaves the document just as clear, the sentence is filler. Delete it.

## Banned phrasings

These appear in almost all generated research and carry almost no information. Do not write them.

| Banned | Why | Write instead |
|---|---|---|
| 在当今快速发展的……环境中 | Says nothing; true of every topic, every year | Delete the clause entirely |
| 值得注意的是 / 值得一提的是 | Meta-commentary, not content | Just state the thing |
| 综上所述 | Announces a summary without being one | Write the summary directly |
| 总而言之 | Same as above | Delete |
| 具有广阔的市场前景 | Unsupported claim | The actual market size, with a URL |
| 显著提升了效率 | Unquantified | `将 X 从 A 降至B（测量方法，来源）` |
| 极大程度上取决于 | Hedging that says nothing | Name the actual dependency |
| 不断 /  increasingly / 日益 | Trend without a number | `2024→2026 从 12 增至 31` |
| 据悉 / 有媒体报道称 | Anonymous sourcing | Name the outlet and link it |
| 多方认为 | Conflates disagreement with consensus | Attribute each view separately |
| 打造 / 赋能 / 闭环 / 抓手 / 生态位 | Vague industry jargon | The concrete mechanism |

Also: any sentence that begins with the section heading and restates it. A section called "定价对比" does not need to open with "定价是衡量产品竞争力的重要维度。"

## Compression rules

**Verbs over nominalizations.** `提供了支持` → `支持`. `进行了优化` → `优化`. Chinese technical writing pads with these; each pad costs the reader a parse.

**Merge related cells.** If a cell says "支持 Windows 和 macOS" that is one cell, not two. If the comparison has 12 columns and 6 are empty across all rows, those 6 columns are noise — drop them and say so in a note.

**Cut the preamble.** No "本调研旨在...". No "随着...的发展". The scope belongs in one line, or in a `README` sheet / caption.

**No restating the obvious in prose.** If the table already shows 5 vendors with 3 price tiers, do not narrate the prices. Spend the sentence on what the pattern *means*.

## Numbers need context

A bare number is nearly useless. Give it a comparison or a consequence.

| Weak | Strong |
|---|---|
| 延迟 200ms | 延迟 200ms，是 B（450ms）的 44% |
| 市场份额 12% | 份额 12%，排名第三，前二合计 61% |
| 支持 40 种语言 | 支持 40 种语言，其中 12 种为完整本地化（非机器翻译） |

**Every number needs a source URL** — either in the row's source column or in the cell comment. An unsourced number is a liability.

## Uncertainty is expressed precisely

Not "大概"/"可能" for everything. Distinguish these states:

- `未查到` — searched, no public source. Honest and specific.
- `未公开` — the vendor does not disclose it. Different from未查到.
- `需联系厂商` — obtainable only by asking. Actionable.
- `预计 2026Q4` — with the URL of where the estimate came from.

Uniform hedging (`可能大概也许`) is as useless as false precision. Name the state.

## Before/after

**Before**
> 在当今 AI 硬件快速发展的背景下，各厂商的产品在形态和算力上存在一定差异。值得注意的是，华为昇腾 910B 的算力参数与英伟达 A100 存在较大差距，这可能对生态建设产生影响。

**After**
> 昇腾 910B 算力 320 TFLOPS(FP16)，A100 为 312 TFLOPS——单卡算力相当，但生态是主要约束：CUDA 库迁移成本约 3–6 人月（来源：迁移评估报告, 2026-03）。

The second version has the same sentence count, no preamble, an actual number with a source, and it ends on the thing that actually matters.

## Final audit

Before delivering, run these:

1. Search the output for banned phrases. Any hit is a delete.
2. Count sentences that only restate their heading. Delete them.
3. Verify every number has a URL. Un-sourced numbers get removed or marked.
4. Check no `可能` / `也许` where a state could be named precisely.
5. Read the first two sentences of the document — if they describe what the document is *about* rather than what it *found*, rewrite them to lead with the finding.
