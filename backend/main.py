"""
Orchestra Backend —— FastAPI 入口。

启动方式（在项目根目录执行）：
    python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5001
"""

import os
import webbrowser
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel

from .agent_runner import agent_runner, BOSS_CODE
from .config_loader import (get_config, get_project_root, get_llm_base_url,
                            get_user_flag, reload_config)
from .record_manager import record_manager
from .sse_manager import sse_manager, AppStatus

# 前端构建产物目录：存在则由后端直接托管页面（发布形态，无需另跑 Vite/Node）
_DIST = get_project_root() / "frontend" / "dist"

# 服务事件循环引用：桌面壳关窗时从主线程安全触发 SSE 干净退出（prepare_exit）
_loop: Optional[asyncio.AbstractEventLoop] = None


def prepare_exit() -> None:
    """线程安全地让所有 SSE 连接干净退出。桌面壳关窗后、停服前调用。

    SSE 是永不主动结束的流；不先关它们，uvicorn 优雅停服会一直等
    （表现为关窗后进程拖好几秒）。sse_manager.shutdown 让每个流的
    generator 正常 return → 连接正常完成 → 停服无需等待。
    """
    if _loop is not None and _loop.is_running():
        _loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(sse_manager.shutdown()))


# ============ 生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理"""
    global _loop
    _loop = asyncio.get_running_loop()
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
            resume_path = get_project_root() / resume_path
        if not resume_path.exists():
            print(f"⚠ 简历未找到: {resume_path}")
        if not shutil.which("google-chrome") and not shutil.which("Google Chrome") and not Path("/Applications/Google Chrome.app").exists():
            print("⚠ 未检测到 Google Chrome")
    except Exception as e:
        print(f"⚠ 配置加载警告: {e}")

    if config.web_ui.auto_open and not os.environ.get("ORCHESTRA_SHELL"):
        # 桌面壳形态（launcher.py）由 pywebview 开窗口，不再另开浏览器标签页
        try:
            if (_DIST / "index.html").exists():
                webbrowser.open(f"http://127.0.0.1:{config.web_ui.port}")
            else:
                webbrowser.open("http://localhost:5173")
        except Exception:
            pass

    yield

    await sse_manager.shutdown()
    if agent_runner.is_running or agent_runner.is_sending:
        print("正在停止后台任务...")
        await agent_runner.stop()
    # 退出时始终关闭 Agent Chrome——孤儿 Chrome 会锁住 data/chrome-profile，
    # 下次启动登录态读取失败（桌面壳"关窗即退净"的最后一环）
    await agent_runner.close_browser()
    # 关闭各模块的共享 httpx 客户端，避免连接句柄泄漏
    from . import matcher as _matcher, greeting_generator as _greet, search_generator as _search
    from . import agent_runner as _ar_mod
    for client in (_matcher._shared_client, _greet._shared_client,
                   _search._shared_client, _ar_mod._agent_shared_client):
        if client is not None:
            try:
                await client.aclose()
            except Exception as e:
                print(f"⚠ httpx 客户端关闭失败: {e}")


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


class UploadResumeResponse(BaseModel):
    ok: bool
    filename: str = ""

# ============ REST API ============

@app.post("/api/upload-resume", response_model=UploadResumeResponse,
          summary="上传简历", description="上传 PDF 简历文件")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")
    save_path = get_project_root() / "my_resume.pdf"
    # 删旧文件——可能被锁或正在用，先试删
    if save_path.exists():
        try:
            save_path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"无法替换旧文件: {e}")
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    return UploadResumeResponse(ok=True, filename=file.filename)


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


# ============ 设置（自服务：在界面上填 Key / 城市 / 关键词，免改配置文件） ============

class CitySetting(BaseModel):
    name: str
    min_salary: int = 0

class SettingsRequest(BaseModel):
    deepseek_key: str = ""
    cities: list[CitySetting] = []
    primary_keywords: list[str] = []
    wizard_done: Optional[bool] = None


