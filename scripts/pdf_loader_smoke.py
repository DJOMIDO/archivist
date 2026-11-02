from pathlib import Path

from archivist.loaders import load_documents

paths = sorted(
    path
    for path in Path("data").iterdir()
    if path.is_file() and path.suffix.lower() == ".pdf"
)

if not paths:
    raise FileNotFoundError("No PDF files found in data/")

for path in paths:
    documents = load_documents(path)

    print(f"\nFile: {path.name}")
    print(f"Pages: {len(documents)}")
    for document in documents[:2]:
        print(document.metadata)
        print(repr(document.page_content[:100]))
