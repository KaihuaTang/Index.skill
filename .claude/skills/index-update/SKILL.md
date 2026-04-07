---
name: index-update
description: 整理已读笔记与聊天记录至分层知识库，归档至深度记忆 / Organize read notes and chat logs into hierarchical memory system, archive to deep memory
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

You are IndexUpdate, the Knowledge Librarian.

# Objective

Scan `_new/` for notes marked as "已读", extract knowledge from each, organize it into the hierarchical memory system in `memory/`, and archive the note to `deep/`. Then process chat logs in `_chat/`: apply any persona updates to `persona.md`, extract new knowledge from user-provided information, and archive chat files to `deep/`.

**Usage**: `/index-update`

# Important Paths

```
VAULT_PATH     = ./IndexVault
NEW_DIR        = ./IndexVault/_new
DEEP_DIR       = ./IndexVault/deep
MEMORY_DIR     = ./IndexVault/memory
CHAT_DIR       = ./IndexVault/_chat
PERSONA_FILE   = ./IndexVault/persona.md
RESOURCES_DIR  = ./skills/index-update/resources
```

---

# Memory System Architecture

The memory system uses a **layered index design** — never load all knowledge at once. Navigate top-down through indexes:

```
memory/
├── memory-index.md                 # Level 0: Route to knowledge category
├── 事实性记忆/                      # Factual: "是什么"
│   ├── _local_index.md         # Level 1: Route to keyword file
│   └── {KEY_WORD}.md               # Level 2: Actual knowledge entries
├── 程序性记忆/                      # Procedural: "怎么做"
│   ├── _local_index.md
│   └── {KEY_WORD}.md
├── 条件性记忆/                      # Conditional: "何时/为何用"
│   ├── _local_index.md
│   └── {KEY_WORD}.md
└── 元认知记忆/                      # Metacognitive: "怎么学/怎么错"
    ├── _local_index.md
    └── {KEY_WORD}.md
```

### Four Knowledge Categories

| Category | What it stores | Examples |
|----------|---------------|----------|
| 事实性记忆 (Factual) | "是什么" — definitions, facts, formulas, architectures, benchmarks, taxonomies | Transformer的定义, BLEU分数含义, ResNet架构 |
| 程序性记忆 (Procedural) | "怎么做" — methods, algorithms, workflows, implementation steps, code patterns | LoRA微调流程, Docker部署步骤, Git rebase操作 |
| 条件性记忆 (Conditional) | "何时/为何用" — when to use which method, trade-offs, comparisons, selection criteria, failure modes | 何时用Adam vs SGD, CNN vs ViT的选择, 分布式训练的适用场景 |
| 元认知记忆 (Metacognitive) | "怎么学/怎么错" — learning strategies, common pitfalls, mental models, personal reflections, anything else | 论文阅读方法论, 常见调参误区, 我的研究盲区 |

---

# Workflow

## Step 0: Ensure Memory Structure Exists

Check if `./IndexVault/memory/memory-index.md` exists. If not, initialize the full structure:

```bash
mkdir -p "./IndexVault/_new" \
         "./IndexVault/deep" \
         "./IndexVault/_chat" \
         "./IndexVault/memory/事实性记忆" \
         "./IndexVault/memory/程序性记忆" \
         "./IndexVault/memory/条件性记忆" \
         "./IndexVault/memory/元认知记忆"
```

Then copy templates from resources:
```bash
cp ./skills/index-update/resources/memory-index.md ./IndexVault/memory/memory-index.md
cp ./skills/index-update/resources/_local_index.md "./IndexVault/memory/事实性记忆/_local_index.md"
cp ./skills/index-update/resources/_local_index.md "./IndexVault/memory/程序性记忆/_local_index.md"
cp ./skills/index-update/resources/_local_index.md "./IndexVault/memory/条件性记忆/_local_index.md"
cp ./skills/index-update/resources/_local_index.md "./IndexVault/memory/元认知记忆/_local_index.md"
```

If memory structure already exists, skip this step.

## Step 1: Scan for Read Notes

Use Glob to find all `.md` files in `_new/`:

```
Glob: pattern = "*.md", path = "./IndexVault/_new"
```

For each file found, use Grep to check for the **checked** read marker:

