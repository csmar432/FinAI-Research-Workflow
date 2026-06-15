#!/usr/bin/env bash
# scripts/check_latex.sh
# 用法:
#   bash scripts/check_latex.sh                     # 编译 output/ 下所有 .tex
#   bash scripts/check_latex.sh path/to/paper.tex   # 编译指定文件
# 退出码: 0=全部成功, 1=有失败

set -uo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
NC=$'\033[0m'

log()   { echo "[$(date +%H:%M:%S)] $*"; }
ok()    { echo "${GREEN}✓${NC} $*"; }
warn()  { echo "${YELLOW}⚠${NC} $*"; }
err()   { echo "${RED}✗${NC} $*"; }

# 收集 .tex 文件
if [ $# -gt 0 ]; then
    TEX_FILES=("$@")
else
    mapfile -t TEX_FILES < <(find output/ -name "*.tex" -type f 2>/dev/null | sort)
fi

if [ ${#TEX_FILES[@]} -eq 0 ]; then
    warn "No .tex files to check"
    exit 0
fi

log "Found ${#TEX_FILES[@]} LaTeX file(s) to check"
echo ""

PASS=0
FAIL=0
FAILED_FILES=()

for TEX in "${TEX_FILES[@]}"; do
    [ -f "$TEX" ] || continue
    DIR=$(dirname "$TEX")
    BASENAME=$(basename "$TEX" .tex)

    log "Checking: $TEX"

    # 跳过明显不是主文档的 (如 preamble.tex, settings.tex)
    if [[ "$BASENAME" == "preamble" || "$BASENAME" == "settings" || "$BASENAME" == "macros" ]]; then
        warn "  Skipped (auxiliary file)"
        continue
    fi

    cd "$PROJECT_ROOT/$DIR" || continue

    # 标准 4 步编译: pdflatex -> bibtex -> pdflatex -> pdflatex
    cp /dev/null "${BASENAME}.log" 2>/dev/null || true
    cp /dev/null "${BASENAME}.blg" 2>/dev/null || true

    # 第 1 遍 pdflatex
    pdflatex -interaction=nonstopmode -halt-on-error "$BASENAME.tex" > /dev/null 2>&1
    RC1=$?

    # bibtex (如果 .aux 存在且包含 \citation 或 \bibdata)
    if [ -f "${BASENAME}.aux" ] && grep -qE "\\\\citation|\\\\bibdata" "${BASENAME}.aux" 2>/dev/null; then
        bibtex "$BASENAME" > /dev/null 2>&1 || true
    fi

    # 第 2、3 遍 pdflatex (解析引用)
    pdflatex -interaction=nonstopmode -halt-on-error "$BASENAME.tex" > /dev/null 2>&1
    RC2=$?
    pdflatex -interaction=nonstopmode -halt-on-error "$BASENAME.tex" > /dev/null 2>&1
    RC3=$?

    # 检查是否生成了 PDF
    if [ -f "${BASENAME}.pdf" ] && [ -s "${BASENAME}.pdf" ]; then
        ok "  $BASENAME.pdf compiled ($(stat -f%z "${BASENAME}.pdf" 2>/dev/null || stat -c%s "${BASENAME}.pdf") bytes)"
        PASS=$((PASS+1))
    else
        err "  Compile FAILED for $BASENAME"
        # 输出错误信息
        if [ -f "${BASENAME}.log" ]; then
            grep -E "^!|Error|error" "${BASENAME}.log" 2>/dev/null | head -5 | sed 's/^/    /'
        fi
        FAIL=$((FAIL+1))
        FAILED_FILES+=("$TEX")
    fi

    cd "$PROJECT_ROOT"
done

echo ""
echo "================================================"
log "Result: $PASS passed, $FAIL failed"

if [ $FAIL -gt 0 ]; then
    err "Failed files:"
    for f in "${FAILED_FILES[@]}"; do
        echo "  - $f"
    done
    exit 1
fi

ok "All LaTeX files compiled successfully"
exit 0
