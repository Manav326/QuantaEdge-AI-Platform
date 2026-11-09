from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    page_number: int | None
    content: str


def chunk_pages(pages: list[tuple[int | None, str]], max_characters: int, overlap_characters: int) -> list[TextChunk]:
    if max_characters < 100:
        raise ValueError("max_characters must be at least 100")
    if overlap_characters < 0 or overlap_characters >= max_characters:
        raise ValueError("overlap_characters must be between 0 and max_characters - 1")
    chunks: list[TextChunk] = []
    for page_number, raw_text in pages:
        text = " ".join(raw_text.split())
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + max_characters, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + max_characters // 2, end)
                if boundary > start:
                    end = boundary
            content = text[start:end].strip()
            if content:
                chunks.append(TextChunk(index=len(chunks), page_number=page_number, content=content))
            if end >= len(text):
                break
            start = max(end - overlap_characters, start + 1)
    return chunks
