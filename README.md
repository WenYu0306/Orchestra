# Orchestra（JobHunter）v1.1

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Node](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)
[![Chrome](https://img.shields.io/badge/Chrome-最新版-orange.svg)](https://www.google.com/chrome/)

AI Agent —— BOSS 直聘 + 智联招聘全自动求职：搜索 → 评分 → 分层 → 生成招呼语 → 一键发送。Agent 自主调度，多平台适配器架构。

## 项目状态

| 模块 | BOSS 直聘 | 智联招聘 |
|------|----------|---------|
| 搜索 | XHR API 直取 | CDP 输入 + 新标签页拦截 |
| 评分 | DeepSeek 标签初筛 + 详情重评 | 同左 |
| VectorDB 粗筛 | TF-IDF 余弦相似度 | 同左 |
| 分层 | 按分数阈值 (≥80 / ≥60 / <60) | 同左 |
| 招呼语 | CDP 内核注入（开源首次公开） | 系统简历投递 |
| SSE 推送 | 前端逐条卡片 | 同左 |
| Agent 调度 | DeepSeek 动态选词选城 | 开发中 |
| 端到端验证 | ✅ 生产可用 | 🔧 搜索/评分/分层已验证 |

详细安装指南见 [SETUP.md](SETUP.md)。

## 多平台架构

```
                   config.yaml: platform.name
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
      BossAdapter    ZhilianAdapter  WuyouAdapter
      (XHR API)      (CDP + DOM)    (Qwen VL 视觉)
           │              │              │
           └──────────────┴──────────────┘
                          │
              PlatformAdapter 抽象接口
                search() / fetch_detail() / send()
                          │
           执行层：VectorDB → DeepSeek 评分 → validator
           决策层：Agent 循环（观察→决策→执行）
```

切换平台只需改一行 `config.yaml`：`platform.name: "boss"` | `"zhilian"` | `"wuyou"`

> `feat/multi-platform` 分支正在开发智联适配器，`master` 分支为 BOSS 生产版。

## 快速开始

### 环境

- Python 3.12+
- Node.js 18+
- Google Chrome
- DeepSeek API Key

### 安装

```bash
git clone https://github.com/WenYu0306/Orchestra.git
cd Orchestra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
# 编辑 config.yaml：简历路径、搜索城市、薪资下限
```

### 启动

```bash
./start.sh   # 一键启动前后端，浏览器打开 http://localhost:5173
```

或 Docker 部署：

```bash
docker compose up -d
```

## 技术栈

| 层 | 技术 |
|---|---|
| 浏览器操控 | nodriver（CDP）+ Chrome + XHR / CDP input |
| AI | DeepSeek（httpx AsyncClient） |
| 向量检索 | 手写 TF-IDF + 余弦相似度（零外部依赖） |
| 后端 | Python 3.12 / FastAPI + uvicorn + SSE |
| 前端 | Vue 3 + Vite |
| 部署 | Docker + docker-compose + Nginx |
| 多平台 | PlatformAdapter 抽象接口 |

## 架构

三层 —— 连接层（nodriver + CDP + XHR / DOM）、执行层（VectorDB → DeepSeek → validator）、决策层（Agent 自主调度循环）。

详见 [architecture.md](architecture.md) 和 [ARCHITECTURE.html](ARCHITECTURE.html)。

## 项目文档

- [DEVLOG.md](DEVLOG.md) — 13 天开发日志，从零到全链路闭环
- [SETUP.md](SETUP.md) — 零基础安装指南
- [docs/DEPLOY.md](docs/DEPLOY.md) — 生产部署方案
- [docs/LANGGRAPH.md](docs/LANGGRAPH.md) — LangGraph 迁移参考

## License

MIT
