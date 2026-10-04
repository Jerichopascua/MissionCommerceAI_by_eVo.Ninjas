"""Can the LLM produce valid, structured owner profiles? (Sim.PesoWeb owner/persona generation.)

Tries vLLM's JSON-schema constrained output first, then falls back to prompt-only JSON.
Either way the result is validated here, because the simulator must never trust raw LLM output.
"""
import json
import os
import sys
import time
import urllib.request

BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000")
MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

VERTICALS = ["convenience", "grocery_pharmacy", "motorcycle_parts", "sports", "mixed"]
AMBITIONS = ["cautious", "steady", "aggressive"]

SCHEMA = {
    "type": "object",
    "properties": {
        "owners": {
            "type": "array", "minItems": 3, "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "vertical": {"type": "string", "enum": VERTICALS},
                    "capital_php": {"type": "integer", "minimum": 50000, "maximum": 50000000},
                    "branches": {"type": "integer", "minimum": 1, "maximum": 12},
                    "staff_per_branch": {"type": "integer", "minimum": 1, "maximum": 15},
                    "ambition": {"type": "string", "enum": AMBITIONS},
                },
                "required": ["name", "vertical", "capital_php", "branches", "staff_per_branch", "ambition"],
            },
        }
    },
    "required": ["owners"],
}

PROMPT = ("Create exactly 3 different Philippine retail business owners for a simulation. "
          "Return only JSON matching the schema. Vary vertical, capital, number of branches and ambition. "
          "Keep numbers realistic for the capital.")


def post(payload):
    req = urllib.request.Request(f"{BASE_URL}/v1/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def validate(obj):
    errs = []
    owners = obj.get("owners") if isinstance(obj, dict) else None
    if not isinstance(owners, list) or len(owners) != 3:
        return ["owners must be a list of 3"]
    for i, o in enumerate(owners):
        if not isinstance(o.get("name"), str) or not o["name"].strip():
            errs.append(f"{i}: name")
        if o.get("vertical") not in VERTICALS:
            errs.append(f"{i}: vertical {o.get('vertical')!r}")
        if o.get("ambition") not in AMBITIONS:
            errs.append(f"{i}: ambition {o.get('ambition')!r}")
        for k, lo, hi in (("capital_php", 50000, 50000000), ("branches", 1, 12), ("staff_per_branch", 1, 15)):
            v = o.get(k)
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                errs.append(f"{i}: {k}={v!r}")
    return errs


def main():
    base = {"model": MODEL, "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 600, "temperature": 0.7}
    mode = "schema-enforced"
    t0 = time.perf_counter()
    try:
        out = post({**base, "response_format": {"type": "json_schema",
                                                "json_schema": {"name": "owners", "schema": SCHEMA}}})
    except Exception as e:  # server without json_schema support
        print("json_schema mode failed:", e, "-> falling back to prompt-only JSON")
        mode = "prompt-only"
        out = post(base)
    dt = time.perf_counter() - t0
    text = out["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    obj = json.loads(text)
    errs = validate(obj)
    print(json.dumps(obj, indent=2))
    print(f"mode={mode} latency={dt:.2f}s valid={not errs}")
    if errs:
        print("validation errors:", errs)
        sys.exit(1)


if __name__ == "__main__":
    main()
