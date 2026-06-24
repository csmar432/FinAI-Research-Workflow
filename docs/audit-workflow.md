# Audit Workflow — Defending Against LLM-Hallucinated Audit Reports

## Problem

LLM-generated audit reports (e.g., the 2026-06-24 v3 audit we received
with 26 items) frequently contain **confident but false claims**:

| Hallucination pattern | Real-world example |
|----------------------|--------------------|
| Claims a version reference exists | "README says v1.8.5" — but 0 references exist |
| Claims a feature is missing | "0 `assert_allclose` calls" — actually 21 calls |
| Reports stale metrics | "coverage fail_under=6" — actually 10 |
| Misreads API signatures | "RegressionEngine(y_col=...)" — kwarg is y_var |
| Fabricates file contents | Quotes from non-existent files |
| Wrong dependency recommendations | "use moderndid" — package not on PyPI |

In our v3 audit, **20 of 26 items (77%) were false positives** when
verified with simple grep/test commands. Acting on all of them would
have wasted ~3 person-months and broken working code.

## Defense in depth

### Layer 1: `scripts/audit_guard.py` (automatic)

Run on every commit via pre-commit. Verifies 8 critical claims:

```bash
python scripts/audit_guard.py          # 8/8 expected to pass
python scripts/audit_guard.py --json   # for CI consumption
```

If a check fails, **assume the audit claim is wrong** and re-verify
manually before changing code. The check exists because we already
saw it fail on a verified-false audit item.

### Layer 2: Pre-commit hook (mandatory)

`.pre-commit-config.yaml` runs 5 cheap audit_guard checks on every
commit. They take <3 seconds total. If they fail, the commit is
blocked until the false-positive pattern is fixed or the underlying
state is corrected.

### Layer 3: Manual verification protocol

Before fixing ANY audit item, run through this checklist:

```
□ Does the cited file actually exist?         [check files]
□ Does the cited symbol/string actually exist? [grep -rn]
□ Does the cited test actually fail?           [pytest]
□ Is the cited metric actually current?        [re-compute]
□ Did the cited issue exist before the audit?  [git log -p]
□ Does the proposed fix break anything?        [run tests after]
```

If any answer is "no", the audit item is likely a hallucination.
Push back with evidence rather than committing the fix.

### Layer 4: Audit report metadata

Future audit reports should be evaluated with these rejection criteria:

- **Reject** if the report contains any version number not found by grep
- **Reject** if "missing" claims contradict `ls`/`grep` results
- **Reject** if proposed fixes reference libraries not on PyPI
- **Reject** if the report's title (P0/P1) was generated without
  measuring blast radius (lines-of-code affected, test coverage impact)
- **Accept** only items where grep/pytest evidence is reproducible

## Origin of this workflow

After fixing 6 real issues from v3 audit on 2026-06-24, we verified
the remaining 20 items were false positives. The audit_guard.py
captures the evidence-collection commands so future audits can be
triaged in <5 minutes instead of <5 hours.

## When audit_guard fails

If a check fails:

1. **First**: re-run to rule out flaky test (`--check 6`)
2. **If persistent**: investigate whether the underlying state has
   legitimately regressed (e.g., someone deleted a test)
3. **If state is fine**: update the audit claim — it was wrong
4. **Never**: commit a "fix" for a claim that isn't reproducible
