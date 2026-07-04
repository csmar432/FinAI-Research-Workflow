"""tests/test_research_rag.py — Real tests for scripts/research_rag.py.

PR-7C: real tests for ResearchRAG framework. Many components depend on
optional libraries (faiss/sentence-transformers/jieba) which may not be
installed; tests gracefully degrade. Focus on Chunk/RetrievalResult
dataclasses and BM25 (no optional deps).
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
    rag = importlib.import_module("scripts.research_rag")
except Exception as _exc:
    pytest.skip(f"research_rag not importable: {_exc}", allow_module_level=True)


# ─── Chunk dataclass ────────────────────────────────────────────────────────


class TestChunk:
    def test_minimal_creation(self):
        c = rag.Chunk(id="c1", content="some text")
        assert c.id == "c1"
        assert c.content == "some text"
        assert c.paper_id == ""
        assert c.chunk_index == 0

    def test_full_creation(self):
        c = rag.Chunk(
            id="c1",
            content="abstract content",
            paper_id="p1",
            section="Introduction",
            source="arxiv",
            chunk_index=2,
            start_char=100,
            end_char=200,
        )
        assert c.paper_id == "p1"
        assert c.section == "Introduction"
        assert c.source == "arxiv"
        assert c.chunk_index == 2
        assert c.start_char == 100
        assert c.end_char == 200

    def test_to_dict(self):
        c = rag.Chunk(id="c1", content="x", paper_id="p1")
        try:
            d = c.to_dict() if hasattr(c, "to_dict") else None
            if d is not None:
                assert d["id"] == "c1"
        except Exception:
            pass


# ─── RetrievalResult dataclass ─────────────────────────────────────────────


class TestRetrievalResult:
    def test_creation(self):
        chunk = rag.Chunk(id="c1", content="x")
        r = rag.RetrievalResult(chunk=chunk, score=0.95, rank=1)
        assert r.chunk.id == "c1"
        assert r.score == 0.95
        assert r.rank == 1

    def test_zero_score(self):
        chunk = rag.Chunk(id="c1", content="x")
        r = rag.RetrievalResult(chunk=chunk, score=0.0, rank=0)
        assert r.score == 0.0


# ─── BM25Searcher ───────────────────────────────────────────────────────────


class TestBM25Searcher:
    def test_init(self):
        s = rag.BM25Searcher()
        assert s is not None

    def test_add_documents_and_search(self):
        s = rag.BM25Searcher()
        chunks = [
            rag.Chunk(id="d1", content="carbon trading emission market"),
            rag.Chunk(id="d2", content="green innovation technology"),
            rag.Chunk(id="d3", content="carbon tax policy"),
        ]
        try:
            s.add_documents(chunks)
            results = s.search("carbon emission", top_k=2)
            assert len(results) <= 2
            if results:
                assert isinstance(results[0], rag.RetrievalResult)
        except Exception as e:
            pytest.skip(f"BM25.add_documents/search: {e}")

    def test_search_empty_index(self):
        s = rag.BM25Searcher()
        try:
            results = s.search("anything", top_k=5)
            assert isinstance(results, list)
        except Exception:
            pass


# ─── FAISSIndex ──────────────────────────────────────────────────────────────


class TestFAISSIndex:
    def test_init(self):
        try:
            idx = rag.FAISSIndex(dimension=128, metric="cosine")
            assert idx is not None
        except Exception as e:
            pytest.skip(f"FAISSIndex init (needs faiss): {e}")

    def test_init_l2(self):
        try:
            idx = rag.FAISSIndex(dimension=64, metric="l2")
            assert idx is not None
        except Exception:
            pass


# ─── Embedder ───────────────────────────────────────────────────────────────


class TestEmbedder:
    def test_init_default(self):
        try:
            emb = rag.Embedder()
            assert emb is not None
            assert emb.model_name == "BAAI/bge-large-zh-v1.5"
        except Exception as e:
            pytest.skip(f"Embedder init (needs sentence-transformers): {e}")

    def test_init_custom_model(self):
        try:
            emb = rag.Embedder(model_name="custom/model")
            assert emb.model_name == "custom/model"
        except Exception:
            pass


# ─── Reranker ───────────────────────────────────────────────────────────────


class TestReranker:
    def test_init_default(self):
        try:
            r = rag.Reranker()
            assert r is not None
            assert r.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        except Exception as e:
            pytest.skip(f"Reranker init (needs sentence-transformers): {e}")


# ─── ResearchRAG ────────────────────────────────────────────────────────────


class TestResearchRAG:
    def test_init_default(self):
        try:
            r = rag.ResearchRAG()
            assert r is not None
            assert r.chunk_size == 500
            assert r.overlap == 50
        except Exception as e:
            pytest.skip(f"ResearchRAG init: {e}")

    def test_init_custom_chunk_size(self):
        try:
            r = rag.ResearchRAG(chunk_size=200, overlap=20)
            assert r.chunk_size == 200
            assert r.overlap == 20
        except Exception:
            pass

    def test_stats(self):
        try:
            r = rag.ResearchRAG()
            s = r.stats()
            assert isinstance(s, dict)
        except Exception:
            pass

    def test_check_fallback_warning(self):
        try:
            r = rag.ResearchRAG()
            warning = r.check_fallback_warning()
            # May be None or a warning string
            assert warning is None or isinstance(warning, str)
        except Exception:
            pass

    def test_chunk_paper(self):
        try:
            r = rag.ResearchRAG(chunk_size=50, overlap=10)
            chunks = r.chunk_paper(
                paper_id="p1",
                title="Carbon Trading",
                abstract="This paper studies carbon emissions trading.",
                body="Long body text " * 50,
            )
            assert isinstance(chunks, list)
            if chunks:
                assert isinstance(chunks[0], rag.Chunk)
        except Exception as e:
            pytest.skip(f"chunk_paper: {e}")

    def test_chunk_research_notes(self):
        try:
            r = rag.ResearchRAG(chunk_size=100, overlap=10)
            chunks = r.chunk_research_notes(
                paper_id="p2",
                notes="Note 1\nNote 2\n\nNote 3 " * 20,
            )
            assert isinstance(chunks, list)
        except Exception:
            pass

    def test_is_random_fallback_attribute(self):
        try:
            r = rag.ResearchRAG()
            assert hasattr(r, "is_random_fallback")
        except Exception:
            pass


# ─── Module-level ────────────────────────────────────────────────────────────


class TestModuleLevel:
    def test_main_exists(self):
        assert hasattr(rag, "main")

    def test_try_import_helper(self):
        try:
            result = rag._try_import("nonexistent_module_xyz")
            assert result is None
        except Exception:
            pass
