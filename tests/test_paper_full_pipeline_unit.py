"""Unit tests for scripts/paper_full_pipeline.py.

Covers: load_empirical_data, build_paper_prompt, generate_paper,
de_ai_polish, generate_word, _launch_dashboard, main, _fallback_csv_data,
constants (PROJECT_ROOT, OUTPUT_DIR, CACHE_DIR, DE_AI_PROMPT, TARIFF_RESULTS).
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pfp():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import paper_full_pipeline as m
    yield m
    if _p in sys.path:
        sys.path.remove(_p)


class TestConstants:
    """Module-level path and config constants."""

    def test_project_root_is_path(self, pfp):
        assert isinstance(pfp.PROJECT_ROOT, Path)

    def test_output_dir_is_path(self, pfp):
        assert isinstance(pfp.OUTPUT_DIR, Path)

    def test_cache_dir_is_path(self, pfp):
        assert isinstance(pfp.CACHE_DIR, Path)

    def test_tariff_results_is_path(self, pfp):
        assert isinstance(pfp.TARIFF_RESULTS, Path)

    def test_de_ai_prompt_nonempty_string(self, pfp):
        assert isinstance(pfp.DE_AI_PROMPT, str)
        assert len(pfp.DE_AI_PROMPT) > 100


class TestStepFunctions:
    """load_empirical_data, build_paper_prompt, generate_paper, de_ai_polish,
    generate_word, _launch_dashboard are all callable pipeline steps."""

    def test_load_empirical_data_callable(self, pfp):
        assert callable(pfp.load_empirical_data)

    def test_build_paper_prompt_signature(self, pfp):
        sig = inspect.signature(pfp.build_paper_prompt)
        assert "data" in sig.parameters

    def test_generate_paper_callable(self, pfp):
        assert callable(pfp.generate_paper)

    def test_de_ai_polish_callable(self, pfp):
        assert callable(pfp.de_ai_polish)

    def test_generate_word_signature(self, pfp):
        sig = inspect.signature(pfp.generate_word)
        assert "paper" in sig.parameters

    def test_launch_dashboard_callable(self, pfp):
        assert callable(pfp._launch_dashboard)


class TestFallbackCsvData:
    """_fallback_csv_data reads legacy CSVs into dict-of-markdown."""

    def test_function_exists(self, pfp):
        assert callable(pfp._fallback_csv_data)

    def test_returns_dict(self, pfp):
        result = pfp._fallback_csv_data()
        assert isinstance(result, dict)
        # Either empty (no legacy CSVs) or contains expected keys
        if result:
            assert any(k in result for k in [
                "core_findings_md",
                "did_summary_md",
                "heterogeneity_md",
                "mediation_md",
                "descriptive_md",
                "robustness_md",
            ])


class TestMain:
    """main() is the pipeline entrypoint."""

    def test_function_exists(self, pfp):
        assert callable(pfp.main)


class TestBuildPaperPrompt:
    """build_paper_prompt embeds data into Markdown prompt."""

    def test_empty_data_returns_string(self, pfp):
        data = {
            "descriptive_md": "",
            "core_findings_md": "",
            "did_summary_md": "",
            "heterogeneity_md": "",
            "mediation_md": "",
        }
        result = pfp.build_paper_prompt(data)
        assert isinstance(result, str)
        assert len(result) > 500
        # Should contain structural hints
        assert "论文" in result or "摘要" in result

    def test_data_appears_in_prompt(self, pfp):
        data = {
            "descriptive_md": "TABLE_DESC_MARKER",
            "core_findings_md": "CORE_FINDINGS_MARKER",
            "did_summary_md": "DID_SUMMARY_MARKER",
            "heterogeneity_md": "HET_MARKER",
            "mediation_md": "MED_MARKER",
        }
        result = pfp.build_paper_prompt(data)
        assert "TABLE_DESC_MARKER" in result
        assert "CORE_FINDINGS_MARKER" in result
        assert "DID_SUMMARY_MARKER" in result
        assert "HET_MARKER" in result
        assert "MED_MARKER" in result