import argparse
import csv
import json
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
            raise FileNotFoundError(f"Hittar inte filen: {path}")

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
        print(f"\nLäser {path.name} …", flush=True)

        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file, delimiter="\t", quoting=csv.QUOTE_NONE, strict=True)
            for row_number, row in enumerate(reader, start=1):
                result["rows"] += 1
                if row_number % 500_000 == 0:
                    print(f"  {row_number:,} rader lästa", flush=True)

                if len(row) != 12:
                    result["wrong_width"] += 1
                    if len(result["problem_examples"]) < 5:
                        result["problem_examples"].append(
                            f"Rad {row_number}: {len(row)} fält, förväntat 12"
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
                            f"Rad {row_number}: ogiltig tidsstämpel {timestamp!r}"
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
    print("\n--- ALLA TRE FILER TILLSAMMANS ---")
    print(f"Totalt antal rader: {combined['rows']:,}")
    print(f"Unika PostID:n: {combined['unique_post_ids']:,}")
    print(f"ID:n som återkommer: {repeated_ids:,}")
    print(f"Extra ID-förekomster: {combined['extra_id_occurrences']:,}")
    print(f"ID:n som finns i flera filer: {combined['ids_in_multiple_files']:,}")
    for names, count in sorted(overlaps.items()):
        print(f"  Exakt dessa filer: {names}: {count:,} ID:n")
    if example_ids:
        print(f"Exempel på ID:n i flera filer: {example_ids}")
    print("\nAntal rader per månad, alla filer:")
    for month, count in sorted(combined_months.items()):
        print(f"  {month}: {count:,}")

    return {"files": results, "combined": combined}


def print_file_result(result):
    print(f"\n--- {result['file']} ---")
    print(f"Antal rader: {result['rows']:,}")
    print(f"Rader med 12 fält: {result['valid_width']:,}")
    print(f"Fel antal fält: {result['wrong_width']:,}")
    print(f"Unika PostID:n i filen: {result['unique_post_ids']:,}")
    print(f"Extra ID-förekomster inom filen: {result['extra_id_occurrences_within_file']:,}")
    for column, count in result["missing"].items():
        print(f"Saknade {column}: {count:,}")
    print(f"Ogiltiga, ej saknade datum: {result['invalid_dates']:,}")
    print(f"Tidigaste datum: {result['earliest']}")
    print(f"Senaste datum: {result['latest']}")
    print("Antal rader per månad:")
    for month, count in result["months"].items():
        print(f"  {month}: {count:,}")
    for example in result["problem_examples"]:
        print(f"  FORMATPROBLEM: {example}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--report", type=Path, help="Valfri sökväg till en ny JSON-fil med resultaten")
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error("Rapportfilen finns redan. Välj ett nytt namn.")
    try:
        result = analyze(args.data_dir.expanduser())
    except (OSError, UnicodeError, csv.Error, MemoryError) as error:
        raise SystemExit(
            f"Kontrollen avbröts ({type(error).__name__}): {error}. "
            "Eventuella delresultat ovan täcker inte hela materialet."
        ) from error
    if args.report:
        with args.report.open("x", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        print(f"\nResultaten sparades i {args.report}")


if __name__ == "__main__":
    main()
