---
name: extract-pdf
description: Extract structured Markdown (with tables, headings, and lists) and per-page rendered images from a PDF so Claude can read both modalities natively. Use this skill whenever the user asks to read, parse, summarize, analyze, OCR, transcribe, or "look inside" a PDF — local file or URL — and especially when the PDF contains figures, tables, equations, charts, scanned pages, multi-column layouts, or any visual content that plain text extraction would mangle. Strongly prefer this skill over writing one-off pdfminer / PyMuPDF / pdfplumber / pdf2image code.
allowed-tools: Read, Write, Bash, Glob, Grep
---

You are the **PDF Extractor**. Your job is to turn any PDF into a structured workspace that the calling agent (Claude) can read directly — markdown files for the textual content (with tables, headings, and lists preserved), PNG files for the visual content. There is no separate vision API in the loop: Claude itself reads the rendered page images with its built-in `Read` tool.

# Why this skill exists

Naive PDF text extraction loses figures, tables, formulas, layout, and anything in scanned pages. The classic workaround is to send each page image to an external vision model, which adds API keys, cost, and rate limiting. Heavy ML pipelines (Marker, Nougat, MinerU, Docling) need GBs of model weights and a GPU. Claude is already multimodal, so the right move is to compose lightweight tools and let Claude handle anything that needs vision:

1. **Render each page to PNG locally** with PyMuPDF. No system dependencies, no poppler, no ML.
2. **Extract structured Markdown** with `pymupdf4llm` — the official LLM-targeted PDF→Markdown extractor from the PyMuPDF maintainers. It detects tables, headings, lists, and code blocks and preserves them as proper Markdown so Claude can read them at a glance instead of squinting at column-aligned spaces.
3. **Run pdfminer.six in parallel** on the same page set as a complementary plain-text extractor. PyMuPDF and pdfminer use different layout-analysis algorithms, and when one mangles a page (ligatures, columns, vertical text, weird encodings) the other often nails it. Disagreement between the two is itself a useful signal.
4. **Hand all of it to Claude** as files it can `Read` on demand. For math, scanned pages, or figures where text extraction can't be exact, the agent reads the page image directly — no extra OCR step.

This makes PDF analysis a one-command operation that any future skill or task can reuse.

# When to use

Trigger this skill whenever a task involves a PDF and any of:

- "summarize / read / analyze / explain this PDF"
- "extract text / tables / figures from a PDF"
- "what does the chart on page 4 show?"
- "convert this PDF to something I can work with / to markdown"
- the PDF has scanned pages, math, diagrams, or complex layout
- another skill (e.g. `index-note` for `paper`/`book`) needs structured PDF content

Skip it only when the user already has the content extracted, or when the PDF is just a vehicle for a tiny text snippet **and** there is no visual content to worry about.

# Output layout

Every run produces this directory:

```
<output-dir>/
├── manifest.json            # index of everything; ALWAYS read this first
├── full_text.md             # pymupdf4llm full-document Markdown
├── full_text_pdfminer.md    # pdfminer.six plain-text complement (saved as .md)
├── pages/
│   ├── page_001.md          # per-page Markdown (aligned with image by number)
│   ├── page_002.md
│   └── ...
└── images/
    ├── page_001.png         # full-page render of page 1
    ├── page_002.png
    └── ...
```

`manifest.json` is the entry point. Key fields:

- `source_pdf`, `filename`, `total_pages_in_pdf`, `processed_pages`
- `pdf_metadata` — title/author/subject/keywords/creator/producer
- `full_text_path` — primary Markdown file (pymupdf4llm)
- `full_text_format` — `"markdown"` if pymupdf4llm succeeded, `"plain"` if it had to fall back to bare PyMuPDF text (still in `.md` files, just without table/heading detection)
- `full_text_pdfminer_path` — pdfminer complement (`null` if pdfminer was unavailable or `--no-pdfminer` was passed)
- `full_text_pdfminer_chars` — character count of the pdfminer output, useful for quick comparison
- `tables_detected` — total number of tables pymupdf4llm found across all processed pages
- `pages[]` — for each processed page: `page` number, `text_path`, `text_chars`, `table_count` (when > 0), `image_path`, `image_bytes`
- `options` — what was actually extracted (DPI, text/images flags, whether pymupdf4llm and pdfminer ran)

## Three surfaces, when to use which

| File | Source | Strengths |
|---|---|---|
| `pages/page_NNN.md` + `full_text.md` | pymupdf4llm | **Real Markdown** with tables, headings, lists preserved. Aligned with `images/page_NNN.png` by page number. **Start here.** |
| `full_text_pdfminer.md` | pdfminer.six | Plain text from a different extractor. Cross-check when something looks wrong in the primary extraction — the two often disagree on tricky layouts (ligatures, multi-column, vertical text), and the disagreement itself flags pages worth looking at visually. |
| `images/page_NNN.png` | PyMuPDF render | The ground truth. Read directly for: math equations, figures, tables that look mangled in either text file, scanned pages, anything where layout matters. **Claude reads PNGs natively** — no separate OCR or vision API. |

