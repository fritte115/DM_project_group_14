import csv
from collections import Counter
from pathlib import Path

file_path = Path(__file__).resolve().parent.parent / "data" / "users.csv"

total_rows = 0
valid_rows = 0
wrong_field_count = 0
missing_descriptions = 0
missing_ids = 0

account_types = Counter()
user_ids = Counter()
problem_examples = []

with file_path.open(encoding="utf-8-sig", newline="") as file:
    reader = csv.reader(
        file,
        delimiter="|",
        quoting=csv.QUOTE_NONE,
        strict=True,
    )

    for row_number, row in enumerate(reader, start=1):
        total_rows += 1

        if len(row) != 5:
            wrong_field_count += 1

            if len(problem_examples) < 5:
                problem_examples.append((row_number, len(row)))

            continue

        valid_rows += 1
        user_id, account_type, name, reserved, description = row

        account_types[account_type] += 1

        if user_id.strip().lower() in ("", "null"):
            missing_ids += 1
        else:
            user_ids[user_id] += 1

        if description.strip().lower() in ("", "null"):
            missing_descriptions += 1

repeated_ids = sum(count > 1 for count in user_ids.values())
extra_occurrences = sum(count - 1 for count in user_ids.values())

print("\n--- FILE STRUCTURE ---")
print(f"Total CSV records:             {total_rows:,}")
print(f"Records with five fields:      {valid_rows:,}")
print(f"Records with wrong field count: {wrong_field_count:,}")

if problem_examples:
    print("Examples of malformed records (record number, field count):")
    print(problem_examples)

print("\n--- ACCOUNT TYPES ---")
for account_type, count in account_types.most_common():
    percentage = count / valid_rows * 100
    print(f"{account_type!r}: {count:,} records ({percentage:.1f} %)")

print("\n--- USER IDS ---")
print(f"Records without ID:              {missing_ids:,}")
print(f"Unique non-missing IDs:          {len(user_ids):,}")
print(f"IDs occurring more than once:    {repeated_ids:,}")
print(f"Extra occurrences of those IDs:  {extra_occurrences:,}")

print("\n--- PROFILE DESCRIPTIONS ---")
print(f"Missing description: {missing_descriptions:,}")

if valid_rows:
    percentage = missing_descriptions / valid_rows * 100
    print(f"Share missing descriptions: {percentage:.1f} %")
