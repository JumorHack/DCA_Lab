#!/usr/bin/env bash
#
# 一键启动脚本：自动创建/激活 Python 虚拟环境、安装前后端依赖，并同时启动后端与前端。
#
#   用法:   ./start.sh
#   停止:   按 Ctrl+C （会自动关闭前后端两个进程）
#
# 可选环境变量:
#   BACKEND_PORT   后端端口 (默认 8010)
#   FRONTEND_PORT  前端端口 (默认 5173)
#   REINSTALL=1    强制重新安装依赖
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
export BACKEND_PORT FRONTEND_PORT

# ----- pretty logging ------------------------------------------------------- #
if [ -t 1 ]; then
  C_BLUE=$'\033[1;34m'; C_GREEN=$'\033[1;32m'; C_YELLOW=$'\033[1;33m'; C_RED=$'\033[1;31m'; C_DIM=$'\033[2m'; C_RESET=$'\033[0m'
else
  C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_RESET=""
fi
log()  { printf "${C_BLUE}▶ %s${C_RESET}\n" "$1"; }
ok()   { printf "${C_GREEN}✓ %s${C_RESET}\n" "$1"; }
warn() { printf "${C_YELLOW}! %s${C_RESET}\n" "$1"; }
die()  { printf "${C_RED}✗ %s${C_RESET}\n" "$1" >&2; exit 1; }

port_in_use() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# ----- prerequisites -------------------------------------------------------- #
command -v python3 >/dev/null 2>&1 || die "未找到 python3，请先安装 Python ≥ 3.9"
command -v npm     >/dev/null 2>&1 || die "未找到 npm，请先安装 Node.js ≥ 18"

# ----- 清除会导致联网失败的本地/沙箱代理 ------------------------------------ #
# Cursor 等会注入 HTTP_PROXY=127.0.0.1:xxxxx，该代理只在沙箱内有效；若泄漏到普通
# 终端，会让 akshare 无法访问东方财富/新浪而报 502。行情源均为境内站点，直连即可。
_proxy_blob="${HTTP_PROXY:-} ${HTTPS_PROXY:-} ${ALL_PROXY:-} ${http_proxy:-} ${https_proxy:-} ${all_proxy:-}"
if [ -n "${__CURSOR_SANDBOX_ENV_RESTORE:-}" ] || printf '%s' "$_proxy_blob" | grep -qiE '127\.0\.0\.1|localhost'; then
  warn "检测到本地/沙箱代理，已为本次启动清除（避免行情接口 502）。如确需代理请手动设置。"
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy \
        SOCKS_PROXY SOCKS5_PROXY socks_proxy socks5_proxy GIT_HTTP_PROXY GIT_HTTPS_PROXY
fi

# ----- 1. backend venv + deps ---------------------------------------------- #
log "准备后端虚拟环境 (.venv)"
cd "$BACKEND_DIR"
NEED_BACKEND_INSTALL=0
if [ ! -d .venv ]; then
  if command -v uv >/dev/null 2>&1; then
    ok "使用 uv 创建虚拟环境"
    uv venv .venv
  else
    ok "使用 python3 -m venv 创建虚拟环境"
    python3 -m venv .venv
  fi
  NEED_BACKEND_INSTALL=1
fi
if [ "$NEED_BACKEND_INSTALL" = "1" ] || [ "${REINSTALL:-0}" = "1" ]; then
  log "安装后端依赖 (requirements.txt)"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python .venv/bin/python -r requirements.txt
  else
    ./.venv/bin/python -m pip install --upgrade pip >/dev/null
    ./.venv/bin/pip install -r requirements.txt
  fi
fi
ok "后端依赖就绪"

# ----- 2. frontend deps ----------------------------------------------------- #
log "准备前端依赖"
cd "$FRONTEND_DIR"
if [ ! -d node_modules ] || [ "${REINSTALL:-0}" = "1" ]; then
  log "安装前端依赖 (npm install)"
  npm install
fi
ok "前端依赖就绪"

# ----- 3. port checks ------------------------------------------------------- #
if port_in_use "$BACKEND_PORT"; then
  die "后端端口 $BACKEND_PORT 已被占用，请用 BACKEND_PORT=<其他端口> ./start.sh 重试"
fi
if port_in_use "$FRONTEND_PORT"; then
  warn "前端端口 $FRONTEND_PORT 已被占用，Vite 可能会自动选择其他端口"
fi

# ----- 4. start both, clean shutdown on exit -------------------------------- #
BACK_PID=""; FRONT_PID=""
cleanup() {
  printf "\n"
  log "正在停止服务…"
  [ -n "$FRONT_PID" ] && kill "$FRONT_PID" 2>/dev/null || true
  [ -n "$BACK_PID" ]  && kill "$BACK_PID"  2>/dev/null || true
  wait 2>/dev/null || true
  ok "已停止"
}
trap cleanup INT TERM EXIT

log "启动后端  http://localhost:$BACKEND_PORT  ${C_DIM}(首次启动需加载 akshare，约 20-30s)${C_RESET}"
cd "$BACKEND_DIR"
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACK_PID=$!

log "启动前端  http://localhost:$FRONTEND_PORT"
cd "$FRONTEND_DIR"
npm run dev &
FRONT_PID=$!

printf "\n"
ok  "已启动！在浏览器打开 ${C_GREEN}http://localhost:$FRONTEND_PORT${C_RESET}"
warn "按 Ctrl+C 关闭前后端"
printf "\n"

# 任一进程退出则整体退出（触发 cleanup）。兼容 macOS 自带 bash 3.2（无 wait -n）。
while kill -0 "$BACK_PID" 2>/dev/null && kill -0 "$FRONT_PID" 2>/dev/null; do
  sleep 1
done
