from pathlib import Path

import pytest
from ebooklib import epub

from archivist.loaders import find_files, load_documents
from archivist.loaders.epub import load_epub


def make_section(name: str, content: str) -> epub.EpubHtml:
    return epub.EpubHtml(
        uid=name,
        file_name=f"{name}.xhtml",
        title=name,
        content=content,
    )


def test_load_epub_preserves_spine_order_and_filters_content(tmp_path: Path):
    path = tmp_path / "sample.epub"
    book = epub.EpubBook()
    book.set_identifier("test-book")
    book.set_title("Test Book")
    book.set_language("en")

    first = make_section("a", "<h1>Alpha</h1><p>中文 &amp; English</p>")
    second = make_section(
        "b",
        "<h1>Beta</h1>"
        "<script>noise()</script>"
        "<style>p {color:red}</style>"
        "<nav>Menu</nav>"
        "<footer>Keep this note.</footer>",
    )
    blank = make_section("blank", "<p> </p>")
    extra = make_section("extra", "<p>Outside spine</p>")
    navigation = epub.EpubNav()

    for item in [first, second, blank, extra, navigation]:
        book.add_item(item)

    book.toc = (first, second)
    book.spine = [navigation, (second, "no"), blank, first]
    epub.write_epub(str(path), book)

    documents = load_epub(path)

    assert [document.page_content for document in documents] == [
        "Beta\nKeep this note.",
        "Alpha\n中文 & English",
    ]
    assert [document.metadata for document in documents] == [
        {
            "source": str(path.resolve()),
            "file_type": "epub",
            "section": section,
        }
        for section in ["b.xhtml", "a.xhtml"]
    ]


def test_load_epub_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_epub(tmp_path / "missing.epub")


@pytest.mark.parametrize("suffix", [".epub", ".EPUB"])
def test_load_documents_from_directory_with_epub(tmp_path: Path, suffix: str):
    text_path = tmp_path / "note.md"
    text_path.write_text("Text note", encoding="utf-8")
    subdirectory = tmp_path / "sub"
    subdirectory.mkdir()
    epub_path = subdirectory / f"sample{suffix}"

    book = epub.EpubBook()
    book.set_identifier("mixed-test-book")
    book.set_title("Mixed Test Book")
    book.set_language("en")

    first = make_section("a", "<p>Alpha</p>")
    second = make_section("b", "<p>Beta</p>")
    for item in [first, second, epub.EpubNav()]:
        book.add_item(item)

    book.toc = (first, second)
    book.spine = [second, first]
    epub.write_epub(str(epub_path), book)

    assert set(find_files(tmp_path)) == {text_path, epub_path}

    documents = load_documents(tmp_path)

    assert len(documents) == 3
    text_documents = [
        document for document in documents if document.metadata["file_type"] == "md"
    ]
    epub_documents = [
        document for document in documents if document.metadata["file_type"] == "epub"
    ]

    assert len(text_documents) == 1
    assert text_documents[0].page_content == "Text note"
    assert [document.page_content for document in epub_documents] == [
        "Beta",
        "Alpha",
    ]
    assert [document.metadata for document in epub_documents] == [
        {
            "source": str(epub_path.resolve()),
            "file_type": "epub",
            "section": section,
        }
        for section in ["b.xhtml", "a.xhtml"]
    ]
