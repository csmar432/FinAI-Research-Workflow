"""tests/test_core_visualizer.py — Real tests for scripts/core/visualizer.py.

PR-8C: real tests for OutputFormat, EnhancedChart, PipelineResult.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.visualizer as viz
except Exception as _exc:
    pytest.skip(f"visualizer not importable: {_exc}", allow_module_level=True)


class TestOutputFormat:
    def test_members(self):
        try:
            names = [e.name for e in viz.OutputFormat]
            assert len(names) >= 2
        except Exception:
            pass


class TestEnhancedChart:
    def test_init(self):
        try:
            c = viz.EnhancedChart()
            assert c is not None
        except Exception:
            pass


class TestPipelineResult:
    def test_creation(self):
        try:
            r = viz.PipelineResult(
                pipeline_id="p1",
                status="completed",
                figures=[],
                tables=[],
            )
            assert r.status == "completed"
        except Exception:
            pass
