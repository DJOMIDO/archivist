"""Discover files and dispatch them to format-specific loaders."""

from collections.abc import Callable
from pathlib import Path

from langchain_core.documents import Document

from archivist.loaders.docx import load_docx
from archivist.loaders.pdf import load_pdf
from archivist.loaders.text import load_text

Loader = Callable[[Path], list[Document]]

LOADERS: dict[str, Loader] = {
    ".md": load_text,
    ".txt": load_text,
    ".pdf": load_pdf,
    ".docx": load_docx,
}

SUPPORTED_SUFFIXES = set(LOADERS)


def find_files(path: Path) -> list[Path]:
    """Return supported files at `path` (a file or a directory, recursively)."""
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    if path.is_file():
        candidates = [path]
    else:
        candidates = [p for p in sorted(path.rglob("*")) if not _is_hidden(p, path)]
    return [
        p for p in candidates if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    ]


def _is_hidden(path: Path, root: Path) -> bool:
    """Whether any part of `path` below `root` starts with a dot."""
    return any(part.startswith(".") for part in path.relative_to(root).parts)


def load_file(path: Path) -> list[Document]:
    """Load a file using its registered format-specific loader."""
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return loader(path)


def load_documents(path: Path) -> list[Document]:
    """Load and flatten Documents from every supported file under path."""
    documents: list[Document] = []
    for file_path in find_files(path):
        documents.extend(load_file(file_path))
    return documents
