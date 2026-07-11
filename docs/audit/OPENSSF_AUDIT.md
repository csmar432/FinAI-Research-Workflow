# OpenSSF Best Practices · Local Audit

**Result**: 20/21 (95%)
**Tier**: 🥇 Gold (90%+)

## Passed

- [D1] README.md exists and > 1KB — README.md OK
- [D2] README has Installation section — README.md OK
- [D3] README has Usage section — README.md OK
- [D4] LICENSE present (MIT/Apache/BSD) — LICENSE OK
- [C1] CONTRIBUTING.md present and > 1KB — CONTRIBUTING.md OK
- [C2] Issue template exists — .github/ISSUE_TEMPLATE is non-empty directory
- [C3] PR template exists — .github/PULL_REQUEST_TEMPLATE.md OK
- [C4] CI workflow exists — .github/workflows is non-empty directory
- [R1] SECURITY.md present — SECURITY.md OK
- [R2] CODE_OF_CONDUCT.md present — CODE_OF_CONDUCT.md OK
- [R3] Discussion category templates exist — .github/DISCUSSION_TEMPLATE is non-empty directory
- [S1] Dependabot configured — .github/dependabot.yml OK
- [S2] No hardcoded secrets in tracked files — no hardcoded secrets detected
- [Q1] Test directory exists with >= 50 tests — 7802 test functions found
- [Q2] pyproject.toml has version — pyproject.toml OK
- [Q3] Python >= 3.10 declared — pyproject.toml OK
- [Q4] Type checker configured (mypy/ruff) — pyproject.toml OK
- [M1] ROADMAP.md present — ROADMAP.md OK
- [M2] CHANGELOG.md present — CHANGELOG.md OK
- [M3] Zenodo DOI in CITATION.cff — CITATION.cff OK

## Failed

- [S3] requirements.txt has pip-audit / safety — requirements.txt content check failed

## Notes

- This is a *local* audit covering checks we can verify without API access.
- For full OpenSSF scoring, visit https://www.bestpractices.dev/ after the next GitHub webhook fires.
