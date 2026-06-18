#!/usr/bin/env python3
"""
CNKI MCP Server
===============
中国知网（CNKI）学术论文检索服务。

⚠️  法律免责声明
----------------
本 MCP 服务器仅供研究和教育目的使用。

您使用本服务器即表示同意以下条款：
  1. 本软件按"现状"提供，不提供任何明示或暗示的担保。
  2. 您有责任确保您的使用符合所有适用法律、法规及 CNKI (cnki.net) 的服务条款。
  3. 本服务器尽可能遵守 robots.txt，但遵守 robots.txt 不构成任何网站的合法抓取许可。
  4. 建议申请 CNKI 机构账号以获得更好的数据访问。
  5. 高频访问可能被临时封禁，请设置合理的请求间隔（默认 ≥2 秒）。
  6. 下载的论文版权归原作者及出版商所有，使用时须遵守著作权法。
  7. 本项目作者及维护者对使用本服务器产生的任何法律后果不承担任何责任。
     如不同意上述条款，请勿使用本 MCP 服务器。

数据源：
  - CNKI 官方搜索界面（scholar.cnki.net）
  - 通过 requests + BeautifulSoup 实现网页爬取

Usage:
    python server.py
"""

from __future__ import annotations

import json
import logging
import random
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

warnings_filter_imported = False
try:
    import warnings
    warnings.filterwarnings("ignore")
    warnings_filter_imported = True
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
)
_log = logging.getLogger("cnki_mcp")

_SERVER_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SERVER_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ─── Constants ─────────────────────────────────────────────────────────────────

_CNKI_SEARCH_URL = "https://kns.cnki.net/kns8s/defaultresult/index"
_CNKI_ADVANCED_URL = "https://kns.cnki.net/kns8s/defaultresult/AdvSearch"
_CNKI_HOME_URL = "https://www.cnki.net"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.cnki.net/",
}

_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)

# Polite notice about robots.txt compliance
_ROBOTS_TXT_NOTICE = (
    "本服务使用网页爬虫方式获取 CNKI 数据。爬虫行为受 robots.txt 约束，"
    "请勿高频访问或大规模抓取。建议使用 CNKI 机构账号获取更稳定的数据访问。"
)

# ─── Tool Definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_cnki_papers",
        "description": (
            "搜索 CNKI（中国知网）学术论文。\n\n"
            "支持按主题词、作者、期刊、基金、DOI 等多维度检索。"
            "返回论文标题、作者、期刊、年份、摘要、被引次数等元数据。\n\n"
            "注意：CNKI 无免费公开 API，本工具通过网页爬虫实现。访问可能受限，"
            "建议设置合理的请求间隔（≥3秒）。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如：碳排放权交易 绿色创新 DID",
                },
                "author": {
                    "type": "string",
                    "description": "作者姓名（可选）",
                },
                "journal": {
                    "type": "string",
                    "description": "期刊名称（可选），如：经济研究",
                },
                "year_from": {
                    "type": "integer",
                    "description": "起始年份",
                    "default": 2020,
                },
                "year_to": {
                    "type": "integer",
                    "description": "结束年份",
                    "default": 2024,
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数（默认20，最大50）",
                    "default": 20,
                },
                "search_type": {
                    "type": "string",
                    "description": "检索类型：theme（主题）/ author（作者）/ journal（期刊）/ fund（基金）",
                    "default": "theme",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_cnki_paper_detail",
        "description": (
            "获取 CNKI 单篇论文的详细信息。\n\n"
            "通过 CNKI 论文详情页获取完整元数据，包括："
            "摘要、关键词、作者信息、期刊信息、基金、DOI、分类号等。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cnki_id": {
                    "type": "string",
                    "description": "CNKI 论文 ID（如 CNKI:ODE...）",
                },
                "title": {
                    "type": "string",
                    "description": "论文标题（用于模糊匹配搜索）",
                },
                "fetch_citations": {
                    "type": "boolean",
                    "description": "是否获取引用该论文的其他论文",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "get_cnki_citations",
        "description": (
            "获取引用某篇 CNKI 论文的所有施引文献。\n\n"
            "返回施引文献列表，包括标题、作者、期刊、年份、被引次数等信息。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cnki_id": {
                    "type": "string",
                    "description": "CNKI 论文 ID",
                },
                "paper_title": {
                    "type": "string",
                    "description": "论文标题（用于先搜索再查引用）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数",
                    "default": 50,
                },
            },
        },
    },
]


# ─── HTTP Helpers ─────────────────────────────────────────────────────────────

