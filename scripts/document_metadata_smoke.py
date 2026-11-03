from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.documents import Document

from archivist.loaders import load_file
from archivist.metadata import build_file_metadata
from archivist.splitting import split_documents

path = Path("data/lt3-lab1.pdf")
originals = load_file(path)[:2]
shared = asdict(build_file_metadata(path, ingested_at=datetime.now(UTC)))

documents = [
    Document(
        page_content=document.page_content,
        metadata={**document.metadata, **shared},
    )
    for document in originals
]
chunks = split_documents(documents, chunk_size=100, chunk_overlap=20)

print(f"Documents: {len(documents)}")
print(f"Chunks: {len(chunks)}")
print(f"Pages: {sorted({chunk.metadata['page'] for chunk in chunks})}")

for chunk in chunks[:2]:
    print(chunk.metadata)

assert chunks
assert all(chunk.metadata["content_hash"] == shared["content_hash"] for chunk in chunks)
assert all(chunk.metadata["ingested_at"] == shared["ingested_at"] for chunk in chunks)
assert all("start_index" in chunk.metadata for chunk in chunks)
assert all("content_hash" not in document.metadata for document in originals)

print("Metadata propagation checks passed.")
