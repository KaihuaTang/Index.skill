#!/usr/bin/env python3
"""
WebUI Input Processing Test Suite

Tests that all 3 input methods (text, file, URL) correctly classify
into all 6 note types, and that the processing pipeline (classify →
generate ID → read template → build fallback note) works end-to-end.

Run:  uv run --with flask --with python-frontmatter python webUI/test_input.py
"""

import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# ── Setup paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "webUI"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "index-note" / "scripts"))

from classify_input import classify
from generate_id import get_next_id

# ── Test infrastructure ──────────────────────────────────────────────────
passed = 0
failed = 0
errors = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f"  ({detail})"
        print(msg)
        errors.append(msg)


def section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


# ======================================================================
# Part 1: classify_input.py — all 6 types via structural rules
# ======================================================================
section("Part 1: Input Classification (classify_input.py)")

# ── 1a: idea (plain text) ────────────────────────────────────────────
print("\n[idea] Plain text input")
r = classify("大语言模型的推理可能本质上是模式匹配而非逻辑推理")
check("Chinese text → idea", r["type"] == "idea", f"got {r['type']}")
check("confidence >= 0.9", r["confidence"] >= 0.9, f"got {r['confidence']}")
check("not a URL", r["is_url"] is False)
check("not a local path", r["is_local_path"] is False)

r2 = classify("Build a RAG pipeline with hybrid search")
check("English text → idea", r2["type"] == "idea", f"got {r2['type']}")

# ── 1b: paper (arXiv bare ID) ────────────────────────────────────────
print("\n[paper] arXiv bare ID")
r = classify("2501.12948")
check("bare arXiv ID → paper", r["type"] == "paper", f"got {r['type']}")
check("confidence = 0.95", r["confidence"] == 0.95, f"got {r['confidence']}")
check("details has arxiv_id", r["details"].get("arxiv_id") == "2501.12948")

r2 = classify("2401.12345v2")
check("arXiv ID with version → paper", r2["type"] == "paper", f"got {r2['type']}")

# ── 1c: paper (arXiv URL) ────────────────────────────────────────────
print("\n[paper] arXiv URL")
r = classify("https://arxiv.org/abs/2501.12948")
check("arXiv abs URL → paper", r["type"] == "paper", f"got {r['type']}")
check("is_url = True", r["is_url"] is True)

r2 = classify("https://arxiv.org/pdf/2501.12948")
check("arXiv pdf URL → paper", r2["type"] == "paper", f"got {r2['type']}")

# ── 1d: paper (academic domain) ──────────────────────────────────────
print("\n[paper] Academic domain URLs")
r = classify("https://doi.org/10.1234/example")
check("doi.org → paper", r["type"] == "paper", f"got {r['type']}")
check("needs_phase2 = True", r["needs_phase2"] is True)

r2 = classify("https://openreview.net/forum?id=xyz")
check("openreview.net → paper", r2["type"] == "paper", f"got {r2['type']}")

# ── 1e: project (GitHub URL) ─────────────────────────────────────────
print("\n[project] GitHub URL")
r = classify("https://github.com/anthropics/claude-code")
check("GitHub URL → project", r["type"] == "project", f"got {r['type']}")
check("confidence = 0.95", r["confidence"] == 0.95, f"got {r['confidence']}")

r2 = classify("https://www.github.com/user/repo")
check("GitHub URL with www → project", r2["type"] == "project", f"got {r2['type']}")

# ── 1f: project (local directory) ────────────────────────────────────
print("\n[project] Local directory")
# Use a directory that actually exists
r = classify(str(PROJECT_ROOT / "skills"))
check("existing local dir → project", r["type"] == "project", f"got {r['type']}")
check("is_local_path = True", r["is_local_path"] is True)

# ── 1g: book (local file with book extension) ────────────────────────
print("\n[book] Local file with book extensions")
# Create temp files to test
with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
    f.write(b"test")
    docx_path = f.name
with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
    f.write(b"test")
    epub_path = f.name
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
    f.write(b"test")
    txt_path = f.name

r = classify(docx_path)
check(".docx file → book", r["type"] == "book", f"got {r['type']}")
r2 = classify(epub_path)
check(".epub file → book", r2["type"] == "book", f"got {r2['type']}")
r3 = classify(txt_path)
check(".txt file → book", r3["type"] == "book", f"got {r3['type']}")

os.unlink(docx_path)
os.unlink(epub_path)
os.unlink(txt_path)

# ── 1h: paper/book ambiguous (PDF) ───────────────────────────────────
print("\n[paper/book] PDF file (ambiguous, needs phase2)")
with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
    f.write(b"test pdf content")
    pdf_path = f.name

r = classify(pdf_path)
check(".pdf file → paper (tentative)", r["type"] == "paper", f"got {r['type']}")
check("needs_phase2 = True for PDF", r["needs_phase2"] is True)
check("confidence = 0.50 (ambiguous)", r["confidence"] == 0.50, f"got {r['confidence']}")

