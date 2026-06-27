"""Tests for scripts/count_assets.py (P0-A auto-generated metrics, 2026-06-27)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "count_assets.py"


def test_script_runs():
    """脚本必须能运行（不依赖 MCP/LLM）。"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=10,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    assert "MCP server directories:" in result.stdout


def test_script_json_output():
    """--json 必须输出合法 JSON。"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        capture_output=True, text=True, timeout=10,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "mcp_servers" in data
    assert "econometric_methods" in data
    assert "tests" in data
    assert data["mcp_servers"]["total"] >= 40, "MCP 数量应≥40"
    assert data["tests"]["test_functions"] >= 200, "测试函数数应≥200"


def test_script_markdown_output():
    """--markdown 必须输出 README 友好格式。"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--markdown"],
        capture_output=True, text=True, timeout=10,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0
    md = result.stdout
    assert "| Metric | Count |" in md
    assert "MCP server directories" in md
    assert "Econometric method modules" in md


def test_mcp_count_consistent():
    """MCP 目录数应与文件系统一致。"""
    from scripts.count_assets import count_mcp_servers
    stats = count_mcp_servers()
    actual = sum(1 for d in (PROJECT_ROOT / "mcp_servers").iterdir()
                 if d.is_dir() and d.name.startswith("user_"))
    assert stats["total"] == actual, (
        f"count_assets 报告 {stats['total']} 个，但 mcp_servers/ 实际有 {actual} 个"
    )


def test_test_function_count_consistent():
    """test_ 函数数应与 grep 一致。"""
    from scripts.count_assets import count_test_files
    import re
    stats = count_test_files()
    actual = 0
    for tf in (PROJECT_ROOT / "tests").glob("test_*.py"):
        actual += len(re.findall(r"^def test_", tf.read_text(), re.MULTILINE))
    assert stats["test_functions"] == actual, (
        f"count_assets 报告 {stats['test_functions']} 个 test_，"
        f"实际 grep 找到 {actual} 个"
    )


def test_econometric_methods_count():
    """计量方法模块数应≥40（项目声明 30+ 种）。"""
    from scripts.count_assets import count_econometric_methods
    n = count_econometric_methods()
    assert n >= 40, f"仅发现 {n} 个方法模块，预期 ≥40"
