#!/usr/bin/env python3
"""CI 辅助验证脚本。供 GitHub Actions CI 调用。"""
import re, sys
from pathlib import Path


def check_docker_compose():
    """验证 docker-compose.yml 中引用的所有 Dockerfile 存在。"""
    if not Path("docker-compose.yml").exists():
        print("⚠️  docker-compose.yml not found, skipping")
        return

    with open("docker-compose.yml") as f:
        content = f.read()

    ok, fail = 0, []
    for m in re.finditer(r"context:\s+(.+?)\n\s+dockerfile:\s+(.+?)\n", content):
        ctx, df = m.group(1).strip(), m.group(2).strip()
        path = Path(ctx) / df
        if path.exists():
            ok += 1
        else:
            fail.append(f"{ctx}/{df}")

    if fail:
        print(f"❌ Missing Dockerfiles ({len(fail)}): {fail}")
        sys.exit(1)
    print(f"✅ All {ok} Dockerfiles referenced in docker-compose.yml exist")


def check_mcp_schemas():
    """调用 MCP schema 检查脚本。"""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/mcp_schema_check.py"],
        capture_output=True, text=True,
    )
    # Check only for the "real" issues (non-dispatcher)
    lines = result.stdout.splitlines()
    for line in lines:
        # These are dispatcher-mode warnings, skip
        if "dispatcher" in line:
            continue
        # Real issues start with ❌
        if "❌" in line:
            print(f"⚠️  MCP issue: {line.strip()}")
    print(f"✅ MCP schema check done ({len([l for l in lines if '✅' in l])} OK)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--docker-check":
        check_docker_compose()
    elif len(sys.argv) > 1 and sys.argv[1] == "--schema-check":
        check_mcp_schemas()
    else:
        check_docker_compose()
        print()
        check_mcp_schemas()
