#!/usr/bin/env python3
"""Third-Party ESG MCP Server — 第三方ESG评级数据

数据来源:
  - 商道融绿 (SynTao) ESG评级: https://www.syntao.com
  - 华证指数 (CSI) ESG评级: http://www.csi.com.cn
  - 中证ESG评分: http://www.csindex.com.cn
  - 富时ESG评级（境外）

数据覆盖:
  - ESG综合评分（E/S/G三个维度）
  - ESG评级（AAA-C）
  - ESG争议事件
  - ESG排名（行业/全市场）
  - 碳排放数据（E维度）
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

SYNTAO_KEY = os.environ.get("SYNTAO_API_KEY", "")
CSI_KEY = os.environ.get("CSI_ESG_API_KEY", "")
CUSTOM_KEY = os.environ.get("THIRD_PARTY_ESG_KEY", "")

TOOLS: list[Tool] = [
    Tool(
        name="get_esg_rating",
        description="获取企业ESG综合评分和评级。支持商道融绿、华证、中证、富时等多家评级机构。返回E/S/G分项得分及综合评级。",
        inputSchema={
            "type": "object",
            "properties": {
                "stock_code": {"type": "string", "description": "股票代码（如000001.SZ）"},
                "company_name": {"type": "string", "description": "公司名称（与股票代码二选一）"},
                "provider": {"type": "string", "enum": ["syntao", "csi", "csi_esg", "ftse", "all"], "default": "all", "description": "评级机构"},
                "year": {"type": "integer", "description": "评级年份（默认最新）"},
                "include_subscores": {"type": "boolean", "default": True, "description": "是否包含E/S/G分项得分"},
            },
        },
    ),
    Tool(
        name="get_esg_trend",
        description="获取企业ESG评分历史趋势数据。展示近5年ESG得分变化，支持与行业均值对比。",
        inputSchema={
            "type": "object",
            "properties": {
                "stock_code": {"type": "string", "description": "股票代码"},
                "company_name": {"type": "string", "description": "公司名称"},
                "years": {"type": "integer", "default": 5, "description": "返回年份数"},
            },
        },
    ),
    Tool(
        name="get_esg_controversy",
        description="查询企业ESG相关争议事件。覆盖环境处罚、劳动纠纷、治理违规、财务造假等负面事件。",
        inputSchema={
            "type": "object",
            "properties": {
                "stock_code": {"type": "string", "description": "股票代码"},
                "event_type": {"type": "string", "enum": ["environmental", "social", "governance", "financial", "all"], "default": "all"},
                "severity": {"type": "string", "enum": ["high", "medium", "low", "all"], "default": "all"},
                "start_date": {"type": "string", "description": "事件日期起（YYYY-MM-DD）"},
                "end_date": {"type": "string", "description": "事件日期止（YYYY-MM-DD）"},
            },
        },
    ),
    Tool(
        name="get_esg_ranking",
        description="获取ESG评分全市场排名或行业排名。",
        inputSchema={
            "type": "object",
            "properties": {
                "market": {"type": "string", "enum": ["A-share", "CSI300", "CSI500", "CSI800", "all"], "default": "all"},
                "industry": {"type": "string", "description": "行业名称（如制造业、金融）"},
                "year": {"type": "integer", "description": "年份"},
                "top_n": {"type": "integer", "default": 100, "description": "返回前N名"},
            },
        },
    ),
]


def _check_credentials() -> dict:
    """Check if any ESG API key is configured."""
    if not (SYNTAO_KEY or CSI_KEY or CUSTOM_KEY):
        return {
            "status": "warning",
            "message": "No ESG API key configured. Set SYNTAO_API_KEY, CSI_ESG_API_KEY, or THIRD_PARTY_ESG_KEY environment variable.",
            "fallback_suggestion": "Use user-yfinance for ESG-related data, or provide manual ESG data files in data/esg/ directory.",
        }
    return {}


async def handle_esg_rating(params: dict) -> dict:
    cred = _check_credentials()
    if cred:
        return cred
    
    import httpx
    
    provider = params.get("provider", "all")
    
    if provider in ("syntao", "all") and SYNTAO_KEY:
        url = "https://api.syntao.com/esg/rating"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {SYNTAO_KEY}"},
                    params={k: v for k, v in params.items() if k != "provider" and v is not None},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            _log.warning("[ESG] SynTao API failed: %s", e)
    
    if provider in ("csi", "all") and CSI_KEY:
        url = "https://api.csi.com.cn/esg/rating"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url,
                    headers={"X-API-Key": CSI_KEY},
                    params={k: v for k, v in params.items() if k != "provider" and v is not None},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            _log.warning("[ESG] CSI ESG API failed: %s", e)
    
    return {
        "status": "warning",
        "message": "No configured ESG API key returned data. Configure SYNTAO_API_KEY or CSI_ESG_API_KEY.",
        "data": {},
    }


async def handle_esg_trend(params: dict) -> dict:
    cred = _check_credentials()
    if cred:
        return cred
    
    import httpx
    
    if SYNTAO_KEY:
        url = "https://api.syntao.com/esg/trend"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {SYNTAO_KEY}"},
                    params=params,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            _log.warning("[ESG] Trend API failed: %s", e)
    
    return {"status": "warning", "message": "ESG trend data requires SYNTAO_API_KEY.", "data": []}


async def handle_esg_controversy(params: dict) -> dict:
    cred = _check_credentials()
    if cred:
        return cred
    
    import httpx
    
    if CUSTOM_KEY:
        url = "https://api.esgdata.com/controversy"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {CUSTOM_KEY}"},
                    params={k: v for k, v in params.items() if v is not None},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            _log.warning("[ESG] Controversy API failed: %s", e)
    
    return {"status": "warning", "message": "ESG controversy data requires THIRD_PARTY_ESG_KEY.", "data": []}


async def handle_esg_ranking(params: dict) -> dict:
    cred = _check_credentials()
    if cred:
        return cred
    
    import httpx
    
    if CSI_KEY:
        url = "http://www.csi.com.cn/api/esg/ranking"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url,
                    headers={"X-API-Key": CSI_KEY},
                    params={k: v for k, v in params.items() if v is not None},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            _log.warning("[ESG] Ranking API failed: %s", e)
    
    return {"status": "warning", "message": "ESG ranking requires CSI_ESG_API_KEY.", "data": []}


def create_server():
    server = Server("user-third-party-esg")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        handlers = {
            "get_esg_rating": handle_esg_rating,
            "get_esg_trend": handle_esg_trend,
            "get_esg_controversy": handle_esg_controversy,
            "get_esg_ranking": handle_esg_ranking,
        }
        
        handler = handlers.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        try:
            result = await handler(arguments)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
        except Exception as e:
            _log.error("[ESG] Tool %s failed: %s", name, e)
            return [TextContent(type="text", text=json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))]
    
    return server


async def main():
    if not HAS_MCP:
        print("Third-Party ESG MCP Server — 第三方ESG评级数据")
        print(f"SynTao Key: {'Yes' if SYNTAO_KEY else 'No (set SYNTAO_API_KEY)'}")
        print(f"CSI ESG Key: {'Yes' if CSI_KEY else 'No (set CSI_ESG_API_KEY)'}")
        return
    
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
