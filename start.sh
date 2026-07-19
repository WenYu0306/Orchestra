#!/bin/bash
# Orchestra 一键启动
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# 环境检查
if [ -f check.py ]; then
  echo "🔍 运行环境检查..."
  python3 check.py
fi

# 检查 venv
if [ ! -d ".venv" ]; then
  echo "⛔ 虚拟环境不存在，请先运行：python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# 检查前端依赖
if [ ! -d "frontend/node_modules" ]; then
  echo "📦 安装前端依赖..."
  cd frontend && npm install && cd ..
fi

# 清理 Chrome 进程
echo "🧹 清理旧 Chrome 进程..."
pkill -9 -f "Google Chrome" 2>/dev/null || true
sleep 1
rm -rf /tmp/jh-* 2>/dev/null || true

# 启动
echo "📦 激活虚拟环境..."
source .venv/bin/activate

echo "🚀 启动后端 (FastAPI :5001)..."
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5001 &
BACKEND_PID=$!

echo "🎨 启动前端 (Vite :5173)..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 后端: http://localhost:5001"
echo "✅ 前端: http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '已停止'" EXIT
wait