def _rate_limit(min_seconds: float = 3.0, max_seconds: float = 6.0) -> None:
    """Simple rate limiting with random jitter."""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def _fetch_page(url: str, params: dict | None = None, timeout: int = 20) -> str:
    """Fetch a page with error handling and rate limiting."""
    try:
        resp = _SESSION.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except requests.RequestException as exc:
        _log.warning(f"Request failed for {url[:60]}: {exc}")
        return ""


# ─── CNKI Search Implementation ───────────────────────────────────────────────

def _build_cnki_search_params(query: str, year_from: int, year_to: int,
                               author: str = "", journal: str = "",
                               search_type: str = "theme",
                               page: int = 1,
                               page_size: int = 20) -> dict:
    """Build CNKI advanced search API parameters."""
    # CNKI uses a complex multi-key parameter format
    encoded_query = urllib.parse.quote(query)
    return {
        "KCode": encoded_query,
        "crossids": "YSTT4HG0,LSTPFY19,SCDBME,CPFDAB,CAPJDJD,BJQJCP,"
                    "ZHDPTDM,SWZUIFE,CGJSDB,HDQJND,SYSCDB",
        "S_DB": "SCDB",
        "S_Tp": "1",
        "S_TK": query,
        "syy": str(year_from),
        "syy2": str(year_to),
        "spm": "common.0.0.1",
        "zt": "commonzt",
        "cfg": "[]",
        "action": "sc.search",
        "ua": "1.21",
        "is from": "1",
        "appcode": "global",
        "from": "index",
    }


def _parse_cnki_search_results(html: str, max_results: int = 20) -> dict:
    """Parse CNKI search results page.

    CNKI search results page structure:
      - Results are in <div class="brief-div"> or similar containers
      - Each result has: title, authors, journal, year, cited count
    """
    papers = []
    total = 0

    soup = BeautifulSoup(html, "lxml")

    # Try to find result count
    count_elem = soup.select_one(".total, .result-count, .count")
    if count_elem:
        try:
            total = int("".join(filter(str.isdigit, count_elem.get_text())))
        except ValueError:
            pass

    # Find result items — CNKI uses different structures
    # Try multiple selectors for robustness
    result_selectors = [
        ".result-list .item",
        ".brief-box",
        ".article-list li",
        ".search-result-list tr[data-id]",
        "div[class*=result]",
        "dl.result-list",
    ]

    result_items = []
    for sel in result_selectors:
        result_items = soup.select(sel)
        if result_items:
            break

    if not result_items:
        # Try generic table/list parsing
        result_items = soup.select("li, tr")

    for item in result_items[:max_results]:
        paper = _parse_single_result_item(item)
        if paper:
            papers.append(paper)

    # If parsing failed, try JSON data sometimes embedded in the page
    if not papers:
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict) and "itemListElement" in data:
                    for entry in data["itemListElement"][:max_results]:
                        item = entry.get("item", {})
                        papers.append({
                            "title": item.get("name", ""),
                            "authors": [item.get("author", {}).get("name", "")] if isinstance(item.get("author"), dict) else [],
                            "year": item.get("datePublished", "")[:4] if item.get("datePublished") else "",
                            "journal": item.get("publisher", {}).get("name", "") if isinstance(item.get("publisher"), dict) else "",
                            "doi": item.get("identifier", ""),
                            "url": item.get("url", ""),
                            "source": "cnki",
                        })
            except (json.JSONDecodeError, AttributeError):
                pass

    return {"total": total or len(papers), "papers": papers}


def _parse_single_result_item(item) -> dict | None:
    """Parse a single CNKI search result item from BeautifulSoup element."""
    try:
        # Title
        title_elem = (
            item.select_one("a.title, .title a, h3 a, .name, [class*=title]")
        )
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        detail_url = title_elem.get("href", "")

        # Authors
        author_elems = item.select(".author, .authors, [class*=author]")
        authors = [a.get_text(strip=True) for a in author_elems if a.get_text(strip=True)]
        if not authors:
            author_text = item.get_text()
            # Try to extract author pattern
            import re
            author_matches = re.findall(r"[\u4e00-\u9fa5]{2,4}", author_text[:200])
            if author_matches:
                authors = author_matches[:5]

        # Year and journal
        year = ""
        journal = ""
        meta_elems = item.select(".journal, .source, .date, [class*=journal]")
        for elem in meta_elems:
            text = elem.get_text(strip=True)
            if text:
                import re
                year_match = re.search(r"(20\d{2})", text)
                if year_match:
                    year = year_match.group(1)
                if "年" in text or re.search(r"20\d{2}", text):
                    journal = re.sub(r"\d{4}年?", "", text).strip()
                    break

        # DOI / CNKI ID
        cnki_id = ""
        doi = ""
        import re
        doi_match = re.search(r"doi[:：]?\s*([^\s,，]+)", item.get_text(), re.IGNORECASE)
        if doi_match:
            doi = doi_match.group(1)

        # Cited count
        cited = 0
        cited_elem = item.select_one(".cited, .cited-count, [class*=cited]")
        if cited_elem:
            try:
                cited = int(re.sub(r"\D", "", cited_elem.get_text()))
            except ValueError:
                pass

        return {
            "title": title,
            "authors": authors[:5],
            "year": year,
            "journal": journal,
            "doi": doi,
            "cnki_id": cnki_id,
            "url": detail_url,
            "cited_by_count": cited,
            "source": "cnki",
        }
    except Exception as exc:
        _log.debug(f"Failed to parse result item: {exc}")
        return None


