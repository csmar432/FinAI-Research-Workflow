#!/usr/bin/env python3
"""
Wanfang MCP Server
==================
万方数据（Wanfang Data）学术论文检索服务。

数据源：
  - 万方数据官网（wanfangdata.com.cn）
  - 通过 requests + BeautifulSoup 实现网页爬取

注意：
  - 万方数据没有公开的免费 API，本服务使用网页爬虫实现
  - 请遵守万方数据的服务条款
  - 高频访问可能被临时封禁，建议设置合理的请求间隔
  - 万方数据提供付费 API，建议机构用户申请正式账号

Usage:
    python server.py
"""

from __future__ import annotations

import json
import logging
import random
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    import warnings
    warnings.filterwarnings("ignore")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
)
_log = logging.getLogger("wanfang_mcp")

_SERVER_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SERVER_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ─── Constants ─────────────────────────────────────────────────────────────────

_WANFANG_SEARCH_URL = "https://s.wanfangdata.com.cn/paper"
_WANFANG_DETAIL_URL = "https://www.wanfangdata.com.cn/details"
_WANFANG_HOME_URL = "https://www.wanfangdata.com.cn"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.wanfangdata.com.cn/",
}

_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)

_ROBOTS_TXT_NOTICE = (
    "本服务使用网页爬虫方式获取万方数据。爬虫行为受网站服务条款约束，"
    "请勿高频访问或大规模抓取。建议使用万方数据机构账号获取更稳定的数据访问。"
)

