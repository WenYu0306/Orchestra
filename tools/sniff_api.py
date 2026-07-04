"""用 JS 拦截 BOSS 所有 API 请求。Chrome 弹出来自动搜，等 15 秒看输出。"""
import asyncio, json, nodriver as uc

INJECT = """
(function() {
    window.__boss_apis = [];
    const orig_fetch = window.fetch;
    window.fetch = function(...args) {
        if (typeof args[0] === 'string' && args[0].includes('zhipin.com')) {
            window.__boss_apis.push(args[0]);
            console.log('[SNIFF] ' + args[0]);
        }
        return orig_fetch.apply(this, args);
    };
    const orig_open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        if (url.includes('zhipin.com') && (url.includes('search') || url.includes('job') || url.includes('wapi'))) {
            window.__boss_apis.push(url);
            console.log('[SNIFF] ' + url);
        }
        return orig_open.apply(this, arguments);
    };
})();
"""

async def main():
    browser = await uc.start(headless=False,
        browser_executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        user_data_dir="/tmp/jh-nodriver",
        browser_args=["--disable-blink-features=AutomationControlled", "--no-first-run"])
    tab = browser.main_tab

    # 注入拦截脚本——在导航之前
    await tab.evaluate(INJECT)

    await tab.get("https://www.zhipin.com/web/geek/job?query=AI%E5%BA%94%E7%94%A8%E5%BC%80%E5%8F%91&city=101010100")
    await tab.sleep(10)

    apis = await tab.evaluate("JSON.stringify(window.__boss_apis)")
    if apis:
        urls = json.loads(apis)
        print(f"\n=== 找到 {len(urls)} 个 API ===")
        for u in urls:
            print(u)
    else:
        print("\n未找到 API（页面可能还没加载完）")

    await tab.sleep(3)
    browser.stop()

asyncio.run(main())
