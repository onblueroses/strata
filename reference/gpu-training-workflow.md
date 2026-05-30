<!-- keywords: training run, vram, gpu training, overnight training, tmux monitor, fine-tune, unsloth, training workflow, gpu workflow, unattended training -->
# GPU Training Workflow

Semi-autonomous ML training on external GPUs: platform selection, pre-flight, launch, monitoring, recovery, and result retrieval. Applies to Vast.ai, Colab, Kaggle, Modal, Lightning AI.

Read this before launching any overnight or unattended training run. The patterns here come from real failure modes across training-run-A and training-run-B sessions.

## Quick Nav

| Task | Section |
|------|---------|
| Work out what the job needs before choosing anything | Requirements Analysis |
| Pick a platform | Platform Selection |
| Check before launching | Pre-Flight Checklist |
| Launch patterns (Colab, Vast.ai, Modal) | Launch Patterns |
| Keep training alive across SSH disconnects | tmux on Remote Instances |
| Set up the cron job (key mechanism) | Cron Monitor |
| Resume a crashed or migrated run | Mid-Run Recovery |
| Get results back | Result Retrieval |
| Keep Claude Code session alive across compactions | Session Context Saving |
| What just went wrong | Failure Mode Taxonomy |

> **Local scripts rule**: Launch scripts, teardown scripts, monitor scripts, .env files, and anything with API keys must go in `.local/` within the repo (globally gitignored). Never commit provider-specific scripts to tracked directories.

---

## Requirements Analysis

<details>
<summary>Requirements Analysis</summary>

Do this before looking at any platform or instance listing. The failed attempts in this project's history (A4000 thermal throttle, 40GB disk filling before training started, PyTorch CPU fallback, Modal connection drop burning the monthly quota) all share a root cause: the instance was chosen before the job's actual requirements were known. Spend 5 minutes here and it saves hours of debugging on rented hardware.

### VRAM

Work out peak VRAM usage before renting. The formula for transformer fine-tuning:

```
VRAM ≈ (model_params × bytes_per_param × 4) + (batch_size × seq_len × hidden_dim × layers × 2 bytes)
      [model weights + optimizer states]       [activations]
```

In practice, look up the model card or use a rule of thumb:

| Model class | Params | fp32 VRAM (no optim) | fp16 + AdamW training |
|-------------|--------|----------------------|-----------------------|
| DeBERTa-v3-xsmall | ~70M | ~0.3 GB | ~4-6 GB |
| DeBERTa-v3-small | ~141M | ~0.6 GB | ~8-10 GB |
| DeBERTa-v3-base | ~183M | ~0.7 GB | ~10-14 GB |
| DistilBERT | ~66M | ~0.25 GB | ~4-5 GB |
| LLaMA-7B | ~7B | ~28 GB | ~56 GB (fp16 + AdamW) |

**Key questions:**
- What batch size do you need? Each 2x increase in batch size roughly doubles activation VRAM.
- Using gradient accumulation? grad_accum=N means you can use batch_size/N on GPU while simulating batch_size. Reduces VRAM, adds steps.
- Mixed precision (fp16/bf16)? Cuts model weight VRAM roughly in half but optimizer states stay fp32.
- Rule of thumb: add 20% buffer above your estimate. VRAM fragmentation and framework overhead add up.

**Minimum GPU by scenario:**
- DeBERTa-xsmall, batch=16, seq=512: 8 GB (T4 works)
- DeBERTa-xsmall, batch=32, seq=512: 16-18 GB (needs 4090/A4000)
- DeBERTa-small, batch=32, seq=512: 22-24 GB (4090 is the minimum)

### Disk

List every file that will land on the instance and estimate sizes:

