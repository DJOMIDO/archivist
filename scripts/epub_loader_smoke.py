from pathlib import Path

from archivist.loaders import load_documents

paths = sorted(
    path
    for path in Path("data").iterdir()
    if path.is_file() and path.suffix.lower() == ".epub"
)

if not paths:
    raise FileNotFoundError("No EPUB files found in data/")

for path in paths:
    documents = load_documents(path)

    print(f"\nFile: {path.name}")
    print(f"Documents: {len(documents)}")
    for document in documents:
        print(document.metadata)
        print(f"Characters: {len(document.page_content)}")
        print(repr(document.page_content[:200]))
