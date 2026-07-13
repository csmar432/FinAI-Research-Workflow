"""reference_validator.py — 参考文献完备性与虚假引用静态检查

针对论文草稿的参考文献做静态校验，标记：
  - 参考文献数量不足（中文 CSSCI 实证论文通常 ≥ 25 条）
  - 「幽灵引用」：出现在参考文献列表但正文从未引用
  - 「悬空引用」：正文引用了某编号/作者，但参考文献列表缺失
  - 「方法挂名」：把某方法学文献列进参考文献，但正文并未实施该方法
    （对应审计中 Callaway-Sant'Anna / Sun-Abraham 被列引但未实施）
  - DOI 形态可疑（不满足 10.xxxx/ 前缀）

【设计原则】
- 纯静态、不联网：DOI 只做**形态**校验，不解析真伪。
- 只标记，不改写。
- 中英文引用体裁都尽量兼容（[1] 数字式 / (Author, Year) 作者-年份式）。

【用法】
    from scripts.research_framework.reference_validator import validate_references
    report = validate_references(md_text, min_references=25,
                                 method_claims={"Callaway": ["csdid", "组别-时间"]})
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ── ANSI Colors ────────────────────────────────────────────────────────────────

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


# ── 数据结构 ────────────────────────────────────────────────────────────────────


@dataclass
class ReferenceEntry:
    raw: str
    index: Optional[int]  # [1] 式编号；作者-年份式为 None
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None


@dataclass
class RefIssue:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str


@dataclass
class ReferenceReport:
    n_references: int
    entries: list[ReferenceEntry]
    ghost_citations: list[str]      # 列出但正文未引用
    dangling_citations: list[str]   # 正文引用但列表缺失
    unimplemented_methods: list[str]  # 方法挂名但正文未实施
    suspicious_dois: list[str]
    issues: list[RefIssue]
    passed: bool
    summary_message: str

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ── 解析 helpers ─────────────────────────────────────────────────────────────────

_DOI_RE = re.compile(r"10\.\d{3,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
_YEAR_RE = re.compile(r"(19|20)\d{2}")
# 参考文献节标题
_REF_HEADING_RE = re.compile(
    r"^#{1,6}\s*(参考文献|References|REFERENCES|Bibliography|引用文献)\s*$"
)
# 数字式条目：[1] xxx  或  1. xxx
_NUM_ENTRY_RE = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)[.)])\s+(.*)$")


def _extract_reference_section(md_text: str) -> list[str]:
    """抽取参考文献节的所有非空行。找不到节则返回 []。"""
    lines = md_text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if _REF_HEADING_RE.match(ln.strip()):
            start = i + 1
            break
    if start is None:
        return []
    out: list[str] = []
    for ln in lines[start:]:
        # 下一个同级/更高标题结束参考文献节
        if re.match(r"^#{1,6}\s+\S", ln) and not _REF_HEADING_RE.match(ln.strip()):
            break
        if ln.strip():
            out.append(ln.rstrip())
    return out


def _parse_entries(ref_lines: list[str]) -> list[ReferenceEntry]:
    entries: list[ReferenceEntry] = []
    for ln in ref_lines:
        m = _NUM_ENTRY_RE.match(ln)
        if m:
            idx = int(m.group(1) or m.group(2))
            body = m.group(3)
        else:
            # 非编号行：可能是作者-年份式，或上一条的续行。
            # 简化处理：只把有年份或 DOI 的行视为独立条目。
            if _YEAR_RE.search(ln) or _DOI_RE.search(ln):
                idx = None
                body = ln.strip()
            else:
                continue
        doi_m = _DOI_RE.search(body)
        year_m = _YEAR_RE.search(body)
        # 作者：取条目开头到第一个 . 或 年份 之前的片段中的大写词
        authors = re.findall(r"[A-Z][a-zA-Z\u4e00-\u9fff]+", body[:60])
        entries.append(
            ReferenceEntry(
                raw=ln.strip(),
                index=idx,
                authors=authors[:3],
                year=int(year_m.group(0)) if year_m else None,
                doi=doi_m.group(0) if doi_m else None,
            )
        )
    return entries


def _body_without_references(md_text: str) -> str:
    """返回去掉参考文献节之后的正文，用于统计正文引用。"""
    lines = md_text.splitlines()
    for i, ln in enumerate(lines):
        if _REF_HEADING_RE.match(ln.strip()):
            return "\n".join(lines[:i])
    return md_text


def _find_numeric_citations(body: str) -> set[int]:
    """正文中的 [1] / [1,2] / [1-3] 数字引用。"""
    cited: set[int] = set()
    for m in re.finditer(r"\[([\d,\s\-–]+)\]", body):
        token = m.group(1)
        for part in re.split(r"[,\s]+", token):
            part = part.strip()
            if not part:
                continue
            rng = re.match(r"(\d+)\s*[-–]\s*(\d+)$", part)
            if rng:
                a, b = int(rng.group(1)), int(rng.group(2))
                if a <= b and b - a < 200:
                    cited.update(range(a, b + 1))
            elif part.isdigit():
                cited.add(int(part))
    return cited


class ReferenceValidator:
    """参考文献完备性与虚假引用静态检查器。"""

    def __init__(
        self,
        md_text: str,
        *,
        min_references: int = 25,
        method_claims: Optional[dict[str, list[str]]] = None,
    ) -> None:
        """
        Args:
            md_text: 论文 Markdown 全文。
            min_references: 参考文献数量下限。
            method_claims: {方法学文献标识 -> [正文应出现的实施证据关键词]}。
                若某文献被列入参考文献，但其任一实施关键词都未在正文出现，
                则标记为「方法挂名（未实施）」。
                例：{"Callaway": ["csdid", "组别-时间", "group-time", "att_gt"]}
        """
        self.md_text = md_text or ""
        self.min_references = min_references
        self.method_claims = method_claims or {}
        self._report: Optional[ReferenceReport] = None

    def analyze(self) -> ReferenceReport:
        ref_lines = _extract_reference_section(self.md_text)
        entries = _parse_entries(ref_lines)
        body = _body_without_references(self.md_text)

        issues: list[RefIssue] = []

        # 1. 数量检查
        n_refs = len(entries)
        if n_refs < self.min_references:
            issues.append(
                RefIssue(
                    severity="error",
                    code="TOO_FEW_REFS",
                    message=f"参考文献仅 {n_refs} 条，低于建议下限 {self.min_references} 条",
                )
            )

        # 2. 数字式幽灵/悬空引用
        numbered = {e.index for e in entries if e.index is not None}
        ghost: list[str] = []
        dangling: list[str] = []
        if numbered:
            cited = _find_numeric_citations(body)
            for idx in sorted(numbered):
                if idx not in cited:
                    ghost.append(f"[{idx}]")
            for idx in sorted(cited):
                if idx not in numbered:
                    dangling.append(f"[{idx}]")
            if ghost:
                issues.append(
                    RefIssue(
                        severity="warning",
                        code="GHOST_CITATION",
                        message=f"以下参考文献在正文未被引用：{', '.join(ghost)}",
                    )
                )
            if dangling:
                issues.append(
                    RefIssue(
                        severity="error",
                        code="DANGLING_CITATION",
                        message=f"以下正文引用在参考文献列表缺失：{', '.join(dangling)}",
                    )
                )

        # 3. 方法挂名（未实施）
        unimplemented: list[str] = []
        ref_blob = "\n".join(e.raw for e in entries)
        body_low = body.lower()
        for marker, evidence_kws in self.method_claims.items():
            if marker.lower() in ref_blob.lower():
                implemented = any(kw.lower() in body_low for kw in evidence_kws)
                if not implemented:
                    unimplemented.append(marker)
        if unimplemented:
            issues.append(
                RefIssue(
                    severity="warning",
                    code="METHOD_NOT_IMPLEMENTED",
                    message=(
                        "以下方法学文献被列入参考文献，但正文未见实施证据："
                        f"{', '.join(unimplemented)}"
                    ),
                )
            )

        # 4. 可疑 DOI（有 doi 字样但形态不符）
        suspicious: list[str] = []
        for e in entries:
            if "doi" in e.raw.lower() and not e.doi:
                suspicious.append(e.raw[:50])
        if suspicious:
            issues.append(
                RefIssue(
                    severity="info",
                    code="SUSPICIOUS_DOI",
                    message=f"{len(suspicious)} 条声称含 DOI 但形态不符（10.xxxx/…）",
                )
            )

        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        passed = error_count == 0

        summary = (
            f"[{'通过' if passed else '未通过'}] "
            f"参考文献={n_refs} 幽灵={len(ghost)} 悬空={len(dangling)} "
            f"方法挂名={len(unimplemented)} "
            f"错误={error_count} 警告={warning_count}"
        )

        self._report = ReferenceReport(
            n_references=n_refs,
            entries=entries,
            ghost_citations=ghost,
            dangling_citations=dangling,
            unimplemented_methods=unimplemented,
            suspicious_dois=suspicious,
            issues=issues,
            passed=passed,
            summary_message=summary,
        )
        return self._report

    def print_report(self, report: Optional[ReferenceReport] = None) -> None:
        r = report or self._report or self.analyze()
        print()
        print(c("═" * 64, CYAN))
        print(c("  参考文献完备性检查报告", CYAN))
        print(c("═" * 64, CYAN))
        print()
        col = GREEN if r.n_references >= self.min_references else RED
        print(f"  参考文献条数: {c(str(r.n_references), col)}（建议下限 {self.min_references}）")
        print()

        if r.dangling_citations:
            print(c("  🔴 悬空引用（正文引用但列表缺失）:", RED))
            print(f"     {', '.join(r.dangling_citations)}")
            print()
        if r.ghost_citations:
            print(c("  🟡 幽灵引用（列表有但正文未引用）:", YELLOW))
            print(f"     {', '.join(r.ghost_citations)}")
            print()
        if r.unimplemented_methods:
            print(c("  🟡 方法挂名（列引但未实施）:", YELLOW))
            print(f"     {', '.join(r.unimplemented_methods)}")
            print()

        if r.issues:
            print(c("  问题清单:", BOLD))
            for i in r.issues:
                icon = {"error": c("🔴", RED), "warning": c("🟡", YELLOW), "info": c("⚪", DIM)}.get(
                    i.severity, "•"
                )
                print(f"    {icon} [{i.code}] {i.message}")
            print()

        verdict = c("✅ 通过", GREEN) if r.passed else c("❌ 未通过", RED)
        print(f"  结论: {verdict}")
        print(c("─" * 64, CYAN))
        print()


# ── 便捷函数 ────────────────────────────────────────────────────────────────────


def validate_references(
    md_text: str,
    min_references: int = 25,
    method_claims: Optional[dict[str, list[str]]] = None,
) -> ReferenceReport:
    """一行调用：校验参考文献并返回报告。"""
    return ReferenceValidator(
        md_text, min_references=min_references, method_claims=method_claims
    ).analyze()
