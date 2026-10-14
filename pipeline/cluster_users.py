import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import RobustScaler
from src.extract import read_following, read_subscriptions
from src.features import (
    build_user_features, count_followers, count_unique_responders, detect_bots, estimate_shrinkage,
    read_posts, read_responders, shrink_mean,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Posting frequency x engagement intensity x audience size. The other engagement measures
# (std, engagement rate, distinct responders) correlate 0.84-0.96 with the shrunk mean, so they
# would count intensity twice; follower count correlates only ~0.2 with either other feature.
FEATURE_COLUMNS = ["log_posts_per_day", "log_shrunk_mean_engagement", "log_follower_count"]

def build_feature_table(posts_path, responders_path, max_posts_per_day, min_posts):
    features = build_user_features(read_posts(posts_path))
    unique_responders = count_unique_responders(read_responders(responders_path))

    rows = [
        {
            "author_id": author_id,
            "post_count": f["post_count"],
            "posts_per_day": f["posts_per_day"],
            "engagement_total": f["engagement_total"],
            "mean_engagement": f["mean_engagement"],
            "std_engagement": f["std_engagement"],
            "engagement_rate": f["engagement_rate"],
            "unique_responders": unique_responders.get(author_id, 0),
        }
        for author_id, f in features.items()
    ]
    table = pd.DataFrame(rows)
    table["has_engagement"] = table["engagement_total"] > 0

    # Bot detection only runs on accounts that passed the engagement filter: posting rate is
    # only a meaningful "bot" signal for accounts that are otherwise sponsorship-relevant.
    engaged_features = {
        author_id: f for author_id, f in features.items() if f["engagement_total"] > 0
    }
    bots = detect_bots(engaged_features, max_posts_per_day=max_posts_per_day)
    table["is_bot"] = table["author_id"].isin(bots)
    # Per-author averages over one or two posts are noise, not a user type.
    table["has_min_posts"] = table["post_count"] >= min_posts
    table["eligible"] = table["has_engagement"] & ~table["is_bot"] & table["has_min_posts"]
    return table

def choose_k(X, k_range, sample_size, random_state):
    silhouette, inertia, davies_bouldin = {}, {}, {}
    for k in k_range:
        model = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = model.fit_predict(X)
        silhouette[k] = float(silhouette_score(X, labels, sample_size=min(sample_size, len(X)), random_state=random_state))
        inertia[k] = float(model.inertia_)
        davies_bouldin[k] = float(davies_bouldin_score(X, labels))

    scores = {"silhouette": silhouette, "inertia": inertia, "davies_bouldin": davies_bouldin}
    best_k = max(silhouette, key=silhouette.get)
    return best_k, scores

def name_clusters(active):
    order = active.groupby("cluster")["shrunk_mean_engagement"].mean().sort_values(ascending=False).index
    if len(order) == 3:
        names = dict(zip(order, ("High value", "Baseline", "Low value")))
    else:
        names = {cluster_id: f"Tier {rank + 1} of {len(order)}" for rank, cluster_id in enumerate(order)}
    return active["cluster"].map(names)

def cluster(table, k_range, sample_size, random_state):
    active = table[table["eligible"]].copy()

    # Pull each author's mean toward the population mean in proportion to how few posts it
    # rests on, so one lucky post does not make an author look highly engaging.
    prior_mean, prior_posts = estimate_shrinkage(
        active["post_count"], active["mean_engagement"], active["std_engagement"],
    )
    active["shrunk_mean_engagement"] = shrink_mean(
        active["engagement_total"], active["post_count"], prior_mean, prior_posts,
    )
    active["log_posts_per_day"] = np.log1p(active["posts_per_day"])
    active["log_shrunk_mean_engagement"] = np.log1p(active["shrunk_mean_engagement"])
    active["follower_count"] = active["follower_count"].astype(int)
    active["log_follower_count"] = np.log1p(active["follower_count"])

    X = RobustScaler().fit_transform(active[FEATURE_COLUMNS])

    best_k, scores = choose_k(X, k_range, sample_size, random_state)
    model = KMeans(n_clusters=best_k, n_init=10, random_state=random_state)
    active["cluster"] = model.fit_predict(X)
    active["cluster_name"] = name_clusters(active)

    shrinkage = {"prior_mean_engagement": prior_mean, "prior_posts": prior_posts}
    return active, best_k, scores, shrinkage

def summarize_clusters(active):
    summary = active.groupby("cluster_name").agg(
        accounts=("author_id", "count"),
        mean_posts_per_day=("posts_per_day", "mean"),
        mean_shrunk_engagement=("shrunk_mean_engagement", "mean"),
        median_follower_count=("follower_count", "median"),
        mean_engagement_rate=("engagement_rate", "mean"),
        median_unique_responders=("unique_responders", "median"),
    ).reset_index()
    return summary.sort_values("mean_shrunk_engagement", ascending=False)

def plot_k_selection(scores, output_dir):
    ks = sorted(scores["silhouette"])
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    axes[0].plot(ks, [scores["inertia"][k] for k in ks], marker="o", color="#55A868")
    axes[0].set_title("Elbow method")
    axes[0].set_xlabel("k")
    axes[0].set_ylabel("inertia (lower = tighter)")

    axes[1].plot(ks, [scores["silhouette"][k] for k in ks], marker="o", color="#4C72B0")
    axes[1].set_title("Silhouette score")
    axes[1].set_xlabel("k")
    axes[1].set_ylabel("silhouette (higher = better)")

    axes[2].plot(ks, [scores["davies_bouldin"][k] for k in ks], marker="o", color="#C44E52")
    axes[2].set_title("Davies-Bouldin index")
    axes[2].set_xlabel("k")
    axes[2].set_ylabel("DB index (lower = better)")

    fig.suptitle("Choosing k: three independent diagnostics")
    fig.tight_layout()
    fig.savefig(output_dir / "k_selection.png", dpi=150)
    plt.close(fig)

def run(
    posts_path, responders_path, data_dir, output_dir, clusters_path, max_posts_per_day, min_posts,
    k_range, sample_size, random_state,
):
    output_dir.mkdir(parents=True, exist_ok=True)

    table = build_feature_table(posts_path, responders_path, max_posts_per_day, min_posts)
    # Exclusions are counted in order and are mutually exclusive.
    n_no_engagement = int((~table["has_engagement"]).sum())
    n_bots = int(table["is_bot"].sum())
    n_few_posts = int((table["has_engagement"] & ~table["is_bot"] & ~table["has_min_posts"]).sum())
    n_active = int(table["eligible"].sum())
    print(
        f"Total amount of accounts: {len(table):,}\n"
        f"Removed due to no engagement: {n_no_engagement:,}\n"
        f"Removed due to bot accounts "
        f"(> {max_posts_per_day:.1f} posts/day): {n_bots:,}\n"
        f"Removed due to fewer than {min_posts} posts: {n_few_posts:,}\n"
        f"Still relevant for clustering: {n_active:,}",
        flush=True,
    )

    relevant_authors = set(table.loc[table["eligible"], "author_id"])
    # Counted only for eligible authors to keep the follower sets in memory small; blank for the rest.
    followers = count_followers(
        read_following(data_dir / "followingAugSept.csv"),
        read_subscriptions(data_dir / "subscriptions.csv"),
        relevant_authors,
    )
    table["follower_count"] = table["author_id"].map(followers).astype("Int64")
    active, best_k, scores, shrinkage = cluster(table, k_range, sample_size, random_state)
    print(
        f"Shrinkage: population mean {shrinkage['prior_mean_engagement']:.3f} engagement/post, "
        f"weighted as {shrinkage['prior_posts']:.2f} posts"
    )

    best_k_by_davies_bouldin = min(scores["davies_bouldin"], key=scores["davies_bouldin"].get)
    print(f"Chosen k (silhouette): {best_k}, Best k according to Davies-Bouldin: {best_k_by_davies_bouldin}")

    print("\nCluster Summary")
    print(summarize_clusters(active).to_string(index=False))

    plot_k_selection(scores, output_dir)

    # Intermediate input for follower_check, not a report output.
    clusters_path.parent.mkdir(parents=True, exist_ok=True)
    active[[
        "author_id", "post_count", "posts_per_day", "shrunk_mean_engagement", "follower_count",
        "engagement_rate", "unique_responders", "cluster", "cluster_name",
    ]].to_csv(clusters_path, index=False)
    print(f"\nResults saved in {output_dir}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--posts-path", type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "post_table" / "posts.csv",
    )
    parser.add_argument(
        "--responders-path", type=Path,
        help="Author-responder table from build_posts (default: responders.csv next to --posts-path).",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=PROJECT_ROOT / "data",
        help="Folder with followingAugSept.csv and subscriptions.csv.",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=PROJECT_ROOT / "reports" / "clusters",
    )
    parser.add_argument(
        "--clusters-path", type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "clusters" / "user_clusters.csv",
        help="Where to write the clustered authors for follower_check.",
    )
    parser.add_argument(
        "--bot-threshold-posts-per-day", type=float, default=50.0,
        help="Exclude accounts posting more often than this, on average, as implausible for manual posting.",
    )
    parser.add_argument(
        "--min-posts", type=int, default=5,
        help="Exclude accounts with fewer posts than this in the period.",
    )
    parser.add_argument("--min-k", type=int, default=2)
    parser.add_argument("--max-k", type=int, default=6)
    parser.add_argument("--sample-size", type=int, default=10_000)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    responders_path = args.responders_path or args.posts_path.parent / "responders.csv"
    try:
        run(
            args.posts_path, responders_path, args.data_dir, args.output_dir, args.clusters_path,
            args.bot_threshold_posts_per_day, args.min_posts,
            range(args.min_k, args.max_k + 1), args.sample_size, args.random_state,
        )
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"Could not complete clustering: {error}\n")

if __name__ == "__main__":
    main()
