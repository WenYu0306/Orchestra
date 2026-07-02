# JobHunter v1.0

AI Agent 在 BOSS 直聘上自动搜索职位、评估 JD、分层打分、生成招呼语。三层架构（连接层/执行层/决策层），经由 7 次执行层切换验证。

## 项目状态

| 模块 | 状态 |
|------|------|
| API 获取职位 | ✅ httpx 直接调 BOSS API，15 职位/搜索 |
| DeepSeek 评分 | ✅ 82/72/45 分化正确 |
| 分层决策 | ✅ high/medium/try/skip/pending 五层 |
| 招呼语生成 | ✅ 基于真实简历，不编造 |
| SSE 实时推送 | ✅ 前端实时状态更新 |
| 真发送模式 | ⚠️ 默认 DRY_RUN=true，需手动开启 |
| 频率限制 | ⚠️ 当前 hardcode 8-15s 间隔 |

## 架构

```
决策层 · DeepSeek Orchestrator
├── JD 评分 (0-100)
├── 分层决策 (高≥80 / 中60-79 / 试40-59)
├── 招呼语生成
├── 虚假招聘检测
└── 待选区管理

执行层 · 数据获取
├── API 请求（httpx 直调 BOSS API）
├── 卡片文字提取（fallback）
└── 结果排序 + 去重

连接层 · Chrome Bridge
└── nodriver + CDP 直连 Chrome
```

## 执行层迭代记录

1. Playwright → BOSS 反爬检测 webdriver 标识，页面跳 about:blank
2. DrissionPage → 选择器语法不稳定
3. CDP 直连 → 端口管理复杂，进程生命周期问题
4. nodriver → 连接稳定，但无法触发 BOSS React 事件系统
5. 截图 + Qwen VL → JD 提取不稳定，300-400 字偏差大
6. DOM 遍历 → 文本全是页面 footer，无法定位右侧面板
7. **httpx 调 BOSS API → 从 Chrome 取 cookie，15 职位/搜索** ✓

每次换执行层，决策层（`matcher.py`、`_decide_tier()`、`greeting_generator.py`）一行代码未改。

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+

### 安装

```bash
cd backend
pip install -r requirements.txt --break-system-packages

cd ../frontend
npm install
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
```

编辑 `config.yaml`，填入个人信息。

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
| 推理模型 | DeepSeek V4 Pro |
| 视觉模型 | Qwen3-VL-Flash（应急兜底） |
| 后端 | Python / FastAPI |
| 前端 | Vue3 + Naive UI |
| 实时通信 | SSE |
| 数据存储 | JSON 本地文件 |

## 文件结构

```
backend/
├── agent_runner.py      # Agent 核心调度（228 行）
├── matcher.py           # DeepSeek JD 匹配评分
├── search_generator.py  # 动态搜索词生成
├── greeting_generator.py # 招呼语生成
├── fake_detector.py     # 虚假招聘检测
├── config_loader.py     # 配置 + .env 加载
├── record_manager.py    # 投递记录管理
├── sse_manager.py       # SSE 事件推送
├── main.py              # FastAPI 入口
frontend/
├── App.vue              # 主布局
└── components/          # 4 个组件
```

## License

MIT
