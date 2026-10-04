# arch-mindmap —— 把项目变成一张能改的思维导图

给 Agent（Codex CLI / Claude Code / 其他）装一个技能：读懂你的项目，产出**多层、能继续编辑**的思维导图。

四个设计决定：

1. **不套模板。** 一级分支按什么维度切，由项目的真实结构和你的目的推导，不是从预设视图里挑一个。
2. **深度由信息决定。** 主干分支一路挖到 5～7 层，落到文件名、接口名、参数值这一级；外围分支保持 2～3 层。不平均用力，也不因为「图会变大」就停在两三层。
3. **先出 Markdown 大纲，再转格式。** 大纲能改、能 diff、能进 Git；改完重跑转换即可，AI 的分析结论不会丢。
4. **不依赖 MCP。** `.xmind` 用纯 Python 直接按 Xmind 官方 SDK 的格式写出来 —— 不用 npx、不联网、不会卡在冷启动超时上。

---

## 一、安装

从仓库装（推荐）：

```bash
git clone --depth 1 https://github.com/chivLxz/Skills /tmp/Skills
mkdir -p ~/.codex/skills
cp -r /tmp/Skills/arch-mindmap ~/.codex/skills/
```

或从本地目录装：

```bash
mkdir -p ~/.codex/skills
cp -r ./arch-mindmap ~/.codex/skills/
```

重启后在 Codex 里用 `$arch-mindmap` 调用（Claude Code 用 `/arch-mindmap`）。`/skills` 可确认是否已加载。

> 装的时候传 `arch-mindmap/` 这一层，进到 skills 目录后会变成 `~/.codex/skills/arch-mindmap/SKILL.md` —— Codex 认这个路径，不要再套一层。
>
> `example/` 只是一份示例产物，不参与技能运行，装的时候可以删掉。

---

## 二、你会拿到什么

```
你的项目 ──AI 读懂──> Markdown 大纲 ──转换──> .xmind / .svg / .png / .pdf
                          ↑
                    你在这里改
```

| 产物 | 能改吗 | 怎么用 |
|---|---|---|
| `.md` | ✅ 纯文本 | **真相来源**。改它，然后重跑转换 |
| `.xmind` | ✅ Xmind 里直接编辑 | 交付、协作、二次加工 |
| `.svg` | ✅ 矢量，Illustrator / Figma / Inkscape 可编辑 | 精修排版、嵌网页 |
| `.png` | ❌ 图片 | 贴文档、发消息、插 PPT |
| `.pdf` | ❌ 单页矢量 | 打印、正式汇报 |

Xmind 免费版就能永久编辑本地文件（只有导出 PNG/PDF 才需要订阅）。

---

## 三、跑一次要什么

| 环节 | 依赖 | 没有会怎样 |
|---|---|---|
| `.md` → `.xmind` | 无（纯 Python 标准库） | 不会怎样，必成 |
| `.md` → `.svg` | 无（纯 Python） | 不会怎样，必成 |
| `.svg` → `.png` / `.pdf` | 本机 Chrome / Edge / Chromium | 只出 SVG，脚本会明确告诉你 |

也就是说：**没有浏览器也能拿到可编辑的 `.xmind` 和矢量 `.svg`**，只是少了图片和 PDF。

浏览器找不到时可指定：

```bash
export CHROME_PATH="/path/to/chrome"
```

---

## 四、手动跑

```bash
SKILL=~/.codex/skills/arch-mindmap

python3 $SKILL/scripts/md2xmind.py ./mindmap/outline.md ./mindmap/outline.xmind
python3 $SKILL/scripts/render.py  ./mindmap/outline.md --outdir ./mindmap
```

常用参数：

```bash
# 换布局：默认思维导图，可选 logic-right / logic-left / tree-right / org-chart / timeline
python3 $SKILL/scripts/md2xmind.py outline.md outline.xmind --structure logic-right

# 只要某几种产物
python3 $SKILL/scripts/render.py outline.md --outdir . --only svg,png

# 指定超采样倍率（默认按画布尺寸自动选 1~4 倍）
python3 $SKILL/scripts/render.py outline.md --outdir . --scale 2
```

产物命名与输入同名，只换扩展名。

---

## 五、Markdown 大纲的写法

**标题给主干，列表给深挖。** 两种写法可以混用。

```markdown
# 中心主题

## 一级分支
### 二级分支
#### 三级分支
##### 四级分支
###### 五级分支
- 六级分支（列表顶格）
  - 七级分支（每缩进 2 空格加一级）
    - 八级分支
```

为什么要有列表这一路：**Markdown 标题只有 6 级**，`#` 又占掉中心主题，光靠标题最深只能到 5 层。超过的部分用嵌套列表接着写，**层数没有上限**。

| 写法 | 效果 |
|---|---|
| `## 语音前端 \`src/audio/frontend\`` | 标题只留「语音前端」，路径进节点**备注**（Xmind 里能溯源） |
| `### 声纹识别 ⚠` | 去掉符号，在 Xmind 里变成「待复核」标签、在图上变成橙色下划线 |
| `## A` 直接跳到 `##### B` | 自动压平成连续层级，不会出现断层 |
| 开头带 YAML frontmatter | 自动跳过，里面的列表不会被误当成节点 |

**一条建议**：大纲文件里只写标题和列表，不要夹正文段落 —— 正文里的列表会被当作节点解析。

---

## 六、图太大了怎么办

