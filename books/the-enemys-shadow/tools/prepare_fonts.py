#!/usr/bin/env python3
"""Prepare the book's typefaces.

Downloads EB Garamond (SIL Open Font License 1.1) from the Google Fonts
repository, pins static instances of the variable axes, and subsets the
result down to the character set this novel actually needs (Latin, Latin
Extended-A/B, General Punctuation, the Polish, French and German
diacritics, and a couple of ornaments for scene breaks).

Run once before `build_pdf.py`:

    python3 tools/prepare_fonts.py

Outputs land in `assets/fonts/`. The license text ships alongside them.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from subprocess import check_call
import sys

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets" / "fonts"
CACHE = Path("/tmp/ebg-source")

SOURCE = "https://api.github.com/repos/google/fonts/contents/ofl/ebgaramond/"
SOURCES = {
    "EBGaramond[wght].ttf": "EBG-roman-var.ttf",
    "EBGaramond-Italic[wght].ttf": "EBG-italic-var.ttf",
    "OFL.txt": "OFL.txt",
}

# Static instances we cut out of the variable families.
INSTANCES = [
    ("EBG-roman-var.ttf", 400, "EBGaramond-Regular.ttf"),
    ("EBG-roman-var.ttf", 700, "EBGaramond-Bold.ttf"),
    ("EBG-italic-var.ttf", 400, "EBGaramond-Italic.ttf"),
    ("EBG-italic-var.ttf", 700, "EBGaramond-BoldItalic.ttf"),
]

UNICODE_RANGES = [
    (0x0020, 0x007E),  # Basic Latin
    (0x00A0, 0x00FF),  # Latin-1 Supplement
    (0x0100, 0x017F),  # Latin Extended-A  (Polish: a-ogonek, l-stroke, ...)
    (0x0180, 0x024F),  # Latin Extended-B
    (0x02B0, 0x02FF),  # Spacing Modifier Letters
    (0x0300, 0x036F),  # Combining Diacritical Marks
    (0x2000, 0x206F),  # General Punctuation
    (0x2070, 0x207F),  # Superscripts
    (0x20A0, 0x20BF),  # Currency Symbols
    (0x2100, 0x214F),  # Letterlike Symbols
    (0x2190, 0x21FF),  # Arrows
    (0x2200, 0x22FF),  # Mathematical Operators
    (0x25A0, 0x25FF),  # Geometric Shapes (scene-break ornament)
    (0x2600, 0x26FF),  # Miscellaneous Symbols
    (0x2760, 0x277F),  # Dingbats
]


def download() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    for remote, local in SOURCES.items():
        dest = CACHE / local
        if dest.exists():
            continue
        import urllib.parse

        url = SOURCE + urllib.parse.quote(remote)
        print(f"  fetching {remote}")
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.raw"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())


def build_instances() -> None:
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    for src_name, weight, out_name in INSTANCES:
        out = FONT_DIR / out_name
        font = TTFont(CACHE / src_name)
        instancer.instantiateVariableFont(font, {"wght": weight}, inplace=True, updateFontNames=False)
        font.save(out)
        print(f"  cut {out_name} @ wght={weight}")
        subset(out)


def subset(font_path: Path) -> None:
    unicodes = ",".join(f"U+{lo:04X}-{hi:04X}" for lo, hi in UNICODE_RANGES)
    tmp = font_path.with_suffix(".subset.ttf")
    check_call(
        [
            sys.executable,
            "-m",
            "fontTools.subset",
            str(font_path),
            f"--unicodes={unicodes}",
            "--layout-features=*",
            "--name-IDs=*",
            "--notdef-outline",
            f"--output-file={tmp}",
        ]
    )
    tmp.replace(font_path)
    print(f"    subset -> {font_path.stat().st_size // 1024} KB")


def main() -> None:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    print("Preparing typefaces (EB Garamond, OFL 1.1)…")
    download()
    build_instances()
    (FONT_DIR / "OFL.txt").write_text((CACHE / "OFL.txt").read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Done. Fonts in {FONT_DIR}")


if __name__ == "__main__":
    main()
