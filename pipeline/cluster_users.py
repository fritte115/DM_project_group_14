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
from pipeline.build_posts import POST_COLUMNS
from src.features import build_user_features, detect_bots, read_posts

PROJECT_ROOT = Path(__file__).resolve().parent.parent

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
        silhouette[k] = float(silhouette_score(X, labels, sample_size=min(sample_size, len(X)), random_state=random_state))
        inertia[k] = float(model.inertia_)
        davies_bouldin[k] = float(davies_bouldin_score(X, labels))

    scores = {"silhouette": silhouette, "inertia": inertia, "davies_bouldin": davies_bouldin}
    best_k = max(silhouette, key=silhouette.get)
    return best_k, scores

def name_clusters(active):
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

def flag_steady_high_engagement(active):
    """Flag regular publishers with high, relatively stable engagement.

    Raw low standard deviation almost never occurs with a high mean, because a
    few strong posts raise the SD. Variability is therefore judged by the
    coefficient of variation (SD / mean) among accounts that already post
    often enough to rule out one-hit wonders.
    """
    min_posts = 16
    min_posts_per_day = float(active["posts_per_day"].median())
    min_mean = float(active["mean_engagement"].quantile(0.75))
    cv = active["std_engagement"] / active["mean_engagement"].replace(0, np.nan)
    eligible = (
        (active["post_count"] >= min_posts)
        & (active["posts_per_day"] >= min_posts_per_day)
        & (active["mean_engagement"] >= min_mean)
    )
    max_cv = float(cv[eligible].quantile(0.4))
    flagged = eligible & (cv <= max_cv)
    return flagged, {
        "min_posts": min_posts,
        "min_posts_per_day": min_posts_per_day,
        "min_mean_engagement": min_mean,
        "max_cv": max_cv,
        "count": int(flagged.sum()),
    }


def plot_clusters(active, output_dir):
    categories = active["cluster_name"].astype("category")
    category_names = list(categories.cat.categories)
    highlighted, highlight_rule = flag_steady_high_engagement(active)
    color_map = {
        name: plt.get_cmap("tab10")(index)
        for index, name in enumerate(category_names)
    }

    fig, ax = plt.subplots(figsize=(7, 5))
    for name in category_names:
        group = active[categories == name]
        ax.scatter(
            group["log_posts_per_day"], group["log_mean_engagement"],
            color=color_map[name], label=name, s=6, alpha=0.4,
        )
    ax.set_xlabel("log(1 + posts per day)")
    ax.set_ylabel("log(1 + mean reactions per post)")
    ax.set_title(
        "User clusters: posting frequency vs. engagement intensity\n"
        "(colors also use the hidden engagement-variability feature)"
    )
    ax.legend(title="Cluster", loc="upper right")
    fig.tight_layout()
    fig.savefig(output_dir / "user_clusters_scatter.png", dpi=150)
    plt.close(fig)

    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")
    centroids = active.groupby("cluster_name")[
        ["log_posts_per_day", "log_mean_engagement", "log_std_engagement"]
    ].mean()
    for name in category_names:
        group = active[categories == name]
        ax.scatter(
            group["log_posts_per_day"],
            group["log_mean_engagement"],
            group["log_std_engagement"],
            color=color_map[name],
            label=name,
            s=7,
            alpha=0.25,
            depthshade=False,
        )
    for name in category_names:
        center = centroids.loc[name]
        ax.scatter(
            center["log_posts_per_day"],
            center["log_mean_engagement"],
            center["log_std_engagement"],
            color=color_map[name],
            marker="X",
            s=180,
            edgecolor="black",
            linewidth=1.0,
            depthshade=False,
        )
        ax.text(
            center["log_posts_per_day"],
            center["log_mean_engagement"],
            center["log_std_engagement"],
            f"  {name}",
            fontsize=8,
            weight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.7, "pad": 1},
        )
    if highlighted.any():
        focus = active.loc[highlighted]
        ax.scatter(
            focus["log_posts_per_day"],
            focus["log_mean_engagement"],
            focus["log_std_engagement"],
            facecolors="none",
            edgecolors="#111111",
            s=28,
            linewidths=0.8,
            depthshade=False,
            label=f"Steady high-engagement ({highlight_rule['count']})",
        )
    ax.set_xlabel("Posts per day", labelpad=8)
    ax.set_ylabel("Mean reactions per post", labelpad=10)
    ax.set_zlabel("Engagement variability", labelpad=8)
    ax.set_title("User clusters in the three fitted dimensions\n(X = cluster centroid)")
    ax.view_init(elev=22, azim=-58)
    ax.legend(title="Cluster", loc="upper left")
    fig.tight_layout()
    fig.savefig(output_dir / "user_clusters_3d.png", dpi=180)
    plt.close(fig)
    write_interactive_3d(active, output_dir, category_names, highlighted, highlight_rule)