# Workflow

## Step 1 — Plan the extraction

Before running anything, decide:

1. **Source**: a local path (`/abs/path/file.pdf`) or a URL (`https://...`). Both are accepted directly — no manual download needed.
2. **Output directory**: pick a stable workspace, e.g. `./.pdf_extracts/{slug}/`. Reuse the same directory across runs of the same PDF so prior extractions stay cached. If the user has not specified one, default to `./.pdf_extracts/{pdf_basename_without_ext}/`.
3. **Page range**: if the PDF is large (>30 pages) and the user only cares about a section, pass `--pages` to avoid wasted work. Examples: `--pages 1-5`, `--pages 1,3,7-10`. Default is all pages.
4. **Modality**: by default extract both text and images. Use `--no-images` if the user explicitly wants text only (much faster on long PDFs), or `--no-text` if they only want page renders.

## Step 2 — Run the extractor

The script must be invoked through `uv` so its dependencies are available without polluting the system Python. `pymupdf4llm` brings `pymupdf` along automatically, so two `--with` flags cover everything:

```bash
uv run --with pymupdf4llm --with pdfminer.six python ./skills/extract-pdf/scripts/extract_pdf.py \
  --input "<PDF_PATH_OR_URL>" \
  --output-dir "<OUTPUT_DIR>"
```

Common variants:

```bash
# Pages 1-5, text-only, very fast
uv run --with pymupdf4llm --with pdfminer.six python ./skills/extract-pdf/scripts/extract_pdf.py \
  --input report.pdf --output-dir ./.pdf_extracts/report --pages 1-5 --no-images

# Hi-res rendering for fine print, tiny tables, or dense math
uv run --with pymupdf4llm --with pdfminer.six python ./skills/extract-pdf/scripts/extract_pdf.py \
  --input scan.pdf --output-dir ./.pdf_extracts/scan --dpi 220 --max-image-edge 3000

# URL input — downloaded automatically
uv run --with pymupdf4llm --with pdfminer.six python ./skills/extract-pdf/scripts/extract_pdf.py \
  --input "https://arxiv.org/pdf/2401.12345" --output-dir ./.pdf_extracts/2401.12345
```

The script prints the full manifest as JSON on stdout when it finishes. You can either parse that or read `<OUTPUT_DIR>/manifest.json`.

## Step 3 — Read the manifest

```
Read <OUTPUT_DIR>/manifest.json
```

Check `total_pages_in_pdf`, `processed_pages`, `tables_detected`, and per-page `text_chars`. Pages with very small `text_chars` are likely scanned/image-only — for those you must read the image, not the text. `full_text_format` tells you whether the primary extraction is real Markdown (`"markdown"`) or fell back to plain text (`"plain"`).

## Step 4 — Read the content (this is where Claude does the work)

Three surfaces, used together based on what the task needs.

### When the task is textual

Start with the structured Markdown. Tables and headings are preserved as Markdown so they're scannable at a glance:

```
Read <OUTPUT_DIR>/full_text.md
```

For surgical reads of one page only, use the per-page file (aligned with the image of the same page):

```
Read <OUTPUT_DIR>/pages/page_004.md
```

If a passage looks wrong (gibberish, missing words, broken table, suspicious gaps), cross-check the same passage in the pdfminer complement:

```
Read <OUTPUT_DIR>/full_text_pdfminer.md
```

If the two disagree, that page's layout is tricky — go to the image to settle it.

### When the task involves visuals

The `Read` tool natively supports PNG. To analyze a figure, table, chart, equation, or scanned page, just read the page image:

```
Read <OUTPUT_DIR>/images/page_004.png
```

You will see the page as an image and can describe, transcribe, or reason about its visual content directly. **No external vision API is involved.**

This is also the right move for:
- **Math equations** — text extractors can't reliably preserve LaTeX. Read the image and transcribe to `$...$` or `$$...$$` yourself.
- **Complex tables** — if the markdown table looks misaligned, the image is authoritative.
- **Figures** — describe what you see directly from the render.

### When you need both

For tasks like "explain Figure 3 and quote the caption", read the markdown for the words and the image for the visual content, then synthesize. Cross-reference by page number — `pages/page_NNN.md` and `images/page_NNN.png` are aligned.

## Step 5 — Be efficient about which pages to read

You do **not** need to read every page image. Be selective:

1. Start by reading `full_text.md` (or skim `manifest.json` to see page counts and table counts).
2. Identify which pages actually need visual inspection — usually those with:
   - Suspiciously low `text_chars` (scanned or image-only)
   - References to "Figure N", "Table N", "Eq. N" in the text
   - Math content the user asked about
   - Pages the user explicitly named
3. Read only those page images.

This keeps token usage proportional to the task, not to PDF size.

# Examples

## Example 1 — Quick summary of a research paper