# ─── Tool Definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_wanfang_papers",
        "description": (
            "搜索万方数据（Wanfang）学术论文。\n\n"
            "万方数据是国内三大中文学术数据库之一，覆盖期刊、学位、会议、专利等。\n"
            "支持按主题词、作者、期刊、年份等多维度检索。\n\n"
            "返回论文标题、作者、期刊、年份、摘要、被引次数等元数据。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如：数字金融 绿色创新",
                },
                "author": {
                    "type": "string",
                    "description": "作者姓名（可选）",
                },
                "journal": {
                    "type": "string",
                    "description": "期刊名称（可选）",
                },
                "year_from": {
                    "type": "integer",
                    "description": "起始年份（默认2020）",
                    "default": 2020,
                },
                "year_to": {
                    "type": "integer",
                    "description": "结束年份（默认2024）",
                    "default": 2024,
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数（默认20，最大50）",
                    "default": 20,
                },
                "paper_type": {
                    "type": "string",
                    "description": "文献类型：periodical（期刊）/ thesis（学位论文）/ conference（会议）/ patent（专利）",
                    "default": "periodical",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_wanfang_paper_detail",
        "description": (
            "获取万方数据单篇论文的详细信息。\n\n"
            "通过论文 ID 或标题获取完整元数据，包括："
            "摘要、关键词、作者信息、期刊信息、基金、DOI、ISSN等。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "wanfang_id": {
                    "type": "string",
                    "description": "万方数据论文 ID",
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
]


# ─── HTTP Helpers ─────────────────────────────────────────────────────────────

def _rate_limit(min_seconds: float = 3.0, max_seconds: float = 6.0) -> None:
    """Simple rate limiting with random jitter."""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def _fetch_page(url: str, params: dict | None = None,
                data: dict | None = None,
                timeout: int = 20) -> str:
    """Fetch a page with error handling and rate limiting."""
    try:
        if data:
            resp = _SESSION.post(url, data=data, params=params, timeout=timeout)
        else:
            resp = _SESSION.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except requests.RequestException as exc:
        _log.warning(f"Request failed for {url[:60]}: {exc}")
        return ""


# ─── Wanfang Search Implementation ───────────────────────────────────────────

def _build_wanfang_search_url(query: str, year_from: int, year_to: int,
                               author: str = "", journal: str = "",
                               paper_type: str = "periodical",
                               page: int = 1) -> tuple[str, dict]:
    """Build Wanfang search URL and params."""
    encoded_query = urllib.parse.quote(query)

    # Build base URL with query params
    params = {
        "q": query,
        "pt": paper_type,
        "p": page,
    }
    if author:
        params["a"] = author
    if journal:
        params["j"] = journal

    url = _WANFANG_SEARCH_URL
    return url, params


def _parse_wanfang_search_results(html: str, max_results: int = 20) -> dict:
    """Parse Wanfang search results page.

    Wanfang data search page structure:
      - Results in <div class="result-list"> or similar
      - Each item has: title, authors, journal, year, cited count
    """
    papers = []
    total = 0

    soup = BeautifulSoup(html, "lxml")

    # Try to find result count
    count_selectors = [
        ".total", ".result-count", ".count", ".total-num",
        "[class*=total]", ".search-result-count",
    ]
    for sel in count_selectors:
        elem = soup.select_one(sel)
        if elem:
            text = elem.get_text(strip=True)
            # Extract number
            num_match = re.search(r"(\d[\d,]*)", text)
            if num_match:
                try:
                    total = int(num_match.group(1).replace(",", ""))
                    break
                except ValueError:
                    pass

    # Find result items
    result_selectors = [
        ".result-list .item",
        ".paper-list .item",
        ".search-list .result",
        "div[class*=result-item]",
        ".list-item",
        "li.result-item",
    ]

    result_items = []
    for sel in result_selectors:
        result_items = soup.select(sel)
        if result_items:
            break

    # Fallback: try div/li with title
    if not result_items:
        result_items = soup.select("div[class*=item], li[class*=item]")

    for item in result_items[:max_results]:
        paper = _parse_wanfang_result_item(item)
        if paper:
            papers.append(paper)

    # Try JSON-LD structured data
    if not papers:
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for entry in data:
                        if entry.get("@type") == "ScholarlyArticle":
                            papers.append(_parse_wanfang_ld_json(entry))
                elif data.get("@type") == "ItemList":
                    for entry in data.get("itemListElement", [])[:max_results]:
                        item = entry.get("item", {})
                        papers.append(_parse_wanfang_ld_json(item))
            except (json.JSONDecodeError, AttributeError):
                pass

    return {"total": total or len(papers), "papers": papers}


def _parse_wanfang_ld_json(data: dict) -> dict:
    """Parse Wanfang JSON-LD structured data."""
    authors = []
    author_data = data.get("author", [])
    if isinstance(author_data, list):
        authors = [a.get("name", "") if isinstance(a, dict) else str(a) for a in author_data]
    elif isinstance(author_data, dict):
        authors = [author_data.get("name", "")]

    publisher = data.get("publisher", {})
    pub_name = ""
    if isinstance(publisher, dict):
        pub_name = publisher.get("name", "")
    elif isinstance(publisher, str):
        pub_name = publisher

    return {
        "title": data.get("name", data.get("headline", "")),
        "authors": authors[:5],
        "year": data.get("datePublished", "")[:4] if data.get("datePublished") else "",
        "journal": pub_name,
        "doi": data.get("identifier", ""),
        "url": data.get("url", ""),
        "cited_by_count": 0,
        "source": "wanfang",
    }


def _parse_wanfang_result_item(item) -> dict | None:
    """Parse a single Wanfang search result item."""
    try:
        # Title
        title_elem = item.select_one(
            "a.title, .title a, h3 a, .name a, [class*=title] a, a[class*=title]"
        )
        if not title_elem:
            # Try without <a> wrapper
            title_elem = item.select_one("a.title, .title, [class*=title]")
        if not title_elem:
            title_elem = item.select_one("h3, .name")

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        detail_url = ""
        if title_elem.name == "a" and title_elem.get("href"):
            detail_url = title_elem.get("href")
        else:
            link = item.select_one("a")
            if link:
                detail_url = link.get("href", "")

        # Make absolute URL
        if detail_url and not detail_url.startswith("http"):
            detail_url = urllib.parse.urljoin(_WANFANG_HOME_URL, detail_url)

        # Authors
        author_elems = item.select(".author, .authors, [class*=author]")
        authors = [a.get_text(strip=True) for a in author_elems if a.get_text(strip=True)]
        if not authors:
            author_text = item.get_text()[:200]
            author_matches = re.findall(r"[\u4e00-\u9fa5]{2,4}", author_text)
            if author_matches:
                authors = author_matches[:5]

        # Year and journal
        year = ""
        journal = ""
        meta_text = item.get_text()
        year_match = re.search(r"(20\d{2})", meta_text)
        if year_match:
            year = year_match.group(1)

        journal_elems = item.select(".journal, .source, [class*=journal], [class*=source]")
        for elem in journal_elems:
            text = elem.get_text(strip=True)
            if text and len(text) > 2 and len(text) < 100:
                journal = re.sub(r"(20\d{2}|[\d期卷号]+)", "", text).strip("[]（）、,，-:：")
                if journal:
                    break

        # DOI
        doi = ""
        doi_match = re.search(r"doi[:：]?\s*([^\s,，]+)", meta_text, re.IGNORECASE)
        if doi_match:
            doi = doi_match.group(1).strip()

        # Cited count
        cited = 0
        cited_elem = item.select_one(".cited, .cited-count, [class*=cited], .引用")
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
            "url": detail_url,
            "cited_by_count": cited,
            "source": "wanfang",
        }
    except Exception as exc:
        _log.debug(f"Failed to parse result item: {exc}")
        return None


# ─── Wanfang Paper Detail ─────────────────────────────────────────────────────

def _fetch_wanfang_paper_detail(wanfang_id: str = "", title: str = "") -> dict:
    """Fetch detailed metadata for a single Wanfang paper."""
    if not wanfang_id and not title:
        return {"error": "wanfang_id or title is required"}

    if wanfang_id:
        url = f"{_WANFANG_DETAIL_URL}.do?pkcms:detail/{wanfang_id}"
    else:
        # Search first
        search_result = search_wanfang_papers_sync(
            query=title,
            max_results=3,
            paper_type="periodical",
        )
        papers = search_result.get("papers", [])
        if papers and papers[0].get("url"):
            url = papers[0]["url"]
            result = _fetch_detail_page(url)
            if title:
                result["query_title"] = title
            return result
        return {"error": f"Paper not found: {title}"}

    return _fetch_detail_page(url)


