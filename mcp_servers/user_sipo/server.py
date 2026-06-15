#!/usr/bin/env python3
"""SIPO MCP Server — 国家知识产权局专利数据

API文档: https://cpquery.cponline.cnipa.gov.cn
注册: https://cponline.cnipa.gov.cn

数据覆盖:
  - 专利基本信息（申请号、公开号、申请人、发明人）
  - 专利法律状态（有效、失效、审中）
  - 专利引文信息
  - 专利质押、许可、转让记录
  - 专利诉讼关联数据
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp.server.stdio import stdio_server
    import asyncio
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

API_KEY = os.environ.get("SIPO_API_KEY", "")
USERNAME = os.environ.get("SIPO_USERNAME", "")
BASE_URL = "https://cpquery.cponline.cnipa.gov.cn"

TOOLS: list[Tool] = [
    Tool(
        name="search_sipo_patent",
        description="按关键词、申请人、发明人检索中国专利数据库。覆盖发明专利、实用新型、外观设计。支持IPC分类号过滤。",
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "关键词（专利名称/摘要中的词）"},
                "applicant": {"type": "string", "description": "申请人/权利人名称"},
                "inventor": {"type": "string", "description": "发明人"},
                "ipc_code": {"type": "string", "description": "IPC国际专利分类号（如H01M）"},
                "patent_type": {"type": "string", "enum": ["发明", "实用新型", "外观设计", "all"], "default": "all"},
                "date_from": {"type": "string", "description": "申请日期起（YYYY-MM-DD）"},
                "date_to": {"type": "string", "description": "申请日期止（YYYY-MM-DD）"},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 20},
            },
        },
    ),
    Tool(
        name="get_patent_detail",
        description="获取指定专利的详细信息，包括摘要、权利要求书要点、附图说明。",
        inputSchema={
            "type": "object",
            "properties": {
                "patent_number": {"type": "string", "description": "专利号（如CN202110123456.7）"},
                "include_claims": {"type": "boolean", "default": False, "description": "是否包含权利要求"},
            },
        },
    ),
    Tool(
        name="get_patent_bibliographic",
        description="获取专利著录项目信息（申请人、发明人、IPC分类、申请日期、优先权等）。",
        inputSchema={
            "type": "object",
            "properties": {
                "patent_number": {"type": "string", "description": "专利号"},
            },
        },
    ),
    Tool(
        name="get_patent_litigation",
        description="查询专利相关的诉讼案件、质押记录、许可记录、转让记录。",
        inputSchema={
            "type": "object",
            "properties": {
                "patent_number": {"type": "string", "description": "专利号"},
                "record_type": {"type": "string", "enum": ["诉讼", "质押", "许可", "转让", "all"], "default": "all"},
            },
        },
    ),
]


async def handle_search(params: dict) -> dict:
    if not API_KEY and not USERNAME:
        return {
            "status": "warning",
            "message": "SIPO credentials not configured. Set SIPO_API_KEY or SIPO_USERNAME environment variable. Register at https://cpquery.cponline.cnipa.gov.cn",
            "data": [],
            "fallback": "Use user-openalex for international patents, or user-brave-search for Chinese patent news.",
        }
    
    import httpx
    
    url = f"{BASE_URL}/api/search"
    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            resp = await client.get(url, params={k: v for k, v in params.items() if v is not None})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        _log.warning("[SIPO] Search failed: %s", e)
        return {"status": "error", "message": str(e), "data": []}


async def handle_detail(params: dict) -> dict:
    if not API_KEY and not USERNAME:
        return {
            "status": "warning",
            "message": "SIPO credentials not configured.",
            "data": {},
        }
    
    import httpx
    url = f"{BASE_URL}/api/detail"
    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        _log.warning("[SIPO] Detail failed: %s", e)
        return {"status": "error", "message": str(e), "data": {}}


async def handle_bibliographic(params: dict) -> dict:
    return await handle_detail({**params, "mode": "bibliographic"})


async def handle_litigation(params: dict) -> dict:
    return await handle_detail({**params, "mode": "litigation"})


def create_server():
    server = Server("user-sipo")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        handlers = {
            "search_sipo_patent": handle_search,
            "get_patent_detail": handle_detail,
            "get_patent_bibliographic": handle_bibliographic,
            "get_patent_litigation": handle_litigation,
        }
        
        handler = handlers.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        try:
            result = await handler(arguments)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
        except Exception as e:
            _log.error("[SIPO] Tool %s failed: %s", name, e)
            return [TextContent(type="text", text=json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))]
    
    return server


async def main():
    if not HAS_MCP:
        print("SIPO MCP Server — 国家知识产权局专利数据")
        print(f"API Key configured: {'Yes' if API_KEY else 'No (set SIPO_API_KEY)'}")
        return
    
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
