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
LIKE_COLUMNS = ("userID", "PostID", "Timestamp")
COMMENT_COLUMNS = (
    "PostID", "EntryID", "PostedBy", "SourceName", "SourceURL",
    "GeoX", "GeoY", "Timestamp", "Text",
)
FOLLOWING_COLUMNS = ("follower_id", "followed_id", "Timestamp")
SUBSCRIPTION_COLUMNS = ("subscriber_id", "subscribed_to_id")


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


def read_likes(path: str | Path) -> Iterator[dict[str, str]]:
    path = Path(path).expanduser()
    csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            if len(row) != len(LIKE_COLUMNS):
                raise ValueError(
                    f"{path}, rad {reader.line_num}: "
                    f"förväntade {len(LIKE_COLUMNS)} fält, fick {len(row)}."
                )
            yield dict(zip(LIKE_COLUMNS, row))


def read_comments(path: str | Path) -> Iterator[dict[str, str]]:
    path = Path(path).expanduser()
    csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            if len(row) != len(COMMENT_COLUMNS):
                raise ValueError(
                    f"{path}, rad {reader.line_num}: "
                    f"förväntade {len(COMMENT_COLUMNS)} fält, fick {len(row)}."
                )
            yield dict(zip(COMMENT_COLUMNS, row))


def read_following(path: str | Path) -> Iterator[dict[str, str]]:
    path = Path(path).expanduser()
    csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            if len(row) != len(FOLLOWING_COLUMNS):
                raise ValueError(
                    f"{path}, rad {reader.line_num}: "
                    f"förväntade {len(FOLLOWING_COLUMNS)} fält, fick {len(row)}."
                )
            yield dict(zip(FOLLOWING_COLUMNS, row))


def read_subscriptions(path: str | Path) -> Iterator[dict[str, str]]:
    path = Path(path).expanduser()
    csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter=",", quoting=csv.QUOTE_NONE)
        for row in reader:
            if len(row) != len(SUBSCRIPTION_COLUMNS):
                raise ValueError(
                    f"{path}, rad {reader.line_num}: "
                    f"förväntade {len(SUBSCRIPTION_COLUMNS)} fält, fick {len(row)}."
                )
            yield dict(zip(SUBSCRIPTION_COLUMNS, row))


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
