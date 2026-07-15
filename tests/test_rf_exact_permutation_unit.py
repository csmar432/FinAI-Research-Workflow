"""Unit tests for scripts.research_framework.exact_permutation module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def MODULE_ABBREV():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.research_framework import exact_permutation as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_exact_permutation_result_dataclass(MODULE_ABBREV):
    """ExactPermutationResult is a dataclass."""
    import dataclasses

    ExactPermutationResult = MODULE_ABBREV.ExactPermutationResult
    assert dataclasses.is_dataclass(ExactPermutationResult)


def test_exact_permutation_result_fields(MODULE_ABBREV):
    """ExactPermutationResult exposes its fields (for inspection)."""
    import dataclasses

    ExactPermutationResult = MODULE_ABBREV.ExactPermutationResult
    fields = [f.name for f in dataclasses.fields(ExactPermutationResult)]
    assert len(fields) > 0
    # all field names are strings
    for f in fields:
        assert isinstance(f, str)


def test_exact_permutation_function_exists(MODULE_ABBREV):
    """exact_permutation_test is callable."""
    fn = MODULE_ABBREV.exact_permutation_test
    assert callable(fn)


def test_exact_permutation_function_signature(MODULE_ABBREV):
    """Function has at least one parameter (besides self)."""
    import inspect

    fn = MODULE_ABBREV.exact_permutation_test
    sig = inspect.signature(fn)
    assert len(sig.parameters) >= 1
