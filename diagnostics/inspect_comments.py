import argparse
import csv
import io
from collections import Counter
from itertools import islice
from pathlib import Path


COLUMNS = [
    "PostID",
    "EntryID",
    "PostedBy",
    "SourceName",
    "SourceURL",
    "GeoX",
    "GeoY",
    "Timestamp",
    "Text",
]


def inspect(path):
    limit = 256 * 1024
    print(f"File: {path.name}")
    print(f"Size: {path.stat().st_size / 1024**2:.1f} MiB")

    with path.open("rb") as file:
        raw = file.read(limit + 1)
    truncated = len(raw) > limit
    raw = raw[:limit]

    if truncated:
        last_newline = raw.rfind(b"\n")
        if last_newline < 0:
            raise ValueError("No complete row fits in the sample.")
        raw = raw[:last_newline + 1]

    sample = raw.decode("utf-8-sig")
    if not sample:
        raise ValueError("The file or sample is empty.")

    print("\n--- Start of file as raw text ---")
    print(repr(sample[:800]))
    print("\nDelimiter: tab (\\t).")

    csv.field_size_limit(max(csv.field_size_limit(), limit))
    reader = csv.reader(
        io.StringIO(sample, newline=""),
        delimiter="\t",
        quoting=csv.QUOTE_NONE,
        strict=True,
    )
    rows = list(islice(reader, 100))

    print(f"\n--- Format check of {len(rows)} rows in the sample ---")
    for fields, count in sorted(Counter(len(row) for row in rows).items()):
        print(f"{count} rows have {fields} fields")
    print(f"Expected from the first local sample: {len(COLUMNS)}")

    print("\n--- First three rows ---")
    for number, row in enumerate(rows[:3], start=1):
        print(f"\nRow {number} ({len(row)} fields):")
        matches = len(row) == len(COLUMNS)
        if not matches:
            print("  Wrong number of fields.")
        for index, value in enumerate(row):
            label = COLUMNS[index] if matches else f"Field {index + 1}"
            suffix = " … [display truncated]" if len(value) > 150 else ""
            print(f"  {label:12}: {value[:150]!r}{suffix}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file", type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "commentAugSept.csv",
    )
    args = parser.parse_args()
    try:
        inspect(args.file.expanduser())
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        parser.exit(1, f"\nCould not complete the format sample: {error}\n")


if __name__ == "__main__":
    main()
