import argparse
import csv
from collections.abc import Iterator
from itertools import islice
from pathlib import Path
from pprint import pprint


USER_COLUMNS = ("id", "type", "name", "reserved", "description")
ENTRY_COLUMNS = (
    "PostID", "PostedBy", "SourceName", "SourceURL", "GeoX", "GeoY",
    "Timestamp", "Text", "NumImg", "ImgURL", "NumVideo", "VideoURL",
)
DEFAULT_USERS_PATH = Path(__file__).resolve().parent.parent / "data" / "users.csv"


def read_users(path: str | Path) -> Iterator[dict[str, str]]:
    path = Path(path).expanduser()
    csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter="|", quoting=csv.QUOTE_NONE)
        for row in reader:
            if len(row) != len(USER_COLUMNS):
                raise ValueError(
                    f"{path}, rad {reader.line_num}: "
                    f"förväntade {len(USER_COLUMNS)} fält, fick {len(row)}."
                )
            yield dict(zip(USER_COLUMNS, row))


def read_entries(path: str | Path) -> Iterator[dict[str, str]]:
    path = Path(path).expanduser()
    csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            if len(row) != len(ENTRY_COLUMNS):
                raise ValueError(
                    f"{path}, rad {reader.line_num}: "
                    f"förväntade {len(ENTRY_COLUMNS)} fält, fick {len(row)}."
                )
            yield dict(zip(ENTRY_COLUMNS, row))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_USERS_PATH)
    args = parser.parse_args()

    rows = read_users(args.file)
    try:
        for row in islice(rows, 5):
            pprint(row, sort_dicts=False)
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        parser.exit(1, f"Kunde inte läsa users: {error}\n")
    finally:
        rows.close()


if __name__ == "__main__":
    main()
