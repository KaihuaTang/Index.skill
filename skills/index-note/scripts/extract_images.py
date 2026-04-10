#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IndexNote Image Extractor
Extracts images from various sources and saves to Obsidian vault _images/ folder.

Supports:
- arXiv papers (3-level priority: source package > PDF figures > PDF extraction)
- Local PDF files (books, papers)
- Web pages (downloads linked images)

Usage:
  python extract_images.py --type paper --input <arxiv_id_or_pdf_path> --note-id <note_id> --output-dir <_images_dir>
  python extract_images.py --type book --input <pdf_path> --note-id <note_id> --output-dir <_images_dir>
  python extract_images.py --type web --input <url> --note-id <note_id> --output-dir <_images_dir>
"""

import os
import sys
import re
import json
import shutil
import tarfile
import tempfile
import logging
import argparse
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    logger.warning("PyMuPDF (fitz) not found -- PDF image extraction disabled")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False


# ── arXiv source package download ────────────────────────────────────

def download_arxiv_source(arxiv_id, temp_dir):
    """Download and extract arXiv source package."""
    source_url = f"https://arxiv.org/e-print/{arxiv_id}"
    print(f"Downloading arXiv source: {source_url}", file=sys.stderr)

    try:
        if HAS_REQUESTS:
            response = requests.get(source_url, timeout=60)
            content = response.content if response.status_code == 200 else None
            status = response.status_code
        else:
            try:
                req = urllib.request.urlopen(source_url, timeout=60)
                content = req.read()
                status = req.status
            except urllib.error.HTTPError as e:
                logger.error("HTTP error %d: %s", e.code, e.reason)
                return False

        if status == 200 and content:
            tar_path = os.path.join(temp_dir, f"{arxiv_id}.tar.gz")
            with open(tar_path, "wb") as f:
                f.write(content)

            try:
                with tarfile.open(tar_path, "r:gz") as tar:
                    safe_members = []
                    for member in tar.getmembers():
                        if member.name.startswith("/") or ".." in member.name:
                            continue
                        if member.issym() or member.islnk():
                            continue
                        safe_members.append(member)
                    tar.extractall(path=temp_dir, members=safe_members)
                print(f"Source extracted to: {temp_dir}", file=sys.stderr)
                return True
            except tarfile.ReadError:
                # Not a tar.gz -- might be a single file (e.g., .tex)
                print("Source is not a tar.gz archive, skipping source extraction", file=sys.stderr)
                return False
        else:
            print(f"Download failed: HTTP {status}", file=sys.stderr)
            return False
    except Exception as e:
        logger.error("Failed to download source: %s", e)
        return False


def download_arxiv_pdf(arxiv_id, temp_dir):
    """Download arXiv PDF."""
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    pdf_path = os.path.join(temp_dir, f"{arxiv_id}.pdf")
    print(f"Downloading PDF: {pdf_url}", file=sys.stderr)

    try:
        if HAS_REQUESTS:
            response = requests.get(pdf_url, timeout=60)
            if response.status_code == 200:
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                return pdf_path
        else:
            urllib.request.urlretrieve(pdf_url, pdf_path)
            return pdf_path
    except Exception as e:
        logger.error("Failed to download PDF: %s", e)
    return None


# ── Source package image discovery ───────────────────────────────────

def find_source_images(temp_dir):
    """Find image files in arXiv source package directories."""
    figures = []
    seen = set()
    image_exts = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"}
    figure_dirs = ["pics", "figures", "fig", "images", "img", "figs", "figure"]

    # Search known figure directories
    for fig_dir in figure_dirs:
        fig_path = os.path.join(temp_dir, fig_dir)
        if os.path.isdir(fig_path):
            print(f"  Found figure directory: {fig_dir}/", file=sys.stderr)
            for fname in os.listdir(fig_path):
                fpath = os.path.join(fig_path, fname)
                if os.path.isfile(fpath) and fname not in seen:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in image_exts:
                        seen.add(fname)
                        figures.append({"path": fpath, "filename": fname, "source": "arxiv-source"})

    # Fallback: check root directory for image files
    if not figures:
        for fname in os.listdir(temp_dir):
            fpath = os.path.join(temp_dir, fname)
            if os.path.isfile(fpath):
                ext = os.path.splitext(fname)[1].lower()
                if ext in {".png", ".jpg", ".jpeg"} and "logo" not in fname.lower() and "icon" not in fname.lower():
                    figures.append({"path": fpath, "filename": fname, "source": "arxiv-source"})

    return figures


# ── PDF image extraction ────────────────────────────────────────────

def _is_pixmap_blank(pix, threshold=0.03):
    """Quick check if a pixmap is nearly all-black/blank by sampling pixels."""
    samples = pix.samples
    total = len(samples)
    n = pix.n                       # bytes per pixel (channels incl. alpha)
    if total == 0 or n == 0:
        return True
    num_pixels = total // n
    pixel_step = max(1, num_pixels // 500)     # sample ~500 pixels
    bright = 0
    count = 0
    for p in range(0, num_pixels, pixel_step):
        offset = p * n
        # Check max across all channels (skip alpha = last if present)
        channels = n - pix.alpha if pix.alpha else n
        max_val = max(samples[offset + c] for c in range(channels))
        count += 1
        if max_val > 15:
            bright += 1
    return count == 0 or (bright / count) < threshold


def _extract_pixmap(doc, xref, smask_xref):
    """Build a Pixmap from xref, applying SMask and CMYK conversion."""
    pix = fitz.Pixmap(doc, xref)

    # CMYK → RGB conversion (must happen before SMask compositing)
    if pix.n - pix.alpha > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)

    # Apply soft mask if present — without this, masked images appear all-black
    if smask_xref > 0:
        try:
            mask = fitz.Pixmap(doc, smask_xref)
            if not pix.alpha:
                pix = fitz.Pixmap(pix, 1)       # add alpha channel
            pix.set_alpha(mask.samples)          # write mask into alpha
        except Exception as e:
            logger.debug("SMask apply failed (xref=%d): %s", xref, e)

    # Final output must be RGB or RGBA (strip other spaces)
    if pix.n - pix.alpha < 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)

    return pix


def extract_images_from_pdf(pdf_path, output_dir, note_id, start_idx=1,
                            min_width=200, min_height=200, min_bytes=5000):
    """Extract images directly from a PDF file using PyMuPDF.

    Uses Pixmap-based extraction so that SMask (soft-mask) layers are
    composited and CMYK images are converted to RGB.  Falls back to
    raw ``extract_image`` for edge cases.
    """
    if not HAS_FITZ:
        print("PyMuPDF not available, skipping PDF extraction", file=sys.stderr)
        return []

    print(f"Extracting images from PDF: {os.path.basename(pdf_path)}", file=sys.stderr)
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.error("Cannot open PDF: %s", e)
        return []

    extracted = []
    skipped = 0
    seen_xrefs = set()          # deduplicate across pages
    idx = start_idx

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            images = page.get_images(full=True)

            for img_info in images:
                xref = img_info[0]
                smask_xref = img_info[1]       # 0 means no soft-mask

                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                try:
                    pix = _extract_pixmap(doc, xref, smask_xref)
                except Exception:
                    # Fallback: raw byte extraction (simple images w/o mask)
                    try:
                        base_image = doc.extract_image(xref)
                        if not base_image:
                            continue
                        img_bytes = base_image["image"]
                        img_w = base_image.get("width", 0)
                        img_h = base_image.get("height", 0)
                        if img_w < min_width or img_h < min_height or len(img_bytes) < min_bytes:
                            skipped += 1
                            continue
                        ext = base_image["ext"]
                        filename = f"{note_id}_{idx:02d}.{ext}"
                        filepath = os.path.join(output_dir, filename)
                        with open(filepath, "wb") as f:
                            f.write(img_bytes)
                        extracted.append({
                            "filename": filename,
                            "size": len(img_bytes),
                            "width": img_w,
                            "height": img_h,
                            "ext": ext,
                            "source": "pdf-extraction",
                            "page": page_num + 1,
                        })
                        idx += 1
                    except Exception:
                        pass
                    continue

                # Size filter
                if pix.width < min_width or pix.height < min_height:
                    skipped += 1
                    continue

                # Blank / all-black filter
                if _is_pixmap_blank(pix):
                    skipped += 1
                    continue

                # Save as PNG (lossless, universal)
                filename = f"{note_id}_{idx:02d}.png"
                filepath = os.path.join(output_dir, filename)
                pix.save(filepath)
                file_size = os.path.getsize(filepath)

                if file_size < min_bytes:
                    os.remove(filepath)
                    skipped += 1
                    continue

                extracted.append({
                    "filename": filename,
                    "size": file_size,
                    "width": pix.width,
                    "height": pix.height,
                    "ext": "png",
                    "source": "pdf-extraction",
                    "page": page_num + 1,
                })
                idx += 1
    finally:
        doc.close()

    if skipped:
        print(f"  Filtered {skipped} small/blank images", file=sys.stderr)
    return extracted


def convert_pdf_figure_to_png(pdf_fig_path, output_dir, note_id, start_idx=1):
    """Convert a PDF figure file (from source package) to PNG."""
    if not HAS_FITZ:
        return []

    try:
        doc = fitz.open(pdf_fig_path)
    except Exception:
        return []

    extracted = []
    idx = start_idx

    try:
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(dpi=150)
            filename = f"{note_id}_{idx:02d}.png"
            filepath = os.path.join(output_dir, filename)
            pix.save(filepath)

            extracted.append({
                "filename": filename,
                "size": os.path.getsize(filepath),
                "width": pix.width,
                "height": pix.height,
                "ext": "png",
                "source": "pdf-figure",
                "original": os.path.basename(pdf_fig_path),
            })
            idx += 1
    finally:
        doc.close()

    return extracted


# ── Web image download ──────────────────────────────────────────────

def download_web_images(url, output_dir, note_id, max_images=5):
    """Download images from a web page (best-effort)."""
    # This is a lightweight approach -- the main skill workflow
    # will handle web screenshots via WebFetch/browser tools
    # This function handles direct image URL downloads
    extracted = []

    if not url:
        return extracted

    # If the URL itself is a direct image
    img_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
    if any(url.lower().endswith(ext) for ext in img_exts):
        try:
            ext = os.path.splitext(url)[1].lower().lstrip(".")
            filename = f"{note_id}_01.{ext}"
            filepath = os.path.join(output_dir, filename)

            if HAS_REQUESTS:
                r = requests.get(url, timeout=30)
                if r.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(r.content)
                    extracted.append({
                        "filename": filename,
                        "size": len(r.content),
                        "ext": ext,
                        "source": "web-download",
                        "url": url,
                    })
            else:
                urllib.request.urlretrieve(url, filepath)
                extracted.append({
                    "filename": filename,
                    "size": os.path.getsize(filepath),
                    "ext": ext,
                    "source": "web-download",
                    "url": url,
                })
        except Exception as e:
            logger.warning("Failed to download image: %s", e)

    return extracted


# ── Main extraction pipeline ────────────────────────────────────────

def extract_paper_images(input_str, note_id, output_dir):
    """Full 3-level priority extraction for papers."""
    all_images = []
    idx = 1

    # Determine if input is arXiv ID or local PDF
    arxiv_id = None
    pdf_path = None

    arxiv_match = re.match(r"(\d{4}\.\d{4,5})(v\d+)?$", input_str)
    if arxiv_match:
        arxiv_id = arxiv_match.group(1)
    elif os.path.isfile(input_str):
        pdf_path = input_str
        # Try to extract arXiv ID from filename
        m = re.search(r"(\d{4}\.\d{4,5})", os.path.basename(input_str))
        if m:
            arxiv_id = m.group(1)

    with tempfile.TemporaryDirectory() as temp_dir:
        processed_pdfs = set()          # track PDF figures already converted

        # Priority 1: arXiv source package images
        if arxiv_id:
            if download_arxiv_source(arxiv_id, temp_dir):
                source_imgs = find_source_images(temp_dir)
                if source_imgs:
                    print(f"\n  Found {len(source_imgs)} images in arXiv source", file=sys.stderr)
                    for fig in source_imgs:
                        ext = os.path.splitext(fig["filename"])[1].lower()
                        if ext == ".pdf":
                            # Convert PDF figures to PNG
                            converted = convert_pdf_figure_to_png(
                                fig["path"], output_dir, note_id, start_idx=idx
                            )
                            processed_pdfs.add(os.path.realpath(fig["path"]))
                            for c in converted:
                                all_images.append(c)
                                idx += 1
                        elif ext in (".eps", ".svg"):
                            # Skip vector formats that Obsidian can't display inline
                            print(f"  Skipping vector format: {fig['filename']}", file=sys.stderr)
                        else:
                            # Copy raster images directly
                            filename = f"{note_id}_{idx:02d}{ext}"
                            dst = os.path.join(output_dir, filename)
                            shutil.copy2(fig["path"], dst)
                            all_images.append({
                                "filename": filename,
                                "size": os.path.getsize(dst),
                                "ext": ext.lstrip("."),
                                "source": "arxiv-source",
                                "original": fig["filename"],
                            })
                            idx += 1

        # Priority 2: PDF figure files from source package (skip already processed)
        if arxiv_id and os.path.exists(temp_dir):
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if (f.endswith(".pdf")
                        and "logo" not in f.lower()
                        and f != f"{arxiv_id}.tar.gz"
                        and f != f"{arxiv_id}.pdf"):
                        pdf_fig = os.path.join(root, f)
                        if os.path.realpath(pdf_fig) in processed_pdfs:
                            continue
                        try:
                            converted = convert_pdf_figure_to_png(
                                pdf_fig, output_dir, note_id, start_idx=idx
                            )
                            for c in converted:
                                all_images.append(c)
                                idx += 1
                        except Exception as e:
                            logger.warning("  Skipping PDF figure %s: %s", f, e)

        # Priority 3: Direct PDF extraction (fallback — only if too few images found)
        if len(all_images) < 3:
            if not pdf_path and arxiv_id:
                pdf_path = download_arxiv_pdf(arxiv_id, temp_dir)
            if pdf_path:
                pdf_imgs = extract_images_from_pdf(
                    pdf_path, output_dir, note_id, start_idx=idx
                )
                all_images.extend(pdf_imgs)

    return all_images


def extract_book_images(input_str, note_id, output_dir):
    """Extract images from book PDFs."""
    if not os.path.isfile(input_str):
        return []

    ext = os.path.splitext(input_str)[1].lower()
    if ext != ".pdf":
        print(f"  Book is not PDF ({ext}), no images to extract", file=sys.stderr)
        return []

    return extract_images_from_pdf(input_str, output_dir, note_id, start_idx=1)


def extract_project_images(input_str, note_id, output_dir):
    """Extract images from project README or docs."""
    images = []
    idx = 1
    img_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    search_dir = input_str
    if not os.path.isdir(search_dir):
        return []

    # Look for images in docs/, assets/, images/, screenshots/ directories
    search_paths = [
        search_dir,
        os.path.join(search_dir, "docs"),
        os.path.join(search_dir, "assets"),
        os.path.join(search_dir, "images"),
        os.path.join(search_dir, "screenshots"),
        os.path.join(search_dir, "static"),
    ]

    for sp in search_paths:
        if not os.path.isdir(sp):
            continue
        for fname in os.listdir(sp):
            fpath = os.path.join(sp, fname)
            ext = os.path.splitext(fname)[1].lower()
            if os.path.isfile(fpath) and ext in img_exts:
                fsize = os.path.getsize(fpath)
                if fsize > 5000:  # Skip tiny icons
                    out_name = f"{note_id}_{idx:02d}{ext}"
                    dst = os.path.join(output_dir, out_name)
                    shutil.copy2(fpath, dst)
                    images.append({
                        "filename": out_name,
                        "size": fsize,
                        "ext": ext.lstrip("."),
                        "source": "project-asset",
                        "original": fname,
                    })
                    idx += 1
                    if idx > 10:  # Limit to 10 images
                        break
        if idx > 10:
            break

    return images


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(description="IndexNote Image Extractor")
    parser.add_argument("--type", required=True,
                        choices=["paper", "book", "project", "web"],
                        help="Content type")
    parser.add_argument("--input", required=True,
                        help="arXiv ID, PDF path, folder path, or URL")
    parser.add_argument("--note-id", required=True,
                        help="Note ID (e.g., 2026-04-05_paper_001)")
    parser.add_argument("--output-dir", required=True,
                        help="Output directory for images")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    if args.type == "paper":
        images = extract_paper_images(args.input, args.note_id, args.output_dir)
    elif args.type == "book":
        images = extract_book_images(args.input, args.note_id, args.output_dir)
    elif args.type == "project":
        images = extract_project_images(args.input, args.note_id, args.output_dir)
    elif args.type == "web":
        images = download_web_images(args.input, args.output_dir, args.note_id)
    else:
        images = []

    # Output compact JSON — only fields the skill needs (filename + dimensions)
    compact = []
    for img in images:
        entry = {"filename": img["filename"]}
        if "width" in img:
            entry["width"] = img["width"]
            entry["height"] = img["height"]
        compact.append(entry)
    result = {"total": len(compact), "images": compact}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