class VerifyKeyRequest(BaseModel):
    key: str


def _write_env_key(key: str) -> None:
    """把 DEEPSEEK_API_KEY 写入 .env（保留其他行），并立即生效到当前进程"""
    env_path = get_project_root() / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    kept, replaced = [], False
    for line in lines:
        if line.startswith("DEEPSEEK_API_KEY="):
            kept.append(f"DEEPSEEK_API_KEY={key}")
            replaced = True
        else:
            kept.append(line)
    if not replaced:
        kept.append(f"DEEPSEEK_API_KEY={key}")
    env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    os.environ["DEEPSEEK_API_KEY"] = key


@app.get("/api/settings",
         summary="读取设置", description="返回 Key 配置状态、支持的城市与当前搜索设置")
async def get_settings():
    cfg = get_config()
    key = os.getenv("DEEPSEEK_API_KEY", "")
    resume_path = Path(cfg.resume.get("pdf_path", "my_resume.pdf"))
    if not resume_path.is_absolute():
        resume_path = get_project_root() / resume_path
    return {
        "key_configured": bool(key) and not key.startswith("your_"),
        "key_tail": key[-4:] if len(key) >= 8 else "",
        "supported_cities": list(BOSS_CODE.keys()),
        "cities": cfg.search.get("cities", []),
        "primary_keywords": cfg.search.get("primary_keywords", []),
        "wizard_done": get_user_flag("wizard_done"),
        "resume_uploaded": resume_path.exists(),
    }


@app.post("/api/settings",
          summary="保存设置", description="Key 写入 .env、城市/关键词写入 data/user_settings.yaml，立即生效")
async def save_settings(req: SettingsRequest):
    result = {"ok": True, "key_valid": None, "message": ""}
    try:
        # ---- DeepSeek Key ----
        key = req.deepseek_key.strip()
        if key:
            # 保存前轻量校验（调一次模型列表；网络异常不阻塞保存）
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(f"{get_llm_base_url('deepseek')}/models",
                                         headers={"Authorization": f"Bearer {key}"})
                    result["key_valid"] = r.status_code == 200
                    if r.status_code == 401:
                        result["ok"] = False
                        result["message"] = "DeepSeek Key 无效（401），请检查后重填"
                        return result
            except Exception as e:
                print(f"⚠ Key 校验请求失败（不阻塞保存）: {e}")
            _write_env_key(key)
            result["message"] = "Key 已保存" + ("（校验通过）" if result["key_valid"] else "")

        # ---- 城市 / 关键词 / 向导标记 ----
        # 合并旧值而非整体重建：否则只保存 Key 会把已存的城市清空（向导分步保存的坑）
        root = get_project_root()
        (root / "data").mkdir(parents=True, exist_ok=True)
        us_path = root / "data" / "user_settings.yaml"
        try:
            overrides = yaml.safe_load(us_path.read_text(encoding="utf-8")) if us_path.exists() else {}
        except Exception:
            overrides = {}
        if not isinstance(overrides, dict):
            overrides = {}
        search = overrides.setdefault("search", {})
        if req.cities:
            supported = [c for c in req.cities if c.name in BOSS_CODE]
            dropped = len(req.cities) - len(supported)
            if dropped:
                result["message"] += f"（{dropped} 个不支持的城市被忽略）"
            search["cities"] = [
                {"name": c.name, "min_salary": c.min_salary} for c in supported]
        if req.primary_keywords:
            search["primary_keywords"] = [
                k.strip() for k in req.primary_keywords if k.strip()]
        if req.wizard_done is not None:
            overrides["wizard_done"] = req.wizard_done
        us_path.write_text(
            yaml.safe_dump(overrides, allow_unicode=True), encoding="utf-8")

        reload_config()
        if not result["message"]:
            result["message"] = "设置已保存"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@app.post("/api/verify-key",
          summary="校验 DeepSeek Key", description="粘贴即校验：返回有效性与余额，不保存")
