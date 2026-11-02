pages = [
    {"source": "/notes/a.pdf", "page": 1, "start_index": 0},
    {"source": "/notes/a.pdf", "page": 2, "start_index": 0},
]

for metadata in pages:
    source = metadata["source"]
    start = metadata["start_index"]
    page = metadata["page"]
    print(f"Old: {source}:{start}")
    print(f"New: {source}:page={page}:{start}")