def _fetch_detail_page(url: str) -> dict:
    """Fetch and parse Wanfang paper detail page."""
    _rate_limit()
    html = _fetch_page(url)

    if not html:
        return {"error": f"Failed to fetch: {url}", "url": url}

    soup = BeautifulSoup(html, "lxml")
    result = {"url": url}

    # Title
    title_elem = soup.select_one("h1.title, h1[class*=title], .paper-title, [class*=title] h1")
    if title_elem:
        result["title"] = title_elem.get_text(strip=True)

    # Abstract
    abstract_selectors = [
        ".abstract-text", ".abstract", "#ChDivSummary",
        "[class*=abstract]", ".brief-content", ".summary",
    ]
    for sel in abstract_selectors:
        elem = soup.select_one(sel)
        if elem:
            result["abstract"] = elem.get_text(strip=True)
            break

    # Keywords
    kw_selectors = [
        ".keywords a, .keywords, [class*=keyword]", ".keyword-tag", ".tag-list",
    ]
    keywords = []
    for sel in kw_selectors:
        elems = soup.select(sel)
        if elems:
            keywords = [k.get_text(strip=True) for k in elems if k.get_text(strip=True)]
            break
    if keywords:
        result["keywords"] = keywords

    # DOI
    doi_match = re.search(r"doi[:：]?\s*([^\s<>\"]+)", html)
    if doi_match:
        result["doi"] = doi_match.group(1).strip()

    # ISSN
    issn_match = re.search(r"ISSN[:：]?\s*([\d\-]{9,13})", html, re.IGNORECASE)
    if issn_match:
        result["issn"] = issn_match.group(1).strip()

    return result


# ─── Sync Wrapper ─────────────────────────────────────────────────────────────

def search_wanfang_papers_sync(query: str, max_results: int = 20,
                                year_from: int = 2020, year_to: int = 2024,
                                author: str = "", journal: str = "",
                                paper_type: str = "periodical") -> dict:
    """Synchronous Wanfang paper search."""
    if not query:
        return {"error": "query is required", "papers": []}

    max_results = min(max_results, 50)
    _rate_limit()

    # Build search URL
    url, params = _build_wanfang_search_url(
        query=query,
        year_from=year_from,
        year_to=year_to,
        author=author,
        journal=journal,
        paper_type=paper_type,
    )

    # Add year filter to params if needed
    if year_from or year_to:
        params["date_from"] = f"{year_from}-01-01"
        params["date_to"] = f"{year_to}-12-31"

    try:
        resp = _SESSION.get(url, params=params, timeout=25)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        html = resp.text
    except requests.RequestException as exc:
        _log.warning(f"Wanfang search failed: {exc}")
        return {
            "error": f"Wanfang search request failed: {exc}",
            "papers": [],
            "query": query,
            "notice": _ROBOTS_TXT_NOTICE,
        }

    results = _parse_wanfang_search_results(html, max_results)
    results["query"] = query
    results["year_range"] = f"{year_from}-{year_to}"
    results["author_filter"] = author
    results["journal_filter"] = journal
    results["paper_type"] = paper_type
    results["notice"] = _ROBOTS_TXT_NOTICE

    return results


# ─── MCP Handlers ─────────────────────────────────────────────────────────────

async def handle_search_wanfang_papers(args: dict) -> list[dict]:
    """Handle search_wanfang_papers tool."""
    query = args.get("query", "")
    if not query:
        return [{"type": "text", "text": json.dumps(
            {"error": "query is required"}, ensure_ascii=False)}]

    result = search_wanfang_papers_sync(
        query=query,
        max_results=args.get("max_results", 20),
        year_from=args.get("year_from", 2020),
        year_to=args.get("year_to", 2024),
        author=args.get("author", ""),
        journal=args.get("journal", ""),
        paper_type=args.get("paper_type", "periodical"),
    )
    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]


async def handle_get_wanfang_paper_detail(args: dict) -> list[dict]:
    """Handle get_wanfang_paper_detail tool."""
    wanfang_id = args.get("wanfang_id", "")
    title = args.get("title", "")
    fetch_citations = args.get("fetch_citations", False)

    if not wanfang_id and not title:
        return [{"type": "text", "text": json.dumps(
            {"error": "wanfang_id or title is required"}, ensure_ascii=False)}]

    result = _fetch_wanfang_paper_detail(wanfang_id=wanfang_id, title=title)
    result["notice"] = _ROBOTS_TXT_NOTICE

    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]


TOOL_HANDLERS = {
    "search_wanfang_papers": handle_search_wanfang_papers,
    "get_wanfang_paper_detail": handle_get_wanfang_paper_detail,
}


# ─── MCP Server Entry Point ────────────────────────────────────────────────────

def main():
    import asyncio
    from mcp.server import Server, NotificationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    from mcp.server.models import InitializationOptions

    server = Server("user-wanfang")

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
                    server_name="user-wanfang",
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
