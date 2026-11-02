from pathlib import Path

import pytest

from archivist.loaders.html import load_html


def test_load_html_cleans_text_and_preserves_metadata(tmp_path: Path):
    path = tmp_path / "sample.html"
    path.write_text(
        """
        <html>
          <head>
            <title>Website title</title>
            <style>body { color: red; }</style>
          </head>
          <body>
            <nav>Home | Contact</nav>
            <main>
              <h1>Backup Policy</h1>
              <p>Backups are retained for 14 days.</p>
              <p>中文 &amp; English</p>
              <p><a href="/details">Read policy details</a></p>
            </main>
            <footer>Important footer note</footer>
            <script>console.log("noise");</script>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    documents = load_html(path)

    assert len(documents) == 1
    assert documents[0].page_content == (
        "Backup Policy\n"
        "Backups are retained for 14 days.\n"
        "中文 & English\n"
        "Read policy details"
    )
    assert documents[0].metadata == {
        "source": str(path.resolve()),
        "file_type": "html",
    }


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>Fragment</p>", "Fragment"),
        ("", ""),
        (
            "<html><head><title>Title</title></head><body></body></html>",
            "",
        ),
    ],
)
def test_load_html_fragments_and_empty_content(
    tmp_path: Path, html: str, expected: str
):
    path = tmp_path / "sample.html"
    path.write_text(html, encoding="utf-8")

    documents = load_html(path)

    assert len(documents) == 1
    assert documents[0].page_content == expected


def test_load_html_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_html(tmp_path / "missing.html")
