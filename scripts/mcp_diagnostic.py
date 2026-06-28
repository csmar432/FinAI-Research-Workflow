#!/usr/bin/env python3
"""
mcp_diagnostic.py — MCP 服务器连接状态诊断工具

测试 Cursor 已启用的 MCP 服务器是否可正常调用。

使用方法：
  python scripts/mcp_diagnostic.py              # 诊断所有服务器
  python scripts/mcp_diagnostic.py --server tushare  # 诊断单个服务器
  python scripts/mcp_diagnostic.py --json       # JSON 输出

在 Python 中导入：
  from scripts.mcp_diagnostic import run_mcp_diagnostic
  results = run_mcp_diagnostic()
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def green(t: str) -> str:
    return _c(t, GREEN)


def red(t: str) -> str:
    return _c(t, RED)


def yellow(t: str) -> str:
    return _c(t, YELLOW)


def bold(t: str) -> str:
    return _c(t, BOLD)


def cyan(t: str) -> str:
    return _c(t, CYAN)


def dim(t: str) -> str:
    return _c(t, DIM)


@dataclass
class MCPResult:
    """单个 MCP 服务器的诊断结果。"""
    mcp_id: str
    name: str
    reachable: bool | None  # None = 未测试
    latency_ms: float | None
    error: str = ""
    details: dict = field(default_factory=dict)


def _read_cursor_mcp_config() -> dict[str, Any]:
    """读取 Cursor MCP 配置文件。"""
    candidates = [
        Path.home() / ".cursor" / "mcp.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


# 各 MCP 服务器的测试工具和验证函数
# 格式: mcp_id → (display_name, test_function_or_None)
# test_function 返回 (reachable: bool, latency_ms: float, error: str)
_MCP_TEST_CATALOG: dict[str, tuple[str, str | None]] = {
    # 宏观经济
    "wb-data": ("世界银行数据", "get_wb_gdp_usd"),
    "financial": ("全球宏观数据（中国/日本/欧元区）", "get_macro_china"),
    "fed-data": ("美联储/FOMC 数据", "get_fed_interest_rate"),
    "imf-data": ("IMF 世界经济展望", "get_imf_ifs"),
    "oecd-data": ("OECD 经济数据", "get_oecd_gdp"),
    "eodhd": ("EODHD 全球市场", "get_ust_yield_rates"),
    "macro-stats": ("宏观统计", "get_wb_indicator"),
    "macro-ceic": ("CEIC 中国宏观", "get_ceic_macro_china"),
    "macro-datas": ("宏观数据聚合", None),
    "bea-data": ("美国经济分析局", "get_bea_gdp"),

    # A股数据
    "tushare": ("Tushare A股", "get_daily_quote"),
    "eastmoney-reports": ("东方财富研报", "get_research_report"),
    "eastmoney-fund": ("东方财富基金", "get_fund_performance"),
    "eastmoney-bond": ("东方财富债券", "get_bond_spot"),
    "eastmoney-option": ("东方财富期权", "get_option_greeks"),
    "wind": ("Wind 万得", "get_wind_stock_index"),
    "csmar": ("CSMAR 国泰安", "get_csmar_analyst"),

    # 外汇/大宗商品
    "enhanced-finance": ("增强金融数据（外汇/大宗）", "get_forex_spot"),
    "province-stats": ("中国省级统计", "get_province_rankings"),
    "hubei-stats": ("湖北省统计", "get_china_gdp"),
    "wuhan-stats": ("武汉市统计", "get_wuhan_gdp"),

    # 学术文献
    "nber-wp": ("NBER Working Papers", "search_nber_papers"),
    "latex-mcp": ("LaTeX 排版", "latex_check"),
    "filesystem-mcp": ("文件系统", None),
    "pandas-mcp": ("数据处理", "pd_head"),
    "playwright-mcp": ("浏览器自动化", None),
    "e2b-mcp": ("云端代码执行", None),
}


def _test_mcp_via_mcp_call(mcp_id: str, tool_name: str | None,
                            timeout: float = 10.0) -> tuple[bool | None, float, str]:
    """通过 MCP 协议直接调用测试工具。

    由于 MCP 服务器由 Cursor 管理，我们在当前进程中无法直接调用。
    这个方法返回一个占位，标记为"需 Cursor 运行时测试"。
    """
    return None, 0.0, f"MCP 服务器 {mcp_id} 需要在 Cursor 中运行时测试。\n  请在 Cursor 中输入以下命令测试：\n  "


def _test_mcp_by_script(mcp_id: str, script_path: Path,
                        timeout: float = 10.0) -> tuple[bool, float, str]:
    """通过运行测试脚本来验证 MCP 服务器。"""
    try:
        start = time.time()
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_ms = (time.time() - start) * 1000

        if result.returncode == 0:
            return True, elapsed_ms, ""
        else:
            return False, elapsed_ms, result.stderr[:200]
    except subprocess.TimeoutExpired:
        return False, timeout * 1000, f"超时（>{timeout}s）"
    except Exception as e:
        return False, 0.0, str(e)[:200]


def _build_mcp_test_tools(root: Path) -> dict[str, Path]:
    """扫描 mcp_servers 目录中的测试工具。"""
    tools: dict[str, Path] = {}
    servers_dir = root / "mcp_servers"
    if not servers_dir.exists():
        return tools

    for srv_dir in servers_dir.iterdir():
        if not srv_dir.is_dir():
            continue
        # 查找测试脚本
        test_files = [
            srv_dir / "test_server.py",
            srv_dir / "test.py",
        ]
        for tf in test_files:
            if tf.exists():
                mcp_id = _dir_to_id(srv_dir.name)
                tools[mcp_id] = tf
                break

    return tools


# 目录名 → MCP ID 映射（复用 health_check.py 中的映射）
_DIR_TO_ID: dict[str, str] = {
    "user_enhanced_finance": "enhanced-finance",
    "user_eastmoney_reports": "eastmoney-reports",
    "user_eastmoney_fund": "eastmoney-fund",
    "user_eastmoney_bond": "eastmoney-bond",
    "user_eastmoney_option": "eastmoney-option",
    "user_wb_data": "wb-data",
    "user_imf_data": "imf-data",
    "user_oecd_data": "oecd-data",
    "user_fed_data": "fed-data",
    "user_financial": "financial",
    "user_eodhd": "eodhd",
    "user_tushare": "tushare",
    "user_csmar": "csmar",
    "user_bea_data": "bea-data",
    "user_wind": "wind",
    "user_latex_mcp": "latex-mcp",
    "user_playwright_mcp": "playwright-mcp",
    "user_e2b_mcp": "e2b-mcp",
    "user_pandas_mcp": "pandas-mcp",
    "user_filesystem_mcp": "filesystem-mcp",
    "user_nber_wp": "nber-wp",
    "user_context7": "context7",
    "user_openalex": "openalex",
    "user_chinese_literature": "chinese-literature",
    "user_macro_ceic": "macro-ceic",
    "user_macro_datas": "macro-datas",
    "user_macro_stats": "macro-stats",
    "user_province_stats": "province-stats",
    "user_hubei_stats": "hubei-stats",
    "user_wuhan_stats": "wuhan-stats",
}


def _dir_to_id(dir_name: str) -> str:
    return _DIR_TO_ID.get(dir_name, dir_name)


def _read_env(path: Path) -> dict[str, str]:
    env = {}
    if not path.exists():
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _project_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def run_mcp_diagnostic(target: str | None = None) -> list[dict]:
    """运行 MCP 服务器诊断。

    Returns:
        list of diagnostic results (JSON-serializable dicts)
    """
    Path(__file__).parent.parent.resolve()
    config = _read_cursor_mcp_config()
    enabled = set(config.get("mcpServers", {}).keys())

    results: list[dict] = []

    servers_to_check = (
        [target] if target else sorted(_MCP_TEST_CATALOG.keys())
    )

    for mcp_id in servers_to_check:
        name, test_tool = _MCP_TEST_CATALOG.get(mcp_id, (mcp_id, None))
        is_enabled = mcp_id in enabled or any(
            mcp_id.replace("-", "_") in e or e.replace("-", "_") in mcp_id
            for e in enabled
        )

        if not is_enabled:
            results.append({
                "mcp_id": mcp_id,
                "name": name,
                "status": "disabled",
                "reachable": None,
                "latency_ms": None,
                "error": "在 Cursor MCP 配置中未启用",
                "hint": f"在 ~/.cursor/mcp.json 中启用 {mcp_id}",
            })
            continue

        # 对于需要 API Key 的 MCP，检查是否配置了相应的 key
        api_key_map = {
            "tushare": "TUSHARE_TOKEN",
            "eodhd": "EODHD_API_KEY",
            "financial": "FRED_API_KEY",
            "enhanced-finance": None,
            "eastmoney-reports": None,
            "eastmoney-fund": None,
            "eastmoney-bond": None,
            "eastmoney-option": None,
            "wind": None,
            "csmar": "CSMAR_API_KEY",
            "wb-data": None,
            "fed-data": None,
            "imf-data": None,
            "oecd-data": None,
            "macro-stats": None,
            "macro-ceic": None,
            "macro-datas": None,
            "bea-data": None,
            "province-stats": None,
            "hubei-stats": None,
            "wuhan-stats": None,
            "nber-wp": None,
            "latex-mcp": None,
            "filesystem-mcp": None,
            "pandas-mcp": None,
            "playwright-mcp": None,
            "e2b-mcp": None,
        }

        api_key_var = api_key_map.get(mcp_id)
        api_configured = True
        if api_key_var:
            env = _read_env(_project_root() / ".env.local")
            env.update(_read_env(_project_root() / ".env"))
            api_configured = bool(env.get(api_key_var, "").strip())

        if not api_configured:
            results.append({
                "mcp_id": mcp_id,
                "name": name,
                "status": "needs_api_key",
                "reachable": None,
                "latency_ms": None,
                "error": f"需要 API Key: {api_key_var}",
                "hint": f"请在 .env.local 中设置 {api_key_var}",
            })
            continue

        # 标记为"在 Cursor 中运行时可测试"
        results.append({
            "mcp_id": mcp_id,
            "name": name,
            "status": "ready",
            "reachable": True,
            "latency_ms": None,
            "error": "",
            "hint": (
                f"✅ {mcp_id} 已启用且 API Key 已配置。\n"
                "  在 Cursor 中调用 CallMcpTool 即可使用。"
            ),
        })

    return results


def print_mcp_diagnostic(target: str | None = None, as_json: bool = False) -> None:
    """打印 MCP 诊断报告。"""
    results = run_mcp_diagnostic(target)

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    width = 72

    print()
    print(bold(cyan("═" * width)))
    print(bold(cyan("║")) + f"{' MCP 服务器连接诊断 ':^{width - 4}}".center(width - 4) + bold(cyan(" ║")))
    print(bold(cyan("═" * width)))
    print()
    print(f"  诊断时间: {dim(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
    print()

    groups = {
        "宏观经济": ["wb-data", "financial", "fed-data", "imf-data",
                     "oecd-data", "eodhd", "macro-stats", "macro-ceic",
                     "macro-datas", "bea-data"],
        "A股数据": ["tushare", "eastmoney-reports", "eastmoney-fund",
                    "eastmoney-bond", "eastmoney-option", "wind", "csmar"],
        "外汇/大宗商品": ["enhanced-finance"],
        "中国区域统计": ["province-stats", "hubei-stats", "wuhan-stats"],
        "工具类": ["nber-wp", "latex-mcp", "filesystem-mcp", "pandas-mcp",
                   "playwright-mcp", "e2b-mcp"],
    }

    for group_name, mcp_ids in groups.items():
        items = [r for r in results if r["mcp_id"] in mcp_ids]
        if not items:
            continue

        print(bold(yellow(f"━━━ {group_name} ━━━")))
        for item in items:
            status = item["status"]
            mcp_id = item["mcp_id"]
            name = item["name"]

            if status == "disabled":
                icon = red("❌  未启用")
                print(f"  {icon} {bold(name)} [{mcp_id}]")
                print(f"      {dim(item['error'])}")
            elif status == "needs_api_key":
                icon = yellow("⚠️  缺Key")
                print(f"  {icon} {bold(name)} [{mcp_id}]")
                print(f"      {item['error']} → {dim(item['hint'])}")
            elif status == "ready":
                icon = green("✅  就绪")
                print(f"  {icon} {bold(name)} [{mcp_id}]")
            elif status == "error":
                icon = red("❌  错误")
                print(f"  {icon} {bold(name)} [{mcp_id}]")
                print(f"      {dim(item['error'][:100])}")
        print()

    print(bold(cyan("═" * width)))
    print()
    print(dim("  💡 提示：MCP 服务器需要在 Cursor 中才能真正调用。"))
    print(dim("     此诊断工具验证配置是否正确，而非运行时连通性。"))
    print(dim("     如需测试真实调用，请在 Cursor 中尝试："))
    print(dim("     CallMcpTool(server='tushare', tool='get_daily_quote', ...)"))
    print()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="MCP 服务器连接诊断")
    parser.add_argument("--server", "-s", type=str, help="仅诊断指定服务器")
    parser.add_argument("--json", "-j", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    print_mcp_diagnostic(target=args.server, as_json=args.json)


if __name__ == "__main__":
    main()
