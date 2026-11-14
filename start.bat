@echo off
chcp 65001 >nul

REM 只清理本项目的 Agent Chrome（user_data_dir=data\chrome-profile），不动用户自己的浏览器
echo 清理残留 Agent Chrome...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object {$_.CommandLine -like '*chrome-profile*'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo 激活虚拟环境...
call .venv\Scripts\activate.bat

REM 生产运行不加 --reload：文件变动会重启后端、杀死正在运行的 Agent 任务
echo 启动后端 (FastAPI :5001)...
start "Orchestra Backend" cmd /c "python -m uvicorn backend.main:app --host 127.0.0.1 --port 5001"

if exist "frontend\dist\index.html" (
  echo.
  echo 界面由后端托管（无需 Node）: http://localhost:5001
) else (
  echo 启动前端 (Vite :5173)...
  cd frontend
  start "Orchestra Frontend" cmd /c "npm run dev"
  cd ..
  echo.
  echo 前端: http://localhost:5173
)

echo.
echo 关闭本窗口可停止所有服务
pause
