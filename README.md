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

The raw-data checks in `check_links.py` still cover all dates. Building the post-level response table is the next step; these helpers alone do not create it.
