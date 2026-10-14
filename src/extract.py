from __future__ import annotations
import csv
from collections.abc import Iterator
from pathlib import Path

USER_COLUMNS = ("id", "type", "name", "reserved", "description")
ENTRY_COLUMNS = ("PostID", "PostedBy", "SourceName", "SourceURL", "GeoX", "GeoY", "Timestamp", "Text", "NumImg", "ImgURL", "NumVideo", "VideoURL")
LIKE_COLUMNS = ("userID", "PostID", "Timestamp")
COMMENT_COLUMNS = ("PostID", "EntryID", "PostedBy", "SourceName", "SourceURL", "GeoX", "GeoY", "Timestamp", "Text")
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
                    f"{path}, row {reader.line_num}: "
                    f"expected {len(USER_COLUMNS)} fields, received: {len(row)}."
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
                    f"{path}, row {reader.line_num}: "
                    f"expected {len(ENTRY_COLUMNS)} fields, received: {len(row)}."
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
                    f"{path}, row {reader.line_num}: "
                    f"expected {len(LIKE_COLUMNS)} fields, received: {len(row)}."
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
                    f"{path}, row {reader.line_num}: "
                    f"expected {len(COMMENT_COLUMNS)} fields, received: {len(row)}."
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
                    f"{path}, row {reader.line_num}: "
                    f"expected {len(FOLLOWING_COLUMNS)} fields, received: {len(row)}."
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
                    f"{path}, row {reader.line_num}: "
                    f"expected {len(SUBSCRIPTION_COLUMNS)} fields, received {len(row)}."
                )
            yield dict(zip(SUBSCRIPTION_COLUMNS, row))
