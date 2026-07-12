# Orchestra 安装指南

从零到跑通的完整步骤。每一步都不能跳。

## 1. 环境要求

| 要求 | 最低版本 | 验证命令 |
|------|---------|---------|
| macOS / Windows / Linux | — | — |
| Python | 3.12 | `python3 --version` |
| Node.js | 18 | `node --version` |
| Google Chrome | 最新版 | 打开 Chrome 确认能正常上网 |

## 2. 克隆项目

```bash
git clone https://github.com/WenYu0306/Orchestra.git
cd Orchestra
```

## 3. 创建 Python 虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# 或 .venv\Scripts\activate  # Windows
```

## 4. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

如果安装失败，确认 Python 版本 ≥ 3.12。

## 5. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

## 6. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 DeepSeek API Key：
```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

[DeepSeek API Key 获取地址](https://platform.deepseek.com/api_keys)

## 7. 准备简历

把你的简历 PDF 放在项目根目录下，确认 `config.yaml` 里路径正确：
```yaml
resume:
  pdf_path: "./my_resume.pdf"
```

## 8. 编辑配置文件

`config.yaml` 里可以调整：
- `search.cities` — 搜索城市和最低薪资
- `search.primary_keywords` — 预设搜索关键词
- `matching.tiers` — 分层数量（高/中/可试各几个）

不改也能用，默认搜北京+长春。

## 9. 启动

需要两个终端。

**终端 1 — 后端：**
```bash
source .venv/bin/activate   # 如果还没激活
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000
```

**终端 2 — 前端：**
```bash
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173`。

## 10. 开始使用

点「开始」按钮。Chrome 会自动打开，如果第一次使用需要扫码登录 BOSS 直聘。

评分完成后（约 15-20 分钟），勾选想投递的岗位，点「发送选中」。

## 常见问题

**Q: Chrome 启动失败 "Failed to connect to browser"**
```bash
pkill -9 -f "Google Chrome"
rm -rf /tmp/jh-run-1
```
然后重启后端。

**Q: 前端页面空白**
确认后端已启动且 5000 端口没被占用。

**Q: 发送了但没有消息**
确认你的 BOSS 直聘 APP 上「沟通过」列表里有新对话。默认发的招呼语是系统文案，通过 CDP 发送的自定义文案只有代码里启用了才会有。
