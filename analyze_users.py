import csv
from collections import Counter
from pathlib import Path

file_path = Path(__file__).resolve().parent / "data" / "users.csv"

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

print("\n--- FILENS STRUKTUR ---")
print(f"Totalt antal CSV-poster:       {total_rows:,}")
print(f"Poster med fem fält:           {valid_rows:,}")
print(f"Poster med fel antal fält:     {wrong_field_count:,}")

if problem_examples:
    print("Exempel på avvikande poster (postnummer, antal fält):")
    print(problem_examples)

print("\n--- KONTOTYPER ---")
for account_type, count in account_types.most_common():
    percentage = count / valid_rows * 100
    print(f"{account_type!r}: {count:,} poster ({percentage:.1f} %)")

print("\n--- ANVÄNDAR-ID ---")
print(f"Poster utan ID:                {missing_ids:,}")
print(f"Antal unika, icke-saknade ID:n: {len(user_ids):,}")
print(f"ID:n som förekommer flera gånger: {repeated_ids:,}")
print(f"Extra förekomster av dessa ID:n:  {extra_occurrences:,}")

print("\n--- PROFILBESKRIVNINGAR ---")
print(f"Saknad beskrivning: {missing_descriptions:,}")

if valid_rows:
    percentage = missing_descriptions / valid_rows * 100
    print(f"Andel saknade beskrivningar: {percentage:.1f} %")
