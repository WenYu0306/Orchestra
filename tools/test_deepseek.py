"""直接测试 DeepSeek API 的连接稳定性"""
import time, os
from openai import OpenAI
import httpx
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    timeout=httpx.Timeout(10.0, connect=5.0),
    max_retries=0,
)

print("=== DeepSeek API 直连测试 ===")
print(f"Base URL: {os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')}")
print()

import time, os, random
from openai import OpenAI
import httpx
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    timeout=httpx.Timeout(10.0, connect=5.0),
    max_retries=0,
)

print("=== DeepSeek API 30次批量测试 (间隔8-12s) ===")
print()

for i in range(30):
    t0 = time.time()
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "回复数字1，只回复1，不要其他内容"}],
            max_tokens=5,
        )
        elapsed = time.time() - t0
        print(f"  请求 {i+1}: ✓ {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  请求 {i+1}: ✗ {type(e).__name__} ({elapsed:.1f}s): {str(e)[:120]}")
        break
    delay = random.uniform(8, 12)
    print(f"       等待 {delay:.1f}s...")
    time.sleep(delay)

print()
print("=== 测试完成 ===")

print()
print("=== 测试完成 ===")
