#!/usr/bin/env python3
"""CNRDS MCP Server — 中国研究数据服务平台

API文档: https://www.cnrds.com
注册获取Key: https://www.cnrds.com/Account/Register

数据覆盖:
  - 专利数据（发明/实用新型/外观设计）
  - 学术论文（中文期刊/学位论文）
  - 上市公司财务数据
  - 高新技术企业认定数据
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any
from pathlib import Path

# MCP SDK
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

API_KEY = os.environ.get("CNRDS_API_KEY", "")
BASE_URL = "https://www.cnrds.com/api"

# ─── Tool Definitions ──────────────────────────────────────────────────────────


TOOLS: list[Tool] = [
    Tool(
        name="get_cnrd_patent",
        description="查询CNRDS专利数据库。支持按申请人、发明人、关键词、日期范围检索专利。覆盖中国所有专利类型（发明/实用新型/外观设计）。",
        inputSchema={
            "type": "object",
            "properties": {
                "applicant": {"type": "string", "description": "专利申请人/权利人"},
                "inventor": {"type": "string", "description": "发明人"},
                "keyword": {"type": "string", "description": "关键词"},
                "patent_type": {"type": "string", "enum": ["发明", "实用新型", "外观设计", "all"], "default": "all", "description": "专利类型"},
                "start_date": {"type": "string", "description": "申请日期起（YYYY-MM-DD）"},
                "end_date": {"type": "string", "description": "申请日期止（YYYY-MM-DD）"},
                "page": {"type": "integer", "default": 1, "description": "页码"},
                "page_size": {"type": "integer", "default": 20, "description": "每页条数（最大100）"},
            },
        },
    ),
    Tool(
        name="search_cnrd_papers",
        description="检索CNRDS学术论文数据库。覆盖中文核心期刊、学位论文、会议论文。",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "论文标题关键词"},
                "author": {"type": "string", "description": "作者"},
                "journal": {"type": "string", "description": "期刊名称"},
                "year_from": {"type": "integer", "description": "发表年份起"},
                "year_to": {"type": "integer", "description": "发表年份止"},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 20},
            },
        },
    ),
    Tool(
        name="get_cnrd_company",
        description="查询CNRDS上市公司数据库。获取上市公司基本信息、股权结构、高管信息。",
        inputSchema={
            "type": "object",
            "properties": {
                "stock_code": {"type": "string", "description": "股票代码（支持沪深格式）"},
                "company_name": {"type": "string", "description": "公司名称（模糊匹配）"},
            },
        },
    ),
    Tool(
        name="get_cnrd_financial",
        description="查询CNRDS上市公司财务数据库。获取资产负债、利润表、现金流量数据。",
        inputSchema={
            "type": "object",
            "properties": {
                "stock_code": {"type": "string", "description": "股票代码"},
                "year": {"type": "integer", "description": "年份"},
                "quarter": {"type": "integer", "description": "季度（1-4），不填则返回年度"},
            },
        },
    ),
]


# ─── Tool Handlers ─────────────────────────────────────────────────────────────


async def handle_get_cnrd_patent(params: dict) -> dict:
    """Handle patent query."""
    if not API_KEY:
        return {
            "status": "warning",
            "message": "CNRDS_API_KEY not configured. Please set CNRDS_API_KEY environment variable. Register at https://www.cnrds.com",
            "data": [],
            "fallback_suggestion": "Use user-tushare for A-share financial data, user-openalex for academic papers, or user-brave-search for patent search.",
        }
    
    import httpx
    
    url = f"{BASE_URL}/patent/search"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params={k: v for k, v in params.items() if v is not None})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        _log.warning("[CNRDS] API call failed: %s", e)
        return {"status": "error", "message": str(e), "data": []}


async def handle_search_cnrd_papers(params: dict) -> dict:
    """Handle paper search."""
    if not API_KEY:
        return {
            "status": "warning",
            "message": "CNRDS_API_KEY not configured. Register at https://www.cnrds.com",
            "data": [],
        }
    
    import httpx
    
    url = f"{BASE_URL}/paper/search"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params={k: v for k, v in params.items() if v is not None})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        _log.warning("[CNRDS] Paper search failed: %s", e)
        return {"status": "error", "message": str(e), "data": []}


async def handle_get_cnrd_company(params: dict) -> dict:
    """Handle company query."""
    if not API_KEY:
        return {
            "status": "warning",
            "message": "CNRDS_API_KEY not configured. Register at https://www.cnrds.com",
            "data": {},
        }
    
    import httpx
    
    url = f"{BASE_URL}/company/info"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        _log.warning("[CNRDS] Company query failed: %s", e)
        return {"status": "error", "message": str(e), "data": {}}


async def handle_get_cnrd_financial(params: dict) -> dict:
    """Handle financial data query."""
    if not API_KEY:
        return {
            "status": "warning",
            "message": "CNRDS_API_KEY not configured. Register at https://www.cnrds.com",
            "data": {},
        }
    
    import httpx
    
    url = f"{BASE_URL}/financial/statement"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params={k: v for k, v in params.items() if v is not None})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        _log.warning("[CNRDS] Financial query failed: %s", e)
        return {"status": "error", "message": str(e), "data": {}}


# ─── MCP Server ────────────────────────────────────────────────────────────────


def create_server():
    server = Server("user-cnrd")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        handlers = {
            "get_cnrd_patent": handle_get_cnrd_patent,
            "search_cnrd_papers": handle_search_cnrd_papers,
            "get_cnrd_company": handle_get_cnrd_company,
            "get_cnrd_financial": handle_get_cnrd_financial,
        }
        
        handler = handlers.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        try:
            result = await handler(arguments)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
        except Exception as e:
            _log.error("[CNRDS] Tool %s failed: %s", name, e)
            return [TextContent(type="text", text=json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))]
    
    return server


async def main():
    """Entry point — wires async handlers to the MCP server and runs stdio transport."""
    if not HAS_MCP:
        print("ERROR: mcp package not installed. Run: pip install mcp")
        print("CNRDS MCP Server — 中国研究数据服务平台")
        print(f"API Key configured: {'Yes' if API_KEY else 'No (set CNRDS_API_KEY)'}")
        print(f"Base URL: {BASE_URL}")
        return

    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
