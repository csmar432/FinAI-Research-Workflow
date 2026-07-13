"""Tests for scripts/research_framework/reference_validator.py"""

from __future__ import annotations

from scripts.research_framework.reference_validator import (
    ReferenceReport,
    ReferenceValidator,
    validate_references,
)


def _make_refs(n: int) -> str:
    lines = []
    for i in range(1, n + 1):
        lines.append(f"[{i}] Author{i}, A. ({2000 + i % 20}). Title {i}. Journal.")
    return "\n".join(lines)


def test_too_few_references_flagged():
    body = "正文引用 [1] 和 [2]。\n\n## 参考文献\n\n" + _make_refs(2)
    report = validate_references(body, min_references=25)
    assert isinstance(report, ReferenceReport)
    assert report.n_references == 2
    assert any(i.code == "TOO_FEW_REFS" for i in report.issues)
    assert not report.passed


def test_enough_references_pass_count():
    body_citations = " ".join(f"[{i}]" for i in range(1, 31))
    md = f"正文 {body_citations}\n\n## 参考文献\n\n" + _make_refs(30)
    report = validate_references(md, min_references=25)
    assert report.n_references == 30
    assert not any(i.code == "TOO_FEW_REFS" for i in report.issues)


def test_ghost_citation_detected():
    # reference [3] listed but never cited in body
    md = "正文只引用了 [1] 和 [2]。\n\n## 参考文献\n\n" + _make_refs(3)
    report = validate_references(md, min_references=1)
    assert "[3]" in report.ghost_citations
    assert any(i.code == "GHOST_CITATION" for i in report.issues)


def test_dangling_citation_detected():
    # body cites [5] but only 3 refs exist
    md = "正文引用 [1] [2] [3] [5]。\n\n## 参考文献\n\n" + _make_refs(3)
    report = validate_references(md, min_references=1)
    assert "[5]" in report.dangling_citations
    assert any(i.code == "DANGLING_CITATION" for i in report.issues)
    assert not report.passed  # dangling is an error


def test_citation_range_parsing():
    md = "正文引用 [1-3]。\n\n## 参考文献\n\n" + _make_refs(3)
    report = validate_references(md, min_references=1)
    # all of 1,2,3 cited via range → no ghost
    assert report.ghost_citations == []


def test_method_not_implemented_detected():
    refs = _make_refs(25)
    refs += "\n[26] Callaway, B., & Sant'Anna, P. (2021). Difference-in-Differences. J Econometrics."
    citations = " ".join(f"[{i}]" for i in range(1, 27))
    md = f"正文使用传统双向固定效应 TWFE。{citations}\n\n## 参考文献\n\n{refs}"
    report = validate_references(
        md,
        min_references=25,
        method_claims={"Callaway": ["csdid", "组别-时间", "att_gt", "group-time"]},
    )
    assert "Callaway" in report.unimplemented_methods
    assert any(i.code == "METHOD_NOT_IMPLEMENTED" for i in report.issues)


def test_method_implemented_not_flagged():
    refs = _make_refs(25)
    refs += "\n[26] Callaway, B., & Sant'Anna, P. (2021). Difference-in-Differences. J Econometrics."
    citations = " ".join(f"[{i}]" for i in range(1, 27))
    md = (
        f"正文实施了 Callaway 的组别-时间平均处理效应估计。{citations}"
        f"\n\n## 参考文献\n\n{refs}"
    )
    report = validate_references(
        md,
        min_references=25,
        method_claims={"Callaway": ["csdid", "组别-时间", "att_gt"]},
    )
    assert "Callaway" not in report.unimplemented_methods


def test_no_reference_section():
    md = "正文没有参考文献节。"
    report = validate_references(md, min_references=25)
    assert report.n_references == 0
    assert any(i.code == "TOO_FEW_REFS" for i in report.issues)


def test_doi_extraction():
    md = (
        "引用 [1]。\n\n## 参考文献\n\n"
        "[1] Shen, Y. (2023). ETI dataset. DOI: 10.1038/s41597-023-02815-7"
    )
    report = validate_references(md, min_references=1)
    assert report.entries[0].doi == "10.1038/s41597-023-02815-7"


def test_print_report_smoke(capsys):
    md = "引用 [1]。\n\n## 参考文献\n\n" + _make_refs(1)
    v = ReferenceValidator(md, min_references=25)
    v.analyze()
    v.print_report()
    out = capsys.readouterr().out
    assert "参考文献完备性检查报告" in out


def test_references_heading_english():
    body_citations = " ".join(f"[{i}]" for i in range(1, 31))
    md = f"body {body_citations}\n\n## References\n\n" + _make_refs(30)
    report = validate_references(md, min_references=25)
    assert report.n_references == 30
