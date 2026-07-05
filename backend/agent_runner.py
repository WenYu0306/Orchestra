"""
Agent — 单阶段: 搜→标签评分→全局排序→top 30 详情重评→最终分层。
"""
import asyncio, json, os, random, traceback
import fitz, nodriver as uc
from .config_loader import get_config, get_project_root
from .greeting_generator import generate as gen_greeting
from .matcher import match as ds_match
from .record_manager import record_manager
from .sse_manager import sse_manager, AppStatus
from .validator import check_city, check_salary, check_company


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
            cfg = get_config()
            cities = cfg.search.get("cities",[])
            keywords = list(cfg.search.get("primary_keywords",[]))
            try:
                from .search_generator import generate as sg_gen
                for d in await sg_gen(s._resume):
                    for kw in d.get("keywords",[]):
                        if kw not in keywords: keywords.append(kw)
            except: pass

            await sse_manager.emit_status(AppStatus.RUNNING, {"message":"启动浏览器..."})
            s._browser = await uc.start(headless=False,
                browser_executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                user_data_dir="/tmp/jh-nodriver",
                browser_args=["--disable-blink-features=AutomationControlled","--no-first-run"])
            s._tab = s._browser.main_tab
            await s._tab.get("https://www.zhipin.com/web/geek/job"); await s._tab.sleep(8)

            cur = s._tab.target.url or ""
            # 必须确认当前页面既不包含 login 也不包含 user 才算已登录
            if "/user/" in cur or "login" in cur.lower() or "passport" in cur.lower():
                await sse_manager.emit_status(AppStatus.RUNNING, {"message":"请扫码登录"})
                for _ in range(180):
                    if s._stop: return; await asyncio.sleep(2)
                    cur = s._tab.target.url or ""
                    # 确认跳到职位列表页才算登录成功
                    if "/geek/job" in cur and "login" not in cur.lower() and "/user/" not in cur:
                        await s._tab.sleep(3)  # 再等 3 秒让页面完全加载
                        break
                else: await sse_manager.emit_error("登录超时"); return

            # 扫码后多等一会让 cookie 完全生效
            await s._tab.sleep(5)

            # 动态获取城市编码
            BOSS_CODE = await s._fetch_city_codes(cities)

            # === 标签评分 ===
            all_scored = []
            city_warnings = set()
            salary_skipped = 0
            for city in cities:
                cc = BOSS_CODE.get(city["name"], "101010100")
                min_sal = city.get("min_salary", 0)
                for kw in keywords:
                    if s._stop: break
                    jobs = await s._fetch(kw, cc, city["name"])
                    if not jobs: continue
                    for j in jobs:
                        if s._stop: break
                        co = j.get("brandName","") or j.get("brandName","")
                        po = j.get("jobName","")
                        if not co: continue
                        # ---- 校验层 ----
                        ok, warn = check_city(j, city["name"])
                        if warn: city_warnings.add(warn)
                        ok, warn = check_company(j)
                        if warn: city_warnings.add(warn)
                        ok, warn = check_salary(j, min_sal)
                        if not ok: salary_skipped += 1; continue
                        # ----
                        parts = [po, j.get("salaryDesc",""), j.get("cityName",""),
                                 j.get("jobExperience",""), j.get("jobDegree",""),
                                 j.get("brandIndustry",""), j.get("brandScaleName","")]
                        for k in ("jobLabels","skills","welfareList"):
                            v = j.get(k,[]); parts.extend(v) if isinstance(v,list) else None
                        jd = " ".join(str(p) for p in parts if p)
                        if len(jd) < 10: continue
                        await sse_manager.emit_status(AppStatus.RUNNING, {"message":f"评估:{co}"})
                        try:
                            m = await asyncio.wait_for(ds_match(s._resume, jd[:3000]), timeout=8.0)
                        except asyncio.TimeoutError: continue
                        score = m["score"]
                        if score < 40: continue
                        if m["confidence"] == "low":
                            record_manager.add_pending(co, po, score, m["reason"], "低置信度")
                            continue
                        si = j.get("securityId","")
                        eid = j.get("encryptJobId","")
                        all_scored.append((score, co, po, jd, kw, city["name"], m, si, eid))
                        # 每 15 个岗位保活一次，防 Chrome 闲置超时
                        if len(all_scored) % 15 == 0:
                            try: await s._tab.get("https://www.zhipin.com/web/geek/job"); await s._tab.sleep(2)
                            except: pass
                    await asyncio.sleep(random.uniform(2,3))
                if s._stop: break

            all_scored.sort(key=lambda x: x[0], reverse=True)
            for w in city_warnings:
                print(f"⚠️  {w}", flush=True)
            if salary_skipped:
                print(f"💰 薪资过滤: {salary_skipped} 个岗位", flush=True)
            print(f"[Agent] 标签评分完成，共 {len(all_scored)} 个候选", flush=True)

            # === 详情重评 top 30（比最终多 10 个缓冲） ===
            if all_scored and not s._stop:
                topN = all_scored[:30]
                enriched = []
                print(f"[Agent] 获取 top 30 详情 JD 重新评分...", flush=True)
                for idx, (score, co, po, jd, kw, city_name, m, si, eid) in enumerate(topN):
                    if s._stop: break
                    real_jd = await s._fetch_jd_detail(si) if si else ""
                    if real_jd and len(real_jd) > 100:
                        try:
                            new_m = await asyncio.wait_for(ds_match(s._resume, real_jd[:3000]), timeout=8.0)
                            new_score = new_m["score"]
                            print(f"[Detail] {idx+1}/30 {co}/{po} 标签{score}→真实{new_score} JD:{len(real_jd)}字", flush=True)
                            enriched.append((new_score, co, po, real_jd, kw, city_name, new_m, eid))
                        except Exception:
                            enriched.append((score, co, po, jd, kw, city_name, m, eid))
                    else:
                        enriched.append((score, co, po, jd, kw, city_name, m, eid))
                    await asyncio.sleep(random.uniform(3,4))
                enriched.extend([(sc, c, p, j, k, cn, mm, e) for sc, c, p, j, k, cn, mm, _, e in all_scored[30:]])
                enriched.sort(key=lambda x: x[0], reverse=True)
                print(f"[Agent] 详情重评完成，共 {len(enriched)} 个候选", flush=True)
            else:
                enriched = all_scored

            # === 最终分层：优先取详情重评过的（JD>200字），不足再用标签评分的 ===
            high_quota = cfg.matching.tiers["high"].count
            med_quota  = cfg.matching.tiers["medium"].count
            try_quota  = cfg.matching.tiers["try"].count
            max_total  = high_quota + med_quota + try_quota
            applied = 0

            # 第一遍取 JD>200 字的（详情重评过的）
            apply_limit = int(os.environ.get("APPLY_LIMIT", "0"))
            apply_count = 0
            detail_rich = [x for x in enriched if len(x[3]) > 200]
            for score, co, po, jd, kw, city_name, m, eid in detail_rich:
                if s._stop or applied >= high_quota + med_quota + try_quota: break
                if co in s._ac or record_manager.is_company_recent(co): continue
                if applied < high_quota:          tier = "high"
                elif applied < high_quota + med_quota: tier = "medium"
                else:                              tier = "try"
                s._ac.add(co)
                try:
                    greet = await asyncio.wait_for(gen_greeting(jd[:1500], s._resume), timeout=5.0)
                except Exception:
                    greet = "您好，我对这个职位很感兴趣，希望能进一步了解。"
                send_status = "dry_run"
                if apply_limit > 0 and apply_count < apply_limit and eid:
                    if apply_count == 0:
                        print(f"⏳ 10秒后将发送招呼语到 {co}，按 Ctrl+C 取消...", flush=True)
                        await asyncio.sleep(10)
                    send_ok = await s._try_send_greeting(eid, greet)
                    if send_ok:
                        send_status = "success"
                        apply_count += 1
                        print(f"[Agent] 真发: {tier}/{co}/{po}({score}分) ✅", flush=True)
                    else:
                        print(f"[Agent] 真发失败: {co}, 回退干跑", flush=True)
                else:
                    print(f"[Agent] 干跑: {tier}/{co}/{po}({score}分) 来源:{city_name}/{kw} JD:{len(jd)}字", flush=True)
                s._tc[tier] = s._tc.get(tier,0) + 1
                applied += 1
                rec = record_manager.add_record(company=co, position=po, score=score,
                    reason=m["reason"], tier=tier, status=send_status)
                await sse_manager.emit_record(rec)
                await asyncio.sleep(random.uniform(5,8))

            # 第二遍：JD 不够的不够补足名额
            if applied < max_total:
                label_scored = [x for x in enriched if len(x[3]) <= 200]
                for score, co, po, jd, kw, city_name, m, eid in label_scored:
                    if s._stop or applied >= max_total: break
                    if co in s._ac or record_manager.is_company_recent(co): continue
                    if applied < high_quota:          tier = "high"
                    elif applied < high_quota + med_quota: tier = "medium"
                    else:                              tier = "try"
                    s._ac.add(co)
                    try:
                        greet = await asyncio.wait_for(gen_greeting(jd[:1500], s._resume), timeout=5.0)
                    except Exception:
                        greet = "您好，我对这个职位很感兴趣，希望能进一步了解。"
                    print(f"[Agent] 干跑: {tier}/{co}/{po}({score}分) 来源:{city_name}/{kw} JD:{len(jd)}字", flush=True)
                    s._tc[tier] = s._tc.get(tier,0) + 1
                    applied += 1
                    rec = record_manager.add_record(company=co, position=po, score=score,
                        reason=m["reason"], tier=tier, status="dry_run")
                    await sse_manager.emit_record(rec)
                    await asyncio.sleep(random.uniform(3,5))

            await sse_manager.emit_complete({
                "total_applied": applied,
                "tier_counts": s._tier_stats(),
                "jobs": [{"title":r.get("position","?"),"company":r.get("company","?"),
                    "score":r.get("score",0),"tier":r.get("tier","?"),
                    "reason":r.get("reason",""),"status":r.get("status",""),
                    "search_city":"","search_kw":"","greeting":""} for r in record_manager.get_all_records()]
            })
        except Exception as e:
            traceback.print_exc(); await sse_manager.emit_error(str(e))
        finally:
            if s._browser:
                try: s._browser.stop()
                except: pass

    async def _fetch_city_codes(s, cities: list) -> dict:
        """从 BOSS 城市 API 动态获取城市编码，fallback 到已知编码"""
        try:
            await s._tab.get("https://www.zhipin.com/wapi/zpCommon/data/city.json")
            await s._tab.sleep(3)
            raw = await s._tab.evaluate("document.body.innerText")
            data = json.loads(raw)
            result = {}
            for prov in data.get("zpData", {}).get("cityList", []):
                for city in prov.get("subLevelModelList", []):
                    name = city.get("name", "")
                    for c in cities:
                        if c["name"] in name:
                            result[c["name"]] = city["code"]
            # 验证所有期望城市都找到了
            for c in cities:
                target = c["name"]
                if target not in result:
                    print(f"⚠️  城市 '{target}' 未在 BOSS API 中找到编码，使用已知值", flush=True)
            return result if result else {"北京": "101010100", "长春": "101060100"}
        except Exception:
            print("⚠️  城市编码获取失败，使用已知编码", flush=True)
            return {"北京": "101010100", "长春": "101060100"}

    async def _fetch(s, kw, city_code, city_name, pages=1):
        from urllib.parse import quote
        await sse_manager.emit_status(AppStatus.RUNNING, {"message":f"搜索:{city_name}/{kw}"})
        all_jobs = []; seen_ids = set()
        for page in range(1, pages + 1):
            if s._stop: break
            api_url = (f"https://www.zhipin.com/wapi/zpgeek/search/joblist.json"
                       f"?query={quote(kw)}&city={city_code}&page={page}&pageSize=30")
            try:
                await s._tab.get(api_url); await s._tab.sleep(4)
                raw = await s._tab.evaluate("document.body.innerText")
                if not raw or not isinstance(raw, str): continue
                data = json.loads(raw)
                jl = data.get("zpData", {}).get("jobList", [])
                if not jl: break
                new = 0
                for j in jl:
                    jid = j.get("encryptJobId") or j.get("jobId") or j.get("securityId")
                    if jid and jid not in seen_ids:
                        seen_ids.add(jid); all_jobs.append(j); new += 1
                print(f"[API] {city_name}/{kw} 第{page}页 {new}个（累计{len(all_jobs)}）", flush=True)
                if len(jl) < 30: break
            except Exception as e:
                print(f"[API] {city_name}/{kw} 失败: {e}", flush=True); break
            await asyncio.sleep(random.uniform(1,2))
        return all_jobs

    async def _try_send_greeting(s, encrypt_id: str, greeting: str) -> bool:
        """导航到职位详情页, 尝试点击"立即沟通"并发送招呼语。成功返回 True。"""
        try:
            url = f"https://www.zhipin.com/job_detail/{encrypt_id}.html"
            await s._tab.get(url)
            await s._tab.sleep(4)
            # 找"立即沟通"按钮 (BOSS 常用选择器)
            clicked = await s._tab.evaluate("""
                (() => {
                    const btn = document.querySelector('.btn-chat, .chat-btn, [class*=\"chat\"], [class*=\"communication\"], .op-btn');
                    if (btn) { btn.click(); return true; }
                    // fallback: 找含"沟通"或"聊一聊"的按钮
                    const all = document.querySelectorAll('button, a, span, div');
                    for (const el of all) {
                        const t = el.textContent;
                        if ((t.includes('沟通') || t.includes('聊一聊') || t.includes('立即')) && t.length < 20) {
                            el.click(); return true;
                        }
                    }
                    return false;
                })()
            """)
            if not clicked:
                return False
            await s._tab.sleep(2)
            # 在聊天框 textarea 里输入招呼语并发送
            sent = await s._tab.evaluate(f"""
                (() => {{
                    const ta = document.querySelector('textarea, [contenteditable=\"true\"], .chat-input input');
                    if (!ta) return false;
                    if (ta.tagName === 'TEXTAREA' || ta.tagName === 'INPUT') {{
                        ta.value = {json.dumps(greeting)};
                        ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                    }} else {{
                        ta.textContent = {json.dumps(greeting)};
                        ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                    }}
                    // 按 Enter 发送
                    ta.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', bubbles: true}}));
                    return true;
                }})()
            """)
            return bool(sent)
        except Exception:
            return False

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
