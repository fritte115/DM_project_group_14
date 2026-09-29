import csv
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from build_posts import build_posts


def write_rows(path, rows, delimiter="\t"):
    path.write_text(
        "".join(delimiter.join(row) + "\n" for row in rows), encoding="utf-8",
    )


def entry(post_id, author="a", timestamp="2010-08-10 12:00:00", image="0"):
    return [post_id, author, "", "", "\\N", "\\N", timestamp, "", image, "", "0", ""]


class BuildPostsTests(unittest.TestCase):
    def test_response_counts_and_exclusions(self):
        with TemporaryDirectory() as temp:
            data = Path(temp)
            write_rows(data / "users.csv", [
                ["a", "user", "A", "", "old"],
                ["a", "user", "A", "", "new"],
                ["g", "group", "G", "", ""],
            ], "|")
            write_rows(data / "entries1.csv", [
                entry("p"), entry("zero", image="\\N"), entry("group", author="g"),
                entry("unknown", author="absent"),
            ])
            write_rows(data / "entries2.csv", [
                entry("late", timestamp="2010-09-24 00:00:00"),
                entry("last", timestamp="2010-09-23 23:59:59", image="bad"),
            ])
            write_rows(data / "entries3.csv", [])
            likes = [
                ["b", "p", "2010-08-10 12:00:00"],
                ["b", "p", "2010-08-10 12:00:00"],
                ["b", "p", "2010-08-11 12:00:00"],
                ["a", "p", "2010-08-10 13:00:00"],
                ["c", "p", "2010-08-17 12:00:00"],
                ["d", "p", "2010-08-09 12:00:00"],
                ["d", "p", "2010-08-11 12:00:00"],
                ["e", "missing", "2010-08-11 12:00:00"],
                ["e", "group", "2010-08-11 12:00:00"],
                ["e", "unknown", "2010-08-11 12:00:00"],
                ["e", "late", "2010-09-25 00:00:00"],
                ["e", "last", "2010-09-30 23:59:58"],
                ["f", "last", "2010-10-01 00:00:00"],
            ]
            write_rows(data / "likes.csv", likes)
            write_rows(data / "commentAugSept.csv", [
                [f"p/c/{i}", "p", actor, "", "", "\\N", "\\N", timestamp, text]
                for i, (actor, timestamp, text) in enumerate([
                    ("b", "2010-08-10 13:00:00", ""),
                    ("b", "2010-08-10 13:00:00", "another"),
                    ("a", "2010-08-10 13:00:00", "self"),
                    ("b", "2010-08-17 12:00:00", "late"),
                ])
            ])
            before = {p.name: p.read_bytes() for p in data.iterdir()}
            output = data / "output"
            with redirect_stdout(io.StringIO()):
                report = build_posts(data, output)
            with (output / "posts.csv").open(newline="") as file:
                rows = {row["post_id"]: row for row in csv.DictReader(file)}
            self.assertEqual(set(rows), {"p", "zero", "last"})
            self.assertEqual((rows["p"]["likes_7d"], rows["p"]["comments_7d"]), ("1", "2"))
            self.assertEqual(rows["zero"]["likes_7d"], "0")
            self.assertEqual(rows["last"]["likes_7d"], "1")
            self.assertEqual(rows["zero"]["has_image"], "")
            self.assertEqual(rows["last"]["has_image"], "")
            self.assertEqual(report["likes"]["duplicate_rows_removed"], 3)
            self.assertEqual(report["likes"]["before_publication"], 1)
            self.assertEqual(report["likes"]["included_unknown_actor"], 2)
            self.assertEqual(report["output"]["zero_response_posts"], 1)
            self.assertEqual(before, {name: (data / name).read_bytes() for name in before})
            with self.assertRaises(FileExistsError):
                build_posts(data, output)


if __name__ == "__main__":
    unittest.main()
