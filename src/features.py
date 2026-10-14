from __future__ import annotations
import csv
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from src.transform import POST_END, POST_START

WINDOW_DAYS = (POST_END - POST_START).days

def read_posts(path: str | Path):
    path = Path(path).expanduser()
    csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            yield {
                "post_id": row["post_id"],
                "author_id": row["author_id"],
                "published_at": row["published_at"],
                "likes_7d": int(row["likes_7d"]),
                "comments_7d": int(row["comments_7d"]),
                "has_image": row["has_image"],
                "has_video": row["has_video"],
            }

def build_user_features(posts):
    stats = defaultdict(lambda: {"post_count": 0, "likes_total": 0, "comments_total": 0, "posts_with_engagement": 0, "engagement_sq_total": 0})
    
    for post in posts:
        author = stats[post["author_id"]]
        engagement = post["likes_7d"] + post["comments_7d"]
        author["post_count"] += 1
        author["likes_total"] += post["likes_7d"]
        author["comments_total"] += post["comments_7d"]
        author["engagement_sq_total"] += engagement ** 2
        if engagement:
            author["posts_with_engagement"] += 1

    features = {}
    for author_id, author in stats.items():
        post_count = author["post_count"]
        engagement_total = author["likes_total"] + author["comments_total"]
        mean_engagement = engagement_total / post_count
        mean_engagement_sq = author["engagement_sq_total"] / post_count
        variance = max(0.0, mean_engagement_sq - mean_engagement ** 2)
        features[author_id] = {
            "post_count": post_count,
            "likes_total": author["likes_total"],
            "comments_total": author["comments_total"],
            "engagement_total": engagement_total,
            "posts_with_engagement": author["posts_with_engagement"],
            "engagement_rate": author["posts_with_engagement"] / post_count,
            "mean_engagement": mean_engagement,
            "std_engagement": variance ** 0.5,
            "posts_per_day": post_count / WINDOW_DAYS,
        }
    return features

def detect_bots(features, max_posts_per_day):
    return {
        author_id for author_id, f in features.items()
        if f["posts_per_day"] > max_posts_per_day
    }

def read_responders(path: str | Path):
    path = Path(path).expanduser()
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            yield {
                "author_id": row["author_id"],
                "responder_id": row["responder_id"],
                "responses_7d": int(row["responses_7d"]),
            }

def count_unique_responders(responders):
    # responders.csv has one row per (author, responder) pair, so rows per author = distinct responders.
    return dict(Counter(row["author_id"] for row in responders))

def count_followers(following, subscriptions, authors):
    # Followers are the union of both files, so an account listed in both counts once.
    followers = {author_id: set() for author_id in authors}
    for row in following:
        if row["followed_id"] in followers:
            followers[row["followed_id"]].add(row["follower_id"])
    for row in subscriptions:
        if row["subscribed_to_id"] in followers:
            followers[row["subscribed_to_id"]].add(row["subscriber_id"])
    return {author_id: len(ids) for author_id, ids in followers.items()}

def estimate_shrinkage(post_counts, means, stds):
    # Empirical Bayes (normal-normal): an author's observed mean is their true mean plus
    # sampling noise with variance within / post_count. Returns the population mean and
    # prior_posts = within / between, i.e. how many posts an author needs before their own
    # mean weighs as much as the population mean.
    n, x, s = (np.asarray(values, dtype=float) for values in (post_counts, means, stds))
    prior_mean = float((n * x).sum() / n.sum())
    within = float((s ** 2 * n).sum() / n.sum())
    between = float(x.var() - np.mean(s ** 2 / n))
    if between <= 0:
        raise ValueError("Between-author variance is not positive; shrinkage cannot be estimated.")
    return prior_mean, within / between

def shrink_mean(engagement_total, post_count, prior_mean, prior_posts):
    return (engagement_total + prior_posts * prior_mean) / (post_count + prior_posts)