import argparse
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

FILES = ["entries1.csv", "entries2.csv", "entries3.csv"]
REPEATED = 1 << len(FILES)

def is_missing(value):
    return value.strip().lower() in ("", "null", "\\n")


def analyze(data_dir):
    paths = [data_dir / name for name in FILES]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

    seen = {}
    results = []
    csv.field_size_limit(16 * 1024 * 1024)

    for index, path in enumerate(paths):
        flag = 1 << index
        result = {
            "file": path.name,
            "rows": 0,
            "valid_width": 0,
            "wrong_width": 0,
            "missing": {"PostID": 0, "PostedBy": 0, "Timestamp": 0},
            "invalid_dates": 0,
            "unique_post_ids": 0,
            "extra_id_occurrences_within_file": 0,
            "months": Counter(),
            "problem_examples": [],
        }
        earliest = latest = None
        print(f"\nReading {path.name} ...", flush=True)

        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file, delimiter="\t", quoting=csv.QUOTE_NONE, strict=True)
            for row_number, row in enumerate(reader, start=1):
                result["rows"] += 1

                if len(row) != 12:
                    result["wrong_width"] += 1
                    if len(result["problem_examples"]) < 5:
                        result["problem_examples"].append(
                            f"Row {row_number}: {len(row)} fields, expected 12"
                        )
                    continue

                result["valid_width"] += 1
                post_id, author, timestamp = row[0], row[1], row[6]
                for column, value in [("PostID", post_id), ("PostedBy", author), ("Timestamp", timestamp)]:
                    if is_missing(value):
                        result["missing"][column] += 1

                if not is_missing(post_id):
                    previous = seen.get(post_id, 0)
                    if previous & flag:
                        result["extra_id_occurrences_within_file"] += 1
                    else:
                        result["unique_post_ids"] += 1
                    seen[post_id] = previous | flag | (REPEATED if previous else 0)

                if is_missing(timestamp):
                    continue
                try:
                    date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    result["invalid_dates"] += 1
                    if len(result["problem_examples"]) < 5:
                        result["problem_examples"].append(
                            f"Row {row_number}: invalid timestamp {timestamp!r}"
                        )
                    continue

                result["months"][date.strftime("%Y-%m")] += 1
                earliest = date if earliest is None else min(earliest, date)
                latest = date if latest is None else max(latest, date)

        result["earliest"] = str(earliest) if earliest is not None else None
        result["latest"] = str(latest) if latest is not None else None
        result["months"] = dict(sorted(result["months"].items()))
        results.append(result)
        print_file_result(result)

    file_masks = (1 << len(FILES)) - 1
    overlaps = Counter()
    repeated_ids = 0
    example_ids = []
    for post_id, flags in seen.items():
        if flags & REPEATED:
            repeated_ids += 1
        mask = flags & file_masks
        if mask & (mask - 1):
            names = " + ".join(name for i, name in enumerate(FILES) if mask & (1 << i))
            overlaps[names] += 1
            if len(example_ids) < 5:
                example_ids.append(post_id)

    total_id_rows = sum(r["valid_width"] - r["missing"]["PostID"] for r in results)
    combined_months = Counter()
    for result in results:
        combined_months.update(result["months"])

    combined = {
        "rows": sum(r["rows"] for r in results),
        "unique_post_ids": len(seen),
        "repeated_post_ids": repeated_ids,
        "extra_id_occurrences": total_id_rows - len(seen),
        "ids_in_multiple_files": sum(overlaps.values()),
        "exact_file_combinations": dict(sorted(overlaps.items())),
        "overlap_example_ids": example_ids,
        "months": dict(sorted(combined_months.items())),
    }
    print("\n--- ALL THREE FILES COMBINED ---")
    print(f"Total rows: {combined['rows']:,}")
    print(f"Unique PostIDs: {combined['unique_post_ids']:,}")
    print(f"Repeated IDs: {repeated_ids:,}")
    print(f"Extra ID occurrences: {combined['extra_id_occurrences']:,}")
    print(f"IDs present in several files: {combined['ids_in_multiple_files']:,}")
    for names, count in sorted(overlaps.items()):
        print(f"  Exactly these files: {names}: {count:,} IDs")
    if example_ids:
        print(f"Examples of IDs in several files: {example_ids}")
    print("\nRows per month, all files:")
    for month, count in sorted(combined_months.items()):
        print(f"  {month}: {count:,}")

    return {"files": results, "combined": combined}


def print_file_result(result):
    print(f"\n--- {result['file']} ---")
    print(f"Rows: {result['rows']:,}")
    print(f"Rows with 12 fields: {result['valid_width']:,}")
    print(f"Wrong field count: {result['wrong_width']:,}")
    print(f"Unique PostIDs in the file: {result['unique_post_ids']:,}")
    print(f"Extra ID occurrences within the file: {result['extra_id_occurrences_within_file']:,}")
    for column, count in result["missing"].items():
        print(f"Missing {column}: {count:,}")
    print(f"Invalid, non-missing dates: {result['invalid_dates']:,}")
    print(f"Earliest date: {result['earliest']}")
    print(f"Latest date: {result['latest']}")
    print("Rows per month:")
    for month, count in result["months"].items():
        print(f"  {month}: {count:,}")
    for example in result["problem_examples"]:
        print(f"  FORMAT PROBLEM: {example}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    args = parser.parse_args()
    try:
        analyze(args.data_dir.expanduser())
    except (OSError, UnicodeError, csv.Error, MemoryError) as error:
        raise SystemExit(
            f"Check aborted ({type(error).__name__}): {error}. "
            "Any partial results above do not cover all the data."
        ) from error


if __name__ == "__main__":
    main()
