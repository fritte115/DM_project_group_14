import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from src.extract import read_comments, read_entries, read_likes, read_users
from src.transform import (
    OBSERVATION_END, POST_END, POST_START, RESPONSE_WINDOW,
    clean_likes, clean_users, is_response_in_window, parse_timestamp,
)


POST_COLUMNS = (
    "post_id", "author_id", "published_at", "likes_7d", "comments_7d",
    "has_image", "has_video",
)


def media_flag(value, field, stats):
    if value.strip().lower() in ("", "null", "\\n"):
        stats[f"{field}_missing"] += 1
        return ""
    try:
        count = int(value)
        if count < 0:
            raise ValueError
    except ValueError:
        stats[f"{field}_invalid"] += 1
        return ""
    return int(count > 0)


def response_status(post, actor, timestamp):
    if isinstance(post, str):
        return post
    author, published_at = post
    if timestamp < published_at:
        return "before_publication"
    if actor == author:
        return "self_response"
    if not is_response_in_window(published_at, timestamp):
        return "outside_response_window"
    return "included"


def build_posts(data_dir, output_dir):
    data_dir = Path(data_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    if output_dir.exists():
        raise FileExistsError(f"Resultatmappen finns redan: {output_dir}")
    filenames = (
        "users.csv", "likes.csv", "commentAugSept.csv",
        "entries1.csv", "entries2.csv", "entries3.csv",
    )
    for name in filenames:
        if not (data_dir / name).is_file():
            raise FileNotFoundError(data_dir / name)

    print("Läser konton …", flush=True)
    users = {row["id"]: row["type"] for row in clean_users(read_users(data_dir / "users.csv"))}
    report = {
        "rules": {
            "post_start_inclusive": str(POST_START),
            "post_end_exclusive": str(POST_END),
            "observation_end_exclusive": str(OBSERVATION_END),
            "response_window_days": RESPONSE_WINDOW.days,
            "account_type": "user",
            "exclude_self_responses": True,
            "likes": "earliest timestamp per exact userID/PostID pair, before filtering",
            "missing_media": "blank, not zero",
            "response_exclusion_order": [
                "missing_post", "post_outside_period", "unknown_author", "group_author",
                "before_publication", "self_response", "outside_response_window",
            ],
        },
        "source_files": {
            name: {"bytes": (data_dir / name).stat().st_size,
                   "mtime_ns": (data_dir / name).stat().st_mtime_ns}
            for name in filenames
        },
        "unique_accounts": len(users),
        "entries": Counter(), "likes": Counter(), "comments": Counter(),
        "media": Counter(), "output": Counter(),
    }

    posts = {}
    for name, reader, filename, post_column in (
        ("likes", read_likes, "likes.csv", "PostID"),
        ("comments", read_comments, "commentAugSept.csv", "EntryID"),
    ):
        print(f"Samlar inläggsreferenser från {filename} …", flush=True)
        for row in reader(data_dir / filename):
            posts[row[post_column]] = "missing_post"
            report[name]["raw_rows"] += 1

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".post-table-", dir=output_dir.parent) as temp:
        stage = Path(temp)
        base_path = stage / "base.csv"
        with base_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            for filename in ("entries1.csv", "entries2.csv", "entries3.csv"):
                print(f"Läser {filename} …", flush=True)
                for number, entry in enumerate(read_entries(data_dir / filename), start=1):
                    report["entries"]["raw_rows"] += 1
                    post_id, author = entry["PostID"], entry["PostedBy"]
                    if post_id.strip().lower() in ("", "null", "\\n"):
                        raise ValueError(f"{filename}, rad {number}: saknat PostID")
                    published_at = parse_timestamp(entry["Timestamp"])
                    if not POST_START <= published_at < POST_END:
                        status = "post_outside_period"
                    elif author not in users:
                        status = "unknown_author"
                    elif users[author] != "user":
                        status = "group_author"
                    else:
                        status = "included"
                    report["entries"][status] += 1
                    if post_id in posts:
                        posts[post_id] = (author, published_at) if status == "included" else status
                    if status == "included":
                        writer.writerow([
                            post_id, author, str(published_at),
                            media_flag(entry["NumImg"], "image", report["media"]),
                            media_flag(entry["NumVideo"], "video", report["media"]),
                        ])
                    if number % 500_000 == 0:
                        print(f"  {number:,} rader lästa", flush=True)

        counts = {"likes": Counter(), "comments": Counter()}
        for name, rows, post_column, actor_column in (
            ("likes", clean_likes(read_likes(data_dir / "likes.csv")), "PostID", "userID"),
            ("comments", read_comments(data_dir / "commentAugSept.csv"), "EntryID", "PostedBy"),
        ):
            print(f"Räknar {name} …", flush=True)
            for row in rows:
                report[name]["evaluated_rows"] += 1
                post_id, actor = row[post_column], row[actor_column]
                if actor.strip().lower() in ("", "null", "\\n"):
                    raise ValueError(f"{name}: respons saknar konto-ID")
                timestamp = row["Timestamp"] if name == "likes" else parse_timestamp(row["Timestamp"])
                status = response_status(posts[post_id], actor, timestamp)
                report[name][status] += 1
                if status == "included":
                    counts[name][post_id] += 1
                    if actor not in users:
                        report[name]["included_unknown_actor"] += 1
        report["likes"]["duplicate_rows_removed"] = (
            report["likes"]["raw_rows"] - report["likes"]["evaluated_rows"]
        )
        del posts, users

        print("Sparar inläggstabellen …", flush=True)
        with base_path.open(encoding="utf-8", newline="") as source:
            with (stage / "posts.csv").open("w", encoding="utf-8", newline="") as target:
                writer = csv.writer(target)
                writer.writerow(POST_COLUMNS)
                for post_id, author, published_at, image, video in csv.reader(source):
                    likes = counts["likes"].get(post_id, 0)
                    comments = counts["comments"].get(post_id, 0)
                    writer.writerow([post_id, author, published_at, likes, comments, image, video])
                    report["output"]["rows"] += 1
                    report["output"]["likes_7d"] += likes
                    report["output"]["comments_7d"] += comments
                    if likes == 0 and comments == 0:
                        report["output"]["zero_response_posts"] += 1

        assert report["output"]["rows"] == report["entries"]["included"]
        assert report["output"]["likes_7d"] == report["likes"]["included"]
        assert report["output"]["comments_7d"] == report["comments"]["included"]
        base_path.unlink()
        (stage / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        stage.rename(output_dir)

    for key, count in report["output"].items():
        print(f"{key}: {count:,}")
    print(f"Resultat: {output_dir}")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir or args.data_dir.expanduser() / "processed" / "post_table"
    try:
        build_posts(args.data_dir, output_dir)
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        parser.exit(1, f"Kunde inte bygga inläggstabellen: {error}\n")


if __name__ == "__main__":
    main()
