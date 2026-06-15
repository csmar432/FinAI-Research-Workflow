# ADR-002: ProvenanceChain Architecture

**Status**: Accepted

**Date**: 2026-06-08

## Context

Academic papers require every published number to be traceable to its source. Reviewers increasingly ask for data lineage, and journal policies (e.g., AEA, REStud) now mandate data availability statements. We need a system that tracks the full lineage of every number, chart, and table in a paper.

## Decision

Every data fetch, transformation, and regression registers a **node** in the `ProvenanceChain` (a directed acyclic graph):

**Node Types** (11 types):
- `RAW_DATA` — Original data source (MCP, file, API)
- `CLEANED_DATA` — After cleaning/filtering
- `VARIABLE` — Derived variable
- `CODE` — Analysis script
- `OUTPUT` — Regression/analysis output
- `CHART` — Generated figure
- `TABLE` — Generated table
- `NUMBER` — Extracted number from a table
- `PARAGRAPH` — Written text
- `CITATION` — Referenced paper
- `MODEL` — Trained model

**Export Formats**:
- `export_mermaid()` — Mermaid flowchart for visualization
- `export_report()` — Markdown document with full lineage
- `export_figure_provenance_report()` — Per-figure provenance HTML/MD
- `inject_provenance_into_latex()` — Auto-inject `\note{...}` into figure captions

**LaTeX Integration**: Every figure registered via `register_figure()` automatically appends provenance metadata to its caption.

## Consequences

**Positive**:
- Full audit trail for every published number
- Mermaid diagrams enable visual backtracking
- Latex injection means reviewers see lineage without extra steps

**Negative**:
- Performance overhead: ~10ms per data operation
- Storage: provenance.json grows with each session
- Developer discipline required: every MCP call must register

## References

- `scripts/core/provenance.py` — `ProvenanceChain` class
- `scripts/research_framework/data_fetcher.py` — `_cached_mcp_call()` integration
