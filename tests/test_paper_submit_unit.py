"""Unit tests for scripts/paper_submit.py (pure helper functions)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


class TestLoadPaper:
    def test_loads_existing_file(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("Hello world", encoding="utf-8")
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            from paper_submit import load_paper
            content = load_paper(str(f))
            assert content == "Hello world"
        finally:
            if str(SCRIPTS_DIR) in sys.path:
                sys.path.remove(str(SCRIPTS_DIR))

    def test_raises_on_missing_file(self, tmp_path):
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            from paper_submit import load_paper
            with pytest.raises(FileNotFoundError):
                load_paper(str(tmp_path / "nonexistent.txt"))
        finally:
            if str(SCRIPTS_DIR) in sys.path:
                sys.path.remove(str(SCRIPTS_DIR))


class TestSaveOutput:
    def test_saves_file(self, tmp_path):
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import paper_submit as ps
            original = ps.OUTPUT_DIR
            ps.OUTPUT_DIR = tmp_path
            try:
                from paper_submit import save_output
                result = save_output("test content", "test_file.txt")
                assert (tmp_path / "test_file.txt").exists()
                assert (tmp_path / "test_file.txt").read_text() == "test content"
            finally:
                ps.OUTPUT_DIR = original
        finally:
            if str(SCRIPTS_DIR) in sys.path:
                sys.path.remove(str(SCRIPTS_DIR))


class TestPrintHelpers:
    """Print helpers exist and are callable."""

    def test_print_plagiarism_report_callable(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            from paper_submit import print_plagiarism_report
            assert callable(print_plagiarism_report)
        finally:
            if str(SCRIPTS_DIR) in sys.path:
                sys.path.remove(str(SCRIPTS_DIR))

    def test_print_latex_report_callable(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            from paper_submit import print_latex_report
            assert callable(print_latex_report)
        finally:
            if str(SCRIPTS_DIR) in sys.path:
                sys.path.remove(str(SCRIPTS_DIR))

