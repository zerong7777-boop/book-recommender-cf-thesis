from pathlib import Path
import sys

import pytest
import scripts.download_goodbooks_data as download_mod

from scripts.download_goodbooks_data import DEFAULT_FILES, download_goodbooks_data


def test_download_goodbooks_data_fetches_books_and_ratings(tmp_path):
    calls = []

    def fake_downloader(url: str, target: str):
        target_path = Path(target)
        calls.append((url, target_path.name))
        target_path.write_text(f"downloaded from {url}\n", encoding="utf-8")
        return str(target_path), None

    paths = download_goodbooks_data(tmp_path, downloader=fake_downloader)

    assert {path.name for path in paths} == {"books.csv", "ratings.csv"}
    assert calls == [
        (DEFAULT_FILES["books.csv"], "books.csv"),
        (DEFAULT_FILES["ratings.csv"], "ratings.csv"),
    ]
    assert (tmp_path / "books.csv").read_text(encoding="utf-8").startswith("downloaded from")
    assert (tmp_path / "ratings.csv").read_text(encoding="utf-8").startswith("downloaded from")


def test_download_goodbooks_data_skips_existing_files_without_force(tmp_path, capsys):
    calls = []
    (tmp_path / "books.csv").write_text("existing books\n", encoding="utf-8")
    (tmp_path / "ratings.csv").write_text("existing ratings\n", encoding="utf-8")

    def fake_downloader(url: str, target: str):
        calls.append((url, target))
        raise AssertionError("existing files should not be downloaded without force")

    paths = download_goodbooks_data(tmp_path, downloader=fake_downloader)

    output = capsys.readouterr().out.splitlines()
    assert calls == []
    assert {path.name for path in paths} == {"books.csv", "ratings.csv"}
    assert output == [
        f"skip_existing {tmp_path / 'books.csv'}",
        f"skip_existing {tmp_path / 'ratings.csv'}",
    ]
    assert (tmp_path / "books.csv").read_text(encoding="utf-8") == "existing books\n"
    assert (tmp_path / "ratings.csv").read_text(encoding="utf-8") == "existing ratings\n"


def test_download_goodbooks_data_rejects_empty_existing_file_without_force(tmp_path):
    (tmp_path / "books.csv").write_text("", encoding="utf-8")
    (tmp_path / "ratings.csv").write_text("existing ratings\n", encoding="utf-8")
    calls = []

    def fake_downloader(url: str, target: str):
        calls.append((url, target))
        raise AssertionError("empty existing files should not be skipped without force")

    with pytest.raises(RuntimeError, match=r"Existing file is empty: .*books\.csv"):
        download_goodbooks_data(tmp_path, downloader=fake_downloader)

    assert calls == []


def test_main_prints_ready_for_every_returned_path(monkeypatch, tmp_path, capsys):
    books = tmp_path / "books.csv"
    ratings = tmp_path / "ratings.csv"
    books.write_text("existing books\n", encoding="utf-8")
    ratings.write_text("existing ratings\n", encoding="utf-8")
    calls = []

    def fake_download_goodbooks_data(destination, *, force=False, downloader=download_mod.urlretrieve):
        calls.append((destination, force))
        return [books, ratings]

    monkeypatch.setattr(download_mod, "download_goodbooks_data", fake_download_goodbooks_data)
    monkeypatch.setattr(sys, "argv", ["download_goodbooks_data.py", "--destination", str(tmp_path)])

    assert download_mod.main() == 0

    output = capsys.readouterr().out.splitlines()
    assert calls == [(tmp_path, False)]
    assert output == [
        f"ready {books} bytes={books.stat().st_size}",
        f"ready {ratings} bytes={ratings.stat().st_size}",
    ]
