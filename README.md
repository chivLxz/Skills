# OpenClaw Skills

My collection of OpenClaw agent skills.

## Skills

- [cn-ai-news-digest](./cn-ai-news-digest/) - 国内 AI 行业资讯日报，覆盖 7 个中文科技媒体
- [arch-mindmap](./arch-mindmap/) - 读懂项目/代码库，产出**多层、可编辑、说人话**的思维导图（Markdown 大纲 + .xmind + SVG / PNG / PDF）。主干深挖到 5~7 层但保留采样率/时延/阈值这类产品参数，剔除环境变量与函数名这类代码标识符；零第三方依赖
- [research-workflow](./research-workflow/) - 结构化调研交付：**文本结论出 Excel，视觉结论出带截图的 Word**。先做≥20 条候选网页的全域搜索定范围，再按内容形态分流；内建状态闸门，机械拒绝「已截止却标为可报名」的条目

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
