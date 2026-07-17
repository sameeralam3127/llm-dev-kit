import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    title: str
    text: str


def markdown_title(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    return match.group(1).strip() if match else fallback.rsplit("/", maxsplit=1)[-1]


def chunk_markdown(
    markdown: str,
    *,
    path: str,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")

    title = markdown_title(markdown, fallback=path)
    normalized = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    chunks: list[DocumentChunk] = []
    start = 0
    index = 0
    while start < len(normalized):
        text = normalized[start : start + chunk_size].strip()
        if text:
            chunks.append(
                DocumentChunk(chunk_id=f"{path}:{index}", title=title, text=text)
            )
            index += 1
        start += chunk_size - overlap
    return chunks
