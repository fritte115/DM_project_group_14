import argparse
import csv
from collections import Counter
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

    print("Läser users.csv …", flush=True)
    user_ids = {
        row["id"] for row in read_users(data_dir / "users.csv")
        if not is_missing(row["id"])
    }
    print(f"Unika konto-ID:n: {len(user_ids):,}")

    references = {}
    results = {}
    for name, reader, filename, user_column, post_column in (
        ("likes", read_likes, "likes.csv", "userID", "PostID"),
        ("comments", read_comments, "commentAugSept.csv", "PostedBy", "EntryID"),
    ):
        print(f"Läser {filename} …", flush=True)
        counts = Counter()
        total = missing_users = 0
        for row in reader(data_dir / filename):
            total += 1
            counts[row[post_column]] += 1
            if row[user_column] not in user_ids:
                missing_users += 1
            if total % 500_000 == 0:
                print(f"  {total:,} rader lästa", flush=True)
        references[name] = counts
        results[name] = {"rows": total, "without_user": missing_users}

    total_entries = missing_authors = 0
    for filename in ("entries1.csv", "entries2.csv", "entries3.csv"):
        print(f"Läser {filename} …", flush=True)
        for number, entry in enumerate(read_entries(data_dir / filename), start=1):
            total_entries += 1
            if entry["PostedBy"] not in user_ids:
                missing_authors += 1
            post_id = entry["PostID"]
            if not is_missing(post_id):
                references["likes"].pop(post_id, None)
                references["comments"].pop(post_id, None)
            if number % 500_000 == 0:
                print(f"  {number:,} rader lästa", flush=True)

    results["entries"] = {"rows": total_entries, "without_user": missing_authors}
    for name in ("likes", "comments"):
        results[name]["without_post"] = sum(references[name].values())

    print("\n--- KOPPLINGSKONTROLL ---")
    for name in ("entries", "likes", "comments"):
        result = results[name]
        print(f"\n{name}: {result['rows']:,} rader")
        for key, label in (
            ("without_user", "Rader utan matchande konto i users"),
            ("without_post", "Rader utan matchande inlägg i entries"),
        ):
            if key in result:
                count = result[key]
                share = f"{count / result['rows']:.2%}" if result["rows"] else "ej tillämpligt"
                print(f"{label}: {count:,} ({share})")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path(__file__).resolve().parent / "data",
    )
    args = parser.parse_args()
    try:
        check_links(args.data_dir)
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        parser.exit(1, f"Kopplingskontrollen avbröts: {error}\n")


if __name__ == "__main__":
    main()