os.unlink(pdf_path)

# ── 1i: webnews (news domain) ────────────────────────────────────────
print("\n[webnews] News domain URLs")
r = classify("https://www.reuters.com/technology/ai-policy-update-2026")
check("reuters.com → webnews", r["type"] == "webnews", f"got {r['type']}")

r2 = classify("https://36kr.com/p/12345678")
check("36kr.com → webnews", r2["type"] == "webnews", f"got {r2['type']}")

r3 = classify("https://techcrunch.com/2026/04/05/new-ai-tool")
check("techcrunch.com → webnews", r3["type"] == "webnews", f"got {r3['type']}")

r4 = classify("https://www.bbc.com/news/technology-12345")
check("bbc.com → webnews", r4["type"] == "webnews", f"got {r4['type']}")

# ── 1j: webinfo (general URL) ────────────────────────────────────────
print("\n[webinfo] General URL")
r = classify("https://huggingface.co/blog/open-llm-leaderboard")
check("huggingface blog → webinfo", r["type"] == "webinfo", f"got {r['type']}")
check("needs_phase2 = True", r["needs_phase2"] is True)

r2 = classify("https://lilianweng.github.io/posts/2023-06-23-agent/")
check("blog URL → webinfo", r2["type"] == "webinfo", f"got {r2['type']}")


# ======================================================================
# Part 2: generate_id.py — sequential ID generation
# ======================================================================
section("Part 2: ID Generation (generate_id.py)")

# Use a temp directory to avoid polluting the real vault
with tempfile.TemporaryDirectory() as tmp_dir:
    # Empty dir → first ID is 001
    nid = get_next_id("idea", tmp_dir)
    check("empty dir → 001", nid == "001", f"got {nid}")

    # Create a fake note to test increment
    Path(tmp_dir, f"2026-04-05_idea_001.md").touch()
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    Path(tmp_dir, f"{today}_idea_001.md").touch()
    nid = get_next_id("idea", tmp_dir, today)
    check("after 001 exists → 002", nid == "002", f"got {nid}")

    # Different type should not conflict
    nid2 = get_next_id("paper", tmp_dir, today)
    check("different type → 001", nid2 == "001", f"got {nid2}")

    # Multiple existing IDs
    Path(tmp_dir, f"{today}_idea_002.md").touch()
    Path(tmp_dir, f"{today}_idea_003.md").touch()
    nid3 = get_next_id("idea", tmp_dir, today)
    check("after 001-003 → 004", nid3 == "004", f"got {nid3}")


# ======================================================================
# Part 3: Flask API — /api/process endpoint and pipeline
# ======================================================================
section("Part 3: Flask API Tests")

from app import app, tasks, tasks_lock, build_fallback_note, parse_note, extract_tldr

app.config["TESTING"] = True
client = app.test_client()

# ── 3a: /api/process with text input ─────────────────────────────────
print("\n[API] POST /api/process — text input")
resp = client.post("/api/process", data={"input_type": "text", "input_text": "测试想法：AI将改变世界"})
data = resp.get_json()
check("returns 200", resp.status_code == 200)
check("returns task_id", "task_id" in data, f"got {data}")

if "task_id" in data:
    # Wait briefly and check task was created
    import time
    time.sleep(2)
    resp2 = client.get(f"/api/task/{data['task_id']}")
    task_data = resp2.get_json()
    check("task exists", resp2.status_code == 200)
    check("task has status", "status" in task_data, f"got {task_data}")
    check("task status is valid",
          task_data.get("status") in ("pending", "classifying", "generating_id",
                                       "extracting", "reading_template", "analyzing",
                                       "completed", "error"),
          f"got {task_data.get('status')}")

# ── 3b: /api/process with URL input ──────────────────────────────────
print("\n[API] POST /api/process — URL input")
resp = client.post("/api/process", data={"input_type": "url", "input_text": "https://arxiv.org/abs/2501.12948"})
data = resp.get_json()
check("URL input returns 200", resp.status_code == 200)
check("URL input returns task_id", "task_id" in data)

# ── 3c: /api/process with file upload ────────────────────────────────
print("\n[API] POST /api/process — file upload")
file_data = io.BytesIO(b"This is a test text file content for classification.")
resp = client.post(
    "/api/process",
    data={"input_type": "file", "file": (file_data, "test_note.txt")},
    content_type="multipart/form-data",
)
data = resp.get_json()
check("file upload returns 200", resp.status_code == 200)
check("file upload returns task_id", "task_id" in data)

# ── 3d: /api/process validation — empty text ─────────────────────────
print("\n[API] Validation — empty inputs")
resp = client.post("/api/process", data={"input_type": "text", "input_text": ""})
check("empty text → 400", resp.status_code == 400)

resp = client.post("/api/process", data={"input_type": "url", "input_text": ""})
check("empty URL → 400", resp.status_code == 400)

resp = client.post("/api/process", data={"input_type": "file"})
check("no file → 400", resp.status_code == 400)

