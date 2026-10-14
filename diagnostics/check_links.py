import argparse
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from src.extract import read_comments, read_entries, read_likes, read_users


def is_missing(value):
    return value.strip().lower() in ("", "null", "\\n")


def check_links(data_dir):
    data_dir = Path(data_dir).expanduser()
    filenames = (
        "users.csv", "likes.csv", "commentAugSept.csv",
        "entries1.csv", "entries2.csv", "entries3.csv",
    )
    for filename in filenames:
        if not (data_dir / filename).is_file():
            raise FileNotFoundError(data_dir / filename)

    print("Reading users.csv ...", flush=True)
    user_ids = {
        row["id"] for row in read_users(data_dir / "users.csv")
        if not is_missing(row["id"])
    }
    print(f"Unique account IDs: {len(user_ids):,}")

    references = {}
    results = {}
    for name, reader, filename, user_column, post_column in (
        ("likes", read_likes, "likes.csv", "userID", "PostID"),
        ("comments", read_comments, "commentAugSept.csv", "PostedBy", "EntryID"),
    ):
        print(f"Reading {filename} ...", flush=True)
        counts = Counter()
        total = missing_users = 0
        for row in reader(data_dir / filename):
            total += 1
            counts[row[post_column]] += 1
            if row[user_column] not in user_ids:
                missing_users += 1
        references[name] = counts
        results[name] = {"rows": total, "without_user": missing_users}

    total_entries = missing_authors = 0
    for filename in ("entries1.csv", "entries2.csv", "entries3.csv"):
        print(f"Reading {filename} ...", flush=True)
        for number, entry in enumerate(read_entries(data_dir / filename), start=1):
            total_entries += 1
            if entry["PostedBy"] not in user_ids:
                missing_authors += 1
            post_id = entry["PostID"]
            if not is_missing(post_id):
                references["likes"].pop(post_id, None)
                references["comments"].pop(post_id, None)

    results["entries"] = {"rows": total_entries, "without_user": missing_authors}
    for name in ("likes", "comments"):
        results[name]["without_post"] = sum(references[name].values())

    print("Counting unmatched likes per month ...", flush=True)
    likes_per_month = Counter()
    unmatched_per_month = Counter()
    for like in read_likes(data_dir / "likes.csv"):
        timestamp = like["Timestamp"]
        if is_missing(timestamp):
            month = "Missing date"
        else:
            try:
                month = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m")
            except ValueError:
                month = "Invalid date"
        likes_per_month[month] += 1
        if like["PostID"] in references["likes"]:
            unmatched_per_month[month] += 1

    assert sum(unmatched_per_month.values()) == results["likes"]["without_post"]
    results["likes"]["rows_by_month"] = dict(sorted(likes_per_month.items()))
    results["likes"]["without_post_by_month"] = dict(sorted(unmatched_per_month.items()))

    print("\n--- LINK CHECK ---")
    for name in ("entries", "likes", "comments"):
        result = results[name]
        print(f"\n{name}: {result['rows']:,} rows")
        for key, label in (
            ("without_user", "Rows without a matching account in users"),
            ("without_post", "Rows without a matching post in entries"),
        ):
            if key in result:
                count = result[key]
                share = f"{count / result['rows']:.2%}" if result["rows"] else "not applicable"
                print(f"{label}: {count:,} ({share})")
    print("\n--- LIKES WITHOUT A MATCHING POST, BY LIKE MONTH ---")
    print(f"{'Month':16} {'All likes':>12} {'Unmatched':>12} {'Share':>10}")
    for month, total in sorted(likes_per_month.items()):
        unmatched = unmatched_per_month[month]
        print(f"{month:16} {total:12,} {unmatched:12,} {unmatched / total:10.2%}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
    )
    args = parser.parse_args()
    try:
        check_links(args.data_dir)
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        parser.exit(1, f"Link check aborted: {error}\n")


if __name__ == "__main__":
    main()
