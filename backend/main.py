"""
Orchestra Backend —— FastAPI 入口。

启动方式（在项目根目录执行）：
    python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000
"""

import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent_runner import agent_runner
from .config_loader import get_config
from .record_manager import record_manager
from .sse_manager import sse_manager, AppStatus


# ============ 生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理"""
    try:
        config = get_config()
        print(f"✓ 配置加载成功")
        print(f"  - 平台: {config.platform.get('name', 'unknown')}")
        print(f"  - 搜索城市: {[c['name'] for c in config.search.get('cities', [])]}")
        print(f"  - Web UI: {config.web_ui.host}:{config.web_ui.port}")

        # 启动健康检查
        import os, shutil
        from pathlib import Path
        dsk = os.getenv("DEEPSEEK_API_KEY", "")
        if not dsk or dsk.startswith("your_"):
            print("⚠ DEEPSEEK_API_KEY 未设置，请编辑 .env 文件")
        resume_path = Path(config.resume.get("pdf_path", "my_resume.pdf"))
        if not resume_path.is_absolute():
            resume_path = Path(__file__).parent.parent / resume_path
        if not resume_path.exists():
            print(f"⚠ 简历未找到: {resume_path}")
        if not shutil.which("google-chrome") and not shutil.which("Google Chrome") and not Path("/Applications/Google Chrome.app").exists():
            print("⚠ 未检测到 Google Chrome")
    except Exception as e:
        print(f"⚠ 配置加载警告: {e}")

    if config.web_ui.auto_open:
        try:
            webbrowser.open("http://localhost:5173")
        except Exception:
            pass

    yield

    await sse_manager.shutdown()
    if agent_runner.is_running:
        print("正在停止后台任务...")
        await agent_runner.stop()


# ============ FastAPI 实例 ============

config = get_config()

app = FastAPI(
    title="Orchestra API",
    version="1.0.0",
    description="Orchestra — AI Agent 编排框架，BOSS 直聘智能求职应用",
    lifespan=lifespan,
)

# CORS —— 允许本地前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 数据模型 ============

class StatusResponse(BaseModel):
    status: str = "idle"
    is_running: bool = False
    is_paused: bool = False
    tier_counts: dict = {}
    total_applied: int = 0
    pending_count: int = 0


class StartResponse(BaseModel):
    success: bool
    message: str


# ============ REST API ============


@app.get("/api/status", response_model=StatusResponse,
          summary="获取运行状态", description="返回 Agent 是否运行中、已匹配数量、分层统计")
async def get_status():
    """获取当前运行状态"""
    return StatusResponse(
        status=sse_manager.status.value,
        is_running=agent_runner.is_running,
        is_paused=agent_runner.is_paused,
        tier_counts=record_manager.get_tier_counts(),
        total_applied=record_manager.get_record_count(),
        pending_count=len(record_manager.get_all_pending()),
    )


@app.post("/api/start", response_model=StartResponse,
          summary="启动任务", description="启动 Agent 搜索评分流程：开浏览器→登录→搜→评→分层→问候语")
async def start_task():
    """启动投递任务"""
    try:
        await agent_runner.start()
        return StartResponse(success=True, message="投递任务已启动")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@app.post("/api/stop", response_model=StartResponse,
          summary="停止任务", description="停止正在运行的 Agent 任务，关闭 Chrome")
async def stop_task():
    """停止投递任务"""
    try:
        await agent_runner.stop()
        return StartResponse(success=True, message="投递任务已停止")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")


@app.post("/api/resume", response_model=StartResponse,
          summary="继续任务", description="手动处理完验证码后调用此接口恢复运行")
async def resume_task():
    """处理完验证码后继续"""
    if not agent_runner.is_paused:
        raise HTTPException(status_code=400, detail="当前不需要处理验证码")

    try:
        await agent_runner.resume_after_captcha()
        return StartResponse(success=True, message="已继续")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"继续失败: {str(e)}")


@app.get("/api/records",
         summary="获取投递记录", description="返回当前会话所有已评分的岗位记录")
async def get_records():
    """获取所有投递记录"""
    return {
        "records": record_manager.get_all_records(),
        "total": record_manager.get_record_count(),
    }


@app.get("/api/pending",
         summary="获取待选区", description="低置信度候选保留在此，最多 5 条")
