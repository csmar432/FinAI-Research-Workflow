"""Unit tests for scripts/update_related_stars.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def urs():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import update_related_stars
    yield update_related_stars
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestFormatStars:
    def test_under_1000(self, urs):
        assert urs.format_stars(0) == "0"
        assert urs.format_stars(999) == "999"

    def test_at_1000(self, urs):
        # 1000 → 1.0K
        assert urs.format_stars(1000) == "1.0K"

    def test_above_1000(self, urs):
        assert urs.format_stars(8200) == "8.2K"

    def test_at_million(self, urs):
        # Python int division
        assert urs.format_stars(1_500_000) == "1500.0K"


class TestRepoLinkRegex:
    def test_matches_simple_link(self, urs):
        m = urs.REPO_LINK_RE.search("[name](https://github.com/owner/repo)")
        assert m is not None
        assert m.group("name") == "name"
        assert m.group("owner") == "owner"
        assert m.group("repo") == "repo"

    def test_matches_with_subgroup(self, urs):
        text = "see [link](https://github.com/foo/bar)"
        m = urs.REPO_LINK_RE.search(text)
        assert m is not None
        assert m.group("owner") == "foo"
        assert m.group("repo") == "bar"


class TestStarsRegex:
    def test_matches_with_k(self, urs):
        m = urs.STARS_RE.search("(8.1K ⭐)")
        assert m is not None
        assert m.group("stars") == "8.1K"

    def test_matches_plain_number(self, urs):
        m = urs.STARS_RE.search("(274 ⭐)")
        assert m is not None
        assert m.group("stars") == "274"

    def test_matches_5digit(self, urs):
        m = urs.STARS_RE.search("(8208 ⭐)")
        assert m is not None


class TestFindRelatedSection:
    def test_finds_section(self, urs):
        text = "intro\n## Related Projects\nstuff\n## Other\n"
        result = urs.find_related_section(text)
        assert result is not None
        start, end = result
        assert start > 0
        assert "Related Projects" in text[start:end]
        assert "stuff" in text[start:end]

    def test_returns_none_when_missing(self, urs):
        text = "no related section here"
        assert urs.find_related_section(text) is None

    def test_stops_at_next_section(self, urs):
        """Section ends at the next ## heading."""
        text = "## Related Projects\nbody\n## Next\nmore"
        result = urs.find_related_section(text)
        assert result is not None
        start, end = result
        # body between Related Projects and Next heading
        assert text[start:end].startswith("## Related Projects")
        assert not text[start:end].startswith("## Next")


class TestFetchStars:
    def test_returns_int_on_success(self, urs, monkeypatch):
        mock_resp = mock.Mock()
        mock_resp.read.return_value = b'{"stargazers_count": 42}'
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(urs.urllib.request, "urlopen", return_value=mock_resp):
            assert urs.fetch_stars("foo", "bar") == 42

    def test_returns_none_on_404(self, urs, monkeypatch):
        """404 → None."""
        err = urllib_error_HTTPError(404)
        with mock.patch.object(urs.urllib.request, "urlopen", side_effect=err):
            assert urs.fetch_stars("foo", "bar") is None

    def test_returns_none_on_rate_limit(self, urs, monkeypatch):
        err = urllib_error_HTTPError(403)
        with mock.patch.object(urs.urllib.request, "urlopen", side_effect=err):
            assert urs.fetch_stars("foo", "bar") is None

    def test_returns_none_on_invalid_json(self, urs, monkeypatch):
        mock_resp = mock.Mock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(urs.urllib.request, "urlopen", return_value=mock_resp):
            # The code does json.loads which raises JSONDecodeError, caught by
            # the (urllib.error.URLError, TimeoutError, json.JSONDecodeError) handler
            assert urs.fetch_stars("foo", "bar") is None


def urllib_error_HTTPError(code):
    import urllib.error
    return urllib.error.HTTPError(
        url="http://x",
        code=code,
        msg=f"HTTP {code}",
        hdrs=None,
        fp=None,
    )

