import unittest

from src.features import WINDOW_DAYS, build_user_features, detect_bots


def post(author, likes=0, comments=0):
    return {"author_id": author, "likes_7d": likes, "comments_7d": comments}


class BuildUserFeaturesTests(unittest.TestCase):
    def test_aggregates_per_author(self):
        posts = [
            post("a"),
            post("b", likes=1),
            post("b"),
            post("c", likes=2),
            post("c"),
            post("c", comments=4),
        ]
        features = build_user_features(posts)

        self.assertEqual(set(features), {"a", "b", "c"})
        self.assertEqual(features["a"]["post_count"], 1)
        self.assertEqual(features["a"]["engagement_total"], 0)
        self.assertEqual(features["a"]["engagement_rate"], 0.0)
        self.assertEqual(features["a"]["std_engagement"], 0.0)

        b = features["b"]
        self.assertEqual(b["post_count"], 2)
        self.assertEqual(b["likes_total"], 1)
        self.assertEqual(b["comments_total"], 0)
        self.assertEqual(b["engagement_total"], 1)
        self.assertEqual(b["posts_with_engagement"], 1)
        self.assertEqual(b["engagement_rate"], 0.5)
        self.assertEqual(b["mean_engagement"], 0.5)
        self.assertEqual(b["std_engagement"], 0.5)
        self.assertEqual(b["posts_per_day"], 2 / WINDOW_DAYS)

        # per-post engagement [2, 0, 4]: mean 2, population variance 8/3
        c = features["c"]
        self.assertEqual(c["mean_engagement"], 2.0)
        self.assertAlmostEqual(c["std_engagement"], (8 / 3) ** 0.5)


class DetectBotsTests(unittest.TestCase):
    def test_flags_only_accounts_strictly_above_the_threshold(self):
        features = {
            "below": {"posts_per_day": 49.9},
            "at": {"posts_per_day": 50.0},
            "above": {"posts_per_day": 50.1},
        }
        self.assertEqual(detect_bots(features, max_posts_per_day=50.0), {"above"})

    def test_empty_features_flags_nothing(self):
        self.assertEqual(detect_bots({}, max_posts_per_day=50.0), set())


if __name__ == "__main__":
    unittest.main()
