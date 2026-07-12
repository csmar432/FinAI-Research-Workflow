# Demo GIF 一键录制脚本 (audit_fix_2026_07_12)

> **目标**: 在 `~/.github/demo/demo.gif` 生成 ≤ 200KB, ≤ 800px 宽, 6-15 秒, monokai 主题
> **依赖**: `asciinema` + `agg` (本脚本自动检测, 缺失时给安装命令)
> **预期时长**: 10 min (含录制 + 转换 + 验证)

---

## 🎬 方案 A: asciinema + agg (推荐, 纯脚本)

### Step 1: 一键安装 (仅首次, ~30s)

```bash
# macOS (Homebrew)
brew install asciinema

# pip (agg)
python3 -m pip install --user agg
```

### Step 2: 一键录制脚本 (`scripts/_record_demo.sh`)

```bash
#!/usr/bin/env bash
# scripts/_record_demo.sh — 一键录制 FinAI demo GIF
# 依赖: asciinema (brew), agg (pip install agg)
# 输出: .github/demo/demo.cast + .github/demo/demo.gif

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
  echo "   brew install asciinema   # macOS"
  echo "   sudo apt install asciinema  # Ubuntu/Debian"
  exit 1
fi

if ! python3 -c "import agg" 2>/dev/null; then
  echo "❌ agg 未安装. 安装命令:"
  echo "   pip install agg"
  exit 1
fi

# 1. 录制 (≤ 15 秒)
echo "▶ 录制中 (15 秒倒计时, 执行下列命令演示):"
echo "   1) python3 scripts/health_check.py --json"
echo "   2) python3 scripts/count_assets.py"
echo "   3) python3 scripts/register_mcp_servers.py --list"
echo ""
echo "   (推荐终端尺寸: 100×30)"
echo ""

cd "$REPO_ROOT"

# -i 1: 实时录制, --cols 100 --rows 30: 标准 GitHub README 尺寸
asciinema rec \
  --title "FinAI Research Workflow — 30s demo" \
  --cols 100 \
  --rows 30 \
  --idle-time-limit 2 \
  --command "bash -c 'echo \"=== FinAI Research Workflow Demo ===\"; \
python3 scripts/health_check.py --compact 2>/dev/null | head -10; \
echo; \
python3 scripts/count_assets.py --compact 2>/dev/null | head -15; \
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

# 帧数 + 时长
DURATION=$(file "$GIF_FILE" | grep -oE "[0-9]+\.[0-9]+s" | head -1 || echo "?")
echo "  时长: $DURATION (目标 6-15s)"

echo ""
echo "✅ 完成. 提交:"
echo "   cd $REPO_ROOT"
echo "   git add .github/demo/demo.cast .github/demo/demo.gif"
echo "   git commit -m 'feat(demo): record asciinema + agg GIF'"
echo "   git push"
```

### Step 3: 使用

```bash
# 添加可执行权限
chmod +x scripts/_record_demo.sh

# 一键录制 (脚本会提示)
./scripts/_record_demo.sh

# 或者, 手动单步录制 (更灵活):
asciinema rec --title "FinAI" --cols 100 --rows 30 \
  --command "bash" .github/demo/demo.cast
# 在 bash 中执行命令, Ctrl-D 退出

agg --theme monokai .github/demo/demo.cast .github/demo/demo.gif
```

---

## 📊 推荐参数表

| 参数 | 值 | 理由 |
|------|----|----|
| 终端尺寸 | 100 × 30 | GitHub README 渲染最佳 |
| 字体大小 | 14 px | 可读性 + 文件大小平衡 |
| 帧率 (agg) | 默认 (≈10 fps) | GitHub 平台优化 |
| 空闲时长限制 | 2 秒 | 消除长等待停顿 |
| 主题 | monokai | 高对比 + 好看 |
| 录制时长 | 6-15 秒 | 用户注意力上限 |
| 输出大小 | ≤ 200 KB | README 加载友好 |
| 循环 | 启用 | 用户无需手动重播 |

---

## 🔧 高级: 多场景录制 (备选)

如果想录制更长的演示 (如完整 agent pipeline):

```bash
# 1. 录制 4 个 15 秒片段
for i in 1 2 3 4; do
  asciinema rec --title "FinAI Scene $i" --cols 100 --rows 30 \
    .github/demo/scene-$i.cast
done

# 2. 用 svg-term 拼接 (需 npm)
npm install -g svg-term

for i in 1 2 3 4; do
  svg-term --cast .github/demo/scene-$i.cast \
    --out .github/demo/scene-$i.svg \
    --width 800 --height 450
done

# 3. 用 ImageMagick 拼接 GIF (需 brew install imagemagick)
convert -delay 100 -loop 0 \
  .github/demo/scene-*.svg \
  .github/demo/demo.gif
```

> ⚠️ **不推荐**: 多片段拼接会显著增加文件大小 (经常 > 1MB), 违反 README 友好性原则.

---

## 🆘 应急

| 问题 | 解决方案 |
|------|----------|
| asciinema 录出来过长 (>30s) | 加 `--idle-time-limit 2` 自动截断 |
| agg 转换慢 | 先 `--speed 2.0` 加速, 转换后用户可自行调整 |
| GIF 文件大 (>500KB) | 减小 `--font-size` 到 12, 或减小 `--cols` 到 80 |
| 中文乱码 | 安装 `fonts-noto-cjk` 或 `wqy-microhei` |
| 不想装 asciinema | 用方案 B: Kap (macOS GUI) |

---

## 备选方案 B: Kap (macOS GUI, 30s)

```bash
brew install --cask kap
```

1. 打开 Kap → 选择窗口 (或全屏)
2. 点录制按钮 (圆形)
3. 执行: `python3 scripts/health_check.py --compact`
4. 停止录制 → 导出为 `docs/assets/demo.gif`

**优点**: 0 安装麻烦, 可加鼠标高亮
**缺点**: 不能脚本化, 文件通常 ≥ 1MB

---

## 备选方案 C: ttyd + 浏览器录制 (no install)

```bash
# 1. 启动 web terminal
pip install ttyd
ttyd --port 7681 python3 -c "
print('=== FinAI Demo ===')
exec(open('scripts/health_check.py').read())
"
# 打开浏览器 http://localhost:7681

# 2. 用浏览器扩展录制 (Loom / Screencastify)
```

---

## 嵌入 README (录制完成后)

将以下代码块添加到 `README.md` 顶部 (在 Quick Start 部分之后):

```markdown
![Quick Demo](.github/demo/demo.gif)

> ⏱️ 6-15 秒看完: 系统诊断 + 资产统计 + MCP 列表. 真实终端录制 (asciinema).
```

---

## ✅ 完成检查清单

- [ ] GIF 文件生成在 `.github/demo/demo.gif`
- [ ] 大小 ≤ 200 KB
- [ ] 宽度 ≤ 800 px
- [ ] 时长 6-15 秒
- [ ] 主题 monokai (高对比)
- [ ] 已在 README 中嵌入 (Quick Start 之后)
- [ ] Git LFS 配置 (可选, > 100KB 时建议): `git lfs track "*.gif"`
- [ ] 已 commit + push

---

**脚本文件**: `scripts/_record_demo.sh` (本脚本导出)
**输出**: `.github/demo/demo.cast` (源) + `.github/demo/demo.gif` (成品)
**总耗时**: 10 min (含首次安装)