# Orchestra v1.0

AI Agent — 在 BOSS 直聘上自动搜索职位、获取完整 JD、DeepSeek 评分、分层排序、生成招呼语。

## 项目状态

| 模块 | 状态 |
|------|------|
| API 获取职位 | ✅ tab.get() 直取 BOSS API，22 个搜索词，30 职位/搜索 |
| 完整 JD 获取 | ✅ 详情 API `job/card.json` 重评 top 30 |
| DeepSeek 评分 | ✅ 标签初筛 + 详情重评两轮评分 |
| 分层决策 | ✅ high(5) / medium(7) / try(8) |
| 招呼语生成 | ✅ 基于真实简历，不编造 |
| SSE 实时推送 | ✅ 前端实时状态更新 |
| Chrome 反爬 | ✅ nodriver 直连 Chrome，保活机制 |
| 真发送模式 | ⚠️ 默认 dry_run，待验证 |

## 架构

三层 Agent 架构 —— 决策层（DeepSeek 评分/分层/招呼语）、执行层（API 直取/详情富化/标签兜底）、连接层（nodriver + CDP）。

评估流程：搜索列表 API → 标签快速初筛 → 全局排序 → 详情 API 重评 top 30 → 最终分层。

详见 [architecture.md](architecture.md)。

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Google Chrome

### 安装

```bash
cd backend
pip install -r requirements.txt

cd ../frontend
npm install
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
```

编辑 `config.yaml`，填入个人信息和求职偏好。

### 启动

```bash
# 终端 1：后端
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000

# 终端 2：前端
cd frontend && npm run dev
```

打开 `http://localhost:5173`，点击「开始分析」。

## 技术栈

| 层 | 技术 |
|---|---|
| 浏览器操控 | nodriver + CDP + Chrome |
| 推理模型 | DeepSeek (httpx) |
| 后端 | Python / FastAPI |
| 前端 | Vue 3 + Naive UI |
| 实时通信 | SSE |
| 数据存储 | JSON 本地文件 |

## License

MIT
# test
