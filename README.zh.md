# Orchestra（JobHunter）v1.0

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Node](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)

> [English](README.md)

AI Agent —— BOSS 直聘全自动求职系统。搜索、评分、分层、生成招呼语、一键发送。Agent 根据搜索质量自主调整策略。

## 架构

三层架构：

- **连接层** — nodriver + CDP + 同步 XHR，绕过 DOM 爬取和反爬检测
- **执行层** — httpx → DeepSeek（Matcher 打分、Generator 搜索词、Composer 招呼语）
- **决策层** — Agent 自主调度循环（观察→DeepSeek 决策→执行原子搜索）

## 快速开始

### 环境

- Python 3.12+、Node.js 18+、Google Chrome

### 安装

```bash
git clone https://github.com/WenYu0306/Orchestra.git
cd Orchestra
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
```

### 启动

**macOS/Linux：** `./start.sh`
**Windows：** `start.bat`

或手动：

```bash
# 终端 1
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000
# 终端 2
cd frontend && npm run dev
```

浏览器打开 `http://localhost:5173`。

## 技术栈

| 层 | 技术 |
|---|---|
| 浏览器 | nodriver (CDP) + Chrome + 同步 XHR |
| AI | DeepSeek (httpx, 连接池 50/10) |
| 后端 | Python / FastAPI |
| 前端 | Vue 3 + Vite + SSE |

## 完整安装指南

详见 [SETUP.md](SETUP.md)。

## License

MIT
