# Backup Policy

This document describes backups in the fictional Cedar Notes app.

Cedar Notes creates a backup every day at 02:00 UTC.
It retains the seven most recent successful backups.

Each backup contains the original documents and the document registry.
Backups do not contain the vector index.

After restoring a backup, the user must rebuild the vector index.
