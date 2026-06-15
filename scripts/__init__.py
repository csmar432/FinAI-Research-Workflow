"""
Scripts package
"""

import logging as _logging
import os as _os

# ── Optional: Research RAG ────────────────────────────────────────────────────

_rag_logger = _logging.getLogger("scripts.research_rag")
# Probe for optional dependencies lazily — demote to DEBUG so the INFO
# startup banner is not polluted when faiss/sentence-transformers/jieba are absent.
if not _os.environ.get("RAG_VERBOSE"):
    _rag_logger.setLevel(_logging.WARNING)

try:
    from scripts.research_rag import (
        BM25Searcher,
        Chunk,
        Embedder,
        Reranker,
        ResearchRAG,
        RetrievalResult,
    )
except ImportError:
    # Graceful degradation — RAG is optional
    pass
else:
    _HAS_RAG = True
finally:
    _HAS_RAG = False

__all__ = [
    # AI Router
    "AI",
    "Task",
    # Knowledge Graph
    "KnowledgeGraph",
    "PaperNode",
    "CitationEdge",
    "SemanticScholarClient",
    # Research RAG (may be absent if optional deps missing)
    "ResearchRAG",
    "Chunk",
    "RetrievalResult",
    "Embedder",
    "BM25Searcher",
    "Reranker",
]
