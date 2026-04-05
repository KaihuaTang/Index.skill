# <img src="./assets/index-icon.png" width="40" height="40" style="border-radius: 50%; vertical-align: middle;" /> 茵蒂克丝.skill（LLM Wiki）

茵蒂克丝.skill是一套运行在 [Claude Code](https://claude.ai/code) 上的一整套知识管理、更新、与交互技能（Skills），能够接受任意输入（文字、网址、文件、代码仓库），自动分类并生成结构化的 [Obsidian](https://obsidian.md/) 笔记，然后通过整理归档后生成层级化的永久记忆库，并可以基于该记忆库进行交流。所有记忆都可通过Obsidian进行展开，做到思维透明。

题外话：该项目的想法在和相关老师交流后，最早在2026.03.30完成设计[草稿](./assets/design-draft.jpg)(链接可以看到当时的手写设计草案)，目的是基于自己的实际工作流，来做一个自己也会使用的知识管理与交互工具。然而有趣的是就在2026.04.03 Karpathy提出了非常相似的LLM-KiWi概念，只能说好的想法总是会趋同演化。因此我也不得不加快步伐开始完善原型。目前项目的核心功能如下：

- 初始化一个你喜欢的“茵蒂克丝”知识库性格，这会让后续交互更符合个人喜好。
- 可以将不同类型的信息与文档都整理为统一的临时Obsidian笔记，以供查阅。
- 定期将“已阅”的笔记统一归档到层级化的记忆空间（也是Obsidian）。
- 基于自定义的性格与记忆空间中的知识进行自由的交流和问答。

## 快速开始

### 前置要求

- [Claude Code](https://claude.ai/code) CLI 环境
- [uv](https://docs.astral.sh/uv/) Python 包管理器（用于运行辅助脚本）
- [Obsidian](https://obsidian.md/)（可选，用于阅览生成的笔记）

### 第一步：初始化

```
/index-init
```

该指令会：

1. **创建 Obsidian 知识库目录** — 包含 `_new`（新笔记）、`_template`（模板）、`_images`（图片）、`_downloads`（下载缓存）等子目录
2. **部署 6 种笔记模板** — 想法、项目、书籍、论文、网页信息、网络新闻各一套
3. **配置 Agent 人格** — 通过交互问答设置你的职业和期望的 Agent 风格

初始化过程中会询问两类信息：

**职业领域**
> 请问您从事的工作与专业领域是什么？

**Agent 人格（MBTI 四维度）**

系统会逐个询问你希望 Agent 具备的特质：

| 维度 | 选项 | 影响 |
|------|------|------|
| 能量方向 | E 外向 / I 内向 | Agent 主动发散 vs 深入聚焦 |
| 信息获取 | S 感觉 / N 直觉 | Agent 注重细节 vs 关注模式 |
| 决策方式 | T 思考 / F 情感 | Agent 理性分析 vs 温暖共情 |
| 工作风格 | J 判断 / P 知觉 | Agent 结构有序 vs 灵活开放 |

完成后会在知识库根目录生成 `persona.md`，包含 MBTI 类型描述和 5 项自动推导的认知特质。

---

### 第二步：开始记录

```
/index-note INPUT_STRING
```

输入任意字符串，系统自动识别类型并生成对应格式的 Obsidian 笔记。

## 支持的输入类型

| 类型 | 输入示例 | 自动识别方式 |
|------|---------|-------------|
| **想法** | `大语言模型的推理可能本质上是模式匹配` | 纯文本 |
| **项目** | `https://github.com/anthropics/claude-code` | GitHub URL |
| **项目** | `C:\Projects\my-app` | 本地文件夹路径 |
| **论文** | `https://arxiv.org/abs/2501.12948` | arXiv URL |
| **论文** | `2501.12948` | 裸 arXiv ID |
| **书籍** | `C:\Books\design_of_everyday_things.pdf` | 本地 PDF/DOCX/TXT |
| **网页信息** | `https://huggingface.co/blog/open-llm-leaderboard` | 通用网页 URL |
| **网络新闻** | `https://www.reuters.com/technology/...` | 新闻域名 |

对于不确定的输入（如 PDF 可能是论文也可能是书籍），系统会进行内容分析后自动判断。

## 输出格式

每次调用生成一个 Obsidian Markdown 文件，保存在 `IndexVault/_new/` 下：

```
文件名格式：YYYY-MM-DD_类型_序号.md

示例：
  2026-04-05_idea_001.md
  2026-04-05_paper_002.md
  2026-04-05_webnews_001.md
```

### 笔记结构

所有笔记遵循基于认知科学的统一设计原则：

- **TL;DR 置顶** — 每篇笔记开头都有 1-3 句摘要（认知负荷理论）
- **自我解释** — 论文笔记包含"用我自己的话"段落，强制深度理解（自我解释效应）
- **类型化关联** — 连接其他笔记时标注关系类型：支撑/矛盾/延伸/类比（Zettelkasten）
- **So What?** — 每篇笔记必须回答"这对我意味着什么"（精细加工）
- **检索提示** — 以场景触发问题结尾："什么时候我会回来翻这篇笔记？"（测试效应）

### 六种笔记模板一览

| 模板 | 核心板块 | 特色 |
|------|---------|------|
| **想法** | 核心想法 → 假设风险表 → 关联网络 → 最小验证实验 | maturity 字段追踪想法成熟度（seed/sprout/tree） |
| **论文** | In My Own Words → 方法架构 → 实验结果 → 批判分析 → 领域定位 | 带评分理由的五维评价表 + 永久笔记提炼 |
| **书籍** | 核心论点 → 关键概念 → 结构图 → 与作者对话 → 立即应用 | 避免冗余章节摘要，用论证脉络图替代 |
| **项目** | 问题与方案 → 适用场景表 → 架构概览 → 设计洞察 | "When to Use / When Not to Use"决策表 |
| **网页信息** | SIFT 可信度速查 → 事实/观点/预测分离 → So What? | info_half_life 字段标注信息保鲜期 |
| **网络新闻** | 5W1H 紧凑表 → 信号 vs 噪音 → 我的预测 | 个人预测含验证时间线，培养判断力 |

## 图片提取

对于 **论文** 和 **书籍**（PDF 格式），系统会自动提取图片：

- **论文**：三级优先级 — arXiv 源码包图片 > PDF figure 转换 > PDF 直接提取
- **书籍**：从 PDF 中提取（过滤小于 200x200 像素的图标）
- **项目**：扫描 docs/、assets/、images/ 等目录

提取的图片保存在 `_images/` 目录下，并自动嵌入到笔记的对应位置。

## Web UI

茵蒂克丝.skill 提供基于浏览器的 Web 界面，无需 Obsidian 即可完成初始化、笔记浏览和信息录入。

### 启动

```bash
uv run --with flask --with python-frontmatter python webUI/app.py
```

服务启动后访问 `http://localhost:5000`。

### 三个界面

| 界面 | 路径 | 说明 |
|------|------|------|
| **初始化向导** | `/init` | 首次使用时自动进入，设置职业和 Agent MBTI 人格（等同 `/index-init`） |
| **笔记库** | `/vault` | 浏览所有已生成的笔记，支持按类型筛选，点击查看完整渲染内容 |
| **信息录入** | `/vault` → 新建笔记 | 三种输入方式（文本 / 文件上传 / URL），提交后自动调用 `/index-note` 流程 |

- 如果尚未初始化（无 `persona.md`），访问首页会自动跳转到初始化向导
- 笔记库与信息录入通过顶部导航栏按钮切换
- 笔记详情页支持 Obsidian 特有格式的渲染：Callout 块、Wikilink、数学公式、图片嵌入

## 目录结构

```
茵蒂克丝.skill/
├── skills/
│   ├── index-init/          # 初始化技能
│   │   ├── SKILL.md
│   │   └── resources/       # 6 个模板源文件
│   └── index-note/          # 知识记录技能
│       ├── SKILL.md
│       └── scripts/
│           ├── classify_input.py    # 输入分类器
│           ├── extract_images.py    # 图片提取器
│           └── generate_id.py       # 序号生成器
├── webUI/                   # Web 界面
│   ├── app.py               # Flask 应用
│   ├── static/              # CSS + JS 静态资源
│   └── templates/           # Jinja2 页面模板
├── IndexVault/            # Obsidian 知识库（index-init 创建）
│   ├── _new/                # 生成的笔记
│   ├── _template/           # 笔记模板
│   ├── _images/             # 提取的图片
│   ├── _downloads/          # 下载缓存
│   ├── persona.md           # Agent 人格配置
│   └── .obsidian/           # Obsidian 配置
├── CLAUDE.md
└── README.md
```

## 在 Obsidian 中使用

初始化完成后，用 Obsidian 打开 `IndexVault` 文件夹即可：

1. 打开 Obsidian → "打开文件夹作为仓库" → 选择 `IndexVault`
2. 在左侧文件浏览器中查看 `_new/` 目录下的笔记
3. 利用 Obsidian 的反向链接和图谱视图查看笔记间的关联
4. 可将 `_new/` 中的笔记整理到自定义文件夹中长期存放
