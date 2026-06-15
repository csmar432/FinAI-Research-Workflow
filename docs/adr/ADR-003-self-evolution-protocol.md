# ADR-003: SEPL (Self-Evolution Protocol Layer)

## Status
Accepted

## Context
AI agents improve through experience. We need a principled way to evolve agent configurations based on execution outcomes. Naive self-modification risks subtle bugs — we need a traceable, assessable, reversible protocol.

## Decision

### Four-Stage SEPL Protocol

```
Act → Observe → Optimize → Remember
```

Implemented as four discrete stages:

#### 1. Propose (Propose)

After each agent execution, the engine analyzes the outcome:

- If quality ≥ baseline → no action
- If quality < baseline → LLM generates improvement suggestions

```
LLM Prompt: "Analyze execution history. Propose specific, actionable
config changes (prompt/temperature/tools/max_iterations/output_format).
Output JSON with expected_impact and confidence."
```

Output: `List[Proposal]` with fields:

- `target`: `"prompt" | "temperature" | "tools" | "max_iterations" | "output_format"`
- `suggestion`: free-text improvement
- `expected_impact`: `"low" | "medium" | "high"`
- `confidence`: 0.0–1.0

#### 2. Assess (Assess)

Evaluate proposals before committing:

| Method | When | Cost |
|---|---|---|
| **Lightweight** (heuristic) | Immediate, after each execution | ~0ms |
| **Heavy** (test on data) | Before committing | ~LLM call |

Lightweight assessment uses a severity matrix:

```
target       | quality < 0.3 | quality < 0.5
------------|---------------|----------------
prompt       | commit        | commit if severity ≥ 0.8
temperature  | commit        | skip
tools        | commit        | skip if severity < 0.6
```

Heavy assessment runs the agent on 5–10 test cases and measures quality delta.

#### 3. Commit (Commit)

Approved changes are applied to agent config and backed up as **golden config**:

```python
# Before committing — backup golden config
self._golden_config[agent_name] = snapshot(agent.config)

# Apply change
apply_proposal(agent.config, proposal)

# Record evolution event
self._history.append(EvolutionEvent(
    proposal=proposal,
    assessment=assessment,
    committed=True,
))
```

Rollback is always available: `engine.rollback(agent_name)` restores golden config.

#### 4. Remember (Remember)

Evolution history is persisted to `long-term memory` and to disk:

```
.cache/evolution_log.jsonl    # all events
.cache/evolution_proposals_*.jsonl  # proposals per agent
```

### Safety Constraints

1. **Golden config backup** before every commit — always roll back to known-good state
2. **Severity threshold** — low-confidence proposals require heavy assessment before commit
3. **Max commits per session** — cap at 5 to prevent runaway modification
4. **Human-in-the-loop gate** — major config changes require HITLGate approval
5. **Audit log** — every proposal, assessment, and commit is timestamped and signed

## Consequences

| | |
|---|---|
| **Positive** | Principled, traceable agent improvement |
| **Positive** | Reversible — golden config ensures no permanent regressions |
| **Positive** | Quantifiable — quality delta measured before/after |
| **Negative** | Proposing is expensive (LLM call per failed execution) |
| **Negative** | Self-modification could introduce subtle bugs (mitigated by golden config + HITL gate) |
| **Negative** | Learning is slow — requires multiple failures before improvement |

## Architecture

```
SelfEvolutionEngine
├── activate()          # Establish golden config, start listening
├── record_and_assess() # Hook: called after each agent.run()
├── propose_improvements() # Heavy: LLM analysis of full history
├── assess_on_tests()   # Heavy: run proposals on test data
├── commit()            # Apply winning proposal, backup golden config
├── rollback()          # Restore golden config
└── stream_events()    # Monitor evolution in real-time

SelfEvolutionAutoTrigger
└── on_task_complete() # Thread-safe hook for ResearchSession

SessionEvolutionIntegration
└── wrap_execute_task() # Wraps ResearchSession._execute_single_task
```

## References

- SkyworkAI/DeepResearchAgent SEPL protocol
- FARAI self-optimizing agents
- Constitutional AI (Anthropic) — principle of bounded self-modification
