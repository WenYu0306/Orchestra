@echo off
chcp 65001 >nul
echo 清理旧 Chrome 进程...
taskkill /f /im chrome.exe 2>nul
timeout /t 2 /nobreak >nul
if exist "%TEMP%\jh-*" del /q "%TEMP%\jh-*"

echo 激活虚拟环境...
call .venv\Scripts\activate.bat

echo 启动后端 (FastAPI :5000)...
start "Orchestra Backend" cmd /c "python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000"

echo 启动前端 (Vite :5173)...
cd frontend
start "Orchestra Frontend" cmd /c "npm run dev"
cd ..

echo.
echo 后端: http://localhost:5000
echo 前端: http://localhost:5173
echo.
echo 关闭本窗口可停止所有服务
pause
