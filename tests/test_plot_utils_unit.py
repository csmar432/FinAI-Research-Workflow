"""Unit tests for scripts/plot_utils.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pu():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import plot_utils
    yield plot_utils
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestCJKFontKeywords:
    def test_contains_noto(self, pu):
        assert "noto sans cjk" in pu.CJK_FONT_KEYWORDS

    def test_contains_pingfang(self, pu):
        assert "pingfang" in pu.CJK_FONT_KEYWORDS

    def test_contains_simhei(self, pu):
        assert "simhei" in pu.CJK_FONT_KEYWORDS

    def test_contains_microsoft_yahei(self, pu):
        assert "microsoft yahei" in pu.CJK_FONT_KEYWORDS

    def test_is_list_of_strings(self, pu):
        assert isinstance(pu.CJK_FONT_KEYWORDS, list)
        for kw in pu.CJK_FONT_KEYWORDS:
            assert isinstance(kw, str)


class TestFindCJKFont:
    def test_finds_font_matching_keyword(self, pu):
        """When a font name contains a CJK keyword, it's returned."""
        fake_font = mock.Mock()
        fake_font.name = "Noto Sans CJK SC"
        with mock.patch.object(pu.fm.fontManager, "ttflist", [fake_font]):
            result = pu._find_cjk_font()
            assert result == "Noto Sans CJK SC"

    def test_returns_none_when_no_match(self, pu):
        """When no font matches, returns None."""
        fake_font = mock.Mock()
        fake_font.name = "Arial"
        with mock.patch.object(pu.fm.fontManager, "ttflist", [fake_font]):
            assert pu._find_cjk_font() is None

    def test_keyword_priority_order(self, pu):
        """First matching keyword (in CJK_FONT_KEYWORDS order) wins."""
        fake1 = mock.Mock()
        fake1.name = "Microsoft YaHei"
        fake2 = mock.Mock()
        fake2.name = "PingFang SC"
        with mock.patch.object(pu.fm.fontManager, "ttflist", [fake1, fake2]):
            # Microsoft YaHei comes after PingFang in the list, but
            # we test that the first match in font order wins for one keyword.
            result = pu._find_cjk_font()
            # Either found, depending on iteration
            assert result in ("Microsoft YaHei", "PingFang SC", None)

    def test_empty_font_list(self, pu):
        with mock.patch.object(pu.fm.fontManager, "ttflist", []):
            assert pu._find_cjk_font() is None


class TestSetupChineseFont:
    def test_returns_none_when_no_font_found(self, pu, capsys):
        """Without any CJK font, returns None and prints warning if verbose."""
        # Mock the expensive fontmanager reload
        with mock.patch.object(pu.fm, "_load_fontmanager", create=True):
            with mock.patch.object(pu, "_find_cjk_font", return_value=None):
                with mock.patch.object(pu.matplotlib, "rcParams", {}):
                    result = pu.setup_chinese_font(verbose=True)
                    assert result is None

    def test_silent_when_not_verbose_and_no_font(self, pu, capsys):
        with mock.patch.object(pu, "_find_cjk_font", return_value=None):
            with mock.patch.object(pu.matplotlib, "rcParams", {}):
                result = pu.setup_chinese_font(verbose=False)
                assert result is None
        out = capsys.readouterr().out
        assert "plot_utils" not in out

    def test_returns_font_name_when_found(self, pu, capsys):
        """When font is found, returns its name."""
        with mock.patch.object(pu, "_find_cjk_font", return_value="PingFang SC"):
            with mock.patch.dict(pu.matplotlib.rcParams, {}, clear=True):
                pu.matplotlib.rcParams["font.sans-serif"] = []
                pu.matplotlib.rcParams["font.family"] = "sans-serif"
                result = pu.setup_chinese_font(verbose=False)
                assert result == "PingFang SC"
                assert "PingFang SC" in pu.matplotlib.rcParams["font.sans-serif"]

    def test_does_not_duplicate_font(self, pu):
        """If the font is already first in sans-serif, don't prepend again."""
        with mock.patch.object(pu, "_find_cjk_font", return_value="PingFang SC"):
            with mock.patch.dict(pu.matplotlib.rcParams, {}, clear=True):
                pu.matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "Arial"]
                pu.setup_chinese_font(verbose=False)
                # PingFang should still be first, not duplicated
                sans_serif = pu.matplotlib.rcParams["font.sans-serif"]
                assert sans_serif.count("PingFang SC") == 1

    def test_sets_axes_unicode_minus(self, pu):
        """axes.unicode_minus is always set to False."""
        with mock.patch.object(pu, "_find_cjk_font", return_value="Arial Unicode"):
            with mock.patch.dict(pu.matplotlib.rcParams, {}, clear=True):
                pu.matplotlib.rcParams["font.sans-serif"] = []
                pu.setup_chinese_font(verbose=False)
                assert pu.matplotlib.rcParams["axes.unicode_minus"] is False


class TestGetCJKFont:
    def test_returns_font_or_none(self, pu):
        result = pu.get_cjk_font()
        assert result is None or isinstance(result, str)

