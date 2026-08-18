from pypdf import PdfReader


def load_pdf(file) -> str:
    reader = PdfReader(file, strict=False)
    text = "\n".join(filter(None, (page.extract_text() for page in reader.pages)))

    if not text.strip():
        raise ValueError("No readable text in PDF")

    return text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks
