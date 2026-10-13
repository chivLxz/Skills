# OpenClaw Skills

My collection of OpenClaw agent skills.

## Skills

- [cn-ai-news-digest](./cn-ai-news-digest/) - 国内 AI 行业资讯日报，覆盖 7 个中文科技媒体
- [arch-mindmap](./arch-mindmap/) - 读懂项目/代码库，产出**多层、可编辑、说人话**的思维导图（Markdown 大纲 + .xmind + SVG / PNG / PDF）。主干深挖到 5~7 层但保留采样率/时延/阈值这类产品参数，剔除环境变量与函数名这类代码标识符；零第三方依赖
- [research-workflow](./research-workflow/) - 结构化调研交付：**文本结论出 Excel，视觉结论出带截图的 Word**。先做≥20 条候选网页的全域搜索定范围，再按内容形态分流；内建状态闸门，机械拒绝「已截止却标为可报名」的条目
- [edu-pm-workflow-v2](./edu-pm-workflow-v2/) - 产品需求全流程工作流 v2：把一句需求落成**可评审的 HTML PRD + 可交互原型 + 流程图 + 验收清单**。产出原型前必问「形态 / 来源 / 落点」，基于已有代码库**先侦察后实现**；**PRD 与原型代码强绑定**（产出 PRD 必须同步改代码，图必须是代码的真实渲染）；双栏预览**三级滚动同步**（页面 / 状态 / 元素）

### research-workflow 速览

四阶段流程，每阶段都有可执行的准入条件：

| 阶段 | 做什么 | 防的是什么 |
|---|---|---|
| Phase 1| 5 角度查询矩阵，候选池 ≥ 20 条，来源分 T1–T5 层 | 被搜索排序绑架，只调研前几条 |
| Phase 1.5 | 每个有截止期的条目锁定 `status`/`deadline`/`verified`/`source` | 已截止的赛事被当成可报名 |
| Phase 2 | 判断内容形态 → 出 Excel（可比较）或 Word+截图（须看见） | 强行把截图类内容塞进表格 |
| Phase 3 | `validate.py` 校验 → `build_all.py` 一份数据渲染两份文件 | Excel 与 Word 内容漂移 |
| Phase 4 | 8 项自检 + 校验器 exit 1 阻断 | 表名与内容矛盾、缺失字段 |

**两份交付物来自同一份数据**：`entries[].fields` 渲染成Excel 行，`entries[].doc` 渲染成 Word 章节，状态列由脚本自动注入—— 所以两者不可能对不上。

```bash
python scripts/validate.py data.json          # 有 ERROR 则禁止交付
python scripts/build_all.py data.json -o out.xlsx --docx out.docx
```

**依赖**：`openpyxl`、`python-docx`，截图需本机 Chrome /Chromium / Edge。无其他依赖。

**隐私**：`shoot.py` 只在本地启动无头浏览器截图，不上传任何内容；纯文本调研全程无需联网浏览器。

### edu-pm-workflow-v2 速览

产出一份 PRD 时要过的几道硬门禁：

| 门禁 | 要求 | 防的是什么 |
|---|---|---|
| 问三 · 落点 | 基于已有代码库时必问：**就地改宿主页** / **独立工作区 + `MERGE-NOTES.md`** / **新版本全量目录** | 「只出文档、代码一字节没动」——首次实战就是这样被用户判为不合格 |
| §3.7 先侦察后实现 | 动手前先定位宿主页、技术栈、命名风格、既有弹窗组件，并回报落点确认 | 把 from-scratch 默认套路（Tailwind / `.device` / 默认产出路径）盖到已有代码库上 |
| §3.9 图 ↔ 代码绑定 | PRD 的每张原型图必须是**本次真实改过的代码**渲染出来的，图 `mtime` ≥ 代码 `mtime` | 手绘 / 设计工具另做 / 别处拷来 / 上一版旧图 |
| §2.6 ⑧ 三级滚动同步 | 左侧滚到某行 → 右侧 L1 换页 / L2 进状态（弹窗、置灰、成功态）/ L3 高亮元素 | 「以为做了元素级同步、其实只到页面级」 |

```bash
python assets/scripts/validate_prd.py "需求名/需求文档/需求名-PRD.html"   # 交付前必跑
```

**依赖**：Python 3.9+；截图引擎优先复用本机 Chrome / Edge，正常情况零下载。
