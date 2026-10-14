import unittest

from src.features import (
    WINDOW_DAYS, build_user_features, count_followers, count_unique_responders, detect_bots,
    estimate_shrinkage, shrink_mean,
)


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


class ShrinkageTests(unittest.TestCase):
    def test_estimates_prior_from_between_and_within_variance(self):
        # means [1, 3] over 2 posts each, std 1: within 1, between var([1, 3]) - 1/2 = 0.5
        prior_mean, prior_posts = estimate_shrinkage([2, 2], [1.0, 3.0], [1.0, 1.0])
        self.assertAlmostEqual(prior_mean, 2.0)
        self.assertAlmostEqual(prior_posts, 2.0)

    def test_raises_when_authors_do_not_differ_beyond_noise(self):
        with self.assertRaises(ValueError):
            estimate_shrinkage([2, 2], [1.0, 1.0], [1.0, 1.0])

    def test_shrink_mean_pulls_small_samples_toward_prior(self):
        self.assertAlmostEqual(shrink_mean(0, 2, prior_mean=2.0, prior_posts=2.0), 1.0)
        self.assertAlmostEqual(shrink_mean(2000, 1000, prior_mean=0.0, prior_posts=2.0), 2000 / 1002)


class CountFollowersTests(unittest.TestCase):
    def test_counts_union_of_following_and_subscriptions_for_requested_authors(self):
        following = [
            {"follower_id": "x", "followed_id": "a"},
            {"follower_id": "y", "followed_id": "a"},
            {"follower_id": "x", "followed_id": "other"},
        ]
        subscriptions = [
            {"subscriber_id": "x", "subscribed_to_id": "a"},
            {"subscriber_id": "z", "subscribed_to_id": "b"},
        ]
        self.assertEqual(
            count_followers(following, subscriptions, {"a", "b", "c"}), {"a": 2, "b": 1, "c": 0},
        )


class CountUniqueRespondersTests(unittest.TestCase):
    def test_counts_distinct_responders_per_author(self):
        rows = [
            {"author_id": "a", "responder_id": "x", "responses_7d": 5},
            {"author_id": "a", "responder_id": "y", "responses_7d": 1},
            {"author_id": "b", "responder_id": "x", "responses_7d": 2},
        ]
        self.assertEqual(count_unique_responders(rows), {"a": 2, "b": 1})


if __name__ == "__main__":
    unittest.main()