resp = client.post("/api/process", data={"input_type": "invalid"})
check("invalid type → 400", resp.status_code == 400)

# ── 3e: /api/task — non-existent task ────────────────────────────────
print("\n[API] Task status — edge cases")
resp = client.get("/api/task/nonexistent_id")
check("unknown task → 404", resp.status_code == 404)


# ======================================================================
# Part 4: Fallback Note Generation
# ======================================================================
section("Part 4: Fallback Note Builder")

# Test with a real template
template_dir = PROJECT_ROOT / "IndexVault" / "_template"
today_str = date.today().isoformat()

for note_type in ["idea", "project", "book", "paper", "webinfo", "webnews"]:
    tmpl_path = template_dir / f"{note_type}_template.md"
    tmpl = tmpl_path.read_text(encoding="utf-8") if tmpl_path.exists() else ""
    note = build_fallback_note(f"test input for {note_type}", note_type, f"{today_str}_{note_type}_099", today_str, tmpl)
    check(f"fallback {note_type} — not empty", len(note.strip()) > 0)
    check(f"fallback {note_type} — has frontmatter", note.strip().startswith("---"))

# Test with URL input
note = build_fallback_note("https://example.com/article", "webinfo", f"{today_str}_webinfo_099", today_str, "")
check("fallback URL — has frontmatter", "---" in note)
check("fallback URL — has source", "example.com" in note or "https://example.com" in note)

# Test with empty template
note = build_fallback_note("我的测试想法", "idea", f"{today_str}_idea_099", today_str, "")
check("fallback empty template — creates minimal note", "TL;DR" in note)


# ======================================================================
# Part 5: Helper Functions
# ======================================================================
section("Part 5: Helper Functions (parse_note, extract_tldr)")

# Test parse_note
sample_note = """---
date: "2026-04-05"
type: paper
id: 2026-04-05_paper_001
title: "Test Paper Title"
tags: [deep-learning, attention]
---

# Test Paper Title

> [!abstract] TL;DR
> This is a test paper about attention mechanisms in transformers.

## Method

Some content here.
"""
with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
    f.write(sample_note)
    tmp_note = Path(f.name)

metadata, body = parse_note(tmp_note)
check("parse_note — type", metadata.get("type") == "paper", f"got {metadata.get('type')}")
check("parse_note — title", metadata.get("title") == "Test Paper Title")
check("parse_note — date", metadata.get("date") == "2026-04-05")
check("parse_note — tags is list", isinstance(metadata.get("tags"), list))
check("parse_note — body has content", "Method" in body)

# Test extract_tldr
tldr = extract_tldr(body)
check("extract_tldr — finds content", "attention" in tldr.lower(), f"got: {tldr}")
check("extract_tldr — no blockquote prefix", not tldr.startswith(">"))

# Test with no TL;DR
no_tldr = extract_tldr("# Just a title\n\nSome content without callout.")
check("extract_tldr — empty when missing", no_tldr == "")

tmp_note.unlink()


# ======================================================================
# Part 6: Classification via all 3 input methods (integration)
# ======================================================================
section("Part 6: Input Method → Classification Integration")

# Simulate what the webUI does for each input method
INPUT_SCENARIOS = [
    # (input_type, input_value, expected_type, description)
    ("text", "跨模态对齐层才是多模态AI的真正瓶颈", "idea", "Chinese text → idea"),
    ("text", "2505.00949", "paper", "arXiv ID as text → paper"),
    ("url", "https://github.com/langchain-ai/langchain", "project", "GitHub URL → project"),
    ("url", "https://arxiv.org/abs/2401.12345", "paper", "arXiv URL → paper"),
    ("url", "https://www.reuters.com/tech/ai-2026", "webnews", "Reuters URL → webnews"),
    ("url", "https://docs.python.org/3/tutorial/", "webinfo", "Python docs URL → webinfo"),
]

for input_type, input_val, expected_type, desc in INPUT_SCENARIOS:
    # For text and url, the input_text goes directly to classify
    effective_input = input_val
    r = classify(effective_input)
    check(f"[{input_type}] {desc}", r["type"] == expected_type, f"got {r['type']}")

# File upload: the effective input becomes the saved file path
print("\n[file] File upload scenarios")
with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
    f.write(b"%PDF-1.4 test")
    pdf_path = f.name
r = classify(pdf_path)
check("[file] .pdf upload → paper (tentative)", r["type"] == "paper", f"got {r['type']}")
os.unlink(pdf_path)

with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
    f.write(b"PK\x03\x04 test")
    docx_path = f.name
r = classify(docx_path)
check("[file] .docx upload → book", r["type"] == "book", f"got {r['type']}")
os.unlink(docx_path)


# ======================================================================
# Summary
# ======================================================================
section("Test Summary")
total = passed + failed
print(f"\n  Total:  {total}")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")

if errors:
    print("\n  Failed tests:")
    for e in errors:
        print(f"    {e}")

print()
sys.exit(0 if failed == 0 else 1)