def write_interactive_3d(active, output_dir, category_names, highlighted, highlight_rule):
    color_values = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    color_map = {
        name: color_values[index % len(color_values)]
        for index, name in enumerate(category_names)
    }
    cluster_codes = {name: index for index, name in enumerate(category_names)}
    highlight_flags = highlighted.to_numpy()
    points = [
        [
            round(row.log_posts_per_day, 5),
            round(row.log_mean_engagement, 5),
            round(row.log_std_engagement, 5),
            cluster_codes[row.cluster_name],
            int(highlight_flags[index]),
        ]
        for index, row in enumerate(active.itertuples())
    ]
    centroids = (
        active.groupby("cluster_name")[
            ["log_posts_per_day", "log_mean_engagement", "log_std_engagement"]
        ]
        .mean()
        .reindex(category_names)
        .round(5)
        .values
        .tolist()
    )
    payload = json.dumps(
        {
            "points": points,
            "centroids": centroids,
            "names": category_names,
            "colors": [color_map[name] for name in category_names],
            "counts": [
                int((active["cluster_name"] == name).sum())
                for name in category_names
            ],
            "highlight": highlight_rule,
        },
        separators=(",", ":"),
    )
    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Interactive Friendfeed user clusters</title>
<style>
  html, body { height: 100%; margin: 0; background: #f7f7f5; color: #202124; font-family: Inter, system-ui, sans-serif; }
  body { display: grid; grid-template-rows: auto 1fr; }
  header { display: flex; align-items: center; gap: 18px; padding: 12px 18px; border-bottom: 1px solid #d7d7d2; background: #fff; }
  h1 { margin: 0; font-size: 18px; font-weight: 650; }
  .hint { color: #666; font-size: 12px; }
  #legend { display: flex; gap: 12px; margin-left: auto; font-size: 12px; }
  #legend label { cursor: pointer; white-space: nowrap; }
  #legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; }
  button { border: 1px solid #bbb; border-radius: 4px; background: #fff; padding: 5px 9px; cursor: pointer; }
  main { position: relative; min-height: 0; }
  canvas { width: 100%; height: 100%; display: block; cursor: grab; }
  canvas.dragging { cursor: grabbing; }
  .rule { position: absolute; left: 15px; bottom: 12px; padding: 7px 9px; background: rgba(255,255,255,.9); border: 1px solid #ddd; font-size: 11px; line-height: 1.45; pointer-events: none; max-width: 360px; }
</style>
</head>
<body>
<header>
  <div>
    <h1>User clusters in the three fitted dimensions</h1>
    <div class="hint">Drag to rotate · scroll to zoom · double-click to reset · X marks centroids · outlined points are steady high-engagement publishers</div>
  </div>
  <div id="legend"></div>
  <button id="reset">Reset view</button>
</header>
<main>
  <canvas id="plot"></canvas>
  <div class="rule" id="rule"></div>
</main>
<script>
const DATA = __DATA__;
const canvas = document.getElementById("plot");
const ctx = canvas.getContext("2d");
const visible = DATA.names.map(() => true);
let showHighlight = true;
let yaw = -0.75, pitch = 0.35, zoom = 1, dragging = false, lastX = 0, lastY = 0;

const mins = [Infinity, Infinity, Infinity], maxs = [-Infinity, -Infinity, -Infinity];
for (const p of DATA.points) for (let i = 0; i < 3; i++) {
  mins[i] = Math.min(mins[i], p[i]); maxs[i] = Math.max(maxs[i], p[i]);
}
function normalize(p) {
  return [0, 1, 2].map(i => ((p[i] - mins[i]) / (maxs[i] - mins[i]) - 0.5) * 2);
}
const points = DATA.points.map(p => [...normalize(p), p[3], p[4] || 0]);
const centers = DATA.centroids.map((p, i) => [...normalize(p), i]);

const legend = document.getElementById("legend");
DATA.names.forEach((name, i) => {
  const label = document.createElement("label");
  label.innerHTML = `<input type="checkbox" checked> <i style="background:${DATA.colors[i]}"></i>${name} (${DATA.counts[i].toLocaleString()})`;
  label.querySelector("input").addEventListener("change", e => { visible[i] = e.target.checked; draw(); });
  legend.appendChild(label);
});
if (DATA.highlight) {
  const label = document.createElement("label");
  label.innerHTML = `<input type="checkbox" checked> <i style="background:transparent;border:1.5px solid #111;border-radius:50%"></i>Steady high-engagement (${DATA.highlight.count.toLocaleString()})`;
  label.querySelector("input").addEventListener("change", e => { showHighlight = e.target.checked; draw(); });
  legend.appendChild(label);
  document.getElementById("rule").innerHTML =
    `Outlined points: at least ${DATA.highlight.min_posts} posts, ` +
    `≥ ${DATA.highlight.min_posts_per_day.toFixed(2)} posts/day, ` +
    `mean reactions ≥ ${DATA.highlight.min_mean_engagement.toFixed(2)}, ` +
    `and SD/mean ≤ ${DATA.highlight.max_cv.toFixed(2)}. This avoids one-hit wonders.`;
}

function resize() {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  draw();
}
function rotate(p) {
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const x = p[0] * cy - p[2] * sy;
  const z0 = p[0] * sy + p[2] * cy;
  const y = p[1] * cp - z0 * sp;
  const z = p[1] * sp + z0 * cp;
  return [x, y, z];
}
function project(p, width, height) {
  const r = rotate(p);
  const perspective = 1 / (3.4 - r[2] * 0.45);
  const scale = Math.min(width, height) * 1.15 * zoom;
  return [width / 2 + r[0] * scale * perspective, height / 2 - r[1] * scale * perspective, r[2]];
}
function line(a, b, color, width, w, h) {
  const p = project(a, w, h), q = project(b, w, h);
  ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]);
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
}
function axisLabel(start, end, text, w, h) {
  const p = project(start, w, h), q = project(end, w, h);
  const dx = q[0] - p[0], dy = q[1] - p[1];
  const length = Math.hypot(dx, dy) || 1;
  const pad = 18;
  const x = q[0] + dx / length * pad;
  const y = q[1] + dy / length * pad;
  ctx.save();
  ctx.font = "600 13px system-ui";
  ctx.fillStyle = "#222";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, x, y);
  ctx.restore();
}
function draw() {
  const ratio = window.devicePixelRatio || 1;
  const w = canvas.width / ratio, h = canvas.height / ratio;
  ctx.clearRect(0, 0, w, h);
  line([-1,-1,-1], [1,-1,-1], "#555", 1.2, w, h);
  line([-1,-1,-1], [-1,1,-1], "#555", 1.2, w, h);
  line([-1,-1,-1], [-1,-1,1], "#555", 1.2, w, h);
  axisLabel([-1,-1,-1], [1,-1,-1], "Posts per day", w, h);
  axisLabel([-1,-1,-1], [-1,1,-1], "Mean reactions per post", w, h);
  axisLabel([-1,-1,-1], [-1,-1,1], "Engagement variability", w, h);
  const projected = [];
  for (const p of points) if (visible[p[3]]) {
    const q = project(p, w, h); projected.push([q[2], q[0], q[1], p[3], p[4]]);
  }
  projected.sort((a, b) => a[0] - b[0]);
  ctx.globalAlpha = 0.28;
  for (const p of projected) {
    ctx.beginPath(); ctx.arc(p[1], p[2], 2.1, 0, Math.PI * 2);
    ctx.fillStyle = DATA.colors[p[3]]; ctx.fill();
  }
  if (showHighlight) {
    ctx.globalAlpha = 1;
    for (const p of projected) if (p[4]) {
      ctx.beginPath(); ctx.arc(p[1], p[2], 3.6, 0, Math.PI * 2);
      ctx.fillStyle = DATA.colors[p[3]]; ctx.fill();
      ctx.lineWidth = 1.4; ctx.strokeStyle = "#111"; ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
  ctx.font = "600 12px system-ui";
  for (const c of centers) if (visible[c[3]]) {
    const p = project(c, w, h), size = 8;
    ctx.strokeStyle = "#111"; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(p[0]-size,p[1]-size); ctx.lineTo(p[0]+size,p[1]+size);
    ctx.moveTo(p[0]+size,p[1]-size); ctx.lineTo(p[0]-size,p[1]+size); ctx.stroke();
    ctx.fillStyle = "#111"; ctx.fillText(DATA.names[c[3]], p[0] + 11, p[1] + 4);
  }
}
canvas.addEventListener("pointerdown", e => {
  dragging = true; lastX = e.clientX; lastY = e.clientY;
  canvas.classList.add("dragging"); canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener("pointermove", e => {
  if (!dragging) return;
  yaw += (e.clientX - lastX) * 0.008; pitch += (e.clientY - lastY) * 0.008;
  pitch = Math.max(-1.45, Math.min(1.45, pitch));
  lastX = e.clientX; lastY = e.clientY; draw();
});
canvas.addEventListener("pointerup", () => { dragging = false; canvas.classList.remove("dragging"); });
canvas.addEventListener("wheel", e => {
  e.preventDefault(); zoom = Math.max(0.45, Math.min(3, zoom * Math.exp(-e.deltaY * 0.001))); draw();
}, { passive: false });
function reset() { yaw = -0.75; pitch = 0.35; zoom = 1; draw(); }
canvas.addEventListener("dblclick", reset);
document.getElementById("reset").addEventListener("click", reset);
new ResizeObserver(resize).observe(canvas.parentElement);
</script>
</body>
</html>"""
    (output_dir / "user_clusters_3d_interactive.html").write_text(
        template.replace("__DATA__", payload), encoding="utf-8",
    )


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

    table = build_feature_table(posts_path, max_posts_per_day)
    n_no_engagement = int((~table["has_engagement"]).sum())
    n_bots = int(table["is_bot"].sum())
    n_active = int((table["has_engagement"] & ~table["is_bot"]).sum())
    print(
        f"Total amount of accounts: {len(table):,}\n"
        f"Removed due to no engagement: {n_no_engagement:,}\n"
        f"Removed due to bot accounts "
        f"(> {max_posts_per_day:.1f} posts/day): {n_bots:,}\n"
        f"Still relevant for clustering: {n_active:,}",
        flush=True,
    )

    relevant_authors = set(table.loc[table["has_engagement"] & ~table["is_bot"], "author_id"])
    posts_written = write_relevant_posts(posts_path, relevant_authors, relevant_posts_path)
    active, best_k, scores = cluster(table, k_range, sample_size, random_state)

    best_k_by_davies_bouldin = min(scores["davies_bouldin"], key=scores["davies_bouldin"].get)
    print(f"Chosen k (silhouette): {best_k}, Best k according to Davies-Bouldin: {best_k_by_davies_bouldin}")

    summary = summarize_clusters(active)
    print("\n Cluster Summary")
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
    print(f"\nResults saved in {output_dir}")
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--posts-path", type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "post_table" / "posts.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=PROJECT_ROOT / "reports" / "clusters",
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
        parser.exit(1, f"Could not complete clustering: {error}\n")

if __name__ == "__main__":
    main()
