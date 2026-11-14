# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 格式。

## [1.5.1] - 2026-11-15

第一轮 AI 内测战役（24 项检查）发现的修复。

### 修复（关键）
- **verify-key 端点 402 错位**：重构时 `@app.post` 装饰器错误地挂到了内部函数 `_check_key(key: str)` 上——key 变成 query 参数，向导 Key 步验证必 422、下一步永久禁用，**v1.5.0 对新买家不可用**。装饰器归位到 verify_key
- **全新买家城市被预选**：向导把 config 默认城市（北京/长春）悄悄勾上，违反「城市步不默认勾选」决策——现在仅完成过向导的用户回填已有城市
- **垃圾 PDF 上传时即拒绝**：文本伪装/随机字节/扫描件 PDF 之前一路通过上传、运行时才炸；现在上传时解析验证，<50 字给人话提示「可能是扫描件/图片版简历或文件损坏」
- **登录前无跳过入口**：「跳过，先不登录」改为常驻（原设计只在登录失败后出现）

### 测试方法沉淀（AI 内测战役 v1）
- Playwright `networkidle` 等不到 SSE 长连接，用 `load` + 显式等待
- 沙盒 dist 是独立副本，前端重建后必须同步
- `.env` 在后端启动后写入不影响运行中进程——预检类测试必须先写环境再起服务

## [1.5.0] - 2026-11-14

岗位池扩张 + 上架前清理（第三轮审计 A/B 项落地）。

### 新增
- **「全国」投递范围**：城市选项新增「全国」（官方特殊码 100010000，浏览器内实测一次搜索返回横跨 14 城的 30 条岗位）——向导城市步置顶推荐；无「城市不在列表里」问题
- **职位级去重**：去重维度由「公司」改为「公司+职位ID」（对齐主流竞品）——同公司不同职位可分别投递，岗位池显著扩大；仅真实发送（sent）拉黑，评过没发/发送失败的职位次日重现（修复"越用岗位越少"）
- **运行前 Key 预检**：点「开始」先校验 Key 有效性与余额（零成本调余额接口），Key 无效/余额为零直接拦截并给人话提示，不再跑到评分阶段才失败；网络异常不阻塞启动
- **卡片发送状态**：发送后卡片显示「✓ 已发送」/「发送失败 · 可勾选重试」角标（重设计时丢失的功能回归）

### 修复
- **Windows 简历替换死锁**：上传改为临时文件 + os.replace 原子替换——旧实现先删旧文件，PDF 被阅读器锁定时上传失败且旧简历已丢；现给人话提示「请关闭后重试」且旧文件无损
- agent_decisions.jsonl 超 1MB 自动归档（原 append-only 永续增长）

### 删除（造轮子审计定案，上架前清理）
- **vectordb.py TF-IDF 向量粗筛**：在 min_score=0/top_k=30 配置下纯空转（搜索页每词每城本就上限 30 条），及其配置项
- **暂停机制死代码**：`/api/resume` 端点、is_paused/_pe/emit_captcha/NEED_CAPTCHA——emit_captcha 无任何调用方，暂停从未真正可用
- **`/api/test` 调试端点**：会真跑 AI 管线的开发后门，不再随包发行给买家
- **三份重复 DeepSeek 客户端**：matcher/greeting/search/agent 四处各自的 httpx 单例收敛为 backend/llm.py 单一客户端

### 变更
- check_city 对「全国」跳过城市校验；`captcha_handling` 配置项随暂停机制删除
- 手册/向导补充版本更新迁移说明（保留 data 与 .env 即保留配置/登录态/记录）

## [1.4.1] - 2026-11-14

Windows 真机冒烟测试（中文区域 GBK + 未装 Chrome + 全新环境）发现的两个启动崩溃修复。

### 修复（关键，均 Windows 真机实测发现）
- **CI 打包缺 python-multipart → 双击启动即崩**：FastAPI 的 `UploadFile` 路由在模块导入阶段就探测 multipart 运行时，而它是动态探测型依赖——CI 构建机只装 requirements.txt（漏了它）→ PyInstaller 无从打包 → 冻结包启动即 `RuntimeError: Form data requires "python-multipart"`，无任何 UI 反馈。requirements.txt 显式声明修复（本地 venv 恰好有它，故 Mac 本地包未暴露）
- **GBK 区域 + 管道/重定向 stdout → UnicodeEncodeError 崩溃**：启动日志的 ✓/⚠ 在 GBK 编码下无法输出。main.py 入口统一 `sys.stdout/stderr.reconfigure(encoding="utf-8")`（真实控制台路径走 WinConsoleIO 本就 UTF-8，不受影响）
- **agent.log FileHandler 显式 utf-8**：GBK 机器上日志写入 ✓/⚠ 同样会出问题，而售后排障依赖日志