```
- [x] <big><big>已读</big></big>
```

**Unchecked** (not yet read, skip these):
```
- [ ] <big><big>已读</big></big>
```

If no read notes are found, skip Step 2 and proceed to Step 3 (Process Chat Logs).

## Step 2: Process Each Read Note

For each read note, perform Steps 2a → 2b → 2c → 2d sequentially.

### Step 2a: Read the Note

Read the full note content. Extract:
- **note_id**: from filename (e.g., `2026-04-05_paper_001`)
- **note_type**: from filename (idea/paper/project/book/webinfo/webnews)
- **title**: from frontmatter `title` field or first `#` heading
- **key_content**: TL;DR, main analysis, connections, "So What?" sections

### Step 2b: Archive the Note (Safe Move)

**Archive FIRST, before updating memory.** This ensures all knowledge entry links point to `deep/` where the note actually resides.

Move the note from `_new/` to `deep/` using the **safe move** procedure to avoid overwriting existing files:

```bash
FILENAME="{filename}"
TARGET="./IndexVault/deep/$FILENAME"
if [ -f "$TARGET" ]; then
    # File already exists in deep/ — add random suffix to avoid overwrite
    BASENAME="${FILENAME%.md}"
    SUFFIX=$(od -An -tx1 -N4 /dev/urandom | tr -d ' \n')
    FILENAME="${BASENAME}_${SUFFIX}.md"
    TARGET="./IndexVault/deep/$FILENAME"
fi
mv "./IndexVault/_new/{original_filename}" "$TARGET"
```

**Important**: If the filename was changed due to dedup, use the **new filename** (with suffix) as the `note_id` in all subsequent wikilinks for `来源` fields in memory entries.

### Step 2c: Extract Knowledge Items

Analyze the note and extract **discrete knowledge items**. Each item has:

| Field | Description | Example |
|-------|-------------|---------|
| `keyword` | Broad conceptual keyword, PascalCase English | `LLM`, `Diffusion`, `AttentionMechanism` |
| `summary` | Concise self-contained summary (1-3 sentences, Chinese) | Transformer使用自注意力机制并行处理序列... |
| `category` | One of 4 knowledge types | 事实性记忆 |
| `entry_title` | Short descriptive title (Chinese) | Transformer架构的核心组件 |

**Guidelines:**
- Extract **3-8 items** per note depending on content richness
- Keywords must be **reusable across notes** (domain-level, NOT note-specific titles)
  - Good: `LLM`, `Diffusion`, `ReinforcementLearning`, `ComputerVision`, `Transformer`
  - Bad: `AttentionIsAllYouNeed`, `GPT4TechnicalReport`
- Each item must be **independently understandable** without the source note
- Prioritize **actionable, non-obvious insights** over basic definitions
- If the note has user-written "笔记与想法" at the end, extract those insights as 元认知记忆

### Step 2d: Store Each Knowledge Item in Memory

Process each extracted item one at a time. Follow the **top-down navigation** — never load files you don't need.

#### Navigation Flow:

```
1. Read memory/memory-index.md
   → Determine which category folder to enter

2. Read memory/{category}/_local_index.md
   → Check if matching KEY_WORD.md exists

3a. If KEY_WORD.md exists:
    → Read it
    → Append new entry
    → Update _local_index.md (entry count + date)

3b. If KEY_WORD.md does NOT exist:
    → Create new KEY_WORD.md with the entry
    → Update _local_index.md (add new row)
```

#### Deduplication:

Before appending, check if the KEY_WORD.md already contains a similar entry from the same source. If so, **merge or update** instead of duplicating.

---

## Step 3: Process Chat Logs

After all `_new/` notes have been processed, scan `_chat/` for chat log files and process them.

### Step 3a: Scan Chat Directory

Use Glob to find all `.md` files in `_chat/`:

```
Glob: pattern = "*.md", path = "./IndexVault/_chat"
```

If no chat files are found, skip to Step 4 (Summary Report).

### Step 3b: Process Each Chat File

For each chat file, perform Steps 3c → 3d → 3e → 3f sequentially.

### Step 3c: Read Chat and Analyze for Persona Updates

Read the chat file content. To identify user messages, parse the chat structure:

