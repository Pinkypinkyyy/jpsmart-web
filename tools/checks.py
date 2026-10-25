#!/usr/bin/env python3
"""Simple site checks for jpsmart-web. Python standard library only.

Checks every .html / .xml / .txt file in the repo:
  1. Every JSON-LD block (<script type="application/ld+json">) parses as JSON.
  2. No "7-day" / "7 day" payment terms.
  3. No banned promise phrases: "any time", "day or night", "guarantee",
     "straight away".

Allow-list: the statutory Australian Consumer Law paragraph in
terms/index.html may use the word "guarantee(s)".

Run from the repo root:  python3 tools/checks.py
Exit code 0 = pass, 1 = fail.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", ".github", "tools", "node_modules", "img"}
EXTS = (".html", ".xml", ".txt")

BANNED = [
    ("7-day / 7 day term", re.compile(r"7[\s\u2011-]day", re.I)),
    ("any time", re.compile(r"\bany\s*time\b", re.I)),
    ("day or night", re.compile(r"day\s+or\s+night", re.I)),
    ("guarantee", re.compile(r"guarantee", re.I)),
    ("straight away", re.compile(r"straight\s+away", re.I)),
]

# (file, phrase label, text that must appear on the same line) -> allowed
ALLOW = [
    ("terms/index.html", "guarantee", "Australian Consumer Law"),
]

JSONLD = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


def files():
    for d, dirs, names in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for n in sorted(names):
            if n.endswith(EXTS):
                yield os.path.join(d, n)


def main():
    errors = []
    blocks = 0
    for path in files():
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for i, m in enumerate(JSONLD.finditer(text), 1):
            blocks += 1
            try:
                json.loads(m.group(1))
            except ValueError as e:
                line = text.count("\n", 0, m.start()) + 1
                errors.append(f"{rel}:{line}: JSON-LD block {i} does not parse: {e}")
        for n, line in enumerate(text.splitlines(), 1):
            for label, rx in BANNED:
                if not rx.search(line):
                    continue
                if any(rel == f and label == l and must in line for f, l, must in ALLOW):
                    continue
                errors.append(f"{rel}:{n}: banned phrase ({label})")
    print(f"Checked JSON-LD blocks: {blocks}")
    if errors:
        print(f"FAIL: {len(errors)} problem(s)")
        for e in errors:
            print("  " + e)
        return 1
    print("PASS: JSON-LD parses; no 7-day terms or banned phrases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
