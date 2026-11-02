from pathlib import Path
from unittest.mock import Mock

import pytest
from pypdf import PdfWriter

from archivist.loaders.pdf import load_pdf


def test_load_pdf_maps_page_text_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"placeholder")

    reader = Mock()
    reader.pages = [Mock(), Mock(), Mock()]
    texts = ["First page", "", None]
    for page, text in zip(reader.pages, texts, strict=True):
        page.extract_text.return_value = text

    monkeypatch.setattr(
        "archivist.loaders.pdf.PdfReader",
        Mock(return_value=reader),
    )

    documents = load_pdf(path)

    assert [document.page_content for document in documents] == [
        "First page",
        "",
        "",
    ]
    assert [document.metadata for document in documents] == [
        {
            "source": str(path.resolve()),
            "file_type": "pdf",
            "page": page_number,
        }
        for page_number in range(1, 4)
    ]


def test_load_pdf_preserves_real_blank_pages(tmp_path: Path):
    path = tmp_path / "blank.pdf"
    with PdfWriter() as writer:
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        writer.write(path)

    documents = load_pdf(path)

    assert len(documents) == 2
    assert [document.page_content for document in documents] == ["", ""]
    assert [document.metadata["page"] for document in documents] == [1, 2]


def test_load_pdf_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_pdf(tmp_path / "missing.pdf")