```
dataset download:        _____ GB   (check HF dataset card - uncompressed Arrow often 3-5x raw)
HF Arrow cache:          _____ GB   (often as large as or larger than the download)
pip packages:            4-8 GB     (transformers + torch stack is large)
model checkpoints:       _____ GB   (model_params × 4 bytes per checkpoint × num_checkpoints)
ONNX/quantized export:  _____ GB   (if applicable)
                         ---------
Total:                   _____ GB
```

Add 20% buffer. Round up to the next tier (40/100/200 GB on Vast.ai).

**RAID-class datasets on Vast.ai:** minimum 100 GB. RAID raw ~5.6M rows, HF conversion cache + filtered balanced subset fills 40 GB before training even starts.

### Download speed / network

Most Vast.ai instances have fast datacenter networking (1-10 Gbps). The bottleneck is usually the HF Hub side, not the instance. With `hf_transfer` enabled, expect 100-500 MB/s for large dataset pulls.

**Slow download symptoms:** `huggingface-cli` stalls at <10 MB/s, progress bar stops for >30s. This is rate limiting on shared IPs, not the instance's fault. Fix: `pip install hf_transfer` + `HF_HUB_ENABLE_HF_TRANSFER=1`. If still slow after that, it's a transient HF issue - retry in 5 min.

**If you're pulling a private dataset:** HF_TOKEN must be set on the instance before the pull. Verify auth with `huggingface-cli whoami` before starting training.

### Estimated wall time

Rough estimate before renting to know if you need an overnight run or can finish in a session:

```
steps_per_epoch = ceil(train_samples / batch_size)
time_per_step  = ~0.1-0.3s (transformer fine-tuning on 4090, seq=512)
epoch_time     = steps_per_epoch × time_per_step
total_time     = epoch_time × num_epochs
```

- DeBERTa-xsmall, 380K samples, batch=32, 4 epochs on RTX 4090: ~25-35 min total
- Same on RTX A4000 (with throttling): ~60-90 min
- Same on T4 (Colab/Kaggle): ~90-120 min

If estimated time > 2h: plan for overnight. Set up tmux + cron before starting.
If estimated time > 9h: Kaggle background execution won't work (9h session limit). Use Vast.ai.
If estimated time > your free quota: use paid Vast.ai, not free tiers.

### The requirements checklist

Answer these before opening any provider dashboard:

```
VRAM needed:          _____ GB   → minimum GPU class: _____
Disk needed:          _____ GB   → minimum disk tier: _____
Estimated wall time:  _____      → overnight? yes / no
Free quota remaining: _____      → provider: _____  or use paid Vast.ai
HF_TOKEN needed:      yes / no
Session must survive unattended: yes / no  → if yes: tmux + cron required
```

Only after filling this in should you open the Platform Selection section.

</details>

---

## Platform Selection

<details>
<summary>Platform Selection</summary>

Choose based on run duration, VRAM requirement, and whether you need the job to survive unattended.

| Scenario | Platform | Why |
|----------|----------|-----|
| Multi-epoch overnight (< 9h, free) | Kaggle | 30h/week, dual T4, background execution, browser can close |
| Iterative experiments (< 30 min each) | Vast.ai RTX 4090 | ~$0.27-0.42/hr, best $/perf, 24GB VRAM, full CLI |
| Large model (> 24 GB VRAM) | Vast.ai A100 or Paperspace A6000 | Scale up instance, same workflow |
| Serverless one-shot | Modal | $30/month credits, no instance management overhead |
| Interactive debugging with IDE | Lightning AI | VS Code interface, 22h/month, A10G available |
| Quick prototype (< 2h) | Google Colab | Fastest to start, but unreliable allocation and session limits |

**Vast.ai GPU tiers** (from actual runs):

| GPU | VRAM | $/hr | Best for | Notes |
|-----|------|------|----------|-------|
| RTX A4000 | 16 GB | ~$0.09 | Budget runs | Throttles at 91°C, 140W limit. ~2.5x slower than 4090 on sustained load |
| RTX 4090 | 24 GB | ~$0.27-0.42 | Default choice | Best $/perf for multi-epoch. Fits batch=32 at seq_len=512 for DeBERTa-class models |
| A100 80GB | 80 GB | ~$1.50+ | Large models | Use only if 4090 VRAM is genuinely insufficient |

