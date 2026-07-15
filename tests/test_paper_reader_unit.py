"""Unit tests for scripts/paper_reader.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pr():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import paper_reader as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestPaperReader:
    def test_class_exists(self, pr):
        assert hasattr(pr, "PaperReader")

    def test_init(self, pr):
        reader = pr.PaperReader()
        assert reader is not None


class TestHelpers:
    def test_arxiv_id_from_url(self, pr):
        url = "https://arxiv.org/abs/2301.12345"
        arxiv_id = pr.arxiv_id_from_url(url)
        assert arxiv_id == "2301.12345"

    def test_arxiv_id_from_url_pdf(self, pr):
        url = "https://arxiv.org/pdf/2301.12345.pdf"
        arxiv_id = pr.arxiv_id_from_url(url)
        assert "2301.12345" in arxiv_id
