from pathlib import Path
from zipfile import ZipFile

import pytest
from langchain_core.documents import Document
from pypdf import PdfWriter

from archivist.loaders import LOADERS, find_files, load_documents, load_file


def test_load_documents_from_directory(tmp_path: Path):
    (tmp_path / "a.md").write_text("# Title\nHello", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("你好", encoding="utf-8")
    (tmp_path / "images.png").write_bytes(b"\x89PNG")

    docs = load_documents(tmp_path)

    assert len(docs) == 2
    assert {d.metadata["file_type"] for d in docs} == {"md", "txt"}
    assert any(d.page_content == "你好" for d in docs)


def test_load_single_file(tmp_path: Path):
    file = tmp_path / "note.md"
    file.write_text("content", encoding="utf-8")

    docs = load_documents(file)

    assert len(docs) == 1
    assert docs[0].metadata["source"] == str(file.resolve())


def test_missing_path_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        find_files(tmp_path / "nope")


def test_skip_hidden_files_and_directories(tmp_path: Path):
    (tmp_path / "visible.md").write_text("keep", encoding="utf-8")
    (tmp_path / ".hidden.md").write_text("skip", encoding="utf-8")
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "config.md").write_text("skip", encoding="utf-8")

    files = find_files(tmp_path)

    assert [p.name for p in files] == ["visible.md"]


@pytest.mark.parametrize("suffix", [".MD", ".TXT"])
def test_load_file_accepts_uppercase_suffix(tmp_path: Path, suffix: str):
    path = tmp_path / f"note{suffix}"
    path.write_text("Hello 你好", encoding="utf-8")

    documents = load_file(path)

    assert len(documents) == 1
    assert documents[0].page_content == "Hello 你好"
    assert documents[0].metadata == {
        "source": str(path.resolve()),
        "file_type": suffix[1:].lower(),
    }


def test_load_file_rejects_unsupported_suffix(tmp_path: Path):
    path = tmp_path / "image.png"
    path.write_bytes(b"\x89PNG")

    with pytest.raises(ValueError, match="Unsupported file type"):
        load_file(path)


def test_load_documents_flattens_loader_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "note.txt"
    path.write_text("placeholder", encoding="utf-8")
    expected = [
        Document(page_content="First page", metadata={"page": 1}),
        Document(page_content="Second page", metadata={"page": 2}),
    ]

    def fake_loader(file_path: Path) -> list[Document]:
        assert file_path == path
        return expected

    monkeypatch.setitem(LOADERS, ".txt", fake_loader)

    documents = load_documents(tmp_path)

    assert documents == expected


@pytest.mark.parametrize("suffix", [".pdf", ".PDF"])
def test_load_documents_from_mixed_directory(tmp_path: Path, suffix: str):
    text_path = tmp_path / "note.md"
    text_path.write_text("Hello", encoding="utf-8")
    subdirectory = tmp_path / "sub"
    subdirectory.mkdir()
    pdf_path = subdirectory / f"sample{suffix}"

    with PdfWriter() as writer:
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        writer.write(pdf_path)

    assert set(find_files(tmp_path)) == {text_path, pdf_path}

    documents = load_documents(tmp_path)

    assert len(documents) == 3
    text_documents = [
        document for document in documents if document.metadata["file_type"] == "md"
    ]
    pdf_documents = [
        document for document in documents if document.metadata["file_type"] == "pdf"
    ]
    assert len(text_documents) == 1
    assert text_documents[0].page_content == "Hello"
    assert [document.metadata for document in pdf_documents] == [
        {
            "source": str(pdf_path.resolve()),
            "file_type": "pdf",
            "page": page_number,
        }
        for page_number in (1, 2)
    ]


@pytest.mark.parametrize("suffix", [".docx", ".DOCX"])
def test_load_documents_from_directory_with_docx(tmp_path: Path, suffix: str):
    text_path = tmp_path / "note.md"
    text_path.write_text("Text note", encoding="utf-8")
    subdirectory = tmp_path / "sub"
    subdirectory.mkdir()
    docx_path = subdirectory / f"sample{suffix}"

    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>DOCX content</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    with ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", xml)

    assert set(find_files(tmp_path)) == {text_path, docx_path}

    documents = load_documents(tmp_path)

    assert len(documents) == 2
    by_source = {document.metadata["source"]: document for document in documents}
    assert by_source[str(text_path.resolve())].page_content == "Text note"

    docx_document = by_source[str(docx_path.resolve())]
    assert docx_document.page_content == "DOCX content"
    assert docx_document.metadata == {
        "source": str(docx_path.resolve()),
        "file_type": "docx",
    }
