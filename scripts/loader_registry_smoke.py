from pathlib import Path

from langchain_core.documents import Document


def load_text(path: Path) -> list[Document]:
    return [
        Document(
            page_content=path.read_text(encoding="utf-8"),
            metadata={
                "source": str(path.resolve()),
                "file_type": path.suffix[1:].lower(),
            },
        )
    ]


loaders = {".md": load_text, ".txt": load_text}

path = Path("evals/corpus/indexing.md")
loader = loaders.get(path.suffix.lower())
if loader is None:
    raise ValueError(f"Unsupported file type: {path.suffix}")

documents = loader(path)
print(len(documents))
print(documents[0].metadata)
print(documents[0].page_content[:100])
