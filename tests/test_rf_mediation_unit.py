"""Unit tests for scripts.research_framework.mediation module.

The module emits a DeprecationWarning on import, so we suppress it via
``filterwarnings``. This is the intended behavior of the test.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def MODULE_ABBREV():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    # The module is explicitly deprecated — silence warning during import.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from scripts.research_framework import mediation as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_mediation_result_dataclass(MODULE_ABBREV):
    import dataclasses

    MediationResult = MODULE_ABBREV.MediationResult
    assert dataclasses.is_dataclass(MediationResult)
    fields = [f.name for f in dataclasses.fields(MediationResult)]
    assert len(fields) > 0


def test_sobel_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.sobel)


def test_bootstrap_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.bootstrap)


def test_classify_mediation_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.classify_mediation)


def test_class_attributes(MODULE_ABBREV):
    """The class methods / functions are accessible by attribute lookup."""
    for name in ("sobel", "bootstrap", "classify_mediation"):
        assert hasattr(MODULE_ABBREV, name)
