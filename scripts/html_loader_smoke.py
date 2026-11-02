from pathlib import Path

from archivist.loaders import load_documents

path = Path("data/sample.html")
documents = load_documents(path)

print(f"Documents: {len(documents)}")
print(documents[0].metadata)
print(documents[0].page_content)
