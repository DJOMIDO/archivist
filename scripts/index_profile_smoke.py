import json
import sqlite3
from contextlib import closing
from importlib.metadata import version
from pathlib import Path
from platform import python_version

from archivist.config import Settings
from archivist.index_profile import (
    INDEX_PACKAGE_NAMES,
    IndexProfile,
    fingerprint_index_profile,
)
from archivist.registry import ensure_index_profile, initialize_registry
from archivist.splitting import SEPARATORS

settings = Settings()

profile = IndexProfile(
    embedding_model=settings.embedding_model,
    embedding_base_url=settings.llm_base_url,
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    separators=SEPARATORS,
    python=python_version(),
    packages={name: version(name) for name in INDEX_PACKAGE_NAMES},
)
fingerprint = fingerprint_index_profile(profile)

print(json.dumps(profile.model_dump(mode="json"), indent=2, ensure_ascii=False))
print(f"Index fingerprint: {fingerprint}")
print(f"Hash length: {len(fingerprint)}")
profile_path = Path("storage/index-profile-smoke.sqlite3")
profile_path.parent.mkdir(parents=True, exist_ok=True)

with closing(sqlite3.connect(profile_path)) as connection:
    initialize_registry(connection)
    created = ensure_index_profile(connection, profile)

if created:
    print("Saved initial profile.")
else:
    print("Stored profile matches.")
