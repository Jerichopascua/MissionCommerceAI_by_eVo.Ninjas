# 03 — AMD Technology Requirements

## Mandatory rule

Every project must run a **meaningful part of its workload on AMD infrastructure or hardware**. The AMD component must be **part of the working product shown to judges**.

### Allowed AMD platforms

- AMD Developer Cloud
- AMD Instinct accelerators
- AMD ROCm
- AMD Ryzen AI
- AMD Radeon hardware
- Other approved AMD-powered infrastructure provided during the event

Teams may choose their own compatible **models, frameworks, and dev tools**.

## AMD offerings

### AMD Developer Cloud
On-demand AMD GPUs in the cloud; spin up in minutes.
- Training and fine-tuning models
- Benchmarking AI workloads on AMD GPUs
- Prototyping before moving to on-prem

### ROCm (AMD's open-source CUDA equivalent)
- PyTorch and TensorFlow on AMD GPUs
- Porting CUDA workloads to AMD
- High-performance AI/ML and HPC workloads

### AMD AI Developer Program (ADP) — required membership
- Tutorials, training, technical resources
- Access to AMD engineers
- Private community channels
- $100 free credits for new members

### Learning resources
- AMD AI Academy courses and documentation
- Hands-on labs with real GPU access
- Links listed on page: AMD AI Developer Program, AMD cloud development, ROCm AI Developer Hub, ROCm documentation, ROCm installation guide, github.com/ROCm/ROCm

## Practical implications for us

- Host our model(s) on AMD Developer Cloud — e.g., **vLLM on ROCm** for an open LLM, plus forecasting/recsys models trained via **PyTorch on ROCm**.
- Make AMD usage **visible in the demo** (endpoint, GPU metrics, `rocm-smi`, benchmark numbers).
- Partner tech (Google, Evolus) is **optional** — but AMD is not.
