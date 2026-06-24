"""mcp_servers — FastMCP data server package.

Each subpackage is a self-contained MCP server (FastMCP 2.x):
    user_eastmoney_reports/  — 东方财富研报/新闻/分析师排名
    user_eastmoney_fund/     — 基金数据（净值/持仓/业绩）
    user_eastmoney_bond/     — 债券数据（收益率曲线/现券/回购）
    user_eastmoney_option/   — 期权数据（希腊值/波动率/链）
    user_financial/          — 全球宏观数据（WB API / akshare，无需 Key）
    user_enhanced_finance/   — 外汇/航运指数/白银/期货
    user_tushare/            — A股行情/财务（需 TUSHARE_TOKEN）
    user_yfinance/            — 美股/港股/ETF/期权（无需 Key）
    user_wb_data/            — 世界银行指标（无需 Key）
    user_imf_data/           — IMF 世界经济展望（无需 Key）
    user_oecd_data/          — OECD 经济数据（无需 Key）
    user_fed_data/           — 美联储/FOMC/褐皮书（无需 Key）
    user_eodhd/             — 美国国债/经济日历（需 EODHD_API_KEY）
    user_bea_data/          — 美国经济分析局 GDP
    user_sec_edgar/          — SEC 10-K/10-Q/8-K（无需 Key）
    user_context7/           — 学术论文全文（无需 Key）
    user_openalex/           — 学术元数据 2亿+（无需 Key）
    user_arxiv/              — ArXiv 预印本（无需 Key）
    user_semantic_scholar/  — Semantic Scholar（可选 Key）
    user_nber_wp/            — NBER 工作论文（无需 Key）
    user_cnki/               — CNKI 中国知网（需机构账号）
    user_wanfang/           — 万方数据（需机构账号）
    user_chinese_literature/ — 中国文学/古籍
    user_chinese_customs/   — 中国海关数据（需机构账号）
    user_csmar/             — CSMAR 国泰安（需机构账号）
    user_wind/               — Wind 万得（需 Wind 账号）
    user_sipo/               — 中国专利数据（无需 Key）
    user_cnrd/               — 中国知网/万方研报
    user_province_stats/     — 中国省级统计（无需 Key）
    user_hubei_stats/        — 湖北省统计（无需 Key）
    user_wuhan_stats/        — 武汉市统计（无需 Key）
    user_macro_ceic/         — CEIC 全球经济（需 Key）
    user_macro_stats/         — 宏观面板数据
    user_macro_datas/        — 宏观面板（教育/R&D/科技）
    user_brave_search/       — 网页搜索（需 BRAVE_SEARCH_API_KEY）
    user_newsapi/            — 财经新闻（需 NEWSAPI_API_KEY）
    user_cryptocompare/       — 加密货币 BTC/ETH（无需 Key）
    user_e2b_mcp/            — E2B 云端代码执行（需 E2B_API_KEY）
    user_latex_mcp/          — LaTeX 排版检查
    user_pandas_mcp/          — pandas 数据处理
    user_filesystem_mcp/     — 文件系统操作
    user_playwright_mcp/     — Playwright 浏览器自动化
    user_third_party_esg/    — ESG 第三方数据

⚠️ Cost badges: ✅ Free (no key) · ⚠️ Limited (free tier available) · 💰 Paid (institutional/personal paid account required)
See MCP Tool Marketplace docs/tutorials/04-mcp-marketplace.md for the complete catalog.

Each server exposes a `mcp` FastMCP instance that can be run directly:
    python -m mcp_servers.user_eastmoney_reports.server

Or via docker-compose (see docker-compose.yml).
"""

from __future__ import annotations

