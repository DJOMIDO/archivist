"""Load documents from disk into LangChain `Document` objects."""

from pathlib import Path

from langchain_core.documents import Document

SUPPORTED_SUFFIXES = {".md", ".txt"}


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


def load_file(path: Path) -> Document:
    """Load a single text file as a `Document`."""
    text = path.read_text(encoding="utf-8")
    return Document(
        page_content=text,
        metadata={
            "source": str(path.resolve()),
            "file_type": path.suffix.lstrip(".").lower(),
        },
    )


def load_documents(path: Path) -> list[Document]:
    """Load every supported document under `path`."""
    return [load_file(p) for p in find_files(path)]
