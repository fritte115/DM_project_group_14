import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Same engagement measure the clusters are built on: small-sample means are shrunk toward the population mean.
ENGAGEMENT = "shrunk_mean_engagement"
# Targets within the top cluster are ranked by distinct people who engaged during the period:
# a small group responding to everything does not inflate it. Per-post reach was not used because
# repeat responders make it fall mechanically as an account posts more.
TARGET_RANKING = "unique_responders"

def plot_final(clusters, top_followed, top_targets, top_cluster_name, output_dir):
    cat_list = list(clusters["cluster_name"].astype("category").cat.categories)
    cmap = plt.get_cmap("tab10")
    color_map = {name: cmap(i) for i, name in enumerate(cat_list)}

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(
        np.log1p(clusters["posts_per_day"]), np.log1p(clusters[ENGAGEMENT]),
        c=clusters["cluster_name"].map(color_map), s=5, alpha=0.15, edgecolors="none",
    )

    ax.scatter(
        np.log1p(top_followed["posts_per_day"]), np.log1p(top_followed[ENGAGEMENT]),
        c=top_followed["cluster_name"].map(color_map),
        s=140, edgecolors="black", linewidths=1.0, zorder=3,
    )
    for _, row in top_followed.iterrows():
        ax.annotate(
            f"{row['author_id']} ({row['follower_count']:,})",
            (np.log1p(row["posts_per_day"]), np.log1p(row[ENGAGEMENT])),
            textcoords="offset points", xytext=(6, 4), fontsize=7, zorder=4,
        )

    ax.scatter(
        np.log1p(top_targets["posts_per_day"]), np.log1p(top_targets[ENGAGEMENT]),
        marker="*", s=320, c="gold", edgecolors="black", linewidths=1.0, zorder=5,
    )
    for _, row in top_targets.iterrows():
        ax.annotate(
            row["author_id"],
            (np.log1p(row["posts_per_day"]), np.log1p(row[ENGAGEMENT])),
            textcoords="offset points", xytext=(6, -11), fontsize=7, zorder=6, color="#7a5c00",
        )

    ax.set_xlabel("log(1 + posts per day)")
    ax.set_ylabel("log(1 + shrunk mean 7-day engagement)")
    ax.set_title(
        f"Top {len(top_followed)} most-followed accounts (circles) vs.\n"
        f"top {len(top_targets)} recommended targets in '{top_cluster_name}' by reach (stars)"
    )
    handles = [
        plt.Line2D([0], [0], marker="o", linestyle="", color=color_map[name],
                   label=name, markeredgecolor="black")
        for name in cat_list
    ]
    handles.append(
        plt.Line2D([0], [0], marker="*", linestyle="", color="gold",
                   label="Recommended target", markeredgecolor="black", markersize=12)
    )
    ax.legend(handles=handles, title="cluster", loc="upper right")
    fig.tight_layout()
    fig.savefig(output_dir / "final_clusters_with_followers.png", dpi=150)
    plt.close(fig)

def run(clusters_path, output_dir, top_n, top_targets_n):
    output_dir.mkdir(parents=True, exist_ok=True)

    # follower_count is computed by cluster_users, where it is also a clustering feature.
    clusters = pd.read_csv(clusters_path, dtype={"author_id": str})

    correlation = float(np.corrcoef(np.log1p(clusters["follower_count"]), np.log1p(clusters[ENGAGEMENT]))[0, 1])
    print(f"\nCorrelation log(follower) vs log(engagement/post): {correlation:.4f}")

    top_followed = clusters.sort_values("follower_count", ascending=False).head(top_n)
    top_cluster_name = clusters.groupby("cluster_name")[ENGAGEMENT].mean().idxmax()
    top_targets = (
        clusters[clusters["cluster_name"] == top_cluster_name]
        .sort_values(TARGET_RANKING, ascending=False)
        .head(top_targets_n)
    )
    plot_final(clusters, top_followed, top_targets, top_cluster_name, output_dir)

    target_columns = [
        "author_id", "follower_count", "post_count", TARGET_RANKING, ENGAGEMENT, "engagement_rate",
    ]
    print(f"\nTop {top_targets_n} recommended accounts in '{top_cluster_name}', by distinct people reached")
    print(top_targets[target_columns].round(2).to_string(index=False))
    print(f"\nResults saved in {output_dir}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clusters-path", type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "clusters" / "user_clusters.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=PROJECT_ROOT / "reports" / "followers",
    )
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--top-targets-n", type=int, default=15)
    args = parser.parse_args()
    try:
        run(args.clusters_path, args.output_dir, args.top_n, args.top_targets_n)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"Could not finish follower check: {error}\n")

if __name__ == "__main__":
    main()
