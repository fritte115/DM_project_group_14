# Final pipeline

Run these stages from the repository root, in order:

```bash
python3 -m pipeline.build_posts
python3 -m pipeline.cluster_users
python3 -m pipeline.follower_check
```

- `build_posts.py` cleans and joins raw posts, likes, comments, and users.
- `cluster_users.py` builds user features, filters the analysis population,
  selects `k`, and fits k-means.
- `follower_check.py` adds follower counts and checks whether follower count
  agrees with engagement-based targeting.
