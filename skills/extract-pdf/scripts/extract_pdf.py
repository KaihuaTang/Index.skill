#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract-pdf skill: PDF content extractor for Claude.

Produces a structured workspace that the calling agent (Claude itself) can read
directly. There is no separate vision API in the loop — Claude is multimodal
and reads the rendered page PNGs natively.

Three extraction surfaces are produced because each catches things the others
miss:

  1. PyMuPDF4LLM     →  Markdown (tables, headings, lists, lists, code blocks)
  2. pdfminer.six    →  Plain-text complement for tricky layouts and ligatures
  3. PyMuPDF render  →  Per-page PNG so the agent can OCR-by-sight, transcribe
                        math/figures, or settle disputes between the two text
                        extractors.

Output structure (under --output-dir):

    manifest.json            Index + metadata. ALWAYS read this first.
    full_text.md             pymupdf4llm full-document markdown
    full_text_pdfminer.md    pdfminer.six full-document plain text (in .md)
    pages/page_NNN.md        Per-page markdown (aligned with images by number)
    images/page_NNN.png      Per-page rendered image

Usage:
    uv run --with pymupdf4llm --with pdfminer.six python extract_pdf.py \\
        --input path/or/url/to/file.pdf \\
        --output-dir ./out

    # Common options:
    --pages 1-5,9          Only process selected pages (1-indexed, inclusive)
    --dpi 150              Render DPI for page images (default 150)
    --no-images            Skip image rendering (text-only, much faster)
    --no-text              Skip text extraction (images only)
    --no-pdfminer          Skip the pdfminer complementary pass
    --max-image-edge 2000  Cap longest edge of rendered page in pixels
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# ── Dependencies ───────────────────────────────────────────────────────
# PyMuPDF (fitz) is required: it does page rendering and acts as the fallback
# text extractor when pymupdf4llm is unavailable. pymupdf4llm and pdfminer.six
# are optional; the script degrades gracefully without them.

try:
    import fitz  # PyMuPDF
except ImportError:
    print(
        "ERROR: PyMuPDF (fitz) is required. Run with:\n"
        "  uv run --with pymupdf4llm --with pdfminer.six python extract_pdf.py ...",
        file=sys.stderr,
    )
    sys.exit(2)

try:
    import pymupdf4llm  # PDF → Markdown with table/heading detection
    HAS_PYMUPDF4LLM = True
except ImportError:
    HAS_PYMUPDF4LLM = False

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    HAS_PDFMINER = True
except ImportError:
    HAS_PDFMINER = False


# ── Input acquisition ──────────────────────────────────────────────────

