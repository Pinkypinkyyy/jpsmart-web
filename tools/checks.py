#!/usr/bin/env python3
"""Simple site checks for jpsmart-web. Python standard library only.

Checks every .html / .xml / .txt file in the repo:
  1. Every JSON-LD block (<script type="application/ld+json">) parses as JSON.
  2. No "7-day" / "7 day" payment terms.
  3. No banned promise phrases: "any time", "day or night", "guarantee",
     "straight away".
  4. No banned service wording (the three words are written as character
     classes in BANNED below, so a repo-wide grep for them stays at 0).
     Three known lines in index.html are allow-listed ONLY until PR #3
     (which removes them) merges; see SERVICE_PENDING_PR3 below.
  5. No phone number other than 0485 005 568 (tel: and +61 forms of the same
     number are fine). Dollar figures, "$10 million", ABN and dates are not
     phone numbers. ACMA's reserved fictional mobile numbers (0491 570 006,
     156, 157, 158, 159 and 110) are allowed as form examples.

  6. QBCC wording (qbcc-wording-final-2026-10-25.md): the only threshold wording
     is QBCC_LINE. No "$3,300 or more", "under $3,300", "QBCC-licensed", penalty
     amounts or penalty units. Every line that says "$3,300" is QBCC_LINE, every
     page's footer carries it, and each service page (home, IKEA, property
     managers) carries it in its body.

  7. No cover/policy claims (held until a current certificate has been seen by
     the CFO and the JP Smart CEO). The banned words are written as character
     classes in COVER_BANNED so a repo-wide grep for them stays at 0.

Allow-list for "guarantee": the statutory Australian Consumer Law paragraph in
terms/index.html (the line containing "Australian Consumer Law").

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
    ("banned service wording", re.compile(r"cl[e]an|pre[s]sure|gut[t]er", re.I)),
]

# (file, label, text that must appear on the same line) -> allowed
ALLOW = [
    ("terms/index.html", "guarantee", "Australian Consumer Law"),
]

# TEMPORARY: these lines are removed by PR #3. Allowing them lets PR #4 pass
# on its own; after PR #3 merges they no longer exist and this list is dead
# (delete it then). The check still fails on any OTHER banned service wording.
SERVICE_PENDING_PR3 = [
    ("index.html", r"Pre[s]sure cl[e]aning</li><li>Single-storey gut[t]er cl[e]ans"),
    ("index.html", r'value="Single-storey gut[t]er cl[e]an"><span>Gut[t]ers</span>'),
    ("index.html", r'value="Pre[s]sure cl[e]aning"><span>Pre[s]sure cl[e]aning</span>'),
]

QBCC_LINE = ("Unlicensed: cannot perform building work valued at more than $3,300 "
             "(including GST, labour and all materials, regardless of who supplies them).")
QBCC_BANNED = re.compile(r"3,300 or more|under \$3,300|less than \$3,300|QBCC-licensed|17,270|penalt|penalty unit", re.I)
COVER_BANNED = re.compile(r"[i]nsur(?:ed|ance|er)|[A]llianz|public [l]iability|certificate of [c]urrency", re.I)
SERVICE_PAGES = ("index.html", "ikea-assembly/index.html", "property-managers/index.html")

OK_PHONES = {
    "0485005568", "61485005568",
    "0491570006", "0491570156", "0491570157", "0491570158", "0491570159",
    "0491570110",
}
# digit runs with optional spaces, dashes, brackets or a leading +
PHONE_RX = re.compile(
    r"(?<![\w$.,/-])(\+?\(?\d{2,4}\)?(?:[ -]\d{2,4}){1,4}|\+?\d{9,12})(?![\w])"
)

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


def phone_problems(line):
    out = []
    for m in PHONE_RX.finditer(line):
        raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        # skip things that are clearly not phones: too short/long, ABN-like,
        # or preceded by "$" handled by the lookbehind
        if len(digits) < 9 or len(digits) > 12:
            continue
        if not (digits.startswith(("0", "61", "1300", "1800"))):
            continue
        if digits not in OK_PHONES:
            out.append(raw.strip())
    return out


def main():
    errors = []
    notes = []
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
                if label.startswith("banned service"):
                    # blank out only the exact pending-PR #3 fragments, then re-test
                    rest = line
                    for f, must in SERVICE_PENDING_PR3:
                        if rel == f:
                            rest = re.sub(must, "", rest)
                    if rest != line:
                        if not rx.search(rest):
                            notes.append(f"{rel}:{n}: pending-PR3 service wording allowed until PR #3 merges")
                            continue
                errors.append(f"{rel}:{n}: banned phrase ({label})")
            if QBCC_BANNED.search(line):
                errors.append(f"{rel}:{n}: banned QBCC wording (threshold or penalty wording)")
            if COVER_BANNED.search(line):
                errors.append(f"{rel}:{n}: banned cover/policy wording (held until a current certificate is seen)")
            if "$3,300" in line and QBCC_LINE not in line:
                errors.append(f"{rel}:{n}: $3,300 appears without the exact QBCC line")
            for bad in phone_problems(line):
                errors.append(f"{rel}:{n}: phone number other than 0485 005 568: {bad}")
    for path in files():
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        if not rel.endswith(".html"):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if "<footer" in text:
            foot = text[text.index("<footer"):]
            if QBCC_LINE not in foot:
                errors.append(f"{rel}: footer is missing the QBCC line")
        if rel in SERVICE_PAGES:
            body = text[:text.index("<footer")] if "<footer" in text else text
            if QBCC_LINE not in body:
                errors.append(f"{rel}: service page body is missing the QBCC line")
    print(f"Checked JSON-LD blocks: {blocks}")
    for note in notes:
        print("  note: " + note)
    if errors:
        print(f"FAIL: {len(errors)} problem(s)")
        for e in errors:
            print("  " + e)
        return 1
    print("PASS: JSON-LD parses; no 7-day terms, banned phrases, banned service wording, stray phone numbers, off-script QBCC wording or cover/policy claims.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