import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Audit fix 2026-06-24: complete and deduplicated list ──────────────────────
# All 43 server IDs present in mcp_servers/ directory.
# Previously had duplicate entries (user_financial, user_enhanced_finance)
# and was missing 14 servers (user_arxiv, user_brave_search, etc.).
AVAILABLE_SERVERS: list[str] = [
    # ── 中国市场 ───────────────────────────────────────────────────────
    "user_tushare",           # A股行情/财务（需 TUSHARE_TOKEN）
    "user_csmar",             # CSMAR 国泰安（需机构账号）
    "user_wind",               # Wind 万得（需 Wind 账号）
    "user_cnki",               # CNKI 中国知网（需机构账号）
    "user_wanfang",           # 万方数据（需机构账号）
    "user_chinese_literature", # 中国文学/古籍
    "user_chinese_customs",    # 中国海关数据（需机构账号）
    "user_cnrd",               # CNKI/万方研报聚合
    "user_sipo",               # 中国专利数据（无需 Key）
    "user_province_stats",     # 中国省级统计（无需 Key）
    "user_hubei_stats",        # 湖北省统计（无需 Key）
    "user_wuhan_stats",        # 武汉市统计（无需 Key）
    # ── 美股 / 全球市场 ───────────────────────────────────────────────
    "user_yfinance",           # 美股/港股/ETF/期权（无需 Key）
    "user_sec_edgar",          # SEC 10-K/10-Q/8-K（无需 Key）
    "user_cryptocompare",      # 加密货币 BTC/ETH（无需 Key）
    "user_eastmoney_reports",  # 东方财富研报/新闻/分析师（无需 Key）
    "user_eastmoney_fund",     # 公募基金（无需 Key）
    "user_eastmoney_bond",     # 债券数据（无需 Key）
    "user_eastmoney_option",   # 期权数据（无需 Key）
    # ── 宏观经济 ──────────────────────────────────────────────────────
    "user_financial",          # 全球宏观（WB API / akshare，无需 Key）
    "user_enhanced_finance",   # 外汇/航运指数/白银/期货（无需 Key）
    "user_wb_data",           # 世界银行指标（无需 Key）
    "user_imf_data",          # IMF 世界经济展望（无需 Key）
    "user_oecd_data",         # OECD 经济数据（无需 Key）
    "user_fed_data",          # 美联储/FOMC（无需 Key）
    "user_eodhd",            # 美国国债/经济日历（需 EODHD_API_KEY）
    "user_bea_data",          # 美国经济分析局 GDP（无需 Key）
    "user_macro_ceic",        # CEIC 全球经济（需 Key）
    "user_macro_stats",        # 宏观面板数据
    "user_macro_datas",        # 宏观面板（教育/R&D/科技）
    # ── 学术文献 ──────────────────────────────────────────────────────
    "user_context7",          # 学术论文全文（无需 Key）
    "user_openalex",          # 学术元数据 2亿+（无需 Key）
    "user_arxiv",             # ArXiv 预印本（无需 Key）
    "user_semantic_scholar",  # Semantic Scholar（可选 Key）
    "user_nber_wp",           # NBER 工作论文（无需 Key）
    # ── 搜索 / 新闻 ──────────────────────────────────────────────────
    "user_brave_search",      # 网页搜索（需 BRAVE_SEARCH_API_KEY）
    "user_newsapi",          # 财经新闻（需 NEWSAPI_API_KEY）
    # ── 工具类 ───────────────────────────────────────────────────────
    "user_e2b_mcp",          # E2B 云端代码执行（需 E2B_API_KEY）
    "user_latex_mcp",         # LaTeX 排版检查
    "user_pandas_mcp",        # pandas 数据处理
    "user_filesystem_mcp",   # 文件系统操作
    "user_playwright_mcp",    # Playwright 浏览器自动化
    "user_third_party_esg",   # ESG 第三方数据
]

# Deduplication guard: ensure no accidental duplicate entries
assert len(AVAILABLE_SERVERS) == len(set(AVAILABLE_SERVERS)), \
    "Duplicate entries in AVAILABLE_SERVERS!"


def get_server_path(server_name: str) -> Path:
    """Get the directory path for a server."""
    return Path(__file__).parent / server_name


def list_available_servers() -> list[str]:
    """Return list of server IDs that have a server.py file."""
    available = []
    for name in AVAILABLE_SERVERS:
        server_file = get_server_path(name) / "server.py"
        if server_file.exists():
            available.append(name)
    return available


__all__ = [
    "AVAILABLE_SERVERS",
    "get_server_path",
    "list_available_servers",
]
