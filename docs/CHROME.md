# Chrome 兼容性

本项目依赖 `nodriver` 通过 Chrome DevTools Protocol 操控浏览器。

## 已验证版本

| nodriver 版本 | Chrome 版本 | 状态 |
|-------------|-----------|------|
| 0.50.3 | 127.x | ✅ 通过（开发环境） |

## 安装

- [Google Chrome 下载](https://www.google.com/chrome/)
- macOS 安装后路径：`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- Windows 安装后路径：`C:\Program Files\Google\Chrome\Application\chrome.exe`
- Linux：`google-chrome`（或通过包管理器安装）

## 故障排查

**"Failed to connect to browser"**

Chrome 进程残留，关闭所有 Chrome 后重试：
```bash
# macOS/Linux
pkill -9 -f "Google Chrome"; sleep 2
# Windows
taskkill /f /im chrome.exe
```

**nodriver 版本不兼容**

```bash
pip install nodriver==0.50.3
```