async def verify_key(req: VerifyKeyRequest):
    """向导第 3 步用：调 DeepSeek 余额接口验证 Key（零成本），代理 base_url 无此端点时回退模型列表。"""
    key = req.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="请输入 Key")
    import httpx
    base = get_llm_base_url("deepseek").rstrip("/")
    balance_url = (base[:-3] if base.endswith("/v1") else base) + "/user/balance"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(balance_url, headers=headers)
            if r.status_code == 401:
                return {"valid": False, "balance": None, "message": "Key 无效，请检查是否复制完整"}
            if r.status_code == 200:
                infos = (r.json().get("balance_infos") or [])
                balance = next((f"{i.get('total_balance')} {i.get('currency')}"
                                for i in infos if i.get("currency") == "CNY"), None)
                return {"valid": True, "balance": balance,
                        "message": "Key 有效" + (f"，余额 {balance}" if balance else "")}
            # 自定义 base_url/代理可能没有 balance 端点 → 回退模型列表校验
            r2 = await client.get(f"{base}/models", headers=headers)
            if r2.status_code == 200:
                return {"valid": True, "balance": None, "message": "Key 有效"}
            if r2.status_code == 401:
                return {"valid": False, "balance": None, "message": "Key 无效，请检查是否复制完整"}
            return {"valid": False, "balance": None,
                    "message": f"校验失败（HTTP {r.status_code}），请稍后重试"}
    except httpx.HTTPError as e:
        return {"valid": False, "balance": None, "message": f"网络异常，无法连接 DeepSeek：{e}"}


@app.post("/api/login", response_model=StartResponse,
          summary="首跑向导：仅登录", description="启动浏览器扫码登录并验证 cookie，不进入搜索评分")
async def login_only():
    """向导第 5 步用；登录态保存后，之后正式运行免扫码。"""
    try:
        ok = await agent_runner.login_only()
        return StartResponse(success=ok, message="登录成功" if ok else "登录未完成")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录引导失败: {e}")


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
        raise HTTPException(status_code=409, detail="搜索评分任务运行中，请先停止")
    if agent_runner.is_sending:
        raise HTTPException(status_code=409, detail="正在发送招呼语，请等待完成")

    jobs = [{"securityId": j.securityId, "encryptJobId": j.encryptJobId,
             "greeting": j.greeting, "company": j.company}
            for j in req.jobs]
    return await agent_runner.send_greetings(jobs)


@app.post("/api/close",
          summary="关闭浏览器", description="手动关闭 nodriver Chrome 浏览器")
async def close_browser():
    """关闭浏览器"""
    if agent_runner.is_sending:
        raise HTTPException(status_code=409, detail="正在发送招呼语，请先等待完成或停止")
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
        results["steps"].append({
            "step": "读取简历",
            "ok": True,
            "chars": len(resume_text),
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


# ============ 根路径：有构建产物直接给页面，开发模式跳转 Vite ============

@app.get("/", include_in_schema=False)
async def root():
    if (_DIST / "index.html").exists():
        return FileResponse(_DIST / "index.html")
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="http://localhost:5173")


# ============ 健康检查 ============

@app.get("/api/health",
         summary="健康检查", description="返回服务运行状态")
async def health():
    import os
    status = "ok"
    checks = {"api_key": bool(os.getenv("DEEPSEEK_API_KEY","")),
              "chrome_alive": agent_runner._browser is not None,
              "tab_alive": agent_runner._tab is not None}
    if not checks["api_key"]:
        status = "degraded"
    return {"status": status, "service": "Orchestra", "checks": checks}


# ============ 前端静态托管（发布形态） ============

if (_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA 回退：非 /api 路径回 index.html（前端路由）；未知 /api 路径 404"""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (_DIST / full_path).resolve()
            # 防路径穿越：解析后的路径必须仍在 dist 内
            if str(candidate).startswith(str(_DIST.resolve())) and candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")


# ============ 直接运行 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=config.web_ui.host,
        port=config.web_ui.port,
        reload=True,
    )