### 附：冒烟通过项
- WebView2 原生窗口、五步向导全新环境进入、文件对话框、关窗即退净（~5s 全进程退出）——Windows 形态核心链路正常

## [1.4.0] - 2026-11-14

桌面应用形态：pywebview 原生窗口 + 首跑向导 + 发送链路根治 + 分层语义重构。

### 新增
- **pywebview 桌面壳**（launcher.py 重写）：原生窗口承载界面（macOS WKWebView / Windows WebView2）——无地址栏、无浏览器标签页、不受扩展干扰；**关窗即优雅停服**（实测 0.3s：`prepare_exit()` 先经事件循环请 SSE 长连接干净退出、再停服，`timeout_graceful_shutdown` 强掐兜底——修复前表现为关窗后进程拖十几秒不退）；启动失败（端口占用）弹人话提示窗；lifespan 退出时始终关闭 Agent Chrome（根治孤儿进程锁 profile）。pywebview>=6.0,<7 入 requirements
- **首跑向导**（OnboardingWizard.vue 五步）：风险告知确认 → 简历拖放 → DeepSeek Key 粘贴即校验（新增 `POST /api/verify-key`：余额接口零成本校验 + 模型列表回退）→ 城市 + 单一期望最低月薪 → 扫码登录（新增 `POST /api/login` + `agent_runner.login_only()`：只登录校验即关浏览器）；`wizard_done` 持久化后启动直达主界面
- **Chrome 多路径探测**（`_find_chrome`）：Windows 用户级安装（%LOCALAPPDATA%）不再漏检——只查 Program Files 会漏一大半
- **结果分层页签**：「可投递 / 低于投递线」双 Tab，默认只渲染投递线以上卡片、低于线按需加载（顺带解决 110 卡全量渲染 + 毛玻璃的性能问题）；新增空状态引导（「点开始」式指引替代纯「等待启动」）
- **错误白话化**：DeepSeek 401/402 → 「Key 无效 / 余额不足」人话直传评分熔断消息；登录失效/扫码超时给出「重新点开始即可」式动作指引；Key/余额类错误横幅点击直达设置；「出错·请查看日志」（买家无日志可看）改为「详见下方提示」

### 修复（关键）
- **发送假发送（P0）**：双重根因——① BOSS 会话页输入框已改为 `.chat-input`（contenteditable），页面遗留一个 0×0 隐藏脚手架 TEXTAREA，裸 `textarea` 选择器优先命中它：字打进隐藏元素、回读通过、Enter 无效；② macOS 对后台窗口的键盘事件有节流，合成 Enter 在 Chrome 非前台时静默丢失。修复：聚焦 `.chat-input` → `insert_text` → **JS click() 发送按钮**（DOM 级调用，免疫键盘节流）→ **消息列表投递后验证**（杜绝一切假发送）。连续 4 条真实发送验证送达
- **设置保存互相清空**：`POST /api/settings` 原为整体重建 user_settings.yaml——分步保存会清掉其他字段（向导多步保存必踩）；改为合并写入

### 变更
- **发布包瘦身 86.9→52.3MB（-40%）**：PyMuPDF（79MB 二进制，占包近半）→ pdfminer.six（纯 Python ~5MB）——实测同一份简历提取字符集重合 461/462；简历每次运行只读一次，速度差异无感
- **评分语义重构**：删除死配置 matching.criteria 权重 / tiers.count·max_score / fake_job_detection.keywords（早期规则评分系统遗骸，全后端零消费者）；虚假招聘判断收敛为公司名黑名单 regex（评分前拦截、省 LLM 调用）+ DeepSeek 单轨；「可尝试」档退役为「低于投递线」（0-39 与 40-59 展示层不再区分）
- **设置抽屉精简**：删关键词输入框（搜索词由 AI 按简历自动生成）、逐城薪资门槛改单一「期望最低月薪」
- 使用手册同步桌面壳形态（五步引导 / 原生窗口 / 双 Tab / 新错误提示 / FAQ 重写）

## [1.3.0] - 2026-10-29

商业化准备：自服务发布形态——「解压 → 双击 → 界面填 Key → 开始」。