**Free tier hard caps** (check `$KB_DIR/areas/infrastructure/compute-budget.md` before use):

| Provider | Cap | Reset | CC? | Gotcha |
|----------|-----|-------|-----|--------|
| Kaggle | 30h GPU/week | Weekly | No | PyTorch 2.10+ silently falls back to CPU on P100 |
| Modal | $30/month | Monthly | No | Log retention 1 day; connection drop mid-run still bills |
| Lightning AI | 22h/month | Monthly | Yes (verify) | A10G and T4 share the same 22h pool |
| SageMaker Studio Lab | 4h GPU/day | Daily | No | Persistent storage survives sessions |
| Google Colab | Opaque | Rolling | No | Throttled after heavy use; K80 allocated during peak |

</details>

---

## Pre-Flight Checklist

<details>
<summary>Pre-Flight Checklist</summary>

Run through this before every training launch. Most session failures trace back to skipping one of these.

### Quota
- [ ] Read `$KB_DIR/areas/infrastructure/compute-budget.md` for the target provider
- [ ] Log your planned run (estimate duration) BEFORE starting
- [ ] If quota is tight, switch provider or ask first

### Environment
- [ ] **Disk**: Minimum 100GB on Vast.ai for any run that downloads RAID or similar large datasets. 40GB fills completely: dataset (~11GB) + HF Arrow cache + pip packages + checkpoints
- [ ] **VRAM**: DeBERTa-v3-xsmall at seq_len=512 needs 24GB for batch=32. Use batch=16 + grad_accum=2 on 16GB instances instead
- [ ] **GPU verification**: After SSH, run `nvidia-smi` immediately. Confirm GPU is visible and not in use by another process
- [ ] **CPU fallback check**: On Kaggle, verify GPU is actually allocated after notebook start. PyTorch 2.10+ silently falls to CPU on P100

### Dependencies
- [ ] Test `import torch; print(torch.cuda.is_available())` before starting training
- [ ] Run `python script.py --dry-run` if a dry-run mode exists
- [ ] If installing packages: install ALL packages before starting, restart runtime/kernel if any numpy/scipy/triton package is downgraded
- [ ] Check for sentencepiece, onnx, hf_transfer - often missing from base images

### Data
- [ ] If using HF Hub private dataset: verify `HF_TOKEN` is set in environment
- [ ] Pre-download check: `huggingface-cli download <dataset>` should complete in <60s with hf_transfer enabled. If it times out once, retry - transient Vast.ai rate limit, usually clears
- [ ] Preprocessing cached on HF Hub? If not, budget 20 min for RAID preprocessing (5.6M rows)

### Resumability
- [ ] Checkpoint saving configured (at minimum: save best + save latest)
- [ ] Run logs going to a file (not just stdout)
- [ ] Know the resume command before you start (add START_EPOCH arg or equivalent)
- [ ] Completion marker: script writes a file on finish that monitoring can detect

</details>

---

## Launch Patterns

<details>
<summary>Launch Patterns</summary>

### Vast.ai

Standard pattern for paid iterative experiments:

```bash
# 1. Find instance
vastai search offers 'gpu_name=RTX_4090 num_gpus=1 disk_space>=100' --order dph_total

# 2. Launch (pytorch image, 100GB disk, label it)
vastai create instance <OFFER_ID> \
  --image pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime \
  --disk 100 \
  --label "project-name-exp001"

# 3. Wait ~60s for SSH to come up, then connect
vastai ssh-url <INSTANCE_ID>   # prints the ssh command

# 4. Upload script + set env
scp -P <PORT> training/train_experiment.py root@<HOST>:/workspace/

# 5. SSH in, start tmux, run training inside it (see tmux section below)
ssh -p <PORT> root@<HOST>
# ... see "tmux on Remote Instances" section for the full pattern

# 6. Cron monitor handles results + teardown (see Cron Monitor section below)
```

