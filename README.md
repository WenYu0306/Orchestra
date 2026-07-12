# Orchestra（JobHunter）v1.0

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Node](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)
[![Chrome](https://img.shields.io/badge/Chrome-最新版-orange.svg)](https://www.google.com/chrome/)

AI Agent —— BOSS 直聘全自动求职：搜索 → 评分 → 分层 → 生成招呼语 → 一键发送。Agent 自主调度可动态调整搜索策略。

## 项目状态

| 模块 | 状态 |
|------|------|
| XHR 搜索 | ✅ 城市×关键词，30 职位/页 |
| DeepSeek 评分 | ✅ 标签初筛 + 详情重评两轮 |
| 分层决策 | ✅ high(5) / medium(7) / try(8) |
| 招呼语生成 | ✅ 基于简历 + JD，DeepSeek 生成 |
| SSE 实时推送 | ✅ 前端逐条显示卡片 |
| 前端勾选发送 | ✅ 复选框 + 发送选中按钮 |
| 自定义招呼语 | ✅ CDP 内核级输入，开源项目首次公开 |
| Agent 自主调度 | ✅ DeepSeek 动态选词选城，观察→决策→执行 |

![截图](docs/screenshot.png)

> 💡 截图请放 `docs/screenshot.png`，参考 SETUP.md 跑一遍后截取前端主页面即可。

## 与同类项目对比

| 项目 | 数据获取 | Agent 调度 | 自定义招呼语 | 前端界面 |
|------|---------|-----------|------------|---------|
| **Orchestra（本项目）** | XHR API 直取 | ✅ DeepSeek 动态决策 | ✅ CDP 内核输入 | ✅ Vue 3 Web UI |
| 同类项目 A | DOM 爬取 | ❌ | ❌ | CLI |
| 同类项目 B | API | ❌ | ❌ | CLI |
| 同类项目 C | DOM 爬取 | ❌ | 弹窗 DOM | Electron |
| 同类项目 D | 插件注入 | ❌ | ❌ | Chrome 扩展 |

## 架构

三层 — 连接层（nodriver + CDP + XHR）、执行层（httpx → DeepSeek）、决策层（Agent 自主调度循环）。

详见 [ARCHITECTURE.html](ARCHITECTURE.html)。

## 快速开始

### 环境

- Python 3.12+
- Node.js 18+
- Google Chrome

### 环境检查

```bash
python check.py
```

缺失项会提示怎么修复。全部通过后再启动。

### 安装

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

### 配置

```bash
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
```

编辑 `config.yaml`：简历路径、搜索城市、薪资下限、匹配参数。

### 启动

```bash
# 终端 1：后端
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000

# 终端 2：前端
cd frontend && npm run dev
```

浏览器打开 `http://localhost:5173`，点击「开始」。

## 技术栈

| 层 | 技术 |
|---|---|
| 浏览器操控 | nodriver（CDP）+ Chrome + 同步 XHR |
| AI | DeepSeek（httpx AsyncClient，连接池 50/keepalive 10） |
| 后端 | Python / FastAPI + uvicorn |
| 前端 | Vue 3 + Vite + SSE |
| 数据 | JSON 本地文件（原子写入） |

## License

MIT
