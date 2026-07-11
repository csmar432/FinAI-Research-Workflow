# Changelog

All notable changes to FinAI Research Workflow are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0-alpha] - 2026-07-11

### Added

- `mcp_servers/_shared/_version.py`: single source of truth for APP_VERSION/APP_NAME,
  reads from top-level `pyproject.toml` (skips `mcp_servers/pyproject.toml` sub-package)
- 3 GitHub Discussion seed posts (#135 release announcement, #136 ideas/arXiv
  auto-submit, #137 Q&A install) for community seeding
- `audit_guard.py` Check 16: scans 260+ scripts/**/*.py files for hardcoded
  `vX.Y.Z` version drift from `[project].version`
- `tests/test_version_drift.py`: 14 regression tests covering CLI banner, MCP
  servers (sec_edgar/cryptocompare/newsapi), `gen_architecture_diagrams.py`
- GitHub Description updated with accurate numbers (43 MCP, 47 methods, 30 templates)
- 3 GitHub Discussion templates + 4 kinds of category defaults enabled

### Fixed

- `scripts/cli.py` banner: was hardcoded `v1.0.0`, now dynamic from pyproject
- `scripts/cli.py` `version_cmd`: fallback `"1.0.0"` → 5-tier resolution
  (pyproject → importlib.metadata → "0.0.0+unknown")
- `mcp_servers/user_sec_edgar/server.py`: `APP_VERSION = "1.0.0"` → dynamic
- `mcp_servers/user_cryptocompare/server.py`: same fix
- `mcp_servers/user_newsapi/server.py`: same fix
- `scripts/gen_architecture_diagrams.py`: header() default `version="v1.0.0"`
  → dynamic; inline "v1.0.0 标签" → dynamic
- `README.md`: "~20 种计量方法" / "~30 Econometric Methods" → "47" (truth)
- `tests/test_research_directions_advanced.py`: stale docstring "all 12" → 13
- `.gitignore`: added MANUAL_TASKS.md (local-only runbook)

### Changed

- This is a pre-release (`alpha`) tag — used during the Star Audit follow-up
  phase. Next stable will be `0.3.0` once DemO GIF + topics + awesome-list
  promotion complete.

## [1.0.1] - 2026-07-08

### Fixed

- Trigger Zenodo webhook for DOI minting. The v1.0.0 release did not auto-archive
  on Zenodo because the GitHub integration toggle was enabled after the release
  was created. This patch release forces a fresh GitHub → Zenodo webhook cycle
  and re-archives the same v1.0.0 source tree (no code changes).

## [1.0.0] - 2026-07-08

### Added

- 8,048 pytest tests across 398 test files (32.2% coverage baseline)
- 47 econometric methods (DID, IV, RDD, PSM, GMM, modern staggered DID variants,
  synthetic control, synthetic DID, panel quantile, interactive fixed effects,
  triple-diff, local projections, spatial regression, ...)
- 43 MCP data-source servers (OpenAlex, ArXiv, Semantic Scholar, NBER, SEC EDGAR,
  Tushare, yfinance, FRED, World Bank, IMF, OECD, Eastmoney reports, ...)
- 30 journal templates (经济研究 / 金融研究 / JF / JFE / RFS / JPE / Econometrica / ...)
- 17 AI skills for Claude Code, Cursor, GitHub Copilot
- GitHub Discussions enabled with 6 default categories
- Smoke tests for `scripts/start_research.py` (0% → 70.5% coverage on entry point)
- Dependabot configuration for Python ecosystem security updates

### Fixed

- `scripts/research_framework/volatility_models.py::VolatilitySpillover.diebold_yilmaz`:
  four silent bugs (statsmodels API drift, shape mismatch, pandas `applymap`
  deprecation, `.loc` slice) caused the main spillover path to silently fall back
  to a correlation-based approximation. All four fixed; main path now produces
  correct diebold-yilmaz spillover indices.
- `pyproject.toml`: pytest/pytest-cov upper bounds widened to match the locked
  versions that dependabot already resolved.

### Changed

- Repository renamed from `FinAI-Research-Workflow` to `finai-research`. Old URL
  permanently 301-redirects to new URL. PyPI package name `finai-research-workflow`
  is intentionally unchanged to preserve `pip install` ergonomics.

### Known Limitations

- All LLM-generated outputs (papers, reviews, design docs) **require human
  verification before submission**. Hallucinated citations and inappropriate
  statistical claims are possible.
- Windows is a secondary platform; macOS and Ubuntu are primary tested targets.