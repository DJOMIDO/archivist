from pathlib import Path
from shutil import copytree

import pytest

from archivist.evaluation import fingerprint_eval_data


@pytest.fixture
def fingerprint_paths(tmp_path: Path):
    cases = tmp_path / "cases.json"
    cases.write_text("[]", encoding="utf-8")

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("Original content", encoding="utf-8")

    return cases, corpus


def test_unchanged_data_has_identical_fingerprints(fingerprint_paths):
    cases, corpus = fingerprint_paths

    first = fingerprint_eval_data(cases, corpus)
    second = fingerprint_eval_data(cases, corpus)

    assert first == second


def test_case_formatting_changes_only_case_hash(fingerprint_paths):
    cases, corpus = fingerprint_paths
    before = fingerprint_eval_data(cases, corpus)

    cases.write_text("[]\n", encoding="utf-8")
    after = fingerprint_eval_data(cases, corpus)

    assert after.cases_sha256 != before.cases_sha256
    assert after.corpus_sha256 == before.corpus_sha256
    assert after.files == before.files


def test_document_content_changes_corpus_hash(fingerprint_paths):
    cases, corpus = fingerprint_paths
    before = fingerprint_eval_data(cases, corpus)

    (corpus / "note.md").write_text("Changed content", encoding="utf-8")
    after = fingerprint_eval_data(cases, corpus)

    assert after.corpus_sha256 != before.corpus_sha256
    assert after.files["note.md"] != before.files["note.md"]
    assert after.cases_sha256 == before.cases_sha256


def test_renaming_document_changes_corpus_hash(fingerprint_paths):
    cases, corpus = fingerprint_paths
    before = fingerprint_eval_data(cases, corpus)

    (corpus / "note.md").rename(corpus / "renamed.md")
    after = fingerprint_eval_data(cases, corpus)

    assert after.corpus_sha256 != before.corpus_sha256
    assert after.files == {"renamed.md": before.files["note.md"]}


def test_ignored_files_do_not_change_fingerprints(fingerprint_paths):
    cases, corpus = fingerprint_paths
    before = fingerprint_eval_data(cases, corpus)

    (corpus / "image.png").write_bytes(b"image")
    (corpus / ".hidden.md").write_text("Hidden", encoding="utf-8")
    hidden_dir = corpus / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "note.md").write_text("Hidden", encoding="utf-8")

    after = fingerprint_eval_data(cases, corpus)

    assert after == before


def test_relocated_corpus_has_identical_fingerprints(fingerprint_paths, tmp_path: Path):
    cases, corpus = fingerprint_paths
    before = fingerprint_eval_data(cases, corpus)

    moved = tmp_path / "moved"
    copytree(corpus, moved)
    after = fingerprint_eval_data(cases, moved)

    assert after == before


def test_empty_corpus_is_rejected(fingerprint_paths, tmp_path: Path):
    cases, _ = fingerprint_paths
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(ValueError, match="no supported files"):
        fingerprint_eval_data(cases, empty)
