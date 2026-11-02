"""Load DOCX files into Documents."""

from pathlib import Path

import docx2txt
from langchain_core.documents import Document


def load_docx(path: Path) -> list[Document]:
    """Load a DOCX file as a single Document without page metadata."""
    text = docx2txt.process(str(path))
    return [
        Document(
            page_content=text,
            metadata={
                "source": str(path.resolve()),
                "file_type": "docx",
            },
        )
    ]
