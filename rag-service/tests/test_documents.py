import random

import pytest

from rag_service.documents import PageText, chunk_pages, extract_pdf
from rag_service.errors import AppError


def test_chunks_keep_pages_positions_and_limits(settings):
    settings.chunk_size_chars = 100
    settings.chunk_overlap_chars = 20
    pages = (
        PageText(2, "Reglamento académico vigente. " * 50), PageText(5, "Sílabos actualizados."),
    )
    chunks = chunk_pages(pages, settings)
    assert [c.position for c in chunks] == list(range(len(chunks)))
    assert all(0 < len(c.text) <= 100 for c in chunks)
    assert all(c.page_start == c.page_end for c in chunks)
    assert chunks[0].page_start == 2 and chunks[-1].page_start == 5
    assert chunks[-1].text == pages[-1].text


@pytest.mark.parametrize("overlap", [0, 1, 20, 99])
def test_chunking_covers_long_word_without_losing_characters(settings, overlap):
    settings.chunk_size_chars = 100
    settings.chunk_overlap_chars = overlap
    text = "".join(random.Random(42).choices("abcdefgh", k=501))
    chunks = chunk_pages((PageText(1, text),), settings)
    assert chunks[0].text == text[:100]
    assert chunks[-1].text == text[-len(chunks[-1].text):]
    reconstructed = chunks[0].text + "".join(c.text[overlap:] for c in chunks[1:])
    assert reconstructed == text
    assert len(chunks) <= len(text)


def test_chunking_rejects_too_many_chunks(settings):
    settings.max_chunks = 1
    with pytest.raises(AppError, match="demasiados fragmentos"):
        chunk_pages((PageText(1, "x" * 4000),), settings)


@pytest.mark.parametrize("content,code", [(b"", "empty_pdf"), (b"not a pdf", "invalid_pdf")])
def test_invalid_file_rejected_before_extraction(tmp_path, settings, content, code):
    path = tmp_path / "bad.pdf"
    path.write_bytes(content)
    with pytest.raises(AppError) as error:
        extract_pdf(path, settings)
    assert error.value.code == code


def test_missing_pdf_has_controlled_error(tmp_path, settings):
    with pytest.raises(AppError) as error:
        extract_pdf(tmp_path / "missing.pdf", settings)
    assert error.value.code == "pdf_unreadable"


def test_size_limit_is_checked_before_parser(tmp_path, settings):
    settings.max_pdf_bytes = 10
    path = tmp_path / "big.pdf"
    path.write_bytes(b"%PDF-" + b"0" * 20)
    with pytest.raises(AppError) as error:
        extract_pdf(path, settings)
    assert error.value.code == "pdf_too_large"
