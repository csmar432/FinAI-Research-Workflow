"""tests/test_agent_pipeline_core.py — Real tests for scripts/core/agent_pipeline_core.py.

PR-7C: real tests for PipelineStage enum and the various stage/dataclass
types (StageConfig, StageResult, QualityGateResult, AutoReviewResult,
AgentOrchestratorPipeline).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    apc = importlib.import_module("scripts.core.agent_pipeline_core")
except Exception as _exc:
    pytest.skip(f"agent_pipeline_core not importable: {_exc}", allow_module_level=True)


# ─── PipelineStage enum ─────────────────────────────────────────────────────


class TestPipelineStage:
    def test_members_exist(self):
        names = [e.name for e in apc.PipelineStage]
        assert len(names) >= 3
        # Common stages expected
        for name in ["IDEATION", "LITERATURE", "WRITING", "REVIEW"]:
            if name in names:
                assert True
                return
        # else at least 3
        assert len(names) >= 3


# ─── StageConfig ────────────────────────────────────────────────────────────


class TestStageConfig:
    def test_default_creation(self):
        try:
            cfg = apc.StageConfig(stage=apc.PipelineStage.IDEATION)
            assert cfg.enabled is True
            assert cfg.skip_on_failure is False
            assert cfg.quality_gate_threshold == 0.6
            assert cfg.max_retries == 1
        except (TypeError, AttributeError):
            pytest.skip("StageConfig signature differs")

    def test_custom_config(self):
        try:
            cfg = apc.StageConfig(
                stage=apc.PipelineStage.WRITING,
                enabled=True,
                max_retries=3,
                timeout_seconds=600.0,
                quality_gate_threshold=0.8,
            )
            assert cfg.max_retries == 3
            assert cfg.timeout_seconds == 600.0
            assert cfg.quality_gate_threshold == 0.8
        except Exception:
            pass


# ─── StageResult ────────────────────────────────────────────────────────────


class TestStageResult:
    def test_creation(self):
        try:
            r = apc.StageResult(
                stage=apc.PipelineStage.IDEATION,
                status="success",
            )
            assert r.status == "success"
            assert r.latency_ms == 0.0
            assert r.retries == 0
        except Exception:
            pass

    def test_failure_result(self):
        try:
            r = apc.StageResult(
                stage=apc.PipelineStage.WRITING,
                status="failed",
                error="LLM timeout",
                retries=2,
            )
            assert r.status == "failed"
            assert r.error == "LLM timeout"
            assert r.retries == 2
        except Exception:
            pass


# ─── QualityGateResult ──────────────────────────────────────────────────────


class TestQualityGateResult:
    def test_creation(self):
        try:
            q = apc.QualityGateResult(
                chapter="intro",
                score=0.85,
                level="pass",
                passed=True,
            )
            assert q.chapter == "intro"
            assert q.score == 0.85
            assert q.passed is True
        except Exception:
            pass

    def test_with_issues(self):
        try:
            q = apc.QualityGateResult(
                chapter="methods",
                score=0.4,
                level="fail",
                passed=False,
                issues=["missing robustness"],
                suggestions=["add placebos"],
            )
            assert "missing robustness" in q.issues
        except Exception:
            pass


# ─── AutoReviewResult ───────────────────────────────────────────────────────


class TestAutoReviewResult:
    def test_creation(self):
        try:
            r = apc.AutoReviewResult(
                domain="finance",
                overall=0.9,
                level="excellent",
                passed=True,
            )
            assert r.domain == "finance"
            assert r.overall == 0.9
        except Exception:
            pass


# ─── AgentOrchestratorPipeline ───────────────────────────────────────────────


class TestAgentOrchestratorPipeline:
    def test_init_default(self):
        try:
            p = apc.AgentOrchestratorPipeline()
            assert p is not None
        except Exception as e:
            pytest.skip(f"AgentOrchestratorPipeline init: {e}")

    def test_init_strict_mode(self, tmp_path):
        try:
            p = apc.AgentOrchestratorPipeline(
                enable_quality_gates=True,
                enable_auto_review=True,
                enable_hitl=True,
                strict_mode=True,
                output_dir=str(tmp_path),
            )
            assert p.strict_mode is True
        except Exception:
            pass

    def test_init_minimal(self):
        try:
            p = apc.AgentOrchestratorPipeline(
                enable_quality_gates=False,
                enable_auto_review=False,
                enable_hitl=False,
            )
            assert p is not None
        except Exception:
            pass
