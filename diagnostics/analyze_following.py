import argparse
import csv
import struct
import tempfile
from collections import Counter
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path


FILES = [("followingAugSept.csv", "\t", 3), ("subscriptions.csv", ",", 2)]
PARTITIONS = 128
RECORD = struct.Struct("<BII")


def missing(value):
    return value.strip().lower() in ("", "null", "\\n")


def read_users(path):
    known = set()
    bad = empty = rows = 0
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.reader(file, delimiter="|", quoting=csv.QUOTE_NONE, strict=True):
            rows += 1
            if len(row) != 5:
                bad += 1
            elif missing(row[0]):
                empty += 1
            else:
                known.add(row[0])
    print(f"users.csv: {rows:,} rows, {len(known):,} unique IDs, "
          f"{bad:,} rows with wrong field count, {empty:,} missing IDs.", flush=True)
    return known


def analyze(data_dir, temp_dir=None):
    for name in ["users.csv", *[item[0] for item in FILES]]:
        if not (data_dir / name).is_file():
            raise FileNotFoundError(f"File not found: {data_dir / name}")
    csv.field_size_limit(16 * 1024 * 1024)
    known = read_users(data_dir / "users.csv")
    codes = {}
    summaries = []

    with tempfile.TemporaryDirectory(prefix="friendfeed_pairs_", dir=temp_dir) as temp:
        parts = [Path(temp) / f"part_{i:03}.bin" for i in range(PARTITIONS)]
        with ExitStack() as stack:
            handles = [stack.enter_context(p.open("wb")) for p in parts]
            for file_index, (name, delimiter, width) in enumerate(FILES):
                s = {"file": name, "rows": 0, "wrong_width": 0, "complete_pairs": 0,
                     "missing_a": 0, "missing_b": 0, "unknown_a_rows": 0,
                     "unknown_b_rows": 0, "missing_dates": 0, "invalid_dates": 0,
                     "self_rows": 0, "months": Counter(), "examples": []}
                ids_a, ids_b, unknown_a, unknown_b = set(), set(), set(), set()
                earliest = latest = None
                print(f"\nReading {name} ...", flush=True)
                with (data_dir / name).open(encoding="utf-8-sig", newline="") as file:
                    reader = csv.reader(file, delimiter=delimiter, quoting=csv.QUOTE_NONE, strict=True)
                    for number, row in enumerate(reader, 1):
                        s["rows"] += 1
                        if len(row) != width:
                            s["wrong_width"] += 1
                            if len(s["examples"]) < 5:
                                s["examples"].append(f"Row {number}: {len(row)} fields")
                            continue

                        a, b = row[:2]
                        converted = []
                        for value, side, ids, unknown in [(a, "a", ids_a, unknown_a),
                                                         (b, "b", ids_b, unknown_b)]:
                            if missing(value):
                                s[f"missing_{side}"] += 1
                                converted.append(None)
                                continue
                            if value not in codes:
                                codes[value] = len(codes)
                            code = codes[value]
                            converted.append(code)
                            ids.add(code)
                            if value not in known:
                                s[f"unknown_{side}_rows"] += 1
                                unknown.add(code)

                        x, y = converted
                        if x is not None and y is not None:
                            s["complete_pairs"] += 1
                            if x == y:
                                s["self_rows"] += 1
                            bucket = (min(x, y) * 1_000_003 + max(x, y)) % PARTITIONS
                            handles[bucket].write(RECORD.pack(file_index, x, y))

                        if width == 3:
                            value = row[2]
                            if missing(value):
                                s["missing_dates"] += 1
                            else:
                                try:
                                    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in value else "%Y-%m-%d %H:%M:%S"
                                    date = datetime.strptime(value, fmt)
                                except ValueError:
                                    s["invalid_dates"] += 1
                                    if len(s["examples"]) < 5:
                                        s["examples"].append(f"Row {number}: invalid date {value!r}")
                                else:
                                    s["months"][date.strftime("%Y-%m")] += 1
                                    earliest = date if earliest is None else min(earliest, date)
                                    latest = date if latest is None else max(latest, date)

                s.update(unique_a=len(ids_a), unique_b=len(ids_b),
                         unknown_a_unique=len(unknown_a), unknown_b_unique=len(unknown_b),
                         earliest=str(earliest) if earliest else None,
                         latest=str(latest) if latest else None,
                         unique_pairs=0, repeated_pairs=0, extra_pair_rows=0, unique_self_pairs=0)
                summaries.append(s)
                del ids_a, ids_b, unknown_a, unknown_b

        del known, codes
        same = reverse = both = 0
        print("\nComparing unique account pairs, one partition at a time ...", flush=True)
        for index, part in enumerate(parts):
            pairs = [set(), set()]
            repeated = [set(), set()]
            with part.open("rb") as file:
                while chunk := file.read(RECORD.size * 50_000):
                    for source, a, b in RECORD.iter_unpack(chunk):
                        key = (a << 32) | b
                        if key in pairs[source]:
                            summaries[source]["extra_pair_rows"] += 1
                            repeated[source].add(key)
                        else:
                            pairs[source].add(key)
                            if a == b:
                                summaries[source]["unique_self_pairs"] += 1
            for source in (0, 1):
                summaries[source]["unique_pairs"] += len(pairs[source])
                summaries[source]["repeated_pairs"] += len(repeated[source])
            for key in pairs[0]:
                reversed_key = ((key & 0xFFFFFFFF) << 32) | (key >> 32)
                match_same = key in pairs[1]
                match_reverse = reversed_key in pairs[1]
                same += match_same
                reverse += match_reverse
                both += match_same and match_reverse
            del pairs, repeated
            part.unlink()

    for s in summaries:
        print(f"\n--- {s['file']} ---")
        labels = [("rows", "All rows"), ("wrong_width", "Wrong field count"),
                  ("complete_pairs", "Rows with both account IDs"),
                  ("unique_a", "Unique IDs in field 1"), ("unique_b", "Unique IDs in field 2"),
                  ("missing_a", "Missing IDs in field 1"), ("missing_b", "Missing IDs in field 2"),
                  ("unknown_a_rows", "Rows with a field 1 ID missing from users"),
                  ("unknown_b_rows", "Rows with a field 2 ID missing from users"),
                  ("unknown_a_unique", "Unique field 1 IDs missing from users"),
                  ("unknown_b_unique", "Unique field 2 IDs missing from users"),
                  ("unique_pairs", "Unique ordered account pairs"),
                  ("repeated_pairs", "Repeated ordered account pairs"),
                  ("extra_pair_rows", "Extra rows with the same ordered pair"),
                  ("self_rows", "Rows where both accounts are the same"),
                  ("unique_self_pairs", "Unique pairs where both accounts are the same")]
        for field, label in labels:
            print(f"{label}: {s[field]:,}")
        if s["file"] == FILES[0][0]:
            print(f"Earliest timestamp: {s['earliest']}")
            print(f"Latest timestamp: {s['latest']}")
            print(f"Missing timestamps: {s['missing_dates']:,}")
            print(f"Invalid, non-missing dates: {s['invalid_dates']:,}")
            for month, count in sorted(s["months"].items()):
                print(f"  {month}: {count:,} rows")
        for example in s["examples"]:
            print(f"FORMAT PROBLEM: {example}")

    print("\n--- OVERLAP BETWEEN THE FILES ---")
    print(f"Same pair (A, B) in subscriptions: {same:,}")
    print(f"Reversed pair (B, A) in subscriptions: {reverse:,}")
    print(f"Both orders in subscriptions: {both:,}")
    print(f"At least one order present: {same + reverse - both:,}")
    return {"files": summaries, "same": same, "reverse": reverse, "both": both}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    parser.add_argument("--temp-dir", type=Path, help="Existing folder with free space for temporary files")
    args = parser.parse_args()
    try:
        analyze(args.data_dir.expanduser(), args.temp_dir.expanduser() if args.temp_dir else None)
    except (OSError, UnicodeError, csv.Error, MemoryError, struct.error) as error:
        raise SystemExit(f"Check aborted ({type(error).__name__}): {error}. "
                         "The data has not been fully checked.") from error


if __name__ == "__main__":
    main()
