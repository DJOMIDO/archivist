"""Load plain-text files into Documents."""

from pathlib import Path

from langchain_core.documents import Document


def load_text(path: Path) -> list[Document]:
    """Load a UTF-8 text file as a single Document."""
    return [
        Document(
            page_content=path.read_text(encoding="utf-8"),
            metadata={
                "source": str(path.resolve()),
                "file_type": path.suffix[1:].lower(),
            },
        )
    ]
