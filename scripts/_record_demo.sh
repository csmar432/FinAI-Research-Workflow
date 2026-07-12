#!/usr/bin/env bash
# scripts/_record_demo.sh — 一键录制 FinAI demo GIF
# 依赖: asciinema (brew), agg (pip install agg)
# 输出: .github/demo/demo.cast + .github/demo/demo.gif
# 文档: scripts/_record_demo.sh.md

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_DIR="$REPO_ROOT/.github/demo"
CAST_FILE="$DEMO_DIR/demo.cast"
GIF_FILE="$DEMO_DIR/demo.gif"

mkdir -p "$DEMO_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  FinAI Demo GIF Recorder (asciinema + agg)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 0. 依赖检测
if ! command -v asciinema >/dev/null 2>&1; then
  echo "❌ asciinema 未安装. 安装命令:"
  echo "   brew install asciinema          # macOS"
  echo "   sudo apt install asciinema      # Ubuntu/Debian"
  exit 1
fi

if ! python3 -c "import agg" 2>/dev/null; then
  echo "❌ agg 未安装. 安装命令:"
  echo "   pip install agg"
  exit 1
fi

# 1. 录制 (≤ 15 秒)
echo "▶ 录制中 (15 秒倒计时, 执行下列命令演示):"
echo "   1) python3 scripts/health_check.py --compact"
echo "   2) python3 scripts/count_assets.py --markdown"
echo "   3) python3 scripts/register_mcp_servers.py --list 2>/dev/null | head -10"
echo ""
echo "   (推荐终端尺寸: 100×30)"
echo ""

cd "$REPO_ROOT"

asciinema rec \
  --title "FinAI Research Workflow — 30s demo" \
  --cols 100 \
  --rows 30 \
  --idle-time-limit 2 \
  --command "bash -c 'echo \"=== FinAI Research Workflow Demo ===\"; \
python3 scripts/health_check.py --compact 2>/dev/null | head -10; \
echo; \
python3 scripts/count_assets.py --markdown 2>/dev/null | head -15; \
echo; \
echo \"Try: python3 scripts/agent_pipeline.py --topic \\\"your topic\\\"\"'" \
  "$CAST_FILE"

echo ""
echo "✅ 录制完成: $CAST_FILE"

# 2. 转换为 GIF
echo "▶ 转换 GIF (monokai 主题)..."
agg \
  --theme monokai \
  --font-size 14 \
  --line-height 1.4 \
  --speed 1.0 \
  --idle-time-limit 2 \
  "$CAST_FILE" \
  "$GIF_FILE"

echo "✅ GIF 生成: $GIF_FILE"

# 3. 验证
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  验证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 大小
SIZE=$(stat -f %z "$GIF_FILE" 2>/dev/null || stat -c %s "$GIF_FILE")
SIZE_KB=$((SIZE / 1024))
echo "  文件大小: ${SIZE_KB} KB (目标 ≤ 200 KB)"

# 尺寸 (macOS 用 sips, Linux 用 file)
if command -v sips >/dev/null 2>&1; then
  W=$(sips -g pixelWidth "$GIF_FILE" 2>/dev/null | awk '/pixelWidth/ {print $2}')
  H=$(sips -g pixelHeight "$GIF_FILE" 2>/dev/null | awk '/pixelHeight/ {print $2}')
  echo "  尺寸: ${W}×${H} (目标 ≤ 800px 宽)"
fi

# 类型
FILE_TYPE=$(file "$GIF_FILE" | cut -d: -f2)
echo "  类型: $FILE_TYPE"

echo ""
echo "✅ 完成. 提交:"
echo "   cd $REPO_ROOT"
echo "   git add .github/demo/demo.cast .github/demo/demo.gif"
echo "   git commit -m 'feat(demo): record asciinema + agg GIF'"
echo "   git push"