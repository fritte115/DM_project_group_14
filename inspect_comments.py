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
    print(f"Fil: {path.name}")
    print(f"Storlek: {path.stat().st_size / 1024**2:.1f} MiB")

    with path.open("rb") as file:
        raw = file.read(limit + 1)
    truncated = len(raw) > limit
    raw = raw[:limit]

    if truncated:
        last_newline = raw.rfind(b"\n")
        if last_newline < 0:
            raise ValueError("Ingen komplett rad ryms i provet.")
        raw = raw[:last_newline + 1]

    sample = raw.decode("utf-8-sig")
    if not sample:
        raise ValueError("Filen eller provet är tomt.")

    print("\n--- Början av filen som råtext ---")
    print(repr(sample[:800]))
    print("\nAvgränsare: tab (\\t).")

    csv.field_size_limit(max(csv.field_size_limit(), limit))
    reader = csv.reader(
        io.StringIO(sample, newline=""),
        delimiter="\t",
        quoting=csv.QUOTE_NONE,
        strict=True,
    )
    rows = list(islice(reader, 100))

    print(f"\n--- Formatkontroll av {len(rows)} rader i provet ---")
    for fields, count in sorted(Counter(len(row) for row in rows).items()):
        print(f"{count} rader har {fields} fält")
    print(f"Förväntat antal utifrån det första lokala provet: {len(COLUMNS)}")

    print("\n--- De första tre raderna ---")
    for number, row in enumerate(rows[:3], start=1):
        print(f"\nRad {number} ({len(row)} fält):")
        matches = len(row) == len(COLUMNS)
        if not matches:
            print("  Fel antal fält.")
        for index, value in enumerate(row):
            label = COLUMNS[index] if matches else f"Fält {index + 1}"
            suffix = " … [visningen förkortad]" if len(value) > 150 else ""
            print(f"  {label:12}: {value[:150]!r}{suffix}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file", type=Path,
        default=Path(__file__).resolve().parent / "data" / "commentAugSept.csv",
    )
    args = parser.parse_args()
    try:
        inspect(args.file.expanduser())
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        parser.exit(1, f"\nKunde inte slutföra formatprovet: {error}\n")


if __name__ == "__main__":
    main()
