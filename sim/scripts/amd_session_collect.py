"""Collects the AMD evidence for the demo video and the documentation, in one run on the AMD server.

    python scripts/amd_session_collect.py --out ../results/amd-session.json \
        [--llm-base http://127.0.0.1:8000] [--llm-model Qwen/Qwen2.5-7B-Instruct] [--individuals 200000] [--days 28]

What it measures (nothing is estimated or filled in; a part that cannot run is recorded as "not run" with the reason):
  1. the GPU and the software: PyTorch version, ROCm/HIP version, device name, `rocm-smi` text, matrix-multiply TFLOPS
  2. Quick Sim (the shopper simulator on tensors): the same run on the GPU and on the CPU, with times and the speed-up
  3. AI Insight wording through the language model served by vLLM on the same GPU: how many notes were reworded, how many
     were refused because the model added a figure, the latency and tokens per second

`amd` is true only when PyTorch reports a HIP (ROCm) build and a visible GPU. Run on any other PC it records what it
measured with amd=false, and the video builder refuses to present that as AMD."""
import argparse
import json
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "ai"))

# Three notes shaped exactly like the real Sell fast rows (see ai/tests/test_insight.py); the wording step is what is measured.
SAMPLE_FACTS = [
    {"product": "Squid Flakes Crackers", "branch": "Main", "daysLeft": 3, "batchQty": 27, "ratePerDay": 3.0, "unitsAtRisk": 18,
     "valueAtRiskAtCost": 270, "suggestedDiscountPct": 30, "suggestedPrice": 17.5, "proposalStatus": "Proposed"},
    {"product": "Rebisco Choco Mucho 30g", "branch": "Main", "daysLeft": 2, "batchQty": 36, "ratePerDay": 4.0, "unitsAtRisk": 28,
     "valueAtRiskAtCost": 140, "suggestedDiscountPct": 40, "suggestedPrice": 6.0, "proposalStatus": "Proposed"},
    {"product": "Quezo Real 50ml", "branch": "Main", "daysLeft": 4, "batchQty": 24, "ratePerDay": 2.0, "unitsAtRisk": 16,
     "valueAtRiskAtCost": 160, "suggestedDiscountPct": 30, "suggestedPrice": 10.5, "proposalStatus": None},
]


def gpu_and_software() -> dict:
    out = {"python": platform.python_version(), "platform": platform.platform()}
    try:
        import torch
        out.update(torch=torch.__version__, hip=getattr(torch.version, "hip", None), cuda_available=bool(torch.cuda.is_available()))
        if torch.cuda.is_available():
            out["device"] = torch.cuda.get_device_name(0)
            n = 8192
            a = torch.randn(n, n, device="cuda", dtype=torch.float16)
            b = torch.randn(n, n, device="cuda", dtype=torch.float16)
            for _ in range(3):
                torch.matmul(a, b)
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            reps = 20
            for _ in range(reps):
                torch.matmul(a, b)
            torch.cuda.synchronize()
            dt = time.perf_counter() - t0
            out["matmul_fp16_tflops"] = round(reps * 2 * n ** 3 / dt / 1e12, 1)
    except Exception as e:                    # no torch or no GPU: say so, do not guess
        out["torch_error"] = f"{type(e).__name__}: {e}"
    try:
        r = subprocess.run(["rocm-smi", "--showproductname", "--showuse", "--showmemuse"], capture_output=True, text=True, timeout=30)
        out["rocm_smi"] = r.stdout.strip()[:1500] if r.returncode == 0 else f"rocm-smi exit {r.returncode}"
    except Exception as e:
        out["rocm_smi"] = f"not available ({type(e).__name__})"
    out["amd"] = bool(out.get("hip") and out.get("cuda_available"))
    return out


def quick_sim(individuals: int, days: int) -> dict:
    from simpeso import quicksim
    result = {}
    for label, device in (("gpu", "cuda"), ("cpu", "cpu")):
        try:
            r = quicksim.run(individuals, days, 20, 60, 1, device)
            result[label] = {"device": r["device"], "gpu": r.get("gpu"), "generation_s": r["generation_s"], "events": r["events"],
                             "events_per_s": r["events_per_s"], "virtual_days_per_s": r["virtual_days_per_s"],
                             "forecast": r["forecast"], "anomalies": r["anomalies"]}
        except Exception as e:
            result[label] = {"not_run": f"{type(e).__name__}: {e}"}
    g, c = result.get("gpu", {}), result.get("cpu", {})
    if g.get("generation_s") and c.get("generation_s") and g.get("device") != c.get("device"):
        result["speedup_x"] = round(c["generation_s"] / g["generation_s"], 1)
    result["individuals"], result["days"] = individuals, days
    return result


def insight_wording(base: str, model: str) -> dict:
    from missionai import insight
    stats = {"calls": 0, "seconds": 0.0, "completion_tokens": 0}

    def wording(system: str, user: str) -> str:
        body = json.dumps({"model": model, "max_tokens": 160, "temperature": 0.2,
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
        req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.load(resp)
        stats["seconds"] += time.perf_counter() - t0
        stats["calls"] += 1
        stats["completion_tokens"] += int(out.get("usage", {}).get("completion_tokens", 0))
        return out["choices"][0]["message"]["content"].strip()

    notes = []
    try:
        for i, facts in enumerate(SAMPLE_FACTS * 4):                      # 12 notes
            facts = dict(facts, product=f"{facts['product']}")
            notes.append(insight.build("SellFast", f"sample:{i}", facts, wording=wording))
    except Exception as e:
        return {"not_run": f"{type(e).__name__}: {e}", "model": model, "base": base}
    reworded = sum(1 for n in notes if n["source"] == "model")
    return {"model": model, "base": base, "notes": len(notes), "reworded_by_model": reworded,
            "kept_standard_wording": len(notes) - reworded, "model_calls": stats["calls"],
            "avg_latency_s": round(stats["seconds"] / max(1, stats["calls"]), 2),
            "tokens_per_s": round(stats["completion_tokens"] / stats["seconds"], 1) if stats["seconds"] else None,
            "example": next((n["body"] for n in notes if n["source"] == "model"), notes[0]["body"] if notes else None)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "results" / "amd-session.json"))
    ap.add_argument("--individuals", type=int, default=200_000)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--llm-base", default=None)
    ap.add_argument("--llm-model", default="Qwen/Qwen2.5-7B-Instruct")
    args = ap.parse_args()

    result = {"measured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "host": platform.node()}
    print("1/3 GPU and software ...")
    result["hardware"] = gpu_and_software()
    result["amd"] = result["hardware"]["amd"]
    print("2/3 Quick Sim on the GPU and on the CPU ...")
    result["quicksim"] = quick_sim(args.individuals, args.days)
    print("3/3 AI Insight wording through the language model ...")
    result["insight_llm"] = insight_wording(args.llm_base, args.llm_model) if args.llm_base else {"not_run": "no --llm-base given"}

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("amd", "measured_at")}, indent=1))
    print("written", args.out)
    if not result["amd"]:
        print("NOTE: this is not an AMD ROCm machine; the numbers must not be presented as AMD results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
