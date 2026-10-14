# Final pipeline

Run these stages from the repository root, in order:

```bash
python3 -m pipeline.build_posts
python3 -m pipeline.cluster_users
python3 -m pipeline.follower_check
```

- `build_posts.py` cleans and joins raw posts, likes, comments, and users.
- `cluster_users.py` builds user features, filters the analysis population,
  selects `k`, fits k-means, and writes both 2D and 3D cluster figures.
- `follower_check.py` adds follower counts and checks whether follower count
  agrees with engagement-based targeting.

The 3D figure is saved as `reports/clusters/user_clusters_3d.png`. Its axes are
the same transformed posting-frequency, mean-engagement, and
engagement-variability features used to fit k-means.

An interactive version is saved as
`reports/clusters/user_clusters_3d_interactive.html`. Open it in a browser to
rotate, zoom, reset the camera, hide individual clusters, or toggle the
steady high-engagement highlight. Outlined points are regular publishers
with high mean reactions and relatively low variability, so they are not
one-hit wonders. The page is self-contained and does not require an
internet connection.