**Fast download setup** (always do this before HF downloads on Vast.ai):
```bash
pip install hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_TOKEN=<token>
```

### Google Colab (semi-autonomous via CDP)

Use CDP keyboard events, not ydotool. ydotool click on Colab UI elements is unreliable.

```python
# Run all cells: CDP Input.dispatchKeyEvent Ctrl+F9
# This reliably reaches the browser page where ydotool doesn't
```

**numpy ABI mismatch fix**: If pip installs downgrade numpy after the kernel has loaded 2.x binaries, you'll get `numpy.dtype size changed` on next import. Fix: Runtime -> Restart session (not just kernel reset). This clears all Python process state. The pip install can then run clean.

**Session limits**: Colab disconnects after ~90 min idle and ~12h total. For runs approaching the limit, switch to Kaggle (9h background execution, browser can close).

### Modal (serverless)

```bash
# Deploy and run
modal run train_script.py::train_fn

# Check logs (1-day retention on free tier - grab before they expire)
modal logs <app_id>
```

**Connection drop risk**: If a Modal run is interrupted by a connection drop mid-train, the GPU time may still bill. The $30/month cap is shared across all projects. Treat Modal free credits as fragile - prefer for short runs (<1h).

### Kaggle (background execution)

Enable "Run All" and detach browser:
1. Runtime selector: verify GPU, not CPU
2. Settings: Internet access = On (disabled by default per notebook)
3. Sidebar: "Run All" → session continues after browser close
4. Check `torch.cuda.get_device_name()` in first cell to confirm GPU before running full notebook

</details>

---

## tmux on Remote Instances

<details>
<summary>tmux on Remote Instances</summary>

tmux is not optional for overnight runs. Without it, your training process is a child of your SSH session. When the SSH connection drops - and it will, especially overnight - the process dies. With tmux, the process is owned by the remote machine's tmux server. SSH disconnects are irrelevant.

### Starting a training run in tmux

```bash
# SSH into instance
ssh -p <PORT> root@<HOST>

# Create a named session
tmux new-session -s train

# Set env vars inside the session (they don't carry from your SSH shell)
export HF_TOKEN=<token>
export HF_HUB_ENABLE_HF_TRANSFER=1

# Start training
python train_experiment.py --exp-id exp001 --hypothesis "focal loss"

# Detach WITHOUT killing the process
# Press: Ctrl+B, then D
```

The training now runs independently of your connection. You can close your terminal.

### Re-attaching to check progress

```bash
# SSH back in
ssh -p <PORT> root@<HOST>

# List sessions (confirm it's still running)
tmux ls

# Attach to the session
tmux attach -t train

# Detach again when done checking
# Ctrl+B, then D
```

### Multiple sessions on one instance

If you need a separate window to check disk/GPU while training runs:

```bash
# In the training session: Ctrl+B, then D (detach)

# Create a second session for monitoring
tmux new-session -s monitor
nvidia-smi
df -h /workspace

# Switch between sessions
tmux attach -t train
tmux attach -t monitor
```

### Key tmux commands reference

| Action | Command |
|--------|---------|
| New session | `tmux new-session -s <name>` |
| Detach (keep running) | `Ctrl+B`, then `D` |
| List sessions | `tmux ls` |
| Re-attach | `tmux attach -t <name>` |
| Kill session | `tmux kill-session -t <name>` |
| New window in session | `Ctrl+B`, then `C` |
| Switch windows | `Ctrl+B`, then `0-9` |

### Why env vars must be set inside tmux

SSH carries your local env vars into the session. tmux does NOT inherit them when you re-attach later. If you set `HF_TOKEN` in your shell before `tmux new`, it works for that session. But if you detach, the instance reboots, or you create a second session - it won't be there.

