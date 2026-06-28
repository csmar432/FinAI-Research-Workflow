"""Tests for scripts/count_assets.py"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_script_runs():
    """count_assets.py 至少能跑一次。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "count_assets.py")],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0


def test_script_json_output():
    """--json 输出含测试数。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "count_assets.py"), "--json"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "tests" in data
    assert data["tests"]["files"] >= 100
    assert data["tests"]["test_functions"] >= 200, "测试函数数应≥200"


def test_script_markdown_output():
    """--markdown 输出含 Markdown 表格。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "count_assets.py"), "--markdown"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    assert "| Test files" in result.stdout


def test_mcp_count_consistent():
    """MCP 服务器计数应与实际目录数一致。"""
    from scripts.count_assets import count_mcp_servers
    stats = count_mcp_servers()
    actual = sum(1 for _ in (PROJECT_ROOT / "mcp_servers").glob("user_*"))
    assert stats["total"] == actual


def test_test_function_count_consistent():
    """test_ 函数数应与 grep 一致（P0 修复 2026-06-28: 同时数 module-level 和 class 内方法）。"""
    from scripts.count_assets import count_test_files

    stats = count_test_files()
    actual = 0
    func_pattern = re.compile(r"^\s+(?:async\s+)?def test_", re.MULTILINE)
    module_pattern = re.compile(r"^(?:async\s+)?def test_", re.MULTILINE)
    class_pattern = re.compile(r"^class\s+Test\w+", re.MULTILINE)
    for tf in (PROJECT_ROOT / "tests").glob("test_*.py"):
        text = tf.read_text()
        actual += len(module_pattern.findall(text))
        for m in class_pattern.finditer(text):
            class_start = m.end()
            next_class = class_pattern.search(text, class_start)
            class_end = next_class.start() if next_class else len(text)
            actual += len(func_pattern.findall(text[class_start:class_end]))
    assert stats["test_functions"] == actual, (
        f"count_assets 报告 {stats['test_functions']} 个 test_，"
        f"实际 grep 找到 {actual} 个"
    )


def test_econometric_methods_count():
    """计量方法模块数应≥40（项目声明 30+ 种）。"""
    from scripts.count_assets import count_econometric_methods
    n = count_econometric_methods()
    assert n >= 40, f"仅发现 {n} 个方法模块，预期 ≥40"
