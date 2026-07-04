#!/usr/bin/env python3
"""
patch_mock_servers.py
=====================
Auto-injects mock-data confirmation into all MCP server files using `ast`.

REPLACES the original regex-based implementation (audit fix 2026-06-24):
  - Old: regex string matching (fragile, broken by whitespace/formatting changes)
  - New: Python ast.NodeTransformer (correct, handles all valid Python syntax)

流程:
    1. Parse server.py with ast
    2. Add mcp_mock_helper import (if not present)
    3. Append MOCK_WARNING to Tool.description strings
    4. Prepend check_mock_permission() call to each handler body
    5. Unparse back to source and write (after creating .bak backup)

用法:
    cd /path/to/mcp_servers
    python patch_mock_servers.py [--dry-run]
"""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MCP_SERVERS_DIR = SCRIPT_DIR

MOCK_SERVERS = [
    "user_fed_data",
    "user_oecd_data",
    "user_imf_data",
    "user_nber_wp",
    "user_csmar",
    "user_eastmoney_option",
    "user_bea_data",
    "user_eastmoney_bond",
    "user_eastmoney_fund",
    "user_macro_ceic",
    "user_wind",
    "user_eodhd",
]

SERVER_DISPLAY_NAMES = {
    "user_fed_data": "user-fed-data",
    "user_oecd_data": "user-oecd-data",
    "user_imf_data": "user-imf-data",
    "user_nber_wp": "user-nber-wp",
    "user_csmar": "user-csmar",
    "user_eastmoney_option": "user-eastmoney-option",
    "user_bea_data": "user-bea-data",
    "user_eastmoney_bond": "user-eastmoney-bond",
    "user_eastmoney_fund": "user-eastmoney-fund",
    "user_macro_ceic": "user-macro-ceic",
    "user_wind": "user-wind",
    "user_eodhd": "user-eodhd",
}

MOCK_WARNING_TEXT = (
    "\\n\\n[模拟数据警告] 此工具返回的是演示/模拟数据，非真实API数据。"
    " 数据不代表真实市场情况，如需真实数据请：\\n"
    "  1. 配置相应的 API Key\\n"
    "  2. 或使用同类无Key工具（如 user-financial）\\n"
    "  3. 或使用 user-playwright-mcp 从网页直接抓取\\n"
)


# ─── AST transformers ───────────────────────────────────────────────────────────

class MockImportInserter(ast.NodeTransformer):
    """Add mcp_mock_helper import if not already present."""

    def visit_Module(self, node: ast.Module) -> ast.Module:
        # Check if already imported
        for child in ast.walk(node):
            if isinstance(child, ast.ImportFrom):
                if child.module and "mcp_mock_helper" in child.module:
                    return node  # already imported, skip
        # Find last import node (ast-wise) to insert after
        import_nodes = [
            n for n in node.body
            if isinstance(n, (ast.Import, ast.ImportFrom))
        ]
        if import_nodes:
            last_import = import_nodes[-1]
            idx = node.body.index(last_import)
        else:
            idx = 0  # insert at top if no imports

        import_node = ast.ImportFrom(
            module=str(MCP_SERVERS_DIR / "mcp_mock_helper"),
            names=[
                ast.alias(name="check_mock_permission", asname=None),
                ast.alias(name="MOCK_WARNING", asname=None),
            ],
            level=0,
        )
        node.body.insert(idx + 1, import_node)
        return node


class ToolWarningAppender(ast.NodeTransformer):
    """Append MOCK_WARNING_TEXT to every Tool() call's description keyword."""

    def visit_Call(self, node: ast.Call) -> ast.Call:
        # Process children first (recursive)
        self.generic_visit(node)
        # Check if this is a Tool() call
        if not (isinstance(node.func, ast.Name) and node.func.id == "Tool"):
            return node
        for kw in node.keywords:
            if kw.arg == "description":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    kw.value = ast.Constant(
                        value=kw.value.value + MOCK_WARNING_TEXT
                    )
        return node


