# AMD Developer Cloud: step-by-step setup and test guide

Audience: you (Jericho), on Windows with PowerShell, setting up an AMD GPU server for the first time.
Goal: get an AMD GPU running, then run the six tests below. Each test proves one thing our design depends on.
Time: about 1.5 to 3 hours of GPU time. Cost: roughly $3 to $6 of your credit, if you destroy the server when done.

> What I could not verify: AMD's console labels and image names change. I could not load two of AMD's own pages while writing this (timeouts), so the screens in Part 1 follow AMD's blog and a user's write-up, not my own login. If a screen differs, follow what the console says and note it in `Docs/amd-smoke-test.md`.

---

## Part 0. What you are getting and what it costs

| Item | Detail |
|---|---|
| GPU | 1x AMD Instinct MI300X, 192 GB GPU memory (an 8x option also exists; you do not need it) |
| Price | about $1.99 per GPU hour (reported figure; confirm on the console's price page) |
| Credit | AMD AI Developer Program members get $100, about 50 hours, and **the credit expires 30 days after it is deposited** |
| Why it matters | 6 hackathon days cannot run a server 24/7 on 50 hours. We will start it only for work sessions, and **destroy it when idle** |

Suggested budget of the 50 hours (an estimate, adjust as we learn):

| Use | Hours |
|---|---|
| Tests in this guide | 3 |
| Persona library generation and model training | 5 |
| Development sessions (Oct 12 to 17) | 20 |
| Demo rehearsal and video recording | 8 |
| Reserve | 14 |

Safe rule: **destroy the instance when you stop** (take a snapshot first if you want to keep the disk). I could not confirm whether a powered-off instance still bills, so do not rely on "off".

---

## Part 1. Account and credit (do this now)

1. Join the AMD AI Developer Program: https://www.amd.com/en/developer/ai-dev-program.html
2. Create or sign in to your AMD account and verify your email.
3. **Click "Join" a second time after verifying.** Creating the account alone does not enroll you (a known confusion).
4. Open your profile on the AMD AI Developer Portal and follow the link for the **$100 Developer Cloud credit**.
5. Go to **https://devcloud.amd.com** and use **"AMD Sign-in"**. Do not use the login link in the DigitalOcean welcome email; it can loop (AMD Developer Cloud runs on DigitalOcean's platform).
6. Check the **Credits** tab: it should show about $100 available and an expiry date. The main Billing page may still show $0.00; that is normal.
7. If a payment method is requested, add one but keep the credit tab in view, and set a calendar reminder for the credit expiry date.

Record in `Docs/amd-smoke-test.md` section 1: date, credit amount, expiry date.

---

## Part 2. Create the server

1. In the Developer Cloud console choose **create a GPU instance (droplet)**.
2. Plan: **1x MI300X (192 GB)**.
3. Image: pick the one that lists **vLLM or ROCm + PyTorch pre-installed (Docker)**. If it only offers JupyterLab or a bare OS, choose the bare/Docker option; we install vLLM via Docker in Part 4.
4. SSH key: create one on your PC, then paste the public key into the console:

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\amd_devcloud
Get-Content $HOME\.ssh\amd_devcloud.pub      # copy this whole line into the console
```

5. Create the instance. Wait until it shows an IP address. Write the IP in your notes.

---

## Part 3. Connect and check the GPU

```powershell
ssh -i $HOME\.ssh\amd_devcloud root@<IP>
```

(If the console shows a different username than `root`, use that one.) On the server:

```bash
rocm-smi              # must list one AMD GPU
rocminfo | head -30   # shows the gfx architecture
docker --version      # Docker must exist for Part 4
```

**Pass:** `rocm-smi` shows the GPU with memory and temperature. Paste its output into `Docs/amd-smoke-test.md` section 4.

If `rocm-smi` is missing, the image has no ROCm tools; recreate with a ROCm image.

---

## Part 4. Start the working container

vLLM and PyTorch-for-ROCm come in AMD's `rocm/vllm` image. **Image tags change often** (two AMD pages showed different versions), so get the current tag from the ROCm vLLM page: https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/inference/vllm.html and put it in `TAG` below.

First copy the test scripts from your PC (run this on **Windows**, in the repo folder):

```powershell
cd D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas
scp -i $HOME\.ssh\amd_devcloud -r ai\smoke root@<IP>:~/smoke
```

Then on the **server**:

```bash
TAG=<current tag from the ROCm vLLM page>
docker pull rocm/vllm:$TAG
mkdir -p ~/models
docker run -d --name sim \
  --device /dev/kfd --device /dev/dri \
  --network=host --ipc=host --group-add=video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  -v ~/models:/app/models -v ~/smoke:/smoke \
  -e HF_HOME=/app/models \
  rocm/vllm:$TAG sleep infinity
docker exec -it sim bash        # you are now inside; open more shells with the same command
```

These flags are from AMD's ROCm docs. The container is named `sim` so you can open several shells into it.

---

## Part 5. The six tests

Run tests A, E and F inside the container (they need PyTorch with ROCm). Tests B, C and D need the vLLM server running (Test 0).

### Test A. GPU and PyTorch (about 1 minute)

```bash
python /smoke/rocm_check.py
```

**Pass:** prints a non-empty `hip` version, an AMD device name, and a TFLOPS figure.
**Proves:** PyTorch sees the GPU, which every model and the Quick Sim generator depend on.

### Test 0. Start the LLM server (keep it running)

In a second shell (`docker exec -it sim bash`), use `tmux` or a second terminal so it keeps running:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --host 127.0.0.1 --port 8000 --max-model-len 8192
```

The first start downloads the model (about 15 GB) and can take several minutes. Wait for a line saying the server is running.
Quick check from the first shell:

```bash
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct python /smoke/llm_smoke.py
```

**Pass:** one-sentence reply plus a tok/s figure. Take a `rocm-smi` snapshot while it runs.
`Qwen/Qwen2.5-7B-Instruct` is only a starting default that needs no access token. A 192 GB GPU can hold much larger models; once this works, try one larger model and keep the biggest one that still answers fast enough.

For the next tests set these in the shell:

```bash
export VLLM_BASE_URL=http://127.0.0.1:8000
export VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

### Test B. Structured owner profiles (about 1 minute)

```bash
python /smoke/json_schema_smoke.py
```

**Pass:** prints 3 owner profiles, `valid=True`, exit code 0. Note whether `mode=schema-enforced` or `prompt-only`.
**Proves:** the LLM can write the business-owner and company plans our simulator needs, in a shape we can validate. If it prints `valid=False` the simulator will reject it, which is the intended safety behaviour; record what failed.

### Test C. Persona library speed (about 1 to 2 minutes)

```bash
REQUESTS=64 CONCURRENCY=32 python /smoke/persona_batch_smoke.py
```

**Pass:** prints aggregate tokens per second and an estimate for 150 archetypes.
**Proves:** how long it takes to generate the customer and owner archetype library on this GPU. Try `CONCURRENCY=64` and keep the better number.

### Test D. GPU event generation (about 1 minute)

```bash
python /smoke/gen_events_bench.py
```

**Pass:** prints `device=cuda`, millions of customers, and an events-per-second figure.
**Proves:** the raw speed of the Quick Sim aggregated lane. Note this is generation only, not the full simulator; quote it that way. Try `CUSTOMERS=5000000 DAYS=60` to see how it scales.

### Test E. Hidden price response recovery (about 10 seconds)

```bash
python /smoke/demand_model_smoke.py
```

**Pass:** prints `device=cuda`, MAE about 0.22, correlation about 0.82, and `PASS`.
**Proves:** model training works on the AMD GPU, and a model can recover a hidden price elasticity from sales. This is the markdown proof in miniature. The true elasticity here is our own assumption, so it shows the method, not real shoppers.
Finding already recorded: fitting each SKU-branch alone from 14 days is noisy, so the real engine will pool across branches and categories.

### Test F. Both at once (about 2 minutes)

Run Test C while Test D runs in another shell, and watch `rocm-smi`.
**Pass:** neither crashes, and you can see how much throughput each loses.
**Proves:** whether the LLM and the generator can share one GPU in a demo, or whether the generator must pause while the LLM answers.

---

## Part 6. Use the server from your PC (optional, safer than opening a port)

The server above listens only on `127.0.0.1`. To call it from Windows, tunnel it:

```powershell
ssh -i $HOME\.ssh\amd_devcloud -N -L 8000:localhost:8000 root@<IP>
```

Leave that window open, then in another PowerShell:

```powershell
$env:VLLM_BASE_URL="http://localhost:8000"; $env:VLLM_MODEL="Qwen/Qwen2.5-7B-Instruct"
python ai\smoke\llm_smoke.py
python ai\smoke\json_schema_smoke.py
```

The three LLM scripts use only Python's standard library, so they run on Windows with no installs.

---

## Part 7. Record the results

Fill `Docs/amd-smoke-test.md`: GPU name, `rocm-smi` snapshot, the output of each test, the model used, and the best persona throughput. Then tell me; I will commit the file and use the numbers to size the plan (how many archetypes we can generate, how large Quick Sim can be, which model to use).

## Part 8. Shut down (do not skip)

1. If you want to keep model downloads, take a snapshot first. Otherwise they are re-downloaded next time.
2. In the console, **destroy** the instance.
3. Open the **Credits** tab and note the remaining balance in `Docs/amd-smoke-test.md`.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| Login loops on DigitalOcean page | You used the email link | Go to devcloud.amd.com and use "AMD Sign-in" |
| No credit shown | Not enrolled yet, or you looked at Billing | Click Join again after email verification; look in the **Credits** tab |
| `ssh` permission denied | Wrong key or user | Use `-i` with the private key (not `.pub`); use the username the console shows |
| `docker pull` fails | Tag no longer exists | Copy the current tag from the ROCm vLLM page |
| `torch.cuda.is_available()` is False in the container | Missing device flags | Re-run `docker run` with `--device /dev/kfd --device /dev/dri --group-add=video` |
| vLLM runs out of memory | Model too large or context too long | Lower `--max-model-len`, or use a smaller model |
| Model download fails with 401/403 | Gated model | Use an ungated one (Qwen), or set a Hugging Face token as an environment variable (never commit it) |
| Test B prints `valid=False` | Model drifted from the schema | Record the output; try a larger model; the simulator rejecting it is correct |
| Tunnel connects but calls hang | Server still downloading the model | Wait for "server running" in the vLLM shell |

## Sources
- [AMD Developer Cloud introduction](https://amd.com/en/blogs/2025/introducing-the-amd-developer-cloud.html)
- [How to get started on the AMD Developer Cloud](https://www.amd.com/en/developer/resources/technical-articles/2025/how-to-get-started-on-the-amd-developer-cloud-.html)
- [AMD AI Developer Program](https://www.amd.com/en/developer/ai-dev-program.html)
- [Claiming the $100 credit: login loop and billing gotchas (user write-up)](https://lilting.ch/en/articles/amd-developer-cloud-credit-journey)
- [vLLM inference and serving on ROCm](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/inference/vllm.html)
