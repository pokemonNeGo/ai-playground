from __future__ import annotations

import re
from dataclasses import dataclass

WIKI_HEADING_RE = re.compile(r'^\s*(={2,6})\s*(.+?)\s*\1\s*$')
MARKDOWN_HEADING_RE = re.compile(r'^\s*(#{1,6})\s+(.+?)\s*$')
NUMBERED_HEADING_RE = re.compile(
    r'^\s*(Глава|Раздел|Часть|Статья|Параграф)\s+'
    r'([0-9IVXLC]+|[A-ZА-ЯЁ][^\.\!\?…]{0,80})\s*$',
    re.IGNORECASE,
)
SENTENCE_RE = re.compile(r'(?s)[^.!?…]+[.!?…]*(?:\s+|$)')


@dataclass
class _Segment:
    text: str
    start: int
    end: int
    heading_path: str


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    """
    Убирает пробельные символы по краям диапазона [start, end).
    Возвращает скорректированные границы.
    """
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _detect_heading(line: str) -> tuple[int, str] | None:
    """
    Пытается распознать заголовок.

    Возвращает:
        (уровень, текст заголовка)
    или None.

    Важно:
    - если парсер ранее уже удалил wiki-заголовки, этот детектор может
      находить только явно выраженные заголовки;
    - если заголовки не найдены, чанкование работает по абзацам/предложениям.
    """
    line = line.rstrip('\n')

    m = WIKI_HEADING_RE.match(line)
    if m:
        return len(m.group(1)), m.group(2).strip()

    m = MARKDOWN_HEADING_RE.match(line)
    if m:
        return len(m.group(1)), m.group(2).strip()

    stripped = line.strip()

    if 3 <= len(stripped) <= 80 and not stripped.endswith(('.', '!', '?', '…', ':')):
        m = NUMBERED_HEADING_RE.match(stripped)
        if m:
            return 2, stripped

        # Очень консервативная эвристика: строка из верхнего регистра,
        # например "ИСТОРИЯ", "ССЫЛКИ", "ЛИТЕРАТУРА".
        if stripped.isupper() and any(c.isalpha() for c in stripped):
            return 1, stripped

    return None


def _lines_with_positions(text: str) -> list[tuple[int, str]]:
    """
    Возвращает список (позиция начала строки, строка).
    """
    lines = []
    start = 0
    for line in text.split('\n'):
        lines.append((start, line))
        start += len(line) + 1
    return lines


def _build_segments(text: str) -> list[_Segment]:
    """
    Разбивает текст на смысловые сегменты:
    - абзацы;
    - с учётом заголовков, если они распознаются.
    """
    segments: list[_Segment] = []
    stack: list[tuple[int, str]] = []
    para_lines: list[tuple[int, str]] = []

    def flush_paragraph() -> None:
        nonlocal para_lines

        if not para_lines:
            return

        start = para_lines[0][0]
        last_start, last_line = para_lines[-1]
        end = last_start + len(last_line)

        start, end = _trim_span(text, start, end)

        if start < end:
            heading_path = ' > '.join(title for _, title in stack)
            segments.append(_Segment(text[start:end], start, end, heading_path))

        para_lines = []

    for pos, line in _lines_with_positions(text):
        if not line.strip():
            flush_paragraph()
            continue

        heading = _detect_heading(line)
        if heading:
            flush_paragraph()
            level, title = heading

            while stack and stack[-1][0] >= level:
                stack.pop()

            stack.append((level, title))
            continue

        para_lines.append((pos, line))

    flush_paragraph()
    return segments


def _split_piece_by_size(
    piece_text: str,
    base_start: int,
    max_chars: int,
    heading_path: str,
) -> list[_Segment]:
    """
    Режет слишком длинный кусок по символам, стараясь резать по пробелам.
    """
    out: list[_Segment] = []
    n = len(piece_text)
    cur = 0

    while cur < n:
        end = min(cur + max_chars, n)

        if end < n:
            space = piece_text.rfind(' ', cur, end)
            if space > cur + max_chars // 2:
                end = space + 1

        part = piece_text[cur:end]

        if part.strip():
            out.append(_Segment(part, base_start + cur, base_start + end, heading_path))

        cur = end

        # Пропускаем пробелы в начале следующего куска.
        while cur < n and piece_text[cur].isspace():
            cur += 1

    return out


def _split_long_segment(seg: _Segment, max_chars: int) -> list[_Segment]:
    """
    Если сегмент длиннее max_chars:
    1. пробуем резать по предложениям;
    2. если предложение всё равно длинное — режем по пробелам/символам.
    """
    if len(seg.text) <= max_chars:
        return [seg]

    sentence_spans = []

    for m in SENTENCE_RE.finditer(seg.text):
        s, e = m.span()
        if e > s:
            sentence_spans.append((s, e))

    if not sentence_spans:
        sentence_spans = [(0, len(seg.text))]

    pieces: list[tuple[int, int]] = []

    cur_s, cur_e = sentence_spans[0]

    for s, e in sentence_spans[1:]:
        if e - cur_s <= max_chars:
            cur_e = e
        else:
            pieces.append((cur_s, cur_e))
            cur_s, cur_e = s, e

    pieces.append((cur_s, cur_e))

    out: list[_Segment] = []

    for s, e in pieces:
        piece_text = seg.text[s:e]

        if not piece_text.strip():
            continue

        if len(piece_text) <= max_chars:
            out.append(
                _Segment(
                    piece_text,
                    seg.start + s,
                    seg.start + e,
                    seg.heading_path,
                )
            )
        else:
            out.extend(
                _split_piece_by_size(
                    piece_text,
                    seg.start + s,
                    max_chars,
                    seg.heading_path,
                )
            )

    return out


def chunk_text_structural(text: str, max_chars: int = 500) -> list[dict]:
    """
    Структурное чанкование текста.

    Возвращает список чанков:
    [
        {
            "heading_path": "...",
            "text": "...",
            "start_char": int,
            "end_char": int,
        },
        ...
    ]
    """
    if not text or not text.strip():
        return []

    segments = _build_segments(text)

    expanded: list[_Segment] = []
    for seg in segments:
        expanded.extend(_split_long_segment(seg, max_chars))

    chunks: list[dict] = []

    current_start: int | None = None
    current_end: int | None = None
    current_heading: str | None = None

    def flush() -> None:
        nonlocal current_start, current_end, current_heading

        if current_start is None or current_end is None:
            current_start = None
            current_end = None
            current_heading = None
            return

        start, end = _trim_span(text, current_start, current_end)

        if start < end:
            chunk_text = text[start:end]
            chunks.append(
                {
                    'heading_path': current_heading or '',
                    'text': chunk_text,
                    'start_char': start,
                    'end_char': end,
                }
            )

        current_start = None
        current_end = None
        current_heading = None

    for seg in expanded:
        if not seg.text.strip():
            continue

        if current_start is None:
            current_start = seg.start
            current_end = seg.end
            current_heading = seg.heading_path
            continue

        same_heading = current_heading == seg.heading_path
        fits = seg.end - current_start <= max_chars

        if same_heading and fits:
            current_end = seg.end
        else:
            flush()
            current_start = seg.start
            current_end = seg.end
            current_heading = seg.heading_path

    flush()

    return chunks