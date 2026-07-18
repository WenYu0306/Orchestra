# LangGraph 迁移参考

当前 Agent 循环（`agent_runner.py:_run`）是一个手写的 while 循环 + DeepSeek 决策。
LangGraph 把同样的逻辑建模成**状态图**（StateGraph），好处是：

- **断点恢复** — LangGraph Checkpointer 自动保存每步状态，崩溃后从断点继续
- **可观测性** — LangSmith 自动追踪每一步的输入输出，不需要手写日志
- **人机协同** — `interrupt` 机制让验证码这类人工介入变得自然

## 状态定义

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

class AgentState(TypedDict):
    resume: str           # 简历文本
    keywords: list[str]   # 候选搜索词
    used_kw: set[str]     # 已用关键词
    cities: list[dict]    # 搜索城市
    candidates: list[ScoredJob]  # 候选池（对应 all_scored）
    loop: int             # 当前轮次
    stop: bool            # 停止信号
```

## 节点定义（每个节点 = 当前代码的一个方法）

```python
def launch_browser(state: AgentState) -> AgentState:
    """对应 _launch_and_login()"""
    ...

def prepare(state: AgentState) -> AgentState:
    """对应 _prepare_keywords() + _prepare_profile()"""
    ...

def search(state: AgentState) -> AgentState:
    """对应 _search_one() —— 单次搜索+评分。
    取一个未用关键词 + 一个城市，搜完加入 candidates。"""
    kw = next(k for k in state["keywords"] if k not in state["used_kw"])
    city = state["cities"][0]  # Agent 决策选城
    new = await agent_runner._search_one(kw, city["name"], ...)
    state["candidates"].extend(new)
    state["used_kw"].add(kw)
    state["loop"] += 1
    return state

def decide(state: AgentState) -> AgentState:
    """对应 _agent_decide() —— DeepSeek 决定下一步。"""
    ...

def reevaluate(state: AgentState) -> AgentState:
    """对应 _detail_reevaluate() —— top 30 详情重评。"""
    ...

def apply_tiers(state: AgentState) -> AgentState:
    """对应 _apply_tiers() —— 分层+生成招呼语。"""
    ...
```

## 图结构

```python
builder = StateGraph(AgentState)

builder.add_node("launch", launch_browser)
builder.add_node("prepare", prepare)
builder.add_node("search", search)
builder.add_node("decide", decide)          # DeepSeek 决策
builder.add_node("reevaluate", reevaluate)
builder.add_node("apply_tiers", apply_tiers)

builder.add_edge(START, "launch")
builder.add_edge("launch", "prepare")
builder.add_edge("prepare", "search")
builder.add_edge("search", "decide")

# 条件边 —— 对应 while 循环
builder.add_conditional_edges(
    "decide",
    lambda s: "search" if s["loop"] < 12 and len(s["candidates"]) < 300 else "reevaluate",
    {"search": "search", "reevaluate": "reevaluate"}
)

builder.add_edge("reevaluate", "apply_tiers")
builder.add_edge("apply_tiers", END)

# 启用断点恢复
graph = builder.compile(checkpointer=MemorySaver())
```

## 当前代码 vs LangGraph 对照

| 当前实现 | LangGraph 等价物 |
|---|---|
| `while not stop and loop < 12` | `add_conditional_edges(decide, ...)` |
| `all_scored` 列表 | `AgentState.candidates` |
| `used_kw` 集合 | `AgentState.used_kw` |
| `checkpoint.json` 手工写入 | `MemorySaver()` 自动 |
| `except Exception: pass` 吞错 | Checkpointer 恢复断点 |
| DeepSeek 决策回退 | 决定节点 Fallback 分支 |

## 为什么当前项目没用 LangGraph

1. 项目跑在个人笔记本上，不需要分布式追踪
2. 手动 while 循环对 12 轮小规模 Agent 足够
3. LangGraph 依赖链重（langchain-core + langgraph ≈ 50MB）

**面试话术：** "我手写过一个 Agent 循环来理解底层机制，也了解 LangGraph 如何用 StateGraph + Checkpointer 把同样的逻辑产品化。当前项目规模不需要 LangGraph，但如果要支持多用户、长时间运行和断点恢复，我会迁移到 LangGraph。"
