#!/bin/bash
# Orchestra 一键启动
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "🧹 清理旧 Chrome 进程..."
pkill -9 -f "Google Chrome" 2>/dev/null || true
sleep 1
rm -rf /tmp/jh-* 2>/dev/null || true

echo "📦 激活虚拟环境..."
source .venv/bin/activate

echo "🚀 启动后端 (FastAPI :5000)..."
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000 &
BACKEND_PID=$!

echo "🎨 启动前端 (Vite :5173)..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 后端: http://localhost:5000"
echo "✅ 前端: http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '已停止'" EXIT
wait
