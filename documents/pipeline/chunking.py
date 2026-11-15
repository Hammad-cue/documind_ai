"""
Step 2: structure-aware chunking.

Instead of cutting text every N characters (which splits clauses in half), we detect
headings (PART / CHAPTER / ARTICLE / Section 12 / "12." / "12.3" / ALL-CAPS titles),
keep a stack of the current section path, and emit one chunk per section. Long
sections are split on paragraph/sentence boundaries. Every chunk remembers the pages
it spans, so answers can cite and open the exact page.
"""
import re
from dataclasses import dataclass

MAX_CHARS = 1500
MIN_CHARS = 200
OVERLAP = 150

ROMAN = r'[IVXLCDM]+'
HEADING_RULES = [
    # (level, regex)
    (1, re.compile(rf'^(PART|CHAPTER|ARTICLE|SCHEDULE|ANNEX(URE)?|APPENDIX)\s+({ROMAN}|\d+|[A-Z])\b.{{0,100}}$', re.I)),
    (2, re.compile(r'^(SECTION|Section|Sec\.|Clause|CLAUSE)\s+\d+[A-Za-z]?\b.{0,120}$')),
    (3, re.compile(r'^\d+\.\d+(\.\d+)*\.?\s+\S.{0,120}$')),
    (2, re.compile(r'^\d{1,3}[.)]\s+[A-Z][^.]{2,100}[.:\-—]?$')),
]


@dataclass
class ChunkData:
    sequence: int
    section_path: str
    heading: str
    text: str
    page_start: int
    page_end: int


def _is_caps_title(line):
    letters = [c for c in line if c.isalpha()]
    return 4 <= len(letters) and len(line) <= 80 and sum(c.isupper() for c in letters) / len(letters) > 0.85 \
        and not line.endswith(',')


def heading_level(line):
    line = line.strip()
    if not line or len(line) > 140:
        return None
    for level, rx in HEADING_RULES:
        if rx.match(line):
            return level
    if _is_caps_title(line):
        return 2
    return None


def _split_long(text, max_chars=MAX_CHARS, overlap=OVERLAP):
    """Split on paragraph, then sentence boundaries."""
    if len(text) <= max_chars:
        return [text]
    parts = re.split(r'\n\s*\n', text)
    if max(len(p) for p in parts) > max_chars:
        parts = re.split(r'(?<=[.;:])\s+', text)
    out, buf = [], ''
    for p in parts:
        if len(buf) + len(p) + 1 > max_chars and buf:
            out.append(buf.strip())
            buf = buf[-overlap:] + ' ' + p
        else:
            buf = f'{buf}\n{p}' if buf else p
    if buf.strip():
        out.append(buf.strip())
    final = []
    for piece in out:  # hard cut any remaining giant sentence
        while len(piece) > max_chars * 1.5:
            final.append(piece[:max_chars])
            piece = piece[max_chars - overlap:]
        final.append(piece)
    return final


def chunk_pages(pages):
    """pages: list of (page_number, text). Returns list[ChunkData]."""
    sections = []          # (path, heading, [(page, line)])
    stack = []             # [(level, heading)]
    current = {'path': '', 'heading': '', 'lines': []}

    def flush():
        if any(l.strip() for _, l in current['lines']):
            sections.append(dict(current))

    for page_no, text in pages:
        for raw in (text or '').split('\n'):
            line = raw.rstrip()
            level = heading_level(line)
            if level is not None:
                flush()
                stack[:] = [s for s in stack if s[0] < level]
                stack.append((level, line.strip()[:120]))
                current = {'path': ' > '.join(h for _, h in stack), 'heading': line.strip()[:300],
                           'lines': [(page_no, line)]}
            else:
                current['lines'].append((page_no, line))
    flush()

    # merge tiny sections into the next one (e.g. a heading followed by a sub-heading)
    merged = []
    for s in sections:
        body = '\n'.join(l for _, l in s['lines']).strip()
        if merged and len('\n'.join(l for _, l in merged[-1]['lines']).strip()) < MIN_CHARS:
            merged[-1]['lines'].extend(s['lines'])
            merged[-1]['path'] = s['path'] or merged[-1]['path']
            continue
        if body:
            merged.append({'path': s['path'], 'heading': s['heading'], 'lines': list(s['lines'])})

    chunks, seq = [], 0
    for s in merged:
        # character offset -> page map for this section
        text, spans, pos = '', [], 0
        for page_no, line in s['lines']:
            spans.append((pos, page_no))
            text += line + '\n'
            pos = len(text)

        def page_at(offset):
            page = spans[0][1]
            for start, p in spans:
                if start > offset:
                    break
                page = p
            return page

        cursor = 0
        for piece in _split_long(text.strip()):
            start = text.find(piece[:80], cursor)
            if start < 0:
                start = cursor
            end = start + len(piece) - 1
            cursor = max(cursor, start + 1)
            seq += 1
            p_start, p_end = page_at(start), page_at(end)
            chunks.append(ChunkData(seq, s['path'], s['heading'], piece, p_start, max(p_start, p_end)))
    return chunks
