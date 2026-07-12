"""
Agent — 单阶段: 搜→标签评分→全局排序→top 20 详情重评→最终分层。
稳定优先，每次API调用间隔3-8秒。
"""
import asyncio, json, logging, os, random, re, sys, traceback
from logging.handlers import TimedRotatingFileHandler
import fitz, nodriver as uc
from .config_loader import get_config, get_api_key, get_llm_base_url, get_project_root
from .greeting_generator import generate as gen_greeting
from .matcher import match as ds_match
from .record_manager import record_manager
from .sse_manager import sse_manager, AppStatus
from .validator import check_city, check_salary, check_company

# ---- logging setup ----
_log = logging.getLogger("agent")
_log.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")

# console handler
_ch = logging.StreamHandler(sys.stdout); _ch.setFormatter(_fmt); _log.addHandler(_ch)

# file handler — daily rotating, keep 7 days
_log_dir = get_project_root() / "data" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_fh = TimedRotatingFileHandler(str(_log_dir / "agent.log"), when="midnight", backupCount=7)
_fh.setFormatter(_fmt); _log.addHandler(_fh)


class AgentRunner:
    def __init__(s):
        s._task = None; s._stop = False; s._browser = None; s._tab = None
        s._pe = asyncio.Event(); s._pe.set()
        s._resume = ""
        s._tc = {"high":0,"medium":0,"try":0}; s._ac = set()

    @property
    def is_running(s): return s._task is not None and not s._task.done()
    @property
    def is_paused(s): return not s._pe.is_set()

    async def start(s):
        if s.is_running: raise RuntimeError("运行中")
        if s._browser:
            try: s._browser.stop()
            except: pass
            s._browser = None; s._tab = None
        s._stop = False; s._pe.set(); s._tc = {"high":0,"medium":0,"try":0}; s._ac = set()
        record_manager.reset_session()
        s._task = asyncio.create_task(s._run())

    async def stop(s):
        s._stop = True; s._pe.set()
        try: await sse_manager.emit_status(AppStatus.IDLE, {"message":"已停止"})
        except: pass

    async def resume_after_captcha(s):
        s._pe.set()
        try: await sse_manager.emit_status(AppStatus.RUNNING, {"message":"继续"})
        except: pass

    async def _run(s):
        try:
            s._resume = s._read_resume()
            cfg = get_config()

            if not await s._launch_and_login():
                return

            keywords = await s._prepare_keywords(cfg)
            _log.info(f"搜索关键词: {len(keywords)} 个 — {', '.join(keywords[:8])}")

            # === Agent 批量搜索循环 ===
            MIN_CANDIDATES = 200
            BATCH_SIZE = 3
            all_scored = []
            city_warnings = set()
            salary_skipped = 0
            loop = 0

            for i in range(0, len(keywords), BATCH_SIZE):
                if s._stop:
                    break
                batch = keywords[i:i + BATCH_SIZE]
                loop += 1
                _log.info(f"[Agent] 第{loop}批搜索: {batch}")

                scored, warns, skipped = await s._search_and_score(cfg, batch)
                all_scored.extend(scored)
                city_warnings |= warns
                salary_skipped += skipped

                high70 = sum(1 for x in all_scored if x[0] >= 70)
                _log.info(f"[Agent] 进度: {len(all_scored)}候选, {high70}个≥70分")

                if len(all_scored) >= MIN_CANDIDATES:
                    _log.info(f"[Agent] 候选池达{len(all_scored)}，停止搜索")
                    break
                if loop >= 10:
                    _log.info(f"[Agent] 已达最大轮次，停止搜索")
                    break

            for w in city_warnings:
                _log.warning(w)
            if salary_skipped:
                _log.info(f"薪资过滤: {salary_skipped} 个岗位")
            all_scored.sort(key=lambda x: x[0], reverse=True)
            _log.info(f"标签评分完成，共 {len(all_scored)} 个候选")

            enriched = await s._detail_reevaluate(all_scored)

            applied = await s._apply_tiers(enriched, cfg)

            await s._emit_results(applied)

        except Exception as e:
            traceback.print_exc(); await sse_manager.emit_error(str(e))
        finally:
            if s._stop and s._browser:
                try: s._browser.stop()
                except: pass

    # ====== 步骤方法 ======

    async def _prepare_keywords(s, cfg) -> list:
        """合并配置预设 + DeepSeek 动态生成的关键词"""
        keywords = list(cfg.search.get("primary_keywords", []))
        try:
            from .search_generator import generate as sg_gen
            for d in await sg_gen(s._resume):
                for kw in d.get("keywords", []):
                    if kw not in keywords:
                        keywords.append(kw)
        except Exception:
            pass
        return keywords

    async def _launch_and_login(s) -> bool:
        """启动 Chrome + 扫码登录 + Cookie 验证。返回 True 表示成功。"""
        await sse_manager.emit_status(AppStatus.RUNNING, {"message": "启动浏览器..."})
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.name == "nt":
            chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        elif os.name == "posix" and not __import__('pathlib').Path(chrome_path).exists():
            chrome_path = "google-chrome"
        s._browser = await uc.start(headless=False,
            browser_executable_path=chrome_path,
            user_data_dir=str(__import__('pathlib').Path(
                __import__('tempfile').gettempdir()) / "jh-run-1"),
            no_sandbox=True,
            browser_args=["--disable-blink-features=AutomationControlled", "--no-first-run"])
        s._tab = s._browser.main_tab
        await s._tab.get("https://www.zhipin.com/web/geek/job")
        await s._tab.sleep(8)

        cur = s._tab.target.url or ""
        if "/user/" in cur or "login" in cur.lower() or "passport" in cur.lower() or "/geek/job" not in cur:
            await sse_manager.emit_status(AppStatus.RUNNING, {"message": "请扫码登录"})
            for _ in range(180):
                if s._stop:
                    return False
                await asyncio.sleep(2)
                cur = s._tab.target.url or ""
                if "/geek/job" in cur and "login" not in cur.lower() and "/user/" not in cur and "passport" not in cur.lower():
                    await s._tab.sleep(3)
                    break
            else:
                await sse_manager.emit_error("登录超时")
                return False

        await s._tab.sleep(5)

        # cookie 验证
        verify_ok = False
        for _ in range(3):
            try:
                await s._tab.get("https://www.zhipin.com/wapi/zpgeek/search/joblist.json?query=AI%E5%BA%94%E7%94%A8%E5%BC%80%E5%8F%91&city=101010100&page=1&pageSize=1")
                await s._tab.sleep(2)
                raw = await s._tab.evaluate("document.body.innerText")
                if raw and isinstance(raw, str) and '"code":0' in raw and '"jobList"' in raw:
                    verify_ok = True
                    break
            except Exception:
                await asyncio.sleep(1)
        if not verify_ok:
            await sse_manager.emit_error("登录验证失败，cookie未生效，请重启重试")
            return False

        _log.info("Cookie 验证通过")
        return True

    async def _search_and_score(s, cfg, keywords: list) -> tuple:
        """城市×关键词搜索 + 标签评分 + 过滤。
        返回 (all_scored, city_warnings, salary_skipped)。"""
        BOSS_CODE = {"北京": "101010100", "长春": "101060100"}
        cities = cfg.search.get("cities", [])
        all_scored = []
        city_warnings = set()
        salary_skipped = 0

        for city in cities:
            cc = BOSS_CODE.get(city["name"], "101010100")
            min_sal = city.get("min_salary", 0)
            for kw in keywords:
                if s._stop:
                    break
                jobs = await s._fetch(kw, cc, city["name"])
                if not jobs:
                    continue
                for j in jobs:
                    if s._stop:
                        break
                    co = j.get("brandName", "") or j.get("brandName", "")
                    po = j.get("jobName", "")
                    if not co:
                        continue
                    ok, warn = check_city(j, city["name"])
                    if warn: city_warnings.add(warn)
                    ok, warn = check_company(j)
                    if warn: city_warnings.add(warn)
                    ok, warn = check_salary(j, min_sal)
                    if not ok:
                        salary_skipped += 1
                        continue
                    parts = [po, j.get("salaryDesc", ""), j.get("cityName", ""),
                             j.get("jobExperience", ""), j.get("jobDegree", "")]
                    for k in ("jobLabels", "skills", "welfareList"):
                        v = j.get(k, [])
                        parts.extend(v) if isinstance(v, list) else None
                    jd = " ".join(str(p) for p in parts if p)
                    if len(jd) < 10:
                        continue
                    await sse_manager.emit_status(AppStatus.RUNNING, {"message": f"评估:{co}"})
                    try:
                        m = await asyncio.wait_for(ds_match(s._resume, jd[:3000]), timeout=15.0)
                    except asyncio.TimeoutError:
                        continue
                    score = m["score"]
                    if score < 40:
                        continue
                    if m.get("is_fake_job"):
                        city_warnings.add(f"🚨 虚假招聘跳过: {co} · {po}")
                        continue
                    if m["confidence"] == "low":
                        record_manager.add_pending(co, po, score, m["reason"], "低置信度")
                        continue
                    si = j.get("securityId", "")
                    encId = j.get("encryptJobId", "")
                    all_scored.append((score, co, po, jd, kw, city["name"], m, si, encId))
                    if len(all_scored) % 15 == 0:
                        try:
                            await s._tab.get("https://www.zhipin.com/web/geek/job")
                            await s._tab.sleep(2)
                        except Exception:
                            pass
                await asyncio.sleep(random.uniform(2, 3))
            if s._stop:
                break

        all_scored.sort(key=lambda x: x[0], reverse=True)
        return all_scored, city_warnings, salary_skipped

    async def _detail_reevaluate(s, all_scored: list) -> list:
        """top 30 详情重评。返回 enriched 列表。"""
        if not all_scored or s._stop:
            return all_scored

        topN = all_scored[:30]
        enriched = []
        _log.info("获取 top 30 详情 JD 重新评分...")
        for idx, (score, co, po, jd, kw, city_name, m, si, encId) in enumerate(topN):
            if s._stop:
                break
            real_jd = await s._fetch_jd_detail(si) if si else ""
            if real_jd and len(real_jd) > 100:
                try:
                    new_m = await asyncio.wait_for(ds_match(s._resume, real_jd[:3000]), timeout=15.0)
                    new_score = new_m["score"]
                    _log.debug(f"[Detail] {idx+1}/30 {co}/{po} 标签{score}→真实{new_score} JD:{len(real_jd)}字")
                    enriched.append((new_score, co, po, real_jd, kw, city_name, new_m, si, encId))
                except Exception:
                    enriched.append((score, co, po, jd, kw, city_name, m, si, encId))
            else:
                enriched.append((score, co, po, jd, kw, city_name, m, si, encId))
            await asyncio.sleep(random.uniform(3, 4))
        enriched.extend([(sc, c, p, j, k, cn, mm, s, e) for sc, c, p, j, k, cn, mm, s, e in all_scored[30:]])
        enriched.sort(key=lambda x: x[0], reverse=True)
        _log.info(f"详情重评完成，共 {len(enriched)} 个候选")
        return enriched

    async def _apply_tiers(s, enriched: list, cfg) -> int:
        """最终分层：优先 JD>200 字的，不足补标签评分。生成招呼语 + 推送。返回 applied 数量。"""
        high_quota = cfg.matching.tiers["high"].count
        med_quota = cfg.matching.tiers["medium"].count
        try_quota = cfg.matching.tiers["try"].count
        max_total = high_quota + med_quota + try_quota
        applied = 0

        detail_rich = [x for x in enriched if len(x[3]) > 200]
        for score, co, po, jd, kw, city_name, m, si, encId in detail_rich:
            if s._stop or applied >= max_total:
                break
            if co in s._ac or record_manager.is_company_recent(co):
                continue
            tier = s._assign_tier(applied, high_quota, med_quota)
            s._ac.add(co)
            greet = await s._generate_greeting(jd)
            _log.info(f"干跑: {tier}/{co}/{po}({score}分) 来源:{city_name}/{kw} JD:{len(jd)}字")
            s._tc[tier] = s._tc.get(tier, 0) + 1
            applied += 1
            rec = record_manager.add_record(company=co, position=po, score=score,
                reason=m["reason"], tier=tier, status="dry_run",
                security_id=si, encrypt_job_id=encId, greeting=greet)
            await sse_manager.emit_record(rec)
            await asyncio.sleep(random.uniform(5, 8))

        if applied < max_total:
            label_scored = [x for x in enriched if len(x[3]) <= 200]
            for score, co, po, jd, kw, city_name, m, si, encId in label_scored:
                if s._stop or applied >= max_total:
                    break
                if co in s._ac or record_manager.is_company_recent(co):
                    continue
                tier = s._assign_tier(applied, high_quota, med_quota)
                s._ac.add(co)
                greet = await s._generate_greeting(jd)
                _log.info(f"干跑: {tier}/{co}/{po}({score}分) 来源:{city_name}/{kw} JD:{len(jd)}字")
                s._tc[tier] = s._tc.get(tier, 0) + 1
                applied += 1
                rec = record_manager.add_record(company=co, position=po, score=score,
                    reason=m["reason"], tier=tier, status="dry_run",
                    security_id=si, encrypt_job_id=encId, greeting=greet)
                await sse_manager.emit_record(rec)
                await asyncio.sleep(random.uniform(3, 5))

        return applied

    def _assign_tier(s, applied: int, high_quota: int, med_quota: int) -> str:
        if applied < high_quota:
            return "high"
        if applied < high_quota + med_quota:
            return "medium"
        return "try"

    async def _generate_greeting(s, jd: str) -> str:
        try:
            return await asyncio.wait_for(gen_greeting(jd[:1500], s._resume), timeout=5.0)
        except Exception:
            return "您好，我对这个职位很感兴趣，希望能进一步了解。"

    async def _emit_results(s, applied: int):
        await sse_manager.emit_complete({
            "total_applied": applied,
            "tier_counts": s._tier_stats(),
            "jobs": [{"title": r.get("position", "?"), "company": r.get("company", "?"),
                      "score": r.get("score", 0), "tier": r.get("tier", "?"),
                      "reason": r.get("reason", ""), "status": r.get("status", ""),
                      "securityId": r.get("security_id", ""),
                      "encryptJobId": r.get("encrypt_job_id", ""),
                      "search_city": "", "search_kw": "",
                      "greeting": r.get("greeting", "")} for r in record_manager.get_all_records()]
        })

    async def send_greetings(s, jobs: list[dict]):
        """逐条发送招呼语。jobs 格式来自前端: [{encryptJobId, securityId, greeting, company}, ...]

        流程：先回到搜索列表页 → 历遍卡片定位目标 → 点沟通按钮 → 弹窗填招呼语 → 发送。
        """
        if not s._tab:
            await sse_manager.emit_error("浏览器未就绪")
            return {"ok": False, "error": "浏览器未就绪"}

        _log.info(f"[Send] 收到 {len(jobs)} 条: {[(j.get('company','?'),j.get('encryptJobId','')[:20],j.get('greeting','')[:30]) for j in jobs]}")
        greet_btns = ["立即沟通","发起沟通","沟通一下","聊一聊","联系Ta","开始沟通"]
        results = []; total = len(jobs)

        for idx, job in enumerate(jobs):
            encId = job.get("encryptJobId","") or job.get("securityId","")
            greeting = job.get("greeting","")
            company = job.get("company","?")
            if not encId or not greeting:
                results.append({"company":company,"ok":False,"reason":"缺少ID或招呼语"})
                continue

            try:
                await sse_manager.emit_status(AppStatus.RUNNING,
                    {"message":f"发送: {idx+1}/{total} {company}"})

                # 打开职位详情页（encryptJobId）
                url = f"https://www.zhipin.com/job_detail/{encId}.html"
                _log.info(f"[Send] {idx+1}/{total} 导航到 {url}")
                await s._tab.get(url); await s._tab.sleep(5)
                cur_url = s._tab.target.url or ""
                _log.info(f"[Send] {idx+1}/{total} 当前URL: {cur_url[:80]}")

                # 已沟通过则跳过
                already = await s._tab.evaluate("""
                    (function(){
                        var all=document.querySelectorAll('a,button,span,div');
                        for(var i=0;i<all.length;i++){
                            if((all[i].textContent||'').includes('继续沟通')) return true
                        }
                        return false
                    })()
                """)
                if already:
                    results.append({"company":company,"ok":False,"reason":"已沟通过"})
                    continue

                # 点沟通按钮（六种文本变体）
                btns_json = json.dumps(greet_btns, ensure_ascii=False)
                clicked = await s._tab.evaluate(f"""
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
                    results.append({"company":company,"ok":False,"reason":"未找到沟通按钮"})
                    continue

                # 取 api_url + redirect-url（聊天页）
                api_url = await s._tab.evaluate("""
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

                if add_url:
                    # XHR 调 friend/add.json 建立沟通关系
                    xhr_result = await s._tab.evaluate(f"""
                        (function(){{
                            var x=new XMLHttpRequest();
                            x.open('POST','{add_url}',false);
                            x.setRequestHeader('Content-Type','application/json');
                            try{{x.send(JSON.stringify({{}}))}}catch(e){{return'xhr_err:'+e.message}}
                            return'xhr_ok:'+x.status;
                        }})()
                    """)
                    _log.info(f"[Send] {idx+1}/{total} friend/add: {xhr_result}")
                    send_ok = xhr_result or 'friend_add_done'
                else:
                    send_ok = "no_api_url"
                    _log.warning(f"[Send] {idx+1}/{total} 无data-url")

                # 如果有聊天页 URL，跳过去发自定义招呼语
                if chat_path:
                    chat_full = f"https://www.zhipin.com{chat_path}" if chat_path.startswith('/') else chat_path
                    _log.info(f"[Send] {idx+1}/{total} 聊天页: {chat_full[:120]}")
                    await s._tab.get(chat_full); await s._tab.sleep(5)

                    # CDP Input.insertText + dispatchKeyEvent（内核键盘，React 认）
                    try:
                        # 先聚焦输入框
                        await s._tab.evaluate("""
                            (function(){
                                var inp=document.querySelector('textarea,[contenteditable="true"]');
                                if(inp)inp.focus();
                            })()
                        """)
                        await s._tab.sleep(0.5)

                        # CDP 文本输入 + 回车键（内核级，React 认）
                        from nodriver.cdp import input_ as cdp_input
                        await s._tab.send(cdp_input.insert_text(text=greeting))
                        await s._tab.sleep(0.3)
                        await s._tab.send(cdp_input.dispatch_key_event(
                            type_="keyDown", key="Enter", code="Enter",
                            windows_virtual_key_code=13))
                        await s._tab.sleep(0.1)
                        await s._tab.send(cdp_input.dispatch_key_event(
                            type_="keyUp", key="Enter", code="Enter",
                            windows_virtual_key_code=13))
                        _log.info(f"[Send] {idx+1}/{total} CDP完成")
                    except Exception as cdp_err:
                        _log.warning(f"[Send] {idx+1}/{total} CDP失败: {cdp_err}")
                else:
                    _log.info(f"[Send] {idx+1}/{total} 无聊天URL, 只用系统默认")
                results.append({"company":company,"ok":True,"detail":send_ok})
                await sse_manager.emit_status(AppStatus.RUNNING,
                    {"message":f"已发送: {idx+1}/{total} {company}"})

            except Exception as e:
                results.append({"company":company,"ok":False,"reason":str(e)})

            await asyncio.sleep(random.uniform(10,20))

        ok = sum(1 for r in results if r.get("ok"))
        await sse_manager.emit_complete({
            "total_sent":ok,"total_failed":total-ok,"results":results})
        return {"ok":True,"total":total,"sent":ok,"results":results}

    async def close_browser(s):
        if s._browser:
            try: s._browser.stop()
            except: pass
            s._browser = None; s._tab = None
        sse_manager.set_status(AppStatus.IDLE)

    async def _fetch(s, kw, city_code, city_name, pages=1):
        """搜索页内部XHR调API——Sec-Fetch-Mode:cors，不是地址栏导航。"""
        from urllib.parse import quote
        await sse_manager.emit_status(AppStatus.RUNNING, {"message":f"搜索:{city_name}/{kw}"})
        all_jobs = []; seen_ids = set()
        for page in range(1, pages + 1):
            if s._stop: break
            # 导航到正常搜索结果页，不是 API URL
            search_url = f"https://www.zhipin.com/web/geek/job?query={quote(kw)}&city={city_code}"
            api_url = (f"https://www.zhipin.com/wapi/zpgeek/search/joblist.json"
                       f"?query={quote(kw)}&city={city_code}&page={page}&pageSize=30")
            try:
                await s._tab.get(search_url); await s._tab.sleep(6)
                # 在页面内部用同步 XHR 调 API，请求头跟真人浏览一模一样
                raw = await s._tab.evaluate(f"""
                    (function(){{
                        var x = new XMLHttpRequest();
                        x.open('GET','{api_url}',false);
                        try{{x.send()}}catch(e){{return'[]'}}
                        if(x.status!=200)return'[]';
                        try{{return JSON.stringify(JSON.parse(x.responseText).zpData.jobList)}}
                        catch(e){{return'[]'}}
                    }})()
                """)
                if not raw or not isinstance(raw, str): continue
                try: jl = json.loads(raw)
                except Exception: continue
                if not jl: break
                new = 0
                for j in jl:
                    jid = j.get("encryptJobId") or j.get("jobId") or j.get("securityId")
                    if jid and jid not in seen_ids:
                        seen_ids.add(jid); all_jobs.append(j); new += 1
                _log.debug(f"[API] {city_name}/{kw} 第{page}页 {new}个（累计{len(all_jobs)}）")
                if len(jl) < 30: break
            except Exception as e:
                _log.debug(f"[API] {city_name}/{kw} 失败: {e}"); break
            await asyncio.sleep(random.uniform(1,2))
        return all_jobs

    async def _fetch_jd_detail(s, security_id):
        try:
            url = f"https://www.zhipin.com/wapi/zpgeek/job/card.json?securityId={security_id}"
            await s._tab.get(url); await s._tab.sleep(3)
            raw = await s._tab.evaluate("document.body.innerText")
            data = json.loads(raw)
            jd = data.get("zpData", {}).get("jobCard", {}).get("postDescription", "")
            if jd and len(str(jd)) > 100: return str(jd)
        except Exception: pass
        return ""

    def _tier_max(s):
        cfg = get_config()
        return {"high":cfg.matching.tiers["high"].count,"medium":cfg.matching.tiers["medium"].count,"try":cfg.matching.tiers["try"].count}
    def _tier_stats(s):
        mx = s._tier_max()
        return {t:{"current":s._tc.get(t,0),"max":mx[t]} for t in ("high","medium","try")}
    def _read_resume(s):
        path = get_project_root()/get_config().resume.get("pdf_path","my_resume.pdf")
        if not path.exists(): return "[简历未找到]"
        doc = fitz.open(str(path)); t="\n".join(p.get_text() for p in doc); doc.close(); return t

agent_runner = AgentRunner()
