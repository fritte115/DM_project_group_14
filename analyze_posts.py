import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.features import WINDOW_DAYS, build_user_features, read_posts


def load_posts(path):
    return pd.read_csv(
        path,
        dtype={
            "post_id": str, "author_id": str, "likes_7d": "int64", "comments_7d": "int64",
            "has_image": str, "has_video": str,
        },
        parse_dates=["published_at"],
        keep_default_na=False,
    )


def check_issues(posts):
    issues = {
        "rows": len(posts),
        "duplicate_post_id": int(posts["post_id"].duplicated().sum()),
        "negative_likes_7d": int((posts["likes_7d"] < 0).sum()),
        "negative_comments_7d": int((posts["comments_7d"] < 0).sum()),
        "timestamp_out_of_period": int(
            ((posts["published_at"] < "2010-08-01") | (posts["published_at"] >= "2010-09-24")).sum()
        ),
        "has_image_blank": int((posts["has_image"] == "").sum()),
        "has_video_blank": int((posts["has_video"] == "").sum()),
        "zero_response_posts": int(((posts["likes_7d"] == 0) & (posts["comments_7d"] == 0)).sum()),
        "zero_response_share": float(((posts["likes_7d"] == 0) & (posts["comments_7d"] == 0)).mean()),
    }
    return issues


def plot_engagement_histograms(posts, output_dir):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, column in zip(axes, ("likes_7d", "comments_7d")):
        values = np.log1p(posts[column])
        ax.hist(values, bins=40, color="#4C72B0")
        ax.set_title(f"log1p({column})")
        ax.set_xlabel("log(1 + count)")
        ax.set_ylabel("posts")
    fig.suptitle("Distribution of 7-day engagement (log scale, zero-heavy)")
    fig.tight_layout()
    fig.savefig(output_dir / "engagement_histograms.png", dpi=150)
    plt.close(fig)


def plot_engagement_boxplots(posts, output_dir):
    fig, ax = plt.subplots(figsize=(6, 4))
    data = [np.log1p(posts["likes_7d"]), np.log1p(posts["comments_7d"])]
    ax.boxplot(data, tick_labels=["log1p(likes_7d)", "log1p(comments_7d)"])
    ax.set_title("Engagement outliers (log scale)")
    fig.tight_layout()
    fig.savefig(output_dir / "engagement_boxplots.png", dpi=150)
    plt.close(fig)


def plot_media_bar(posts, output_dir):
    fig, ax = plt.subplots(figsize=(5, 4))
    no_media = (posts["has_image"] == "0") & (posts["has_video"] == "0")
    labels = ["has_image", "has_video", "no_media"]
    shares = [
        (posts["has_image"] == "1").sum() / len(posts),
        (posts["has_video"] == "1").sum() / len(posts),
        no_media.sum() / len(posts),
    ]
    ax.bar(labels, shares, color="#55A868")
    ax.set_ylabel("share of posts")
    ax.set_ylim(0, 1)
    ax.set_title("Posts containing media")
    fig.tight_layout()
    fig.savefig(output_dir / "media_shares.png", dpi=150)
    plt.close(fig)


def plot_posting_frequency(posts_path, output_dir):
    features = build_user_features(read_posts(posts_path))
    posts_per_day = np.array([f["posts_per_day"] for f in features.values()])

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(np.log1p(posts_per_day), bins=40, color="#C44E52")
    ax.set_title(f"Posting frequency per author over {WINDOW_DAYS} days (log scale)")
    ax.set_xlabel("log(1 + posts per day)")
    ax.set_ylabel("authors")
    fig.tight_layout()
    fig.savefig(output_dir / "posting_frequency_histogram.png", dpi=150)
    plt.close(fig)

    top10 = sorted(features.items(), key=lambda item: item[1]["post_count"], reverse=True)[:10]
    return {
        "unique_authors": len(features),
        "posts_per_day_median": float(np.median(posts_per_day)),
        "posts_per_day_p99": float(np.percentile(posts_per_day, 99)),
        "top_10_most_frequent_authors": [
            {"author_id": author_id, "post_count": f["post_count"], "posts_per_day": f["posts_per_day"]}
            for author_id, f in top10
        ],
    }


def generate_report(posts_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Läser posts.csv …", flush=True)
    posts = load_posts(posts_path)

    print("Kontrollerar datakvalitet …", flush=True)
    issues = check_issues(posts)

    print("Ritar histogram över engagemang …", flush=True)
    plot_engagement_histograms(posts, output_dir)
    plot_engagement_boxplots(posts, output_dir)
    plot_media_bar(posts, output_dir)

    print("Beräknar publiceringsfrekvens per konto …", flush=True)
    frequency = plot_posting_frequency(posts_path, output_dir)

    summary = {
        "data_issues": issues,
        "posting_frequency": frequency,
        "describe": {
            column: posts[column].describe().to_dict()
            for column in ("likes_7d", "comments_7d")
        },
    }
    (output_dir / "eda_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )

    print("\n--- DATAKVALITET ---")
    for key, value in issues.items():
        print(f"{key}: {value}")
    print(f"\nFigurer och sammanfattning sparade i {output_dir}")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--posts-path", type=Path,
        default=Path(__file__).resolve().parent / "data" / "processed" / "post_table" / "posts.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(__file__).resolve().parent / "reports" / "eda",
    )
    args = parser.parse_args()
    try:
        generate_report(args.posts_path, args.output_dir)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"Kunde inte slutföra analysen: {error}\n")


if __name__ == "__main__":
    main()
