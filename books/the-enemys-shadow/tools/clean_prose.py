#!/usr/bin/env python3
"""Strip the 'the whole of' verbal tic from manuscript chapters.

A safety net for drafting: the phrase can spread through a page the way a
stain spreads through paper and flatten the prose. Removing it (and the
doubled words it leaves behind) restores the sentences without touching
narrative content.

    python3 tools/clean_prose.py manuscript/ch18.md [...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

KEEP_AFTER_A_WHOLE = (
    "day", "days", "week", "weeks", "month", "months", "year", "years", "hour",
    "hours", "life", "night", "nights", "morning", "afternoon", "evening",
    "summer", "winter", "minute", "minutes",
)

PATTERNS = [
    (r"\bone whole of an?\b\s*", "one "),
    (r"\bno whole of an?\b\s*", "no "),
    (r"\ba whole (?=(?!(?:" + "|".join(KEEP_AFTER_A_WHOLE) + r")\b)\S)", "a "),
    (r"\ba whole of a\b\s*", "a "),
    (r"\ba whole of the\b\s*", "the "),
    (r"\bthe whole of the\b\s*", "the "),
    (r"\bthe whole of a\b\s*", "a "),
    (r"\bthe whole of\b\s*", ""),
    (r"\bwhole of the\b\s*", "the "),
    (r"\ba whole of\b\s*", "a "),
]


def clean_paragraph(p: str) -> str:
    prev = None
    for _ in range(14):
        if prev == p:
            break
        prev = p
        for pattern, replacement in PATTERNS:
            p = re.sub(pattern, replacement, p)
    p = re.sub(r"\b(The|A|An|This|That|It|She|He|In|Of|And) \1\b", r"\1", p)  # doubled words, any case
    p = re.sub(r"\b(\w+) \1\b(?=\s+[a-z])", lambda m: m.group(1) if m.group(1).lower() not in {"had", "that", "so"} else m.group(0), p)
    p = re.sub(r"[ \t]{2,}", " ", p)
    return p.replace(" ,", ",").replace(" .", ".").strip()


def clean_document(text: str) -> str:
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped == "---" or stripped.startswith("#") or stripped == "* * *":
            out.append(line)
        else:
            out.append(clean_paragraph(line))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def main() -> None:
    for arg in sys.argv[1:]:
        path = Path(arg)
        before = path.read_text()
        after = clean_document(before)
        path.write_text(after)
        print(f"{path.name}: {before.lower().count('the whole of')} -> "
              f"{after.lower().count('the whole of')} tics, {len(after.split()):,} words")


if __name__ == "__main__":
    main()