async def get_pending():
    """获取待选区列表"""
    return {
        "items": record_manager.get_all_pending(),
        "count": len(record_manager.get_all_pending()),
    }


# ============ SSE 端点 ============

@app.get("/api/events",
         summary="SSE 实时推送", description="前端通过 EventSource 订阅：status/record/complete/error 四种事件")
async def sse_events():
    """SSE 事件流 —— 前端通过 EventSource 订阅"""
    return await sse_manager.subscribe()


# ============ 发送招呼语 ============

class SendJob(BaseModel):
    securityId: str
    encryptJobId: str = ""
    greeting: str
    company: str = ""

class SendRequest(BaseModel):
    jobs: list[SendJob]


@app.post("/api/send",
          summary="批量发送招呼语", description="将前端选中的岗位逐条发送：friend/add.json 建关系 → CDP 输入自定义文案")
async def send_greetings(req: SendRequest):
    """发送招呼语给前端选中的职位"""
    if not agent_runner._tab:
        raise HTTPException(status_code=400, detail="浏览器未就绪，请先运行搜索评分")
    if agent_runner.is_running:
        raise HTTPException(status_code=409, detail="已有任务运行中")

    jobs = [{"securityId": j.securityId, "encryptJobId": j.encryptJobId,
             "greeting": j.greeting, "company": j.company}
            for j in req.jobs]
    return await agent_runner.send_greetings(jobs)


@app.post("/api/close",
          summary="关闭浏览器", description="手动关闭 nodriver Chrome 浏览器")
async def close_browser():
    """关闭浏览器"""
    await agent_runner.close_browser()
    return {"ok": True, "message": "浏览器已关闭"}


# ============ 快速测试（验证 AI 链路） ============

@app.get("/api/test",
         summary="AI 链路验证", description="不开浏览器纯测 AI：读简历→搜词生成→JD 打分")
async def test_pipeline():
    """快速测试：简历读取 → 搜索词生成 → JD 匹配打分，不开浏览器"""
    import time
    results = {"steps": [], "errors": []}

    # Step 1: 读取简历
    t0 = time.time()
    try:
        resume_text = agent_runner._read_resume()
        preview = resume_text[:200] + "..." if len(resume_text) > 200 else resume_text
        results["steps"].append({
            "step": "读取简历",
            "ok": True,
            "chars": len(resume_text),
            "preview": preview,
            "elapsed_ms": int((time.time() - t0) * 1000),
        })
    except Exception as e:
        results["steps"].append({"step": "读取简历", "ok": False, "error": str(e)})
        results["errors"].append(f"读取简历: {e}")
        return results

    # Step 2: 生成搜索方向
    t0 = time.time()
    try:
        from .search_generator import generate as sg_gen
        directions = await sg_gen(resume_text)
        results["steps"].append({
            "step": "搜索词生成",
            "ok": True,
            "directions": directions,
            "elapsed_ms": int((time.time() - t0) * 1000),
        })
    except Exception as e:
        results["steps"].append({"step": "搜索词生成", "ok": False, "error": str(e)})
        results["errors"].append(f"搜索词生成: {e}")

    # Step 3: JD 匹配打分（用一段示例 JD）
    t0 = time.time()
    try:
        from .matcher import match as ds_match
        sample_jd = (
            "职位：AI应用开发工程师。"
            "要求：精通Python，有LLM应用开发经验，熟悉LangChain、向量数据库。"
            "加分项：全栈能力、有跨行业项目经验。"
            "薪资：20K-35K，工作地点：北京。"
        )
        match_result = await ds_match(resume_text, sample_jd)
        results["steps"].append({
            "step": "JD匹配打分",
            "ok": True,
            "sample_jd": sample_jd,
            "result": match_result,
            "elapsed_ms": int((time.time() - t0) * 1000),
        })
    except Exception as e:
        results["steps"].append({"step": "JD匹配打分", "ok": False, "error": str(e)})
        results["errors"].append(f"JD匹配打分: {e}")

    return results


# ============ 根路径跳转到前端 ============

@app.get("/")
async def root():
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="http://localhost:5173")


# ============ 健康检查 ============

@app.get("/api/health",
         summary="健康检查", description="返回服务运行状态")
async def health():
    return {"status": "ok", "service": "Orchestra"}


# ============ 直接运行 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=config.web_ui.host,
        port=config.web_ui.port,
        reload=True,
    )