Safe pattern: always export env vars as the first thing inside the tmux session, before running any training code.

</details>

---

## Cron Monitor

<details>
<summary>Cron Monitor</summary>

The cron job is the mechanism that makes "semi-autonomous" actually work. Without it, you cannot safely go to sleep - you'd need to manually check if training finished, manually pull results, manually destroy the instance. With it: set it up before you sleep, wake up with results already local and the instance already gone.

**Set up the cron job before you start the training run, not after.** If training finishes while you're setting up the cron job, you've already missed the window.

### The full cron monitor script

Save as `~/.local/bin/monitor-training.sh` (or project-specific path). Parametrize per-run via variables at the top.

```bash
#!/bin/bash
# monitor-training.sh
# Called every 6 min by cron. Polls for completion, syncs results, destroys instance.
# Edit the three variables below for each new run.

INSTANCE_ID="33981912"
RESULTS_DIR="$HOME/Work/training-run-A/runs/v0.4.1"
MARKER_FILE="${RESULTS_DIR}/training_complete.json"
DONE_MARKER="${RESULTS_DIR}/.monitor-done"

# Already handled - cron entry hasn't been removed yet
if [ -f "${DONE_MARKER}" ]; then
    exit 0
fi

# Sync latest results from instance (partial sync is fine, gives progress)
vastai copy C.${INSTANCE_ID}:/workspace/results/ ${RESULTS_DIR}/ 2>/dev/null

# Check if training wrote its completion marker
if [ -f "${MARKER_FILE}" ]; then
    echo "[$(date)] Completion marker found. Starting teardown."

    # Full final sync
    vastai copy C.${INSTANCE_ID}:/workspace/ ${RESULTS_DIR}/ 2>/dev/null
    echo "[$(date)] Results synced to ${RESULTS_DIR}"

    # Destroy instance
    vastai destroy instance ${INSTANCE_ID}
    echo "[$(date)] Destroy command sent for instance ${INSTANCE_ID}"

    # Verify destruction within 30s
    sleep 30
    if vastai show instances 2>/dev/null | grep -q "${INSTANCE_ID}"; then
        echo "[$(date)] MANUAL CLEANUP NEEDED: instance ${INSTANCE_ID} may still be running"
    else
        echo "[$(date)] Instance confirmed destroyed."
    fi

    # Mark done so cron stops doing anything
    touch "${DONE_MARKER}"
fi
```

### Installing the cron job

```bash
# Open crontab editor
crontab -e

# Add this line (runs every 6 min, logs to file you check next morning)
*/6 * * * * bash $HOME/.local/bin/monitor-training.sh >> /tmp/training-monitor.log 2>&1
```

### Checking the log next morning

```bash
# See what happened overnight
cat /tmp/training-monitor.log

# Check if instance was destroyed
vastai show instances

# Verify results are local
ls -la $HOME/Work/<project>/runs/<version>/
```

### Completion marker on the instance

The training script must write this file when it finishes. Without it the cron job never triggers teardown.

```python
# Add to end of training script (after all checkpoints are saved)
import json, datetime, os

results_dir = '/workspace/results'
os.makedirs(results_dir, exist_ok=True)

with open(f'{results_dir}/training_complete.json', 'w') as f:
    json.dump({
        'status': 'complete',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'best_tpr': best_tpr,   # your primary metric
        'epochs_completed': epoch,
    }, f)
```

**Write the completion marker as the very last thing** - after saving best checkpoint, after ONNX export, after writing experiments.jsonl. Once the cron job sees it, it will start the sync + destroy sequence.

### Billing safety

Max billing exposure = cron interval (6 min) after training completes. If cron is set to `*/6` and training finishes at 3:00am, the instance is destroyed by 3:06am at the latest.

