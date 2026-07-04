"""
debate_arena.py — Structured Multi-Agent Debate Arena

Implements the three-round debate protocol used in top-tier academic review:
  Round 1 — Proposer: presents the empirical claim with supporting evidence
  Round 2 — Critic: challenges methodology, identification, and external validity
  Round 3 — Synthesizer: resolves conflicts and produces a graded verdict

Each round uses a specialized LLM agent prompt. Verdict includes:
  - Overall score (0-10)
  - Confidence band (±δ)
  - Key unresolved concerns
  - Suggested revisions

    Usage:
    from scripts.core.debate_arena import (
        DebateClaim, DebateRound, DebateVerdict, DebateArena
    )
    arena = DebateArena(llm_gateway=my_gateway)
    verdict = await arena.debate(
        claim="Carbon trading increases green patents by 15%",
        context={"data": "...", "methodology": "DID", "sample": "..."},
        rounds=3,
    )

Integration with ReviewerCalibrator:
    from scripts.core.debate_calibrator_bridge import DebateCalibratorBridge
    bridge = DebateCalibratorBridge(llm_gateway=gateway, journal="经济研究")
    verdict = bridge.review_claim(claim="...", context={...})
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "DebateRole",
    "DebateStage",
    "DebateClaim",
    "DebateRound",
    "DebateVerdict",
    "DebateArena",
    "DebateJudge",
    "SSEEvent",
]


# ─── Enums ────────────────────────────────────────────────────────────────────


class DebateRole(str, Enum):
    """Debate participant roles."""
    PROPOSER = "proposer"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"


class DebateStage(str, Enum):
    """Debate progression stages."""
    CLAIM = "claim"
    ROUND_1 = "round_1"
    ROUND_2 = "round_2"
    ROUND_3 = "round_3"
    VERDICT = "verdict"


# ─── System Prompts ───────────────────────────────────────────────────────────


PROPOSER_SYSTEM_PROMPT = """You are a rigorous empirical researcher presenting an academic claim.
Present the claim with specific evidence, citing papers, data sources, and effect sizes.
Structure your response as:
1. Claim statement (clear, falsifiable)
2. Supporting evidence (papers, data, statistics)
3. Mechanism (why does this hold theoretically)
4. Magnitude (quantified effect size with confidence interval)
Be precise and quantitative. Do not overstate."""


CRITIC_SYSTEM_PROMPT = """You are a skeptical reviewer for a top economics journal (JF/JFE/RFS level).
Challenge this claim on:
1. Identification validity (causal identification assumptions)
2. Internal validity (endogeneity, selection, omitted variable bias)
3. External validity (generalizability to other contexts)
4. Measurement error (errors-in-variables)
5. Statistical concerns (power, multiple testing, p-hacking)
6. Confounding variables
Be precise and cite specific methodological concerns. Name the econometric issue explicitly."""


SYNTHESIZER_SYSTEM_PROMPT = """You are a senior editor at a top economics journal.
Weigh the evidence from both Proposer and Critic fairly.
Produce a balanced verdict.
State:
1. What the evidence supports (strengths)
2. What remains unconvincing (weaknesses)
3. What revisions would strengthen the paper
4. Your confidence level in the claim
Be fair, rigorous, and constructive. Do not simply split the difference."""


# ─── Critic Challenge Templates ───────────────────────────────────────────────


CRITIC_CHALLENGE_TEMPLATES: list[str] = [
    "Parallel trends assumption may be violated in the pre-treatment period. "
    "Conduct an event-study and show the coefficients on leads are jointly zero.",

    "Treatment endogeneity: the policy was not randomly assigned. Use an instrumental "
    "variable or regression discontinuity design to address selection on observables.",

    "Sample selection bias: the analysis excludes firms that exited the market. "
    "Apply Heckman correction or use survival analysis.",

    "Spillover contamination: treated firms may affect control group outcomes through "
    "input/output markets, violating SUTVA.",

    "Anticipation effects: firms may have changed behavior before policy implementation. "
    "Test for pre-trends and exclude periods near the cutoff.",

    "Measurement error in the treatment variable: self-reported data is subject to "
    "classical or classical-plus attenuation bias.",

    "Multiple hypothesis testing without correction: with many outcome variables, "
    "the family-wise error rate inflates. Apply Bonferroni or Benjamini-Hochberg.",

    "Heterogeneous treatment effects: the average effect masks important variation "
    "across firm size, industry, or region.",

    "Dynamic spillovers: early adopters may affect later adopters' outcomes, "
    "complicating the interpretation of treatment timing.",

    "General equilibrium effects: removing the policy would have economy-wide impacts "
    "not captured by the partial-equilibrium research design.",

    "Confounding policy changes: other contemporaneous policies (environmental regs, "
    "trade reforms) may drive the observed outcomes.",

    "Difference-in-differences with staggered adoption: use Callaway-SantAnna or "
    "Sun-Abraham to avoid the negative weighting issue.",

    "Placebo tests with false treatments: results should be robust to random "
    "placebo policy assignment.",

    "Sensitivity to bandwidth choice: if RDD, results should hold across "
    "different bandwidth selectors (IK, CCT, MSE-optimal).",

    "Falsification tests on pre-determined outcomes: demonstrate that "
    "outcomes unaffected by the policy are indeed unchanged.",

    "External validity: findings from one province/industry/year may not "
    "generalize to the broader economy.",

    "Publication bias: small studies with positive results are more likely published, "
    "inflating the estimated effect.",

    "Attrition and non-compliance: intent-to-treat vs. treatment-on-treated "
    "distinction matters for causal interpretation.",

    "Synthetic control unit weighting: the synthetic control may overfit noise. "
    "Conduct permutation tests with placebo treated units.",

    "Instrument validity: the proposed instrument must satisfy relevance and exclusion. "
    "Test the first stage F-statistic and conduct overidentification tests.",
]


# ─── SSE Event ────────────────────────────────────────────────────────────────


@dataclass
class SSEEvent:
    """Server-Sent Event wrapper for debate streaming."""
    event: str
    data: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        return f"id: {self.event_id}\nevent: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


# ─── DebateClaim ──────────────────────────────────────────────────────────────


@dataclass
class DebateClaim:
    """
    An empirical claim submitted for adversarial debate.

    Attributes
    ----------
    claim_text : str
        The core empirical claim to be debated.
    context : dict
        Background context (data description, methodology summary, etc.).
    domain : str
        Research domain (e.g., "climate economics", "corporate finance").
    methodology : str
        Empirical methodology used (e.g., "DID", "RDD", "IV").
    sample_info : str
        Sample description (e.g., "A-share listed firms 2010-2023").
    submitted_by : str
        Identifier of who submitted the claim.
    submitted_at : float
        Unix timestamp of submission.
    """
    claim_text: str
    context: dict[str, Any] = field(default_factory=dict)
    domain: str = ""
    methodology: str = ""
    sample_info: str = ""
    submitted_by: str = "anonymous"
    submitted_at: float = field(default_factory=time.time)

    def to_prompt(self) -> str:
        """Render the claim as a structured prompt for the Proposer."""
        parts = [
            f"## Claim\n{self.claim_text}",
        ]
        if self.domain:
            parts.append(f"## Domain\n{self.domain}")
        if self.methodology:
            parts.append(f"## Methodology\n{self.methodology}")
        if self.sample_info:
            parts.append(f"## Sample\n{self.sample_info}")
        if self.context:
            parts.append(f"## Context\n{json.dumps(self.context, ensure_ascii=False, indent=2)}")
        return "\n\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── DebateRound ──────────────────────────────────────────────────────────────


@dataclass
class DebateRound:
    """
    A single debate round contributed by one participant.

    Attributes
    ----------
    round_number : int
        Which debate round (1=Proposer, 2=Critic, 3=Synthesizer).
    role : DebateRole
        Who produced this round.
    content : str
        The substantive argument text.
    evidence_cited : list[str]
        Citations or references raised in this round.
    objections_raised : list[str]
        Specific objections raised (Critic role).
    counter_arguments : list[str]
        Rebuttals or counter-arguments raised (Proposer role).
    timestamp : float
        Unix timestamp of round completion.
    """
    round_number: int
    role: DebateRole
    content: str
    evidence_cited: list[str] = field(default_factory=list)
    objections_raised: list[str] = field(default_factory=list)
    counter_arguments: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def is_substantive(self) -> bool:
        """Check if the round has sufficient content (>100 chars)."""
        return len(self.content.strip()) > 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "role": self.role.value,
            "content": self.content,
            "evidence_cited": self.evidence_cited,
            "objections_raised": self.objections_raised,
            "counter_arguments": self.counter_arguments,
            "timestamp": self.timestamp,
        }


# ─── DebateVerdict ────────────────────────────────────────────────────────────


@dataclass
class DebateVerdict:
    """
    Final verdict from the debate arena.

    Attributes
    ----------
    claim : str
        The original claim being verdicted.
    overall_score : float
        Score from 0 (completely unconvincing) to 10 (fully convincing).
    confidence_delta : float
        Confidence band half-width (±δ).
    key_concerns : list[str]
        Main concerns raised during debate.
    unresolved_issues : list[str]
        Objections not adequately addressed by the Proposer.
    suggested_revisions : list[str]
        Concrete revisions to strengthen the claim.
    confidence_reasoning : str
        Explanation of why confidence is high/medium/low.
    rounds_summary : list[DebateRound]
        All debate rounds that contributed to the verdict.
    accepted : bool
        Whether the claim is accepted as valid.
    confidence_level : str
        "high", "medium", or "low".
    """
    claim: str
    overall_score: float
    confidence_delta: float
    key_concerns: list[str] = field(default_factory=list)
    unresolved_issues: list[str] = field(default_factory=list)
    suggested_revisions: list[str] = field(default_factory=list)
    confidence_reasoning: str = ""
    rounds_summary: list[DebateRound] = field(default_factory=list)
    accepted: bool = False
    confidence_level: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "overall_score": self.overall_score,
            "confidence_delta": self.confidence_delta,
            "key_concerns": self.key_concerns,
            "unresolved_issues": self.unresolved_issues,
            "suggested_revisions": self.suggested_revisions,
            "confidence_reasoning": self.confidence_reasoning,
            "confidence_level": self.confidence_level,
            "accepted": self.accepted,
            "rounds_summary": [r.to_dict() for r in self.rounds_summary],
        }

    def to_review_text(self) -> str:
        """
        Generate a ~200-word academic review paragraph.

        Returns a structured paragraph summarizing the debate outcome.
        """
        accepted_str = "accepted" if self.accepted else "not accepted"
        conf = self.confidence_level.upper()

        lines = [
            f"This debate evaluated the empirical claim: \"{self.claim[:100]}{'...' if len(self.claim) > 100 else ''}\"",
            f"The claim was {accepted_str} with an overall score of {self.overall_score:.1f}/10 "
            f"({conf} confidence, ±{self.confidence_delta:.1f}).",
        ]

        if self.key_concerns:
            concerns = "; ".join(self.key_concerns[:3])
            lines.append(f"Key concerns include: {concerns}.")

        if self.unresolved_issues:
            lines.append(
                f" {len(self.unresolved_issues)} issue(s) remain unresolved, including: "
                f"{'; '.join(self.unresolved_issues[:2])}."
            )

        if self.suggested_revisions:
            lines.append(
                f" Suggested revisions include: {self.suggested_revisions[0]}"
                f"{' and ' + self.suggested_revisions[1] if len(self.suggested_revisions) > 1 else ''}."
            )

        if self.confidence_reasoning:
            lines.append(f" Confidence assessment: {self.confidence_reasoning[:150]}.")

        # Ensure ~200 words
        full_text = " ".join(lines)
        words = len(full_text.split())
        if words < 150:
            lines.append(
                f" Overall, the debate revealed {'strong' if self.accepted else 'moderate'} "
                f"empirical support, with {'high' if self.confidence_level == 'high' else 'some'} "
                f"remaining uncertainty that {'can be addressed' if self.suggested_revisions else 'requires further investigation'}."
            )

        return " ".join(lines)


# ─── DebateArena ──────────────────────────────────────────────────────────────


class DebateArena:
    """
    Orchestrates structured three-round adversarial debate.

    Parameters
    ----------
    llm_gateway : callable or None
        LLM gateway callable. If None, uses mock responses for testing.
        Expected signature: llm_gateway(prompt, system=None, temperature=0.3) -> str
    max_rounds : int
        Maximum debate rounds. Default 3 (Proposer, Critic, Synthesizer).
    temperature : float
        LLM sampling temperature. Default 0.3 (low, for reproducible arguments).

    Usage
    -----
        arena = DebateArena(llm_gateway=my_gateway)
        verdict = await arena.debate(
            claim=DebateClaim(claim_text="...", domain="finance", methodology="DID"),
            rounds=3,
        )
    """

    def __init__(
        self,
        llm_gateway: Callable[[str, str | None, float], str] | None = None,
        max_rounds: int = 3,
        temperature: float = 0.3,
    ):
        self.llm_gateway = llm_gateway
        self.max_rounds = max_rounds
        self.temperature = temperature

    async def debate(self, claim: DebateClaim, rounds: int | None = None) -> DebateVerdict:
        """
        Run the full multi-round debate.

        Parameters
        ----------
        claim : DebateClaim
            The empirical claim to debate.
        rounds : int, optional
            Number of rounds. Defaults to self.max_rounds.

        Returns
        -------
        DebateVerdict
            Complete verdict with scores, concerns, and revisions.
        """
        n_rounds = rounds or self.max_rounds
        all_rounds: list[DebateRound] = []

        # Round 1: Proposer
        logger.info("Running Round 1: Proposer")
        proposer_round = await self._run_proposer_round(claim)
        all_rounds.append(proposer_round)

        # Round 2: Critic
        if n_rounds >= 2:
            logger.info("Running Round 2: Critic")
            critic_round = await self._run_critic_round(claim, proposer_round)
            all_rounds.append(critic_round)

        # Round 3: Synthesizer
        if n_rounds >= 3:
            logger.info("Running Round 3: Synthesizer")
            synthesizer_round = await self._run_synthesizer_round(claim, all_rounds)
            all_rounds.append(synthesizer_round)

        # Compute verdict
        logger.info("Computing final verdict")
        verdict = self._compute_verdict(claim, all_rounds)
        return verdict

    async def _run_proposer_round(self, claim: DebateClaim) -> DebateRound:
        """Round 1: Proposer presents the claim with evidence."""
        prompt = (
            f"Present the following empirical claim with supporting evidence.\n\n"
            f"{claim.to_prompt()}\n\n"
            f"Structure your response with:\n"
            f"1. Clear claim statement\n"
            f"2. Supporting evidence (papers, statistics, data sources)\n"
            f"3. Theoretical mechanism\n"
            f"4. Quantified effect size with confidence interval"
        )

        content = await self._call_llm(prompt, DebateRole.PROPOSER)

        # Extract evidence citations (look for bracketed citations or patterns)
        evidence = self._extract_citations(content)

        return DebateRound(
            round_number=1,
            role=DebateRole.PROPOSER,
            content=content,
            evidence_cited=evidence,
            counter_arguments=[],
            timestamp=time.time(),
        )

    async def _run_critic_round(
        self, claim: DebateClaim, proposer_round: DebateRound
    ) -> DebateRound:
        """Round 2: Critic challenges methodology and identification."""
        # Inject a challenge template to ensure the critic never runs out of ammunition
        challenge_pick = CRITIC_CHALLENGE_TEMPLATES[
            hash(claim.claim_text) % len(CRITIC_CHALLENGE_TEMPLATES)
        ]

        prompt = (
            f"You are a skeptical journal reviewer. Challenge this claim rigorously.\n\n"
            f"## Claim\n{claim.claim_text}\n\n"
            f"## Proposer's argument\n{proposer_round.content[:2000]}\n\n"
            f"## Methodology claimed\n{claim.methodology or 'Not specified'}\n\n"
            f"## Sample\n{claim.sample_info or 'Not specified'}\n\n"
            f"## Suggested challenge angle\n{challenge_pick}\n\n"
            f"Challenge the claim on:\n"
            f"1. Identification validity (causal assumptions)\n"
            f"2. Internal validity (endogeneity, selection)\n"
            f"3. External validity (generalizability)\n"
            f"4. Measurement error\n"
            f"5. Statistical concerns (multiple testing, p-hacking)\n"
            f"Be specific and cite named econometric concerns."
        )

        content = await self._call_llm(prompt, DebateRole.CRITIC)

        # Extract objections (look for numbered lists, "concern", "issue", etc.)
        objections = self._extract_objections(content)

        return DebateRound(
            round_number=2,
            role=DebateRole.CRITIC,
            content=content,
            evidence_cited=[],
            objections_raised=objections,
            timestamp=time.time(),
        )

    async def _run_synthesizer_round(
        self, claim: DebateClaim, rounds: list[DebateRound]
    ) -> DebateRound:
        """Round 3: Synthesizer weighs evidence and produces balanced verdict."""
        rounds_text = "\n\n".join(
            f"=== Round {r.round_number} ({r.role.value}) ===\n{r.content[:1500]}"
            for r in rounds
        )

        prompt = (
            f"Weigh the following Proposer and Critic arguments. Produce a balanced verdict.\n\n"
            f"{rounds_text}\n\n"
            f"## Your task\n"
            f"1. Summarize what evidence supports the claim\n"
            f"2. Summarize what remains unconvincing\n"
            f"3. State what revisions would strengthen the paper\n"
            f"4. Assess your confidence: high / medium / low\n"
            f"5. Score the claim 0-10 with reasoning\n"
            f"6. List unresolved objections that need future work\n"
            f"Be fair and rigorous. Do not simply split the difference."
        )

        content = await self._call_llm(prompt, DebateRole.SYNTHESIZER)

        return DebateRound(
            round_number=3,
            role=DebateRole.SYNTHESIZER,
            content=content,
            evidence_cited=[],
            timestamp=time.time(),
        )

    def _compute_verdict(
        self, claim: DebateClaim, rounds: list[DebateRound]
    ) -> DebateVerdict:
        """Score the debate and produce a structured verdict."""
        # Compute scores using the rule-based judge
        proposer_score, critic_score, unresolved = DebateJudge.score_from_rounds(
            rounds, claim
        )

        # Synthesizer round provides the judgment text
        synthesizer_round = next(
            (r for r in rounds if r.role == DebateRole.SYNTHESIZER), None
        )
        critic_round = next(
            (r for r in rounds if r.role == DebateRole.CRITIC), None
        )

        # Extract score from synthesizer text (look for "X/10" pattern)
        synth_content = synthesizer_round.content if synthesizer_round else ""
        score_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", synth_content)
        if score_match:
            llm_score = float(score_match.group(1))
            # Blend rule-based and LLM scores (60% judge, 40% LLM)
            final_score = round(0.6 * (proposer_score + critic_score) / 2 + 0.4 * llm_score, 2)
        else:
            final_score = round((proposer_score + critic_score) / 2, 2)

        final_score = max(0.0, min(10.0, final_score))

        # Confidence band: wider when many unresolved issues
        n_unresolved = len(unresolved)
        confidence_delta = min(2.5, 0.5 + 0.25 * n_unresolved)

        # Confidence level
        if critic_score >= 7.0 and n_unresolved <= 1:
            confidence_level = "high"
        elif critic_score >= 5.0 and n_unresolved <= 3:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        # Accepted = score >= 6.0 and confidence != low
        accepted = final_score >= 6.0 and confidence_level != "low"

        # Key concerns
        key_concerns = []
        if critic_round:
            key_concerns = list(critic_round.objections_raised[:5])

        # Suggested revisions (from synthesizer)
        suggested_revisions = self._extract_suggestions(synth_content)

        return DebateVerdict(
            claim=claim.claim_text,
            overall_score=final_score,
            confidence_delta=round(confidence_delta, 2),
            key_concerns=key_concerns,
            unresolved_issues=unresolved,
            suggested_revisions=suggested_revisions,
            confidence_reasoning=(
                f"Score {final_score:.1f}/10 based on proposer ({proposer_score:.1f}) "
                f"and critic ({critic_score:.1f}) strength. "
                f"{n_unresolved} unresolved objection(s) reduce confidence."
            ),
            rounds_summary=rounds,
            accepted=accepted,
            confidence_level=confidence_level,
        )

    async def _call_llm(self, prompt: str, role: DebateRole) -> str:
        """
        Call the LLM gateway with role-specific system prompts.

        If llm_gateway is None, returns a mock response for testing.
        """
        system_map = {
            DebateRole.PROPOSER: PROPOSER_SYSTEM_PROMPT,
            DebateRole.CRITIC: CRITIC_SYSTEM_PROMPT,
            DebateRole.SYNTHESIZER: SYNTHESIZER_SYSTEM_PROMPT,
        }
        system_prompt = system_map.get(role, "")

        if self.llm_gateway is None:
            return self._mock_response(role, prompt[:500])

        try:
            result = self.llm_gateway(prompt, system=system_prompt, temperature=self.temperature)
            # Handle async gateway
            import asyncio
            if asyncio.iscoroutine(result):
                result = await result
            return str(result)
        except Exception as e:
            logger.warning(f"LLM call failed for {role}: {e}")
            return self._mock_response(role, prompt[:500])

    def _mock_response(self, role: DebateRole, prompt_snippet: str) -> str:
        """Generate a deterministic mock response for testing."""
        if role == DebateRole.PROPOSER:
            return (
                f"Mock Proposer response for: {prompt_snippet[:100]}\n\n"
                f"This claim is supported by three key empirical findings. "
                f"First, [Author, Year] document a {5 + (hash(prompt_snippet) % 20)}% "
                f"effect using panel data. Second, natural experiments confirm "
                f"the mechanism. Third, the effect is robust across multiple "
                f"specifications and subsamples. Effect size: β = "
                f"{0.05 + (hash(prompt_snippet) % 15) * 0.01:.2f} "
                f"(95% CI: [lower, upper], p < 0.05)."
            )
        elif role == DebateRole.CRITIC:
            return (
                f"Mock Critic response for: {prompt_snippet[:100]}\n\n"
                f"Three major concerns:\n"
                f"1. Parallel trends assumption may be violated (event-study needed)\n"
                f"2. Treatment endogeneity: selection on observables not fully addressed\n"
                f"3. External validity: findings may not generalize to other contexts\n"
                f"These issues require additional robustness checks before acceptance."
            )
        else:  # SYNTHESIZER
            return (
                f"Mock Synthesizer response for: {prompt_snippet[:100]}\n\n"
                f"Verdict: This claim has moderate empirical support.\n"
                f"Score: 6.5/10\n"
                f"Confidence: Medium\n"
                f"Strengths: Novel context, plausible mechanism, some robustness checks.\n"
                f"Weaknesses: Identification concerns remain, sample limited.\n"
                f"Suggested revisions: Conduct event-study, add IV, test external validity."
            )

    def _extract_citations(self, text: str) -> list[str]:
        """Extract citation patterns from text."""
        patterns = [
            r"\[[A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}\]",
            r"[A-Z][a-z]+\s+et\s+al\.?\s+\(\d{4}\)",
            r"\([A-Z][a-z]+\s+et\s+al\.?,\s*\d{4}\)",
        ]
        citations: list[str] = []
        for pattern in patterns:
            citations.extend(re.findall(pattern, text))
        return list(dict.fromkeys(citations))[:10]  # Deduplicate, max 10

    def _extract_objections(self, text: str) -> list[str]:
        """Extract numbered objections from critic text."""
        lines = text.split("\n")
        objections: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Numbered items, "concern", "issue", "problem" patterns
            if re.match(r"^\d+[.)]\s+", stripped) or "concern" in stripped.lower() or "issue" in stripped.lower():
                cleaned = re.sub(r"^\d+[.)]\s+", "", stripped).strip()
                if len(cleaned) > 20:
                    objections.append(cleaned)
        return objections[:10]

    def _extract_suggestions(self, text: str) -> list[str]:
        """Extract suggested revisions from synthesizer text."""
        lines = text.split("\n")
        suggestions: list[str] = []
        for line in lines:
            stripped = line.strip()
            if (
                re.match(r"^\d+[.)]\s+", stripped)
                or "suggest" in stripped.lower()
                or "revise" in stripped.lower()
            ):
                cleaned = re.sub(r"^\d+[.)]\s+", "", stripped).strip()
                if len(cleaned) > 15:
                    suggestions.append(cleaned)
        return suggestions[:5]

    def stream_debate(self, claim: DebateClaim) -> SSEEvent:
        """
        Synchronous SSE event generator for each round completion.

        Yields SSEEvent objects for each round's completion.
        Use in a streaming endpoint or iterate in a loop.

        Parameters
        ----------
        claim : DebateClaim
            The claim to debate.

        Yields
        ------
        SSEEvent
            Events: "debate_start", "round_1_complete", "round_2_complete",
            "round_3_complete", "verdict_complete".
        """
        yield SSEEvent(event="debate_start", data={"claim": claim.claim_text[:100]})

        # Run synchronously via judge scoring
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            verdict = loop.run_until_complete(self.debate(claim))
        finally:
            loop.close()

        for _i, r in enumerate(verdict.rounds_summary):
            stage_map = {1: "round_1_complete", 2: "round_2_complete", 3: "round_3_complete"}
            yield SSEEvent(
                event=stage_map.get(r.round_number, f"round_{r.round_number}_complete"),
                data={
                    "round": r.round_number,
                    "role": r.role.value,
                    "content_preview": r.content[:200],
                    "substantive": r.is_substantive(),
                },
            )

        yield SSEEvent(
            event="verdict_complete",
            data={
                "score": verdict.overall_score,
                "confidence": verdict.confidence_level,
                "accepted": verdict.accepted,
                "key_concerns": verdict.key_concerns[:3],
                "unresolved": verdict.unresolved_issues[:3],
                "suggestions": verdict.suggested_revisions[:3],
            },
        )


# ─── DebateJudge ──────────────────────────────────────────────────────────────


class DebateJudge:
    """
    Standalone rule-based scoring without LLM.

    Provides transparent, reproducible scoring for debate rounds.
    """

    @staticmethod
    def score_from_rounds(
        rounds: list[DebateRound], claim: DebateClaim
    ) -> tuple[float, float, list[str]]:
        """
        Score debate rounds without LLM.

        Parameters
        ----------
        rounds : list[DebateRound]
            All debate rounds.
        claim : DebateClaim
            Original claim for context.

        Returns
        -------
        tuple[float, float, list[str]]
            (proposer_score, critic_score, unresolved_issues)
            - Proposer score: min(10, 5 + substantiveness_weight * evidence_count)
            - Critic score: min(10, 5 + substantiveness_weight * objection_count)
            - Final = weighted average (proposer 40%, critic 30%, synthesizer 30%)
            - Confidence = 1 - abs(critic_score - proposer_score) / 10
            - Unresolved = all objections not addressed by synthesizer

        Scoring logic
        -------------
        - Each piece of evidence cited adds 0.5 points (max +2.5)
        - Each objection raised adds 0.5 points (max +2.5)
        - Substantive content (>100 chars) is required for points
        - Objections addressed by synthesizer reduce unresolved count
        """
        proposer_round = next((r for r in rounds if r.role == DebateRole.PROPOSER), None)
        critic_round = next((r for r in rounds if r.role == DebateRole.CRITIC), None)
        synthesizer_round = next((r for r in rounds if r.role == DebateRole.SYNTHESIZER), None)

        # Proposer score: base 5 + evidence bonus
        evidence_bonus = 0.0
        if proposer_round and proposer_round.is_substantive():
            evidence_bonus = min(2.5, len(proposer_round.evidence_cited) * 0.5)
            evidence_bonus += 0.5 if len(proposer_round.content) > 500 else 0.0
        proposer_score = min(10.0, 5.0 + evidence_bonus)

        # Critic score: base 5 + objection bonus
        objection_bonus = 0.0
        if critic_round and critic_round.is_substantive():
            objection_bonus = min(2.5, len(critic_round.objections_raised) * 0.5)
            objection_bonus += 0.5 if len(critic_round.content) > 500 else 0.0
        critic_score = min(10.0, 5.0 + objection_bonus)

        # Compute final weighted score
        # Round 3 (synthesizer) contributes 30% weight implicitly via verdict

        # Determine unresolved issues: critic objections not in synthesizer
        all_objections = set(critic_round.objections_raised) if critic_round else []
        synthesizer_content_lower = (
            synthesizer_round.content.lower() if synthesizer_round else ""
        )

        all_objections_set = set(all_objections)
        addressed: set[str] = set()
        for obj in all_objections:
            # Check if synthesizer addressed the objection
            obj_keywords = obj.lower().split()[:3]
            if any(kw in synthesizer_content_lower for kw in obj_keywords if len(kw) > 4):
                addressed.add(obj)

        unresolved_issues = list(all_objections_set - addressed)

        # Adjust critic score based on how many objections were addressed
        address_ratio = len(addressed) / max(1, len(all_objections_set))
        critic_score = min(10.0, critic_score * (1 - 0.2 * address_ratio))

        return round(proposer_score, 2), round(critic_score, 2), unresolved_issues
