from pathlib import Path

from archivist.loaders import load_documents

paths = sorted(
    path
    for path in Path("data").iterdir()
    if path.is_file() and path.suffix.lower() == ".docx"
)

if not paths:
    raise FileNotFoundError("No DOCX files found in data/")

for path in paths:
    documents = load_documents(path)
    print(f"\nFile: {path.name}")
    print(f"Documents: {len(documents)}")
    print(documents[0].metadata)
    print(repr(documents[0].page_content[:500]))
