# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

茵蒂克丝.skill（LLM Wiki）is a knowledge management system built as Claude Code skills. It captures arbitrary input (text, URLs, files, folders), auto-classifies it into 6 types, and produces structured Obsidian notes with extracted images. It also provides persona-driven chat with memory-augmented retrieval.

## Skills

Four complementary skills in `skills/`:

- **index-init** (`/index-init`): First-run setup. Creates the Obsidian vault directory structure, copies templates from `skills/index-init/resources/` to the vault, and generates `persona.md` via interactive MBTI questionnaire.
- **index-note** (`/index-note INPUT`): Core skill. Classifies input → downloads content if needed → extracts images → fills type-specific template → writes note to `_new/`.
- **index-chat** (`/index-chat INPUT`): Chat skill. Loads persona from `persona.md` → extracts keywords from user input → retrieves relevant knowledge from `memory/` via layered navigation → responds in persona style with references → saves conversation to `_chat/`.
- **index-update** (`/index-update`): Knowledge organizer. Scans `_new/` for notes marked "已读" → extracts knowledge items → classifies into 4-type hierarchical memory system (`memory/`) → archives note to `deep/`. Also processes `_chat/` logs: applies persona updates to `persona.md`, extracts user-provided knowledge, and archives chat files to `deep/`. The read marker is a literal checkbox at the bottom of every note: `- [x] <big><big>已读</big></big>` triggers archiving; `- [ ] <big><big>已读</big></big>` is skipped.

Each skill is defined by a `SKILL.md` file with frontmatter:
```yaml
---
name: index-note
description: ...
allowed-tools: Read, Write, Bash, WebFetch, Glob, Grep, WebSearch
---
```

## Key Paths

All paths are relative to the project root:

```
IndexVault/              Obsidian vault root
IndexVault/_new/         Generated notes output (YYYY-MM-DD_TYPE_NNN.md)
IndexVault/deep/         Archive for read notes (moved from _new/ after reading)
IndexVault/memory/       Hierarchical knowledge base (see Memory System below)
IndexVault/_template/    6 note templates (idea/project/book/paper/webinfo/webnews)
IndexVault/_images/      Extracted images, organized per-note ({note_id}/{note_id}_{nn}.ext)
IndexVault/_downloads/   Downloaded source material
IndexVault/_chat/        Chat logs (YYYY-MM-DD_Chat.md, archived to deep/ by index-update)
IndexVault/persona.md    Agent personality config (created by index-init, updated by index-update from chat logs)
```

## Memory System

Hierarchical knowledge base in `IndexVault/memory/` with layered index navigation (never load all knowledge at once):

```
memory/
├── memory-index.md              # Level 0: routes to knowledge category
├── 事实性记忆/                    # "是什么" — definitions, facts, formulas
│   ├── _local_index.md      # Level 1: routes to keyword file
│   └── {KEY_WORD}.md            # Level 2: actual knowledge entries
├── 程序性记忆/                    # "怎么做" — methods, workflows, code patterns
│   ├── _local_index.md
│   └── {KEY_WORD}.md
├── 条件性记忆/                    # "何时/为何用" — trade-offs, selection criteria
│   ├── _local_index.md
│   └── {KEY_WORD}.md
└── 元认知记忆/                    # "怎么学/怎么错" — learning strategies, reflections
    ├── _local_index.md
    └── {KEY_WORD}.md
```

KEY_WORD files use PascalCase English (e.g., `LLM.md`, `Transformer.md`). Each contains multiple knowledge entries with summaries and wikilinks back to source notes in `deep/`.

**Invariants when working with memory:**
- **Layered access only**: Always navigate `memory-index.md` → `_local_index.md` → `KEY_WORD.md`. Never glob/read all `KEY_WORD.md` files at once.
- **Concept-level keywords**: Keywords must be reusable across notes (`LLM`, `Diffusion`, `ReinforcementLearning`), not note-specific titles (`AttentionIsAllYouNeed`, `GPT4TechnicalReport`). A keyword is expected to accumulate multiple entries over time.
- **Archive before memory write** (index-update): Move the note to `deep/` *first*, then write memory entries. This way every `来源` wikilink points to the actual archived location (and uses the post-collision filename if a suffix was added).

## Running Python Scripts

Python is accessed via `uv` (no system Python installed):

```bash
# Classification
uv run python ./skills/index-note/scripts/classify_input.py --input "INPUT_STRING"

# ID generation (scans both _new/ and deep/ to avoid collisions after archiving)
uv run python ./skills/index-note/scripts/generate_id.py --type TYPE --vault-new-dir ./IndexVault/_new/ --vault-deep-dir ./IndexVault/deep/

# Image extraction to temp dir (needs PyMuPDF)
# Progress goes to stderr; stdout is compact JSON: {"total": N, "images": [{"filename": "...", "width": N, "height": N}, ...]}
uv run --with pymupdf --with requests python ./skills/index-note/scripts/extract_images.py \
  --type paper --input "2505.00949" --note-id "2026-04-05_paper_001" \
  --output-dir ./IndexVault/_images/_tmp_2026-04-05_paper_001/

# Finalize images (keep only those referenced in note, move to _images/{note_id}/)
# stdout: {"kept": N, "removed": N}
uv run python ./skills/index-note/scripts/finalize_images.py \
  --note-path ./IndexVault/_new/2026-04-05_paper_001.md \
  --temp-dir ./IndexVault/_images/_tmp_2026-04-05_paper_001/ \
  --images-dir ./IndexVault/_images/ --note-id 2026-04-05_paper_001
```

### Image Extraction Details

