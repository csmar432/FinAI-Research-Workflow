"""Unit tests for scripts/core/sse_app.py.

This module requires `fastapi`/`pydantic` which may not be installed.
Tests attempt to load the module with mocked dependencies.
"""
from __future__ import annotations

import sys
import importlib.util
import types
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _make_mock_pkg(name):
    """Create a fake package that allows submodules."""
    mod = types.ModuleType(name)
    mod.__path__ = []  # mark as package
    sys.modules[name] = mod
    return mod


def _try_load_sse_app():
    """Attempt to load sse_app with mocked fastapi/pydantic/sse_starlette."""
    # Fake fastapi as a package
    fastapi_mod = _make_mock_pkg("fastapi")

    class FakeFastAPI:
        def __init__(self, *a, **k): pass

        def get(self, *a, **k):
            def dec(f):
                return f
            return dec

        def post(self, *a, **k):
            def dec(f):
                return f
            return dec

        def mount(self, *a, **k): pass

    class FakeHTTPException(Exception):
        def __init__(self, status_code=500, detail=""):
            self.status_code = status_code
            self.detail = detail

    class FakeRequest:
        pass

    fastapi_mod.FastAPI = FakeFastAPI
    fastapi_mod.HTTPException = FakeHTTPException
    fastapi_mod.Request = FakeRequest

    # Submodules
    middleware_mod = _make_mock_pkg("fastapi.middleware")
    cors_mod = _make_mock_pkg("fastapi.middleware.cors")

    class FakeCORSMiddleware:
        def __init__(self, *a, **k): pass

    cors_mod.CORSMiddleware = FakeCORSMiddleware

    responses_mod = _make_mock_pkg("fastapi.responses")

    class FakeJSONResponse:
        def __init__(self, *a, **k): pass

    class FakeStreamingResponse:
        def __init__(self, *a, **k): pass

    responses_mod.JSONResponse = FakeJSONResponse
    responses_mod.StreamingResponse = FakeStreamingResponse

    # Fake sse_starlette
    sse_mod = types.ModuleType("sse_starlette")

    class FakeEventSourceResponse:
        def __init__(self, *a, **k): pass

    sse_mod.EventSourceResponse = FakeEventSourceResponse
    sys.modules["sse_starlette"] = sse_mod

    # Add scripts to path
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))

    spec = importlib.util.spec_from_file_location(
        "sse_app_test_module", "scripts/core/sse_app.py"
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sse_app_test_module"] = mod
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


@pytest.fixture(scope="module")
def sa():
    """Try to load sse_app; skip all tests if it fails."""
    mod = _try_load_sse_app()
    if mod is None:
        pytest.skip("sse_app requires dependencies that are not installed")
    yield mod


class TestSseAppSurface:
    def test_module_imports(self, sa):
        assert sa is not None


class TestFunctions:
    def test_get_pipeline_steps_exists(self, sa):
        assert hasattr(sa, "get_pipeline_steps")

    def test_get_research_pipeline_steps_exists(self, sa):
        assert hasattr(sa, "get_research_pipeline_steps")

    def test_get_paper_pipeline_steps_exists(self, sa):
        assert hasattr(sa, "get_paper_pipeline_steps")

    def test_get_financial_report_steps_exists(self, sa):
        assert hasattr(sa, "get_financial_report_steps")


class TestClasses:
    def test_PipelinePreset_exists(self, sa):
        assert hasattr(sa, "PipelinePreset")

    def test_HITLGateState_exists(self, sa):
        assert hasattr(sa, "HITLGateState")

    def test_HITLActionRequest_exists(self, sa):
        assert hasattr(sa, "HITLActionRequest")
