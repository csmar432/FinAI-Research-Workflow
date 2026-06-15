# ADR-003: SEPL (Self-Evolution Protocol Layer)

**Status**: Accepted

**Date**: 2026-06-08

## Context

AI research agents improve through experience. We need a principled way to evolve agent configurations (prompts, temperature, tools) based on execution outcomes, without introducing subtle bugs or losing reproducibility.

## Decision

Four-stage SEPL protocol implemented in `SelfEvolutionEngine`:

1. **Propose** — `propose_improvements()`: LLM analyzes execution history and failure patterns, generates JSON improvement suggestions
2. **Assess** — `assess_on_tests()`: Proposals evaluated on test data or via heuristic severity scoring
3. **Commit** — `commit()`: Approved changes applied to agent config, golden config snapshotted before each change
4. **Remember** — `save_to_memory()`: Evolution history stored in `ResearchMemory` for cross-session learning

**Golden Config**: Before every `activate()`, the current agent config is snapshotted. On rollback, the golden config is restored.

**Automatic Trigger**: `SelfEvolutionAutoTrigger` monitors consecutive failures. After N failures, triggers evolution proposal automatically.

## Consequences

**Positive**:
- Principled, traceable agent improvement with full history
- Automatic recovery from degraded configurations
- Cross-session learning via `CrossSessionKnowledge`

**Negative**:
- Proposing is expensive (LLM calls per proposal)
- Self-modification could introduce subtle bugs (mitigated by golden config + rollback)
- Evolution history can grow large over time

## References

- `scripts/core/self_evolution.py` — `SelfEvolutionEngine`
- `scripts/core/memory.py` — `ResearchMemory.store_knowledge()`
