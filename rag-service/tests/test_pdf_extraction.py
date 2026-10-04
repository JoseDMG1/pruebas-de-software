import hashlib

import pytest

pytest.importorskip("pypdf")
from pypdf import PdfReader, PdfWriter

from conftest import pdf_bytes
from rag_service.documents import extract_pdf
from rag_service.errors import AppError


def test_real_pdf_text_pages_and_hash(sample_pdf, settings):
    pdf = extract_pdf(sample_pdf, settings)
    assert pdf.total_pages == 2
    assert pdf.pages[0].number == 1
    assert "enrollment" in pdf.pages[0].text
    assert pdf.sha256 == hashlib.sha256(sample_pdf.read_bytes()).hexdigest()
    assert not pdf.skipped_pages


def test_blank_or_scanned_pdf_requires_ocr(tmp_path, settings):
    path = tmp_path / "scan.pdf"
    path.write_bytes(pdf_bytes([""]))
    with pytest.raises(AppError) as error:
        extract_pdf(path, settings)
    assert error.value.code == "no_text"


def test_mixed_document_reports_pages_without_text(tmp_path, settings):
    path = tmp_path / "mixed.pdf"
    path.write_bytes(pdf_bytes(["", "Text on page two.", ""]))
    pdf = extract_pdf(path, settings)
    assert pdf.skipped_pages == (1, 3)
    assert pdf.pages[0].number == 2


def test_encrypted_document_has_controlled_error(sample_pdf, settings, tmp_path):
    writer = PdfWriter()
    writer.append_pages_from_reader(PdfReader(sample_pdf))
    writer.encrypt("test-password")
    path = tmp_path / "encrypted.pdf"
    writer.write(path)
    with pytest.raises(AppError) as error:
        extract_pdf(path, settings)
    assert error.value.code == "encrypted_pdf"


def test_damaged_pdf_has_controlled_error(tmp_path, settings):
    path = tmp_path / "damaged.pdf"
    path.write_bytes(b"%PDF-1.4\ntruncated data")
    with pytest.raises(AppError) as error:
        extract_pdf(path, settings)
    assert error.value.code == "invalid_pdf"


def test_page_limit_is_enforced(sample_pdf, settings):
    settings.max_pdf_pages = 1
    with pytest.raises(AppError) as error:
        extract_pdf(sample_pdf, settings)
    assert error.value.code == "too_many_pages"
