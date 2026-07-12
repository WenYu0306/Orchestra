# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 格式。

## [1.0.0] - 2026-07-13

### 新增
- 全链路闭环：XHR 搜索 → 两级评分 → 分层 → 招呼语 → CDP 自定义文案发送
- Agent 自主调度：DeepSeek 根据搜索状态动态选城市和关键词
- SSE 实时推送前端，Vue 3 单页渲染
- 前端确认发送按钮 + 复选框
- 虚假招聘和城市/薪资三重过滤
- CDP `Input.insertText` + `Input.dispatchKeyEvent` 自定义招呼语

### 优化
- `_run()` 拆分为 8 个独立方法
- logging 替换 print，终端 + 文件双输出，每日滚动
- Chrome profile 时间戳防冲突
- CORS 安全限制
- 断点续跑 checkpoint
- `applied_jobs.json` 200 条自动截断
- 前端响应式适配和进度条修正
- 5 个核心数据结构测试
- 安装指南、启动脚本、.env 模板

[1.0.0]: https://github.com/WenYu0306/Orchestra/releases/tag/v1.0.0
