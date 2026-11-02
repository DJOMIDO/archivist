"""Load PDF pages into Documents."""

from pathlib import Path

from langchain_core.documents import Document
from pypdf import PdfReader


def load_pdf(path: Path) -> list[Document]:
    """Load each PDF page as a Document with a 1-based page number."""
    documents: list[Document] = []
    source = str(path.resolve())

    with path.open("rb") as file:
        reader = PdfReader(file)
        for page_number, page in enumerate(reader.pages, start=1):
            documents.append(
                Document(
                    page_content=page.extract_text() or "",
                    metadata={
                        "source": source,
                        "file_type": "pdf",
                        "page": page_number,
                    },
                )
            )

    return documents
