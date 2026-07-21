# CLAUDE.md

## 项目结构

```
Orchestra（JobHunter）
├── backend/
│   ├── agent_runner.py      Agent 主循环 + 所有平台共享的评分/分层
│   ├── platform_adapter.py  PlatformAdapter 抽象接口（5个方法）
│   ├── adapters/            各平台适配器（zhilian.py 等）
│   ├── matcher.py           DeepSeek 简历-JD 匹配打分
│   ├── greeting_generator.py 招呼语生成
│   ├── search_generator.py  搜索关键词动态生成
│   ├── vectordb.py          TF-IDF + 余弦相似度向量检索
│   ├── validator.py         城市/公司/薪资 三道校验栅栏
│   ├── record_manager.py    投递记录持久化
│   ├── sse_manager.py       SSE 实时推送管理
│   ├── config_loader.py     配置加载（config.yaml + .env）
│   └── main.py              FastAPI 入口 + REST API + SSE
├── frontend/                Vue 3 + Vite 前端
├── tools/                   开发工具/测试脚本
├── data/                    运行时数据（日志/缓存）
├── docs/                    文档（LANGGRAPH.md / DEPLOY.md）
├── Dockerfile.* + docker-compose.yml  容器化部署
├── config.yaml              主配置文件
└── start.sh                 一键启动脚本
```

## 分支

- `master` — BOSS 直聘生产版。一切正常，不碰
- `feat/multi-platform` — 多平台扩展开发版（智联适配器）

新功能在 `feat/multi-platform` 开发，验证通过后再合并到 `master`。

## 关键规约

1. **不动 master 的 BOSS 链路。** 所有多平台改动在 feat/multi-platform 分支
2. **错误处理：** 不允许 `except Exception: pass`，必须加日志
3. **数据结构：** 用 `ScoredJob` dataclass，不用元组索引
4. **端口：** 后端 5001（macOS AirPlay 占 5000），前端 5173
5. **Python：** 用 `.venv/bin/python`（3.12），不用系统 python3（3.9）