If `vastai destroy` fails (network issue, API error), the script logs "MANUAL CLEANUP NEEDED". Check `/tmp/training-monitor.log` first thing after waking. Run `vastai show instances` to confirm.

### Removing the cron entry after the run

The `.monitor-done` marker prevents the script from doing anything after teardown, but the cron entry still runs every 6 min doing nothing. Clean it up:

```bash
crontab -e
# Delete the monitor-training.sh line
```

Or if you want cron to remove itself automatically, replace `touch "${DONE_MARKER}"` at the end with:
```bash
# Self-removing cron entry (fragile - only if crontab has exactly one entry for this script)
crontab -l | grep -v "monitor-training.sh" | crontab -
```

</details>

---

## Mid-Run Recovery

<details>
<summary>Mid-Run Recovery</summary>

### Instance migration (thermal throttle, disk full, billing issue)

Standard procedure when a run needs to move mid-epoch:

```bash
# 1. Pause/interrupt training on old instance (Ctrl+C or kill process)
# 2. Pull checkpoint and logs locally (takes ~5 min)
vastai copy C.<OLD_ID>:/workspace/runs/ ./runs/ 2>/dev/null

# 3. Destroy old instance
vastai destroy instance <OLD_ID>

# 4. Rent new instance (100GB disk, better GPU)
vastai create instance <NEW_OFFER_ID> \
  --image pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime \
  --disk 100 \
  --label "project-migration"

# 5. Upload checkpoint to new instance
vastai copy ./runs/ C.<NEW_ID>:/workspace/runs/ 2>/dev/null

# 6. Resume from checkpoint
python train.py --start-epoch <N> --checkpoint /workspace/runs/latest.pt
```

**Overhead**: ~5 min total. Worth it when throttling is cutting throughput by 60%+.

### BATCH_SIZE is locked after epoch 1

**Never change BATCH_SIZE when resuming mid-run.** The LR scheduler fast-forward replays `(START_EPOCH - 1) * steps_per_epoch` steps to restore state. This calculation assumes the same batch size used in epoch 1. Changing batch size mid-run corrupts the LR schedule silently - training continues but warmup/decay are wrong.

If you need a different batch size, run a new experiment from scratch.

### Disk full during training

Symptoms: HF download hangs, checkpoint save fails silently, pip install fails.

40GB disk is not enough for RAID-class datasets. Sequence that fills 40GB:
- Dataset download: ~11GB
- HF Arrow cache (converted format): ~15-20GB
- pip packages (transformers, torch, etc.): ~6-8GB
- Checkpoints: variable

Fix: always rent 100GB minimum. If already running and out of disk:
1. `du -sh /root/.cache/huggingface/hub/*/` - find redundant cached models
2. `rm -rf /root/.cache/huggingface/hub/models--<old-model>/` - delete unused
3. If still stuck: migrate to new 100GB instance

### HF Hub download retry

RAID and similar large datasets sometimes time out on first pull (transient Vast.ai rate limit). Standard fix:
```bash
# Retry once with hf_transfer - usually resolves on second attempt
HF_HUB_ENABLE_HF_TRANSFER=1 python -c "from datasets import load_dataset; load_dataset('liamdugan/raid', split='train')"
```

If it fails twice, the issue is something else (disk space, token auth).

</details>

---

## Result Retrieval

<details>
<summary>Result Retrieval</summary>

Pull results before destroying the instance. Order matters.

```bash
# 1. Pull ALL results first
vastai copy C.<ID>:/workspace/results/ ./runs/experiment-001/ 2>/dev/null
vastai copy C.<ID>:/workspace/*.json ./runs/experiment-001/ 2>/dev/null

# 2. Verify key files exist locally
ls -la ./runs/experiment-001/

# 3. Then destroy
vastai destroy instance <ID>
```

**What to always pull:**
- Best checkpoint (`.pt` or `.bin`) - can be large, verify size before pulling
- Training log / metrics JSON
- ONNX export if applicable
- Any completion markers