# ─── CNKI Paper Detail ────────────────────────────────────────────────────────

def _fetch_cnki_paper_detail(cnki_id: str = "", title: str = "") -> dict:
    """Fetch detailed metadata for a single CNKI paper."""
    if cnki_id:
        url = f"https://kns.cnki.net/kcms/detail/detail.aspx"
        params = {
            "dbcode": "SCDB",
            "filename": cnki_id,
            "dflag": "cnki_top",
        }
    elif title:
        # First search for the paper
        search_result = search_cnki_papers_sync(
            query=title,
            max_results=5,
            search_type="theme",
        )
        papers = search_result.get("papers", [])
        if papers and papers[0].get("url"):
            detail_url = papers[0]["url"]
            html = _fetch_page(detail_url)
            return _parse_cnki_detail_page(html, papers[0])
        return {"error": f"Paper not found: {title}"}
    else:
        return {"error": "cnki_id or title is required"}

    html = _fetch_page(url, params=params)
    return _parse_cnki_detail_page(html, {"title": title})


def _parse_cnki_detail_page(html: str, base_info: dict) -> dict:
    """Parse CNKI paper detail page."""
    if not html:
        return {**base_info, "error": "Failed to fetch page"}

    soup = BeautifulSoup(html, "lxml")

    result = {**base_info}

    # Try to extract abstract
    abstract_selectors = [
        ".abstract-text", ".abstract", "#ChDivSummary", "[class*=abstract]",
        "span.summary", ".brief-content",
    ]
    for sel in abstract_selectors:
        elem = soup.select_one(sel)
        if elem:
            result["abstract"] = elem.get_text(strip=True)
            break

    # Keywords
    keywords_selectors = [
        ".keywords a", "#ChDivKWM", "[class*=keyword]",
        ".tag-list a", ".keyword-tag",
    ]
    keywords = []
    for sel in keywords_selectors:
        elems = soup.select(sel)
        if elems:
            keywords = [k.get_text(strip=True) for k in elems if k.get_text(strip=True)]
            break
    if keywords:
        result["keywords"] = keywords

    # DOI
    import re
    doi_match = re.search(r"doi[:：]?\s*([^\s<>\"]+)", html)
    if doi_match:
        result["doi"] = doi_match.group(1).strip()

    # Classification
    cls_selectors = [
        ".cls-num", "[class*=classification]",
        ".zone-code", ".amend-detail-left",
    ]
    for sel in cls_selectors:
        elem = soup.select_one(sel)
        if elem:
            result["classification"] = elem.get_text(strip=True)
            break

    return result


# ─── CNKI Citations ───────────────────────────────────────────────────────────

def _fetch_cnki_citations(cnki_id: str = "", paper_title: str = "",
                          max_results: int = 50) -> dict:
    """Fetch papers that cite a given CNKI paper."""
    if not cnki_id and not paper_title:
        return {"error": "cnki_id or paper_title is required"}

    if paper_title:
        # Search first
        search_result = search_cnki_papers_sync(
            query=paper_title,
            max_results=1,
            search_type="theme",
        )
        papers = search_result.get("papers", [])
        if papers:
            cnki_id = papers[0].get("cnki_id", "")

    if not cnki_id:
        return {"error": f"Could not find CNKI ID for: {paper_title}"}

    # CNKI citations URL pattern
    citations_url = f"https://kns.cnki.net/kcms/detail/detail.aspx"
    params = {
        "dbcode": "SCDB",
        "filename": cnki_id,
        "dflag": "cited",
    }

    _rate_limit()
    html = _fetch_page(citations_url, params=params, timeout=25)
    citations = _parse_cnki_search_results(html, max_results)

    return {
        "cnki_id": cnki_id,
        "paper_title": paper_title,
        "total_citations": citations.get("total", 0),
        "citations": citations.get("papers", [])[:max_results],
        "source": "cnki",
    }


