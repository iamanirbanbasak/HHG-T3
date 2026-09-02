from __future__ import annotations

import pytest

from facechain.profiles import Account, group_accounts, handle_of, platform_of


class TestPlatform:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.instagram.com/p/ABC/", "instagram"),
        ("https://x.com/someone/status/1", "x"),
        ("https://au.linkedin.com/in/jane-doe", "linkedin"),
        ("https://www.tiktok.com/@user/video/1", "tiktok"),
        ("https://bsky.app/profile/a.bsky.social", "bsky"),
        ("https://github.com/jane", "github"),
        ("https://example.org/x", "example.org"),
    ])
    def test_platform_detection(self, url, expected):
        assert platform_of(url) == expected


class TestHandle:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.instagram.com/janedoe/", "janedoe"),
        ("https://x.com/janedoe", "janedoe"),
        ("https://x.com/janedoe/status/123", "janedoe"),
        ("https://www.linkedin.com/in/jane-doe-123/", "jane-doe-123"),
        ("https://www.tiktok.com/@janedoe/video/1", "janedoe"),
        ("https://www.reddit.com/user/janedoe/", "janedoe"),
        ("https://github.com/janedoe", "janedoe"),
        ("https://github.com/janedoe/some-repo", "janedoe"),
    ])
    def test_extracts_handle(self, url, expected):
        assert handle_of(url) == expected

    @pytest.mark.parametrize("url", [
        "https://www.instagram.com/p/C9gkjieTRAb/",     # permalink carries no handle
        "https://www.instagram.com/reel/DcTqtCuytGq/",
        "https://www.linkedin.com/pub/dir/+/Farsee",
        "https://www.youtube.com/shorts/JBvyPIxgyM8",
        "https://github.com/features/copilot",
    ])
    def test_returns_none_rather_than_guessing(self, url):
        """Inventing a handle would attach a fabricated identity to a real score."""
        assert handle_of(url) is None


class TestGrouping:
    def test_posts_from_one_account_collapse(self):
        accts = group_accounts([
            ("https://x.com/jane/status/1", 0.81),
            ("https://x.com/jane/status/2", 0.77),
        ])
        assert len(accts) == 1
        assert accts[0].handle == "jane" and len(accts[0].urls) == 2
        assert accts[0].best_cosine == pytest.approx(0.81)

    def test_unknown_handles_are_not_merged(self):
        accts = group_accounts([
            ("https://www.instagram.com/p/AAA/", 0.9),
            ("https://www.instagram.com/p/BBB/", 0.8),
        ])
        assert len(accts) == 2, "posts without handles must not be merged into one account"

    def test_sorted_by_best_score(self):
        accts = group_accounts([
            ("https://x.com/low", 0.5), ("https://x.com/high", 0.95),
        ])
        assert [a.handle for a in accts] == ["high", "low"]

    def test_profile_url_derived_where_possible(self):
        a = group_accounts([("https://x.com/jane/status/1", 0.8)])[0]
        assert a.profile_url == "https://x.com/jane"

    def test_github_profile_url(self):
        a = group_accounts([("https://github.com/jane/repo", 0.8)])[0]
        assert a.platform == "github" and a.handle == "jane"
        assert a.profile_url == "https://github.com/jane"

    def test_no_profile_url_when_handle_unknown(self):
        a = group_accounts([("https://www.instagram.com/p/AAA/", 0.8)])[0]
        assert a.profile_url is None
        assert "(post)" in a.display
