"""data_warning_notifier.py
=========================

Non-blocking, deduplicated warning emitter for silent-fallback data paths
(audit_fix_2026-07-12 T13).

Background
----------
Five ``research_directions/*.py`` modules historically swallowed exceptions
in their data-acquisition paths and returned ``{"status": "error",
"tables": {}, "error": "..."}`` to the caller. Callers (and downstream
report generators) treated that return value as if it were a real result
and silently produced "empty-table" drafts. This is an academic-integrity
risk: the user might submit a paper built on zero observations, never
realizing the pipeline failed.

This module provides a single, lightweight entry point — ``warn()`` — that
prints a visible ``⚠️`` warning and appends a structured record to a local
JSONL audit log (``data_warnings.jsonl``) so operators can audit which
research directions produced silent fallbacks during a run.

Design parallels ``scripts/core/paid_source_notifier.py``:

  - Non-blocking (no ``raise``, no ``sys.exit``).
  - Process-level deduplication: each ``(category, source)`` pair is
    warned at most once per process.
  - Suppression: ``FINAI_SUPPRESS_DATA_WARNINGS=1`` silences all output.
  - Configurable log path: ``FINAI_DATA_WARN_LOG=/path/to/file.jsonl``.
  - Thread-safe (locks the dedup set so concurrent pipeline stages don't
    each emit the same warning).

Usage
-----

.. code-block:: python

    from scripts.core.data_warning_notifier import warn
    try:
        df = fetch(...)
    except Exception as exc:                       # noqa: BLE001
        warn(
            category="research_direction",
            source="behavioral_finance",
            reason=f"Statsmodels import failed: {exc}",
        )
        return {"status": "import_error", "tables": {}, "error": str(exc)}

The ``warn()`` call must happen **before** the existing ``return`` so that
the warning still fires when the function returns its fallback payload.
Adding the call is a pure-visibility upgrade — behavior is unchanged.

CLI
---
``FINAI_SUPPRESS_DATA_WARNINGS=1``    silence warnings (CI batch runs)
``FINAI_DATA_WARN_LOG=<path>``        redirect JSONL audit log
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
_LOG_PATH = Path(
    os.environ.get(
        "FINAI_DATA_WARN_LOG",
        str(_PROJECT_ROOT / "data_warnings.jsonl"),
    )
)
_SUPPRESSED = os.environ.get("FINAI_SUPPRESS_DATA_WARNINGS") == "1"


@dataclass(frozen=True)
class DataWarning:
    """A single silent-fallback warning record."""

    category: str        # e.g. "research_direction"
    source: str          # e.g. "behavioral_finance"
    reason: str          # human-readable explanation
    ts: float = field(default_factory=time.time)
    site: Optional[str] = None  # caller-provided call-site for diagnostics


class DataWarningNotifier:
    """Process-level singleton that records silent-fallback warnings.

    A warning is emitted at most once per ``(category, source)`` pair per
    process. The ``stats()`` helper exposes the dedup set for downstream
    health-check reporting.
    """

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()
        self._lock = threading.Lock()
        self._disabled: bool = False

    def configure(self, *, disabled: bool = False) -> None:
        """Process-level toggle. ``disabled=True`` silences all warnings."""
        with self._lock:
            self._disabled = disabled

    def warn(
        self,
        category: str,
        source: str,
        reason: str,
        site: Optional[str] = None,
    ) -> bool:
        """Emit a single dedup warning. Returns True if it fired.

        Side effects (non-blocking):
          - Prints a ⚠️ block to stderr (deduplicated per process).
          - Appends a JSONL line to ``data_warnings.jsonl``.

        Never raises — all I/O failures are swallowed so callers can
        safely invoke this from inside their ``except`` branches.
        """
        # Suppression gates
        if self._disabled or _SUPPRESSED:
            return False

        # Dedup within process
        dedup_key = (category, source)
        with self._lock:
            if dedup_key in self._seen:
                return False
            self._seen.add(dedup_key)

        # ── Build message ──────────────────────────────────────────────
        msg = _format_warning(category, source, reason, site)

        # ── Print to stderr (visible by default; suppressed in CI) ─────
        try:
            print(msg, file=sys.stderr, flush=True)
        except Exception:
            pass  # printing must not break pipeline

        # ── Append to JSONL audit log ──────────────────────────────────
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": time.time(),
                            "category": category,
                            "source": source,
                            "reason": reason,
                            "site": site,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception:
            pass  # log failures must not break pipeline

        return True

    def stats(self) -> dict:
        """Return counts of unique (category, source) pairs warned."""
        with self._lock:
            seen_list = sorted(self._seen)
            return {
                "unique_warnings": len(self._seen),
                "warnings": [
                    {"category": c, "source": s} for (c, s) in seen_list
                ],
            }


def _format_warning(
    category: str,
    source: str,
    reason: str,
    site: Optional[str],
) -> str:
    """Format the human-readable warning text."""
    lines = [
        "",
        "━" * 64,
        f"⚠️  数据静默回退 (silent fallback): {category} / {source}",
        "━" * 64,
        "  说明: 该研究方向的回归/数据获取失败, 已返回 status=error/no_data/import_error,",
        "        tables={}. 调用方应当识别这种返回值并提示用户, 而非继续当作成功处理.",
        f"  原因: {reason}",
    ]
    if site:
        lines.append(f"  调用点: {site}")
    lines.extend(
        [
            "  后果: 继续用空表渲染 LaTeX 会得到内容为空的论文草稿, 涉嫌科研诚信风险.",
            "  建议: 检查 MCP 数据源连通性、依赖包安装情况、或更换研究主题.",
            "  关闭: FINAI_SUPPRESS_DATA_WARNINGS=1 (用于 CI 批处理)",
            "━" * 64,
        ]
    )
    return "\n".join(lines)


# ─── 进程级单例 ──────────────────────────────────────────────────────────────
data_notifier = DataWarningNotifier()


# ─── 便捷函数 (供 caller 调用) ──────────────────────────────────────────────


def warn(
    category: str,
    source: str,
    reason: str,
    site: Optional[str] = None,
) -> bool:
    """Module-level convenience wrapper around :py:meth:`DataWarningNotifier.warn`.

    Kept as a top-level function so callers can do::

        from scripts.core.data_warning_notifier import warn
        warn("research_direction", "behavioral_finance", "statsmodels missing")

    without reaching into the singleton.
    """
    return data_notifier.warn(category=category, source=source, reason=reason, site=site)


__all__ = [
    "DataWarning",
    "DataWarningNotifier",
    "data_notifier",
    "warn",
]
