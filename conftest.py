"""
Root conftest.py — ensure project root is on sys.path for all pytest
test collection, regardless of pytest-xdist worker subprocess behavior.

audit-2026-07-04 PR-2 follow-up: the previous batch architecture
implicitly avoided this issue by using explicit test lists per job.
Unifying into 'pytest tests/' exposes that the only sys.path injection
came from tests/conftest.py, which pytest-xdist worker subprocesses
may run after some module imports have already been attempted.

This root conftest runs before any test module is imported, so the
sys.path insertion is guaranteed to take effect for the entire
collection phase.
"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.resolve()
print(f"[conftest] project_root={_PROJECT_ROOT}", file=sys.stderr)
print(f"[conftest] sys.path:", file=sys.stderr)
for p in sys.path:
    print(f"  {p}", file=sys.stderr)
print(f"[conftest] scripts package dir exists: {(_PROJECT_ROOT / 'scripts').exists()}", file=sys.stderr)
print(f"[conftest] scripts/core dir exists: {(_PROJECT_ROOT / 'scripts' / 'core').exists()}", file=sys.stderr)
print(f"[conftest] scripts/core/debate_arena.py exists: {(_PROJECT_ROOT / 'scripts' / 'core' / 'debate_arena.py').exists()}", file=sys.stderr)
print(f"[conftest] scripts/core/__init__.py exists: {(_PROJECT_ROOT / 'scripts' / 'core' / '__init__.py').exists()}", file=sys.stderr)
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
    print(f"[conftest] inserted {_PROJECT_ROOT}", file=sys.stderr)
print(f"[conftest] scripts.core.debate_arena importable: ", end="", file=sys.stderr)
try:
    import scripts.core.debate_arena  # noqa: F401
    print("YES", file=sys.stderr)
except Exception as e:
    print(f"NO ({e})", file=sys.stderr)
# Try importlib
print(f"[conftest] importlib.util.find_spec('scripts.core.debate_arena'):", file=sys.stderr)
import importlib.util
spec = importlib.util.find_spec('scripts.core.debate_arena')
print(f"  spec={spec}", file=sys.stderr)