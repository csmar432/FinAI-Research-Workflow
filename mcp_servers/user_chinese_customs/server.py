#!/usr/bin/env python3
"""Chinese Customs MCP Server — 中国海关进出口数据

数据来源: https://stats.customs.gov.cn
注册: https://stats.customs.gov.cn/ account/Register

数据覆盖:
  - 按HS编码的进出口金额/数量（金额单位：万美元）
  - 按贸易伙伴（国别/地区）的进出口数据
  - 按省份/城市的进出口数据
  - 按企业性质的进出口数据（国有企业/外资企业/民营企业）
  - 贸易顺差/逆差
  - 同比/环比增长率

用途:
  - 评估出口依存度（出口额/营业收入）
  - 关税政策效果评估（DID分析）
  - 中美贸易摩擦研究
"""

from __future__ import annotations

import os
import json
import logging

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

API_KEY = os.environ.get("CHINESE_CUSTOMS_API_KEY", "")
BASE_URL = "https://stats.customs.gov.cn/api"

TOOLS: list[Tool] = [
    Tool(
        name="get_customs_import",
        description="查询中国海关进口数据。按HS编码、商品名称、贸易伙伴、月份等维度检索进口金额和数量。",
        inputSchema={
            "type": "object",
            "properties": {
                "hs_code": {"type": "string", "description": "HS商品编码（前6位，如847130=自动数据处理设备）"},
                "country": {"type": "string", "description": "贸易伙伴国家/地区代码（如USA、CHN、JPN）"},
                "province": {"type": "string", "description": "省份名称（如广东省、浙江省）"},
                "month_from": {"type": "string", "description": "起始月份（YYYY-MM）"},
                "month_to": {"type": "string", "description": "结束月份（YYYY-MM）"},
                "unit": {"type": "string", "default": "USD", "description": "金额单位：USD（美元）/CNY（人民币）/RMB"},
            },
        },
    ),
    Tool(
        name="get_customs_export",
        description="查询中国海关出口数据。按HS编码、商品名称、贸易伙伴、月份等维度检索出口金额和数量。",
        inputSchema={
            "type": "object",
            "properties": {
                "hs_code": {"type": "string", "description": "HS商品编码"},
                "country": {"type": "string", "description": "贸易伙伴国家/地区代码"},
                "province": {"type": "string", "description": "省份名称"},
                "month_from": {"type": "string", "description": "起始月份（YYYY-MM）"},
                "month_to": {"type": "string", "description": "结束月份（YYYY-MM）"},
                "unit": {"type": "string", "default": "USD"},
            },
        },
    ),
    Tool(
        name="get_customs_trade_balance",
        description="查询中国整体或特定商品/国家的贸易收支（出口-进口）。正值为顺差，负值为逆差。",
        inputSchema={
            "type": "object",
            "properties": {
                "hs_code": {"type": "string", "description": "HS商品编码（不填则返回总额）"},
                "country": {"type": "string", "description": "贸易伙伴国家/地区代码"},
                "year": {"type": "integer", "description": "年份"},
            },
        },
    ),
    Tool(
        name="get_customs_by_country",
        description="查询与特定国家/地区的双边贸易数据。包括进出口总额、贸易差额、主要商品构成。",
        inputSchema={
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "国家/地区代码（如USA、DEU、KOR）"},
                "year": {"type": "integer", "description": "年份"},
                "top_hs_codes": {"type": "integer", "default": 10, "description": "返回前N大商品"},
            },
        },
    ),
]


async def _make_request(url: str, params: dict) -> dict:
    """Make authenticated request to customs API."""
    if not API_KEY:
        return {
            "status": "warning",
            "message": "CHINESE_CUSTOMS_API_KEY not configured. Register at https://stats.customs.gov.cn",
            "data": [],
            "fallback": "Use user-tushare for A-share data, or provide manual customs data files in data/customs/",
        }
    
    import httpx
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params={k: v for k, v in params.items() if v is not None})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        _log.warning("[Customs] API call failed: %s", e)
        return {"status": "error", "message": str(e), "data": []}


async def handle_import(params: dict) -> dict:
    return await _make_request(f"{BASE_URL}/import", params)


async def handle_export(params: dict) -> dict:
    return await _make_request(f"{BASE_URL}/export", params)


async def handle_balance(params: dict) -> dict:
    return await _make_request(f"{BASE_URL}/balance", params)


async def handle_country(params: dict) -> dict:
    return await _make_request(f"{BASE_URL}/bilateral", params)


def create_server():
    server = Server("user-chinese-customs")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        handlers = {
            "get_customs_import": handle_import,
            "get_customs_export": handle_export,
            "get_customs_trade_balance": handle_balance,
            "get_customs_by_country": handle_country,
        }
        
        handler = handlers.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        try:
            result = await handler(arguments)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
        except Exception as e:
            _log.error("[Customs] Tool %s failed: %s", name, e)
            return [TextContent(type="text", text=json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))]
    
    return server


async def main():
    if not HAS_MCP:
        print("Chinese Customs MCP Server — 中国海关进出口数据")
        print(f"API Key configured: {'Yes' if API_KEY else 'No (set CHINESE_CUSTOMS_API_KEY)'}")
        return
    
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