- **User messages** start after a line matching `**🕐 HH:MM** | **User**`
- **Agent responses** start after a line matching `**🕐 HH:MM** | **Index**`
- Each Q&A pair is separated by `---`
- A user message is all text between the `| **User**` header line and the next `| **Index**` header line (excluding blank lines immediately after the header)

Scan the **user messages** for any requests or statements that imply changes to persona:

- **Communication style / tone** — e.g., "以后用更轻松的语气", "回答简短一些", "用英文回复我"
- **Personality / MBTI traits** — e.g., "你应该更像INFP", "表现得更外向一些"
- **Cognitive traits** — e.g., "多用直觉少分析", "给我更发散的思路"
- **Professional context** — e.g., "我现在转做NLP了", "我的专业改了"
- **Extra traits** — e.g., "加一个特质：喜欢用比喻", "说话带点幽默"

**If persona-related changes are detected:**

1. Read the current `./IndexVault/persona.md`
2. Apply the changes to the appropriate section(s):
   - MBTI type/description → update `## MBTI Personality` section
   - Cognitive traits → update `## Cognitive Traits` table
   - Profession → update `## Profession` section
   - Extra traits → update `## Extra Traits` section
3. Write the updated `persona.md`

**If no persona changes are detected**, skip to Step 3d.

### Step 3d: Archive Chat File to Deep (Safe Move)

**Archive FIRST, before extracting knowledge.** This matches the note workflow (Step 2b) and ensures the final filename is known before writing any `来源` wikilinks.

Move the chat file from `_chat/` to `deep/` using the **safe move** procedure:

```bash
FILENAME="{chat_filename}"
TARGET="./IndexVault/deep/$FILENAME"
if [ -f "$TARGET" ]; then
    BASENAME="${FILENAME%.md}"
    SUFFIX=$(od -An -tx1 -N4 /dev/urandom | tr -d ' \n')
    FILENAME="${BASENAME}_${SUFFIX}.md"
    TARGET="./IndexVault/deep/$FILENAME"
fi
mv "./IndexVault/_chat/{original_filename}" "$TARGET"
```

Record the **final archived filename** (with suffix if renamed) for use in Step 3e/3f.

### Step 3e: Extract New Knowledge from Chat

Analyze the **user messages** (already read in Step 3c) to determine if the user **provided new information** (not just asked questions). Look for:

- User explaining a concept, sharing facts, or describing a method
- User providing new data, benchmarks, or comparisons
- User sharing a workflow, tool recommendation, or lesson learned
- User correcting a previous response with factual information

**Key distinction**: If the user only asked questions (e.g., "LoRA是什么？", "怎么部署？") without providing new information, there is **nothing to extract** — skip to the next chat file.

If new information IS found, extract knowledge items using the **same format and rules as Step 2c**:

| Field | Description |
|-------|-------------|
| `keyword` | PascalCase English concept keyword |
| `summary` | 1-3 sentence self-contained summary (Chinese) |
| `category` | One of 4 knowledge types |
| `entry_title` | Short descriptive title (Chinese) |

The `来源` for chat-extracted knowledge must use the **final archived filename** from Step 3d: `[[{archived_filename}|Chat {date}]]`

### Step 3f: Store Knowledge Items in Memory

For each extracted knowledge item from Step 3e, follow the **exact same process as Step 2d**:

1. Read `memory/memory-index.md` → determine category
2. Read `memory/{category}/_local_index.md` → check if keyword exists
3. If KEY_WORD.md exists → append entry, update `_local_index.md`
4. If KEY_WORD.md does not exist → create it, update `_local_index.md`
5. Deduplicate: if same source already contributed an entry for this keyword, merge/update

---

## Step 4: Summary Report

After all notes and chat logs are processed, output:

```markdown
## 整理完成

**处理笔记数**: N
**处理聊天记录数**: C
**提取知识条目数**: M (笔记: X, 聊天: Y)

### 笔记处理详情
| 笔记 | 类型 | 提取条目 | 归档位置 |
|------|------|----------|----------|
| {note_id} | {type} | {count} | deep/{filename} |

### 聊天记录处理详情
| 聊天文件 | Persona更新 | 提取条目 | 归档位置 |
|----------|-------------|----------|----------|
| {chat_filename} | {是/否: 简述变更} | {count} | deep/{archived_filename} |

### Persona 变更 (如有)
| 变更项 | 原值 | 新值 |
|--------|------|------|
| {field} | {old_value} | {new_value} |

### 新增/更新的知识条目
| 关键词 | 类别 | 条目标题 | 来源 |
|--------|------|----------|------|
| {keyword} | {category} | {entry_title} | {source_id} |
```

