import csv
from collections import defaultdict
from pathlib import Path

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
    stats = defaultdict(lambda: {
        "post_count": 0, "likes_total": 0, "comments_total": 0,
        "posts_with_engagement": 0, "engagement_sq_total": 0,
    })
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
