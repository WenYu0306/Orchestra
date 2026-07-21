"""
智联招聘适配器 —— DOM 定位 + CDP 输入。

路线：搜索框 CDP 输入关键词 → Enter → "立即投递"做锚点定位父容器提取卡片内容。
已验证：城市代码 jl530=北京，详情页 CC....htm，按钮/文本结构稳定。
"""

import json, logging, asyncio, re
from urllib.parse import quote

from ..platform_adapter import PlatformAdapter, JobCard, register_platform

_log = logging.getLogger("agent")


@register_platform
class ZhilianAdapter(PlatformAdapter):
    name = "zhilian"
    login_url = "https://www.zhaopin.com/"
    search_page_url = "https://www.zhaopin.com/beijing/"

    CITY_CODES = {
        "北京": "530", "上海": "538", "深圳": "489", "广州": "763",
        "杭州": "653", "成都": "801", "长春": "574",
    }

    @property
    def city_codes(self) -> dict[str, str]:
        return self.CITY_CODES

    def __init__(self):
        self._tab = None
        self._browser = None

    def bind_tab(self, tab):
        self._tab = tab

    def bind_browser(self, browser):
        self._browser = browser

    # ==== 搜索 ====

    def _load_url_map(self) -> dict[str, str]:
        """加载预采集的搜索 URL 映射（关键词 → 完整 URL）"""
        from pathlib import Path as _Path
        map_path = _Path(__file__).resolve().parent.parent.parent / "data" / "zhilian_urls.json"
        try:
            if map_path.exists():
                import json as _json
                return _json.loads(map_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_url_map(self, url_map: dict) -> None:
        """保存搜索 URL 映射到文件"""
        from pathlib import Path as _Path
        map_path = _Path(__file__).resolve().parent.parent.parent / "data" / "zhilian_urls.json"
        map_path.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        map_path.write_text(_json.dumps(url_map, ensure_ascii=False, indent=2), encoding="utf-8")

    async def search(self, keyword: str, city_name: str, city_code: str,
                     page: int = 1, page_size: int = 30) -> list[JobCard]:
        """
        CDP 输入 → Enter → 新标签页打开 → 提取卡片。

        浏览器自己编码关键词，根本不需破解算法。
        采集过的 URL 存到 zhilian_urls.json 加速复用。
        """
        url_map = self._load_url_map()

        # 已有缓存的直接走快速通道
        if keyword in url_map:
            import re
            search_url = re.sub(r'/p\d+', f'/p{page}', url_map[keyword])
            _log.info(f"[智联] 复用缓存: {keyword}")
            await self._tab.get(search_url)
            await self._tab.sleep(10)
            return await self._extract_cards()

        # 首次搜索：CDP 输入 + 拦截新标签页
        from nodriver.cdp import input_ as cdp_input

        # 1) 城市首页
        city_pages = {"530": "https://www.zhaopin.com/beijing/"}
        city_url = city_pages.get(city_code, "https://www.zhaopin.com/beijing/")
        await self._tab.get(city_url)
        await self._tab.sleep(6)

        # 2) 聚焦 + 输入
        await self._tab.evaluate("""var i=document.querySelector('.zp-search__input');if(i)i.focus()""")
        await self._tab.sleep(0.3)
        await self._tab.send(cdp_input.insert_text(text=keyword))
        await self._tab.sleep(0.5)

        # 3) 记录当前浏览器 tab 数 + Enter
        tabs_before = len(self._browser.tabs) if self._browser else 1
        await self._tab.send(cdp_input.dispatch_key_event(
            type_="keyDown", key="Enter", code="Enter",
            text="\r", windows_virtual_key_code=13))
        await self._tab.sleep(0.08)
        await self._tab.send(cdp_input.dispatch_key_event(type_="char", text="\r"))
        await self._tab.sleep(0.08)
        await self._tab.send(cdp_input.dispatch_key_event(
            type_="keyUp", key="Enter", code="Enter",
            text="\r", windows_virtual_key_code=13))

        # 4) 等新标签页出现
        new_tab = None
        for t in range(12):
            await asyncio.sleep(1)
            if self._browser and len(self._browser.tabs) > tabs_before:
                new_tab = self._browser.tabs[-1]
                break

        if new_tab is None:
            _log.warning(f"[智联] 未检测到新标签页，回退 URL 编码")
            search_url = f"https://www.zhaopin.com/sou/jl{city_code}/kw{quote(keyword)}/p{page}?kt=3"
            await self._tab.get(search_url)
            await self._tab.sleep(10)
            return await self._extract_cards()

        # 5) 切换到新标签页
        search_url = new_tab.target.url or ""
        _log.info(f"[智联] 新标签页: {search_url[:100]}")

        if "/sou/" in search_url:
            # 保存到缓存
            url_map[keyword] = search_url
            self._save_url_map(url_map)
            _log.info(f"[智联] 已缓存 {keyword}")

        self._tab = new_tab
        await self._tab.sleep(6)
        return await self._extract_cards()

    async def _extract_cards(self) -> list[JobCard]:
        """从当前页用"立即投递"锚点提取所有岗位卡片。"""
        data = await self._tab.evaluate("""
            (function(){
                var JT = '立即投递';
                var cards = [];
                var all = document.querySelectorAll('span, button, a');
                all.forEach(function(el){
                    var t = (el.innerText||el.textContent||'').trim();
                    if (t !== JT) return;
                    var p = el.parentElement;
                    for (var i = 0; i < 4 && p; i++) {
                        var txt = (p.innerText||'').trim();
                        if (txt.length >= 60 && txt.length <= 800) {
                            if (cards.indexOf(txt) === -1) cards.push(txt);
                            break;
                        }
                        p = p.parentElement;
                    }
                });
                return JSON.stringify(cards);
            })()
        """)

        if not isinstance(data, str):
            return []

        cards = []
        for block in json.loads(data):
            card = self._parse_card_text(block)
            if card and card.company:
                cards.append(card)

        # 也找 jobdetail 链接（可以做查重验证）
        links = await self._tab.evaluate("""
            JSON.stringify(
                Array.from(document.querySelectorAll('a[href*="jobdetail"]'))
                    .slice(0, 30)
                    .map(a => ({href: a.href}))
            )
        """)
        if isinstance(links, str):
            detail_hrefs = [j.get("href", "") for j in json.loads(links)]
            for idx, card in enumerate(cards):
                if idx < len(detail_hrefs):
                    card.security_id = detail_hrefs[idx]
                    card.encrypt_job_id = detail_hrefs[idx]

        _log.info(f"[智联] 提取 {len(cards)} 个岗位")
        return cards

    def _parse_card_text(self, text: str) -> JobCard | None:
        """从已验证的文本格式解析单个卡片。结构（从下往上）：

            立即投递             ← 底部锚点
            立即沟通
            关胤·HR             ← HR行（必含·）
            国企 1000-9999人 银行  ← 公司属性（1-N行）
            北京建投科信...      ← ★ 公司名（紧挨HR行前面，不做属性行）
            硕士                ← 学历
            经验不限             ← 经验
            北京·丰台·看丹       ← 城市（含·）
            Python              ← 标签（1-N行）
            7000-10000元        ← 薪资
            it技术运维工程师     ← 职位名（首行）
        """
        JT = "立即投递"
        lines = [l.strip() for l in text.split('\n') if l.strip() and l.strip() not in (JT, "立即沟通", "收藏")]
        if len(lines) < 4:
            return None

        # 1) 找 HR 行（最后一行含·的就是HR行）
        hr_idx = None
        for i in range(len(lines) - 1, -1, -1):
            if '·' in lines[i]:
                hr_idx = i
                break

        if hr_idx is None:
            hr_idx = len(lines) - 1  # 兜底

        # 2) 公司名：HR行往前，跳过属性行
        company = ""
        attr_re = re.compile(
            r'(民营|国企|外资|上市|股份制|合资|外商|事业单位|政府|NGO|其它|'
            r'\d+[-~]\d+人|\d+人以上|\d+人以下|\d+人|[百千万亿]余人?|'
            r'\d+[-~]\d+年|经验不限|经验|应届|'
            r'优选雇主|最佳雇主|高回复率|昨日活跃|今日活跃|刚刚活跃|小时内回复|'
            r'不需要融资|已上市|天使轮|[ABCDE]轮|未融资|'
            r'软件/|IT服务|互联网|人工智能|计算机|教育科技|'
            r'投资与|咨询服务|课外培训|人力资源|'
            r'计算机硬件|专用设备|工业自动化|通信|银行|保险|证券)'
        )
        # 纯技术词（不含公司后缀的短行），注意必须整行匹配避免误杀
        tech_re = re.compile(
            r'^(大模型算法|大数据|自然语言处理|深度学习|机器学习|计算机视觉|'
            r'Python|Java|React|Golang|Node|RAG|LLM|NLP|CV|'
            r'C\+\+|TensorFlow|PyTorch|Docker|Kubernetes)$'
        )
        co_suffix = re.compile(r'(公司|有限|股份|集团|科技|网络|信息|数据|文化|传媒|咨询|'
                               r'工作室|事务所|中心|实验室)')
        for i in range(hr_idx - 1, -1, -1):
            l = lines[i]
            if '·' in l or '(' in l or '/' in l or '.' in l:
                continue
            if attr_re.search(l) or tech_re.match(l):
                continue
            # ≤3字且无公司后缀 → 属性/标签
            if len(l) <= 3 and not co_suffix.search(l):
                continue
            company = l
            break

        # 3) 薪资 + 职位名（首部往下找）
        salary_desc = ""
        position = ""
        sal_re = re.compile(r'^\d+\.?\d*[-~·]\d+\.?\d*[元Kk万]|^\d+[元Kk万]|面议')
        for i in range(len(lines)):
            l = lines[i]
            if sal_re.search(l):
                salary_desc = l
                if i > 0:
                    position = lines[i - 1]
                break

        # 4) 城市（含·区/县/市/镇/路）
        city = ""
        for l in lines:
            if '·' in l and any(c in l for c in '区县市镇路海'):
                city = l.split('·')[0].strip()
                break

        # 5) 经验/学历
        experience = ""
        degree = ""
        for l in lines:
            parts = l.split()
            for p in parts:
                if re.search(r'经验|年|应届', p) and not experience:
                    experience = p
                if re.search(r'硕士|本科|大专|博士|学历|不限', p) and '经验' not in p and not degree:
                    degree = p

        if not position or not company:
            return None
        # 公司名等于职位名 → 卡片没有真实公司名，丢弃
        if company == position:
            return None

        return JobCard(
            company=company,
            position=position,
            salary_desc=salary_desc,
            city=city,
            experience=experience,
            degree=degree,
            labels=[],
            skills=[],
            security_id="",
            encrypt_job_id="",
        )

    # ==== 详情 ====

    async def fetch_job_detail(self, security_id: str) -> str:
        """导航到 jobdetail 页面，取 body.innerText 中的 JD 段落。"""
        if not security_id:
            return ""

        if not security_id.startswith("http"):
            security_id = f"http://www.zhaopin.com/jobdetail/{security_id}"

        await self._tab.get(security_id)
        await self._tab.sleep(6)

        # 找 JD 容器
        jd = await self._tab.evaluate("""
            (function(){
                var sel = document.querySelector('[class*="describ"], [class*="desc"], [class*="detail"], [class*="job-detail"], [class*="content"]');
                if (sel) return sel.innerText;
                return document.body.innerText || '';
            })()
        """)
        return str(jd) if isinstance(jd, str) and len(jd) > 100 else ""

    # ==== 投递 ====

    async def send_greeting(self, card: JobCard, greeting: str) -> dict:
        """详情页点击"立即投递"，系统简历投递。"""
        detail_url = card.security_id or card.encrypt_job_id
        if not detail_url:
            return {"ok": False, "reason": "缺少详情 URL"}

        if not detail_url.startswith("http"):
            detail_url = f"http://www.zhaopin.com/jobdetail/{detail_url}"

        await self._tab.get(detail_url)
        await self._tab.sleep(5)

        clicked = await self._tab.evaluate("""
            (function(){
                var all = document.querySelectorAll('div, button, span, a');
                for (var i=0; i<all.length; i++) {
                    if ((all[i].innerText||all[i].textContent||'').trim() === '立即投递') {
                        all[i].click(); return true;
                    }
                }
                return false;
            })()
        """)

        if not clicked:
            return {"ok": False, "reason": "未找到投递按钮"}

        await self._tab.sleep(3)
        return {"ok": True}
