#!/usr/bin/env python3
"""Typeset *The Enemy's Shadow* into a print-quality PDF.

Not a file converter: a small book compositor. It performs its own
line-breaking, dictionary hyphenation (pyphen), full justification, first-line
indents, drop caps, scene-break ornaments, running heads, part pages and a
page-numbered table of contents, then mirrors margins for recto/verso pages.

    python3 tools/build_pdf.py [--manuscript DIR] [--out FILE] [--check]

Trim: 6in x 9in (152 x 229 mm), the standard size for literary historical
fiction. Two text passes are run so the contents can carry real folios.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pyphen
from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
CHAPTER_DIR = ROOT / "manuscript"
OUT_DIR = ROOT / "output"
FONT_DIR = ROOT / "assets" / "fonts"
DEFAULT_OUT = OUT_DIR / "the-enemys-shadow.pdf"

TITLE = "The Enemy's Shadow"

# ---------------------------------------------------------------- page geometry
PAGE_W, PAGE_H = 152.0, 229.0
M_TOP, M_BOTTOM = 22.0, 20.0          # body text block
M_INNER, M_OUTER = 21.0, 17.5         # mirrored
TEXT_W = PAGE_W - M_INNER - M_OUTER
HEAD_Y, FOLIO_Y = 11.6, 218.5
BOTTOM = PAGE_H - M_BOTTOM

BODY_SIZE = 10.8
LEADING = 4.90                      # millimetres (13.9pt) - the measure is in mm
INDENT = 5.4
QUOTE_SIZE = 9.9
QUOTE_LEADING = 4.35
CHAP_TITLE_SIZE = 22.5
DROPCAP_LINES = 3
CAP_RATIO = 0.65                       # EB Garamond sCapHeight / em
PT2MM = 25.4 / 72.0
OPENER_TOP = 56.0
OPENER_TEXT_TOP = 98.5

BLACK = (19, 17, 16)
INK_GREY = (114, 108, 103)
RULE_GREY = (172, 166, 160)

EM = "\u2014"
DIAMOND = "\u25C6"
PAGE_WORDS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
              "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
              "Seventeen", "Eighteen", "Nineteen", "Twenty", "Twenty-One", "Twenty-Two",
              "Twenty-Three", "Twenty-Four", "Twenty-Five", "Twenty-Six", "Twenty-Seven"]


# ---------------------------------------------------------------------- styling
@dataclass(frozen=True)
class Style:
    variant: str = ""                  # "" | "B" | "I" | "BI"
    size: float = BODY_SIZE
    tracking: float = 0.0
    color: Tuple[int, int, int] = BLACK

    def with_(self, **kw) -> "Style":
        return Style(**{**self.__dict__, **kw})


BODY = Style()


class Book(FPDF):
    """FPDF with absolute glyph placement and hand-built page furniture."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format=(PAGE_W, PAGE_H))
        self.set_auto_page_break(False)
        self.set_margins(0, 0, 0)
        self.set_compression(True)
        for variant, filename in {
            "": "EBGaramond-Regular.ttf",
            "B": "EBGaramond-Bold.ttf",
            "I": "EBGaramond-Italic.ttf",
            "BI": "EBGaramond-BoldItalic.ttf",
        }.items():
            self.add_font("EB Garamond", variant, str(FONT_DIR / filename))
        self._active: Optional[Style] = None
        self.roman_folio = True
        self.folio_offset = 0
        self.running_title = ""         # printed on the recto head

    # -- glyph level -------------------------------------------------------
    def apply(self, style: Style) -> None:
        if self._active != style:
            self.set_font("EB Garamond", style.variant, style.size)
            self.set_char_spacing(style.tracking)
            self.set_text_color(*style.color)
            self._active = style

    @property
    def odd(self) -> bool:
        return self.page_no() % 2 == 1

    def left(self) -> float:
        return M_INNER if self.odd else M_OUTER

    def measure(self, style: Style, s: str) -> float:
        if not s:
            return 0.0
        self.apply(style)
        w = self.get_string_width(s)
        if style.tracking and len(s) > 1:
            w += style.tracking * (len(s) - 1)
        return w

    def put(self, style: Style, x: float, baseline: float, s: str) -> None:
        if not s:
            return
        self.apply(style)
        if style.tracking:
            cx = x
            for ch in s:
                self.text(cx, baseline, ch)
                cx += self.get_string_width(ch) + style.tracking
        else:
            self.text(x, baseline, s)

    def put_center(self, style: Style, baseline: float, s: str, width: float = TEXT_W,
                   x0: Optional[float] = None) -> None:
        x0 = self.left() if x0 is None else x0
        w = self.measure(style, s)
        self.put(style, x0 + (width - w) / 2, baseline, s)

    def hairline(self, y: float, width: float, color=RULE_GREY, x0: Optional[float] = None) -> None:
        self.set_draw_color(*color)
        self.set_line_width(0.18)
        x = (self.left() + (TEXT_W - width) / 2) if x0 is None else x0
        self.line(x, y, x + width, y)

    def ornament(self, y: float, gap: float = 8.4, size: float = 6.4) -> None:
        style = Style(size=size, tracking=0.3, color=INK_GREY)
        cx = self.left() + TEXT_W / 2 - gap
        for _ in range(3):
            w = self.measure(style, DIAMOND)
            self.put(style, cx - w / 2, y, DIAMOND)
            cx += gap

    # -- page furniture ----------------------------------------------------
    def folio_text(self) -> str:
        if self.roman_folio:
            return to_roman(self.page_no())
        return str(self.page_no() - self.folio_offset)

    def start_page(self, kind: str = "body") -> None:
        """kind: body | opener | part | front | blank"""
        self.add_page()
        if kind == "part" or kind == "blank":
            return
        if kind == "body":
            head = TITLE.upper() if not self.odd else self.running_title.upper()
            if head:
                self.put_center(Style(size=7.6, tracking=1.5, color=INK_GREY), HEAD_Y, head)
        self.put_center(Style(size=9.2), FOLIO_Y, self.folio_text())


