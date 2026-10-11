# AMD session runbook

One session (about 2 hours of GPU time) that produces everything the submission needs from AMD: **numbers**, **a screen recording of AMD inside the working product**, and **the final video**. Follow it top to bottom. The generic setup tests (A to F) are in `amd-setup-guide.md`; this file is the order of work and what to capture.

**Rule it satisfies:** *a meaningful part of the workload runs on AMD infrastructure and is part of the working product shown to judges.* Two parts of the product use the GPU, and both are shown:

| What | Where it appears in the product | Hardware / software |
|---|---|---|
| **Quick Sim**: 200,000 shoppers over 28 days as tensors, then the same demand model and anomaly detector run over it | the simulator behind the A/B and scale results | PyTorch on ROCm |
| **AI Insight wording**: the language model that rewords the AI's plain-language notes; any note with an invented figure is refused | Intelligent Hub, Overview, "What the AI did, and why", notes marked "AI wording" | vLLM on ROCm, Qwen |

The prediction itself (demand model, optimizer) is statistics and does not need a GPU. Say that plainly; do not claim the GPU makes the prediction.

---

## 0. Before you pay for GPU time (on your PC, 10 minutes)

- [ ] The repo is pushed (the server clones it): https://github.com/Jerichopascua/MissionCommerceAI_by_eVo.Ninjas, branch `master`
- [ ] AMD account joined to the AI Developer Program and the **$100 credit shows on the Credits tab** (it expires 30 days after it is deposited)
- [ ] An SSH key exists: `ssh-keygen -t ed25519 -f $HOME\.ssh\amd_devcloud`; the **public** key (`.pub`) is added in the console. The private key stays on your PC and is never committed
- [ ] The collector works on your PC (it must say `amd: false` here, that is correct):
  ```powershell
  cd D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas\sim
  python scripts\amd_session_collect.py --out D:\tmp_amd_local.json --individuals 20000 --days 7
  ```
- [ ] Decide the model. Default `Qwen/Qwen2.5-7B-Instruct` (no access token needed). A larger one is optional once this works
- [ ] A screen recorder is ready (Windows: `Win+G` Game Bar, or OBS), and PesoWeb, the customer app and the agent run on your PC (`RUN\START.cmd`)

---

## 1. Create the server (5 minutes)

1. https://devcloud.amd.com, **AMD Sign-in** (do not use the DigitalOcean email link; it can loop).
2. Create a GPU instance: **1x AMD Instinct MI300X (192 GB)**, an image with **ROCm / vLLM (Docker)**, your public SSH key.
3. Wait for an IP address. Note the **time you started** (the clock is running at about $2 an hour).

## 2. Connect and check the GPU (2 minutes)

```powershell
ssh -i $HOME\.ssh\amd_devcloud root@<IP>
```
```bash
rocm-smi              # must list one AMD GPU
rocminfo | head -30   # shows the gfx architecture
docker --version
```
**Pass:** `rocm-smi` shows the GPU with memory and temperature. **Screen-record this** (shot 1).

## 3. Get the project and start the container (10 minutes)

On the server:
```bash
git clone https://github.com/Jerichopascua/MissionCommerceAI_by_eVo.Ninjas ~/mc
mkdir -p ~/models
TAG=<current tag from https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/inference/vllm.html>
docker pull rocm/vllm:$TAG
docker run -d --name sim \
  --device /dev/kfd --device /dev/dri \
  --network=host --ipc=host --group-add=video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  -v ~/models:/app/models -v ~/mc:/work \
  -e HF_HOME=/app/models \
  rocm/vllm:$TAG sleep infinity
docker exec -it sim bash
```
Inside the container, once:
```bash
pip install -r /work/sim/requirements.txt
python /work/ai/smoke/rocm_check.py        # Test A: prints hip version, the AMD device name, TFLOPS
```
**Pass:** a non-empty `hip` version and an AMD device name. (If it says no GPU, the image has no ROCm build of PyTorch: recreate with the ROCm image.)

## 4. Start the language model server (5 to 15 minutes, mostly the download)

In a **second** shell (`docker exec -it sim bash`, or `tmux`) and leave it running:
```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --host 127.0.0.1 --port 8000 --max-model-len 8192
```
Wait for the line saying the server is running. Check from the first shell:
```bash
VLLM_BASE_URL=http://127.0.0.1:8000 VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct python /work/ai/smoke/llm_smoke.py
```
**Pass:** a one-sentence reply and a tokens-per-second figure. **Record** `rocm-smi` in a third shell while it answers (shot 2).

## 5. Collect the evidence (5 to 10 minutes)

In the first shell:
```bash
cd /work/sim
python scripts/amd_session_collect.py \
  --out /work/results/amd-session.json \
  --llm-base http://127.0.0.1:8000 --llm-model Qwen/Qwen2.5-7B-Instruct
```
It measures, and writes nothing it did not measure: the GPU, ROCm/HIP and PyTorch versions, `rocm-smi`, matrix-multiply TFLOPS; **Quick Sim on the GPU and then on the CPU** (time and speed-up) for 200,000 shoppers over 28 days; and **AI Insight wording through the model** (notes reworded, notes refused, latency, tokens per second).