`extract_images.py` outputs only compact JSON to stdout (progress logs go to stderr). For PDF extraction it uses Pixmap-based processing with:
- **SMask compositing**: Applies soft masks so masked images are not extracted as all-black
- **CMYK → RGB conversion**: Converts CMYK color space before saving
- **Cross-page xref dedup**: Same image on multiple pages is extracted only once
- **Blank image filtering**: Samples pixels to detect and skip all-black/blank images
- **Lazy PDF download**: For arXiv papers, only downloads the PDF when Priority 1+2 yield fewer than 3 images

## Input Classification (6 Types)

`classify_input.py` uses a two-phase approach:
- **Phase 1** (structural): regex/path detection — bare arXiv ID → paper, GitHub URL → project, local dir → project, local file → book/paper, news domain → webnews, other URL → webinfo, plain text → idea
- **Phase 2** (content-based): if ambiguous (.pdf could be book or paper, general URL could be reclassified), analyze content to reclassify

## Obsidian Formatting Rules

These rules apply to ALL generated notes:

- Frontmatter: valid YAML between `---` markers
- Tags: hyphens not spaces (`machine-learning` not `machine learning`)
- Wikilinks: `[[File_Name|Display Title]]` with display alias
- Images: `![[filename.png|600]]` (Obsidian wikilink, not markdown)
- Missing data: `--` (not `---` which renders as horizontal rule)
- Formulas: inline `$...$`, block `$$...$$`
- Bilingual headers: `## English (中文)`

## Template Design Principles

Templates are based on cognitive science research:

- **TL;DR first**: Every note starts with `> [!abstract] TL;DR` callout
- **Self-explanation**: Paper notes have "In My Own Words" section before technical details
- **Typed connections**: Classify relationships as supports/contradicts/extends, not just list links
- **Retrieval cues**: End with scenario triggers ("when would I come back to this?")
- **So What?**: Every note answers "how does this change what I do?"

## Safe Move (Archiving to deep/)

When moving files from `_new/` or `_chat/` to `deep/`, always check for filename collisions. If a file with the same name already exists in `deep/`, append a random hex suffix before the `.md` extension:

```bash
FILENAME="{original}.md"
TARGET="./IndexVault/deep/$FILENAME"
if [ -f "$TARGET" ]; then
    BASENAME="${FILENAME%.md}"
    SUFFIX=$(od -An -tx1 -N4 /dev/urandom | tr -d ' \n')
    FILENAME="${BASENAME}_${SUFFIX}.md"
fi
```

## Template Source of Truth

Templates exist in two places — `skills/index-init/resources/` is the canonical source; `IndexVault/_template/` is the deployed copy. When modifying templates, update both locations (or update resources/ and re-run index-init).

## Web UI

Flask-based web interface in `webUI/` with sidebar navigation and six views:

```
webUI/
├── app.py                 # Flask app (routes, MBTI logic, background tasks, chat/update APIs)
├── static/
│   ├── css/style.css      # Custom styles (sidebar, cards, chat bubbles, callouts, Obsidian rendering)
│   └── js/main.js         # SPA navigation, Obsidian markdown renderer, chat, polling
└── templates/
    ├── base.html          # Shared layout (Bootstrap 5, marked.js, KaTeX CDN)
    ├── init.html          # 7-step init wizard (profession → MBTI × 4 → extra traits → confirm)
    ├── app.html           # Main app (sidebar + 6 views: new/read/archived/input/chat/update)
    └── note_detail.html   # Single note viewer with mark-read toggle + personal notes input
```

### Running the Web UI

```bash
uv run --with flask --with python-frontmatter python webUI/app.py
# Runs on http://localhost:3008 by default (override with PORT=8080)
```

### Key Routes

- `GET /` — Redirects to `/init` (no persona) or `/app` (vault exists)
- `GET /init` — Init wizard (MBTI persona generation, deterministic Python)
- `GET /app` — Main interface with sidebar (6 views: new/read/archived/input/chat/update)
- `GET /note/<source>/<filename>` — Note detail (source = `new` or `archived`)
- `POST /api/init` — Execute vault initialization (accepts `profession`, `mbti`, optional `extra_traits`)
- `GET /api/notes?status=new|read|archived` — List notes by status
- `GET /api/note/<source>/<filename>` — Note detail as JSON
- `POST /api/note/toggle-read` — Toggle the read marker in a note (accepts optional `personal_notes` to write after "（可选）笔记与想法")
- `POST /api/process` — Start note processing (background pipeline via Claude CLI)
- `POST /api/chat` — Send chat message (spawns `claude -p "/index-chat INPUT"`)
- `POST /api/update` — Trigger archive (spawns `claude -p "/index-update"`)
- `GET /api/task/<id>` — Poll background task status
- `GET /api/stats` — Note counts per category (for sidebar badges)

### Note Classification (Three States)

Notes are classified into three categories based on location and read marker:
- **新加入 (New)**: In `_new/`, read marker unchecked (`- [ ] <big><big>已读</big></big>`)
- **已读 (Read)**: In `_new/`, read marker checked (`- [x] <big><big>已读</big></big>`)
- **已归档 (Archived)**: In `deep/` (moved by `/index-update`)

### Obsidian Markdown Rendering

`main.js` implements a custom pipeline: extract math → convert `![[img]]` / `[[wikilinks]]` → convert callouts (with inner markdown via `marked.parse`) → run marked.js → restore math via KaTeX.

### MBTI Logic

`app.py` contains deterministic MBTI persona generation (16-type lookup table + 5 cognitive trait derivation rules), matching the logic in `skills/index-init/SKILL.md`. No AI needed for init.

### Background Task State

The `tasks` dict in `app.py` is in-memory and lost on Flask restart. Polling `/api/task/<id>` will 404 after a server restart even if the underlying `claude -p` process completed.
