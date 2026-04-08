---
name: cn-ai-news-digest
version: "1.1.0"
description: "国内顶级科技媒体 AI 资讯日报。从7个中文科技媒体 RSS 并行抓取 AI 新闻，经去重和筛选后，由（本Agent自身）LLM 智能分类为四大板块：AI大模型、AI软件产品、AI硬件产品、AI公司股票，每类不少于5条，输出 Markdown 表格。当用户说AI资讯、AI新闻、今天的AI动态、AI日报等时触发。"
---

# CN AI News Digest v1.1.0

国内 AI 行业资讯日报，覆盖 7 个中文科技媒体，全自动流水线处理。

## Pipeline 总览

```
RSS抓取(Python) → 去重(Python) → LLM分类(OpenClaw Agent自身) → 输出
```

### Step 1: RSS 抓取 (Python)

7 个数据源，全部使用直接 RSS feed：

| 媒体 | RSS 地址 |
|------|----------|
| 量子位 | `https://www.qbitai.com/feed` |
| 36氪 | `https://36kr.com/feed` |
| 机器之心 | `https://www.jiqizhixin.com/rss` |
| InfoQ 中文 | `https://www.infoq.cn/feed` |
| 爱范儿 | `https://www.ifanr.com/feed` |
| 钛媒体 | `https://www.tmtpost.com/rss` |
| 雷锋网 | `https://www.leiphone.com/feed` |

Python 脚本职责：
- 并行抓取 7 个 RSS feed
- XML 解析失败时自动降级为正则提取（兼容格式异常的 feed）
- 提取字段：title、link、description、pubDate、source_name
- AI 关键词预过滤（宽松匹配）
- 标题去重（前 25 字符）
- 日期过滤（当天不足 20 篇时扩展到近 3 天）
- 输出干净的 JSON 数组到 stdout 或 --output 文件

输出格式：
```json
[
  {
    "title": "标题",
    "link": "https://...",
    "description": "摘要文本（来自RSS feed）",
    "source": "来源媒体名",
    "pub_date": "2026-04-06T10:30:00+08:00"
  }
]
```

### Step 2: 去重 (Python)

- 以标题前 25 字符为 key 去重
- 跨源去重，避免不同媒体报道同一新闻时重复

### Step 3: LLM 分类 (OpenClaw Agent 自身)

Python 脚本不再调用 LLM，只负责数据抓取。分类工作由 OpenClaw Agent 自身完成，使用 Agent 自带的模型能力。

Agent 分类 Prompt：

```
请将以下 AI 新闻按四大分类进行归类，每篇文章只属于一个分类。

四大分类定义：

1. AI大模型 (Foundation Models & Algorithms):
   核心范围是国内外主流LLM及多模态模型的技术迭代与生态演进。
   收录模型新版本发布、评测榜单变动、重大技术突破、核心算法研究。

2. AI软件产品 (Software, Agents & Applications):
   核心范围是AI技术在纯软件层面的落地应用与工具生态。
   收录生产力工具发布更新、Agent框架演进、开发者AI工具链、端侧推理框架。

3. AI硬件产品 (Hardware, Chips & Smart Terminals):
   核心范围是AI的实体物理载体。
   收录AI处理器新架构发布、算力评测、AIPC/AI手机/AI穿戴设备/具身智能/自动驾驶硬件、边缘计算设备。

4. AI公司股票 (AI Capital, A-Shares & HK Stocks):
   核心范围是AI产业链商业化与资本市场。
   收录A股/港股/美股AI概念异动、宏观政策、独角兽融资IPO、大厂财报并购人事变动。

执行约束：
- 绝对禁止重复（同一篇不能出现在多个分类）
- 摘要50-80字精简
- 以Markdown表格输出：| # | 标题 | 摘要 | 来源 |
- 某类无相关新闻则显示"今日无相关资讯"

新闻列表：
[在此处粘贴Python脚本输出的JSON数据]

请输出完整的分类结果，包含四大板块。
```

### Step 4: 输出

以 Markdown 表格格式输出分类结果：

```markdown
## AI大模型 (Foundation Models & Algorithms)

| # | 标题 | 摘要 | 来源 |
|---|------|------|------|
| 1 | [标题](链接) | 50-80字摘要 | 量子位 |

## AI软件产品 (Software, Agents & Applications)

...

## AI硬件产品 (Hardware, Chips & Smart Terminals)

...

## AI公司股票 (AI Capital, A-Shares & HK Stocks)

...
```

## 使用方式

```bash
# Agent 调用（推荐）
python3 ${SKILL_DIR}/scripts/fetch_ai_news.py --output /tmp/ai_news_today.json

# 指定日期
python3 ${SKILL_DIR}/scripts/fetch_ai_news.py --date 2026-04-05 --output /tmp/ai_news.json

# 限制最大文章数
python3 ${SKILL_DIR}/scripts/fetch_ai_news.py --max-articles 50
```

Agent 工作流：
1. 执行 Python 脚本获取 JSON 格式的新闻列表
2. 使用 Agent 自身的 LLM 能力进行分类
3. 输出分类结果为 Markdown 表格

## 文件结构

```
cn-ai-news-digest/
├── SKILL.md                          # 本文件
└── scripts/
    └── fetch_ai_news.py              # 主脚本（纯 Python 标准库）
```

## 技术约束

- **纯标准库**：仅用 Python 标准库（urllib、xml、json、re），无第三方依赖
- **无 Playwright**：所有源均通过 RSS feed 获取，无需浏览器爬取
- **无 LLM 调用**：Python 脚本不调用任何 LLM API，分类由 Agent 自身完成
- **容错设计**：XML 解析失败时自动降级为正则提取
- **智能扩展**：文章不足时自动扩展日期范围，确保分类内容充实
- **无环境变量依赖**：不需要 LLM_API_KEY、LLM_BASE_URL 等环境变量