### 新增
- **城市支持 8 → 73**：新增 `backend/city_codes.py` 官方码表——28 城直接抓取 BOSS 拼音 SEO 页的 citySiteCode 验证，45 城经「天气码末位 1→0 = BOSS 码」规则推导（规则在 27 个直验城市上 100% 成立）。重要发现：BOSS 城市码**不是**天气网标准码（长春 101060100 vs 天气 101060101）；错误城市码由 check_city 城市名校验兜底（表现为搜不到岗位而非投错城市）。扩展与再验证方法见该文件 docstring
- **设置界面（自服务）**：`/api/settings` 读写端点 + 设置抽屉重写——DeepSeek Key 在界面填写（保存前调 DeepSeek 校验，写入 .env 立即生效）、城市多选 + 每城薪资门槛、搜索关键词，写入 `data/user_settings.yaml` 覆盖层（不动 config.yaml 本体，可随时删除恢复默认）；未配置 Key 时自动弹出设置引导
- **后端直接托管前端**：存在 frontend/dist 时由 FastAPI 伺服静态文件 + SPA 回退（含路径穿越防护），发布形态无需 Node.js；无构建产物时自动回退 Vite 开发模式
- **package.py 发布打包脚本**：前端构建 → pyinstaller 打当前平台可执行 → 组装（可执行 + 前端产物 + 干净 config + 手册 + 双击入口）→ 敏感内容扫描 fail-closed（.env/简历/data/.git 混入即失败删包）
- **GitHub Actions 发布流水线**（.github/workflows/release.yml）：windows + macos 双平台矩阵（跑测试 → 构建前端 → package.py → 上传 zip 产物，nodriver 锁定本地验证版本）；手动触发或推 tag（如 v1.3.0）——tag 触发时自动创建 GitHub Release 并附两个平台的 zip（永久下载链接）；pyinstaller 不支持交叉编译，Windows 包由此产出
- **launcher.py 打包入口**：frozen 模式下以 ORCHESTRA_ROOT 定位用户目录
- **docs/使用手册.md**：买家版三步上手 + FAQ + 免责声明（macOS Gatekeeper / Windows SmartScreen 提示）

### 修复
- start.bat：不再 `taskkill /f /im chrome.exe` 全杀用户浏览器（改为 PowerShell 只杀本项目 chrome-profile 进程）；去掉 --reload；双形态启动
- start.sh：双形态启动（有 dist 免 Node）

## [1.2.0] - 2026-10-29

生产前审计修复（ECC 七维审计：产品/设计/开发/验收/目标）。

### 修复（关键）
- **端口 5000→5001 全链路统一**：config/start.sh/Docker/nginx/vite（macOS AirPlay 占用 5000，原来 `./start.sh` 无法启动）
- **跨会话去重失效**：`reset_session` 清空内存记录导致每次运行把 applied_jobs.json 覆盖成只剩本次会话；改为历史永久保留（max_records=2000）+ 会话视图切片，损坏文件先备份再重建
- **发送结果造假**：`send_greetings` 原来无论 CDP 输入是否成功都返回 ok=True；改为输入框回读校验 + 逐条真实状态（sent/send_failed 回写记录，send_failed 解除公司拉黑）
- **薪资「万」格式误杀**：`2-3万` 被解析成 2K，高薪岗位被静默过滤；支持 万/日薪/年薪 格式
- **向量粗筛空结果吞掉整批岗位**：全部低于阈值时回退全量送 LLM；min_score 改为 config 可调（默认 0）
- **简历缺失静默跑全流程**：`_read_resume` 失败直接中止并报错（原来用占位符跑完整个评分+招呼语）
- **测试是假的**：test_record_manager 原来测自造 Fake 类、test_validator 断言已过期且失败；全部改为测真实实现，CI 安装依赖后跑全部测试

### 新增（发送安全栅栏）
- 每日发送上限 `safety.daily_send_cap`（默认 25，跨运行累计）
- 发送间隔 `safety.send_delay_min/max`（默认 45-120 秒/条，模拟真人）
- 发送时间窗口 `safety.active_hours`（可选，如 "09:00-20:00"）
- 连续 3 条发送失败自动熔断；连续 5 次 LLM 评分失败中止本轮；连续 3 次搜索失败判定风控/验证码并中止
- `min_apply_score`（默认 60）：低于投递线的岗位只进待审区，不自动生成招呼语
- 前端：刷新后恢复卡片与已发送数、SSE 指数退避重连、招呼语可编辑、默认文案徽标、「已发送」真实计数

### 优化
- stop() 真正取消任务；发送循环响应停止；发送与搜索互斥
- Chrome profile 移到 data/chrome-profile（登录态跨重启保留）；start.sh 不再误杀用户自己的 Chrome、不用系统 python3、去掉 --reload
- 登录验证/JD 详情改为页面内 XHR（不再直接导航 API 地址）；add_url 白名单 + JSON 编码防注入
- Docker 端口只绑 127.0.0.1、密钥走 env_file；.dockerignore 排除简历 PDF；.env 权限 600
- 静默失败全面补日志（matcher/greeting/search/vector/detail/fetch），`except: pass` 清零
- 低置信岗位进待选区；虚假招聘/薪资过滤/去重前置统计上报；已投公司在 LLM 评分前去重

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
