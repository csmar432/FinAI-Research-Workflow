#!/usr/bin/env python3
"""
Brave Search MCP Server
=======================
Brave Search API 网络搜索服务。

数据源：Brave Search API（需 BRAVE_SEARCH_API_KEY）
注册：https://api.search.brave.com

Usage:
    python server.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("brave_search_mcp")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
    load_dotenv(_PROJECT_ROOT / ".env.local", override=True)
except Exception:
    pass

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    log.error("mcp package required. pip install mcp")
    sys.exit(1)

import requests

server = Server("user-brave-search")
_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
_API_BASE = "https://api.search.brave.com/res/v1/web/search"

TOOLS = [
    Tool(
        name="brave_web_search",
        description="网络搜索工具。使用 Brave Search API。需配置 BRAVE_SEARCH_API_KEY（免费注册：https://api.search.brave.com）",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询词"},
                "count": {"type": "integer", "description": "返回结果数量（默认10，最大50）", "default": 10},
            },
            "required": ["query"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if not _API_KEY:
        return [TextContent(
            type="text",
            text="BRAVE_SEARCH_API_KEY not configured. Set in .env.local:\nBRAVE_SEARCH_API_KEY=your_key\nGet free key at: https://api.search.brave.com\n\nAlternatively, use the WebSearch tool (global, no key needed)."
        )]

    query = arguments.get("query", "")
    count = min(arguments.get("count", 10), 50)

    headers = {
        "X-Subscription-Token": _API_KEY,
        "Accept": "application/json",
        "User-Agent": "FinResearch-Agent/1.0",
    }
    params = {"q": query, "count": count}

    try:
        resp = requests.get(_API_BASE, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("web", {}).get("results", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
                "age": item.get("age", ""),
            })

        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Brave Search error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
