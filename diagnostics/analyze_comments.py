import argparse
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


COLUMNS = ["PostID", "EntryID", "PostedBy", "SourceName", "SourceURL",
           "GeoX", "GeoY", "Timestamp", "Text"]


def is_missing(value):
    return value.strip().lower() in ("", "null", "\\n")


def analyze(path):
    rows = valid_rows = wrong_width = invalid_dates = id_mismatches = 0
    missing = Counter()
    months = Counter()
    comment_ids = Counter()
    entry_ids = set()
    authors = set()
    problems = []
    earliest = latest = None
    csv.field_size_limit(16 * 1024 * 1024)

    print(f"Reading {path.name} ...", flush=True)
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter="\t", quoting=csv.QUOTE_NONE, strict=True)
        for number, row in enumerate(reader, start=1):
            rows += 1
            if len(row) != 9:
                wrong_width += 1
                if len(problems) < 5:
                    problems.append(f"Row {number}: {len(row)} fields, expected 9")
                continue

            valid_rows += 1
            for column, value in zip(COLUMNS, row):
                if is_missing(value):
                    missing[column] += 1

            comment_id, entry_id, author = row[:3]
            timestamp = row[7]
            if not is_missing(comment_id):
                comment_ids[comment_id] += 1
            if not is_missing(entry_id):
                entry_ids.add(entry_id)
            if not is_missing(author):
                authors.add(author)

            if not is_missing(comment_id) and not is_missing(entry_id):
                prefix, marker, suffix = comment_id.partition("/c/")
                if not marker or not suffix or prefix != entry_id:
                    id_mismatches += 1

            if is_missing(timestamp):
                continue
            try:
                date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                invalid_dates += 1
                if len(problems) < 5:
                    problems.append(f"Row {number}: invalid date {timestamp!r}")
                continue
            months[date.strftime("%Y-%m")] += 1
            earliest = date if earliest is None else min(earliest, date)
            latest = date if latest is None else max(latest, date)

    repeated_ids = sum(count > 1 for count in comment_ids.values())
    extra_occurrences = sum(count - 1 for count in comment_ids.values())

    print("\n--- STRUCTURE ---")
    print(f"Total rows: {rows:,}")
    print(f"Rows with nine fields: {valid_rows:,}")
    print(f"Wrong field count: {wrong_width:,}")

    print("\n--- COMMENTS, POSTS AND ACCOUNTS ---")
    print(f"Unique comment IDs (PostID): {len(comment_ids):,}")
    print(f"Unique referenced post IDs (EntryID): {len(entry_ids):,}")
    print(f"Unique author IDs (PostedBy): {len(authors):,}")
    print(f"Repeated comment IDs: {repeated_ids:,}")
    print(f"Extra occurrences of comment IDs: {extra_occurrences:,}")
    print(f"Deviations from the ID format EntryID/c/comment-ID: {id_mismatches:,}")

    print("\n--- MISSING VALUES ---")
    for column in COLUMNS:
        print(f"{column:12}: {missing[column]:,}")

    print("\n--- DATES ---")
    print(f"Earliest valid date: {earliest}")
    print(f"Latest valid date: {latest}")
    print(f"Invalid, non-missing dates: {invalid_dates:,}")
    print("Rows per month:")
    for month, count in sorted(months.items()):
        print(f"  {month}: {count:,}")
    print(f"Rows in August–September 2010: {months['2010-08'] + months['2010-09']:,}")

    if problems:
        print("\n--- EXAMPLES OF FORMAT PROBLEMS ---")
        for problem in problems:
            print(problem)

    return {"rows": rows, "valid_rows": valid_rows, "wrong_width": wrong_width,
            "missing": dict(missing), "months": dict(months), "invalid_dates": invalid_dates,
            "unique_comments": len(comment_ids), "unique_entries": len(entry_ids),
            "unique_authors": len(authors), "repeated_ids": repeated_ids,
            "extra_occurrences": extra_occurrences, "id_mismatches": id_mismatches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "commentAugSept.csv")
    args = parser.parse_args()
    try:
        analyze(args.file.expanduser())
    except (OSError, UnicodeError, csv.Error, MemoryError) as error:
        raise SystemExit(f"Check aborted ({type(error).__name__}): {error}. "
                         "The data has not been fully checked.") from error


if __name__ == "__main__":
    main()
