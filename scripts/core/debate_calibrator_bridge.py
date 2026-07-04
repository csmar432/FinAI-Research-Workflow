"""
debate_calibrator_bridge.py — Integrates DebateArena with ReviewerCalibrator

This module creates a unified review pipeline that combines:
  - DebateArena: Structured multi-agent debate (proposer/critic/synthesizer)
  - ReviewerCalibrator: Bias detection and calibration adjustments

The bridge ensures:
  1. Debate outcomes feed into calibrator bias tracking
  2. Calibrator's journal-specific standards inform debate scoring
  3. A unified verdict score integrates both debate and calibration signals

Usage:
    from scripts.core.debate_calibrator_bridge import DebateCalibratorBridge
    bridge = DebateCalibratorBridge(llm_gateway=gateway, journal="经济研究")
    verdict = await bridge.review_claim(claim="...", context={...})

Integration with ReviewerCalibrator:
    from scripts.core.debate_calibrator_bridge import DebateCalibratorBridge
    bridge = DebateCalibratorBridge(llm_gateway=gateway, journal="经济研究")
    verdict = bridge.review_claim(claim="...", context={...})
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

# Imports from debate_arena
try:
    from scripts.core.debate_arena import (
        DebateArena,
        DebateClaim,
        DebateRole,
        DebateVerdict,
    )
    _DEBATE_AVAILABLE = True
except ImportError:
    _DEBATE_AVAILABLE = False
    DebateArena = None
    DebateClaim = None
    DebateVerdict = None
    DebateRole = None

# Imports from reviewer_calibrator
# Note: DualReviewer lives in dual_reviewer.py, not reviewer_calibrator.py
try:
    from scripts.core.reviewer_calibrator import (
        BiasHistoryDB,
        BiasInstance,
        BiasReport,
        BiasType,
        ReviewerCalibrator,
    )
    _CALIBRATOR_AVAILABLE = True
except ImportError:
    _CALIBRATOR_AVAILABLE = False
    ReviewerCalibrator = None
    BiasType = None
    BiasHistoryDB = None
    BiasInstance = None
    BiasReport = None

DualReviewer = None  # lives in dual_reviewer.py, not reviewer_calibrator.py

_log = logging.getLogger("debate_calibrator_bridge")

__all__ = [
    "CalibrationDebateVerdict",
    "DebateCalibratorBridge",
    "_DEBATE_AVAILABLE",
    "_CALIBRATOR_AVAILABLE",
]


# ─── Weighted Score Mapping ────────────────────────────────────────────────────

# Maps confidence_level to a weight multiplier applied to debate score.
# High confidence → more weight on debate; low confidence → more on calibrator.
_CONFIDENCE_WEIGHT_MAP: dict[str, float] = {
    "high": 0.75,
    "medium": 0.60,
    "low": 0.40,
}

# Base weights when confidence is medium (default)
_BASE_DEBATE_WEIGHT = 0.60
_BASE_CALIBRATION_WEIGHT = 0.40


# ─── CalibrationDebateVerdict ─────────────────────────────────────────────────


@dataclass
class CalibrationDebateVerdict:
    """
    Extends DebateVerdict with calibration metadata from ReviewerCalibrator.

    Attributes
    ----------
    debate_verdict : DebateVerdict
        The original debate verdict.
    calibrator_score : float | None
        Calibrated score from ReviewerCalibrator (0-10).
    bias_adjustment : float
        Total bias adjustment applied (can be positive or negative).
    calibrated_score : float
        Final score after calibration (0-10).
    journal : str
        Target journal for standardization.
    concerns_from_debate : list[str]
        Key concerns extracted from debate verdict.
    suggestions_from_debate : list[str]
        Suggested revisions from debate verdict.
    unresolved_from_debate : list[str]
        Unresolved issues from debate.
    confidence_level : str
        Confidence level: "high", "medium", or "low".
    accepted : bool
        Whether the claim is accepted as valid.
    debate_score : float
        Raw debate score (before calibration).
    calibrator_weight_used : float
        Weight given to calibrator score in final computation.
    debate_weight_used : float
        Weight given to debate score in final computation.
    timestamp : float
        Unix timestamp when verdict was generated.
    """

    debate_verdict: DebateVerdict | None = None
    calibrator_score: float | None = None
    bias_adjustment: float = 0.0
    calibrated_score: float = 0.0
    journal: str = "经济研究"
    concerns_from_debate: list[str] = field(default_factory=list)
    suggestions_from_debate: list[str] = field(default_factory=list)
    unresolved_from_debate: list[str] = field(default_factory=list)
    confidence_level: str = "medium"
    accepted: bool = False
    debate_score: float = 0.0
    calibrator_weight_used: float = 0.40
    debate_weight_used: float = 0.60
    timestamp: float = field(default_factory=time.time)

    # Propagate from DebateVerdict for convenience
    claim: str = ""
    overall_score: float = 0.0
    confidence_delta: float = 0.0

    def __post_init__(self):
        """Populate convenience fields from debate_verdict if provided."""
        if self.debate_verdict is not None:
            dv = self.debate_verdict
            self.claim = getattr(dv, "claim", self.claim)
            self.overall_score = getattr(dv, "overall_score", self.overall_score)
            self.confidence_delta = getattr(dv, "confidence_delta", self.confidence_delta)
            self.concerns_from_debate = list(self.concerns_from_debate) or list(
                getattr(dv, "key_concerns", [])
            )
            self.suggestions_from_debate = list(self.suggestions_from_debate) or list(
                getattr(dv, "suggested_revisions", [])
            )
            self.unresolved_from_debate = list(self.unresolved_from_debate) or list(
                getattr(dv, "unresolved_issues", [])
            )
            # Only propagate confidence_level/accepted/debate_score if they haven't
            # been explicitly set to non-default values
            dv_confidence = getattr(dv, "confidence_level", "medium")
            if self.confidence_level == "medium":
                self.confidence_level = dv_confidence
            dv_accepted = getattr(dv, "accepted", False)
            if not self.accepted:
                self.accepted = dv_accepted
            dv_score = getattr(dv, "overall_score", 0.0)
            if self.debate_score == 0.0:
                self.debate_score = dv_score

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "claim": self.claim,
            "overall_score": self.overall_score,
            "calibrated_score": self.calibrated_score,
            "debate_score": self.debate_score,
            "calibrator_score": self.calibrator_score,
            "bias_adjustment": self.bias_adjustment,
            "journal": self.journal,
            "confidence_level": self.confidence_level,
            "confidence_delta": self.confidence_delta,
            "accepted": self.accepted,
            "calibrator_weight_used": self.calibrator_weight_used,
            "debate_weight_used": self.debate_weight_used,
            "concerns_from_debate": self.concerns_from_debate,
            "suggestions_from_debate": self.suggestions_from_debate,
            "unresolved_from_debate": self.unresolved_from_debate,
            "timestamp": self.timestamp,
        }

    def to_publication_report(self) -> str:
        """
        Generate a publication-ready assessment paragraph.

        Returns
        -------
        str
            A structured paragraph suitable for inclusion in a review report
            or methodology section of a paper.
        """
        parts = []

        # Header
        claim_preview = (
            self.claim[:80] + "..."
            if len(self.claim) > 80
            else self.claim
        )
        parts.append(f"Claim: \"{claim_preview}\"")

        # Score summary
        verdict_word = "accepted" if self.accepted else "not recommended for acceptance"
        conf_str = self.confidence_level.upper()
        parts.append(
            f"Unified assessment: {verdict_word} "
            f"(calibrated score {self.calibrated_score:.2f}/10, "
            f"debate score {self.debate_score:.2f}/10, "
            f"calibration score {self._fmt(self.calibrator_score)}/10; "
            f"{conf_str} confidence)."
        )

        # Calibration details
        if self.bias_adjustment != 0.0:
            direction = "upward" if self.bias_adjustment > 0 else "downward"
            parts.append(
                f"Calibration adjustment of {abs(self.bias_adjustment):.2f} applied "
                f"({direction}) based on journal-specific standards ({self.journal})."
            )

        # Journal context
        parts.append(
            f"Standards aligned with {self.journal} review conventions "
            f"(debate weight: {self.debate_weight_used:.0%}, "
            f"calibration weight: {self.calibrator_weight_used:.0%})."
        )

        # Key concerns
        if self.concerns_from_debate:
            concerns_text = "; ".join(self.concerns_from_debate[:3])
            parts.append(f"Key methodological concerns: {concerns_text}.")

        # Unresolved issues
        if self.unresolved_from_debate:
            n_unresolved = len(self.unresolved_from_debate)
            parts.append(
                f"{n_unresolved} unresolved issue(s) remain: "
                f"{'; '.join(self.unresolved_from_debate[:2])}."
            )

        # Suggested revisions
        if self.suggestions_from_debate:
            parts.append(
                f"Recommended revisions: {self.suggestions_from_debate[0]}"
                f"{' and ' + self.suggestions_from_debate[1] if len(self.suggestions_from_debate) > 1 else ''}."
            )

        return " ".join(parts)

    def _fmt(self, value: float | None) -> str:
        """Format a float for display."""
        if value is None:
            return "N/A"
        return f"{value:.2f}"


# ─── DebateCalibratorBridge ───────────────────────────────────────────────────


class DebateCalibratorBridge:
    """
    Unified bridge between DebateArena and ReviewerCalibrator.

    Parameters
    ----------
    llm_gateway : callable or None
        LLM gateway callable. Passed to DebateArena.
        Expected signature: llm_gateway(prompt, system=None, temperature=0.3) -> str
    journal : str
        Target journal name (e.g., "经济研究", "JF", "JFE").
        Used for calibrator standardization.
    use_debate : bool
        Whether to run the debate phase. Default True.
    use_calibration : bool
        Whether to run calibration. Default True.
    calibrator : ReviewerCalibrator | None
        Pre-configured calibrator instance. If None, creates one.
    db_path : str | None
        Path to SQLite bias history DB. None skips persistence.

    Usage
    -----
        bridge = DebateCalibratorBridge(llm_gateway=gateway, journal="经济研究")
        verdict = await bridge.review_claim(
            claim="Carbon trading increases green patents by 15%",
            context={"methodology": "DID", "sample": "A-share 2010-2023"},
        )
        print(verdict.to_publication_report())
    """

    def __init__(
        self,
        llm_gateway: Any = None,
        journal: str = "经济研究",
        use_debate: bool = True,
        use_calibration: bool = True,
        calibrator: Any = None,
        db_path: str | None = ".bias_history.db",
    ):
        self.llm_gateway = llm_gateway
        self.journal = journal
        self.use_debate = use_debate
        self.use_calibration = use_calibration

        # Initialize DebateArena
        if _DEBATE_AVAILABLE and use_debate:
            self.arena = DebateArena(llm_gateway=llm_gateway)
        else:
            self.arena = None

        # Initialize calibrator
        if _CALIBRATOR_AVAILABLE and use_calibration:
            self.calibrator: Any = (
                calibrator
                if calibrator is not None
                else ReviewerCalibrator(journal_baselines=None)
            )
            # Optional persistent bias tracking
            self._bias_db: Any = None
            if db_path is not None:
                try:
                    self._bias_db = BiasHistoryDB(db_path)
                except Exception:
                    self._bias_db = None
        else:
            self.calibrator = None
            self._bias_db = None

        _log.info(
            "DebateCalibratorBridge initialized: debate=%s, calibration=%s, journal=%s",
            use_debate,
            use_calibration,
            journal,
        )

    async def review_claim(
        self,
        claim: str,
        context: dict[str, Any],
    ) -> CalibrationDebateVerdict:
        """
        Run the unified review pipeline on an empirical claim.

        Parameters
        ----------
        claim : str
            The empirical claim to evaluate.
        context : dict
            Supporting context (methodology, sample, data description, etc.).

        Returns
        -------
        CalibrationDebateVerdict
            Unified verdict with debate scores and calibration metadata.
        """
        debate_verdict: DebateVerdict | None = None
        debate_score = 0.0

        # ── Phase 1: Debate ───────────────────────────────────────────────────
        if self.arena is not None and self.use_debate:
            try:
                debate_claim = DebateClaim(
                    claim_text=claim,
                    context=context,
                    methodology=context.get("methodology", ""),
                    sample_info=context.get("sample", ""),
                )
                debate_verdict = await self.arena.debate(debate_claim)
                debate_score = debate_verdict.overall_score
                _log.info(
                    "Debate completed: score=%.2f, confidence=%s",
                    debate_score,
                    debate_verdict.confidence_level,
                )
            except Exception as e:
                _log.warning("Debate failed: %s; proceeding without debate", e)
                debate_verdict = None

        # ── Phase 2: Calibration ───────────────────────────────────────────────
        calibrator_score: float | None = None

        if self.calibrator is not None and self.use_calibration:
            try:
                # Build a synthetic review report from debate verdict
                review_report = self._build_review_report(claim, debate_verdict)

                cal_report = self.calibrator.calibrate_review(
                    review_report,
                    method="standardization",
                    target_journal=self.journal,
                )
                calibrator_score = cal_report.calibrated_overall_score
                _log.info(
                    "Calibration completed: calibrated=%.2f (original=%.2f)",
                    calibrator_score,
                    cal_report.original_overall_score,
                )

                # Record biases if debate raised concerns
                if debate_verdict is not None:
                    self._record_debate_biases(debate_verdict)

            except Exception as e:
                _log.warning("Calibration failed: %s; proceeding without calibration", e)
                calibrator_score = None

        # ── Phase 3: Merge Scores ──────────────────────────────────────────────
        calibrated_score, debate_wt, calib_wt = self._compute_final_score(
            debate_score,
            calibrator_score,
            debate_verdict,
        )

        # Determine acceptance
        accepted = (
            calibrated_score >= 6.0
            and (debate_verdict is None or debate_verdict.confidence_level != "low")
        )

        confidence_level = (
            debate_verdict.confidence_level
            if debate_verdict is not None
            else "medium"
        )

        # Build verdict
        verdict = CalibrationDebateVerdict(
            claim=claim,
            debate_verdict=debate_verdict,
            calibrator_score=calibrator_score,
            bias_adjustment=round(calibrated_score - debate_score, 4)
            if debate_score > 0
            else 0.0,
            calibrated_score=round(calibrated_score, 2),
            journal=self.journal,
            concerns_from_debate=list(
                debate_verdict.key_concerns if debate_verdict else []
            ),
            suggestions_from_debate=list(
                debate_verdict.suggested_revisions if debate_verdict else []
            ),
            unresolved_from_debate=list(
                debate_verdict.unresolved_issues if debate_verdict else []
            ),
            confidence_level=confidence_level,
            accepted=accepted,
            debate_score=debate_score,
            calibrator_weight_used=calib_wt,
            debate_weight_used=debate_wt,
            overall_score=round(calibrated_score, 2),
        )

        return verdict

    def sync_review_claim(
        self,
        claim: str,
        context: dict[str, Any],
    ) -> CalibrationDebateVerdict:
        """
        Synchronous wrapper around review_claim.

        Uses asyncio to run the async pipeline in a new event loop.
        """
        import asyncio

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            else:
                _log.warning("Already in async context, creating new loop for sync wrapper")
                loop = asyncio.new_event_loop()

            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.review_claim(claim, context),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.review_claim(claim, context))
        except RuntimeError:
            return asyncio.run(self.review_claim(claim, context))

    def _compute_final_score(
        self,
        debate_score: float,
        calibrator_score: float | None,
        verdict: DebateVerdict | None,
    ) -> tuple[float, float, float]:
        """
        Merge debate and calibration scores into a single calibrated score.

        Logic
        -----
        - When calibrator_score is None, use debate_score directly (bridge acts
          as pure DebateArena).
        - When calibrator_score is available, blend with debate_score.
        - Weighting is adjusted by confidence:
            high confidence  → debate weight 75%, calibrator 25%
            medium confidence → debate 60%, calibrator 40%  (default)
            low confidence   → debate 40%, calibrator 60%
        - The calibrator score used is capped at the journal baseline
          to prevent extreme corrections.

        Returns
        -------
        tuple[float, float, float]
            (final_score, debate_weight_used, calibrator_weight_used)
        """
        if calibrator_score is None or self.calibrator is None:
            # No calibration available — use debate score as-is
            return debate_score, 1.0, 0.0

        # Determine confidence-based weights
        confidence = (
            verdict.confidence_level
            if verdict is not None
            else "medium"
        )
        debate_weight = _CONFIDENCE_WEIGHT_MAP.get(
            confidence, _BASE_DEBATE_WEIGHT
        )
        calibration_weight = 1.0 - debate_weight

        # Soft-cap calibrator score against journal baseline
        if self.calibrator is not None:
            baselines = getattr(self.calibrator, "journal_baselines", None)
            if isinstance(baselines, dict):
                journal_bl = baselines.get(self.journal, baselines.get("JF", {}))
                if isinstance(journal_bl, dict):
                    baseline_overall = journal_bl.get("overall", 7.5)
                    deviation = abs(calibrator_score - baseline_overall)
                    if deviation > 2.0:
                        # Strong correction: dampen extreme scores
                        damping = 0.5
                        calibrator_score = baseline_overall + (calibrator_score - baseline_overall) * damping

        # Weighted average
        final_score = debate_weight * debate_score + calibration_weight * calibrator_score

        return round(final_score, 2), round(debate_weight, 2), round(calibration_weight, 2)

    def _build_review_report(
        self,
        claim: str,
        verdict: DebateVerdict | None,
    ) -> dict[str, Any]:
        """
        Build a synthetic review report dict from a DebateVerdict.

        This allows the calibrator to process debate outcomes through its
        standardization pipeline.
        """
        if verdict is not None:
            score = verdict.overall_score
            n_concerns = len(verdict.key_concerns)
        else:
            score = 5.0
            n_concerns = 0

        # Map debate concerns to dimension scores
        # More unresolved concerns → lower methodology score
        methodology_score = max(1.0, min(10.0, 7.5 - n_concerns * 0.3))
        novelty_score = max(1.0, min(10.0, 7.0 + (score - 5.0) * 0.3))
        writing_score = max(1.0, min(10.0, 7.0))

        return {
            "review_id": f"debate_{int(time.time())}",
            "claim": claim,
            "overall_score": score,
            "dimension_scores": {
                "methodology": round(methodology_score, 2),
                "novelty": round(novelty_score, 2),
                "writing": round(writing_score, 2),
                "theory": round(max(1.0, min(10.0, score - 0.5)), 2),
                "reproducibility": round(max(1.0, min(10.0, score - 1.0)), 2),
            },
            "metadata": {
                "journal": self.journal,
                "source": "debate_arena",
            },
        }

    def _record_debate_biases(self, verdict: DebateVerdict) -> None:
        """
        Extract biases from debate objections and record them to BiasHistoryDB.

        This enriches the calibrator's bias history with concerns raised
        during the debate phase, so future calibrations can account for
        systematic methodological weaknesses.
        """
        if self._bias_db is None or verdict is None:
            return

        try:
            # Infer bias types from debate concerns
            bias_instances: list = []

            if _CALIBRATOR_AVAILABLE:
                unresolved = verdict.unresolved_issues or []
                n_unresolved = len(unresolved)

                # Map unresolved issues to bias type
                concern_keywords = {
                    "methodology": [
                        "parallel trends",
                        "identification",
                        "endogeneity",
                        "selection",
                        "iv",
                        "instrument",
                        "rdd",
                        "did",
                    ],
                    "measurement": [
                        "measurement",
                        "error",
                        "attenuation",
                        "self-reported",
                    ],
                    "external": [
                        "external validity",
                        "generaliz",
                        "spillover",
                    ],
                    "statistical": [
                        "multiple testing",
                        "p-hacking",
                        "power",
                        "family-wise",
                        "bonferroni",
                    ],
                }

                for concern in unresolved:
                    lowered = concern.lower()
                    matched_type: str | None = None

                    for bias_key, keywords in concern_keywords.items():
                        if any(kw in lowered for kw in keywords):
                            matched_type = bias_key
                            break

                    if matched_type is None:
                        matched_type = "methodology"

                    # Estimate severity from unresolved count
                    severity = min(0.5 + n_unresolved * 0.1, 1.0)

                    bias_instances.append(
                        BiasInstance(
                            bias_type=BiasType.METHODOLOGY_BIAS
                            if matched_type == "methodology"
                            else BiasType.ORDER_EFFECT,
                            severity=severity,
                            description=f"Debate-raised concern: {concern[:100]}",
                            affected_dimensions=[matched_type],
                            statistical_evidence={
                                "source": "debate_arena",
                                "unresolved_count": n_unresolved,
                            },
                            recommendation="Address in revision or provide additional evidence.",
                        )
                    )

                if bias_instances and BiasReport is not None:
                    bias_report = BiasReport(
                        total_reviews=1,
                        detected_biases=bias_instances,
                        overall_bias_score=sum(b.severity for b in bias_instances)
                        / len(bias_instances),
                        is_calibration_needed=True,
                        bias_patterns={"source": "debate_arena"},
                        review_history_summary={},
                    )
                    self._bias_db.record_review(
                        review_id=f"debate_{int(time.time())}",
                        journal=self.journal,
                        bias_report=bias_report,
                        metadata={"source": "debate_arena"},
                    )
                    _log.info(
                        "Recorded %d debate biases to history DB", len(bias_instances)
                    )
        except Exception as e:
            _log.warning("Failed to record debate biases: %s", e)