**What not to bother with:**
- Intermediate checkpoints (only best + latest)
- pip caches, HF caches, anything in `~/.cache`

**Log Modal runs within 24h.** Free tier log retention is 1 day. If a Modal run completes overnight, pull logs first thing next morning.

### Local checkpoint organization

Keep checkpoints at `Work/<project>/runs/<version>/` with a consistent structure:
```
Work/training-run-A/runs/v0.4.1/
  checkpoint-best.pt       # selected by primary metric (TPR@5%FPR, not accuracy)
  checkpoint-latest.pt     # last epoch, for resumption
  training_log.json        # per-epoch metrics
  config.json              # hyperparams used
```

Record run details in `experiments.jsonl` or equivalent log before pulling - the checkpoint alone doesn't capture what hypothesis was tested.

</details>

---

## Session Context Saving

<details>
<summary>Session Context Saving</summary>

Long training runs routinely outlast a single Claude Code session. Compaction happens, you come back the next morning, and without deliberate context preservation the next instance has no idea what ran, what failed, or what's next.

### Use a spec for any multi-step training run

For any training workflow with more than one meaningful step (preprocess → push → first run → iterate), create a spec via `/spec`. The spec survives compaction because it's a file, not context. It holds:
- Current step (updated before/after each step)
- Decisions table (why this GPU, why this batch size, why this baseline)
- Learnings (failure modes discovered mid-run)
- Completion state (which experiments passed, which are pending)

Without a spec, after compaction you must reconstruct what ran from compute-budget.md and experiments.jsonl - possible but slow and error-prone.

**When to update the spec:**
- Before starting a run: update `>> Current Step` with what's about to happen
- After a run completes: check the box, add TPR result to Completed, advance `>> Current Step`
- When something unexpected happens: add to Learnings immediately

### Pre-compaction save

Before context window fills:
1. Run `/context-save` to write `.claude/auto-context-save-{sessionId}.md`
2. The save captures: current goal, active spec reference, in-progress state, next action

The `PreCompact` hook (`context-pre-compaction-save.sh`) fires automatically and writes a save file. This is the fallback if you forget to run `/context-save` manually.

### Recovery after compaction

When you return to a training session after compaction:

1. Check `.claude/specs/` for a spec with `Status: in-progress` matching the session
2. Read `>> Current Step` - this is authoritative
3. Read Learnings - these capture discoveries made since the spec was written
4. Read compute-budget.md to know remaining quota
5. Check `experiments.jsonl` (or equivalent log) for what already ran and what the current baseline is

**Do NOT re-derive decisions from scratch.** If the Decisions table says "RTX 4090 because A4000 throttled at 91°C", trust it. Don't re-research GPU options.

### Experiment log as ground truth

`experiments.jsonl` (or equivalent) is the persistent log that survives everything - compaction, instance destruction, session end. It's what lets any future instance reconstruct the experiment history without relying on context.

Every run before it starts should write at minimum:
```jsonl
{"exp_id": "focal-001", "hypothesis": "focal loss over BCE", "started": "2026-04-02T03:00:00Z", "status": "running"}
```

Update to `"status": "complete"` with TPR result after the run. This way even a crashed session leaves a partial record.

### The pattern that prevents lost overnight work

```
Before sleeping:
  1. Training running inside tmux session on instance (tmux ls confirms it)
  2. Cron job installed and verified (crontab -l shows the entry)
  3. Training script will write completion marker when done
  4. Spec >> Current Step updated with what's running and expected duration
  5. compute-budget.md row added with estimated hours

After waking:
  1. cat /tmp/training-monitor.log  ← did cron fire? did teardown run?
  2. vastai show instances           ← instance should be gone
  3. ls $HOME/Work/<project>/runs/       ← results should be local
  4. Update spec with outcome (TPR, KEEP/DISCARD), advance >> Current Step
  5. Update compute-budget.md row with actual duration
```

