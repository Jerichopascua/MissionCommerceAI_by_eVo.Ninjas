"""How fast can the GPU write a persona library? Fires many short generations in parallel.

Env: REQUESTS (default 64), CONCURRENCY (default 32), VLLM_BASE_URL, VLLM_MODEL.
Reports aggregate completion tokens/s, which is the number that decides how long
generating ~40 (starter) or ~150 (full) archetypes will take.
"""
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000")
MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
REQUESTS = int(os.environ.get("REQUESTS", "64"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "32"))

AGES = ["student", "young office worker", "night-shift nurse", "parent of two", "retired senior",
        "motorcycle commuter", "market vendor", "call-center agent"]


def one(i):
    who = AGES[i % len(AGES)]
    body = json.dumps({
        "model": MODEL, "max_tokens": 150, "temperature": 0.8,
        "messages": [{"role": "user", "content":
                      f"In 3 short lines describe the shopping habits of a Philippine {who} (variant {i}): "
                      "when they shop, what they usually buy, how price-sensitive they are."}],
    }).encode()
    req = urllib.request.Request(f"{BASE_URL}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return out.get("usage", {}).get("completion_tokens", 0)


def main():
    t0 = time.perf_counter()
    with ThreadPoolExecutor(CONCURRENCY) as ex:
        toks = list(ex.map(one, range(REQUESTS)))
    dt = time.perf_counter() - t0
    total = sum(toks)
    print(f"requests={REQUESTS} concurrency={CONCURRENCY} wall={dt:.1f}s "
          f"completion_tokens={total} aggregate={total / dt:.0f} tok/s")
    print(f"estimate: 150 archetypes x ~250 tokens = {150 * 250 / max(total / dt, 1):.0f}s at this rate")


if __name__ == "__main__":
    main()
