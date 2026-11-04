import pytest

from archivist.chunk_manifest import build_chunk_manifest


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
        ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("你好", "670d9743542cae3ea7ebe36af56bd53648b0a1126162e78d81a32934a711302e"),
    ],
)
def test_manifest_uses_utf8_sha256(text, expected):
    assert build_chunk_manifest(["chunk-1"], [text]) == {"chunk-1": expected}


def test_manifest_preserves_distinct_ids_with_identical_text():
    manifest = build_chunk_manifest(["chunk-1", "chunk-2"], ["abc", "abc"])

    assert set(manifest) == {"chunk-1", "chunk-2"}
    assert manifest["chunk-1"] == manifest["chunk-2"]


@pytest.mark.parametrize("texts", [["abc", "abc"], ["abc", "changed"]])
def test_manifest_rejects_duplicate_ids(texts):
    with pytest.raises(ValueError, match="Duplicate chunk ID: chunk-1"):
        build_chunk_manifest(["chunk-1", "chunk-1"], texts)


@pytest.mark.parametrize(
    ("chunk_ids", "texts"),
    [
        (["chunk-1", "chunk-2"], ["abc"]),
        (["chunk-1"], ["abc", "extra"]),
    ],
)
def test_manifest_rejects_mismatched_lengths(chunk_ids, texts):
    with pytest.raises(ValueError):
        build_chunk_manifest(chunk_ids, texts)


def test_empty_manifest():
    assert build_chunk_manifest([], []) == {}


def test_manifest_does_not_modify_inputs():
    chunk_ids = ["chunk-2", "chunk-1"]
    texts = ["second", "first"]
    ids_before = chunk_ids.copy()
    texts_before = texts.copy()

    manifest = build_chunk_manifest(chunk_ids, texts)

    assert chunk_ids == ids_before
    assert texts == texts_before
    assert manifest == build_chunk_manifest(chunk_ids[::-1], texts[::-1])
    assert manifest != build_chunk_manifest(chunk_ids, ["changed", "first"])
