# Final pipeline

Run these stages from the repository root, in order:

```bash
python3 -m pipeline.build_posts
python3 -m pipeline.cluster_users
python3 -m pipeline.follower_check
```

- `build_posts.py` cleans and joins raw posts, likes, comments, and users into
  `posts.csv` and the author-responder table `responders.csv`.
- `cluster_users.py` builds user features, filters the analysis population
  (engagement, bots, minimum posts), shrinks mean engagement, counts
  followers, selects `k`, and fits k-means on frequency, intensity and
  audience size.
- `follower_check.py` checks whether follower count agrees with
  engagement-based targeting and ranks recommended targets by distinct
  people reached.

See the "Clustering" section of the top-level README for the features.
