# Orchestra 安装指南（零基础版）

本文写给没有任何编程经验的人。你只需要会用电脑和手机。

## 第一步：确认你的电脑准备好了

### 1.1 打开终端

**Mac：** 按键盘上 `Cmd(⌘) + 空格`，输入"终端"，回车。

**Windows：** 按键盘上 `Win键 + R`，输入 `cmd`，回车。

你看到一个小黑窗，这就是终端。后面所有操作都在这里进行。

### 1.2 检查 Python 是否安装

在终端里复制粘贴下面这行，回车：

```bash
python3 --version
```

如果显示 `Python 3.12.x` 或更高——✅ 没问题。

如果显示 `command not found`——你需要先装 Python。

**Mac：** 打开浏览器，搜 `Python 3.12 download Mac`，从 python.org 下载安装。

**Windows：** 打开浏览器，搜 `Python 3.12 download Windows`，从 python.org 下载安装。安装时☑️"Add Python to PATH"。

### 1.3 检查 Node.js 是否安装

```bash
node --version
```

如果显示 `v18.x.x` 或更高——✅ 没问题。

如果显示 `command not found`：

打开浏览器，搜 `Node.js download`，从 nodejs.org 下载 LTS 版本安装。

### 1.4 确认 Chrome 已安装

你的电脑如果装了 Google Chrome 浏览器——✅ 没问题。没有的话，先去 google.com/chrome 下载安装。

---

## 第二步：下载项目

### 2.1 安装 Git（如果没有）

```bash
git --version
```

如果有版本号——✅。如果没有——Mac 会提示你安装，Windows 去 git-scm.com 下载。

### 2.2 克隆项目

在终端里输入：

```bash
git clone https://github.com/WenYu0306/Orchestra.git
```

等待下载完成。然后进入项目目录：

```bash
cd Orchestra
```

---

## 第三步：安装所有需要的库

### 3.1 创建虚拟环境

```bash
python3 -m venv .venv
```

这会在项目里建一个独立的环境，不影响你电脑上其他 Python 程序。

### 3.2 激活虚拟环境

**Mac：**
```bash
source .venv/bin/activate
```

**Windows：**
```bash
.venv\Scripts\activate
```

终端前面会多出 `(.venv)` 字样，说明成功了。

### 3.3 安装 Python 库

```bash
pip install -r requirements.txt
```

这一步会下载约 100 个库，等 2-5 分钟。如果看到 `Successfully installed`——✅。

如果中途报错，大概率是网络问题。重试一次就好。

### 3.4 安装前端库

```bash
cd frontend && npm install && cd ..
```

等 1-3 分钟。如果看到一堆安装进度条但没有红色报错——✅。

---

## 第四步：配置

### 4.1 配置 API Key

```bash
cp .env.example .env
```

这创建了你的配置文件夹。你需要注册 DeepSeek 账号并获取 API Key。

1. 打开 https://platform.deepseek.com ，注册并登录
2. 在左侧菜单找「API Keys」，创建一个新 Key
3. 复制那串 `sk-xxxxxxxx` 开头的字符串

回到终端，打开配置文件。直接在终端里运行：

```bash
open .env   # Mac 会用文本编辑器打开
# 或直接双击项目文件夹里的 .env 文件
```

把文件里的 `your_deepseek_api_key_here` 替换成你刚才复制的 Key，保存并关闭文件。

### 4.2 准备简历

把你的简历 PDF 放到项目文件夹里，重命名为 `my_resume.pdf`。

确认 `config.yaml` 里的路径正确：
```yaml
resume:
  pdf_path: "./my_resume.pdf"
```

> 默认配置是搜索北京和长春的岗位。如果你想改城市或薪资，编辑 `config.yaml`。

---

## 第五步：启动

### 5.1 运行环境检查（可选）

```bash
python3 check.py
```

全部显示 ✅ 就说明环境就绪。（有些项显示 ⚠️ 也可以跑，但 ✅ 比较安心）

### 5.2 启动

**一行搞定（Mac 推荐）：**
```bash
./start.sh
```

**一行搞定（Mac 和 Windows 都行的）：**
```bash
python3 -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5001
```

看到终端打印 `Application startup complete` 说明后端启动了。

**再开一个新终端**，进入项目目录，运行前端：

```bash
cd 你下载的项目目录/Orchestra/frontend
npm run dev
```

> `你下载的项目目录` 要换成你实际的路径。如果你不知道路径，在刚才的终端里输入 `pwd`，它会告诉你。

---

## 第六步：开始使用

浏览器打开 `http://localhost:5173`。

点「开始」按钮。Chrome 会自动打开，你需要扫码登录 BOSS 直聘。

等 15-20 分钟评分完成，勾选想投的岗位，点「发送选中」。

---

## 常见问题

**Chrome 启动失败**
```bash
pkill -9 -f "Google Chrome"
rm -rf /tmp/jh-*
```
然后重启后端。

**"未检测到 Google Chrome"**
确认 Chrome 安装路径，Mac 默认是 `/Applications/Google Chrome.app`。

**前端页面空白**
确认后端已启动且没报错。

**发送了但没收到消息**
打开手机 BOSS 直聘 APP，在「沟通过」里检查。

**完全不知道怎么做**
把错误截图和终端日志贴到 GitHub Issues:
https://github.com/WenYu0306/Orchestra/issues
