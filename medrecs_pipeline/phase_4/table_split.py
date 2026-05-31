from __future__ import annotations

from .token_utils import count_tokens


def parse_markdown_table_rows(text: str) -> list[str]:
    """Return contiguous markdown table row lines (starting with '|')."""
    rows: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            rows.append(stripped)
    return rows


def pipe_count(row: str) -> int:
    return row.count("|")


def is_separator_row(row: str) -> bool:
    compact = row.replace(" ", "")
    if not compact.startswith("|") or not compact.endswith("|"):
        return False
    inner = compact.strip("|")
    return bool(inner) and "-" in inner and all(ch in "|-:" for ch in inner)


def split_table_by_rows(text: str, *, max_tokens: int) -> list[str]:
    """
    Split an oversized markdown table into sub-tables with repeated header rows.
    Returns [text] unchanged when under budget or not parseable as a table.
    """
    if max_tokens <= 0 or count_tokens(text) <= max_tokens:
        return [text] if (text or "").strip() else []

    rows = parse_markdown_table_rows(text)
    if len(rows) < 2:
        return [text]

    header_rows: list[str] = [rows[0]]
    data_start = 1
    if len(rows) > 1 and is_separator_row(rows[1]):
        header_rows.append(rows[1])
        data_start = 2

    data_rows = rows[data_start:]
    if not data_rows:
        return [text]

    expected_pipes = pipe_count(header_rows[0])
    valid_data = [
        r
        for r in data_rows
        if pipe_count(r) == expected_pipes and not is_separator_row(r)
    ]
    if not valid_data:
        return [text]

    prefix_lines = [
        ln
        for ln in text.splitlines()
        if not ln.strip().startswith("|")
    ]
    prefix = "\n".join(prefix_lines).strip()
    prefix_block = f"{prefix}\n\n" if prefix else ""

    header_block = "\n".join(header_rows)
    header_tokens = count_tokens(f"{prefix_block}{header_block}")
    if header_tokens >= max_tokens:
        return [text]

    chunks: list[str] = []
    current_rows: list[str] = []

    def flush() -> None:
        if not current_rows:
            return
        body = "\n".join(current_rows)
        chunk = f"{prefix_block}{header_block}\n{body}".strip()
        chunks.append(chunk)
        current_rows.clear()

    for row in valid_data:
        candidate_rows = current_rows + [row]
        candidate_body = "\n".join(candidate_rows)
        candidate = f"{prefix_block}{header_block}\n{candidate_body}".strip()
        if current_rows and count_tokens(candidate) > max_tokens:
            flush()
        current_rows.append(row)
    flush()

    return chunks if chunks else [text]


def validate_table_rows(text: str) -> bool:
    """True when each markdown table segment has consistent pipe counts per row."""
    for segment in (text or "").split("\n\n"):
        rows = parse_markdown_table_rows(segment)
        if not rows:
            continue
        expected = pipe_count(rows[0])
        for row in rows[1:]:
            if is_separator_row(row):
                continue
            pc = pipe_count(row)
            # Allow a missing trailing empty cell (common in EMR extractions).
            if not (expected - 1 <= pc <= expected):
                return False
    return True
