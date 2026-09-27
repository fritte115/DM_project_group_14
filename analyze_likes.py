import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

file_path = Path(__file__).resolve().parent / "data" / "likes.csv"

total_rows = 0
valid_rows = 0
wrong_field_count = 0
invalid_dates = 0

missing = Counter()
months = Counter()
users = set()
posts = set()

exact_rows = Counter()
pairs = Counter()
pair_timestamps = {}

earliest = None
latest = None
problem_examples = []


def is_missing(value):
    return value.strip().lower() in ("", "null")


with file_path.open(encoding="utf-8-sig", newline="") as file:
    reader = csv.reader(file, delimiter="\t", strict=True)

    for row_number, row in enumerate(reader, start=1):
        total_rows += 1

        if len(row) != 3:
            wrong_field_count += 1
            if len(problem_examples) < 5:
                problem_examples.append(
                    f"Post {row_number}: {len(row)} fält"
                )
            continue

        valid_rows += 1
        user_id, post_id, timestamp = row
        exact_rows[tuple(row)] += 1

        for column, value in zip(
            ["userID", "PostID", "Timestamp"], row
        ):
            if is_missing(value):
                missing[column] += 1

        if not is_missing(user_id):
            users.add(user_id)

        if not is_missing(post_id):
            posts.add(post_id)

        if not is_missing(user_id) and not is_missing(post_id):
            pair = (user_id, post_id)
            pairs[pair] += 1

            if pair not in pair_timestamps:
                pair_timestamps[pair] = set()

            if not is_missing(timestamp):
                pair_timestamps[pair].add(timestamp)

        if is_missing(timestamp):
            continue

        try:
            date = datetime.strptime(
                timestamp, "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            invalid_dates += 1
            if len(problem_examples) < 5:
                problem_examples.append(
                    f"Post {row_number}: ogiltigt datum {timestamp!r}"
                )
            continue

        months[date.strftime("%Y-%m")] += 1
        earliest = date if earliest is None else min(earliest, date)
        latest = date if latest is None else max(latest, date)


extra_exact_rows = sum(count - 1 for count in exact_rows.values())
repeated_pairs = sum(count > 1 for count in pairs.values())
different_timestamps = sum(
    len(timestamps) > 1 for timestamps in pair_timestamps.values()
)

print("\n--- STRUKTUR ---")
print(f"Totalt antal poster:       {total_rows:,}")
print(f"Poster med tre fält:       {valid_rows:,}")
print(f"Fel antal fält:            {wrong_field_count:,}")

print("\n--- ANVÄNDARE OCH INLÄGG ---")
print(f"Unika användar-ID:n:       {len(users):,}")
print(f"Unika inläggs-ID:n:        {len(posts):,}")

print("\n--- SAKNADE VÄRDEN ---")
for column in ["userID", "PostID", "Timestamp"]:
    print(f"{column:12}: {missing[column]:,}")

print("\n--- DATUM ---")
print(f"Tidigaste giltiga datum:  {earliest}")
print(f"Senaste giltiga datum:    {latest}")
print(f"Ogiltiga, ej tomma datum: {invalid_dates:,}")

print("\nAntal poster per månad:")
for month, count in sorted(months.items()):
    print(f"  {month}: {count:,}")

print("\n--- DUBBLETTER ---")
print(f"Extra exakt identiska rader: {extra_exact_rows:,}")
print(f"Återkommande användare–inlägg-par: {repeated_pairs:,}")
print(f"Par med olika tidsstämpeltexter:   {different_timestamps:,}")

if problem_examples:
    print("\n--- EXEMPEL PÅ FORMATPROBLEM ---")
    for example in problem_examples:
        print(example)
