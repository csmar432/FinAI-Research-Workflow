#!/usr/bin/env python3
"""
ArXiv MCP Server
================
ArXiv 学术论文搜索与获取服务。

数据源：ArXiv API（无需 API Key，完全免费）

Usage:
    python server.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
import urllib.request
import urllib.parse
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("arxiv_mcp")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    log.error("mcp package required. pip install mcp")
    sys.exit(1)

server = Server("user-arxiv")
_API_BASE = "http://export.arxiv.org/api/query"


def _parse_atom(xml_text: str) -> list[dict]:
    entries = []
    for block in re.split(r"<entry>", xml_text)[1:]:
        entry = {}
        for field in ["id", "title", "summary", "author", "published", "updated", "comment", "doi"]:
            m = re.search(rf"<{field}[^>]*>(.*?)</{field}>", block, re.DOTALL)
            if m:
                val = re.sub(r"<[^>]+>", "", m.group(1).strip())
                entry[field] = val
        cats = re.findall(r'<category term="([^"]+)"', block)
        entry["categories"] = cats
        if cats:
            entry["primary_category"] = cats[0]
        entries.append(entry)
    return entries


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="semantic_search",
            description="ArXiv 学术论文搜索。使用 ArXiv API，无需 API Key，完全免费。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询词（支持 AND/OR/NOT 布尔逻辑）"},
                    "max_results": {"type": "integer", "description": "最大返回数量", "default": 10},
                    "sort_by": {"type": "string", "description": "排序方式", "enum": ["relevance", "lastUpdatedDate", "submittedDate"], "default": "relevance"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_arxiv_paper",
            description="通过 ArXiv ID 获取论文详情。使用 ArXiv API，无需 API Key。",
            inputSchema={
                "type": "object",
                "properties": {
                    "arxiv_id": {"type": "string", "description": "ArXiv ID（如 2301.12345）"},
                    "include_pdf": {"type": "boolean", "description": "是否返回PDF摘要", "default": False},
                },
                "required": ["arxiv_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "semantic_search":
            query = arguments.get("query", "")
            max_results = min(arguments.get("max_results", 10), 100)
            sort_by = arguments.get("sort_by", "relevance")
            url = f"{_API_BASE}?search_query=all:{urllib.parse.quote_plus(query)}&start=0&max_results={max_results}&sortBy={sort_by}"
            req = urllib.request.Request(url, headers={"User-Agent": "FinResearch-Agent/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_text = resp.read().decode("utf-8")
            entries = _parse_atom(xml_text)
            results = [{
                "arxiv_id": e.get("id", "").split("/")[-1] if e.get("id") else "",
                "title": e.get("title", ""),
                "summary": e.get("summary", "")[:600],
                "authors": e.get("author", ""),
                "published": e.get("published", ""),
                "categories": e.get("categories", []),
                "doi": e.get("doi", ""),
                "url": f"https://arxiv.org/abs/{e.get('id','').split('/')[-1]}",
            } for e in entries]
            return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]

        elif name == "get_arxiv_paper":
            arxiv_id = arguments.get("arxiv_id", "").strip()
            base_id = re.sub(r"v\d+$", "", arxiv_id)
            url = f"{_API_BASE}?id_list={base_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "FinResearch-Agent/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_text = resp.read().decode("utf-8")
            entries = _parse_atom(xml_text)
            if not entries:
                return [TextContent(type="text", text=f"No paper found for {arxiv_id}")]
            e = entries[0]
            return [TextContent(type="text", text=json.dumps({
                "arxiv_id": base_id,
                "title": e.get("title", ""),
                "summary": e.get("summary", ""),
                "authors": e.get("author", ""),
                "published": e.get("published", ""),
                "categories": e.get("categories", []),
                "doi": e.get("doi", ""),
                "pdf_url": f"https://arxiv.org/pdf/{base_id}.pdf",
                "abs_url": f"https://arxiv.org/abs/{base_id}",
            }, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"ArXiv error: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
