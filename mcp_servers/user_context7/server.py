#!/usr/bin/env python3
"""
Context7 MCP Server
==================
Context7 论文全文索引服务。

数据源：Context7 API（无需 API Key，完全免费）
覆盖：ArXiv + 开放获取论文全文

Usage:
    python server.py
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("context7_mcp")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    log.error("mcp package required. pip install mcp")
    sys.exit(1)

import requests

server = Server("user-context7")
_API_BASE = "https://api.context7.com/v1"
_SESSION = requests.Session()

TOOLS = [
    Tool(
        name="get_context7_by_arxiv",
        description="通过 ArXiv ID 获取论文全文。使用 Context7，无需 API Key。",
        inputSchema={
            "type": "object",
            "properties": {
                "arxiv_id": {"type": "string", "description": "ArXiv ID（如 2301.12345）"},
                "max_results": {"type": "integer", "description": "最大返回片段数", "default": 5},
            },
            "required": ["arxiv_id"],
        },
    ),
    Tool(
        name="get_context7_by_query",
        description="通过关键词搜索 Context7 索引中的论文全文。无需 API Key。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询词"},
                "max_results": {"type": "integer", "description": "最大返回结果数", "default": 10},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_context7_by_doi",
        description="通过 DOI 获取论文全文内容。",
        inputSchema={
            "type": "object",
            "properties": {
                "doi": {"type": "string", "description": "论文 DOI，例如 '10.1038/nature12373'"},
            },
            "required": ["doi"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    headers = {"User-Agent": "FinResearch-Agent/1.0", "Accept": "application/json"}

    try:
        if name == "get_context7_by_arxiv":
            arxiv_id = arguments.get("arxiv_id", "").strip()
            max_results = arguments.get("max_results", 5)

            # 去掉版本号
            import re
            base_id = re.sub(r"v\d+$", "", arxiv_id)
            url = f"{_API_BASE}/rag?dataset=arxiv&file_id={base_id}&max_results={max_results}"

            resp = _SESSION.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]
            else:
                return [TextContent(type="text", text=f"Context7 API error: HTTP {resp.status_code} - {resp.text[:200]}")]

        elif name == "get_context7_by_query":
            query = arguments.get("query", "")
            max_results = arguments.get("max_results", 10)
            url = f"{_API_BASE}/search?dataset=arxiv&q={requests.utils.quote(query)}&max_results={max_results}"

            resp = _SESSION.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]
            else:
                return [TextContent(type="text", text=f"Context7 API error: HTTP {resp.status_code}")]

        elif name == "get_context7_by_doi":
            doi = arguments.get("doi", "").strip()
            if not doi:
                return [TextContent(type="text", text="doi is required")]
            url = f"{_API_BASE}/resolve?doi={requests.utils.quote(doi)}"
            resp = _SESSION.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]
            else:
                return [TextContent(type="text", text=f"Context7 API error: HTTP {resp.status_code} - {resp.text[:200]}")]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        log.error(f"Context7 error in {name}: {e}")
        return [TextContent(type="text", text=f"Context7 error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
