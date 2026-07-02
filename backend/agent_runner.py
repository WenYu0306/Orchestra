"""
Agent — 两阶段架构: Chrome 收集数据 → 脱机评分。
"""

import asyncio, json, os, random, re, traceback
import fitz, nodriver as uc
from .config_loader import get_config, get_api_key, get_llm_base_url, get_project_root
from .greeting_generator import generate as gen_greeting
from .matcher import match as ds_match
from .record_manager import record_manager
from .sse_manager import sse_manager, AppStatus


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
            await sse_manager.emit_status(AppStatus.RUNNING, {"message":"启动..."})

            cfg = get_config()
            BOSS_CODE = {"北京":"101010100","长春":"101190100"}
            cities = cfg.search.get("cities",[])
            keywords = list(cfg.search.get("primary_keywords",[]))
            try:
                from .search_generator import generate as sg_gen
                for d in await sg_gen(s._resume):
                    for kw in d.get("keywords",[]):
                        if kw not in keywords: keywords.append(kw)
            except: pass

            # === 阶段 1: 收集数据（Chrome 存活）===
            all_jobs = []
            s._browser = await uc.start(headless=False,
                browser_executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                user_data_dir="/tmp/jh-nodriver",
                browser_args=["--disable-blink-features=AutomationControlled","--no-first-run"])
            s._tab = s._browser.main_tab
            await s._tab.get("https://www.zhipin.com/web/geek/job"); await s._tab.sleep(5)

            cur = s._tab.target.url or ""
            if "/user/" in cur or "login" in cur.lower():
                await sse_manager.emit_status(AppStatus.RUNNING, {"message":"请扫码登录"})
                for _ in range(180):
                    if s._stop: return; await asyncio.sleep(2)
                    cur = s._tab.target.url or ""
                    if "/user/" not in cur and "login" not in cur.lower(): break
                else: await sse_manager.emit_error("登录超时"); return

            for city in cities:
                cc = BOSS_CODE.get(city["name"], "101010100")
                for kw in keywords:
                    if s._stop: break
                    jl = await s._fetch(kw, cc, city["name"])
                    if jl: all_jobs.append((kw, city["name"], jl))
                    await asyncio.sleep(random.uniform(2,5))
                if s._stop: break

            # Chrome 使命完成，杀掉
            try: s._browser.stop()
            except: pass
            s._browser = None; s._tab = None

            # === 阶段 2: 脱机评分 → 收集全部评分后全局排序选 top 20 ===
            all_scored = []  # [(score, tier, co, po, jd, kw, city), ...]

            for kw, city_name, jobs in all_jobs:
                if s._stop: break
                if not jobs: continue
                print(f"[Stage2] 评分: {city_name}/{kw} ({len(jobs)}职位)", flush=True)
                for idx, j in enumerate(jobs):
                    if s._stop: break
                    if (idx+1) % 10 == 0:
                        print(f"  [{city_name}/{kw}] 进度: {idx+1}/{len(jobs)}", flush=True)
                    co = j.get("brandName","") or j.get("brandName","")
                    po = j.get("jobName","")
                    if not co: continue
                    parts = [po, j.get("salaryDesc",""), j.get("cityName",""), j.get("jobExperience",""), j.get("jobDegree","")]
                    for k in ("jobLabels","skills","welfareList"):
                        v = j.get(k,[]); parts.extend(v) if isinstance(v,list) else None
                    jd = " ".join(str(p) for p in parts if p)
                    if len(jd) < 10: continue
                    await sse_manager.emit_status(AppStatus.RUNNING, {"message":f"评估:{co}"})
                    try:
                        m = await asyncio.wait_for(ds_match(s._resume, jd[:3000]), timeout=8.0)
                    except asyncio.TimeoutError:
                        print(f"[Agent] 评分超时跳过: {co}")
                        continue
                    score = m["score"]; tier = _decide_tier(s, m)
                    if tier not in ("skip","pending"):
                        all_scored.append((score, tier, co, po, jd, kw, city_name, m))
                    elif tier == "pending":
                        record_manager.add_pending(co, po, score, m["reason"], "低置信度")

            # 全局排序 → 取 top 20 分配三层
            all_scored.sort(key=lambda x: x[0], reverse=True)
            applied = 0
            for score, tier, co, po, jd, kw, city_name, m in all_scored:
                if s._stop or applied >= 20: break
                if co in s._ac or record_manager.is_company_recent(co):
                    continue
                s._ac.add(co)
                try:
                    greet = await asyncio.wait_for(gen_greeting(jd[:1500], s._resume), timeout=5.0)
                except Exception:
                    greet = "您好，我对这个职位很感兴趣，希望能进一步了解。"
                print(f"[Agent] 干跑: {tier}/{co}/{po}({score}分) 来源:{city_name}/{kw}", flush=True)
                s._tc[tier] = s._tc.get(tier,0) + 1
                applied += 1
                rec = record_manager.add_record(company=co, position=po, score=score, reason=m["reason"], tier=tier, status="dry_run")
                await sse_manager.emit_record(rec)

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

    async def _fetch(s, kw, city_code, city_name):
        from urllib.parse import quote
        await sse_manager.emit_status(AppStatus.RUNNING, {"message":f"搜索:{city_name}/{kw}"})
        search_url = f"https://www.zhipin.com/web/geek/job?query={quote(kw)}&city={city_code}"
        await s._tab.get(search_url); await s._tab.sleep(6)
        jobs = []
        try:
            api_url = f"https://www.zhipin.com/wapi/zpgeek/search/joblist.json?query={quote(kw)}&city={city_code}&page=1&pageSize=30"
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
            if raw and isinstance(raw,str) and raw.startswith("["):
                jl = json.loads(raw)
                if jl: print(f"[API] {len(jl)} 个职位"); jobs = jl
        except Exception as e: print(f"[API] 失败: {e}")
        return jobs

    async def _score(s, kw, city_name, jobs):
        import os
        msg = f"[Agent] {city_name}/{kw} → {len(jobs)} 个职位（脱机评分） PID:{os.getpid()}"
        print(msg, flush=True)
        scored = 0
        for j in jobs:
            if s._stop: return
            scored += 1
            if scored % 5 == 0:
                print(f"  [{city_name}/{kw}] 进度: {scored}/{len(jobs)}", flush=True)
            co = j.get("brandName","") or j.get("brandName","")
            po = j.get("jobName","")
            if not co or co in s._ac: continue
            parts = [po, j.get("salaryDesc",""), j.get("cityName",""), j.get("jobExperience",""), j.get("jobDegree","")]
            for k in ("jobLabels","skills","welfareList"):
                v = j.get(k,[]); parts.extend(v) if isinstance(v,list) else None
            jd = " ".join(str(p) for p in parts if p)
            if len(jd) < 10: continue
            s._ac.add(co)
            await sse_manager.emit_status(AppStatus.RUNNING, {"message":f"评估:{co}"})
            try:
                m = await asyncio.wait_for(ds_match(s._resume, jd[:3000]), timeout=8.0)
            except asyncio.TimeoutError:
                print(f"[Agent] 评分超时跳过: {co}")
                continue
            score = m["score"]; tier = _decide_tier(s, m)
            if tier == "skip": continue
            if tier == "pending":
                record_manager.add_pending(co, po, score, m["reason"], "低置信度")
                await sse_manager.emit_pending(record_manager.get_all_pending()); continue
            try:
                greet = await asyncio.wait_for(gen_greeting(jd[:1500], s._resume), timeout=5.0)
            except Exception:
                greet = "您好，我对这个职位很感兴趣，希望能进一步了解。"
            print(f"[Agent] 干跑: {tier}/{co}/{po}({score}分) JD:{len(jd)}字", flush=True)
            s._tc[tier] = s._tc.get(tier,0) + 1
            rec = record_manager.add_record(company=co, position=po, score=score, reason=m["reason"], tier=tier, status="dry_run")
            await sse_manager.emit_record(rec)
            # 分段休眠，随时可被中断
            for _ in range(16):
                if s._stop: return
                await asyncio.sleep(0.5)

    def _tier_max(s):
        cfg = get_config()
        return {"high":cfg.matching.tiers["high"].count,"medium":cfg.matching.tiers["medium"].count,"try":cfg.matching.tiers["try"].count}
    def _tier_stats(s):
        mx = s._tier_max()
        return {t:{"current":s._tc.get(t,0),"max":mx[t]} for t in ("high","medium","try")}
    def _all_done(s):
        mx = s._tier_max()
        return s._tc.get("high",0)>=mx["high"] and s._tc.get("medium",0)>=mx["medium"] and s._tc.get("try",0)>=mx["try"]
    def _read_resume(s):
        path = get_project_root()/get_config().resume.get("pdf_path","my_resume.pdf")
        if not path.exists(): return "[简历未找到]"
        doc = fitz.open(str(path)); t="\n".join(p.get_text() for p in doc); doc.close(); return t

def _decide_tier(s, m):
    score = m["score"]
    if m["confidence"] == "low": return "pending"
    if score >= 80: tier = "high"
    elif score >= 60: tier = "medium"
    elif score >= 40: tier = "try"
    else: return "skip"
    mx = s._tier_max()
    if tier == "medium" and score >= 77 and s._tc.get("high",0) < mx["high"]: tier = "high"
    if tier == "try" and score >= 57 and s._tc.get("medium",0) < mx["medium"]: tier = "medium"
    if s._tc.get(tier,0) >= mx[tier]:
        for alt in ("medium","try"):
            if tier == "high" and s._tc.get("medium",0) < mx["medium"]: return "medium"
            if tier in ("high","medium") and s._tc.get("try",0) < mx["try"]: return "try"
        return "skip"
    return tier

agent_runner = AgentRunner()
