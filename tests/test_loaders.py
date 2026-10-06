from pathlib import Path

import pytest

from archivist.loaders import find_files, load_documents


def test_load_documents_from_directory(tmp_path: Path):
    (tmp_path / "a.md").write_text("# Title\nHello", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("你好", encoding="utf-8")
    (tmp_path / "images.png").write_bytes(b"\x89PNG")

    docs = load_documents(tmp_path)

    assert len(docs) == 2
    assert {d.metadata["file_type"] for d in docs} == {"md", "txt"}
    assert any(d.page_content == "你好" for d in docs)


def test_load_single_file(tmp_path: Path):
    file = tmp_path / "note.md"
    file.write_text("content", encoding="utf-8")

    docs = load_documents(file)

    assert len(docs) == 1
    assert docs[0].metadata["source"] == str(file.resolve())


def test_missing_path_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        find_files(tmp_path / "nope")


def test_skip_hidden_files_and_directories(tmp_path: Path):
    (tmp_path / "visible.md").write_text("keep", encoding="utf-8")
    (tmp_path / ".hidden.md").write_text("skip", encoding="utf-8")
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "config.md").write_text("skip", encoding="utf-8")

    files = find_files(tmp_path)

    assert [p.name for p in files] == ["visible.md"]