深度放开之后图会变大。**别靠砍深度来控制规模，靠拆图。**

单张图节点超过约 **180 个**，或某个一级分支自己就超过约 **60 个节点**时，拆成「总览图 + 分支详图」：

- **总览图** —— 全部一级分支，最多 2～3 层，让人一眼看清全局
- **分支详图** —— 那个庞大的分支单独成图，从自己开始一路展开到叶子

各自是独立的 `.md`，各自转换。技能里已经写了这条规则，AI 会自己判断。

---

## 七、为什么没用 markmap / MCP

**markmap 渲染不可靠。** 它靠浏览器端 JS 现算布局，在无头环境下页面经常在真正绘制前就「空闲」了，Chrome 于是截出白图 —— 同一份文件连跑三次，结果会不一样。本项目的图由纯 Python 算好坐标再输出静态 SVG，没有 JS、没有网络，**结果逐像素可复现**。

**MCP 会卡。** `xmind-generator-mcp` 走 `npx`，Codex 的 MCP `startup_timeout_sec` 默认只有 10 秒，冷启动必超时；沙箱还会拦网络。这里改成直接写文件：格式严格对齐 Xmind 官方 SDK（`xmindltd/xmind-generator`）的 `content.json` / `metadata.json` / `manifest.json` 结构，跳过一切中间环节。

---

## 八、免踩坑清单

| 坑 | 现象 | 解法 |
|---|---|---|
| 调用符号 | `$arch-mindmap` 没反应 | Codex 用 `$` 不是 `/`；先跑 `/skills` 确认已加载 |
| 图画得太浅 | 只有两三层，全是模块名 | 这是分析问题不是脚本问题：让 Agent 按技能里的「逐层展开检查表」再走一遍，先补齐侦察 |
| 沙箱拦外部进程 | 生成 PNG/PDF 时报错 | 用 `--only svg` 只出矢量图，或让宿主放行 |
| 图太挤 | 节点打架、看不清 | 触发技能里的分图规则；或 `--only svg` 后用矢量工具调间距 |
| AI 编模块名 | 图上出现项目里没有的东西 | 技能里已强制禁止 + 推断项必须标 `⚠`；看到 ⚠ 就人工核一遍 |
| 中文变方框 | PNG 里中文显示异常 | 系统缺中文字体，装思源黑体或苹方 |

---

## 九、实测记录（2026-10-04，macOS / Chrome / Xmind 26.05）

样例：79 节点大纲（6 个一级 / 14 个二级 / 32 个三级 / 19 个四级 / 6 个五级 / 2 个六级）

| 验证项 | 结果 |
|---|---|
| `.xmind` 产出 | 8.5 KB，zip 内含 `content.json` + `metadata.json` + `manifest.json`，STORE 压缩 |
| 格式兼容性 | 用第三方库 `xmindparser` 反解成功，层级与备注全部正确 |
| 布局字段合法性 | `org.xmind.ui.map.unbalanced` 等常量在本机 Xmind 26.05 资源中确认存在 |
| `.svg` | 1013 × 1446 px，32 KB，纯静态矢量 |
| `.png` | 2861 × 4144 px，711 KB，3 倍超采样后自动裁边 |
| `.pdf` | 单页矢量，365 KB，字体内嵌 |
| SVG 确定性 | 同一输入连跑 3 次，字节完全一致 |
| XMind 确定性 | 结构完全一致，差异仅来自节点 UUID（随机属预期） |

边界测试：

| 用例 | 结果 |
|---|---|
| 空文件 / 无标题 | 明确报错退出码 3，不产生半成品文件 |
| 只有一条单链 | 正常展开 |
| 跳级（`##` 直跳 `#####`） | 自动压平成连续层级 |
| 有序列表 `1.` / 嵌套缩进 | 正确解析 |
| 开头带 YAML frontmatter | 正确跳过，不污染节点 |
| 极深 13 层单链 | 12 层全部渲染，视觉分层不塌 |
| 350 节点大图 | 0.12 秒解析、2.3 秒出全套图；自动从窄长条切成两翼布局 |
| 标题含 `<&>"'` 等特殊字符 | SVG 转义正确，不破图 |

---

## 十、文件清单

```
arch-mindmap/
├── SKILL.md                 # 技能主体 —— 放 ~/.codex/skills/arch-mindmap/
├── README.md                # 本文件
├── scripts/
│   ├── md2xmind.py          # Markdown → .xmind（零依赖，对齐 Xmind 官方 SDK 格式）
│   ├── md2svg.py            # Markdown → 矢量 SVG（自算布局，7 级视觉分层）
│   └── render.py            # 编排：SVG / PNG / PDF（PNG、PDF 需要本机浏览器）
└── example/                 # 一份 6 层示例大纲与四类产物
    ├── example-outline.md
    ├── example-outline.xmind
    ├── example-outline.svg
    ├── example-outline.png
    └── example-outline.pdf
```

脚本零第三方依赖（`render.py` 的裁边功能会用 Pillow，没装则跳过裁边，不影响出图）。

---

## 版本

- **v1.1.0** —— 深度放开：删除「层级 ≤4」限制，支持嵌套列表突破 Markdown 六级标题上限；侦察改为「建地图 + 定向深读」两轮；新增逐层展开检查表与深度预算；渲染视觉分层从 3 档扩到 7 档。
- **v1.0.0** —— 初版：Markdown 大纲 → .xmind / SVG / PNG / PDF。

---

可自由使用与修改。
