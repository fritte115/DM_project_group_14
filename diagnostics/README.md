# Raw-data diagnostics

These scripts document the initial inspection and validation of the source
files. They are not stages of the final clustering pipeline.

- `inspect_*.py`: small format samples used to identify delimiters and columns.
- `analyze_*.py`: complete-file checks for missing values, duplicates, dates,
  and malformed rows.
- `check_links.py`: verifies account and post references across files.

Run a diagnostic from the repository root, for example:

```bash
python3 -m diagnostics.inspect_comments
python3 -m diagnostics.analyze_entries
python3 -m diagnostics.check_links
```
