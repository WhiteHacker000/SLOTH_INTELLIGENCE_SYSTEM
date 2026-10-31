import re

CODE_FENCE = re.compile(r"(```.*?```)", re.DOTALL)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
EXTRA_BLANK_LINES = re.compile(r"\n{3,}")

MAX_CHUNK_CHARS = 1200
OVERLAP_CHARS = 150


def clean_markdown(text: str) -> str:
    """Remove template comments and images, leaving code blocks untouched."""
    parts = CODE_FENCE.split(text.replace("\r\n", "\n"))
    cleaned = [part if part.startswith("```") else _clean_prose(part) for part in parts]
    return "".join(cleaned).strip()


def split_into_chunks(
    text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS
) -> list[str]:
    """Split on paragraph breaks, keeping chunks under max_chars.

    A paragraph longer than max_chars is cut into overlapping windows so no
    text is lost at the boundary.
    """
    chunks: list[str] = []
    current = ""
    for paragraph in _paragraphs(text):
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_windows(paragraph, max_chars, overlap))
        elif len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def _clean_prose(text: str) -> str:
    text = HTML_COMMENT.sub("", text)
    text = IMAGE.sub("", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return EXTRA_BLANK_LINES.sub("\n\n", text)


def _paragraphs(text: str) -> list[str]:
    # Code blocks count as one paragraph even if they contain blank lines.
    paragraphs: list[str] = []
    for part in CODE_FENCE.split(text):
        if part.startswith("```"):
            paragraphs.append(part)
        else:
            paragraphs.extend(p.strip() for p in part.split("\n\n") if p.strip())
    return paragraphs


def _windows(text: str, size: int, overlap: int) -> list[str]:
    # Stop once the last window reaches the end, so no window is just overlap.
    last_start = max(len(text) - overlap, 1)
    return [
        text[start : start + size] for start in range(0, last_start, size - overlap)
    ]