def to_roman(n: int) -> str:
    vals = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
            (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


# ------------------------------------------------------------- inline parsing
RUN_RE = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|_[^_]+?_)", re.S)


def parse_runs(text: str, base: Style = BODY) -> List[Tuple[Style, str]]:
    runs: List[Tuple[Style, str]] = []
    for chunk in RUN_RE.split(text):
        if not chunk:
            continue
        if chunk.startswith("**") and chunk.endswith("**"):
            runs.append((base.with_(variant="B"), chunk[2:-2]))
        elif chunk.startswith("*") and chunk.endswith("*"):
            runs.append((base.with_(variant="I"), chunk[1:-1]))
        elif chunk.startswith("_") and chunk.endswith("_"):
            runs.append((base.with_(variant="I"), chunk[1:-1]))
        else:
            runs.append((base, chunk))
    return runs


@dataclass
class Word:
    fragments: List[Tuple[Style, str]]

    @property
    def text(self) -> str:
        return "".join(t for _, t in self.fragments)

    @property
    def style(self) -> Style:
        return self.fragments[0][0]


def words_of(runs: Sequence[Tuple[Style, str]]) -> List[Word]:
    words: List[Word] = []
    current: List[Tuple[Style, str]] = []
    for style, text in runs:
        buf = ""
        i = 0
        while i < len(text):
            if text.startswith("--", i):
                buf += EM
                i += 2
                continue
            ch = text[i]
            if ch.isspace():
                if buf:
                    current.append((style, buf))
                    buf = ""
                if current:
                    words.append(Word(current))
                    current = []
                i += 1
                continue
            buf += ch
            i += 1
        if buf:
            current.append((style, buf))
    if current:
        words.append(Word(current))
    return words


def word_width(book: Book, word: Word) -> float:
    return sum(book.measure(style, text) for style, text in word.fragments)


_HYPH = pyphen.Pyphen(lang="en_US")


def hyphen_split(book: Book, word: Word, avail: float) -> Optional[Tuple[Word, Word]]:
    if len(word.fragments) != 1:
        return None
    text = word.text
    if not text.isalpha() or not (7 <= len(text) <= 20):
        return None
    style = word.style
    best: Optional[int] = None
    for cut in _HYPH.positions(text):
        if cut < 4 or len(text) - cut < 3:
            continue
        if book.measure(style, text[:cut] + "-") <= avail:
            best = cut
    if best is None:
        return None
    return Word([(style, text[:best] + "-")]), Word([(style, text[best:])])


@dataclass
class Line:
    words: List[Word] = field(default_factory=list)
    last: bool = False


def compose(book: Book, runs: Sequence[Tuple[Style, str]], limits: List[float],
            default_limit: float) -> List[Line]:
    """Greedy line filling; limits[i] is the measure available to line i."""
    space = book.measure(BODY, " ")
    lines: List[Line] = []
    cur: List[Word] = []
    cur_w = 0.0
    idx = 0

    def limit() -> float:
        return limits[idx] if idx < len(limits) else default_limit

    queue = deque(words_of(runs))
    while queue:
        word = queue.popleft()
        w = word_width(book, word)
        gap = space if cur else 0.0
        if cur_w + gap + w <= limit() + 0.02:
            cur_w += gap + w
            cur.append(word)
            continue
        avail = limit() - cur_w - gap
        split = hyphen_split(book, word, avail) if cur else None
        if split:
            head, tail = split
            cur.append(head)
            lines.append(Line(cur))
            cur, cur_w = [], 0.0
            idx += 1
            queue.appendleft(tail)
            continue
        if cur:
            lines.append(Line(cur))
            cur, cur_w = [], 0.0
            idx += 1
            queue.appendleft(word)
            continue
        split = hyphen_split(book, word, limit())
        if split:
            head, tail = split
            lines.append(Line([head]))
            idx += 1
            queue.appendleft(tail)
            continue
        lines.append(Line([word]))
        idx += 1
    if cur:
        lines.append(Line(cur))
    if lines:
        lines[-1].last = True
    return lines


def draw_lines(book: Book, lines: Sequence[Line], x: float, y_top: float, limits: List[float],
               default_limit: float, justify: bool = True, color=BLACK) -> float:
    y = y_top
    space = book.measure(BODY, " ")
    for i, line in enumerate(lines):
        limit = limits[i] if i < len(limits) else default_limit
        baseline = y + LEADING * 0.72
        if line.words:
            natural = sum(word_width(book, w) for w in line.words) + space * (len(line.words) - 1)
            gaps = len(line.words) - 1
            extra = 0.0
            if justify and not line.last and gaps > 0 and natural < limit - 0.02:
                extra = (limit - natural) / gaps
            cx = x
            for w in line.words:
                for style, text in w.fragments:
                    book.put(style.with_(color=color), cx, baseline, text)
                    cx += book.measure(style, text)
                cx += space + extra
        y += LEADING
    return y


# ------------------------------------------------------------------ manuscript
@dataclass
class Block:
    kind: str                          # para | scene | quote | subhead
    text: str = ""


@dataclass
class Unit:
    key: str
    number: str
    title: str
    blocks: List[Block]
    words: int = 0
    kind: str = "chapter"


def parse_body(body: str) -> List[Block]:
    blocks: List[Block] = []
    for chunk in re.split(r"\n\s*\n", body):
        chunk = chunk.strip()
        if not chunk:
            continue
        if re.match(r"^(?:\*\s*){3,}$", chunk) or chunk in {"---", "***"}:
            blocks.append(Block("scene"))
            continue
        if chunk.startswith("### "):
            blocks.append(Block("subhead", chunk[4:].strip()))
            continue
        if chunk.startswith(">"):
            text = " ".join(l.lstrip(">").strip() for l in chunk.split("\n")).strip()
            blocks.append(Block("quote", text))
            continue
        text = " ".join(l.strip() for l in chunk.split("\n"))
        blocks.append(Block("para", text))
    return blocks


def load_units(directory: Path) -> List[Unit]:
    units: List[Unit] = []
    for path in sorted(directory.glob("*.md")):
        raw = path.read_text(encoding="utf-8").strip()
        lines = raw.split("\n")
        heading = next((l for l in lines if l.startswith("# ")), None)
        if heading is None:
            raise SystemExit(f"{path.name}: missing '# ' heading")
        label = heading[2:].strip()
        blocks = parse_body("\n".join(lines[lines.index(heading) + 1:]))
        words = sum(len(b.text.split()) for b in blocks if b.kind in ("para", "quote"))
        m = re.match(r"^Chapter\s+(\d+)\s*[:\u2014-]\s*(.+)$", label, re.I)
        if m:
            num = int(m.group(1))
            units.append(Unit(f"ch{num:02d}", str(num), m.group(2).strip(), blocks, words))
            continue
        m = re.match(r"^Epilogue\s*[:\u2014-]?\s*(.*)$", label, re.I)
        if m:
            units.append(Unit("epilogue", "", m.group(1).strip(), blocks, words, kind="epilogue"))
            continue
        units.append(Unit(path.stem, "", label, blocks, words, kind="other"))
    return units


# ------------------------------------------------------------------- structure
PARTS = [
    ("One", "The Beautiful Lie", [f"ch{i:02d}" for i in range(1, 9)]),
    ("Two", "The City of Ash", [f"ch{i:02d}" for i in range(9, 18)]),
    ("Three", "Tempest", [f"ch{i:02d}" for i in range(18, 26)]),
]

EPIGRAPH = [
    "In the bedroom of the enemy,",
    "intimacy is an instrument of war.",
]

FRONT_NOTE = [
    "This is a work of fiction. Names, characters, organisations, places and",
    "incidents are either the product of the author's imagination or are used",
    "fictitiously. Any resemblance to actual persons, living or dead, is",
    "coincidental. Historical events, institutions and formations are depicted",
    "in invented circumstances.",
    "",
    "Contains explicit sexual content, violence and depictions of persecution.",
    "Intended for adult readers.",
    "",
    "First edition",
]


# ---------------------------------------------------------------------- layout
class Layout:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.y = M_TOP

    # -- page helpers ------------------------------------------------------
    def blank_verso(self) -> None:
        """Ensure the next page created is a recto (odd folio)."""
        if self.book.page_no() % 2 == 1:
            self.book.start_page("blank")

    def break_to(self, top: Optional[float] = None) -> None:
        self.book.start_page("body")
        self.y = M_TOP if top is None else top

    def need(self, height: float) -> None:
        if self.y + height > BOTTOM:
            self.break_to()

    # -- content -----------------------------------------------------------
    def paragraph(self, text: str, indent: bool, drop: bool = False) -> None:
        book = self.book
        if drop:
            if self.y + LEADING * (DROPCAP_LINES + 1) > BOTTOM:
                self.break_to()
            lead, letter, rest = strip_first_letter(text)
            dc_size = cap_size(letter)
            dc_style = Style(size=dc_size)
            dc_w = book.measure(dc_style, letter)
            gap = dc_size * PT2MM * 0.10
            narrow = TEXT_W - (dc_w + gap)
            limits = [narrow] * DROPCAP_LINES
            lines = compose(book, parse_runs(lead + rest), limits + [TEXT_W], TEXT_W)
            baseline0 = self.y + LEADING * 0.72
            cap_top = baseline0 - BODY_SIZE * PT2MM * CAP_RATIO
            dc_baseline = cap_top + cap_ink_ratio(letter) * dc_size * PT2MM
            book.put(dc_style, book.left(), dc_baseline, letter)
            self.flow(lines, first_extra=dc_w + gap, first_k_limits=limits)
            return
        extra = INDENT if indent else 0.0
        lines = compose(book, parse_runs(text), [], TEXT_W - extra)
        self.flow(lines, first_extra=extra)

    def flow(self, lines: List[Line], first_extra: float = 0.0,
             first_k_limits: Optional[List[float]] = None, justify: bool = True,
             color=BLACK) -> None:
        """Place composed lines, breaking across pages. Only line 0 of the
        paragraph is indented; lines that fall to a new page are flush."""
        book = self.book
        space = book.measure(BODY, " ")
        idx = 0
        while idx < len(lines):
            capacity = int((BOTTOM - self.y) // LEADING + 1e-9)
            if capacity < 1 or (capacity < 2 and len(lines) - idx > 2):
                self.break_to()
                continue
            take = max(1, min(capacity, len(lines) - idx))
            if len(lines) - idx - take == 1 and take >= 2:
                take -= 1
            for j in range(take):
                gi = idx + j
                line = lines[gi]
                in_dropcap = bool(first_k_limits) and gi < len(first_k_limits)
                if gi == 0 or in_dropcap:
                    extra = first_extra
                else:
                    extra = 0.0
                if in_dropcap:
                    limit = first_k_limits[gi]
                else:
                    limit = TEXT_W - extra
                baseline = self.y + LEADING * 0.72
                is_final = gi == len(lines) - 1
                self.draw_line(line, book.left() + extra, baseline, limit,
                               justify and not is_final, space, color)
                self.y += LEADING
            idx += take
            if idx < len(lines):
                self.break_to()

    def draw_line(self, line: Line, x: float, baseline: float, limit: float,
                  justify: bool, space: float, color=BLACK) -> None:
        book = self.book
        if not line.words:
            return
        natural = sum(word_width(book, w) for w in line.words) + space * (len(line.words) - 1)
        gaps = len(line.words) - 1
        extra = (limit - natural) / gaps if (justify and gaps > 0 and natural < limit - 0.02) else 0.0
        cx = x
        for w in line.words:
            for style, text in w.fragments:
                book.put(style.with_(color=color), cx, baseline, text)
                cx += book.measure(style, text)
            cx += space + extra

    def scene_break(self) -> None:
        book = self.book
        if self.y + LEADING * 3 > BOTTOM:
            self.break_to()
        self.y += LEADING * 1.05
        book.ornament(self.y)
        self.y += LEADING * 1.35

    def quote_block(self, text: str) -> None:
        book = self.book
        inset = 7.5
        qw = TEXT_W - inset * 2
        lines = compose(book, parse_runs(text, Style(variant="I", size=QUOTE_SIZE)), [], qw)
        height = len(lines) * QUOTE_LEADING + LEADING * 1.0
        if self.y + height > BOTTOM:
            self.break_to()
        self.y += LEADING * 0.45
        book.set_draw_color(*RULE_GREY)
        book.set_line_width(0.3)
        rule_top = self.y - 1.4
        book.line(book.left() + 1.7, rule_top, book.left() + 1.7,
                  rule_top + len(lines) * QUOTE_LEADING)
        space = book.measure(BODY, " ")
        for line in lines:
            baseline = self.y + QUOTE_LEADING * 0.74
            self.draw_line(line, book.left() + inset, baseline, qw, False, space)
            self.y += QUOTE_LEADING
        self.y += LEADING * 0.5

    def subhead(self, text: str) -> None:
        book = self.book
        self.need(LEADING * 3)
        self.y += LEADING * 0.7
        book.put_center(Style(size=11.2, tracking=1.4), self.y, text.upper())
        self.y += LEADING * 1.25

    def chapter_opener(self, unit: Unit, epilogue: bool = False, note: bool = False) -> None:
        book = self.book
        if note:
            book.put_center(Style(size=9.2, tracking=3.0, color=INK_GREY), OPENER_TOP - 8.5,
                            "APPENDIX")
            book.put_center(Style(size=18), OPENER_TOP + 6, unit.title)
            book.hairline(OPENER_TOP + 16, 30)
            self.y = OPENER_TOP + 32
            return
        label = "EPILOGUE" if epilogue else "CHAPTER " + PAGE_WORDS[int(unit.number)].upper()
        book.put_center(Style(size=9.2, tracking=3.0, color=INK_GREY), OPENER_TOP, label)
        if unit.title:
            book.put_center(Style(size=CHAP_TITLE_SIZE), OPENER_TOP + 14.5, unit.title)
            book.ornament(OPENER_TOP + 26.5)
        else:
            book.ornament(OPENER_TOP + 14.5)
        self.y = OPENER_TEXT_TOP


_CAP_INK_CACHE: Dict[str, float] = {}


def cap_ink_ratio(letter: str) -> float:
    """Height of a capital's ink as a fraction of the em, read from the font."""
    if letter in _CAP_INK_CACHE:
        return _CAP_INK_CACHE[letter]
    ratio = CAP_RATIO
    try:
        from fontTools.ttLib import TTFont

        face = TTFont(str(FONT_DIR / "EBGaramond-Regular.ttf"))
        upm = face["head"].unitsPerEm
        cmap = face.getBestCmap()
        code = ord(letter)
        if code in cmap:
            ratio = face["glyf"][cmap[code]].yMax / upm
    except Exception:
        pass
    _CAP_INK_CACHE[letter] = ratio
    return ratio


def cap_size(letter: str) -> float:
    """Type size (pt) so the capital's ink spans DROPCAP_LINES lines exactly."""
    height = (DROPCAP_LINES - 1) * LEADING + BODY_SIZE * PT2MM * CAP_RATIO
    return height / (cap_ink_ratio(letter) * PT2MM)


def strip_first_letter(text: str) -> Tuple[str, str, str]:
    m = re.match(r"^([\u201c\u2018\"'(]*)([A-Za-z\u00c0-\u024f])(.*)$", text)
    if not m:
        return "", " ", text
    return m.group(1), m.group(2), m.group(3)


# ------------------------------------------------------------------ front/back
def draw_front_matter(layout: Layout) -> None:
    book = layout.book
    # i - half title
    book.start_page("blank")
    book.put_center(Style(size=13.5, tracking=3.4), 94, TITLE.upper())
    # ii - blank
    book.start_page("blank")
    # iii - title page
    book.start_page("blank")
    book.put_center(Style(size=26), 66, TITLE)
    book.put_center(Style(size=10.6, tracking=2.6, color=INK_GREY), 86, "A NOVEL")
    book.put_center(Style(size=8.8, tracking=1.6, color=INK_GREY), 168, "PARIS   \u00b7   WARSAW")
    book.put_center(Style(size=8.8, tracking=1.6, color=INK_GREY), 174, "1943")
    # iv - copyright
    book.start_page("blank")
    y = 158
    for line in FRONT_NOTE:
        if line:
            book.put_center(Style(size=8.1, color=INK_GREY), y, line)
        y += 4.7
    # v - blank (verso of the epigraph spread)
    layout.blank_verso()
    # epigraph
    book.start_page("blank")
    for i, line in enumerate(EPIGRAPH):
        book.put_center(Style(variant="I", size=11.4), 99 + i * 7.8, line)
    # contents (reserved now, drawn by build())
    layout.blank_verso()


CONTENTS_FIRST_Y = 56.0
CONTENTS_CHAPTER_ROW = 8.4
CONTENTS_PART_LEAD = 4.6
CONTENTS_PART_ROW = 6.4


def contents_rows(units: List[Unit]) -> List[Tuple[str, str, str]]:
    by_key = {u.key: u for u in units}
    rows: List[Tuple[str, str, str]] = []
    for part_num, part_title, keys in PARTS:
        rows.append(("part", f"Part {part_num}\u2002\u00b7\u2002{part_title}", f"part:{part_num}"))
        for key in keys:
            u = by_key.get(key)
            if u:
                rows.append(("chapter", f"{PAGE_WORDS[int(u.number)]}|{u.title}", key))
    for u in units:
        if u.kind == "epilogue":
            rows.append(("chapter", f"Epilogue|{u.title}", u.key))
    rows.append(("chapter", "|A Note on the History", "note"))
    return rows


def paginate_contents(rows: List[Tuple[str, str, str]]) -> List[List[Tuple[str, str, str]]]:
    pages: List[List[Tuple[str, str, str]]] = []
    page: List[Tuple[str, str, str]] = []
    y = CONTENTS_FIRST_Y
    for row in rows:
        step = CONTENTS_CHAPTER_ROW if row[0] == "chapter" else CONTENTS_PART_LEAD + CONTENTS_PART_ROW + 2.2
        if y + step > BOTTOM - 6 and page:
            pages.append(page)
            page = []
            y = CONTENTS_FIRST_Y
        y += step
        page.append(row)
    if page:
        pages.append(page)
    return pages or [[]]


def draw_contents_page(book: Book, rows: List[Tuple[str, str, str]], page_no_of,
                       first: bool) -> None:
    book.start_page("blank")
    if first:
        book.put_center(Style(size=12.4, tracking=3.5), 34, "CONTENTS")
        book.hairline(41.5, 20)
    y = CONTENTS_FIRST_Y
    num_col = 0.0
    for kind, label, _key in rows:
        if kind != "part":
            num_col = max(num_col, book.measure(Style(size=10.2), label.split("|", 1)[0]))
    for kind, label, key in rows:
        if kind == "part":
            y += CONTENTS_PART_LEAD
            book.put_center(Style(size=8.0, tracking=1.8, color=INK_GREY), y, label.upper())
            y += CONTENTS_PART_ROW + 2.2
        else:
            num, title = label.split("|", 1)
            base_x = book.left() + 5.0
            num_style = Style(size=10.2)
            if num:
                book.put(num_style, base_x, y, num)
                num_w = book.measure(num_style, num)
            else:
                num_w = 0.0
            title_x = base_x + max(18.0, num_col + 3.5)
            book.put(Style(variant="I", size=10.2), title_x, y, title)
            tw = book.measure(Style(variant="I", size=10.2), title)
            p = page_no_of(key) or ""
            pw = book.measure(num_style, p)
            dot_start = title_x + tw + 3.0
            dot_end = book.left() + TEXT_W - pw - 3.0
            dot_style = Style(size=10.2, color=RULE_GREY)
            cx = dot_start
            while cx < dot_end:
                book.put(dot_style, cx, y, ".")
                cx += 2.7
            book.put(Style(size=10.2), book.left() + TEXT_W - pw, y, p)
            y += CONTENTS_CHAPTER_ROW
    return y


# ------------------------------------------------------------------------- build
def render_unit(layout: Layout, unit: Unit) -> None:
    first = True          # a paragraph opening a scene sits flush, unindented
    opened = False        # has the chapter's drop cap been spent?
    for block in unit.blocks:
        if block.kind == "scene":
            layout.scene_break()
            first = True
        elif block.kind == "quote":
            layout.quote_block(block.text)
            first = False
        elif block.kind == "subhead":
            layout.subhead(block.text)
            first = True
        else:
            drop = (not opened) and unit.kind == "chapter"
            layout.paragraph(block.text, indent=not first, drop=drop)
            opened = True
            first = False


def build(units: List[Unit], page_map: Dict[str, int]) -> Tuple[Book, Dict[str, int]]:
    """One full pass. `page_map` supplies folios for the contents pass."""
    book = Book()
    book.set_title("The Enemy's Shadow")
    book.set_author("Novel OS")
    book.set_subject("A novel of occupied Paris and Warsaw, 1943-1944")
    book.set_creator("build_pdf.py")
    layout = Layout(book)
    found: Dict[str, int] = {}
    by_key = {u.key: u for u in units}

    def folio() -> int:
        return book.page_no() - book.folio_offset

    def page_no_of(key: str) -> str:
        return str(page_map.get(key, "")) if page_map else ""

    draw_front_matter(layout)
    for i, page_rows in enumerate(paginate_contents(contents_rows(units))):
        draw_contents_page(book, page_rows, page_no_of, first=(i == 0))

    first_opener = True
    for part_num, part_title, keys in PARTS:
        layout.blank_verso()
        book.start_page("part")
        found[f"part:{part_num}"] = folio()
        book.put_center(Style(size=10.2, tracking=4.2, color=INK_GREY), 96,
                        "PART " + part_num.upper())
        book.put_center(Style(variant="I", size=19.5), 110, part_title)
        book.hairline(121, 32)
        for key in keys:
            unit = by_key.get(key)
            if unit is None:
                continue
            layout.blank_verso()
            if first_opener:
                book.folio_offset = book.page_no()      # the next page becomes folio 1
                book.roman_folio = False
                first_opener = False
            book.start_page("opener")
            found[unit.key] = folio()
            book.running_title = unit.title
            layout.chapter_opener(unit)
            render_unit(layout, unit)

    for unit in units:
        if unit.kind != "epilogue":
            continue
        layout.blank_verso()
        book.start_page("opener")
        found[unit.key] = folio()
        book.running_title = unit.title
        layout.chapter_opener(unit, epilogue=True)
        render_unit(layout, unit)

    note_title = "A Note on the History"
    layout.blank_verso()
    book.start_page("opener")
    found["note"] = folio()
    book.running_title = note_title
    layout.chapter_opener(Unit("note", "", note_title, []), note=True)
    for para in HISTORICAL_NOTE:
        if not para:
            layout.y += LEADING * 0.35
            continue
        lines = compose(book, parse_runs(para, Style(size=9.9)), [], TEXT_W)
        layout.flow(lines)
        layout.y += 5.2
    return book, found


HISTORICAL_NOTE: List[str] = [
    "The Warsaw Rising began at five o'clock in the afternoon of the first of August 1944 and ended "
    "with an act of capitulation signed on the evening of the second of October, sixty-three days later. "
    "It was fought by some forty to fifty thousand soldiers of the Polish Home Army and by a civilian "
    "population of about a million people, inside a city the German administration had already intended "
    "to hold as a fortress. The arms of the insurgents, for the whole of the first week, were rifles "
    "left over from 1939, a few machine guns, bottles of petrol and paving stones.",

    "The rising was ordered by the Polish underground command in the expectation of a few days of "
    "fighting before the Red Army crossed the Vistula. The Red Army reached the river, took the right-bank "
    "district of Praga in the middle of September, and did not cross in support of the rising; the reasons "
    "for that decision remain one of the bitter arguments of Polish history. The insurgents in the centre of "
    "the city held until October.",

    "Between the fifth and the seventh of August 1944 the police and SS formations of the district carried "
    "out, in the western quarter of Wola, the mass murder of the civilian population of that quarter; the "
    "figure generally accepted is between forty and fifty thousand people killed in four days, in streets, "
    "courtyards and hospitals. Before the rising ended, between one hundred and fifty and two hundred "
    "thousand civilians of Warsaw had been killed, most of them by execution, bombardment and fire. The "
    "German high command in the city refused to sign the order that made the killing a matter of policy; "
    "the record of that refusal survives in the files, and it did not alter anything.",

    "In early October some five hundred thousand surviving inhabitants were driven out of the city. Many "
    "passed through the transit camp at Pruszków, where they were sorted into transports for the Reich or "
    "for the province of the Generalgouvernement. The wounded, the very old and the children were moved in "
    "open trucks in October weather. From October until January the German army and police formations "
    "destroyed the city systematically, street by street and building by building; the destruction was "
    "carried out as an operation of engineering with a technique of its own. Roughly eighty-five per cent "
    "of the built fabric of Warsaw was gone when the Red Army entered the ruins on the seventeenth of "
    "January 1945.",

    "The Pawiak prison on the Dzielna was emptied before and during the rising; its prisoners were shot in "
    "the ruins of the ghetto, deported, or left to the transports of the last week of July. The Krasiński "
    "Library, the city archive and the manuscript collections of the Polish nation were burned in the "
    "last days of August 1944. The headquarters of the Sicherheitsdienst were at 25 aleja Szucha, and it "
    "was understood in Warsaw that a person taken in through that gate did not come out again.",

    "This book is a novel, and the people in it are invented. Marion Herschlag and Krystyna "
    "Stankiewiczówna, Friedrich von Reuth, Phillip Brandt, Werner Kroll, Dietrich Ehlers, René Tissier, "
    "the Zaleskis, the Countess Ostrowska, Colonel Wilczek and the household on the Bagatela are all "
    "fictional, and no invented character in these pages is meant for a person who lived. The file named "
    "Fall Wotan, its map of the Vistula line and its table of rolling stock are fictional; the code name "
    "Wotan was, however, a genuine designation used by the German army for a defensive position in the "
    "east, and the problem of holding a line along a great river against an army that had already reached "
    "it is the problem that the German staff in Warsaw was in fact arguing about in July 1944.",

    "The furniture of the place is real. The Generalgouvernement, the Standortkommandantur, the "
    "Kennkarte and the Ausweis, the prohibition notices in German over the tram-car compartments, the "
    "curfew, the identity round-ups in the streets, the black-market stalls, the placards of the executed, "
    "the walled-off ruins of the ghetto, the bridges over the Vistula and the forest of Kampinos are all "
    "as they appear here. The Minox subminiature camera existed and was used by intelligence services "
    "before and during the war. The wax impressions, the patient social work of a kept woman in an "
    "occupied capital, and the household arrangement of a senior officer's mistress are the materials of "
    "the period; the particular arrangement in this novel is not.",

    "German, Polish and French words are left as the characters would have spoken them. Place names keep "
    "their Polish spelling. Three dates in the narrative have been moved by a day or two to suit the "
    "story, and the composition of the German intelligence offices in Warsaw has been simplified: in "
    "1944 an intelligence service in an occupied district was a smaller and duller thing than the "
    "headquarters described here, and its officers were, for the most part, not men standing in the "
    "middle of a marble hall with their caps in their hands.",

    "Among the books that inform these pages, and which a reader who wishes to go further might begin "
    "with, are Norman Davies's Rising '44, Miron Białoszewski's A Memoir of the Warsaw Uprising, written "
    "by a man who was there and who remembered the cellar, the water, the coal and the fear, and "
    "Władysław Bartoszewski's record of the occupation of the city day by day. The dead of Warsaw "
    "were not an argument, a symbol or a lesson; they were people in streets on a Tuesday afternoon, and "
    "the invented women and men of a novel are one way of measuring the size of them.",

    "",
    "The rest is the reader's.",
]


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manuscript", default=str(CHAPTER_DIR))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--check", action="store_true", help="report chapters outside 4,900-6,200 words")
    args = ap.parse_args()

    units = load_units(Path(args.manuscript))
    total = sum(u.words for u in units)
    print(f"{len(units)} units \u00b7 {total:,} words")
    for u in units:
        flag = ""
        if args.check and u.kind in ("chapter", "epilogue"):
            if not (4900 <= u.words <= 6200):
                flag = "  <-- out of range"
        print(f"  {u.key:10s} {u.words:6,d}  {u.title}{flag}")
    if args.check:
        return

    page_map: Dict[str, int] = {}
    prev_signature = None
    book = None
    for attempt in range(4):
        book, found = build(units, page_map)
        signature = (book.page_no(), tuple(sorted(found.items())))
        page_map = found
        if signature == prev_signature:
            break
        prev_signature = signature
    assert book is not None
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    book.output(str(out))
    print(f"wrote {out} \u00b7 {book.page_no()} pages")


if __name__ == "__main__":
    main()
