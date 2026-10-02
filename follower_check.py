import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.extract import read_following, read_subscriptions


def count_followers(data_dir, relevant_authors):
    followers = {author_id: set() for author_id in relevant_authors}

    print("Läser followingAugSept.csv …", flush=True)
    for row in read_following(data_dir / "followingAugSept.csv"):
        followed = row["followed_id"]
        if followed in followers:
            followers[followed].add(row["follower_id"])

    print("Läser subscriptions.csv …", flush=True)
    for row in read_subscriptions(data_dir / "subscriptions.csv"):
        subscribed_to = row["subscribed_to_id"]
        if subscribed_to in followers:
            followers[subscribed_to].add(row["subscriber_id"])

    return {author_id: len(ids) for author_id, ids in followers.items()}


def run(clusters_path, data_dir, output_dir, top_n, top_targets_n):
    output_dir.mkdir(parents=True, exist_ok=True)

    clusters = pd.read_csv(clusters_path, dtype={"author_id": str})
    follower_counts = count_followers(data_dir, set(clusters["author_id"]))
    clusters["follower_count"] = clusters["author_id"].map(follower_counts).fillna(0).astype(int)

    label_column = "cluster_name" if "cluster_name" in clusters.columns else "cluster"
    categories = clusters[label_column].astype("category")

    log_followers = np.log1p(clusters["follower_count"])
    log_engagement = np.log1p(clusters["mean_engagement"])
    correlation = float(np.corrcoef(log_followers, log_engagement)[0, 1])
    print(f"\nKorrelation log(följare) vs log(engagemang per inlägg): {correlation:.4f}")

    fig, ax = plt.subplots(figsize=(7, 5))
    scatter = ax.scatter(
        log_followers, log_engagement, c=categories.cat.codes, cmap="tab10", s=6, alpha=0.4,
    )
    ax.set_xlabel("log(1 + follower count)")
    ax.set_ylabel("log(1 + mean 7-day engagement)")
    ax.set_title(f"Followers vs. engagement (r = {correlation:.2f}), colored by cluster")
    handles, _ = scatter.legend_elements()
    legend = ax.legend(handles, categories.cat.categories, title="cluster", loc="upper right")
    ax.add_artist(legend)
    fig.tight_layout()
    fig.savefig(output_dir / "followers_vs_engagement.png", dpi=150)
    plt.close(fig)

    # The "final" graph: the full population faint in the background, with
    # only the top-N most-followed accounts highlighted and labeled, to make
    # one specific point legible: the biggest accounts land in all three
    # clusters, not just "High value".
    if "posts_per_day" in clusters.columns:
        cat_list = list(categories.cat.categories)
        cmap = plt.get_cmap("tab10")
        color_map = {name: cmap(i) for i, name in enumerate(cat_list)}

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(
            np.log1p(clusters["posts_per_day"]), log_engagement,
            c=clusters[label_column].map(color_map), s=5, alpha=0.15, edgecolors="none",
        )

        top_followed_plot = clusters.sort_values("follower_count", ascending=False).head(top_n)
        ax.scatter(
            np.log1p(top_followed_plot["posts_per_day"]), np.log1p(top_followed_plot["mean_engagement"]),
            c=top_followed_plot[label_column].map(color_map),
            s=140, edgecolors="black", linewidths=1.0, zorder=3,
        )
        for _, row in top_followed_plot.iterrows():
            ax.annotate(
                f"{row['author_id']} ({row['follower_count']:,})",
                (np.log1p(row["posts_per_day"]), np.log1p(row["mean_engagement"])),
                textcoords="offset points", xytext=(6, 4), fontsize=7, zorder=4,
            )

        # The actual recommendation: the top accounts, by mean engagement,
        # within whichever cluster has the highest average engagement (the
        # "High value" cluster at k=3) - the concrete answer to "who should a
        # sponsor target", shown alongside the top-followed accounts above.
        top_cluster_name = clusters.groupby(label_column)["mean_engagement"].mean().idxmax()
        top_targets_plot = (
            clusters[clusters[label_column] == top_cluster_name]
            .sort_values("mean_engagement", ascending=False)
            .head(top_targets_n)
        )
        ax.scatter(
            np.log1p(top_targets_plot["posts_per_day"]), np.log1p(top_targets_plot["mean_engagement"]),
            marker="*", s=320, c="gold", edgecolors="black", linewidths=1.0, zorder=5,
        )
        for _, row in top_targets_plot.iterrows():
            ax.annotate(
                row["author_id"],
                (np.log1p(row["posts_per_day"]), np.log1p(row["mean_engagement"])),
                textcoords="offset points", xytext=(6, -11), fontsize=7, zorder=6, color="#7a5c00",
            )

        ax.set_xlabel("log(1 + posts per day)")
        ax.set_ylabel("log(1 + mean 7-day engagement)")
        ax.set_title(
            f"Top {top_n} most-followed accounts (circles) vs.\n"
            f"top {top_targets_n} recommended targets in '{top_cluster_name}' (stars)"
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

    top_followed = clusters.sort_values("follower_count", ascending=False).head(top_n)
    print(f"\n--- TOP {top_n} EFTER FÖLJARANTAL ---")
    print(
        top_followed[[
            "author_id", "follower_count", label_column, "mean_engagement", "engagement_rate",
        ]].to_string(index=False)
    )

    top_cluster_name = clusters.groupby(label_column)["mean_engagement"].mean().idxmax()
    top_targets = (
        clusters[clusters[label_column] == top_cluster_name]
        .sort_values("mean_engagement", ascending=False)
        .head(top_targets_n)
    )
    print(f"\n--- TOP {top_targets_n} REKOMMENDERADE KONTON ('{top_cluster_name}') ---")
    print(
        top_targets[[
            "author_id", "follower_count", "mean_engagement", "engagement_rate",
        ]].to_string(index=False)
    )

    clusters.to_csv(output_dir / "user_clusters_with_followers.csv", index=False)
    report = {
        "accounts": len(clusters),
        "correlation_log_followers_vs_log_engagement": correlation,
        "top_followed": top_followed[[
            "author_id", "follower_count", label_column, "mean_engagement", "engagement_rate",
        ]].to_dict(orient="records"),
        "top_recommended_targets": top_targets[[
            "author_id", "follower_count", "mean_engagement", "engagement_rate",
        ]].to_dict(orient="records"),
    }
    (output_dir / "follower_check_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"\nResultat sparade i {output_dir}")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clusters-path", type=Path,
        default=Path(__file__).resolve().parent / "reports" / "clusters" / "user_clusters.csv",
    )
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path(__file__).resolve().parent / "data",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(__file__).resolve().parent / "reports" / "followers",
    )
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--top-targets-n", type=int, default=15)
    args = parser.parse_args()
    try:
        run(args.clusters_path, args.data_dir, args.output_dir, args.top_n, args.top_targets_n)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"Kunde inte slutföra följarkontrollen: {error}\n")


if __name__ == "__main__":
    main()