**Pass:** the last lines show `"amd": true`. If it shows `false`, PyTorch did not see an AMD GPU (see Troubleshooting); do not use the numbers.

Optional extra proof (the generic tests, about 5 minutes): Test D `python /work/ai/smoke/gen_events_bench.py` and Test E `python /work/ai/smoke/demand_model_smoke.py`. Quote Test D as generation speed only.

Copy the file back to your PC (from PowerShell, not the server):
```powershell
scp -i $HOME\.ssh\amd_devcloud root@<IP>:~/mc/results/amd-session.json D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas\results\amd-session.json
```

## 6. Show AMD inside the working product (15 minutes, **this is the footage**)

The point: the Intelligent Hub on your PC shows notes whose wording comes from the model running on the AMD GPU.

1. Open a tunnel (PowerShell window 1, leave it open):
   ```powershell
   ssh -i $HOME\.ssh\amd_devcloud -N -L 8000:localhost:8000 root@<IP>
   ```
2. In PowerShell window 2, point the agent at it and start the agent (the same window must start it, so the variables are inherited):
   ```powershell
   $env:LLM_BASE_URL = "http://localhost:8000"
   $env:LLM_MODEL    = "Qwen/Qwen2.5-7B-Instruct"
   cd D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas\RUN
   .\AGENT-REAL.ps1
   ```
   (No key is needed for your own vLLM server; do not put any key in a file.)
3. **Screen-record the following** (shot 3, about 60 seconds):
   - the `rocm-smi` terminal on the server visible on one side;
   - PesoWeb **Intelligent Hub, Overview**, section **What the AI did, and why**, press **Refresh the notes**;
   - the notes appear marked **AI wording** (not "Standard wording"); GPU use goes up in `rocm-smi`;
   - say what you see: "this wording is produced by Qwen on the AMD GPU, and every figure is checked against the data".
4. Quick proof for the documentation:
   ```powershell
   cd ..\sim
   python scripts\insight_check.py            # prints "wording: OpenAI-compatible API (http://localhost:8000 ...)" and how many notes the model reworded
   ```
   (`insight_check.py` uses the same environment variables.)

If a note stays "Standard wording", the model added a figure and it was refused; that is the safety rule working, not a failure. Keep one example of each for the video.

## 7. Save the evidence (10 minutes, before you destroy anything)

- [ ] `results\amd-session.json` is on your PC and has `"amd": true`
- [ ] 3 recordings: shot 1 (`rocm-smi`), shot 2 (model answering), shot 3 (the Hub with AI wording)
- [ ] 2 screenshots: the Hub with "AI wording", and the terminal with the collector's final lines
- [ ] Fill `Docs/amd-smoke-test.md`: date, GPU name, ROCm/PyTorch/vLLM versions, model, the numbers from `amd-session.json`, credit before and after
- [ ] Add one line to the project description: *"The shopper simulation (PyTorch on ROCm) and the language model that words the AI's notes (vLLM on ROCm) run on an AMD Instinct MI300X on the AMD Developer Cloud."* Only if `amd` is true.

## 8. Shut down (do not skip)

1. Optional: take a snapshot if you want to keep the model download.
2. In the console **destroy** the instance (a powered-off instance may still bill).
3. Open the **Credits** tab and write the remaining balance in `Docs/amd-smoke-test.md`.

## 9. Build the final video

```powershell
cd D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas
python video\make_pitch.py --cut full  --final      # about 4 minutes
python video\make_pitch.py --cut short --final      # about 3 minutes
```
`--final` refuses to build unless `results/amd-session.json` is a real AMD run, so the AMD scene can never show a placeholder or a CPU number. Replace the AMD scene's footage with your recordings (shot 1 to 3) in the editor you use for the voice-over, and commit `results/amd-session.json` and `Docs/amd-smoke-test.md`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `rocm-smi: command not found` | image without ROCm tools | recreate the instance with a ROCm image |
| collector says `"amd": false` | PyTorch is a CPU build, or the container has no `/dev/kfd` `/dev/dri` | start the container with the flags in step 3; use the `rocm/vllm` image |
| `torch.cuda.is_available()` is false in the container | missing `--device /dev/kfd --device /dev/dri` or `--group-add=video` | recreate the container with them |
| vLLM out of memory | `--max-model-len` too large, or another model is loaded | lower `--max-model-len`; restart the server |
| model download 401/403 | a gated model | use an ungated one (Qwen) or set a Hugging Face token as an environment variable (never commit it) |
| tunnel drops | idle SSH | add `-o ServerAliveInterval=30` to the `ssh -N -L` command |
| Hub notes are all "Standard wording" | the model added figures (refused), or the agent was started without the variables | check `LLM_BASE_URL` in the agent's own window; run `insight_check.py` |
| `ssh` permission denied | wrong key or user | use `-i` with the private key (not `.pub`) and the username the console shows |

## Do not

- Do not commit the SSH private key, any token, or `RUN\CREDENTIALS.txt`.
- Do not show a CPU result as an AMD result.
- Do not claim the GPU does the demand prediction: it generates and scores the simulation and serves the wording model.
- Do not leave the instance running overnight.
