#!/usr/bin/env python3
"""
OpenAlex MCP Server
===================
OpenAlex 学术论文元数据搜索服务。

数据源：OpenAlex API（无需 API Key，完全免费，无速率限制）
覆盖：2亿+ 学术成果（论文、预印本、书籍、会议论文）

Usage:
    python server.py
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.request
import urllib.parse
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("openalex_mcp")

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

server = Server("user-openalex")
_API_BASE = "https://api.openalex.org"

TOOLS = [
    Tool(
        name="get_openalex_works",
        description="OpenAlex 学术论文元数据搜索。OpenAlex 是全球最大的开放学术知识图谱，涵盖2亿+论文、作者、机构。完全免费，无需 API Key。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询词（支持布尔搜索、过滤器）"},
                "per_page": {"type": "integer", "description": "每页结果数（最大200）", "default": 25},
                "page": {"type": "integer", "description": "页码", "default": 1},
                "filter": {"type": "string", "description": "过滤条件（如 type:article, year:2024, is_open_access:true）"},
                "sort": {"type": "string", "description": "排序字段", "default": "cited_by_count:desc"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_openalex_authors",
        description="OpenAlex 作者搜索。无需 API Key。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "作者姓名"},
                "per_page": {"type": "integer", "description": "每页结果数", "default": 10},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_openalex_institutions",
        description="OpenAlex 机构搜索。无需 API Key。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "机构名称"},
                "per_page": {"type": "integer", "description": "每页结果数", "default": 10},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_openalex_author",
        description="获取作者信息及其发表成果。无需 API Key。",
        inputSchema={
            "type": "object",
            "properties": {
                "author_id": {"type": "string", "description": "OpenAlex 作者 ID"},
            },
            "required": ["author_id"],
        },
    ),
    Tool(
        name="get_openalex_concepts",
        description="获取主题概念树（用于发现研究领域层次结构）。无需 API Key。",
        inputSchema={
            "type": "object",
            "properties": {
                "concept_id": {"type": "string", "description": "概念 ID（如 C168846120）"},
            },
            "required": ["concept_id"],
        },
    ),
    Tool(
        name="get_openalex_works_by_author",
        description="获取特定作者的所有发表成果（通过作者ID查询）。无需 API Key。",
        inputSchema={
            "type": "object",
            "properties": {
                "author_id": {"type": "string", "description": "OpenAlex 作者 ID（如 A123456789）"},
                "per_page": {"type": "integer", "description": "每页结果数（最大200）", "default": 25},
            },
            "required": ["author_id"],
        },
    ),
]


def _clean_work(w: dict) -> dict:
    """清洗OpenAlex论文数据"""
    return {
        "id": w.get("id", ""),
        "title": w.get("title", ""),
        "display_name": w.get("display_name", ""),
        "publication_year": w.get("publication_year", ""),
        "type": w.get("type", ""),
        "doi": w.get("doi", ""),
        "cited_by_count": w.get("cited_by_count", 0),
        "open_access": w.get("open_access", {}).get("is_oa", False),
        "authors": [
            {"name": a.get("display_name", ""), "id": a.get("id", "")}
            for a in w.get("authorships", [])[:10]  # 只取前10个作者
        ],
        "concepts": [c.get("display_name", "") for c in w.get("concepts", [])[:5]],
        "publicationvenue": w.get("primary_location", {}).get("source", {}).get("display_name", ""),
        "url": w.get("doi", ""),
    }


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    def _fetch(url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": "FinResearch-Agent/1.0 (mailto:research@example.com)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except json.JSONDecodeError as e:
            log.warning(f"OpenAlex JSON decode error for URL {url[:50]}: {e}")
            return {}

    try:
        if name == "get_openalex_works":
            query = arguments.get("query", "")
            per_page = min(arguments.get("per_page", 25), 200)
            page = arguments.get("page", 1)
            filter_str = arguments.get("filter", "")
            sort = arguments.get("sort", "cited_by_count:desc")

            params = [f"search={urllib.parse.quote_plus(query)}"]
            params.append(f"per_page={per_page}")
            params.append(f"page={page}")
            params.append(f"sort={sort}")
            if filter_str:
                params.append(f"filter={filter_str}")

            url = f"{_API_BASE}/works?{'&'.join(params)}"
            data = _fetch(url)

            works = [_clean_work(w) for w in data.get("results", [])]

            meta = {
                "total": data.get("meta", {}).get("count", 0),
                "page": page,
                "per_page": per_page,
                "next_page": data.get("meta", {}).get("next_cursor", None),
            }
            return [TextContent(type="text", text=json.dumps({"meta": meta, "works": works}, ensure_ascii=False, indent=2))]

        elif name == "get_openalex_authors":
            query = arguments.get("query", "")
            per_page = min(arguments.get("per_page", 10), 100)
            url = f"{_API_BASE}/authors?search={urllib.parse.quote_plus(query)}&per_page={per_page}"
            data = _fetch(url)
            authors = [{
                "id": a.get("id", "").split("/")[-1],
                "display_name": a.get("display_name", ""),
                "works_count": a.get("works_count", 0),
                "cited_by_count": a.get("cited_by_count", 0),
                "orcid": a.get("orcid", ""),
                "affiliations": [inst.get("display_name", "") for inst in a.get("institutions", [])[:3]],
            } for a in data.get("results", [])]
            return [TextContent(type="text", text=json.dumps(authors, ensure_ascii=False, indent=2))]

        elif name == "get_openalex_institutions":
            query = arguments.get("query", "")
            per_page = min(arguments.get("per_page", 10), 100)
            url = f"{_API_BASE}/institutions?search={urllib.parse.quote_plus(query)}&per_page={per_page}"
            data = _fetch(url)
            institutions = [{
                "id": i.get("id", "").split("/")[-1],
                "display_name": i.get("display_name", ""),
                "country_code": i.get("country_code", ""),
                "type": i.get("type", ""),
                "works_count": i.get("works_count", 0),
            } for i in data.get("results", [])]
            return [TextContent(type="text", text=json.dumps(institutions, ensure_ascii=False, indent=2))]

        elif name == "get_openalex_author":
            author_id = arguments.get("author_id", "")
            if not author_id:
                return [TextContent(type="text", text="author_id is required")]
            url = f"{_API_BASE}/authors/{author_id}"
            data = _fetch(url)
            author = {
                "id": data.get("id", "").split("/")[-1],
                "display_name": data.get("display_name", ""),
                "orcid": data.get("orcid", ""),
                "works_count": data.get("works_count", 0),
                "cited_by_count": data.get("cited_by_count", 0),
                "h_index": data.get("h_index", 0),
                "last_known_institution": (
                    data.get("last_known_institution", {}).get("display_name", "") if data.get("last_known_institution") else ""
                ),
                "topics": [
                    {"display_name": t.get("display_name", ""), "score": t.get("score", 0)}
                    for t in data.get("topics", [])[:10]
                ],
                "counts_by_year": data.get("counts_by_year", [])[:5],
            }
            return [TextContent(type="text", text=json.dumps(author, ensure_ascii=False, indent=2))]

        elif name == "get_openalex_concepts":
            concept_id = arguments.get("concept_id", "")
            per_page = min(arguments.get("per_page", 10), 100)
            if concept_id:
                url = f"{_API_BASE}/concepts/{concept_id}"
                data = _fetch(url)
                concept = {
                    "id": data.get("id", "").split("/")[-1],
                    "display_name": data.get("display_name", ""),
                    "level": data.get("level", 0),
                    "description": data.get("description", ""),
                    "works_count": data.get("works_count", 0),
                    "cited_by_count": data.get("cited_by_count", 0),
                    "ancestors": [a.get("display_name", "") for a in data.get("ancestors", [])],
                    "descendants": [d.get("display_name", "") for d in data.get("descendants", [])[:5]],
                }
                return [TextContent(type="text", text=json.dumps(concept, ensure_ascii=False, indent=2))]
            else:
                url = f"{_API_BASE}/concepts?per_page={per_page}&filter=level:2"
                data = _fetch(url)
                concepts = [{
                    "id": c.get("id", "").split("/")[-1],
                    "display_name": c.get("display_name", ""),
                    "level": c.get("level", 0),
                    "description": c.get("description", ""),
                    "works_count": c.get("works_count", 0),
                } for c in data.get("results", [])]
                return [TextContent(type="text", text=json.dumps(concepts, ensure_ascii=False, indent=2))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except urllib.error.HTTPError as e:
        return [TextContent(type="text", text=f"HTTP Error {e.code}: {e.reason}")]
    except Exception as e:
        log.error(f"OpenAlex error in {name}: {e}")
        return [TextContent(type="text", text=f"OpenAlex error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
