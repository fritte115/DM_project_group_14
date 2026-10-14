import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

file_path = Path(__file__).resolve().parent.parent / "data" / "likes.csv"

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
                    f"Record {row_number}: {len(row)} fields"
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
                    f"Record {row_number}: invalid date {timestamp!r}"
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

print("\n--- STRUCTURE ---")
print(f"Total records:             {total_rows:,}")
print(f"Records with three fields: {valid_rows:,}")
print(f"Wrong field count:         {wrong_field_count:,}")

print("\n--- USERS AND POSTS ---")
print(f"Unique user IDs:           {len(users):,}")
print(f"Unique post IDs:           {len(posts):,}")

print("\n--- MISSING VALUES ---")
for column in ["userID", "PostID", "Timestamp"]:
    print(f"{column:12}: {missing[column]:,}")

print("\n--- DATES ---")
print(f"Earliest valid date:       {earliest}")
print(f"Latest valid date:         {latest}")
print(f"Invalid, non-empty dates:  {invalid_dates:,}")

print("\nRecords per month:")
for month, count in sorted(months.items()):
    print(f"  {month}: {count:,}")

print("\n--- DUPLICATES ---")
print(f"Extra exactly identical rows:        {extra_exact_rows:,}")
print(f"Repeated user–post pairs:            {repeated_pairs:,}")
print(f"Pairs with different timestamp text: {different_timestamps:,}")

if problem_examples:
    print("\n--- EXAMPLES OF FORMAT PROBLEMS ---")
    for example in problem_examples:
        print(example)
