# Search strategy: breadth before depth

The purpose of Phase 1 is to build a candidate pool, not to answer the question. Answering comes later, from a pool that has already been widened.

## The anchor trap

When you search one query and read the top hits, you inherit the ranking of a search engine that has already decided what matters. This produces confident, plausible, narrow research. Every safeguard below exists to break that inheritance.

**The rule: no deep read until the pool has ≥ 20 candidates.**

## Query matrix

Run at least 4 rows of this matrix. Each row is a different attack on the same topic.

| Angle | Query shape | Finds |
|---|---|---|
| Entity | `<leader>`, `<leader> alternatives`, `<leader> vs` | Direct competitors, comparison pages |
| Category | `<category term>`, `how to choose <category>`, `<category> landscape` | The industry's own taxonomy, buying guides |
| Chinese | 中文核心词、中文竞品/对比/选型 | Domestic coverage, fresher posts, local vendors |
| Recency | `<topic> 2026`, `<topic> 发布/更新/评测`, `what's new in <topic>` | Current state, recent releases |
| Negative | `<topic> 缺点/踩坑/局限`, `<topic> limitations/problems/criticism` | Failure modes, real-world friction |
| Spec | `<topic> datasheet/specs/API reference` | Primary factual data |
| Pricing | `<topic> pricing/cost/价格/报价` | Commercial positioning |

**Row 4 (Chinese) is not optional for any topic touching Chinese-language markets.** Search the Chinese web natively — translating an English query into Chinese often returns a different, more specific result set rather than the same pages in another language.

## Source tiering

Rank by proximity to the primary artifact, and note the tier in your candidate table.

| Tier | Source type | Use for |
|---|---|---|
| **T1** | Official site, docs, pricing page, spec sheet, changelog, filings | All factual claims — price, version, capability, date |
| **T2** | Technical blogs from practitioners, conference talks, official forum answers | How things actually behave in practice |
| **T3** | Industry media, analyst coverage | Market context, positioning, trend |
| **T4** | Community discussion, user reviews, forum threads | Failure modes, real satisfaction, gaps in official docs |
| **T5** | SEO listicles, aggregator content farms, "best X of 2026" posts | **Discovery only.** Never cite as a source of fact |

T5 deserves emphasis: these pages are frequently AI-generated or affiliate-driven. Use them to find names you missed. Do not copy their claims, and do not cite them.

## Candidate pool format

Record as you search. This is the working ledger for triage:

```json
{
  "entity": "产品或厂商名",
  "url": "https://...",
  "tier": "T1",
  "date": "2026-08-14",
  "angle": "recency",
  "status": "pending",
  "note": "官方定价页，含完整规格"
}
```

`status` transitions: `pending` → `read` | `skip`. When marking `skip`, put the reason in `note` — "登录墙" / "内容与A重复" / "软文无实质信息". Without the reason you will re-discover it in Phase 3 and have no memory of why it was dropped.

## Before-narrowing checklist

- [ ] ≥ 20 candidates recorded
- [ ] ≥ 4 matrix angles run
- [ ] At least one Chinese-language query executed
- [ ] At least one T1 primary source per key entity
- [ ] No entity's pool is entirely T4/T5 (that means you're relying on forum gossip)

## Narrowing criteria

When the pool exceeds ~25 candidates, cut down by these criteria, in order:

1. **Relevance to the comparison axis** — if the axis is price, drop candidates with no public pricing.
2. **Recency** — for fast-moving topics, anything older than the time window becomes a "historical reference" note rather than a primary row.
3. **Entity distinctness** — near-duplicate pages (same content, different domain) collapse to one; keep the T1 version and the URL that is easiest for the reader to verify.
4. **Verifiability** — if a candidate cannot be cited back to a stable URL, it cannot become a row in the deliverable. Note it in a "未获取" list instead.

## The "so what" requirement

A row in the deliverable is not a fact, it is a fact plus its consequence. `价格: $20/月` is a fact. `价格: $20/月, 仅为 A 的 1/4，是其主要价格优势` is a finding. The second one is what the reader can act on.

For every data point you write, ask the one question: *does this change a decision?* If not, it may still belong in the table, but it must not inflate the prose around it.
