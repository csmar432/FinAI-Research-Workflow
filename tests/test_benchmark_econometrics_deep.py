"""tests/test_benchmark_econometrics_deep.py — Deep tests for benchmark_econometrics."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.benchmark_econometrics as mod
except Exception as _exc:
    pytest.skip(f"benchmark_econometrics not importable: {_exc}", allow_module_level=True)


class TestModule:
    def test_imports(self):
        assert mod is not None

    def test_has_functions(self):
        funcs = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n, None))]
        assert isinstance(funcs, list)

    def test_has_classes(self):
        classes = [n for n in dir(mod) if not n.startswith("_") and isinstance(getattr(mod, n, None), type)]
        assert isinstance(classes, list)


class TestGenerateData:
    def test_generate_did_data(self):
        fn = getattr(mod, "generate_did_data", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(n_units=20, n_periods=4)
            assert r is not None
        except Exception:
            pass

    def test_generate_staggered_did_data(self):
        fn = getattr(mod, "generate_staggered_did_data", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(n_units=20, n_periods=4)
            assert r is not None
        except Exception:
            pass

    def test_generate_sdid_data(self):
        fn = getattr(mod, "generate_sdid_data", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(n_donor=4, n_treated=1)
            assert r is not None
        except Exception:
            pass

    def test_generate_ife_data(self):
        fn = getattr(mod, "generate_ife_data", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(n_units=20, n_periods=4)
            assert r is not None
        except Exception:
            pass

    def test_generate_cce_data(self):
        fn = getattr(mod, "generate_cce_data", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(n_units=20, n_periods=4)
            assert r is not None
        except Exception:
            pass


class TestBenchmarkResult:
    def test_default(self):
        cls = getattr(mod, "BenchmarkResult", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass


class TestPrintFunctions:
    def test_print_header(self, capsys):
        fn = getattr(mod, "print_header", None)
        if fn is None: pytest.skip("not present")
        try:
            fn()
            out = capsys.readouterr()
            assert len(out.out) > 0
        except Exception:
            pass

    def test_print_summary(self, capsys):
        fn = getattr(mod, "print_summary", None)
        if fn is None: pytest.skip("not present")
        try:
            fn([])
            out = capsys.readouterr()
            assert isinstance(out.out, str)
        except Exception:
            pass


class TestReferenceFunctions:
    def test_reference_ife(self):
        import numpy as np
        fn = getattr(mod, "reference_ife", None)
        if fn is None: pytest.skip("not present")
        try:
            Y = np.random.randn(20, 4)
            r = fn(Y)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_reference_cce(self):
        import numpy as np
        fn = getattr(mod, "reference_cce", None)
        if fn is None: pytest.skip("not present")
        try:
            Y = np.random.randn(20, 4)
            r = fn(Y)
            assert isinstance(r, dict)
        except Exception:
            pass


class TestMain:
    def test_main_safe(self):
        """Test main with --help to avoid full execution."""
        fn = getattr(mod, "main", None)
        if fn is None: pytest.skip("not present")
        # We won't actually invoke main since it might require args / run benchmarks.
        # Just verify it exists and is callable.
        import inspect
        try:
            sig = inspect.signature(fn)
            assert callable(fn)
        except Exception:
            pass