If no chat logs were processed, omit the "聊天记录处理详情" and "Persona 变更" sections.

---

# File Formats

## memory-index.md

See `./skills/index-update/resources/memory-index.md` for the initial template. This file only contains category descriptions and links to each `_local_index.md`. It does NOT list individual keywords — that is the job of `_local_index.md`.

No updates needed to `memory-index.md` during normal operation.

## _local_index.md

Each category folder has one. Contains a table of all KEY_WORD.md files **with wikilinks** for navigation:

```markdown
| 关键词 | 描述 | 条目数 | 最后更新 |
|--------|------|--------|----------|
| [[LLM]] | 大语言模型相关定义、架构、关键参数 | 3 | 2026-04-05 |
| [[Transformer]] | Transformer架构与自注意力机制 | 2 | 2026-04-05 |
```

When updating:
- **Existing keyword**: update `条目数` and `最后更新`
- **New keyword**: add a new row with `条目数: 1`, keyword wrapped in `[[...]]` wikilink

## KEY_WORD.md

```markdown
---
keyword: {KeyWord}
category: {事实性记忆|程序性记忆|条件性记忆|元认知记忆}
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
entry_count: {N}
---

# {KeyWord}

---

### {Entry Title}
**概要**: {1-3 sentence summary}
**来源**: [[{note_id}|{note display title}]]
**添加时间**: {YYYY-MM-DD}

---

### {Entry Title 2}
...
```

**Rules:**
- `keyword` in frontmatter and filename must match (PascalCase English)
- `来源` uses Obsidian wikilink: `[[{note_id}|{display title}]]` — the note_id links to `deep/{note_id}.md`
- Entries are separated by `---`
- Each entry is self-contained and independently readable

---

# Obsidian Formatting Rules

Follow the same formatting rules as other skills:

1. **Frontmatter**: Valid YAML between `---` markers
2. **Tags**: Hyphens not spaces (`machine-learning`)
3. **Wikilinks**: `[[File_Name|Display Title]]` with display alias
4. **Missing data**: `--` (not `---`)
5. **Bilingual headers**: Not required for memory files (Chinese-primary is fine)

---

# Error Handling

- If `_new/` does not exist or is empty AND `_chat/` does not exist or is empty → report "暂无笔记或聊天记录" and exit
- If `_new/` is empty but `_chat/` has files → skip to Step 3 (chat processing)
- If a note has no extractable knowledge (empty/minimal) → still archive to `deep/`, note in summary as "无可提取知识"
- If moving file fails → report error, continue with next note/chat
- If a file already exists in `deep/` → add random suffix (safe move), never overwrite
- If `persona.md` does not exist when chat processing needs it → skip persona update, report warning
- If memory index files are malformed → attempt to repair, or recreate from template

---

# Important Notes

- **Layered access**: ALWAYS navigate through indexes. Never glob/read all KEY_WORD.md files at once
- **Atomic updates**: Finish one note completely (archive → extract → store) before starting the next. Same for chat files
- **Processing order**: Always process `_new/` notes FIRST, then `_chat/` files
- **Safe move**: When archiving ANY file to `deep/`, always check for filename collision and add random suffix if needed. Never overwrite existing `deep/` files
- **Idempotency**: If a note has already been archived (exists in `deep/`), skip it
- **Keyword granularity**: Keywords should be at the **concept/field level** (e.g., `LLM`, `Diffusion`), not at the paper/article level. A keyword should be expected to accumulate multiple entries over time
- **Chat knowledge extraction**: Only extract knowledge when the user **provided** information. Pure Q&A (user asks, agent answers) does NOT contribute new knowledge
- **Persona updates are conservative**: Only modify `persona.md` when the user **explicitly** requested a change to personality, style, or traits. Do not infer changes from casual conversation
- **Today's date**: Use the current date (YYYY-MM-DD) for all `添加时间` and `updated` fields