</details>

---

## Failure Mode Taxonomy

<details>
<summary>Failure Mode Taxonomy</summary>

| Failure | Symptom | Cause | Fix |
|---------|---------|-------|-----|
| Silent CPU fallback | Training "completes" in minutes, loss barely moves | Kaggle P100 + PyTorch 2.10+: GPU not accessible, falls to CPU | Switch to Colab or Vast.ai; on Kaggle, verify `torch.cuda.is_available()` immediately after GPU allocation |
| numpy ABI mismatch | `numpy.dtype size changed, may indicate binary incompatibility` | pip downgraded numpy <2.0 after 2.x was already loaded into process | Full runtime restart (not kernel reset) - clears loaded binaries |
| LR schedule corrupted | Training loss trajectory wrong after resume | BATCH_SIZE changed between epochs when using scheduler fast-forward | Never change batch size mid-run; start new experiment |
| Thermal throttle | GPU utilization ~40-50% despite high process load | A4000 hitting 91°C, 140W power limit | Migrate to RTX 4090 instance; 4090 runs cooler, ~2.5x faster at similar cost |
| Disk full silently | HF download hangs, checkpoint fails | 40GB disk filled by dataset + cache + packages | Always rent 100GB; clean HF cache of unused models mid-run as stopgap |
| HF download timeout | `requests.exceptions.ConnectionError` mid-download | Vast.ai shared IP rate-limited by HuggingFace | Retry once with hf_transfer; usually clears |
| tar pipe silent truncation | Transfer "succeeds" but file is truncated or corrupt | Vast.ai SSH proxy buffer overflow on large binary streams | Never tar pipe on Vast.ai; use `vastai copy` or rsync |
| Missing dependency | `ModuleNotFoundError: No module named 'sentencepiece'` | Base Docker image missing package | Run full pip install + --dry-run before starting real training |
| Modal quota burned | $30 hits 0 mid-experiment | Connection drop during long run, still billed | Use Modal for <1h runs only; prefer Vast.ai for multi-epoch |
| Account verification blocker | Platform shows "verify phone" gate | Lightning AI, SageMaker require phone verify before GPU access | Resolve before needing it; Lightning AI phone verify is one-time |
| SSH proxy failure | Connection drops mid-transfer | Vast.ai proxy connection limits | Use `vastai copy`, not manual scp/rsync for large files |
| Concurrent quota burn | Quota exhausted unexpectedly | Multiple Claude Code instances each logging usage; or single session mis-estimating | Always read compute-budget.md before starting; log estimate first |

</details>

---

## Experiment Hygiene

<details>
<summary>Experiment Hygiene</summary>

These apply to any iterative ML experiment workflow (autooptimize-style or manual).

**One change per run.** Each experiment tests exactly one hypothesis vs a fixed baseline. Combining multiple changes makes results uninterpretable.

**Log before you run.** Write the JSONL/log entry (or at least the compute-budget row) before starting training. If the instance crashes, you still have a record.

**Primary metric is not validation accuracy.** For tasks with class imbalance or skewed deployment conditions (like AI text detection), use the task-specific metric as the primary selector for "best" checkpoint. TPR@5%FPR matters more than 99% accuracy for a browser extension classifier.

**Baseline is architecture-specific.** Don't compare across different model architectures (v0.3 DeBERTa-small vs v0.4 xsmall). Establish a fresh baseline for each new architecture, then iterate within it.

**Disk size for RAID-class datasets**: 100GB minimum. Sequence: download (~11GB) + HF conversion cache (~15-20GB) + packages (~6-8GB) + checkpoints. 40GB fills before training starts.

**Model size vs deployment target**: DeBERTa-v3-small INT8 is 164MB (not 70MB). Always check exported model size against deployment constraints before committing to an architecture. xsmall is the realistic choice for browser extensions.

</details>
