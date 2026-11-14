#!/bin/bash
# Orchestra 一键启动
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# 检查 venv
if [ ! -d ".venv" ]; then
  echo "⛔ 虚拟环境不存在，请先运行：python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt"
  exit 1
fi

# 环境检查（用 venv 的 Python 3.12，不用系统 python3）
if [ -f check.py ]; then
  echo "🔍 运行环境检查..."
  .venv/bin/python check.py
fi

# 只清理本项目的 Agent Chrome（user_data_dir=data/chrome-profile）
# 不要 pkill 整个 Google Chrome —— 那会把用户自己的浏览器一起杀掉
echo "🧹 清理残留 Agent Chrome..."
pkill -9 -f "chrome-profile" 2>/dev/null || true
sleep 1

# 端口从 config.yaml 读取（默认 5001；macOS AirPlay 接收器占用 5000）
BACKEND_PORT="$(.venv/bin/python -c 'from backend.config_loader import get_config; print(get_config().web_ui.port)')"

# 生产运行不加 --reload：文件变动会重启后端、杀死正在运行的 Agent 任务
echo "🚀 启动后端 (FastAPI :${BACKEND_PORT})..."
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "${BACKEND_PORT}" &
BACKEND_PID=$!

if [ -f "frontend/dist/index.html" ]; then
  # 发布形态：前端构建产物由后端直接托管，无需 Node/Vite
  echo "📦 界面由后端托管（无需 Node）"
  echo ""
  echo "✅ 界面: http://localhost:${BACKEND_PORT}"
  echo "按 Ctrl+C 停止"
  trap "kill $BACKEND_PID 2>/dev/null; echo '已停止'" EXIT
  wait
else
  # 开发形态：需要跑 Vite
  if [ ! -d "frontend/node_modules" ]; then
    echo "📦 安装前端依赖..."
    cd frontend && npm install && cd ..
  fi
  echo "🎨 启动前端 (Vite :5173)..."
  (cd frontend && npm run dev) &
  FRONTEND_PID=$!
  echo ""
  echo "✅ 后端: http://localhost:${BACKEND_PORT}"
  echo "✅ 前端: http://localhost:5173"
  echo "按 Ctrl+C 停止所有服务"
  trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '已停止'" EXIT
  wait
fi