def resolve_input(input_str: str, work_dir: str) -> str:
    """Return a local PDF path. Downloads if input is a URL."""
    if os.path.isfile(input_str):
        return input_str

    if input_str.startswith(("http://", "https://")):
        local_name = os.path.basename(input_str.split("?")[0]) or "downloaded.pdf"
        if not local_name.lower().endswith(".pdf"):
            local_name += ".pdf"
        local_path = os.path.join(work_dir, local_name)
        logger.info("Downloading %s → %s", input_str, local_path)
        try:
            req = urllib.request.Request(
                input_str,
                headers={"User-Agent": "Mozilla/5.0 (extract-pdf-skill)"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(local_path, "wb") as f:
                    f.write(resp.read())
            return local_path
        except urllib.error.HTTPError as e:
            raise SystemExit(f"HTTP {e.code} downloading {input_str}: {e.reason}")
        except Exception as e:
            raise SystemExit(f"Failed to download {input_str}: {e}")

    raise SystemExit(f"Input not found and not a URL: {input_str}")


# ── Page selection ─────────────────────────────────────────────────────

def parse_page_spec(spec: str, total: int) -> list[int]:
    """Parse '1-5,9,12-15' (1-indexed inclusive) → sorted 0-indexed list."""
    if not spec:
        return list(range(total))

    selected: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            start = max(1, int(a))
            end = min(total, int(b))
            for p in range(start, end + 1):
                selected.add(p - 1)
        else:
            p = int(chunk)
            if 1 <= p <= total:
                selected.add(p - 1)
    return sorted(selected)


# ── Text extraction ────────────────────────────────────────────────────

def _normalize_whitespace(text: str) -> str:
    """Clean up whitespace without destroying paragraph structure."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_markdown_chunks(doc, page_indices: list[int], table_strategy: str) -> tuple[list[dict], str]:
    """
    Run pymupdf4llm in one batch over the selected pages.

    Returns (chunks, format) where format is "markdown" on success or "plain"
    if we had to fall back to bare fitz text. Each chunk is a dict with at
    least a "text" key and a "page" number.

    `table_strategy` controls table detection. We default to "lines_strict"
    (pymupdf4llm's own default) because the "text" strategy is far too
    aggressive on prose-heavy PDFs — it detects whole paragraphs as fake
    tables and wraps entire pages in pipe syntax, destroying readability.
    "lines_strict" finds bordered tables reliably; for borderless tables,
    the row data still comes through as plain-text lines in the markdown
    (no information loss) and the agent can fall back to the page image to
    recover the table layout visually. Power users who know their PDFs
    have only well-formed borderless tables can pass --table-strategy text.
    """
    if HAS_PYMUPDF4LLM:
        try:
            raw = pymupdf4llm.to_markdown(
                doc,
                pages=page_indices,
                page_chunks=True,
                write_images=False,
                embed_images=False,
                table_strategy=table_strategy,
                show_progress=False,
            )
            # pymupdf4llm returns a list of dicts; normalize to a uniform shape.
            chunks = []
            for i, item in enumerate(raw):
                if isinstance(item, dict):
                    text = (item.get("text") or "").strip()
                    tables = item.get("tables") or []
                    chunks.append({
                        "page": page_indices[i] + 1,
                        "text": text,
                        "table_count": len(tables),
                    })
                else:
                    chunks.append({
                        "page": page_indices[i] + 1,
                        "text": str(item).strip(),
                        "table_count": 0,
                    })
            return chunks, "markdown"
        except Exception as e:
            logger.warning("pymupdf4llm failed (%s); falling back to plain text", e)

    # Fallback: bare fitz per-page text. No table detection, no markdown
    # structure, but never loses content.
    chunks = []
    for idx in page_indices:
        page = doc[idx]
        text = _normalize_whitespace(page.get_text("text") or "")
        chunks.append({"page": idx + 1, "text": text, "table_count": 0})
    return chunks, "plain"


def extract_full_text_pdfminer(pdf_path: str, page_indices: list[int]) -> str | None:
    """Run pdfminer.six on the same page set. Returns text or None on failure."""
    if not HAS_PDFMINER:
        return None
    try:
        text = pdfminer_extract_text(pdf_path, page_numbers=list(page_indices)) or ""
        return _normalize_whitespace(text)
    except Exception as e:
        logger.warning("pdfminer extraction failed: %s", e)
        return None


# ── Image rendering ────────────────────────────────────────────────────

def render_page_image(page, dpi: int, max_edge: int | None) -> bytes:
    """Render a page to PNG bytes, optionally clamping the longest edge."""
    zoom = dpi / 72.0  # PyMuPDF native is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)

    if max_edge and max(pix.width, pix.height) > max_edge:
        scale = max_edge / max(pix.width, pix.height)
        matrix = fitz.Matrix(zoom * scale, zoom * scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

    return pix.tobytes("png")


# ── Main processing ────────────────────────────────────────────────────

def process_pdf(
    doc,
    pdf_path: str,
    output_dir: str,
    page_indices: list[int],
    dpi: int,
    do_text: bool,
    do_images: bool,
    max_edge: int | None,
    do_pdfminer: bool,
    table_strategy: str = "lines_strict",
) -> dict:
    """
    Drive the full extraction over an already-open fitz doc and return the
    manifest. The doc is opened ONCE by the caller (efficiency: avoids the
    double-open this script used to do).
    """
    os.makedirs(output_dir, exist_ok=True)
    pages_dir = os.path.join(output_dir, "pages")
    images_dir = os.path.join(output_dir, "images")
    if do_text:
        os.makedirs(pages_dir, exist_ok=True)
    if do_images:
        os.makedirs(images_dir, exist_ok=True)

    total_pages = len(doc)

    # 1. Markdown extraction (one batched call over the page set).
    md_chunks: list[dict] = []
    md_format = None
    if do_text:
        md_chunks, md_format = extract_markdown_chunks(doc, page_indices, table_strategy)

    # 2. Per-page output: markdown file + image render. Both come from the
    #    same already-open doc, in one loop, so we never re-walk the PDF.
    manifest_pages = []
    full_md_parts: list[str] = []
    md_by_page = {c["page"]: c for c in md_chunks}

    for idx in page_indices:
        page_num = idx + 1
        page_entry: dict = {"page": page_num}

        if do_text:
            chunk = md_by_page.get(page_num, {"text": "", "table_count": 0})
            md_text = chunk["text"]
            page_md_name = f"page_{page_num:03d}.md"
            with open(os.path.join(pages_dir, page_md_name), "w", encoding="utf-8") as f:
                f.write(md_text + ("\n" if md_text and not md_text.endswith("\n") else ""))
            page_entry["text_path"] = f"pages/{page_md_name}"
            page_entry["text_chars"] = len(md_text)
            if chunk.get("table_count"):
                page_entry["table_count"] = chunk["table_count"]
            full_md_parts.append(f"\n\n## Page {page_num}\n\n{md_text}")

        if do_images:
            page = doc[idx]
            png_bytes = render_page_image(page, dpi=dpi, max_edge=max_edge)
            img_name = f"page_{page_num:03d}.png"
            with open(os.path.join(images_dir, img_name), "wb") as f:
                f.write(png_bytes)
            page_entry["image_path"] = f"images/{img_name}"
            page_entry["image_bytes"] = len(png_bytes)

        manifest_pages.append(page_entry)

    # 3. Full-document markdown.
    full_md_rel = None
    total_tables = sum(p.get("table_count", 0) for p in manifest_pages)
    if do_text and full_md_parts:
        full_md_rel = "full_text.md"
        header = (
            f"# {os.path.basename(pdf_path)}\n\n"
            f"_Extracted by pymupdf4llm ({md_format}). "
            f"{len(manifest_pages)} pages, {total_tables} tables detected._\n"
        )
        with open(os.path.join(output_dir, full_md_rel), "w", encoding="utf-8") as f:
            f.write(header + "".join(full_md_parts).rstrip() + "\n")

    # 4. Complementary pdfminer pass — runs on the path, not the open doc, so
    #    no contention. Saved with .md extension because plain text is valid
    #    markdown and the agent treats this as a fallback file alongside the
    #    structured one.
    full_pdfminer_rel = None
    pdfminer_chars = 0
    if do_text and do_pdfminer:
        if not HAS_PDFMINER:
            logger.warning(
                "pdfminer.six not installed; skipping complementary extraction. "
                "Add --with pdfminer.six to your uv invocation."
            )
        else:
            text = extract_full_text_pdfminer(pdf_path, page_indices)
            if text:
                full_pdfminer_rel = "full_text_pdfminer.md"
                with open(os.path.join(output_dir, full_pdfminer_rel), "w", encoding="utf-8") as f:
                    f.write(text)
                pdfminer_chars = len(text)

    # 5. Manifest.
    meta = doc.metadata or {}
    manifest = {
        "source_pdf": os.path.abspath(pdf_path),
        "filename": os.path.basename(pdf_path),
        "total_pages_in_pdf": total_pages,
        "processed_pages": len(manifest_pages),
        "pdf_metadata": {
            "title": meta.get("title") or "",
            "author": meta.get("author") or "",
            "subject": meta.get("subject") or "",
            "keywords": meta.get("keywords") or "",
            "creator": meta.get("creator") or "",
            "producer": meta.get("producer") or "",
        },
        "full_text_path": full_md_rel,
        "full_text_format": md_format,  # "markdown" or "plain"
        "full_text_pdfminer_path": full_pdfminer_rel,
        "full_text_pdfminer_chars": pdfminer_chars,
        "tables_detected": total_tables,
        "pages": manifest_pages,
        "options": {
            "dpi": dpi if do_images else None,
            "max_image_edge": max_edge if do_images else None,
            "text_extracted": do_text,
            "images_rendered": do_images,
            "pymupdf4llm_used": do_text and HAS_PYMUPDF4LLM and md_format == "markdown",
            "table_strategy": table_strategy if do_text else None,
            "pdfminer_extracted": bool(full_pdfminer_rel),
        },
    }

    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(
        description="Extract markdown text and page images from a PDF for Claude to read.",
    )
    parser.add_argument("--input", required=True,
                        help="Path or http(s) URL to the PDF file.")
    parser.add_argument("--output-dir", required=True,
                        help="Directory where extracted assets will be written.")
    parser.add_argument("--pages", default="",
                        help='Page selection, e.g. "1-5,9,12-15" (1-indexed). Default: all.')
    parser.add_argument("--dpi", type=int, default=150,
                        help="Render DPI for page images (default: 150).")
    parser.add_argument("--max-image-edge", type=int, default=2000,
                        help="Cap longest edge of rendered images in pixels (default: 2000). 0 disables.")
    parser.add_argument("--no-images", action="store_true",
                        help="Skip image rendering (text-only).")
    parser.add_argument("--no-text", action="store_true",
                        help="Skip text extraction (images only).")
    parser.add_argument("--no-pdfminer", action="store_true",
                        help="Skip the complementary pdfminer.six full-text pass.")
    parser.add_argument("--table-strategy", default="lines_strict",
                        choices=["lines_strict", "lines", "text"],
                        help=("pymupdf4llm table detection strategy. Default 'lines_strict' "
                              "is conservative: finds bordered tables reliably and never "
                              "false-positives on prose. Use 'text' only for table-heavy "
                              "documents with clean column alignment — it can wrap whole "
                              "prose pages in fake tables."))
    args = parser.parse_args()

    if args.no_images and args.no_text:
        print("ERROR: --no-images and --no-text together produce nothing.", file=sys.stderr)
        sys.exit(2)

    with tempfile.TemporaryDirectory() as work_dir:
        pdf_path = resolve_input(args.input, work_dir)

        # Open the PDF exactly once. Used for page-count probing, page-range
        # parsing, image rendering, AND passed straight into pymupdf4llm.
        with fitz.open(pdf_path) as doc:
            total = len(doc)
            page_indices = parse_page_spec(args.pages, total) if args.pages else list(range(total))

            if not page_indices:
                print("ERROR: --pages selected zero pages.", file=sys.stderr)
                sys.exit(2)

            manifest = process_pdf(
                doc=doc,
                pdf_path=pdf_path,
                output_dir=args.output_dir,
                page_indices=page_indices,
                dpi=args.dpi,
                do_text=not args.no_text,
                do_images=not args.no_images,
                max_edge=(args.max_image_edge if args.max_image_edge > 0 else None),
                do_pdfminer=not args.no_pdfminer,
                table_strategy=args.table_strategy,
            )

    # Print manifest to stdout for the calling agent.
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
