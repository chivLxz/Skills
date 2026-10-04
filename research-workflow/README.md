# research-workflow

结构化调研交付 skill：**文本结论出 Excel，视觉结论出带截图的 Word**。

## 解决什么问题

调研交付有两个反复出现的失败模式，本skill 用流程和脚本分别堵住：

| 失败模式 | 对策 |
|---|---|
| 只调研搜索结果前几条，被搜索排序绑架 | Phase 1 强制 5 角度查询矩阵，候选池 ≥ 20 条 |
| 已截止的条目被呈现为可报名 | `validate.py` 机械拒绝「过去日期 + status=open」，有 ERROR 则 exit 1 |
| Excel 与 Word 各写一份数据，内容必然漂移 | 一份 `entries` 数据同时渲染两份文件 |
| 字段留空，读者无法判断是没查到还是没找 | 精确空值词表：`未查到` / `未公开` / `需联系主办方` / `待定` |

## 安装

把整个目录放进 skills 目录：

```bash
# OpenClaw / Claude Code
git clone https://github.com/chivLxz/Skills.git ~/.openclaw/skills/
# 或直接把 research-workflow/ 复制到你的 skills 目录
```

依赖：

- Python 3.9+
- `openpyxl`（Excel 输出）
- `python-docx`（Word 输出）
- 本机Chrome / Chromium / Edge（仅截图功能需要）

```bash
pip install openpyxl python-docx
```

## 用法

直接说「调研一下 X」触发；也可显式调用：

```
/research-workflow 调研一下有哪些适合个人参加的大厂Agent 比赛
```

### 三种交付形态

| 调研内容 | 产出 |
|---|---|
| 参数、价格、规格、功能对比 | `.xlsx` |
| 产品界面、硬件形态、页面布局 | `.docx`（每节配截图） |
| 混合型 | 两者都出，Excel 为对比主干，Word 为视觉附录 |

## 工作流

### Phase 1：全域搜索定范围

目标只���**建候选池**，不做深读。跑 5 个以上角度的查询：

- **实体**：`<leader>`、`<leader> alternatives`、`<leader> vs`
- **品类**：`<category>`、`<category> landscape`
- **中文**：中文核心词（覆盖英文检索拿不到的内容）
- **时效**：`<topic> 2026`、`<topic> 发布/更新/评测`
- **负面**：`<topic> 缺点/踩坑/局限`

来源分五层：**T1** 官方站/文档/定价页 · **T2** 技术博客/官方论坛 · **T3** 行业媒体 · **T4** 社区讨论/评测 · **T5** SEO 榜单（**只用于发现，绝不引用为事实来源**）。

### Phase 1.5：锁定状态

任何有截止期的对象（赛事、招标、发布、峰会）必须带四个字段：

| 字段 | 说明 |
|---|---|
| `status` | `open` / `upcoming` / `closed` / `ongoing` / `unknown` |
| `deadline` | `YYYY-MM-DD`，滚动招领型为 `null` |
| `verified` | 你亲自核验的日期 |
| `source` | 状态从哪读的 |

**规则**：写状态前必须把今天和 `deadline` 比一遍。截止日已过就是 `closed`，无论页面怎么写，除非官方明确宣布延期。状态只取自官方页面——新闻转述和聚合站会过期。查不到就写 `unknown`，绝不猜测。

### Phase 2：判断内容形态

能放进表格（每行一个对象）→ Excel。必须看见才算证据（界面、硬件、页面）→ Word + 截图。两者都做时，**必须共用一份数据**。

### Phase 3：构建

```bash
python scripts/validate.py data.json                    # 先过闸门
python scripts/build_all.py data.json -o out.xlsx --docx out.docx
```

需要截图时：

```bash
python scripts/shoot.py urls.txt -o images/ --width 1440 --height 900
```

`shoot.py` 逐 URL 输出 JSON 状态行；登录墙/空白页要如实记录，不要用占位图替代。

### Phase 4：交付前自检

- [ ] `validate.py` 报 0 错误
- [ ] Excel 与 Word 条目一一对应，状态一致
- [ ] 每个有截止期的对象都与今天比对过
- [ ] **表名与内容一致**（名为「可报名」的表里不能有已截止项）
- [ ] 每行有来源 URL
- [ ] 空字段用了精确空值，不是空白
- [ ] 必填矩阵完整：参与方式、身份门槛、时间窗口
- [ ] 打开文件确认版式正常、无缺图标记

## 数据格式

```json
{
  "meta": { "title": "...", "collected_at": "2026-10-03" },
  "columns": [{ "key": "name", "title": "名称", "width": 30 }],
  "entries": [
    {
      "id": "stable-slug",
      "name": "示例名称",
      "status": "open",
      "deadline": "2026-12-01",
      "verified": "2026-10-03",
      "source": "https://official.example.com",
      "fields": { "name": "示例名称", "status": "open" },
      "doc": { "intro": "开篇即结论。", "blocks": [{ "type": "para", "text": "..." }] }
    }
  ]
}
```

填空的完整模板见 [`assets/unified-template.json`](assets/unified-template.json)，含 `ongoing` 与 `unknown` 两种特殊状态的写法。

## 脚本

| 脚本 | 用途 |
|---|---|
| `validate.py` | **交付前必跑**。校验状态/截止日一致性、必填字段、Excel↔Word 对应 |
| `build_all.py` | 首选渲染器。一份数据 → xlsx + docx |
| `build_xlsx.py` | 仅 Excel |
| `build_docx.py` | 仅 Word |
| `shoot.py` | 批量 URL 截图（无头 Chrome） |

## 文档

- [`references/search-strategy.md`](references/search-strategy.md) — 查询矩阵、来源分层、反锚定
- [`references/status-and-completeness.md`](references/status-and-completeness.md) — 状态定义、截止日规则、必填矩阵
- [`references/excel-output-spec.md`](references/excel-output-spec.md) — 表格约定
- [`references/word-output-spec.md`](references/word-output-spec.md) — 文档结构与截图规则
- [`references/no-filler-rules.md`](references/no-filler-rules.md) — 禁用话术、压缩规则

## License

MIT
