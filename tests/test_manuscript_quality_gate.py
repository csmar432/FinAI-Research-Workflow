"""Tests for scripts/research_framework/manuscript_quality_gate.py"""

from __future__ import annotations

from scripts.research_framework.manuscript_quality_gate import (
    ManuscriptQualityGate,
    QualityReport,
    check_manuscript,
    count_cjk_chars,
    count_words,
    detect_language,
)


def test_count_cjk_chars_basic():
    assert count_cjk_chars("碳交易试点") == 5
    assert count_cjk_chars("abc 123 !@#") == 0
    assert count_cjk_chars("中文abc混合123") == 4


def test_count_words_basic():
    assert count_words("hello world foo") == 3
    assert count_words("") == 0


def test_detect_language_zh_vs_en():
    zh = "本文研究碳交易试点对城市能源转型的影响，采用多期双重差分方法。"
    en = "This paper studies the effect of carbon trading pilots on cities."
    assert detect_language(zh) == "zh"
    assert detect_language(en) == "en"


def test_detect_language_empty():
    assert detect_language("") == "en"
    assert detect_language("   \n  ") == "en"


def test_short_manuscript_flagged_too_short():
    md = "# 标题\n\n## 一、引言\n\n碳交易试点研究。\n"
    report = check_manuscript(md, language="zh", min_total_zh=8000)
    assert isinstance(report, QualityReport)
    assert report.language == "zh"
    assert not report.passed
    assert any(i.code == "TOO_SHORT" for i in report.issues)
    assert report.error_count() >= 1


def test_long_manuscript_passes_length():
    body = "碳" * 9000
    md = f"# 标题\n\n## 一、引言\n\n{body}\n\n## 免责声明\n\n本草稿由AI生成，需研究者逐字审阅后方可投稿。\n"
    report = check_manuscript(md, language="zh", min_total_zh=8000)
    assert report.total_chars >= 8000
    assert not any(i.code == "TOO_SHORT" for i in report.issues)


def test_disclaimer_detection():
    body = "碳" * 9000
    with_disc = f"## 引言\n\n{body}\n\n本文由AI生成，需研究者审阅。"
    without_disc = f"## 引言\n\n{body}"
    r1 = check_manuscript(with_disc, language="zh", min_total_zh=100)
    r2 = check_manuscript(without_disc, language="zh", min_total_zh=100)
    assert r1.has_disclaimer is True
    assert r2.has_disclaimer is False
    assert any(i.code == "NO_DISCLAIMER" for i in r2.issues)


def test_thin_section_detection():
    intro = "字" * 900
    litrev = "文献不足"  # way below 1000
    md = (
        f"# 标题\n\n## 一、引言\n\n{intro}\n\n"
        f"## 二、文献综述\n\n{litrev}\n\n"
        "本文由AI生成，需研究者审阅。"
    )
    report = check_manuscript(md, language="zh", min_total_zh=100)
    thin_titles = [s.title for s in report.section_stats if s.is_thin]
    assert any("文献" in t for t in thin_titles)
    assert any(i.code == "THIN_SECTION" for i in report.issues)


def test_abstract_not_flagged_thin():
    body = "字" * 900
    md = f"## 摘要\n\n短摘要。\n\n## 一、引言\n\n{body}\n\n本文由AI生成，需研究者审阅。"
    report = check_manuscript(md, language="zh", min_total_zh=100)
    abstract_stats = [s for s in report.section_stats if "摘要" in s.title]
    assert abstract_stats
    assert all(not s.is_thin for s in abstract_stats)


def test_tables_excluded_from_wordcount():
    table = "\n".join(["| a | b |", "|---|---|"] + ["| 数据 | 值 |"] * 50)
    md = f"## 结果\n\n{table}\n\n本文由AI生成，需研究者审阅。"
    report = check_manuscript(md, language="zh", min_total_zh=100)
    # table cell text should not inflate the prose count much
    assert report.total_chars < 60


def test_render_report_markdown_contains_sections():
    md = "## 一、引言\n\n碳交易试点研究。\n\n本文由AI生成，需研究者审阅。"
    gate = ManuscriptQualityGate(md, language="zh", min_total_zh=8000)
    gate.analyze()
    out = gate.render_report_markdown()
    assert "论文草稿质量门禁报告" in out
    assert "章节字数明细" in out


def test_print_report_smoke(capsys):
    md = "## 一、引言\n\n碳交易。\n"
    gate = ManuscriptQualityGate(md, language="zh")
    gate.analyze()
    gate.print_report()
    captured = capsys.readouterr()
    assert "论文草稿质量门禁报告" in captured.out


def test_english_manuscript_wordcount():
    body = " ".join(["word"] * 5000)
    md = f"## Introduction\n\n{body}\n\nThis draft is AI-generated and must be reviewed."
    report = check_manuscript(md, language="en", min_total_en=4000)
    assert report.language == "en"
    assert report.total_chars >= 4000
    assert not any(i.code == "TOO_SHORT" for i in report.issues)
