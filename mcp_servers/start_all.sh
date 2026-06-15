#!/usr/bin/env bash
# =============================================================================
# MCP 一键启动脚本 — mcp_servers/start_all.sh
#
# 功能：使用 docker-compose 一键启动所有 MCP 数据服务器
#
# 使用方法：
#   ./mcp_servers/start_all.sh              # 启动所有服务
#   ./mcp_servers/start_all.sh --stop       # 停止所有服务
#   ./mcp_servers/start_all.sh --restart    # 重启所有服务
#   ./mcp_servers/start_all.sh --status     # 查看服务状态
#   ./mcp_servers/start_all.sh --logs       # 查看所有日志
#   ./mcp_servers/start_all.sh --health     # 健康检查
#
#   # 按类别启动（减少资源占用）
#   ./mcp_servers/start_all.sh --group finance    # 仅启动金融数据服务
#   ./mcp_servers/start_all.sh --group macro      # 仅启动宏观数据服务
#   ./mcp_servers/start_all.sh --group academic    # 仅启动学术数据服务
#   ./mcp_servers/start_all.sh --group china      # 仅启动中国数据服务
#
# 依赖：
#   - Docker Desktop (macOS) 或 Docker Engine (Linux)
#   - docker-compose 或 docker compose (v2+)
#
# 安装 Docker Desktop：见 ../docs/DOCKER_INSTALL.md
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
COMPOSE_PROJECT="finresearch"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}   $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 前置检查 ──────────────────────────────────────────────────────────────────

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装！请参考 docs/DOCKER_INSTALL.md 安装 Docker Desktop。"
        echo ""
        echo "  macOS 安装："
        echo "    brew install --cask docker"
        echo "    # 或从 https://www.docker.com/products/docker-desktop 下载"
        echo ""
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker 未运行！请启动 Docker Desktop 后重试。"
        exit 1
    fi

    # 检查 docker compose v2 vs v1
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        log_error "docker-compose 未安装！请安装 Docker Desktop（含 docker compose）。"
        exit 1
    fi

    log_success "Docker 环境检查通过 ($(${COMPOSE_CMD} --version | head -1))"
}

# ── 帮助信息 ──────────────────────────────────────────────────────────────────

show_help() {
    cat << 'EOF'
用法: ./mcp_servers/start_all.sh [选项]

MCP 数据服务器一键启动脚本

选项:
  --help            显示本帮助信息
  --start           启动所有 MCP 服务器（默认）
  --stop            停止所有 MCP 服务器
  --restart         重启所有 MCP 服务器
  --status          查看所有服务状态
  --logs            查看所有服务日志
  --health          健康检查所有服务
  --pull            拉取最新镜像
  --build           构建所有镜像

按组启动（减少资源占用）:
  --group finance   仅启动金融数据服务（yfinance, eastmoney）
  --group macro     仅启动宏观数据服务（fed-data, wb-data, imf-data...）
  --group academic  仅启动学术数据服务（openalex, arxiv, context7...）
  --group china     仅启动中国数据服务（tushare, esg, province...）

示例:
  ./mcp_servers/start_all.sh              # 启动全部
  ./mcp_servers/start_all.sh --group academic --start
  ./mcp_servers/start_all.sh --status
  ./mcp_servers/start_all.sh --stop

详细安装说明请参考: ../docs/DOCKER_INSTALL.md
EOF
}

# ── 服务组定义 ────────────────────────────────────────────────────────────────

get_group_services() {
    local group="$1"
    case "$group" in
        finance)
            echo "mcp_yfinance mcp_eastmoney_reports mcp_eastmoney_fund mcp_eastmoney_bond mcp_eastmoney_option"
            ;;
        macro)
            echo "mcp_fed_data mcp_wb_data mcp_imf_data mcp_oecd_data mcp_bea_data mcp_macro_ceic mcp_macro_datas mcp_macro_stats mcp_eodhd"
            ;;
        academic)
            echo "mcp_openalex mcp_arxiv mcp_context7 mcp_semantic_scholar mcp_nber_wp"
            ;;
        china)
            echo "mcp_tushare mcp_financial mcp_eastmoney_reports mcp_province_stats mcp_hubei_stats mcp_wuhan_stats"
            ;;
        *)
            echo ""
            ;;
    esac
}

# ── Docker Compose 操作 ────────────────────────────────────────────────────────

do_start() {
    local services="${1:-}"
    log_info "启动 MCP 服务器${services:+(服务: $services)}..."
    ${COMPOSE_CMD} -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" up -d ${services:+$services}
    log_success "MCP 服务器已启动！"
    echo ""
    echo "查看状态: $0 --status"
    echo "查看日志: $0 --logs"
    echo "停止服务: $0 --stop"
}

do_stop() {
    log_info "停止所有 MCP 服务器..."
    ${COMPOSE_CMD} -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" down
    log_success "所有 MCP 服务器已停止。"
}

do_restart() {
    log_info "重启所有 MCP 服务器..."
    ${COMPOSE_CMD} -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" restart
    log_success "所有 MCP 服务器已重启。"
}

do_status() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  MCP 服务器状态${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""
    ${COMPOSE_CMD} -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" ps
    echo ""
}

do_logs() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  MCP 服务器日志（最近 50 行）${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""
    ${COMPOSE_CMD} -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" logs --tail=50
    echo ""
}

do_health() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  MCP 服务器健康检查${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""

    local running=0
    local total=0

    while IFS= read -r line; do
        total=$((total + 1))
        if echo "$line" | grep -q "Up"; then
            running=$((running + 1))
            echo -e "  ${GREEN}✓${NC} $(echo "$line" | awk '{print $1}')"
        else
            echo -e "  ${RED}✗${NC} $(echo "$line" | awk '{print $1}')"
        fi
    done < <(${COMPOSE_CMD} -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" ps 2>/dev/null | tail -n +2)

    if [ "$total" -eq 0 ]; then
        log_warn "未检测到运行中的服务。可能需要先运行 $0 --start"
    else
        echo ""
        log_info "健康状态: $running/$total 服务运行中"
    fi
}

do_pull() {
    log_info "拉取最新镜像..."
    ${COMPOSE_CMD} -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" pull
    log_success "镜像拉取完成。"
}

do_build() {
    log_info "构建所有镜像（包含代码更改）..."
    ${COMPOSE_CMD} -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" build --parallel
    log_success "镜像构建完成。"
}

# ── 主逻辑 ────────────────────────────────────────────────────────────────────

main() {
    local action="${1:-}"
    local group="${2:-}"

    check_docker

    case "$action" in
        --start|-s|"")
            do_start "$group"
            ;;
        --stop)
            do_stop
            ;;
        --restart)
            do_restart
            ;;
        --status)
            do_status
            ;;
        --logs)
            do_logs
            ;;
        --health)
            do_health
            ;;
        --pull)
            do_pull
            ;;
        --build)
            do_build
            ;;
        --group)
            if [ -z "$group" ]; then
                log_error "请指定服务组: finance | macro | academic | china"
                show_help
                exit 1
            fi
            local services
            services=$(get_group_services "$group")
            if [ -z "$services" ]; then
                log_error "未知服务组: $group"
                show_help
                exit 1
            fi
            do_start "$services"
            ;;
        --help|-h|help)
            show_help
            ;;
        *)
            log_error "未知选项: $action"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
