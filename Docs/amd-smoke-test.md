# AMD smoke test results (P0)

Follow `Docs/amd-setup-guide.md`. Paste real outputs here. Never paste API keys, tokens or SSH keys.

Status: **not run yet.** If a test fails, record what failed and the workaround under "Problems".

## 1. Access
- Date:
- ADP joined, credit claimed (yes/no), credit amount and expiry date:
- Instance plan (expected 1x MI300X):
- GPU name:
- Image used, and the `rocm/vllm` tag used:

## 2. GPU visible (`rocm-smi`)
```
(paste)
```

## 3. Tests

| Test | What it proves | Result (paste key numbers) | Pass? |
|---|---|---|---|
| A `rocm_check.py` | PyTorch sees the AMD GPU | hip version, device, TFLOPS: | |
| 0 `llm_smoke.py` | vLLM serves an LLM | model, latency, tok/s: | |
| B `json_schema_smoke.py` | LLM writes valid owner profiles | mode (schema-enforced or prompt-only), valid: | |
| C `persona_batch_smoke.py` | Persona library generation speed | aggregate tok/s, estimate for 150 archetypes: | |
| D `gen_events_bench.py` | Quick Sim generator speed | customers, events/s: | |
| E `demand_model_smoke.py` | Training works; hidden price response recoverable | MAE, correlation, train time: | |
| F C + D together | LLM and generator can share the GPU | throughput of each when shared: | |

Raw output of each test:

```
(paste)
```

## 4. GPU utilization snapshot during Test 0 or C (`rocm-smi`)
```
(paste)
```

## 5. Problems and workarounds
-

## 6. Decisions this unlocks
- Best model that answered fast enough:
- Persona library generation time (starter 40, full 150):
- Largest Quick Sim customer count that ran comfortably:
- Can the LLM and generator share the GPU during the demo (yes/no):

## 7. After shutdown
- Instance destroyed (yes/no):
- Credit remaining:
