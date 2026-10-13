# The Enemy's Shadow

A historical novel. Three parts, 25 chapters and an epilogue. 26 units · 155,181 words.

## Read it

- **Typeset PDF (379 pp., A5-ish 152x229 mm):** [`the-enemys-shadow.pdf`](output/the-enemys-shadow.pdf)
- **Manuscript (Markdown, one file per unit):** [`manuscript/`](manuscript)

## Contents

**Part One (ch01-ch08)** — ch01 8,163w; ch02 5,098w; ch03 6,216w; ch04 6,298w; ch05 5,026w; ch06 6,024w; ch07 5,188w; ch08 5,592w

**Part Two (ch09-ch17)** — ch09 5,314w; ch10 6,113w; ch11 5,625w; ch12 5,357w; ch13 4,903w; ch14 5,599w; ch15 5,728w; ch16 5,055w; ch17 5,960w

**Part Three (ch18-ch25)** — ch18 5,540w; ch19 6,225w; ch20 5,740w; ch21 5,568w; ch22 7,471w; ch23 7,968w; ch24 6,243w; ch25 7,006w

Epilogue — 6,161 words, plus an appendix ("A Note on the History").

## Rebuilding the PDF

```bash
python3 -m pip install --break-system-packages fpdf2 pyphen fonttools
python3 tools/prepare_fonts.py     # one-off: fetch + subset EB Garamond into assets/fonts
python3 tools/build_pdf.py         # writes output/the-enemys-shadow.pdf
python3 tools/build_pdf.py --check # word counts per unit, flags drift
```

`tools/clean_prose.py` is a drafting aid kept with the project; see the tool's header for what it does.

The story bible (cast, timeline, chapter titles, continuity ledger) is in [`bible/story_bible.md`](bible/story_bible.md).
