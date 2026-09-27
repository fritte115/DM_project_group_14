import argparse
import csv
import io
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument(
    "--file",
    type=Path,
    default=Path(__file__).resolve().parent / "data" / "entries3.csv",
)
args = parser.parse_args()
file_path = args.file.expanduser()

print(f"Fil: {file_path.name}")
print(f"Storlek: {file_path.stat().st_size / 1024**2:.1f} MiB")

with file_path.open("rb") as file:
    raw = file.read(65537)

truncated = len(raw) > 65536
raw = raw[:65536]

if truncated:
    last_newline = raw.rfind(b"\n")
    if last_newline == -1:
        raise ValueError("Ingen hel rad ryms i provet.")
    raw = raw[:last_newline + 1]

sample = raw.decode("utf-8-sig")

if not sample:
    raise ValueError("Filen eller provet är tomt.")

print("\n--- Början som råtext ---")
print(repr(sample[:1000]))

try:
    dialect = csv.Sniffer().sniff(sample, delimiters="|;\t,")
    separator = dialect.delimiter
except csv.Error:
    raise ValueError(
        "Kunde inte gissa avgränsaren."
    ) from None

print(f"\nGissad avgränsare: {separator!r}")

reader = csv.reader(
    io.StringIO(sample, newline=""),
    delimiter=separator,
    quoting=csv.QUOTE_NONE,
)

rows = []

for row in reader:
    if row:
        rows.append(row)
    if len(rows) == 100:
        break

print(f"\n--- Formatkontroll av {len(rows)} rader i provet ---")

for fields, count in sorted(Counter(len(row) for row in rows).items()):
    print(f"{count} rader har {fields} fält")

print("\n--- De första tre raderna, uppdelade i fält ---")

for number, row in enumerate(rows[:3], start=1):
    print(f"\nRad {number} ({len(row)} fält):")

    for column, value in enumerate(row, start=1):
        preview = repr(value[:150])
        suffix = " … [förkortat]" if len(value) > 150 else ""
        print(f"  Fält {column:2}: {preview}{suffix}")
