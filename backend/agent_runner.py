"""
Agent — 单阶段: 搜→标签评分→全局排序→top 20 详情重评→最终分层。
稳定优先，每次API调用间隔3-8秒。
"""
import asyncio, json, logging, os, random, re, sys, time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import nodriver as uc

from .config_loader import get_config, get_api_key, get_llm_base_url, get_project_root
from .city_codes import CITY_CODE as BOSS_CODE
from .greeting_generator import generate as gen_greeting
from .matcher import match as ds_match
from .record_manager import record_manager
from .sse_manager import sse_manager, AppStatus
from .validator import check_city, check_salary, check_company
from dataclasses import dataclass, field

# BOSS 直聘城市代码映射见 backend/city_codes.py（73 城 + 全国，扩展方法见该文件）

# 沟通按钮的六种文本变体
_GREET_BTNS = ["立即沟通","发起沟通","沟通一下","聊一聊","联系Ta","开始沟通"]


@dataclass
class ScoredJob:
    """一个已评分的职位候选。全程用属性名访问，不再用 9 元组索引。"""
    score: int
    company: str
    position: str
    jd: str
    keyword: str
    city: str
    match: dict
    security_id: str
    encrypt_job_id: str
    salary: str = ""


# ---- logging setup ----
_log = logging.getLogger("agent")
_log.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")

# console handler
_ch = logging.StreamHandler(sys.stdout); _ch.setFormatter(_fmt); _log.addHandler(_ch)

# file handler — daily rotating, keep 7 days
_log_dir = get_project_root() / "data" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_fh = TimedRotatingFileHandler(str(_log_dir / "agent.log"), when="midnight", backupCount=7,
                               encoding="utf-8")  # GBK 机器上缺这个会写不进 ✓/⚠（售后排障依赖日志）
_fh.suffix = "%Y-%m-%d"
_fh.setFormatter(_fmt); _log.addHandler(_fh)


