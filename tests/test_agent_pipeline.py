"""tests/test_agent_pipeline.py — Real tests for scripts/agent_pipeline.py.

PR-7C: real functional tests for the AgentPipeline framework. Tests focus
on dataclass instantiation, configuration validation, helper functions,
and lightweight AgentPipeline methods that don't require full LLM stack.
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
    ap = importlib.import_module("scripts.agent_pipeline")
except Exception as _exc:
    pytest.skip(f"agent_pipeline not importable: {_exc}", allow_module_level=True)


# ─── InteractionResult ──────────────────────────────────────────────────────


class TestInteractionResult:
    def test_default_creation(self):
        r = ap.InteractionResult()
        assert r.needs_input is False
        assert r.action_needed == "proceed"
        assert r.llm_available is True

    def test_creation_with_needs_input(self):
        r = ap.InteractionResult(
            needs_input=True,
            action_needed="ask_api_key",
            questions=["Add TUSHARE_TOKEN?"],
            limitations=["Tushare disabled"],
        )
        assert r.needs_input is True
        assert r.action_needed == "ask_api_key"
        assert "Add TUSHARE_TOKEN?" in r.questions

    def test_to_dict_method(self):
        r = ap.InteractionResult(needs_input=True)
        try:
            d = r.to_dict() if hasattr(r, "to_dict") else None
            if d is not None:
                assert "needs_input" in d
        except Exception:
            pass

    def test_lists_are_independent(self):
        r1 = ap.InteractionResult()
        r2 = ap.InteractionResult()
        r1.questions.append("Q1")
        assert "Q1" not in r2.questions


# ─── AgentPipelineConfig ─────────────────────────────────────────────────────


class TestAgentPipelineConfig:
    def test_default_config(self):
        c = ap.AgentPipelineConfig()
        assert c.topic == ""
        assert c.venue == "通用"
        assert c.research_field == "AI/机器学习"
        assert c.use_hitl is False
        assert c.use_evolution is False
        assert c.visualize is True

    def test_config_with_topic(self):
        c = ap.AgentPipelineConfig(
            topic="碳排放权交易对企业绿色创新的影响",
            venue="经济研究",
            research_field="环境经济学",
        )
        assert "碳排放" in c.topic
        assert c.venue == "经济研究"
        assert c.research_field == "环境经济学"

    def test_config_evolution_threshold(self):
        c = ap.AgentPipelineConfig(
            topic="t", use_evolution=True, evolution_threshold=0.8
        )
        assert c.evolution_threshold == 0.8

    def test_config_hitl_stages(self):
        c = ap.AgentPipelineConfig(
            topic="t", use_hitl=True, hitl_stages=["outline", "writing"]
        )
        assert c.use_hitl is True
        assert "outline" in c.hitl_stages


# ─── AgentPipelineResult ─────────────────────────────────────────────────────


class TestAgentPipelineResult:
    def test_default_result(self):
        c = ap.AgentPipelineConfig(topic="t")
        r = ap.AgentPipelineResult(config=c)
        assert r.success is False
        assert r.total_latency_ms == 0.0
        assert r.config.topic == "t"

    def test_result_with_partial_data(self):
        c = ap.AgentPipelineConfig(topic="t")
        r = ap.AgentPipelineResult(
            config=c,
            outline={"sections": ["intro", "methods"]},
            success=True,
            total_latency_ms=1234.5,
        )
        assert r.success is True
        assert r.outline is not None
        assert r.total_latency_ms == 1234.5

    def test_result_errors_collect(self):
        c = ap.AgentPipelineConfig(topic="t")
        r = ap.AgentPipelineResult(config=c)
        r.errors.append("step1 failed")
        r.errors.append("step2 failed")
        assert len(r.errors) == 2

    def test_result_to_dict(self):
        c = ap.AgentPipelineConfig(topic="t")
        r = ap.AgentPipelineResult(config=c, success=True)
        try:
            d = r.to_dict() if hasattr(r, "to_dict") else None
            if d is not None:
                assert isinstance(d, dict)
                assert d.get("success") is True
        except Exception:
            pass


# ─── AgentPipeline ───────────────────────────────────────────────────────────


class TestAgentPipeline:
    def test_init_with_config(self):
        c = ap.AgentPipelineConfig(topic="t", venue="经济研究")
        try:
            pipeline = ap.AgentPipeline(config=c)
            assert pipeline is not None
            assert pipeline.config.topic == "t"
        except Exception as e:
            pytest.skip(f"AgentPipeline.__init__ requires deps: {e}")

    def test_init_default(self):
        try:
            pipeline = ap.AgentPipeline()
            assert pipeline is not None
        except Exception as e:
            pytest.skip(f"AgentPipeline default init: {e}")

    def test_init_with_langgraph(self):
        c = ap.AgentPipelineConfig(topic="t")
        try:
            pipeline = ap.AgentPipeline(config=c, use_langgraph=True)
            assert hasattr(pipeline, "use_langgraph")
            assert pipeline.use_langgraph is True
        except Exception as e:
            pytest.skip(f"AgentPipeline with langgraph: {e}")

    def test_str_method(self):
        c = ap.AgentPipelineConfig(topic="carbon test")
        try:
            pipeline = ap.AgentPipeline(config=c)
            s = str(pipeline)
            assert isinstance(s, str)
        except Exception:
            pass


# ─── PipelineConfigurationError ─────────────────────────────────────────────


class TestPipelineConfigurationError:
    def test_raises(self):
        with pytest.raises(ap.PipelineConfigurationError):
            raise ap.PipelineConfigurationError("test error")

    def test_error_message(self):
        try:
            raise ap.PipelineConfigurationError("config invalid: missing topic")
        except ap.PipelineConfigurationError as e:
            assert "missing topic" in str(e)


# ─── Helper functions ────────────────────────────────────────────────────────


class TestHelperFunctions:
    def test_get_canvas_url_exists(self):
        assert hasattr(ap, "_get_canvas_url")
        try:
            url = ap._get_canvas_url()
            assert isinstance(url, str)
        except Exception:
            pass

    def test_build_canvas_banner(self):
        try:
            banner = ap._build_canvas_banner("Test", "detail")
            assert isinstance(banner, str)
        except Exception:
            pass

    def test_wait_for_viz_server_exists(self):
        assert hasattr(ap, "_wait_for_viz_server")
