# 贡献指南

欢迎贡献！无论是报告 bug、提出新功能、改进文档，还是提交代码变更，都请遵循以下流程。

## 报告 Bug

1. 先搜索 [Issues](../../issues)，确认没有人报过同一个问题
2. 创建新 Issue，标题简洁描述症状
3. 包含：运行环境（Python 版本、Chrome 版本、操作系统）、复现步骤、看到的错误日志、你期望的结果

## 功能建议

在 Issues 中描述你想要的功能、为什么有用、以及可能怎么实现它。不一定在代码层面——如果你的想法比代码更好，就说想法。

## 提 Pull Request

1. Fork 本仓库
2. 创建一个 feature 分支：`git checkout -b feat/你的功能名`
3. 做你的改动，保持改动小而聚焦——一个 PR 解决一件事
4. 跑测试确保没破坏任何东西：
   ```bash
   python backend/tests/test_record_manager.py
   ```
5. 提交并 push：`git commit -m "feat: 你的功能简述"`
6. 发起 Pull Request 到 `master` 分支

## 代码风格

- Python：保持跟现有项目风格一致
- Vue：保持跟现有组件风格一致
- 注释可以中文，变量名保持英文
- 复杂逻辑加一行注释解释

## 开发环境

跟 [SETUP.md](SETUP.md) 完全一样。如果有特殊需求，加入更改并提交。

## License

贡献即表示你同意将你的贡献按照 MIT 许可证进行许可。
