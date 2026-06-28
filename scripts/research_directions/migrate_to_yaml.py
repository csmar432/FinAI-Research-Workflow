"""Migrate research_directions/__init__.py dataclass literals to directions.yaml.

P0-6 修复 2026-06-28: 此脚本把 __init__.py 中的 2,300+ 行 dataclass 字面量
迁移到 directions.yaml，让 _init_registry 可以改为 _load_from_yaml 调用，
显著加快 import 速度（~5.9s → <0.5s）。

Usage:
    python scripts/research_directions/migrate_to_yaml.py [--dry-run]

Options:
    --dry-run   不写入文件，只打印统计信息
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写入")
    args = parser.parse_args()

    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.research_directions import DirectionFactory  # noqa: E402

    # 强制初始化（如果还没初始化）
    if not DirectionFactory._initialized:
        DirectionFactory._init_registry()

    n = len(DirectionFactory._registry)
    yaml_path = PROJECT_ROOT / "scripts" / "research_directions" / "directions.yaml"

    if args.dry_run:
        print(f"[dry-run] Would export {n} directions to {yaml_path}")
        return 0

    DirectionFactory._export_yaml(yaml_path)
    print(f"✅ Exported {n} directions to {yaml_path}")
    print(f"   Next step: change DirectionFactory._init_registry() to call _load_from_yaml()")
    return 0


if __name__ == "__main__":
    sys.exit(main())
