from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pytest

from archivist.loaders.docx import load_docx


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "<w:p><w:r><w:t>Hello</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>你好</w:t></w:r></w:p>",
            "Hello\n\n你好",
        ),
        ("", ""),
    ],
)
def test_load_docx_text_and_metadata(tmp_path: Path, body: str, expected: str):
    path = tmp_path / "sample.docx"
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)

    documents = load_docx(path)

    assert len(documents) == 1
    assert documents[0].page_content == expected
    assert documents[0].metadata == {
        "source": str(path.resolve()),
        "file_type": "docx",
    }


def test_load_docx_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_docx(tmp_path / "missing.docx")


def test_load_docx_corrupt_file_raises(tmp_path: Path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a ZIP archive")

    with pytest.raises(BadZipFile):
        load_docx(path)
