"""Build chunk ID to text-digest manifests for index consistency checks."""

from hashlib import sha256


def build_chunk_manifest(chunk_ids: list[str], texts: list[str]) -> dict[str, str]:
    """Hash chunk texts, rejecting mismatched lengths and duplicate IDs."""
    manifest: dict[str, str] = {}
    for chunk_id, text in zip(chunk_ids, texts, strict=True):
        if chunk_id in manifest:
            raise ValueError(f"Duplicate chunk ID: {chunk_id}")
        manifest[chunk_id] = sha256(text.encode("utf-8")).hexdigest()
    return manifest