class AgentRunner:
    def __init__(self):
        self._task = None; self._stop = False; self._browser = None; self._tab = None
        self._resume = ""
        self._tc = {"high":0,"medium":0,"try":0}
        self._sending = False
        self._llm_fail_streak = 0
        self._search_fail_streak = 0
        self._decide_fallbacks = 0
        self._stats = {}

    @property
    def is_running(self): return self._task is not None and not self._task.done()
    @property
    def is_sending(self): return self._sending

    async def start(self):
        if self.is_running or self._sending:
            raise RuntimeError("搜索评分运行中" if self.is_running else "正在发送招呼语，请等待完成")
        if self._browser:
            try: self._browser.stop()
            except Exception: _log.warning("browser.stop() failed on restart", exc_info=True)
            self._browser = None; self._tab = None
        self._stop = False; self._tc = {"high":0,"medium":0,"try":0}
        self._llm_fail_streak = 0; self._llm_fail_reason = "DeepSeek 连续评分失败"; self._search_fail_streak = 0; self._decide_fallbacks = 0
        self._stats = {"salary_skipped":0,"city_mismatch":0,"company_rejected":0,"excluded":0,
                       "fake":0,"low_conf":0,"llm_failed":0,"dup_skipped":0}
        record_manager.reset_session()
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop = True
        # 取消搜索/评分任务（发送循环通过 _stop 自行中断）
        if self._task and not self._task.done():
            self._task.cancel()
            try: await asyncio.wait_for(self._task, timeout=10)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception) as e:
                _log.debug(f"停止任务收尾: {type(e).__name__}")
            self._task = None
        try: await sse_manager.emit_status(AppStatus.IDLE, {"message":"已停止"})
        except Exception: _log.warning("emit_status failed on stop", exc_info=True)

    async def login_only(self) -> bool:
        """首跑向导专用：只启动浏览器 → 扫码登录 → cookie 校验，然后关闭浏览器。

        不进入搜索评分；登录态保存在 data/chrome-profile，之后正式运行免扫码。
        """
        if self.is_running or self._sending:
            raise RuntimeError("任务运行中，无法执行登录引导")
        if self._browser:
            try:
                self._browser.stop()
            except Exception:
                _log.warning("browser.stop() failed in login_only", exc_info=True)
            self._browser = None
            self._tab = None
        self._stop = False
        try:
            ok = await self._launch_and_login()
            if ok:
                await sse_manager.emit_status(AppStatus.COMPLETED, {"message": "登录成功"})
            return ok
        finally:
            # 校验完就关：登录态在 profile 里，留着窗口只会让买家困惑
            if self._browser:
                try:
                    self._browser.stop()
                except Exception:
                    _log.debug("browser.stop() failed on login_only exit")
                self._browser = None
                self._tab = None

    async def _sleep(self, mult: float = 1.0):
        """内部动作（翻页/评分/记录）间隔：safety.min_delay~max_delay × mult"""
        cfg = get_config()
        lo = max(0.5, cfg.safety.min_delay * mult)
        hi = max(lo + 0.1, cfg.safety.max_delay * mult)
        await asyncio.sleep(random.uniform(lo, hi))

    async def _send_sleep(self):
        """真实发送招呼语之间的间隔——对平台可见的动作，必须足够像人"""
        cfg = get_config()
        await asyncio.sleep(random.uniform(cfg.safety.send_delay_min, cfg.safety.send_delay_max))

    @staticmethod
    def _check_active_hours(win: str) -> tuple[bool, str]:
        """检查当前是否在允许发送的时间窗口内（如 09:00-20:00）"""
        try:
            lo, hi = win.split("-")
            now = time.localtime()
            cur = now.tm_hour * 60 + now.tm_min
            lh, lm = (int(x) for x in lo.strip().split(":"))
            rh, rm = (int(x) for x in hi.strip().split(":"))
            if not (lh * 60 + lm <= cur <= rh * 60 + rm):
                return False, f"当前不在允许发送时间窗口 {win} 内（config.yaml safety.active_hours）"
        except ValueError:
            _log.warning(f"active_hours 配置格式错误: {win!r}，应为 HH:MM-HH:MM")
        return True, ""

    async def _run(self):
        ok = False
        try:
            self._resume = self._read_resume()
            cfg = get_config()

            if not await self._launch_and_login():
                return

            # 城市校验：不在 BOSS_CODE 的城市会被静默按北京搜索
            cities_cfg = cfg.search.get("cities", [])
            unknown = [c.get("name") for c in cities_cfg if c.get("name") not in BOSS_CODE]
            if unknown:
                msg = f"配置城市不在 BOSS_CODE 映射中: {unknown}，请修正 config.yaml 或扩充 agent_runner.BOSS_CODE"
                _log.error(msg)
                await sse_manager.emit_error(msg)
                return

            keywords = await self._prepare_keywords(cfg)
            if not keywords:
                msg = "无可用搜索关键词（config.yaml search.primary_keywords 为空且动态生成失败）"
                _log.error(msg)
                await sse_manager.emit_error(msg)
                return
            _log.info(f"搜索关键词: {len(keywords)} 个 — {', '.join(keywords[:8])}")

            self._profiles = await self._prepare_profile(self._resume)
            _log.info(f"技能剖面: {self._profiles.count(chr(10))+1} 段")

            # === Agent 动态调度搜索 ===
            all_scored = []
            loop = 0
            used_kw = set()

            # 首轮：每个城市 × 前 3 个关键词摸底
            init_kw = keywords[:3]
            used_kw.update(init_kw)
            for kw in init_kw:
                if self._stop: break
                for c in cities_cfg:
                    if self._stop: break
                    cc = BOSS_CODE.get(c["name"], "101010100")
                    ms = c.get("min_salary", 0)
                    loop += 1
                    round_scored = await self._search_one(kw, c["name"], cc, ms)
                    all_scored.extend(round_scored)
                    high70 = sum(1 for x in all_scored if x.score >= 70)
                    _log.info(f"[Agent] 首轮{loop}: {kw}/{c['name']} +{len(round_scored)}, 池{len(all_scored)} ≥70:{high70}")
                    if self._search_fail_streak >= 3:
                        break
                if self._search_fail_streak >= 3:
                    msg = f"搜索连续 {self._search_fail_streak} 次失败——疑似验证码/风控/登录失效，中止运行"
                    _log.error(msg)
                    await sse_manager.emit_error(msg)
                    return

            # Agent 调度循环
            while not self._stop and loop < 12 and len(all_scored) < 300:
                remainder = [kw for kw in keywords if kw not in used_kw]
                if not remainder:
                    _log.info("[Agent] 无剩余关键词，停止搜索")
                    break

                dec = await self._agent_decide(all_scored, remainder,
                                            cities_cfg, loop, len(remainder))
                if dec.get("action") != "search":
                    break
                kw = dec.get("keyword", remainder[0]) if dec.get("keyword") in remainder else remainder[0]
                city_name = dec.get("city", cities_cfg[0]["name"])
                c_match = next((cc for cc in cities_cfg if cc["name"] == city_name), cities_cfg[0])
                cc = BOSS_CODE.get(c_match["name"], "101010100")
                ms = c_match.get("min_salary", 0)

                loop += 1
                used_kw.add(kw)
                round_scored = await self._search_one(kw, city_name, cc, ms)
                all_scored.extend(round_scored)
                high70 = sum(1 for x in all_scored if x.score >= 70)
                _log.info(f"[Agent] {loop}轮: {kw}/{city_name} +{len(round_scored)}, 池{len(all_scored)} ≥70:{high70}")
                if self._search_fail_streak >= 3:
                    msg = f"搜索连续 {self._search_fail_streak} 次失败——疑似验证码/风控/登录失效，中止运行"
                    _log.error(msg)
                    await sse_manager.emit_error(msg)
                    return

            st = self._stats
            _log.info(f"[统计] 薪资过滤{st.get('salary_skipped',0)} 城市不符{st.get('city_mismatch',0)} "
                      f"公司异常{st.get('company_rejected',0)} 排除词{st.get('excluded',0)} "
                      f"虚假招聘{st.get('fake',0)} 低置信{st.get('low_conf',0)} "
                      f"LLM失败{st.get('llm_failed',0)} 重复公司{st.get('dup_skipped',0)}")
            all_scored.sort(key=lambda x: x.score, reverse=True)
            _log.info(f"标签评分完成，共 {len(all_scored)} 个候选")

            enriched = await self._detail_reevaluate(all_scored)

            applied = await self._apply_tiers(enriched, cfg)

            await self._emit_results(applied)
            ok = True

        except Exception as e:
            _log.exception(f"Agent 运行异常终止: {e}")
            await sse_manager.emit_error(str(e))
        finally:
            # 异常或被停止时关闭浏览器；正常跑完保留浏览器供发送招呼语
            if self._browser and (self._stop or not ok):
                try: self._browser.stop()
                except Exception: _log.warning("browser.stop() failed in cleanup", exc_info=True)
                self._browser = None; self._tab = None

    # ====== 步骤方法 ======

    async def _prepare_profile(self, resume: str) -> str:
        """用 DeepSeek 把长简历压缩成 3 个技能侧面"""
        prompt = f"把你这份简历拆成 3 个不同方向的技能描写，每段 30-50 字，每段加编号 1. 2. 3.，方便每次只用一个方向去接岗位的点。\n\n简历：\n{resume[:3000]}"
        try:
            from .config_loader import get_api_key, get_llm_base_url
            from .llm import get_client
            url = f"{get_llm_base_url('deepseek')}/chat/completions"
            headers = {"Authorization": f"Bearer {get_api_key('deepseek')}", "Content-Type": "application/json"}
            body = {"model": "deepseek-chat", "messages": [
                {"role": "system", "content": "你是一个专业的简历分析器。"},
                {"role": "user", "content": prompt}],
                "temperature": 0.3, "max_tokens": 300}
            r = await get_client().post(url, json=body, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or "AI全栈开发，有Agent编排和RAG经验"
        except Exception as e:
            # 技能剖面是招呼语的事实来源；失败后继续会用编造的默认技能替本人求职——必须中止
            raise RuntimeError(f"技能剖面生成失败（DeepSeek）: {e}")

    async def _prepare_keywords(self, cfg) -> list:
        """合并配置预设 + DeepSeek 动态生成的关键词"""
        keywords = list(cfg.search.get("primary_keywords", []))
        try:
            from .search_generator import generate as sg_gen
            for d in await sg_gen(self._resume):
                for kw in d.get("keywords", []):
                    if kw not in keywords:
                        keywords.append(kw)
        except Exception as e:
            _log.warning(f"动态搜索词生成失败，仅使用配置关键词: {e}")
        return keywords

    def _find_chrome(self) -> str:
        """多路径探测 Chrome 可执行文件。

        Windows 用户级安装默认在 %LOCALAPPDATA%（无管理员权限装 Chrome 的用户全在这里），
        只查 Program Files 会漏一大半（docs/商业化方案.md §5 上架前必修）。
        """
        if os.name == "nt":
            candidates = []
            local = os.getenv("LOCALAPPDATA")
            if local:
                candidates.append(Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe")
            candidates += [
                Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            ]
            for c in candidates:
                if c.exists():
                    return str(c)
            raise RuntimeError("未找到 Google Chrome，请先安装：google.cn/chrome")
        if os.name == "posix":
            mac = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            if mac.exists():
                return str(mac)
            return "google-chrome-stable"  # Linux：交给 PATH
        raise RuntimeError(f"不支持的操作系统: {os.name}")

    async def _launch_and_login(self) -> bool:
        """启动 Chrome + 扫码登录 + Cookie 验证。返回 True 表示成功。"""
        await sse_manager.emit_status(AppStatus.RUNNING, {"message": "启动浏览器..."})
        headless = os.getenv("CHROME_HEADLESS", "0") == "1" or get_config().safety.headless
        chrome_path = self._find_chrome()
        # profile 放在 data/ 下：登录态跨重启保留，减少重复扫码（也降低风控特征）
        self._browser = await uc.start(headless=headless,
            browser_executable_path=chrome_path,
            user_data_dir=str(get_project_root() / "data" / "chrome-profile"),
            no_sandbox=headless or os.getenv("CHROME_NO_SANDBOX") == "1",
            browser_args=["--disable-blink-features=AutomationControlled", "--no-first-run"])
        self._tab = self._browser.main_tab
        await self._tab.get("https://www.zhipin.com/web/geek/job")
        await self._tab.sleep(8)

        cur = self._tab.target.url or ""
        if "/user/" in cur or "login" in cur.lower() or "passport" in cur.lower() or "/geek/job" not in cur:
            await sse_manager.emit_status(AppStatus.RUNNING, {"message": "请扫码登录"})
            for i in range(180):
                if self._stop:
                    return False
                await asyncio.sleep(2)
                cur = self._tab.target.url or ""
                if i % 10 == 0:
                    _log.info(f"[登录] 等待扫码确认… 当前页面: {cur[:80]}")
                # 扫码后常跳城市站/首页而非 /geek/job，放宽为任意 BOSS 正常页面；
                # 是否真正已登录由下一步 cookie 校验把关
                if cur.startswith("https://www.zhipin.com") and not any(
                        k in cur.lower() for k in ("login", "passport", "/user/", "security")):
                    _log.info(f"[登录] 检测到登录跳转: {cur[:80]}")
                    await self._tab.sleep(3)
                    break
            else:
                await sse_manager.emit_error("扫码超时（6 分钟未确认）——重新点「开始」再扫一次即可")
                return False

        await self._tab.sleep(5)

        # cookie 验证（页面内 XHR，避免直接导航到 API 地址留下指纹）
        verify_ok = False
        for _ in range(3):
            try:
                raw = await asyncio.wait_for(self._tab.evaluate("""
                    (function(){
                        var x=new XMLHttpRequest();
                        x.open('GET','/wapi/zpgeek/search/joblist.json?query=AI&city=101010100&page=1&pageSize=1',false);
                        try{x.send()}catch(e){return ''}
                        if(x.status!=200)return ''
                        return x.responseText.slice(0,2000);
                    })()
                """), timeout=15.0)
                if raw and isinstance(raw, str) and '"code":0' in raw and '"jobList"' in raw:
                    verify_ok = True
                    break
            except Exception:
                await asyncio.sleep(1)
        if not verify_ok:
            await sse_manager.emit_error(
                "BOSS 登录态已失效——重新点「开始」会弹出 Chrome 窗口，扫码登录即可恢复")
            return False

        _log.info("Cookie 验证通过")
        return True

    async def _search_one(self, kw: str, city_name: str, city_code: str, min_sal: int) -> list:
        """Agent 原子工具——单个关键词 × 单个城市搜索+过滤+评分。

        管线：城市/公司/薪资硬校验 + 排除词 → 已投去重（省 LLM 调用）→ DeepSeek 精排。
        """
        if self._stop:
            return []
        jobs = await self._fetch(kw, city_code, city_name)
        if not jobs:
            return []

        cfg = get_config()
        exclude_kw = [k for k in cfg.search.get("exclude", []) if k]
        fake_cfg = cfg.fake_job_detection
        fake_patterns = fake_cfg.company_name_patterns if fake_cfg.enabled else []

        # 第一道过滤：城市/公司/薪资硬校验 + 排除词
        candidates: list[tuple[dict, str]] = []  # (job_dict, jd_text)
        for j in jobs:
            if self._stop:
                break
            co = j.get("brandName", "")
            po = j.get("jobName", "")
            if not co:
                continue
            ok1, w1 = check_city(j, city_name)
            if not ok1:
                self._stats["city_mismatch"] += 1
                _log.debug(f"[过滤] {co} {w1}")
                continue
            ok2, w2 = check_company(j, fake_patterns)
            if not ok2:
                self._stats["company_rejected"] += 1
                _log.debug(f"[过滤] {co} {w2}")
                continue
            ok3, _w3 = check_salary(j, min_sal)
            if not ok3:
                self._stats["salary_skipped"] += 1
                continue
            if exclude_kw and any(k in po or k in j.get("cityName", "") for k in exclude_kw):
                self._stats["excluded"] += 1
                continue
            parts = [po, j.get("salaryDesc", ""), j.get("cityName", ""),
                     j.get("jobExperience", ""), j.get("jobDegree", "")]
            for k in ("jobLabels", "skills", "welfareList"):
                v = j.get(k, [])
                parts.extend(v) if isinstance(v, list) else None
            jd = " ".join(str(p) for p in parts if p)
            if len(jd) >= 10:
                candidates.append((j, jd))

        if not candidates:
            return []

        # 第二道过滤：已投/已招呼公司去重（在花 LLM 调用之前）
        deduped = []
        for j, jd in candidates:
            if record_manager.is_job_recent(j.get("brandName", ""), j.get("encryptJobId", "")):
                self._stats["dup_skipped"] += 1
            else:
                deduped.append((j, jd))
        candidates = deduped
        if not candidates:
            return []

        # LLM 精排（搜索页每词每城最多 30 条，候选天然有上限，无需额外粗筛——
        # 原 TF-IDF 向量粗筛在 min_score=0/top_k=30 配置下为纯空转，2026-11-14 删除）
        scored = []
        for j, jd in candidates:
            if self._stop:
                break
            co = j.get("brandName", "")
            po = j.get("jobName", "")
            await sse_manager.emit_status(AppStatus.RUNNING, {"message": f"评估:{co}"})
            try:
                m = await asyncio.wait_for(ds_match(self._resume, jd[:3000]), timeout=15.0)
            except asyncio.TimeoutError:
                _log.warning(f"[评分] 超时跳过: {co} · {po}")
                continue
            if (m.get("reason") or "").startswith("匹配评分失败"):
                self._stats["llm_failed"] += 1
                self._llm_fail_streak += 1
                self._llm_fail_reason = m["reason"]  # 带具体原因（401/402/网络）
                if self._llm_fail_streak >= 5:
                    await sse_manager.emit_error(
                        f"{self._llm_fail_reason}——已连续 5 次，本轮中止")
                    return scored
                continue
            self._llm_fail_streak = 0
            score = m["score"]
            if score < 40:
                continue
            if m.get("is_fake_job"):
                # JD 内容的虚假判断由 LLM 单轨承担（公司名黑名单 regex 已在评分前拦截）
                self._stats["fake"] += 1
                _log.info(f"虚假招聘跳过(LLM): {co} · {po}")
                continue
            if m["confidence"] == "low":
                self._stats["low_conf"] += 1
                record_manager.add_pending(co, po, score, m["reason"], "低置信度")
                continue
            si = j.get("securityId", "")
            encId = j.get("encryptJobId", "")
            scored.append(ScoredJob(score=score, company=co, position=po, jd=jd, keyword=kw,
                city=city_name, match=m, security_id=si, encrypt_job_id=encId,
                salary=j.get("salaryDesc") or j.get("salary") or j.get("jobSalary") or ""))
        return scored

    async def _detail_reevaluate(self, all_scored: list) -> list:
        """top 30 详情重评。返回 enriched 列表。"""
        if not all_scored or self._stop:
            return all_scored

        topN = all_scored[:30]
        enriched = []
        re_evaluated = 0
        _log.info("获取 top 30 详情 JD 重新评分...")
        for idx, x in enumerate(topN):
            if self._stop:
                break
            await sse_manager.emit_status(AppStatus.RUNNING,
                {"message": f"重新评分: {idx+1}/30 {x.company}"})
            real_jd, real_salary = await self._fetch_jd_detail(x.security_id) if x.security_id else ("", "")
            if real_jd and len(real_jd) > 100:
                try:
                    new_m = await asyncio.wait_for(ds_match(self._resume, real_jd[:3000]), timeout=15.0)
                    new_score = new_m["score"]
                    re_evaluated += 1
                    _log.debug(f"[Detail] {idx+1}/30 {x.company}/{x.position} 标签{x.score}→真实{new_score} JD:{len(real_jd)}字")
                    enriched.append(ScoredJob(score=new_score, company=x.company, position=x.position, jd=real_jd, keyword=x.keyword, city=x.city, match=new_m, security_id=x.security_id, encrypt_job_id=x.encrypt_job_id, salary=x.salary or real_salary))
                except Exception as e:
                    _log.warning(f"[Detail] {x.company} 重评失败，保留标签分: {e}")
                    enriched.append(x)
            else:
                enriched.append(x)
            await self._sleep(0.5)
        enriched.extend(all_scored[30:])
        enriched.sort(key=lambda x: x.score, reverse=True)
        _log.info(f"详情重评完成: {re_evaluated}/{len(topN)} 条用完整JD重评，其余保留标签分")
        return enriched

    async def _apply_tiers(self, enriched: list, cfg) -> int:
        """分层输出：详情JD优先、标签JD补位；去重 + 30 条硬上限。

        低于 min_apply_score 的岗位只进待审区（review_only，不生成招呼语、
        不占发送额度）；返回生成了招呼语的记录数。
        """
        MAX_OUTPUT = 30  # 单次运行硬上限
        min_apply = cfg.matching.min_apply_score
        applied = 0
        ordered = ([x for x in enriched if len(x.jd) > 200]
                   + [x for x in enriched if len(x.jd) <= 200])
        for x in ordered:
            if self._stop or applied >= MAX_OUTPUT:
                break
            if record_manager.is_job_recent(x.company, x.encrypt_job_id):
                continue
            tier = self._assign_tier(x.score, cfg)
            if x.score < min_apply:
                rec = record_manager.add_record(company=x.company, position=x.position, score=x.score,
                    reason=x.match["reason"], tier=tier, status="review_only",
                    security_id=x.security_id, encrypt_job_id=x.encrypt_job_id, greeting="",
                    salary=x.salary, search_city=x.city, search_kw=x.keyword)
                await sse_manager.emit_record(rec)
                continue
            greet, greet_default = await self._generate_greeting(x.jd)
            _log.info(f"干跑: {tier}/{x.company}/{x.position}({x.score}分)"
                      f"{' [默认招呼语]' if greet_default else ''} 来源:{x.city}/{x.keyword}")
            self._tc[tier] = self._tc.get(tier, 0) + 1
            applied += 1
            rec = record_manager.add_record(company=x.company, position=x.position, score=x.score,
                reason=x.match["reason"], tier=tier, status="dry_run",
                security_id=x.security_id, encrypt_job_id=x.encrypt_job_id, greeting=greet,
                salary=x.salary, search_city=x.city, search_kw=x.keyword,
                greeting_is_default=greet_default)
            await sse_manager.emit_record(rec)
            await self._sleep(0.75)

        return applied

    def _assign_tier(self, score: int, cfg=None) -> str:
        """按分数分层：high / medium；低于投递线返回 'try'。

        'try' 是内部值（兼容历史记录与 API 字段），UI 展示为「低于投递线」——
        0-39（完全不对口）与 40-59（低于投递线）在展示层不再区分。
        """
        if cfg is None:
            cfg = get_config()
        tiers = cfg.matching.tiers
        if score >= tiers["high"].min_score:
            return "high"
        if score >= tiers["medium"].min_score:
            return "medium"
        return "try"

    async def _generate_greeting(self, jd: str) -> tuple[str, bool]:
        """返回 (招呼语, 是否降级为默认文案)。"""
        try:
            text = await asyncio.wait_for(
                gen_greeting(jd[:1500], getattr(self, '_profiles', '')), timeout=18.0)
            return text, False
        except Exception as e:
            _log.warning(f"招呼语生成失败，使用默认文案: {e}")
            return "您好，我对这个职位很感兴趣，希望能进一步了解。", True

    async def _emit_results(self, applied: int):
        await sse_manager.emit_complete({
            "total_applied": applied,
            "tier_counts": self._tier_stats(),
            "jobs": [{"title": r.get("position", "?"), "position": r.get("position", "?"),
                      "company": r.get("company", "?"),
                      "score": r.get("score", 0), "tier": r.get("tier", "?"),
                      "reason": r.get("reason", ""), "status": r.get("status", ""),
                      "securityId": r.get("security_id", ""),
                      "encryptJobId": r.get("encrypt_job_id", ""),
                      "search_city": r.get("search_city", ""),
                      "search_kw": r.get("search_kw", ""),
                      "salary": r.get("salary", ""),
                      "greeting": r.get("greeting", ""),
                      "greeting_is_default": bool(r.get("greeting_is_default", False))} for r in record_manager.get_all_records()]
        })

    async def _agent_decide(self, all_scored: list, remainder: list,
                            cities: list, loop: int, remain_count: int) -> dict:
        """Agent 决策核心——把候选池状态（分数分布/城市分布/剩余关键词）拼文本发给
        DeepSeek，让它决定：搜什么词、搜哪个城、还是停了进分层。失败回退硬规则。"""
        if len(all_scored) >= 300 or loop >= 12:
            return {"action": "stop", "reason": f"安全上限:{len(all_scored)}候选/{loop}轮"}
        if not remainder:
            return {"action": "stop", "reason": "无剩余关键词"}

        high80 = sum(1 for x in all_scored if x.score >= 80)
        high70 = sum(1 for x in all_scored if x.score >= 70)
        city_counts = {}
        for x in all_scored:
            cn = x.city; city_counts[cn] = city_counts.get(cn, 0) + 1
        city_str = ", ".join(f"{k}:{v}" for k, v in city_counts.items())

        city_enum = "|".join(c["name"] for c in cities) if cities else ""
        prompt = (
            f"你是求职Agent调度器。搜索状态：{len(all_scored)}候选(≥80:{high80},≥70:{high70})。"
            f"城市:{city_str}。待搜:{remainder[:6]}。选一个词搜一个城，或stop。"
            f"注意均衡各城市的搜索覆盖，不要总搜同一个城市。"
            f"JSON:{{\"action\":\"search\"|\"stop\",\"keyword\":\"...\",\"city\":\"{city_enum}\",\"reason\":\"...\"}}"
        )

        try:
            from .config_loader import get_api_key, get_llm_base_url
            from .llm import get_client
            url = f"{get_llm_base_url('deepseek')}/chat/completions"
            headers = {"Authorization": f"Bearer {get_api_key('deepseek')}", "Content-Type": "application/json"}
            body = {"model": "deepseek-chat", "messages": [
                {"role": "system", "content": "你是Agent决策器。只输出JSON。"},
                {"role": "user", "content": prompt}],
                "temperature": 0.2, "max_tokens": 150}
            r = await get_client().post(url, json=body, headers=headers, timeout=8)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"] or ""
            m = re.search(r'\{[\s\S]*\}', content)
            if not m:
                raise ValueError(f"决策返回非JSON: {content[:120]}")
            result = json.loads(m.group(0))
            self._decide_fallbacks = 0
            _log.info(f"[Agent] DeepSeek: {result.get('action','?')} {result.get('keyword','')}/{result.get('city','')} — {result.get('reason','')[:60]}")
            act = result.get("action", "search")
            decision = {"action": act, "keyword": result.get("keyword",""),
                    "city": result.get("city",""), "reason": result.get("reason","")}
            # 持久化决策日志
            try:
                dl = _log_dir / "agent_decisions.jsonl"
                # 超 1MB 归档为 .old（保留一代）——append-only 文件没有轮转会永续增长
                if dl.exists() and dl.stat().st_size > 1_000_000:
                    dl.replace(dl.with_suffix(".jsonl.old"))
                with open(dl, "a", encoding="utf-8") as f:
                    decision["pool_size"] = len(all_scored)
                    decision["high80"] = high80; decision["high70"] = high70
                    f.write(json.dumps(decision, ensure_ascii=False) + "\n")
            except Exception: _log.exception("决策日志写入失败")
            return decision
        except Exception as e:
            self._decide_fallbacks += 1
            if self._decide_fallbacks >= 3:
                _log.warning(f"[Agent] AI决策连续失败 {self._decide_fallbacks} 次，停止搜索: {e}")
                return {"action": "stop", "keyword": "", "city": "", "reason": "AI决策连续失败"}
            _log.info(f"[Agent] AI决策回退({self._decide_fallbacks}次): {e} 自动搜{remainder[0]}")
            return {"action": "search", "keyword": remainder[0],
                    "city": cities[0]["name"] if cities else "", "reason": "回退"}

    async def send_greetings(self, jobs: list[dict]):
        """逐条发送招呼语。jobs 格式来自前端: [{encryptJobId, securityId, greeting, company}, ...]

        安全栅栏：每日发送上限、发送间隔（send_delay）、连续失败熔断、stop 立即生效。
        每条发送后把记录状态更新为 sent / send_failed。
        """
        if not self._tab:
            await sse_manager.emit_error("浏览器未就绪")
            return {"ok": False, "error": "浏览器未就绪"}

        cfg = get_config()

        # ---- 发送前安全检查 ----
        sent_today = record_manager.get_sent_count_today()
        cap = cfg.safety.daily_send_cap
        if sent_today >= cap:
            msg = f"今日已发送 {sent_today} 条，达到上限 {cap}（可在 config.yaml safety.daily_send_cap 调整）"
            _log.warning(msg)
            await sse_manager.emit_error(msg)
            return {"ok": False, "error": msg}
        remaining_today = cap - sent_today
        if len(jobs) > remaining_today:
            _log.warning(f"选中 {len(jobs)} 条超出今日剩余额度 {remaining_today} 条，只发送前 {remaining_today} 条")
            jobs = jobs[:remaining_today]

        win = (cfg.safety.active_hours or "").strip()
        if win:
            ok_win, msg = self._check_active_hours(win)
            if not ok_win:
                _log.warning(msg)
                await sse_manager.emit_error(msg)
                return {"ok": False, "error": msg}

        greet_btns = _GREET_BTNS
        results = []; total = len(jobs)
        fail_streak = 0
        _log.info(f"[Send] 收到 {len(jobs)} 条（今日已发 {sent_today}/{cap}）: "
                  f"{[(j.get('company','?'), j.get('greeting','')[:20]) for j in jobs]}")

        self._sending = True
        try:
            for idx, job in enumerate(jobs):
                if self._stop:
                    _log.info(f"[Send] 收到停止请求，中断发送（已处理 {idx}/{total}）")
                    break
                encId = job.get("encryptJobId","")
                greeting = job.get("greeting","")
                company = job.get("company","?")
                if not encId or not greeting:
                    results.append({"company":company,"ok":False,"reason":"缺少岗位ID或招呼语"})
                    continue
                if not re.fullmatch(r"[0-9A-Za-z_\-]+", encId):
                    results.append({"company":company,"ok":False,"reason":"岗位ID格式异常"})
                    continue

                try:
                    await sse_manager.emit_status(AppStatus.RUNNING,
                        {"message":f"发送: {idx+1}/{total} {company}"})
                    ok, detail = await self._send_one(encId, greeting, company, idx, total, greet_btns)
                    results.append({"company":company,"ok":ok,"detail":detail})
                    if detail == "已沟通过":
                        # 对方已在沟通中：记录保持原状（公司保持拉黑）
                        continue
                    record_manager.mark_sent(company, encId, "sent" if ok else "send_failed")
                    fail_streak = 0 if ok else fail_streak + 1
                except Exception as e:
                    results.append({"company":company,"ok":False,"reason":str(e)})
                    record_manager.mark_sent(company, encId, "send_failed")
                    fail_streak += 1

                if fail_streak >= 3:
                    msg = f"连续 {fail_streak} 条发送失败，中止——请检查浏览器（可能遇到验证码/风控）"
                    _log.error(msg)
                    await sse_manager.emit_error(msg)
                    break

                if idx < total - 1:
                    await self._send_sleep()
        finally:
            self._sending = False

        ok_count = sum(1 for r in results if r.get("ok"))
        await sse_manager.emit_complete({
            "total_sent":ok_count,"total_failed":total-ok_count,"results":results})
        return {"ok": ok_count > 0, "total":total,"sent":ok_count,"results":results}

    async def _send_one(self, enc_id: str, greeting: str, company: str,
                        idx: int, total: int, greet_btns: list) -> tuple[bool, str]:
        """发送单条招呼语。返回 (是否成功, 说明)。"""
        url = f"https://www.zhipin.com/job_detail/{enc_id}.html"
        _log.info(f"[Send] {idx+1}/{total} 导航到 {url}")
        await self._tab.get(url); await self._tab.sleep(5)
        cur_url = self._tab.target.url or ""
        if any(k in cur_url.lower() for k in ("verify", "captcha")) or "安全验证" in cur_url:
            raise RuntimeError(f"疑似安全验证页面: {cur_url[:80]}")

        # 已沟通过则跳过
        already = await self._tab.evaluate("""
            (function(){
                var all=document.querySelectorAll('a,button,span,div');
                for(var i=0;i<all.length;i++){
                    if((all[i].textContent||'').includes('继续沟通')) return true
                }
                return false
            })()
        """)
        if already:
            return False, "已沟通过"

        # 点沟通按钮（六种文本变体）
        btns_json = json.dumps(greet_btns, ensure_ascii=False)
        clicked = await self._tab.evaluate(f"""
            (function(){{
                var targets={btns_json};
                var all=document.querySelectorAll('a,button,span,div');
                for(var i=0;i<all.length;i++){{
                    var t=(all[i].textContent||'').trim();
                    if(targets.indexOf(t)>=0){{all[i].click();return true}}
                }}
                return false
            }})()
        """)
        _log.info(f"[Send] {idx+1}/{total} 按钮={clicked}")
        if not clicked:
            return False, "未找到沟通按钮"

        # 取 api_url + redirect-url（聊天页）
        api_url = await self._tab.evaluate("""
            (function(){
                var el=document.querySelector('.btn-startchat[data-url]');
                var r={};
                if(el){r.api=el.getAttribute('data-url')||'';r.chat=el.getAttribute('redirect-url')||''}
                if(!r.api){
                    var all=document.querySelectorAll('.btn');
                    for(var i=0;i<all.length;i++){
                        if(all[i].getAttribute('data-url')&&(all[i].getAttribute('data-url')||'').indexOf('friend')>=0){
                            r.api=all[i].getAttribute('data-url');
                            r.chat=all[i].getAttribute('redirect-url')||'';
                            break;
                        }
                    }
                }
                return JSON.stringify(r);
            })()
        """)
        _log.info(f"[Send] {idx+1}/{total} URLs: {str(api_url)[:200]}")

        urls = json.loads(api_url) if api_url else {}
        add_url = urls.get("api","") or urls.get("api_url","")
        chat_path = urls.get("chat","") or urls.get("redirect-url","")

        # add_url 来自页面 DOM，先白名单校验再用 JSON 编码传入 JS，避免注入
        if not add_url or "/wapi/zpgeek/friend/" not in add_url:
            _log.warning(f"[Send] {idx+1}/{total} data-url 异常: {add_url[:80]}")
            return False, "沟通接口地址异常"

        add_url_json = json.dumps(add_url)
        xhr_result = await asyncio.wait_for(self._tab.evaluate(f"""
            (function(){{
                var x=new XMLHttpRequest();
                x.open('POST',{add_url_json},false);
                x.setRequestHeader('Content-Type','application/json');
                try{{x.send(JSON.stringify({{}}))}}catch(e){{return'xhr_err:'+e.message}}
                return'xhr_ok:'+x.status;
            }})()
        """), timeout=15.0)
        _log.info(f"[Send] {idx+1}/{total} friend/add: {xhr_result}")
        if not str(xhr_result).startswith("xhr_ok:2"):
            return False, f"建立沟通失败: {xhr_result}"

        if not chat_path:
            _log.warning(f"[Send] {idx+1}/{total} 无聊天页URL，自定义招呼语未发出")
            return False, "无聊天页URL，自定义招呼语未发出"

        chat_full = f"https://www.zhipin.com{chat_path}" if chat_path.startswith('/') else chat_path
        _log.info(f"[Send] {idx+1}/{total} 聊天页: {chat_full[:120]}")
        await self._tab.get(chat_full); await self._tab.sleep(5)

        # 聚焦真实输入框：.chat-input（contenteditable）。
        # 注意不能用裸 'textarea' 选择器——页面上存在一个 0x0 隐藏的脚手架 TEXTAREA（class=input），
        # 裸选择器会优先命中它：字打进隐藏元素、回读通过、Enter 无效 = 假发送（2026-11-14 P0）
        focused = await self._tab.evaluate("""
            (function(){
                var inp=document.querySelector('.chat-input');
                if(!inp){
                    // 回退：聊天区域内可见的输入元素（宽>100 高>20，排除隐藏脚手架）
                    var all=document.querySelectorAll('[contenteditable="true"],[role="textbox"],textarea');
                    for(var i=0;i<all.length;i++){
                        var r=all[i].getBoundingClientRect();
                        if(r.width>100&&r.height>20){inp=all[i];break}
                    }
                }
                if(inp){inp.focus();return (inp.className||'').toString().slice(0,40)}
                return 'NOT_FOUND';
            })()
        """)
        _log.info(f"[Send] {idx+1}/{total} 输入框: {focused}")
        if focused == 'NOT_FOUND':
            return False, "聊天输入框未找到（页面可能未渲染）"
        await self._tab.sleep(0.5)

        # CDP 插入定制文案
        from nodriver.cdp import input_ as cdp_input
        await self._tab.send(cdp_input.insert_text(text=greeting))
        await self._tab.sleep(1.0)

        # 回读确认文案真的进了输入框（contenteditable 用 innerText）
        typed = await self._tab.evaluate("""
            (function(){
                var el=document.activeElement;
                if(!el)return '';
                return (el.value||el.innerText||'').slice(0,80);
            })()
        """)
        if greeting[:10] not in (typed or ""):
            return False, f"输入框回读不一致，未发送（读到: {(typed or '')[:20]}）"

        # 点击「发送」按钮提交——不用合成 Enter：
        # macOS 对后台窗口的键盘事件有节流，Enter 会静默丢失（DEVLOG 2026-07 踩坑实录）；
        # JS click() 是 DOM 级调用，不受窗口前后台影响
        st = 'WAIT'
        for _ in range(10):
            st = await self._tab.evaluate("""
                (function(){
                    var b=document.querySelector('button.btn-send,.btn-send');
                    if(!b)return 'NO_BTN';
                    if((b.className||'').indexOf('disabled')>=0)return 'WAIT';
                    b.click();return 'CLICKED';
                })()
            """)
            if st != 'WAIT':
                break
            await self._tab.sleep(0.5)
        if st == 'NO_BTN':
            return False, "发送按钮未找到"
        if st != 'CLICKED':
            return False, "发送按钮未解禁（文案可能未进入输入框）"
        await self._tab.sleep(3)

        # 投递后验证：会话消息列表里应出现该文案——杜绝任何形式的假发送
        prefix_json = json.dumps(greeting[:15], ensure_ascii=False)
        sent_ok = await self._tab.evaluate(f"""
            (function(){{
                var prefix={prefix_json};
                var msgs=document.querySelectorAll('[class*="message"],[class*="item-clear"],[class*="bubble"]');
                for(var i=msgs.length-1;i>=0;i--){{
                    var t=(msgs[i].textContent||'');
                    if(t.indexOf(prefix)>=0)return true;
                }}
                return false;
            }})()
        """)
        if not sent_ok:
            return False, "消息未出现在会话中（发送疑似失败）"
        _log.info(f"[Send] {idx+1}/{total} 定制文案已送达并验证")
        return True, "ok"

    async def close_browser(self):
        if self._browser:
            try: self._browser.stop()
            except Exception: _log.debug("browser.stop() failed on close")
            self._browser = None; self._tab = None
        sse_manager.set_status(AppStatus.IDLE)

    async def _fetch(self, kw, city_code, city_name, pages=1):
        """搜索页内部XHR调API——Sec-Fetch-Mode:cors，不是地址栏导航。

        请求异常（非200/解析失败）会累计 self._search_fail_streak，供上层熔断。
        """
        from urllib.parse import quote
        await sse_manager.emit_status(AppStatus.RUNNING, {"message":f"搜索:{city_name}/{kw}"})
        all_jobs = []; seen_ids = set()
        for page in range(1, pages + 1):
            if self._stop: break
            # 导航到正常搜索结果页，不是 API URL
            search_url = f"https://www.zhipin.com/web/geek/job?query={quote(kw)}&city={city_code}"
            api_path = (f"/wapi/zpgeek/search/joblist.json"
                        f"?query={quote(kw)}&city={city_code}&page={page}&pageSize=30")
            api_path_json = json.dumps(api_path)
            try:
                await self._tab.get(search_url); await self._tab.sleep(6)
                # 在页面内部用同步 XHR 调 API，请求头跟真人浏览一模一样
                raw = await asyncio.wait_for(self._tab.evaluate(f"""
                    (function(){{
                        var x = new XMLHttpRequest();
                        x.open('GET',{api_path_json},false);
                        try{{x.send()}}catch(e){{return JSON.stringify({{err:'network'}})}}
                        if(x.status!=200)return JSON.stringify({{err:'http',status:x.status,body:x.responseText.slice(0,120)}})
                        try{{return JSON.stringify({{jobs:JSON.parse(x.responseText).zpData.jobList}})}}
                        catch(e){{return JSON.stringify({{err:'parse',status:x.status,body:x.responseText.slice(0,120)}})}}
                    }})()
                """), timeout=25.0)
                if not raw or not isinstance(raw, str): continue
                try: payload = json.loads(raw)
                except Exception:
                    self._search_fail_streak += 1
                    _log.warning(f"[API] {city_name}/{kw} 第{page}页返回无法解析")
                    break
                if "err" in payload:
                    self._search_fail_streak += 1
                    _log.warning(f"[API] {city_name}/{kw} 第{page}页异常({payload.get('err')}/{payload.get('status')}): "
                                 f"{str(payload.get('body',''))[:100]}")
                    break
                self._search_fail_streak = 0
                jl = payload.get("jobs") or []
                if not jl: break
                new = 0
                for j in jl:
                    jid = j.get("encryptJobId") or j.get("jobId") or j.get("securityId")
                    if jid and jid not in seen_ids:
                        seen_ids.add(jid); all_jobs.append(j); new += 1
                _log.debug(f"[API] {city_name}/{kw} 第{page}页 {new}个（累计{len(all_jobs)}）")
                if len(jl) < 30: break
            except asyncio.TimeoutError:
                self._search_fail_streak += 1
                _log.warning(f"[API] {city_name}/{kw} 第{page}页超时")
                break
            except Exception as e:
                self._search_fail_streak += 1
                _log.warning(f"[API] {city_name}/{kw} 失败: {e}")
                break
            await self._sleep(0.35)
        return all_jobs

    async def _fetch_jd_detail(self, security_id):
        """页面内 XHR 拉取 JD 详情。返回 (详情JD, 薪资文本)。"""
        try:
            url_json = json.dumps(f"/wapi/zpgeek/job/card.json?securityId={security_id}")
            raw = await asyncio.wait_for(self._tab.evaluate(f"""
                (function(){{
                    var x=new XMLHttpRequest();
                    x.open('GET',{url_json},false);
                    try{{x.send()}}catch(e){{return ''}}
                    if(x.status!=200)return ''
                    try{{var c=JSON.parse(x.responseText).zpData.jobCard||{{}};
                        return JSON.stringify({{jd:c.postDescription||'', salary:c.salaryDesc||c.salary||''}})}}
                    catch(e){{return ''}}
                }})()
            """), timeout=15.0)
            if not raw or not isinstance(raw, str): return "", ""
            d = json.loads(raw)
            jd = d.get("jd", "")
            if jd and len(str(jd)) > 100: return str(jd), str(d.get("salary", "") or "")
        except Exception as e:
            _log.debug(f"获取JD详情失败 securityId={str(security_id)[:20]}: {e}")
        return "", ""

    def _tier_stats(self):
        return {t: self._tc.get(t, 0) for t in ("high", "medium", "try")}
    def _read_resume(self):
        path = get_project_root()/get_config().resume.get("pdf_path","my_resume.pdf")
        if not path.exists():
            raise FileNotFoundError(f"简历文件不存在: {path}（请在前端上传，或修改 config.yaml resume.pdf_path）")
        # pdfminer.six（纯 Python，~5MB）替代 PyMuPDF（79MB+）：简历只读一次，速度无所谓
        from pdfminer.high_level import extract_text
        text = extract_text(str(path))
        if len(text.strip()) < 50:
            raise ValueError(f"简历解析出的文本过短({len(text.strip())}字)，请检查 PDF: {path}")
        return text

agent_runner = AgentRunner()
