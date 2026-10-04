import json
import os
import time
import urllib.request

BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000")
MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")  # starting default; swap to any model that fits the GPU


def main() -> None:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "In one sentence: why does a retail cash drawer end the day short?"}],
        "max_tokens": 80,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(f"{BASE_URL}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)
    dt = time.perf_counter() - t0
    text = out["choices"][0]["message"]["content"]
    toks = out.get("usage", {}).get("completion_tokens", 0)
    print("reply:", text)
    print(f"latency {dt:.2f}s, completion_tokens {toks}, ~{toks / dt:.1f} tok/s")
    assert text.strip(), "empty completion"


if __name__ == "__main__":
    main()
