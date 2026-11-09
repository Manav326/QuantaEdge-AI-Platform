import pytest

from app.services.chunking import chunk_pages


def test_chunks_preserve_page_and_cover_text():
    text = "word " * 800
    chunks = chunk_pages([(3, text)], max_characters=500, overlap_characters=50)
    assert len(chunks) > 1
    assert all(chunk.page_number == 3 for chunk in chunks)
    assert all(chunk.content for chunk in chunks)


def test_chunk_indices_are_contiguous_across_pages():
    chunks = chunk_pages([(1, "a " * 100), (2, "b " * 100)], 150, 20)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.page_number for chunk in chunks} == {1, 2}


def test_invalid_chunk_settings_fail_fast():
    with pytest.raises(ValueError):
        chunk_pages([(None, "text")], 100, 100)
