# Indexing Policy

This document describes the indexing policy of the fictional Cedar Notes app.

Cedar Notes identifies an unchanged document by its SHA-256 content hash.
An unchanged document is skipped without recomputing its embeddings.

When a document changes, Cedar Notes replaces its previous chunks with
chunks from the new version.

Deleting a document removes both its registry entry and all of its chunks.
