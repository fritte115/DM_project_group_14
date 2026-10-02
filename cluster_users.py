import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import RobustScaler

from build_posts import POST_COLUMNS
from src.features import build_user_features, detect_bots, read_posts


def build_feature_table(posts_path, max_posts_per_day):
    features = build_user_features(read_posts(posts_path))

    rows = [
        {
            "author_id": author_id,
            "post_count": f["post_count"],
            "posts_per_day": f["posts_per_day"],
            "engagement_total": f["engagement_total"],
            "mean_engagement": f["mean_engagement"],
            "std_engagement": f["std_engagement"],
            "engagement_rate": f["engagement_rate"],
        }
        for author_id, f in features.items()
    ]
    table = pd.DataFrame(rows)
    table["has_engagement"] = table["engagement_total"] > 0

    # Bot detection only runs on accounts that already passed the engagement
    # filter: posting rate is only a meaningful "bot" signal once we're
    # looking at accounts that are otherwise sponsorship-relevant.
    engaged_features = {
        author_id: f for author_id, f in features.items() if f["engagement_total"] > 0
    }
    bots = detect_bots(engaged_features, max_posts_per_day=max_posts_per_day)
    table["is_bot"] = table["author_id"].isin(bots)
    return table


def write_relevant_posts(posts_path, relevant_authors, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(POST_COLUMNS)
        for post in read_posts(posts_path):
            if post["author_id"] in relevant_authors:
                writer.writerow([
                    post["post_id"], post["author_id"], post["published_at"],
                    post["likes_7d"], post["comments_7d"], post["has_image"], post["has_video"],
                ])
                rows_written += 1
    return rows_written


def choose_k(X, k_range, sample_size, random_state):
    silhouette, inertia, davies_bouldin = {}, {}, {}
    for k in k_range:
        model = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = model.fit_predict(X)
        silhouette[k] = float(
            silhouette_score(X, labels, sample_size=min(sample_size, len(X)), random_state=random_state)
        )
        inertia[k] = float(model.inertia_)
        davies_bouldin[k] = float(davies_bouldin_score(X, labels))

    scores = {"silhouette": silhouette, "inertia": inertia, "davies_bouldin": davies_bouldin}
    best_k = max(silhouette, key=silhouette.get)
    return best_k, scores


def name_clusters(active):
    # Ranked by mean_engagement, highest first. The three-way names only make
    # sense for k=3 (our validated choice); any other k falls back to a
    # generic, still-ranked label rather than guessing a name.
    order = active.groupby("cluster")["mean_engagement"].mean().sort_values(ascending=False).index
    if len(order) == 3:
        names = dict(zip(order, ("High value", "Baseline", "Low value")))
    else:
        names = {cluster_id: f"Tier {rank + 1} of {len(order)}" for rank, cluster_id in enumerate(order)}
    return active["cluster"].map(names)


def cluster(table, k_range, sample_size, random_state):
    active = table[~table["is_bot"] & table["has_engagement"]].copy()
    active["log_posts_per_day"] = np.log1p(active["posts_per_day"])
    active["log_mean_engagement"] = np.log1p(active["mean_engagement"])
    active["log_std_engagement"] = np.log1p(active["std_engagement"])

    feature_columns = ["log_posts_per_day", "log_mean_engagement", "log_std_engagement"]
    X = RobustScaler().fit_transform(active[feature_columns])

    best_k, scores = choose_k(X, k_range, sample_size, random_state)
    model = KMeans(n_clusters=best_k, n_init=10, random_state=random_state)
    active["cluster"] = model.fit_predict(X)
    active["cluster_name"] = name_clusters(active)

    return active, best_k, scores


def summarize_clusters(active):
    summary = active.groupby(["cluster", "cluster_name"]).agg(
        accounts=("author_id", "count"),
        mean_posts_per_day=("posts_per_day", "mean"),
        mean_engagement=("mean_engagement", "mean"),
        mean_std_engagement=("std_engagement", "mean"),
        mean_engagement_rate=("engagement_rate", "mean"),
        median_post_count=("post_count", "median"),
    ).reset_index()
    return summary.sort_values("mean_engagement", ascending=False)


def plot_clusters(active, output_dir):
    categories = active["cluster_name"].astype("category")
    fig, ax = plt.subplots(figsize=(7, 5))
    scatter = ax.scatter(
        active["log_posts_per_day"], active["log_mean_engagement"],
        c=categories.cat.codes, cmap="tab10", s=6, alpha=0.4,
    )
    ax.set_xlabel("posts per day (log scale)")
    ax.set_ylabel("mean weekly engagement (log scale)")
    ax.set_title(
        "User clusters: posting frequency vs. engagement intensity\n"
        "(clustered on these two features plus engagement consistency)"
    )
    handles, _ = scatter.legend_elements()
    legend = ax.legend(handles, categories.cat.categories, title="cluster", loc="upper right")
    ax.add_artist(legend)
    fig.tight_layout()
    fig.savefig(output_dir / "user_clusters_scatter.png", dpi=150)
    plt.close(fig)


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


def run(posts_path, output_dir, relevant_posts_path, max_posts_per_day, k_range, sample_size, random_state):
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Bygger konto-funktioner från posts.csv …", flush=True)
    table = build_feature_table(posts_path, max_posts_per_day)
    n_no_engagement = int((~table["has_engagement"]).sum())
    n_bots = int(table["is_bot"].sum())
    n_active = int((table["has_engagement"] & ~table["is_bot"]).sum())
    print(
        f"Konton totalt: {len(table):,}\n"
        f"  1) Uteslutna utan något engagemang alls (inte sponsringsrelevanta): {n_no_engagement:,}\n"
        f"  2) Uteslutna som bottar bland engagerade konton "
        f"(> {max_posts_per_day:.1f} inlägg/dag): {n_bots:,}\n"
        f"  Kvar för klustring: {n_active:,}",
        flush=True,
    )

    relevant_authors = set(table.loc[table["has_engagement"] & ~table["is_bot"], "author_id"])
    print(f"Skriver inlägg från relevanta konton till {relevant_posts_path} …", flush=True)
    posts_written = write_relevant_posts(posts_path, relevant_authors, relevant_posts_path)
    print(f"  {posts_written:,} inlägg skrivna.", flush=True)

    print("Klustrar aktiva konton …", flush=True)
    active, best_k, scores = cluster(table, k_range, sample_size, random_state)

    best_k_by_davies_bouldin = min(scores["davies_bouldin"], key=scores["davies_bouldin"].get)
    print("\n--- VAL AV k (silhouette väljer, elbow/Davies-Bouldin som kontroll) ---")
    print(f"{'k':>3} {'inertia':>12} {'silhouette':>12} {'davies_bouldin':>15}")
    for k in sorted(scores["silhouette"]):
        print(
            f"{k:>3} {scores['inertia'][k]:>12,.1f} "
            f"{scores['silhouette'][k]:>12.4f} {scores['davies_bouldin'][k]:>15.4f}"
        )
    print(f"Valt k (silhouette): {best_k}  |  bästa k enligt Davies-Bouldin: {best_k_by_davies_bouldin}")

    summary = summarize_clusters(active)
    print("\n--- KLUSTERSAMMANFATTNING ---")
    print(summary.to_string(index=False))

    plot_clusters(active, output_dir)
    plot_k_selection(scores, output_dir)

    table.to_csv(output_dir / "user_features.csv", index=False)
    active[[
        "author_id", "post_count", "posts_per_day",
        "mean_engagement", "std_engagement", "engagement_rate", "cluster", "cluster_name",
    ]].to_csv(output_dir / "user_clusters.csv", index=False)
    summary.to_csv(output_dir / "cluster_summary.csv", index=False)

    report = {
        "total_accounts": len(table),
        "bots_excluded": n_bots,
        "bot_threshold_posts_per_day": max_posts_per_day,
        "no_engagement_excluded": n_no_engagement,
        "clustered_accounts": len(active),
        "relevant_posts_written": posts_written,
        "chosen_k": best_k,
        "best_k_by_davies_bouldin": best_k_by_davies_bouldin,
        "k_selection_scores": scores,
    }
    (output_dir / "clustering_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"\nResultat sparade i {output_dir}")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--posts-path", type=Path,
        default=Path(__file__).resolve().parent / "data" / "processed" / "post_table" / "posts.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(__file__).resolve().parent / "reports" / "clusters",
    )
    parser.add_argument(
        "--relevant-posts-path", type=Path,
        help="Where to write the post-level rows for clustering-eligible authors only "
             "(default: posts_relevant.csv next to --posts-path).",
    )
    parser.add_argument(
        "--bot-threshold-posts-per-day", type=float, default=50.0,
        help="Exclude accounts posting more often than this, on average, as implausible for manual posting.",
    )
    parser.add_argument("--min-k", type=int, default=2)
    parser.add_argument("--max-k", type=int, default=6)
    parser.add_argument("--sample-size", type=int, default=10_000)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    relevant_posts_path = args.relevant_posts_path or args.posts_path.parent / "posts_relevant.csv"
    try:
        run(
            args.posts_path, args.output_dir, relevant_posts_path, args.bot_threshold_posts_per_day,
            range(args.min_k, args.max_k + 1), args.sample_size, args.random_state,
        )
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"Kunde inte slutföra klustringen: {error}\n")


if __name__ == "__main__":
    main()
