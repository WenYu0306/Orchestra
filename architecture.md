# Orchestra — 多平台 Agent 架构

```
                         config.yaml: platform.name
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         BossAdapter       ZhilianAdapter     WuyouAdapter
         (XHR API)         (CDP + DOM)       (Qwen VL 视觉)
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                    PlatformAdapter 接口
                  5 个方法，平台无关
              search() fetch_detail() send() ...
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         VectorDB 粗筛    DeepSeek 评分    validator 栅栏
        (TF-IDF+余弦)    (标签初筛+详情重评)   (城市/公司/薪资)
                                │
                                ▼
                    Agent 决策层（不变）
              观察→决策→执行循环 + 硬规则兜底
                                │
                                ▼
                      SSE 实时推送 → Vue 3 前端
```

## 平台适配层

每个招聘平台只需实现 5 个方法即可接入：

| 方法 | BOSS 直聘 | 智联招聘 |
|------|----------|---------|
| `search()` | XHR 调 `joblist.json` | CDP 输入 + 新标签页拦截 |
| `fetch_job_detail()` | `card.json?securityId=` | 导航 `jobdetail/CC...htm` |
| `send_greeting()` | `friend/add.json` + CDP 自定义文案 | 点 "立即投递" 系统简历 |
| `city_codes` | 9 位数字 `101010100` | 3 位数字 `530` |
| `login_url` | `zhipin.com/web/geek/job` | `zhaopin.com/beijing/` |

## 核心流程

```
用户点击「开始」
  │
  ▼
启动 Chrome → 扫码登录 → Cookie 验证
  │
  ▼
DeepSeek 拆简历 → 3 个技能侧面 + 动态生成搜索关键词
  │
  ▼
┌─ Agent 循环 ─────────────────────────────────────┐
│                                                  │
│  首轮：每个城市 × 前 3 个关键词摸底               │
│  ↓                                                │
│  观察状态 → DeepSeek 决策（搜什么/搜哪个城/停）   │
│  ↓                                                │
│  执行 → 新状态 → 再决策                           │
│  ↓                                                │
│  硬规则兜底：12 轮 或 300 候选 自动停             │
└──────────────────────────────────────────────────┘
  │
  ▼
标签评分：搜索字段拼 JD → DeepSeek 快评
  │
  ▼
VectorDB 粗筛：TF-IDF 余弦相似度，取 top 20
  │
  ▼
validator 三道栅栏：城市/公司/薪资 硬过滤
  │
  ▼
详情重评：top 30 拿完整 JD → DeepSeek 精排
  │
  ▼
分层：≥80 高分 / ≥60 中分 / <60 可试，不限配额
  │
  ▼
SSE 实时推送 → 前端卡片展示
  │
  ▼
用户勾选 → XHR + CDP 发送（BOSS）/ 点按钮投递（智联）
```

## 组件树

```
App.vue
├── TopBar.vue          Logo + 状态指示器 + 简历上传 + 开始/停止
├── ProgressBand.vue    进度条 + 步骤提示
├── StatCards.vue       高分/中分/可试/总数 四张统计卡
├── JobList.vue         排序 + 发送选中按钮 + 卡片列表
│   └── JobCard.vue     公司名 + 职位名 + 分数 + 招呼语 + 复选框
└── BottomBar.vue       底部信息栏
```

## 核心技术数据

| 指标 | BOSS 直聘 | 智联招聘 |
|------|----------|---------|
| 搜索方式 | XHR 调内部 API | CDP 输入 + 新标签页 |
| 数据格式 | 结构化 JSON | DOM 文本提取 |
| 反爬策略 | `nodriver` + 小众CDP库 | 同上（反爬弱于 BOSS） |
| 编码难度 | API 已逆向 | 浏览器自动编码 |
| 投递方式 | friend/add.json + CDP 自定义文案 | 点按钮系统投递 |
| 招呼语 | DeepSeek 生成，CDP 内核注入 | 系统默认文案 |

## 设计理念

- **多层解耦。** 连接/执行/决策三层分离，平台改只动连接层
- **功能主义。** 进度条和统计卡片数字跳变比动效更重要
- **干扰最小。** 状态灯安静呼吸，遇到问题才变色
- **配色系统。** 浅色基底，靛蓝/蓝/琥珀三层区分
- **毛玻璃面板。** `backdrop-filter: blur(24px)` + 多层阴影
