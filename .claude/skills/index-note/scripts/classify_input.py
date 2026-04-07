#!/usr/bin/env python3
"""
IndexNote Input Classifier
Classifies arbitrary input strings into 6 knowledge types:
  idea, project, book, paper, webinfo, webnews
"""

import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse

# ── News domain patterns ──────────────────────────────────────────────
NEWS_DOMAINS = {
    # International
    "reuters.com", "bbc.com", "bbc.co.uk", "cnn.com", "nytimes.com",
    "washingtonpost.com", "theguardian.com", "apnews.com", "bloomberg.com",
    "cnbc.com", "aljazeera.com", "france24.com", "dw.com",
    "news.google.com", "news.yahoo.com",
    # Tech news
    "techcrunch.com", "theverge.com", "arstechnica.com", "wired.com",
    "engadget.com", "zdnet.com", "venturebeat.com", "thenextweb.com",
    # Chinese news
    "xinhuanet.com", "people.com.cn", "chinadaily.com.cn",
    "thepaper.cn", "36kr.com", "sina.com.cn", "163.com", "qq.com",
    "sohu.com", "ifeng.com", "caixin.com", "jiemian.com",
    "huxiu.com", "ithome.com", "guancha.cn",
}

NEWS_PATH_PATTERNS = ["/news/", "/article/", "/breaking/", "/story/",
                      "/headlines/", "/world/", "/politics/", "/business/"]

# ── Academic domain patterns ──────────────────────────────────────────
ACADEMIC_DOMAINS = {
    "arxiv.org", "openreview.net", "semanticscholar.org", "scholar.google.com",
    "doi.org", "dl.acm.org", "ieee.org", "springer.com", "nature.com",
    "sciencedirect.com", "wiley.com", "aaai.org", "proceedings.mlr.press",
    "aclanthology.org", "papers.nips.cc", "biorxiv.org", "medrxiv.org",
}

# ── Book-related patterns ────────────────────────────────────────────
BOOK_EXTENSIONS = {".docx", ".doc", ".txt", ".epub", ".mobi", ".azw3", ".rtf"}
PAPER_OR_BOOK_EXTENSIONS = {".pdf"}

# ── GitHub pattern ───────────────────────────────────────────────────
GITHUB_RE = re.compile(r"^https?://(www\.)?github\.com/[^/]+/[^/]+", re.I)

# ── arXiv patterns ──────────────────────────────────────────────────
ARXIV_URL_RE = re.compile(
    r"^https?://(www\.)?arxiv\.org/(abs|pdf|html)/(\d{4}\.\d{4,5})(v\d+)?", re.I
)
ARXIV_BARE_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")


def is_url(s: str) -> bool:
    """Check if string looks like a URL."""
    try:
        r = urlparse(s)
        return r.scheme in ("http", "https") and bool(r.netloc)
    except Exception:
        return False


def is_local_path(s: str) -> bool:
    """Check if string looks like a local filesystem path."""
    # Windows absolute path or Unix absolute path or relative path with separators
    if re.match(r"^[A-Za-z]:[/\\]", s):
        return True
    if s.startswith("/") or s.startswith("./") or s.startswith("../"):
        return True
    if s.startswith("~"):
        return True
    # Contains path separators and looks like a path
    if (os.sep in s or "/" in s) and not is_url(s):
        return True
    return False


def get_domain(url: str) -> str:
    """Extract domain from URL, removing www. prefix."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def is_news_domain(domain: str) -> bool:
    """Check if domain is a known news outlet."""
    if domain in NEWS_DOMAINS:
        return True
    # Check parent domains (e.g., news.163.com → 163.com)
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        parent = ".".join(parts[i:])
        if parent in NEWS_DOMAINS:
            return True
    # Check if 'news' is a subdomain
    if domain.startswith("news."):
        return True
    return False


def is_news_path(url: str) -> bool:
    """Check if URL path suggests news content."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    return any(p in path for p in NEWS_PATH_PATTERNS)


def is_academic_domain(domain: str) -> bool:
    """Check if domain is an academic/research site."""
    for ad in ACADEMIC_DOMAINS:
        if domain == ad or domain.endswith("." + ad):
            return True
    return False


