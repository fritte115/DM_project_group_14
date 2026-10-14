import argparse
import csv
import io
from collections import Counter
from itertools import islice
from pathlib import Path


FILES = ["followingAugSept.csv", "subscriptions.csv"]


def inspect(path):
    print(f"\n--- {path.name} ---")
    if not path.is_file():
        print(f"File not found: {path}")
        return
    print(f"Size: {path.stat().st_size / 1024**2:.1f} MiB")

    limit = 64 * 1024
    with path.open("rb") as file:
        raw = file.read(limit + 1)
    truncated = len(raw) > limit
    raw = raw[:limit]
    if truncated:
        last_newline = raw.rfind(b"\n")
        if last_newline < 0:
            print("No complete row fits in the sample.")
            return
        raw = raw[:last_newline + 1]

    sample = raw.decode("utf-8-sig")
    if not sample:
        print("The file or sample is empty.")
        return
    print("\nStart of file as raw text:")
    print(repr(sample[:600]))

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="\t|;,")
    except csv.Error:
        print("Could not detect the delimiter. Inspect the raw text above.")
        return

    print(f"\nDetected delimiter: {dialect.delimiter!r}")
    csv.field_size_limit(max(csv.field_size_limit(), limit))
    reader = csv.reader(io.StringIO(sample, newline=""), dialect, strict=True)
    rows = list(islice(reader, 100))

    print(f"\nFormat check of {len(rows)} rows in the sample:")
    for fields, count in sorted(Counter(len(row) for row in rows).items()):
        print(f"{count} rows have {fields} fields")

    print("\nFirst five rows:")
    for number, row in enumerate(rows[:5], start=1):
        print(f"\nRow {number}:")
        for column, value in enumerate(row, start=1):
            suffix = " … [truncated]" if len(value) > 120 else ""
            print(f"  Field {column}: {value[:120]!r}{suffix}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data")
    args = parser.parse_args()
    for name in FILES:
        try:
            inspect(args.data_dir.expanduser() / name)
        except (OSError, UnicodeError, csv.Error) as error:
            print(f"Format sample for {name} was aborted: {error}")


if __name__ == "__main__":
    main()
