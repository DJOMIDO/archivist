from datetime import UTC, datetime
from pathlib import Path

from archivist.loaders import load_file
from archivist.metadata import attach_file_metadata, build_file_metadata
from archivist.splitting import split_documents

path = Path("data/lt3-lab1.pdf")
originals = load_file(path)[:2]
metadata = build_file_metadata(path, ingested_at=datetime.now(UTC))

documents = attach_file_metadata(originals, metadata)
chunks = split_documents(documents, chunk_size=100, chunk_overlap=20)

print(f"Documents: {len(documents)}")
print(f"Chunks: {len(chunks)}")
print(f"Pages: {sorted({chunk.metadata['page'] for chunk in chunks})}")

for chunk in chunks[:2]:
    print(chunk.metadata)

assert chunks
assert all(chunk.metadata["content_hash"] == metadata.content_hash for chunk in chunks)
assert all(chunk.metadata["ingested_at"] == metadata.ingested_at for chunk in chunks)
assert all("start_index" in chunk.metadata for chunk in chunks)
assert all("content_hash" not in document.metadata for document in originals)

print("Metadata propagation checks passed.")
