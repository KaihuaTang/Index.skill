#!/usr/bin/env python3
"""
IndexNote ID Generator
Generates sequential IDs for notes: YYYY-MM-DD_TYPE_NNN.md
Scans the _new/ directory to determine the next available ID.
"""

import argparse
import os
import re
from datetime import date


def get_next_id(note_type: str, vault_new_dir: str, target_date: str = None) -> str:
    """Get the next sequential 3-digit ID for a given type and date."""
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    # Pattern: YYYY-MM-DD_TYPE_NNN.md
    pattern = re.compile(
        rf"^{re.escape(target_date)}_{re.escape(note_type)}_(\d{{3}})\.md$"
    )

    max_id = 0
    if os.path.isdir(vault_new_dir):
        for filename in os.listdir(vault_new_dir):
            m = pattern.match(filename)
            if m:
                num = int(m.group(1))
                if num > max_id:
                    max_id = num

    next_id = max_id + 1
    return f"{next_id:03d}"


def main():
    parser = argparse.ArgumentParser(description="Generate next note ID for IndexNote")
    parser.add_argument("--type", required=True,
                        choices=["idea", "project", "book", "paper", "webinfo", "webnews"],
                        help="The note type")
    parser.add_argument("--vault-new-dir", required=True,
                        help="Path to the _new/ directory in the vault")
    parser.add_argument("--date", default=None,
                        help="Target date (YYYY-MM-DD), defaults to today")
    args = parser.parse_args()

    next_id = get_next_id(args.type, args.vault_new_dir, args.date)
    print(next_id)


if __name__ == "__main__":
    main()
