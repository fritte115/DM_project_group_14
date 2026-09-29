# DM_project_group_14

# Research Question

Can we identify distinct types of Friendfeed users based on how often they publish content and how intensely their audience engages with it — and which of these user types represent the best-value targets for sponsorship or brand partnerships?

# Rationale

Companies deciding where to spend sponsorship money on social platforms typically default to follower count as a proxy for value — but follower count alone is a poor predictor of actual return: a user with many followers who rarely posts, or whose posts get little reaction, delivers far less exposure per sponsorship dollar than a smaller account with intensely engaged followers. If distinct user types can be identified by combining publication frequency and engagement intensity (rather than raw reach alone), that gives a more defensible, data-driven basis for sponsorship decisions than vanity metrics — which is directly useful to any brand or platform running influencer/creator partnerships.

# Analysis period

- Include posts published from 1 August through 23 September 2010: `2010-08-01 00:00:00 <= Timestamp < 2010-09-24 00:00:00`.
- Count likes and comments from publication time up to, but not including, exactly seven days later. This gives each selected post the same observation window within September.
- Exclude October activity from the analysis. Keep all raw files unchanged.
- Use timestamps as recorded, without timezone conversion. Equal observation windows do not guarantee complete data collection.

The time rules are implemented in `src/transform.py`. `filter_entries` selects posts and converts their timestamps to Python datetime values. `is_response_in_window` checks a response against a post's publication time; both arguments must be datetime values. Invalid or missing timestamps raise an error rather than being silently dropped.

The raw-data checks in `check_links.py` still cover all dates. `build_posts.py` applies the analysis rules to create the post-level response table.

# Cleaning rules

- `clean_users` keeps only `id` and `type`, with one row per account. Both users and groups are retained at this stage. Missing IDs, unknown types and conflicting types for the same ID raise an error. Name and description differences are irrelevant to this account lookup.
- `clean_likes` keeps one like per exact `(userID, PostID)` pair, using the earliest recorded timestamp. This also removes exact duplicates. Timestamps become Python datetime values; missing IDs or invalid timestamps raise an error.
- Deduplicate likes across the full file before applying the seven-day response window. Do not replace an earliest timestamp with a later one just because it fits the window.
- Account and post IDs are not normalized. Responses from accounts absent from `users.csv` are retained when their posts can be matched.
- Entries and comments are not deduplicated: the initial checks found unique entry and comment IDs. Multiple distinct comments by one account on one post remain separate comments.

The cleaning functions do not modify or save raw files. They hold account or like-pair lookups in memory. The post-level join reports likes and comments dated before publication and excludes them from the response counts.

# Build the post table

Run from the project root with Python 3.10 or newer (no third-party packages required):

```bash
python3 build_posts.py
```

Outputs are saved under `data/processed/post_table/`, which is ignored by Git:

- `posts.csv`: one row per selected post, including posts with no qualifying response.
- `report.json`: input file sizes and modification times, analysis rules, row counts, exclusion counts, media-quality counts and output totals.

The script includes only posts whose author is a known `user`. In-period posts by groups or accounts absent from `users.csv` are excluded and counted separately. Likes and comments from accounts absent from `users.csv` can still count. The author's own likes and comments are excluded. Distinct comments from the same account remain separate, including comments with empty text.

| Column | Meaning |
|---|---|
| `post_id` | Original entry ID |
| `author_id` | Original publishing account ID |
| `published_at` | Publication timestamp, as recorded |
| `likes_7d` | Distinct account–post likes within the first seven days, excluding the author |
| `comments_7d` | Comments within the first seven days, excluding the author |
| `has_image` | 1 if `NumImg` is positive, 0 if zero, blank if missing or invalid |
| `has_video` | 1 if `NumVideo` is positive, 0 if zero, blank if missing or invalid |

Media flags reflect the source count fields, not inspection of the linked content. Missing media values must not be treated as zero in later comparisons. Malformed row widths, invalid timestamps and conflicting account types stop the build. The build relies on the initial full-file checks for uniqueness of entry and comment IDs; repeat those checks if the raw dataset changes.

Exclusion categories in the report are mutually exclusive, applied in this order: unmatched post, post outside the publication period, unknown author, group author, response before publication, self-response, response outside the seven-day window. Time and self-response checks therefore apply only to selected posts. `included_unknown_actor` is a subset of included responses, not another exclusion category. Like exclusions are counted after deduplication; `duplicate_rows_removed` reports the removed raw rows separately.

The script reads data in stages and temporarily saves selected posts on disk. In memory it retains account IDs, referenced-post metadata and response counts rather than full entry text. Output row and response totals are reconciled before the completed output folder is made available. Existing output folders are not overwritten; use a different folder for another run:

```bash
python3 build_posts.py --output-dir data/processed/post_table_v2
```

Run the small fixture test with:

```bash
python3 -m unittest discover -s tests -v
```
