"""Split documents into chunks small enough to embed and retrieve precisely."""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Tried in order: paragraphs, lines, sentences (Chinese and English), words, characters.
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", " ", ""]


def split_documents(
    documents: list[Document], chunk_size: int, chunk_overlap: int
) -> list[Document]:
    """Split documents into overlapping chunks; each chunk keeps its metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SEPARATORS,
        keep_separator="end",
        add_start_index=True,
    )
    return splitter.split_documents(documents)
