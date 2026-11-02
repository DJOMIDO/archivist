"""Load text from UTF-8 HTML files."""

from pathlib import Path

from bs4 import BeautifulSoup
from langchain_core.documents import Document


def load_html(path: Path) -> list[Document]:
    """Load HTML text after removing selected boilerplate elements."""
    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.select("script, style, nav, footer"):
        tag.decompose()

    root = soup.body if soup.body is not None else soup
    text = root.get_text(separator="\n", strip=True)

    return [
        Document(
            page_content=text,
            metadata={
                "source": str(path.resolve()),
                "file_type": "html",
            },
        )
    ]