def classify(input_str: str) -> dict:
    """Classify the input string into one of 6 types."""
    input_str = input_str.strip()
    result = {
        "type": "idea",
        "input_original": input_str,
        "is_url": False,
        "is_local_path": False,
        "url_domain": "",
        "file_extension": "",
        "confidence": 0.0,
        "needs_phase2": False,
        "details": {},
    }

    # ── Rule 1: Bare arXiv ID ──────────────────────────────────────
    if ARXIV_BARE_ID_RE.match(input_str):
        result["type"] = "paper"
        result["confidence"] = 0.95
        result["details"] = {
            "arxiv_id": input_str.replace("v", "").split("v")[0] if "v" in input_str else input_str,
            "source": "bare_arxiv_id",
        }
        return result

    # ── Rule 2: Local folder path ──────────────────────────────────
    if is_local_path(input_str) and os.path.isdir(input_str):
        result["type"] = "project"
        result["is_local_path"] = True
        result["confidence"] = 0.95
        result["details"] = {"local_dir": input_str}
        return result

    # ── Rule 3: Local file path ────────────────────────────────────
    if is_local_path(input_str) and os.path.isfile(input_str):
        result["is_local_path"] = True
        _, ext = os.path.splitext(input_str.lower())
        result["file_extension"] = ext

        if ext in BOOK_EXTENSIONS:
            result["type"] = "book"
            result["confidence"] = 0.90
            result["details"] = {"local_file": input_str}
        elif ext in PAPER_OR_BOOK_EXTENSIONS:
            # PDF could be paper or book — needs Phase 2
            result["type"] = "paper"  # tentative
            result["confidence"] = 0.50
            result["needs_phase2"] = True
            result["details"] = {
                "local_file": input_str,
                "note": "PDF file — could be paper or book, needs content analysis",
            }
        else:
            result["type"] = "book"
            result["confidence"] = 0.70
            result["details"] = {"local_file": input_str}
        return result

    # ── Rule 4: URL-based classification ───────────────────────────
    if is_url(input_str):
        result["is_url"] = True
        domain = get_domain(input_str)
        result["url_domain"] = domain

        # 4a: GitHub URL → project
        if GITHUB_RE.match(input_str):
            result["type"] = "project"
            result["confidence"] = 0.95
            result["details"] = {"github_url": input_str}
            return result

        # 4b: arXiv URL → paper
        m = ARXIV_URL_RE.match(input_str)
        if m:
            result["type"] = "paper"
            result["confidence"] = 0.95
            result["details"] = {
                "arxiv_id": m.group(3),
                "arxiv_url": input_str,
            }
            return result

        # 4c: Academic domain → paper
        if is_academic_domain(domain):
            result["type"] = "paper"
            result["confidence"] = 0.80
            result["needs_phase2"] = True
            result["details"] = {
                "academic_url": input_str,
                "note": "Academic domain detected — verify paper content",
            }
            return result

        # 4d: News domain or path → webnews
        if is_news_domain(domain) or is_news_path(input_str):
            result["type"] = "webnews"
            result["confidence"] = 0.85
            result["details"] = {"news_url": input_str}
            return result

        # 4e: General URL → webinfo (may be reclassified in Phase 2)
        result["type"] = "webinfo"
        result["confidence"] = 0.70
        result["needs_phase2"] = True
        result["details"] = {
            "url": input_str,
            "note": "General URL — may be reclassified after content analysis",
        }
        return result

    # ── Rule 5: Local path that doesn't exist ──────────────────────
    if is_local_path(input_str):
        result["is_local_path"] = True
        result["type"] = "idea"
        result["confidence"] = 0.50
        result["details"] = {
            "note": f"Path-like input but path does not exist: {input_str}",
        }
        return result

    # ── Rule 6: Plain text → idea ──────────────────────────────────
    result["type"] = "idea"
    result["confidence"] = 0.90
    result["details"] = {"text": input_str}
    return result


def main():
    parser = argparse.ArgumentParser(description="Classify input for IndexNote")
    parser.add_argument("--input", required=True, help="The input string to classify")
    args = parser.parse_args()

    result = classify(args.input)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
