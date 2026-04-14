from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

DEFAULT_DESTINATION = Path("data/raw/goodbooks")
DEFAULT_FILES = {
    "books.csv": "https://raw.githubusercontent.com/zygmuntz/goodbooks-10k/master/books.csv",
    "ratings.csv": "https://raw.githubusercontent.com/zygmuntz/goodbooks-10k/master/ratings.csv",
}


def download_goodbooks_data(
    destination: Path,
    *,
    force: bool = False,
    downloader=urlretrieve,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename, url in DEFAULT_FILES.items():
        target = destination / filename
        if target.exists() and not force:
            if target.stat().st_size <= 0:
                raise RuntimeError(f"Existing file is empty: {target}")
            print(f"skip_existing {target}")
            paths.append(target)
            continue
        print(f"download {url} -> {target}")
        downloader(url, str(target))
        if not target.exists() or target.stat().st_size <= 0:
            raise RuntimeError(f"Downloaded file is empty: {target}")
        paths.append(target)
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download Goodbooks-10k CSV files for local import.")
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_DESTINATION,
        help="Directory that will contain books.csv and ratings.csv.",
    )
    parser.add_argument("--force", action="store_true", help="Re-download files even if they already exist.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    paths = download_goodbooks_data(args.destination, force=args.force)
    for path in paths:
        print(f"ready {path} bytes={path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
