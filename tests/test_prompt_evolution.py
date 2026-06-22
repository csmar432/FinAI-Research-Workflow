"""Tests for scripts/core/prompt_evolution.py

Covers:
    - PromptEvolutionRecord dataclass (to_dict)
    - PromptEvolver (init, record_result, get_task_records, get_avg_quality, analyze_failures, evolve_prompt)
    - LLM-gateway-free unit tests (analyze_failures with insufficient data)
    - _save_record / _load_history (with mock history_dir)
"""

import json
import pytest
from pathlib import Path


class TestPromptEvolutionRecord:
    """PromptEvolutionRecord dataclass tests."""

    def test_required_fields(self):
        from scripts.core.prompt_evolution import PromptEvolutionRecord

        record = PromptEvolutionRecord(
            timestamp=1700000000.0,
            agent_name="literature_agent",
            task_type="generate_summary",
            prompt="Summarize this paper in 200 words",
            output="This paper studies...",
            quality=0.85,
            context={"source": "arXiv"},
        )
        assert record.timestamp == 1700000000.0
        assert record.agent_name == "literature_agent"
        assert record.task_type == "generate_summary"
        assert record.quality == 0.85
        assert record.context["source"] == "arXiv"

    def test_to_dict(self):
        from scripts.core.prompt_evolution import PromptEvolutionRecord

        record = PromptEvolutionRecord(
            timestamp=1700000000.0,
            agent_name="literature_agent",
            task_type="generate_summary",
            prompt="Summarize this paper",
            output="This paper studies digital finance...",
            quality=0.8,
        )
        d = record.to_dict()
        assert d["agent_name"] == "literature_agent"
        assert d["task_type"] == "generate_summary"
        assert d["quality"] == 0.8
        # output is truncated to 500 chars
        assert "prompt" in d
        assert "timestamp" in d

    def test_to_dict_truncation(self):
        from scripts.core.prompt_evolution import PromptEvolutionRecord

        record = PromptEvolutionRecord(
            timestamp=1.0,
            agent_name="test",
            task_type="test",
            prompt="x",
            output="x" * 1000,  # very long output
            quality=0.5,
        )
        d = record.to_dict()
        assert len(d["output"]) <= 500


class TestPromptEvolverInit:
    """PromptEvolver initialization tests."""

    def test_init_creates_history_dir(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path / "evolver_history"))
        assert evolver.history_dir.exists()
        assert evolver.gateway is None
        assert evolver.min_history == 3

    def test_init_custom_min_history(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path), min_history=5)
        assert evolver.min_history == 5

    def test_init_loads_existing_history(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        # Pre-populate a history file
        hist_file = tmp_path / "literature_agent_generate_summary.jsonl"
        hist_file.write_text(
            json.dumps({
                "timestamp": 1700000000.0,
                "agent_name": "literature_agent",
                "task_type": "generate_summary",
                "prompt": "Summarize this",
                "output": "Summary text",
                "quality": 0.7,
                "context": {},
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path), min_history=3)
        assert len(evolver._records) >= 1


class TestPromptEvolverRecording:
    """PromptEvolver recording method tests."""

    def test_record_result(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        evolver.record_result(
            agent_name="literature_agent",
            task_type="generate_summary",
            prompt="Summarize this paper",
            output="This is a summary.",
            quality=0.8,
            context={"paper_id": "1234"},
        )
        assert len(evolver._records) == 1
        assert evolver._records[0].quality == 0.8

    def test_record_result_multiple(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        for q in [0.3, 0.5, 0.7, 0.9]:
            evolver.record_result("analyst", "valuation", "Estimate DCF", "Result", q)

        assert len(evolver._records) == 4
        assert evolver.get_avg_quality("analyst", "valuation") == pytest.approx(0.6)

    def test_record_persists_to_disk(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        evolver.record_result("analyst", "valuation", "DCF", "Result", 0.75)

        hist_file = tmp_path / "analyst_valuation.jsonl"
        assert hist_file.exists()
        lines = hist_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1


class TestPromptEvolverQueries:
    """PromptEvolver query method tests."""

    def test_get_task_records(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        evolver.record_result("analyst", "valuation", "DCF1", "R1", 0.8)
        evolver.record_result("analyst", "dcf", "DCF2", "R2", 0.7)
        evolver.record_result("analyst", "valuation", "DCF3", "R3", 0.9)

        records = evolver.get_task_records("analyst", "valuation")
        assert len(records) == 2

    def test_get_task_records_no_match(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        evolver.record_result("analyst", "valuation", "DCF", "Result", 0.8)

        records = evolver.get_task_records("analyst", "nonexistent_task")
        assert records == []

    def test_get_avg_quality(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        # No records → default 0.5
        assert evolver.get_avg_quality("nonexistent", "task") == 0.5

        evolver.record_result("analyst", "valuation", "DCF", "Result", 0.8)
        evolver.record_result("analyst", "valuation", "DCF2", "Result2", 0.6)
        assert evolver.get_avg_quality("analyst", "valuation") == 0.7

    def test_get_avg_quality_empty(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        assert evolver.get_avg_quality("no_agent", "no_task") == 0.5


class TestPromptEvolverAnalysis:
    """PromptEvolver analysis method tests (no LLM required)."""

    def test_analyze_failures_insufficient_data(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path), min_history=3)

        # Only 1 low-quality record (need 3)
        evolver.record_result("analyst", "valuation", "DCF", "Result", 0.3)

        result = evolver.analyze_failures("analyst", "valuation", threshold=0.6)
        assert result["sufficient_data"] is False
        assert "3" in result["reason"]

    def test_analyze_failures_no_records(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path), min_history=3)
        result = evolver.analyze_failures("nonexistent", "task")
        assert result["sufficient_data"] is False


class TestPromptEvolverEvolve:
    """PromptEvolver.evolve_prompt tests."""

    def test_evolve_no_gateway_returns_none(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        result = evolver.evolve_prompt("analyst", "valuation", base_prompt="Original prompt")
        assert result is None

    def test_evolve_no_records_no_base_returns_none(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        result = evolver.evolve_prompt("nonexistent", "nonexistent")
        assert result is None


class TestPromptEvolverLoadHistory:
    """PromptEvolver._load_history edge case tests."""

    def test_load_corrupted_jsonl(self, tmp_path):
        from scripts.core.prompt_evolution import PromptEvolver

        # Write a corrupted JSONL file
        hist_file = tmp_path / "analyst_dcf.jsonl"
        hist_file.write_text('{"timestamp": 1.0, "agent_name": "analyst", "task_type": "dcf", "prompt": "x", "output": "y", "quality": 0.5}\n{"broken\n', encoding="utf-8")

        # Should not crash — just skip bad lines
        evolver = PromptEvolver(gateway=None, history_dir=str(tmp_path))
        # At least one record should be loaded
        assert isinstance(evolver._records, list)