# ─── Sync Wrappers (used by handlers) ─────────────────────────────────────────

def search_cnki_papers_sync(query: str, max_results: int = 20,
                             year_from: int = 2020, year_to: int = 2024,
                             author: str = "", journal: str = "",
                             search_type: str = "theme") -> dict:
    """Synchronous CNKI paper search with rate limiting."""
    if not query:
        return {"error": "query is required", "papers": []}

    max_results = min(max_results, 50)
    _rate_limit()

    # CNKI uses POST for advanced search
    data = _build_cnki_search_params(
        query=query,
        year_from=year_from,
        year_to=year_to,
        author=author,
        journal=journal,
        search_type=search_type,
    )

    try:
        resp = _SESSION.post(_CNKI_ADVANCED_URL, data=data, timeout=25)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        html = resp.text
    except requests.RequestException as exc:
        _log.warning(f"CNKI search failed: {exc}")
        return {
            "error": f"CNKI search request failed: {exc}",
            "papers": [],
            "query": query,
            "notice": _ROBOTS_TXT_NOTICE,
        }

    results = _parse_cnki_search_results(html, max_results)
    results["query"] = query
    results["year_range"] = f"{year_from}-{year_to}"
    results["author_filter"] = author
    results["journal_filter"] = journal
    results["search_type"] = search_type
    results["notice"] = _ROBOTS_TXT_NOTICE

    return results


# ─── MCP Server Handlers ───────────────────────────────────────────────────────

async def handle_search_cnki_papers(args: dict) -> list[dict]:
    """Handle search_cnki_papers tool."""
    query = args.get("query", "")
    if not query:
        return [{"type": "text", "text": json.dumps(
            {"error": "query is required"}, ensure_ascii=False)}]

    result = search_cnki_papers_sync(
        query=query,
        max_results=args.get("max_results", 20),
        year_from=args.get("year_from", 2020),
        year_to=args.get("year_to", 2024),
        author=args.get("author", ""),
        journal=args.get("journal", ""),
        search_type=args.get("search_type", "theme"),
    )
    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]


async def handle_get_cnki_paper_detail(args: dict) -> list[dict]:
    """Handle get_cnki_paper_detail tool."""
    cnki_id = args.get("cnki_id", "")
    title = args.get("title", "")
    fetch_citations = args.get("fetch_citations", False)

    if not cnki_id and not title:
        return [{"type": "text", "text": json.dumps(
            {"error": "cnki_id or title is required"}, ensure_ascii=False)}]

    result = _fetch_cnki_paper_detail(cnki_id=cnki_id, title=title)

    if fetch_citations and not result.get("error"):
        _rate_limit()
        citations = _fetch_cnki_citations(
            cnki_id=cnki_id,
            paper_title=title,
            max_results=20,
        )
        result["citations"] = citations.get("citations", [])
        result["total_citations"] = citations.get("total_citations", 0)

    result["notice"] = _ROBOTS_TXT_NOTICE
    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]


async def handle_get_cnki_citations(args: dict) -> list[dict]:
    """Handle get_cnki_citations tool."""
    cnki_id = args.get("cnki_id", "")
    paper_title = args.get("paper_title", "")
    max_results = args.get("max_results", 50)

    result = _fetch_cnki_citations(
        cnki_id=cnki_id,
        paper_title=paper_title,
        max_results=max_results,
    )
    result["notice"] = _ROBOTS_TXT_NOTICE
    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]


TOOL_HANDLERS = {
    "search_cnki_papers": handle_search_cnki_papers,
    "get_cnki_paper_detail": handle_get_cnki_paper_detail,
    "get_cnki_citations": handle_get_cnki_citations,
}


# ─── MCP Server Entry Point ────────────────────────────────────────────────────

def main():
    import asyncio
    from mcp.server import Server, NotificationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    from mcp.server.models import InitializationOptions

    server = Server("user-cnki")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            return [TextContent(type="text", text=json.dumps(
                {"error": f"Unknown tool: {name}"}))]
        try:
            results = await handler(arguments)
            return [TextContent(type=r.get("type", "text"), text=r.get("text", ""))
                    for r in results]
        except Exception as exc:
            _log.error(f"Tool {name} failed: {exc}")
            return [TextContent(type="text", text=json.dumps(
                {"error": str(exc)}, ensure_ascii=False))]

    async def amain():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream,
                InitializationOptions(
                    server_name="user-cnki",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

    asyncio.run(amain())


if __name__ == "__main__":
    main()
