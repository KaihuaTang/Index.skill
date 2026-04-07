#!/usr/bin/env python3
"""
IndexNote Image Finalizer
Parses a generated note for ![[image]] references, moves only referenced images
from a temp directory to _images/{note_id}/, and cleans up unused images.
"""

import argparse
import json
import os
import re
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description="Finalize note images")
    parser.add_argument("--note-path", required=True,
                        help="Path to the generated note .md file")
    parser.add_argument("--temp-dir", required=True,
                        help="Temp directory containing extracted images")
    parser.add_argument("--images-dir", required=True,
                        help="Base _images/ directory")
    parser.add_argument("--note-id", required=True,
                        help="Note ID (used as subdirectory name)")
    args = parser.parse_args()

    # Parse note for ![[filename|width]] or ![[filename]] image references
    if not os.path.isfile(args.note_path):
        print(json.dumps({"error": "Note file not found", "kept": 0, "removed": 0}))
        sys.exit(1)

    with open(args.note_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match ![[filename]] and ![[filename|width]]
    referenced = set(re.findall(r"!\[\[([^\]|]+?)(?:\|\d+)?\]\]", content))

    # Create target subdirectory: _images/{note_id}/
    target_dir = os.path.join(args.images_dir, args.note_id)
    os.makedirs(target_dir, exist_ok=True)

    kept = []
    removed = []

    if os.path.isdir(args.temp_dir):
        for fname in os.listdir(args.temp_dir):
            src = os.path.join(args.temp_dir, fname)
            if not os.path.isfile(src):
                continue
            if fname in referenced:
                shutil.move(src, os.path.join(target_dir, fname))
                kept.append(fname)
            else:
                removed.append(fname)

        # Clean up temp directory
        shutil.rmtree(args.temp_dir, ignore_errors=True)

    # Remove target dir if nothing was kept
    if not kept and os.path.isdir(target_dir) and not os.listdir(target_dir):
        os.rmdir(target_dir)

    result = {
        "note_id": args.note_id,
        "kept": len(kept),
        "removed": len(removed),
        "kept_files": kept,
        "removed_files": removed,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
