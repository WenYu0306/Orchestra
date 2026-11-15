# CLAUDE.md

## 项目结构

```
Orchestra（JobHunter）
├── backend/
│   ├── agent_runner.py      Agent 主循环 + 评分/分层/发送调度（BOSS 平台逻辑当前内联于此，
│   │                        平台化拆分方案见架构评估：抽 PlatformAdapter 四方法，编排层不动）
│   ├── matcher.py           DeepSeek 简历-JD 匹配打分
│   ├── greeting_generator.py 招呼语生成（DEFAULT_GREETING 全链路降级文案唯一定义处）
│   ├── search_generator.py  搜索关键词动态生成
│   ├── validator.py         城市/公司/薪资 三道校验栅栏
│   ├── record_manager.py    投递记录持久化（applied_jobs 历史即 sent 去重源）
│   ├── sse_manager.py       SSE 实时推送管理
│   ├── llm.py               DeepSeek httpx 共享客户端（唯一出口）
│   ├── config_loader.py     配置加载（config.yaml 默认 + data/user_settings.yaml 覆盖 + .env）
│   └── main.py              FastAPI 入口 + REST API + SSE
├── frontend/                Vue 3 + Vite 前端（Element Plus，发布时由后端直接托管 dist）
├── tools/                   开发工具/测试脚本（含 md2docx.py 手册转换，不随包分发）
├── data/                    运行时数据（日志/埋点/投递记录/Chrome profile）
├── docs/                    文档（使用手册 + 商业化内参）
├── package.py               发布打包（PyInstaller onedir + fail-closed 敏感扫描）
├── config.yaml              主配置文件
└── start.sh                 一键启动脚本（开发形态）
```

（vectordb.py 已于 1.5.0 删除；platform_adapter.py / adapters/ 仅存在于
feat/multi-platform 分支——master 的平台逻辑尚未抽出，见 agent_runner 注释。）

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