class HandlerGuardInserter(ast.NodeTransformer):
    """Prepend check_mock_permission() guard to each handle_xxx async function body."""

    def __init__(self, server_name: str) -> None:
        self.server_name = server_name
        self.display_name = SERVER_DISPLAY_NAMES.get(server_name, server_name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        if not node.name.startswith("handle_"):
            self.generic_visit(node)
            return node

        guard = ast.If(
            test=ast.Call(
                func=ast.Name(id="check_mock_permission", ctx=ast.Load()),
                args=[
                    ast.Name(id="args", ctx=ast.Load()),
                    ast.Constant(value=node.name),
                    ast.Constant(value=self.display_name),
                ],
                keywords=[],
            ),
            body=[
                ast.Return(
                    value=ast.Call(
                        func=ast.Name(id="check_mock_permission", ctx=ast.Load()),
                        args=[
                            ast.Name(id="args", ctx=ast.Load()),
                            ast.Constant(value=node.name),
                            ast.Constant(value=self.display_name),
                        ],
                        keywords=[],
                    ),
                ),
            ],
            orelse=[],
        )

        # Insert guard as first statement (after any docstring)
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            # docstring present: insert after it
            node.body.insert(1, guard)
        else:
            node.body.insert(0, guard)

        self.generic_visit(node)
        return node

    visit_FunctionDef = visit_AsyncFunctionDef  # sync def (fallback)


# ─── Backup ─────────────────────────────────────────────────────────────────────

def create_backup(server_file: Path) -> Path | None:
    """Create a .bak backup before patching. Returns path to backup, or None on failure."""
    bak = server_file.with_suffix(".py.bak")
    try:
        shutil.copy2(server_file, bak)
        return bak
    except OSError as e:
        print(f"  ! Backup failed: {e}")
        return None


# ─── Main patcher ─────────────────────────────────────────────────────────────

def patch_server(server_dir: Path, dry_run: bool = False) -> bool:
    """Patch a single server's server.py using ast transformers."""
    server_file = server_dir / "server.py"
    if not server_file.exists():
        print(f"  ! server.py not found: {server_file}")
        return False

    try:
        source = server_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(server_file))
    except SyntaxError as e:
        print(f"  ! Parse error in {server_file}: {e}")
        return False

    ast.unparse(tree)

    # Apply transformers in order
    transformers = [
        ("import", MockImportInserter()),
        ("tool warning", ToolWarningAppender()),
        ("handler guard", HandlerGuardInserter(server_dir.name)),
    ]

    patched = tree
    for label, transformer in transformers:
        patched = ast.fix_missing_locations(transformer.visit(patched))

    if not dry_run:
        bak = create_backup(server_file)
        if bak is None:
            print(f"  ! Skipping write due to backup failure")
            return False

        new_source = ast.unparse(patched)
        server_file.write_text(new_source, encoding="utf-8")
        print(f"  ✓ {server_file.name} patched (backup: {bak.name})")
    else:
        print(f"  ✓ [dry-run] {server_file.name} — {len(transformers)} transformers would apply")
    return True


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("MCP Mock Server Confirmation — AST-based patcher")
    print(f"Mode: {'DRY RUN (no writes)' if dry_run else 'LIVE (writes .py + creates .py.bak)'}")
    print(f"Servers to patch: {len(MOCK_SERVERS)}")
    print("=" * 60)

    success = 0
    for name in MOCK_SERVERS:
        server_dir = MCP_SERVERS_DIR / name
        print(f"\n[{name}/]")
        if not server_dir.is_dir():
            print(f"  ! Directory not found, skipping")
            continue
        if patch_server(server_dir, dry_run=dry_run):
            success += 1

    print(f"\n{'[dry-run] Would patch' if dry_run else 'Patched'} {success}/{len(MOCK_SERVERS)} servers")


if __name__ == "__main__":
    main()