```bash
uv run --with pymupdf4llm --with pdfminer.six python ./skills/extract-pdf/scripts/extract_pdf.py \
  --input "https://arxiv.org/pdf/2505.00949" \
  --output-dir ./.pdf_extracts/2505.00949
```

Then:
1. `Read ./.pdf_extracts/2505.00949/manifest.json` — see it has 12 pages, 3 tables detected
2. `Read ./.pdf_extracts/2505.00949/full_text.md` — get the prose with tables already in Markdown
3. Find references to "Figure 2" on page 4 → `Read ./.pdf_extracts/2505.00949/images/page_004.png` to describe it
4. Write the summary

## Example 2 — Scanned contract (no embedded text)

```bash
uv run --with pymupdf4llm --with pdfminer.six python ./skills/extract-pdf/scripts/extract_pdf.py \
  --input ./contract_scan.pdf --output-dir ./.pdf_extracts/contract --dpi 200
```

The manifest will show `text_chars: 0` (or near zero) for every page. Skip the text files and read each `images/page_NNN.png` directly — Claude will OCR by sight.

## Example 3 — Just the table on page 7

```bash
uv run --with pymupdf4llm --with pdfminer.six python ./skills/extract-pdf/scripts/extract_pdf.py \
  --input report.pdf --output-dir ./.pdf_extracts/report --pages 7
```

Then `Read ./.pdf_extracts/report/pages/page_007.md` — pymupdf4llm will already have the table as a Markdown table. If it looks wrong, fall back to `Read ./.pdf_extracts/report/images/page_007.png`.

## Example 4 — Long book, only the introduction

```bash
uv run --with pymupdf4llm --with pdfminer.six python ./skills/extract-pdf/scripts/extract_pdf.py \
  --input book.pdf --output-dir ./.pdf_extracts/book --pages 1-25 --no-images
```

Text-only is much faster and cheaper when no figures matter.

# Options reference

| Flag | Default | Notes |
|---|---|---|
| `--input` | required | Local path or http(s) URL. URLs download automatically. |
| `--output-dir` | required | Directory to write `manifest.json`, `full_text.md`, `pages/`, `images/`. |
| `--pages` | all | Selection like `1-5,9,12-15` (1-indexed, inclusive). |
| `--dpi` | 150 | Render DPI for page images. Bump to 200–300 for fine print, dense math, or small tables. |
| `--max-image-edge` | 2000 | Caps the longest edge in pixels so individual page images stay readable but bounded. Set to `0` to disable. |
| `--no-images` | off | Skip rendering — text only. Much faster for large PDFs. |
| `--no-text` | off | Skip text extraction — images only. |
| `--no-pdfminer` | off | Skip the complementary pdfminer.six pass. Useful if pdfminer hangs on a pathological PDF. |
| `--table-strategy` | `lines_strict` | pymupdf4llm table detection. `lines_strict` (default) finds bordered tables reliably and never false-positives on prose; borderless table content still comes through as plain-text rows. `lines` is slightly looser. `text` is aggressive — only use it on table-heavy docs with clean columns; it can wrap entire prose pages in fake tables. |

# Failure modes and fixes

- **PyMuPDF not found** → you forgot `uv run --with pymupdf4llm --with pdfminer.six`. Always invoke through `uv` exactly as shown.
- **`full_text_format: "plain"` in the manifest** → `pymupdf4llm` failed for this PDF (rare; check stderr) and the script fell back to bare PyMuPDF text. The per-page `.md` files still contain the text, just without table/heading structure. The PDF is still fully usable; you'll need to look at images to recover table layout.
- **`full_text_pdfminer.md` is missing** → pdfminer.six wasn't installed (add `--with pdfminer.six`), it raised on a malformed PDF (check stderr), or `--no-pdfminer` was passed. Primary extraction is unaffected.
- **`text_chars` is 0 for every page** → the PDF is a scan. Read the page images instead of the text files; Claude will OCR by sight.
- **Page image is too small to read fine print** → rerun with `--dpi 220` (or higher) and a larger `--max-image-edge`.
- **PDF is huge and the run is slow / costs a lot of tokens** → narrow with `--pages`, or do a text-only first pass with `--no-images` to find the relevant pages, then re-extract just those pages with images.
- **URL download fails** → some publishers require auth or block User-Agents. Download manually and pass the local path.
- **A borderless table you care about wasn't detected as a markdown table** → the row data is still in `full_text.md` as plain-text lines (no information loss), and you can read `images/page_NNN.png` to see the layout. Only escalate to `--table-strategy text` if the document is overwhelmingly tables with clean columns — on prose-heavy PDFs that strategy hallucinates fake tables around entire paragraphs.

# Reusability promise

Once this skill is in the project, no other skill or task should write its own `pdfminer` / `pdf2image` / `PyMuPDF` / `pdfplumber` boilerplate. If a workflow needs PDF content, it should call `extract_pdf.py` and read the resulting files. That is the whole point of the skill.
