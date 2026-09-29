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
        print(f"Filen hittades inte: {path}")
        return
    print(f"Storlek: {path.stat().st_size / 1024**2:.1f} MiB")

    limit = 64 * 1024
    with path.open("rb") as file:
        raw = file.read(limit + 1)
    truncated = len(raw) > limit
    raw = raw[:limit]
    if truncated:
        last_newline = raw.rfind(b"\n")
        if last_newline < 0:
            print("Ingen komplett rad ryms i provet.")
            return
        raw = raw[:last_newline + 1]

    sample = raw.decode("utf-8-sig")
    if not sample:
        print("Filen eller provet är tomt.")
        return
    print("\nBörjan som råtext:")
    print(repr(sample[:600]))

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="\t|;,")
    except csv.Error:
        print("Kunde inte gissa avgränsaren. Undersök råtexten ovan.")
        return

    print(f"\nGissad avgränsare: {dialect.delimiter!r}")
    csv.field_size_limit(max(csv.field_size_limit(), limit))
    reader = csv.reader(io.StringIO(sample, newline=""), dialect, strict=True)
    rows = list(islice(reader, 100))

    print(f"\nFormatkontroll av {len(rows)} rader i provet:")
    for fields, count in sorted(Counter(len(row) for row in rows).items()):
        print(f"{count} rader har {fields} fält")

    print("\nFörsta fem raderna:")
    for number, row in enumerate(rows[:5], start=1):
        print(f"\nRad {number}:")
        for column, value in enumerate(row, start=1):
            suffix = " … [förkortat]" if len(value) > 120 else ""
            print(f"  Fält {column}: {value[:120]!r}{suffix}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path,
                        default=Path(__file__).resolve().parent / "data")
    args = parser.parse_args()
    for name in FILES:
        try:
            inspect(args.data_dir.expanduser() / name)
        except (OSError, UnicodeError, csv.Error) as error:
            print(f"Formatprovet för {name} avbröts: {error}")


if __name__ == "__main__":
    main()
