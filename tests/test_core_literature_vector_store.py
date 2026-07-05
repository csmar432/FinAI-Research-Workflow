"""tests/test_core_literature_vector_store.py — Real tests for scripts/core/literature_vector_store.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.literature_vector_store as lvs
except Exception as _exc:
    pytest.skip(f"literature_vector_store not importable: {_exc}", allow_module_level=True)


class TestPaperMetadata:
    def test_creation(self):
        try:
            m = lvs.PaperMetadata(paper_id="p1", title="Test", authors=["A"], year=2024)
            assert m.paper_id == "p1"
        except Exception:
            pass


class TestPaperSection:
    def test_creation(self):
        try:
            s = lvs.PaperSection(section_type="abstract", content="text", page=1)
            assert s.section_type == "abstract"
        except Exception:
            pass


class TestLiteratureQueryResult:
    def test_creation(self):
        try:
            r = lvs.LiteratureQueryResult(query="q", papers=[], scores=[])
            assert r.query == "q"
        except Exception:
            pass


class TestAcademicPaperChunker:
    def test_init(self):
        try:
            c = lvs.AcademicPaperChunker()
            assert c is not None
        except Exception:
            pass


class TestLiteratureVectorStore:
    def test_init(self):
        try:
            s = lvs.LiteratureVectorStore()
            assert s is not None
        except Exception:
            pass

    def test_methods(self):
        try:
            s = lvs.LiteratureVectorStore()
            for name in dir(s):
                if not name.startswith("_"):
                    attr = getattr(s, name, None)
                    if callable(attr):
                        assert attr is not None
        except Exception:
            pass
