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
    print(f"users.csv: {rows:,} rader, {len(known):,} unika ID:n, "
          f"{bad:,} rader med fel fältantal, {empty:,} saknade ID:n.", flush=True)
    return known


def analyze(data_dir, temp_dir=None):
    for name in ["users.csv", *[item[0] for item in FILES]]:
        if not (data_dir / name).is_file():
            raise FileNotFoundError(f"Hittar inte {data_dir / name}")
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
                print(f"\nLäser {name} …", flush=True)
                with (data_dir / name).open(encoding="utf-8-sig", newline="") as file:
                    reader = csv.reader(file, delimiter=delimiter, quoting=csv.QUOTE_NONE, strict=True)
                    for number, row in enumerate(reader, 1):
                        s["rows"] += 1
                        if number % 1_000_000 == 0:
                            print(f"  {number:,} rader lästa", flush=True)
                        if len(row) != width:
                            s["wrong_width"] += 1
                            if len(s["examples"]) < 5:
                                s["examples"].append(f"Rad {number}: {len(row)} fält")
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
                                        s["examples"].append(f"Rad {number}: ogiltigt datum {value!r}")
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
        print("\nJämför unika kontopar, en del i taget …", flush=True)
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
            if (index + 1) % 16 == 0:
                print(f"  {index + 1}/{PARTITIONS} delar klara", flush=True)
            del pairs, repeated
            part.unlink()

    for s in summaries:
        print(f"\n--- {s['file']} ---")
        labels = [("rows", "Alla rader"), ("wrong_width", "Fel antal fält"),
                  ("complete_pairs", "Rader med båda konto-ID:n"),
                  ("unique_a", "Unika ID:n i fält 1"), ("unique_b", "Unika ID:n i fält 2"),
                  ("missing_a", "Saknade ID:n i fält 1"), ("missing_b", "Saknade ID:n i fält 2"),
                  ("unknown_a_rows", "Rader med ID i fält 1 som saknas i users"),
                  ("unknown_b_rows", "Rader med ID i fält 2 som saknas i users"),
                  ("unknown_a_unique", "Unika ID:n i fält 1 som saknas i users"),
                  ("unknown_b_unique", "Unika ID:n i fält 2 som saknas i users"),
                  ("unique_pairs", "Unika ordnade kontopar"),
                  ("repeated_pairs", "Ordnade kontopar som återkommer"),
                  ("extra_pair_rows", "Extra rader med samma ordnade kontopar"),
                  ("self_rows", "Rader där båda kontona är samma"),
                  ("unique_self_pairs", "Unika par där båda kontona är samma")]
        for field, label in labels:
            print(f"{label}: {s[field]:,}")
        if s["file"] == FILES[0][0]:
            print(f"Tidigaste tidsstämpel: {s['earliest']}")
            print(f"Senaste tidsstämpel: {s['latest']}")
            print(f"Saknade tidsstämplar: {s['missing_dates']:,}")
            print(f"Ogiltiga, ej saknade datum: {s['invalid_dates']:,}")
            for month, count in sorted(s["months"].items()):
                print(f"  {month}: {count:,} rader")
        for example in s["examples"]:
            print(f"FORMATPROBLEM: {example}")

    print("\n--- ÖVERLAPP MELLAN FILERNA ---")
    print(f"Samma par (A, B) finns i subscriptions: {same:,}")
    print(f"Omvänt par (B, A) finns i subscriptions: {reverse:,}")
    print(f"Båda ordningarna finns i subscriptions: {both:,}")
    print(f"Minst en ordning finns: {same + reverse - both:,}")
    return {"files": summaries, "same": same, "reverse": reverse, "both": both}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--temp-dir", type=Path, help="Befintlig mapp med ledigt utrymme för temporära filer")
    args = parser.parse_args()
    try:
        analyze(args.data_dir.expanduser(), args.temp_dir.expanduser() if args.temp_dir else None)
    except (OSError, UnicodeError, csv.Error, MemoryError, struct.error) as error:
        raise SystemExit(f"Kontrollen avbröts ({type(error).__name__}): {error}. "
                         "Materialet är inte fullständigt kontrollerat.") from error


if __name__ == "__main__":
    main()
