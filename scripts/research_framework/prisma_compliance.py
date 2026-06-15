"""
prisma_compliance.py — PRISMA 2020 Systematic Review Compliance Engine

PRISMA 2020 (Page et al. 2021) seven-stage flow:
  1. Identification: search strategy management (boolean/MeSH/semantic)
  2. Screening: dual-blind with conflict resolution
  3. Included: final inclusion set
  4. Characterisation: PICO/PECOs data extraction
  5. Risk of Bias: ROBINS-I (observational) / Cochrane ROB2 (RCT)
  6. Synthesis: narrative + quantitative (meta-analysis)
  7. Report: PRISMA Flowchart auto-generation + GRADE evidence quality

Usage:
    from scripts.research_framework.prisma_compliance import (
        PRISMAFlowchart, PICOExtractor, ROBAssessment, PRISMAReport
    )

References:
  - Page MJ, McKenzie JE, Bossuyt PM, et al. (2021). The PRISMA 2020 statement.
    BMJ 2021;372:n71. doi:10.1136/bmj.n71
  - Sterne JA, et al. (2019). ROBINS-I: a tool for assessing risk of bias in
    non-randomised studies of interventions. BMJ 2016;355:i4919.
  - Higgins JPT, et al. (2019). Cochrane RoB 2 tool. doi:10.5281/zenodo.3555026
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = [
    "PRISMAStage",
    "PRISMAStageStatus",
    "GRADEQuality",
    "SearchStrategy",
    "ScreeningRecord",
    "PICOExtract",
    "ROBAssessment",
    "PRISMAFlowchart",
    "PRISMAReport",
]

_log = logging.getLogger("prisma_compliance")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PRISMAStage(Enum):
    """
    PRISMA 2020 七个阶段枚举。

    Each stage maps to the PRISMA 2020 statement sections and the
    standard flow diagram boxes (Page et al., BMJ 2021).
    """
    IDENTIFICATION = 1   # 数据库检索 + 额外来源
    SCREENING = 2        # 标题/摘要筛选 + 全文筛选
    INCLUDED = 3         # 最终纳入文献
    CHARACTERISATION = 4 # PICO/PECOs 数据提取
    RISK_OF_BIAS = 5     # 偏倚风险评估 (ROBINS-I / ROB2)
    SYNTHESIS = 6        # 叙事合成 + 定量合成 (Meta 分析)
    REPORT = 7          # PRISMA Flowchart + GRADE 证据质量


class PRISMAStageStatus(Enum):
    """
    单个 PRISMA 阶段的状态枚举。
    """
    PENDING   = "pending"    # 尚未开始
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETE  = "complete"   # 已完成
    SKIPPED   = "skipped"     # 已跳过（如不适用）


class GRADEQuality(Enum):
    """
    GRADE 证据质量等级（Guyatt et al., BMJ 2011）。

    GRADE working group evidence quality assessment:
      HIGH       — 我们非常确信真实效应值接近效应估计值
      MODERATE   — 对效应估计值有中等信心：
                   真实值可能接近估计值，但也可能存在显著差异
      LOW        — 对效应估计值的信心有限：
                   真实值可能与估计值存在显著差异
      VERY_LOW   — 对效应估计值的信心很低：
                   真实值很可能与估计值存在显著差异
    """
    HIGH      = "high"
    MODERATE  = "moderate"
    LOW       = "low"
    VERY_LOW  = "very_low"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SearchStrategy:
    """
    检索策略数据结构。

    记录一次完整的数据库检索过程，包括检索式、检索数据库、
    时间范围和检出记录数量。

    Attributes:
        strategy_id: 策略唯一标识（如 "strat_001"）
        query_text: 完整检索式（布尔型/MeSH/语义式）
        databases: 检索的数据库列表（如 ["PubMed", "Embase", "Web of Science"]）
        date_from: 检索起始日期（YYYY-MM-DD）
        date_to: 检索截止日期（YYYY-MM-DD）
        record_count: 检出记录总数（默认 0）
        prisma_stage: 当前所属 PRISMA 阶段
    """
    strategy_id: str
    query_text: str
    databases: list[str]
    date_from: str
    date_to: str
    record_count: int = 0
    prisma_stage: PRISMAStage = PRISMAStage.IDENTIFICATION

    def to_dict(self) -> dict[str, Any]:
        """
        将检索策略序列化为字典。

        Returns:
            包含所有字段的字典，可直接写入 JSON。
        """
        return {
            "strategy_id": self.strategy_id,
            "query_text": self.query_text,
            "databases": self.databases,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "record_count": self.record_count,
            "prisma_stage": self.prisma_stage.name,
        }

    def add_result_count(self, count: int) -> None:
        """
        更新检出记录数量。

        Args:
            count: 新检出的记录数。
        """
        self.record_count = count
        _log.debug(
            "SearchStrategy %s updated: record_count=%d",
            self.strategy_id, count
        )


@dataclass
class ScreeningRecord:
    """
    单篇文献的筛选记录。

    支持双人独立盲法筛选（dual-blind screening）及冲突解决机制。

    Attributes:
        paper_id: 文献唯一标识（DOI/arXiv ID/内部 ID）
        title: 文献标题
        authors: 作者列表（逗号分隔字符串或 list）
        year: 出版年份
        database: 来源数据库
        inclusion_status: 纳入状态（None / "include" / "exclude"）
        exclusion_reason: 排除原因（当 inclusion_status="exclude" 时填写）
        screened_by_first: 第一位筛选者
        screened_by_second: 第二位筛选者（None 表示单人筛选）
        has_conflict: 是否存在冲突（两位筛选结果不一致）
        conflict_resolved: 冲突是否已解决
        resolved_by: 冲突解决者（None 表示无冲突或未解决）
        notes: 备注字段
    """
    paper_id: str
    title: str
    authors: str | list[str]
    year: int
    database: str
    inclusion_status: str | None = None  # None / "include" / "exclude"
    exclusion_reason: str | None = None
    screened_by_first: str = ""
    screened_by_second: str | None = None
    has_conflict: bool = False
    conflict_resolved: bool = False
    resolved_by: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        # Normalise authors to list
        if isinstance(self.authors, str):
            self.authors = [a.strip() for a in self.authors.split(",")]

    def to_dict(self) -> dict[str, Any]:
        """
        将筛选记录序列化为字典。

        Returns:
            包含所有字段的字典。
        """
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "database": self.database,
            "inclusion_status": self.inclusion_status,
            "exclusion_reason": self.exclusion_reason,
            "screened_by_first": self.screened_by_first,
            "screened_by_second": self.screened_by_second,
            "has_conflict": self.has_conflict,
            "conflict_resolved": self.conflict_resolved,
            "resolved_by": self.resolved_by,
            "notes": self.notes,
        }

    def is_resolved(self) -> bool:
        """
        判断该文献是否已完成筛选（无待解决冲突）。

        Returns:
            True 如果无冲突或冲突已解决。
        """
        return not self.has_conflict or self.conflict_resolved


@dataclass
class PICOExtract:
    """
    PICO（Population, Intervention, Comparator, Outcome）数据提取结构。

    用于系统综述中的结构化数据提取，也支持 PECOs 扩展
    （Population, Exposure, Comparator, Outcomes, Study design）。

    Attributes:
        paper_id: 文献唯一标识
        study_id: 研究内部标识
        population_desc: 研究人群描述
        intervention: 干预措施描述
        comparator: 对照组描述
        outcome_primary: 主要结局指标
        outcome_secondary: 次要结局指标列表
        study_design: 研究设计类型（如 "RCT", "Cohort", "Case-Control"）
        n_participants: 基线样本量
        n_followup: 随访样本量（0 表示无随访）
        setting: 研究场景（如 "医院", "社区", "线上"）
        country: 国家/地区
        risk_of_bias: 偏倚风险评级（"Low" / "Some concerns" / "High"）
        extracted_by: 提取者姓名
        extracted_at: 提取时间戳（Unix timestamp）
    """
    paper_id: str
    study_id: str
    population_desc: str
    intervention: str
    comparator: str
    outcome_primary: str
    outcome_secondary: list[str] = field(default_factory=list)
    study_design: str = ""
    n_participants: int = 0
    n_followup: int = 0
    setting: str = ""
    country: str = ""
    risk_of_bias: str | None = None
    extracted_by: str = ""
    extracted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """
        将 PICO 提取结果序列化为字典。

        Returns:
            PICO 数据的字典表示。
        """
        return {
            "paper_id": self.paper_id,
            "study_id": self.study_id,
            "population_desc": self.population_desc,
            "intervention": self.intervention,
            "comparator": self.comparator,
            "outcome_primary": self.outcome_primary,
            "outcome_secondary": self.outcome_secondary,
            "study_design": self.study_design,
            "n_participants": self.n_participants,
            "n_followup": self.n_followup,
            "setting": self.setting,
            "country": self.country,
            "risk_of_bias": self.risk_of_bias,
            "extracted_by": self.extracted_by,
            "extracted_at": self.extracted_at,
        }

    def to_picos_string(self) -> str:
        """
        将 PICO 格式化为可读字符串，用于报告展示。

        Returns:
            格式化的 PICO 字符串。
        """
        parts = [
            f"P (Population): {self.population_desc}",
            f"I (Intervention): {self.intervention}",
            f"C (Comparator): {self.comparator}",
            f"O (Outcome): {self.outcome_primary}",
        ]
        if self.outcome_secondary:
            parts.append(f"Secondary O: {', '.join(self.outcome_secondary)}")
        if self.study_design:
            parts.append(f"Study Design: {self.study_design}")
        parts.append(f"N = {self.n_participants} ({self.country})")
        return "\n".join(parts)


@dataclass
class ROBAssessment:
    """
    偏倚风险评估（Risk of Bias）数据结构。

    支持两种主流工具：
      - ROBINS-I（Sterne et al., BMJ 2016）：观察性研究
      - Cochrane ROB2（Higgins et al., 2019）：随机对照试验（RCT）

    Each tool评估多个领域（domains），最终给出总体偏倚评级。

    Attributes:
        paper_id: 文献唯一标识
        tool_type: 评估工具类型（"ROBINS-I" 或 "Cochrane_ROB2"）
        domains: 各领域偏倚评级字典
            - ROBINS-I: "bias_due_to_confounders", "bias_in_selection_of_participants",
                        "bias_in_classification_of_interventions", "bias_due_to_deviations",
                        "bias_due_to_missing_data", "bias_in_measurement_of_outcomes",
                        "bias_in_selection_of_reported_result", "overall"
            - ROB2: "bias_due_to_randomization", "bias_due_to_deviations",
                    "bias_due_to_missing_data", "bias_in_measurement_of_outcomes",
                    "bias_in_selection_of_reported_result", "overall"
        overall_rob: 总体偏倚评级（"Low" / "Some concerns" / "High"）
        rob_json: 完整 ROB 评估原始 JSON（用于可视化或审计）
        assessor: 评估者姓名
        assessed_at: 评估时间戳（Unix timestamp）
    """
    paper_id: str
    tool_type: str  # "ROBINS-I" or "Cochrane_ROB2"
    domains: dict[str, str] = field(default_factory=dict)
    overall_rob: str = ""
    rob_json: dict[str, Any] = field(default_factory=dict)
    assessor: str = ""
    assessed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """
        将偏倚评估结果序列化为字典。

        Returns:
            ROB 评估的字典表示。
        """
        return {
            "paper_id": self.paper_id,
            "tool_type": self.tool_type,
            "domains": self.domains,
            "overall_rob": self.overall_rob,
            "rob_json": self.rob_json,
            "assessor": self.assessor,
            "assessed_at": self.assessed_at,
        }

    def to_summary_str(self) -> str:
        """
        生成偏倚评估的人类可读摘要。

        Returns:
            格式化的偏倚评估摘要。
        """
        lines = [
            f"Paper: {self.paper_id}",
            f"Tool: {self.tool_type}",
            f"Overall Risk of Bias: {self.overall_rob}",
            "",
            "Domain-level judgments:",
        ]
        for domain, judgment in self.domains.items():
            marker = "✓" if judgment == "Low" else ("⚠" if judgment == "Some concerns" else "✗")
            lines.append(f"  {marker} {domain}: {judgment}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# PRISMAFlowchart
# ---------------------------------------------------------------------------

class PRISMAFlowchart:
    """
    PRISMA 2020 流程图自动生成器。

    追踪从文献检索到最终纳入口的所有数据，支持 ASCII 流程图渲染
    和 matplotlib 可视化所需的字典输出。

    The flowchart follows the PRISMA 2020 statement (Page et al., BMJ 2021)
    with the seven boxes:
      1. Identification (records from databases + registers + other sources)
      2. Screening (records after deduplication → title/abstract → full-text)
      3. Included (studies in review)

    Example:
        >>> fc = PRISMAFlowchart()
        >>> fc.add_search_strategy(SearchStrategy(
        ...     strategy_id="s1", query_text="diabetes AND metformin",
        ...     databases=["PubMed"], date_from="2020-01-01", date_to="2024-12-31",
        ...     record_count=1200))
        >>> fc.deduplicate(count=300)
        >>> fc.set_fulltext_screened(count=80)
        >>> print(fc.render_ascii())
    """

    # 偏倚评估水平到符号的映射
    _ROB_SYMBOLS = {
        "Low":         "🟢",
        "Some concerns": "🟡",
        "High":        "🔴",
        "":            "⬜",
    }

    def __init__(self) -> None:
        # Flowchart counters
        self._identification_databases: int = 0  # 总检索记录数
        self._identification_other: int = 0     # 其他来源补充
        self._identification_dedup: int = 0      # 去重后记录数
        self._identification_records: int = 0   # 去重后记录（screen阶段）
        self._screening_title_abstract: int = 0  # 标题摘要筛选数
        self._screening_fulltext: int = 0       # 全文筛选数
        self._screening_excluded: int = 0        # 排除数（理由分类）
        self._screening_fulltext_inaccessible: int = 0  # 全文无法获取
        self._included_studies: int = 0         # 最终纳入研究数
        self._included_reports: int = 0         # 最终纳入报告数
        # Exclusion reasons breakdown
        self._exclusion_reasons: dict[str, int] = {}
        # Stage status tracking
        self._stage_statuses: dict[PRISMAStage, PRISMAStageStatus] = {
            st: PRISMAStageStatus.PENDING for st in PRISMAStage
        }
        # Data lists
        self._search_strategies: list[SearchStrategy] = []
        self._screening_records: list[ScreeningRecord] = []
        self._pico_extractions: list[PICOExtract] = []
        self._rob_assessments: list[ROBAssessment] = []
        # GRADE quality tracking
        self._grade_counts: dict[GRADEQuality, int] = {
            q: 0 for q in GRADEQuality
        }

    # ---- Stage status helpers ----

    def get_stage_status(self, stage: PRISMAStage) -> PRISMAStageStatus:
        """返回指定阶段的状态。"""
        return self._stage_statuses.get(stage, PRISMAStageStatus.PENDING)

    def set_stage_status(self, stage: PRISMAStage, status: PRISMAStageStatus) -> None:
        """设置指定阶段的状态。"""
        self._stage_statuses[stage] = status

    # ---- Data management ----

    def add_search_strategy(self, strategy: SearchStrategy) -> None:
        """
        添加一条检索策略，并更新纳入口总数。

        Args:
            strategy: SearchStrategy 实例。
        """
        self._search_strategies.append(strategy)
        self._identification_databases += strategy.record_count
        self._stage_statuses[PRISMAStage.IDENTIFICATION] = PRISMAStageStatus.IN_PROGRESS
        _log.info(
            "Added search strategy '%s': +%d records (total: %d)",
            strategy.strategy_id, strategy.record_count, self._identification_databases
        )

    def add_other_source_records(self, count: int, source: str = "other") -> None:
        """
        添加其他来源（补充检索）的记录数。

        Args:
            count: 其他来源检出记录数。
            source: 来源名称。
        """
        self._identification_other += count
        _log.info("Added %d records from %s (total other: %d)", count, source, self._identification_other)

    def add_screening_record(self, record: ScreeningRecord) -> None:
        """
        添加一条筛选记录并更新阶段计数。

        Args:
            record: ScreeningRecord 实例。
        """
        self._screening_records.append(record)
        # Update counters based on current status
        if record.inclusion_status == "exclude":
            self._screening_excluded += 1
            if record.exclusion_reason:
                self._exclusion_reasons[record.exclusion_reason] = (
                    self._exclusion_reasons.get(record.exclusion_reason, 0) + 1
                )
        elif record.inclusion_status == "include":
            self._included_studies += 1
        self._stage_statuses[PRISMAStage.SCREENING] = PRISMAStageStatus.IN_PROGRESS
        _log.debug(
            "Added screening record: paper_id=%s status=%s",
            record.paper_id, record.inclusion_status
        )

    def add_pico_extraction(self, pico: PICOExtract) -> None:
        """添加一条 PICO 提取记录。"""
        self._pico_extractions.append(pico)
        self._stage_statuses[PRISMAStage.CHARACTERISATION] = PRISMAStageStatus.IN_PROGRESS
        _log.debug("Added PICO extraction: paper_id=%s", pico.paper_id)

    def add_rob_assessment(self, rob: ROBAssessment) -> None:
        """添加一条偏倚评估记录。"""
        self._rob_assessments.append(rob)
        self._stage_statuses[PRISMAStage.RISK_OF_BIAS] = PRISMAStageStatus.IN_PROGRESS
        _log.debug(
            "Added ROB assessment: paper_id=%s tool=%s overall=%s",
            rob.paper_id, rob.tool_type, rob.overall_rob
        )

    def add_grade_count(self, quality: GRADEQuality, count: int = 1) -> None:
        """更新 GRADE 证据质量计数。"""
        self._grade_counts[quality] = self._grade_counts.get(quality, 0) + count

    def deduplicate(self, count: int) -> None:
        """
        设置去重记录数（从纳入口总数中减去）。

        Args:
            count: 被识别的重复记录数量。
        """
        self._identification_dedup = count
        # Records after dedup = total - duplicates
        self._identification_records = (
            self._identification_databases + self._identification_other - count
        )
        _log.info(
            "Deduplication complete: removed %d duplicates, %d unique records remain",
            count, self._identification_records
        )

    def set_title_abstract_screened(self, count: int) -> None:
        """
        设置标题摘要筛选数量。

        Args:
            count: 进行了标题摘要筛选的记录数。
        """
        self._screening_title_abstract = count

    def set_fulltext_screened(self, count: int) -> None:
        """
        设置全文筛选数量。

        Args:
            count: 进行了全文评估的记录数。
        """
        self._screening_fulltext = count

    def set_fulltext_inaccessible(self, count: int) -> None:
        """
        设置无法获取全文的记录数。

        Args:
            count: 无法获取全文的记录数。
        """
        self._screening_fulltext_inaccessible = count

    def set_included_reports(self, count: int) -> None:
        """
        设置最终纳入报告数量（可能大于纳入研究数，因为一项研究多个报告）。

        Args:
            count: 最终纳入的报告数。
        """
        self._included_reports = count

    def mark_stage_complete(self, stage: PRISMAStage) -> None:
        """标记指定阶段为完成状态。"""
        self._stage_statuses[stage] = PRISMAStageStatus.COMPLETE
        _log.info("Stage %s marked as COMPLETE", stage.name)

    # ---- Flowchart data output ----

    def get_flowchart_data(self) -> dict[str, Any]:
        """
        返回 PRISMA 流程图所需的全部数字。

        Returns:
            包含所有流程图计数的字典。
        """
        excluded_not_relevant = self._exclusion_reasons.get("not_relevant", 0)
        excluded_wrong_pop = self._exclusion_reasons.get("wrong_population", 0)
        excluded_wrong_int = self._exclusion_reasons.get("wrong_intervention", 0)
        excluded_wrong_design = self._exclusion_reasons.get("wrong_study_design", 0)
        excluded_other = max(0, self._screening_excluded - excluded_not_relevant
                            - excluded_wrong_pop - excluded_wrong_int - excluded_wrong_design)

        return {
            # Identification
            "identification_databases": self._identification_databases,
            "identification_other": self._identification_other,
            "identification_total": (
                self._identification_databases + self._identification_other
            ),
            "identification_dedup": self._identification_dedup,
            "identification_records": self._identification_records,
            # Screening
            "screening_title_abstract": self._screening_title_abstract,
            "screening_fulltext": self._screening_fulltext,
            "screening_fulltext_inaccessible": self._screening_fulltext_inaccessible,
            "screening_excluded": self._screening_excluded,
            "exclusion_reasons": self._exclusion_reasons,
            "excluded_not_relevant": excluded_not_relevant,
            "excluded_wrong_population": excluded_wrong_pop,
            "excluded_wrong_intervention": excluded_wrong_int,
            "excluded_wrong_study_design": excluded_wrong_design,
            "excluded_other": excluded_other,
            # Included
            "included_studies": self._included_studies,
            "included_reports": self._included_reports,
        }

    def render_ascii(self) -> str:
        """
        将 PRISMA 2020 流程图渲染为 ASCII 艺术文本。

        Returns:
            PRISMA 2020 流程图的 ASCII 表示。
        """
        data = self.get_flowchart_data()
        d = data  # shorthand

        total = d["identification_total"]
        dedup = d["identification_dedup"]
        records = d["identification_records"]
        ta_screened = d["screening_title_abstract"]
        ft_screened = d["screening_fulltext"]
        ft_inacc = d["screening_fulltext_inaccessible"]
        d["screening_title_abstract"] - d["screening_fulltext"]
        excluded_ft = d["screening_fulltext"] - d["included_studies"]
        included_studies = d["included_studies"]
        included_reps = d["included_reports"]

        # Fallback to counts from stored records if not explicitly set
        if ta_screened == 0:
            ta_screened = records
        if ft_screened == 0 and records > 0:
            ft_screened = records

        box_w = 50

        def box(label: str, count: str | int) -> str:
            count_str = str(count)
            inner = f" {label} (n={count_str}) "
            inner_w = box_w
            top = "┌" + "─" * inner_w + "┐"
            bot = "└" + "─" * inner_w + "┘"
            mid = f"│{inner.center(inner_w)}│"
            return f"{top}\n{mid}\n{bot}"

        def arrow(label: str = "") -> str:
            lines = ["│", "▼", "│"]
            if label:
                f"{label}".center(box_w)
                lines = ["│", f"│{label.center(box_w)}│", "│", "▼", "│"]
            return "\n".join(lines)

        lines: list[str] = []

        # ===== IDENTIFICATION =====
        lines.append("╔════════════════════════════════════════════════════════════════════════╗")
        lines.append("║                      1. IDENTIFICATION (识别)                          ║")
        lines.append("╚════════════════════════════════════════════════════════════════════════╝")
        lines.append("")

        # Databases box
        db_total = d["identification_databases"]
        lines.append(box("Records from databases (n={})".format(
            f"databases={db_total}, registers=0, other=0" if db_total == 0
            else f"databases={db_total}"
        ), ""))
        lines.append("")
        lines.append(f"{'Records from registers: n=0':^{box_w}}")
        lines.append("")
        lines.append(box("Records from other sources: n={}".format(
            d["identification_other"]), ""))
        lines.append("")
        lines.append(f"{'▼':^{box_w}}")
        lines.append(f"{f'Records identified through database searching: n={total}'.center(box_w)}")
        lines.append("")
        lines.append(f"{'─' * box_w}")
        lines.append("")
        lines.append(box(f"Records from databases + registers + other sources: n={total}", total))
        lines.append("")
        lines.append(f"{'▼':^{box_w}}")
        lines.append("")
        lines.append(box("Records removed before screening:", ""))
        lines.append("")
        # Deduplication sub-box
        dedup_lines = [
            "┌" + "─" * 30 + "┐",
            f"│ Duplicate records removed: n={dedup} │",
            f"│ Records screened: n={records}         │",
            "└" + "─" * 30 + "┘",
        ]
        lines.extend(["  " + l for l in dedup_lines])
        lines.append("")

        # ===== SCREENING =====
        lines.append("╔════════════════════════════════════════════════════════════════════════╗")
        lines.append("║                      2. SCREENING (筛选)                             ║")
        lines.append("╚════════════════════════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(box(f"Records screened: n={ta_screened}", ta_screened))
        lines.append("")
        lines.append(f"{'▼':^{box_w}}")
        lines.append("")
        lines.append(box(f"Records excluded at title/abstract: n={max(0, ta_screened - ft_screened)}", ""))
        lines.append("")
        lines.append(f"{'▼':^{box_w}}")
        lines.append("")
        lines.append(box(f"Reports assessed for eligibility: n={ft_screened}", ft_screened))
        lines.append("")

        # Full-text inaccessibility sub-box
        if ft_inacc > 0 or d["screening_fulltext_inaccessible"] > 0:
            inacc_lines = [
                "┌" + "─" * 40 + "┐",
                f"│ Reports not retrieved: n={ft_inacc or d['screening_fulltext_inaccessible']}  │",
                "└" + "─" * 40 + "┘",
            ]
            lines.extend(["  " + l for l in inacc_lines])
            lines.append("")

        lines.append(f"{'▼':^{box_w}}")
        lines.append("")
        lines.append(box(f"Reports excluded: n={excluded_ft}", ""))
        lines.append("")
        # Exclusion reasons
        if d["exclusion_reasons"]:
            er_lines = [
                "  ┌" + "─" * 60 + "┐",
                "  │ Exclusion reasons:",
            ]
            for reason, cnt in d["exclusion_reasons"].items():
                er_lines.append(f"  │   - {reason}: n={cnt}")
            er_lines.append("  └" + "─" * 60 + "┘")
            lines.extend(er_lines)
            lines.append("")

        # ===== INCLUDED =====
        lines.append("╔════════════════════════════════════════════════════════════════════════╗")
        lines.append("║                      3. INCLUDED (纳入)                               ║")
        lines.append("╚════════════════════════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(box(f"Studies included in review: n={included_studies}", included_studies))
        lines.append("")
        if included_reps > 0 and included_reps != included_studies:
            lines.append(f"{f'Reports of included studies: n={included_reps}'.center(box_w)}")
            lines.append("")
        lines.append(f"{'─' * box_w}")
        lines.append("")

        # ===== CHARACTERISATION / RISK OF BIAS =====
        if self._pico_extractions or self._rob_assessments:
            lines.append("╔════════════════════════════════════════════════════════════════════════╗")
            lines.append("║           4-5. CHARACTERISATION & RISK OF BIAS (特征化 & 偏倚)    ║")
            lines.append("╚════════════════════════════════════════════════════════════════════════╝")
            lines.append("")
            if self._pico_extractions:
                lines.append(f"{f'PICO extractions completed: n={len(self._pico_extractions)}'.center(box_w)}")
                lines.append("")
            if self._rob_assessments:
                rob_summary: dict[str, int] = {}
                for rob in self._rob_assessments:
                    level = rob.overall_rob or "Unknown"
                    rob_summary[level] = rob_summary.get(level, 0) + 1
                for level, cnt in rob_summary.items():
                    symbol = self._ROB_SYMBOLS.get(level, "⬜")
                    lines.append(f"  {symbol} {level} risk of bias: n={cnt}")
                lines.append("")

        # ===== GRADE =====
        grade_total = sum(self._grade_counts.values())
        if grade_total > 0:
            lines.append("╔════════════════════════════════════════════════════════════════════════╗")
            lines.append("║                      6-7. SYNTHESIS & REPORT (合成 & 报告)          ║")
            lines.append("╚════════════════════════════════════════════════════════════════════════╝")
            lines.append("")
            lines.append(f"{'GRADE Evidence Quality Assessment':^{box_w}}")
            lines.append("")
            grade_lines = [
                f"  🟢 High:      n={self._grade_counts.get(GRADEQuality.HIGH, 0)}",
                f"  🟡 Moderate: n={self._grade_counts.get(GRADEQuality.MODERATE, 0)}",
                f"  🟠 Low:       n={self._grade_counts.get(GRADEQuality.LOW, 0)}",
                f"  🔴 Very Low:  n={self._grade_counts.get(GRADEQuality.VERY_LOW, 0)}",
            ]
            lines.extend(grade_lines)
            lines.append("")

        lines.append("─" * 72)
        lines.append("PRISMA 2020 Flowchart (auto-generated)".center(72))
        lines.append("Generated by prisma_compliance.py".center(72))

        return "\n".join(lines)

    def render_dict(self) -> dict[str, Any]:
        """
        返回所有流程图数字的字典，用于 matplotlib / plotly 可视化。

        Returns:
            包含所有计数的扁平化字典。
        """
        data = self.get_flowchart_data()
        rob_summary: dict[str, int] = {}
        for rob in self._rob_assessments:
            level = rob.overall_rob or "Unknown"
            rob_summary[level] = rob_summary.get(level, 0) + 1

        return {
            # Identification
            "id_databases": data["identification_databases"],
            "id_other": data["identification_other"],
            "id_total": data["identification_total"],
            "id_dedup": data["identification_dedup"],
            "id_records": data["identification_records"],
            # Screening
            "scr_title_abstract": data["screening_title_abstract"],
            "scr_fulltext": data["screening_fulltext"],
            "scr_fulltext_inacc": data["screening_fulltext_inaccessible"],
            "scr_excluded": data["screening_excluded"],
            # Exclusions
            "exc_not_relevant": data["excluded_not_relevant"],
            "exc_wrong_pop": data["excluded_wrong_population"],
            "exc_wrong_int": data["excluded_wrong_intervention"],
            "exc_wrong_design": data["excluded_wrong_study_design"],
            "exc_other": data["excluded_other"],
            # Included
            "inc_studies": data["included_studies"],
            "inc_reports": data["included_reports"],
            # ROB
            "rob_low": rob_summary.get("Low", 0),
            "rob_some_concerns": rob_summary.get("Some concerns", 0),
            "rob_high": rob_summary.get("High", 0),
            # GRADE
            "grade_high": self._grade_counts.get(GRADEQuality.HIGH, 0),
            "grade_moderate": self._grade_counts.get(GRADEQuality.MODERATE, 0),
            "grade_low": self._grade_counts.get(GRADEQuality.LOW, 0),
            "grade_very_low": self._grade_counts.get(GRADEQuality.VERY_LOW, 0),
            # Meta
            "n_search_strategies": len(self._search_strategies),
            "n_screening_records": len(self._screening_records),
            "n_pico_extractions": len(self._pico_extractions),
            "n_rob_assessments": len(self._rob_assessments),
            "stage_statuses": {st.name: s.value for st, s in self._stage_statuses.items()},
        }

    # ---- Convenience properties ----

    @property
    def search_strategies(self) -> list[SearchStrategy]:
        return self._search_strategies

    @property
    def screening_records(self) -> list[ScreeningRecord]:
        return self._screening_records

    @property
    def pico_extractions(self) -> list[PICOExtract]:
        return self._pico_extractions

    @property
    def rob_assessments(self) -> list[ROBAssessment]:
        return self._rob_assessments


# ---------------------------------------------------------------------------
# PRISMAReport
# ---------------------------------------------------------------------------

class PRISMAReport:
    """
    PRISMA 2020 综述报告生成器。

    整合流程图、PICO 提取、偏倚评估和 GRADE 证据质量，
    输出结构化摘要、PRISMA 声明文本和 JSON 报告。

    Example:
        >>> fc = PRISMAFlowchart()
        >>> fc.deduplicate(250)
        >>> report = PRISMAReport(fc)
        >>> report.add_pico(pico)
        >>> report.add_rob(rob)
        >>> print(report.generate_prisma_statement())
    """

    def __init__(self, flowchart: PRISMAFlowchart) -> None:
        self._flowchart = flowchart
        self._picos: list[PICOExtract] = []
        self._robs: list[ROBAssessment] = []
        self._grade_counts: dict[GRADEQuality, int] = {
            q: 0 for q in GRADEQuality
        }
        self._narrative_findings: str = ""
        self._quantitative_findings: str = ""
        self._meta_analysis_notes: str = ""

    def add_pico(self, pico: PICOExtract) -> None:
        """添加一条 PICO 提取记录。"""
        self._picos.append(pico)
        self._flowchart.add_pico_extraction(pico)

    def add_rob(self, rob: ROBAssessment) -> None:
        """添加一条偏倚评估记录。"""
        self._robs.append(rob)
        self._flowchart.add_rob_assessment(rob)

    def set_grade_count(self, quality: GRADEQuality, count: int) -> None:
        """设置 GRADE 证据质量各等级的数量。"""
        self._grade_counts[quality] = count
        for _ in range(count):
            self._flowchart.add_grade_count(quality)

    def set_narrative_findings(self, text: str) -> None:
        """设置叙事合成结论。"""
        self._narrative_findings = text

    def set_quantitative_findings(self, text: str) -> None:
        """设置定量合成结论（Meta 分析结果）。"""
        self._quantitative_findings = text

    def set_meta_analysis_notes(self, notes: str) -> None:
        """设置 Meta 分析备注。"""
        self._meta_analysis_notes = notes

    def generate_summary(self) -> dict[str, Any]:
        """
        生成结构化摘要。

        Returns:
            包含 PRISMA 各阶段计数、PICO 统计、偏倚评估汇总、
            GRADE 证据质量分布的完整字典。
        """
        # Study design distribution
        designs: dict[str, int] = {}
        total_participants = 0
        total_followup = 0
        for pico in self._picos:
            designs[pico.study_design] = designs.get(pico.study_design, 0) + 1
            total_participants += pico.n_participants
            total_followup += pico.n_followup

        # ROB distribution
        rob_dist: dict[str, int] = {}
        for rob in self._robs:
            level = rob.overall_rob or "Unknown"
            rob_dist[level] = rob_dist.get(level, 0) + 1

        fc_data = self._flowchart.get_flowchart_data()

        return {
            "prisma_stages": {
                "identification": {
                    "databases": fc_data["identification_databases"],
                    "other_sources": fc_data["identification_other"],
                    "total_records": fc_data["identification_total"],
                    "after_dedup": fc_data["identification_records"],
                },
                "screening": {
                    "title_abstract_screened": fc_data["screening_title_abstract"],
                    "fulltext_assessed": fc_data["screening_fulltext"],
                    "fulltext_inaccessible": fc_data["screening_fulltext_inaccessible"],
                    "excluded": fc_data["screening_excluded"],
                    "exclusion_reasons": fc_data["exclusion_reasons"],
                },
                "included": {
                    "studies": fc_data["included_studies"],
                    "reports": fc_data["included_reports"],
                },
            },
            "pico_summary": {
                "n_extractions": len(self._picos),
                "study_designs": designs,
                "total_participants": total_participants,
                "total_followup": total_followup,
            },
            "risk_of_bias_summary": {
                "n_assessments": len(self._robs),
                "distribution": rob_dist,
                "tool_types": list({r.tool_type for r in self._robs}),
            },
            "grade_evidence": {
                grade.value: self._grade_counts[grade]
                for grade in GRADEQuality
            },
            "synthesis": {
                "narrative": self._narrative_findings,
                "quantitative": self._quantitative_findings,
                "meta_analysis_notes": self._meta_analysis_notes,
            },
            "flowchart_data": self._flowchart.render_dict(),
        }

    def generate_prisma_statement(self) -> str:
        """
        生成 PRISMA 2020 标准流程声明文本。

        Returns:
            符合 PRISMA 2020 规范的英文流程描述段落。
        """
        fc_data = self._flowchart.get_flowchart_data()

        id_total = fc_data["identification_total"]
        id_dedup = fc_data["identification_dedup"]
        id_records = fc_data["identification_records"]
        ta_screened = fc_data["screening_title_abstract"] or id_records
        ft_screened = fc_data["screening_fulltext"] or ta_screened
        ft_inacc = fc_data["screening_fulltext_inaccessible"]
        excluded_ta = max(0, ta_screened - ft_screened)
        excluded_ft = max(0, ft_screened - fc_data["included_studies"])
        included_studies = fc_data["included_studies"]
        included_reps = fc_data["included_reports"]

        # Build databases string from search strategies
        db_list: list[str] = []
        for strat in self._flowchart.search_strategies:
            for db in strat.databases:
                if db not in db_list:
                    db_list.append(db)
        db_str = ", ".join(db_list) if db_list else "multiple databases"

        # Database and date info
        date_info = ""
        if self._flowchart.search_strategies:
            dates = [(s.date_from, s.date_to) for s in self._flowchart.search_strategies]
            if dates:
                min_from = min(d[0] for d in dates)
                max_to = max(d[1] for d in dates)
                date_info = f" from {min_from} to {max_to}"

        # Exclusion reason text
        ex_reasons = fc_data["exclusion_reasons"]
        excl_lines: list[str] = []
        if ex_reasons:
            for reason, cnt in ex_reasons.items():
                excl_lines.append(
                    f"{cnt} {reason}" + ("s" if cnt > 1 else "")
                )

        # Build statement
        stmt_parts: list[str] = []

        # Identification
        stmt_parts.append(
            f"We identified {id_total:,} records through database searching{date_info} "
            f"across {db_str}."
        )
        if fc_data["identification_other"] > 0:
            stmt_parts.append(
                f" Additionally, {fc_data['identification_other']:,} records were "
                f"identified through other sources."
            )
        stmt_parts.append("")
        stmt_parts.append(
            f"After removing {id_dedup:,} duplicate records, "
            f"{id_records:,} records remained for screening."
        )
        stmt_parts.append("")

        # Screening
        stmt_parts.append(
            f"Two reviewers independently screened {ta_screened:,} titles and abstracts. "
            f"Of these, {excluded_ta:,} were excluded at this stage, "
            f"and {ft_screened:,} reports were sought for full-text assessment."
        )
        if ft_inacc > 0:
            stmt_parts.append(
                f" {ft_inacc:,} reports could not be retrieved."
            )
        stmt_parts.append("")
        stmt_parts.append(
            f"Following full-text review, {excluded_ft:,} reports were excluded "
            f"with reasons: {', '.join(excl_lines) if excl_lines else 'see Supplementary Material'}."
        )
        stmt_parts.append("")

        # Included
        if included_studies == 0:
            stmt_parts.append("No studies met the inclusion criteria.")
        else:
            stmt_parts.append(
                f"A total of {included_studies:,} studies ({included_reps:,} reports) "
                f"were included in the systematic review."
            )
            stmt_parts.append("")

            # PICO summary
            if self._picos:
                designs = {}
                for pico in self._picos:
                    designs[pico.study_design] = designs.get(pico.study_design, 0) + 1
                design_str = "; ".join(
                    f"{cnt} {ds}" for ds, cnt in designs.items()
                )
                total_n = sum(p.n_participants for p in self._picos)
                stmt_parts.append(
                    f"Included studies comprised {design_str}, "
                    f"with a total of {total_n:,} participants."
                )

            # ROB summary
            if self._robs:
                rob_dist: dict[str, int] = {}
                for rob in self._robs:
                    lv = rob.overall_rob or "Unknown"
                    rob_dist[lv] = rob_dist.get(lv, 0) + 1
                rob_str = "; ".join(
                    f"{cnt} at {level}" for level, cnt in rob_dist.items()
                )
                stmt_parts.append(f"Risk of bias assessment: {rob_str}.")

            # GRADE
            grade_total = sum(self._grade_counts.values())
            if grade_total > 0:
                grade_parts: list[str] = []
                for grade in GRADEQuality:
                    cnt = self._grade_counts[grade]
                    if cnt > 0:
                        grade_parts.append(f"{cnt} {grade.value}")
                stmt_parts.append(
                    f"GRADE evidence quality: {', '.join(grade_parts)}."
                )

        # Narrative + quantitative synthesis
        if self._narrative_findings:
            stmt_parts.append("")
            stmt_parts.append(f"Narrative synthesis: {self._narrative_findings}")
        if self._quantitative_findings:
            stmt_parts.append("")
            stmt_parts.append(f"Quantitative synthesis: {self._quantitative_findings}")
        if self._meta_analysis_notes:
            stmt_parts.append(f" Meta-analysis: {self._meta_analysis_notes}")

        return "\n".join(stmt_parts)

    def to_json(self, path: Path | str) -> None:
        """
        将完整报告序列化为 JSON 文件。

        Args:
            path: 输出文件路径。
        """
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.to_dict()
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(content, fh, ensure_ascii=False, indent=2)
        _log.info("PRISMA report saved to %s", output_path)

    def to_dict(self) -> dict[str, Any]:
        """
        将报告的完整内容序列化为字典。

        Returns:
            包含所有组件的字典。
        """
        summary = self.generate_summary()

        # Convert dataclasses to dicts
        picos_dicts = [p.to_dict() for p in self._picos]
        robs_dicts = [r.to_dict() for r in self._robs]
        strategies_dicts = [s.to_dict() for s in self._flowchart.search_strategies]

        return {
            "prisma_version": "2020",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "prisma_statement_text": self.generate_prisma_statement(),
            "summary": summary,
            "search_strategies": strategies_dicts,
            "pico_extractions": picos_dicts,
            "rob_assessments": robs_dicts,
            "flowchart_ascii": self._flowchart.render_ascii(),
            "flowchart_data": self._flowchart.render_dict(),
            "grade_evidence": {
                grade.value: self._grade_counts[grade]
                for grade in GRADEQuality
            },
            "narrative_findings": self._narrative_findings,
            "quantitative_findings": self._quantitative_findings,
            "meta_analysis_notes": self._meta_analysis_notes,
        }

    # ---- Convenience accessors ----

    @property
    def flowchart(self) -> PRISMAFlowchart:
        return self._flowchart

    @property
    def picos(self) -> list[PICOExtract]:
        return self._picos

    @property
    def robs(self) -> list[ROBAssessment]:
        return self._robs
