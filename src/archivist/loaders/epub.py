"""Load EPUB content files into section Documents."""

from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import epub
from langchain_core.documents import Document


def load_epub(path: Path) -> list[Document]:
    """Load non-empty HTML sections in spine order, excluding navigation."""
    book = epub.read_epub(str(path))
    source = str(path.resolve())
    documents: list[Document] = []

    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None:
            raise ValueError(f"Missing spine item: {item_id}")

        if not isinstance(item, epub.EpubHtml):
            continue
        if isinstance(item, epub.EpubNav):
            continue

        soup = BeautifulSoup(
            item.get_body_content(),
            "html.parser",
            from_encoding="utf-8",
        )
        for tag in soup.select("script, style, nav"):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        if not text:
            continue

        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source": source,
                    "file_type": "epub",
                    "section": item.get_name(),
                },
            )
        )

    return documents
