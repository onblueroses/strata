<!-- keywords: vastai, vast.ai, gpu instance, gpu rental, vastai cli, instance launch, vast instance -->
# Vast.ai Operations

Quick reference for Vast.ai GPU instance management. CLI is the primary interface.

**Read this doc when**: spinning up any GPU instance on Vast.ai, launching overnight experiments, running GPU training, or doing data transfer between instances.

## Quick Nav

| Section | Jump to |
|---------|---------|
| CLI Basics | Instance lifecycle, one-call launch, cloud copy, disk sizing, labels |
| Single SSH Launch | Setup + detached launch in one SSH call; where the completion chain lives |
| Data Transfer | `vastai copy`, model caching, `hf download` |
| Auto-Teardown | Pull, verify, then destroy — from the watcher, never the box |
| Dud-Host Failover | Detect a bad host fast and rotate offers |
| Gotchas | SSH proxy limits, model downloads, billing |

> **Local scripts rule**: Launch scripts, teardown scripts, .env files, and anything with API keys must go in `.local/` within the repo (globally gitignored). Never commit provider-specific scripts to tracked directories.

---

## CLI Basics

<details>
<summary>CLI Basics</summary>

The `vastai` CLI is installed at `<user-bin>/vastai`. Substitute the actual cache root for `<model-cache>` (often the container user's Hugging Face hub cache) and an existing public key path for `<ssh-public-key>`. Always use it over raw SSH for instance management.

```bash
# List running instances
vastai show instances-v1

# Create instance
vastai create instance <offer_id> --image <image> --disk <gb> --label <name>

# Destroy instance (stops billing immediately)
vastai destroy instance <instance_id>

# Stop instance (keeps disk, stops billing for compute)
vastai stop instance <instance_id>

# SSH into instance (prefer this over manual ssh for port lookup)
vastai ssh-url <instance_id>

# Copy files between instances or local (uses rsync internally)
vastai copy <src> <dst>
# Instance paths use C.<instance_id>:/path format:
vastai copy C.12345:/workspace/results/ ./local-results/
vastai copy ./local-file C.12345:/workspace/
vastai copy C.12345:/path/ C.67890:/path/   # instance-to-instance
```

### Search + create in one call

`vastai launch instance <gpu_name> <num_gpus> <image>` runs the search and creates from the top offer, so a one-box launch needs no offer-ID plumbing:

```bash
vastai launch instance RTX_4090 1 <current pytorch image> \
  --disk 100 --label "my-experiment" --ssh --cancel-unavail
```

`--cancel-unavail` returns an error instead of creating a stopped instance. Per `--help` (CLI 1.4.3, checked 2026-08-09) that is exactly the host-double-booked failure mode in Dud-Host Failover; unverified against a live dud, so keep the failover poll loop regardless. Use the explicit `search offers` + `create instance` split when you need to exclude machine_ids or filter on `cuda_max_good` — `launch instance` takes neither.

### Push results to object storage

`vastai cloud copy` moves artifacts between an instance and a cloud connection (`vastai show connections`), which keeps the pull off the laptop:

```bash
vastai cloud copy --src /workspace/results --dst <remote-path> \
  --instance <id> --connection <conn_id> --transfer 'Instance To Cloud'
```

### Disk sizing

Size the disk from the actual run: dataset + HF Arrow cache (roughly the dataset again) + pip packages + checkpoints, with the total and its basis recorded in the launch note. The one measured failure: a 40 GB disk filled before training started on an ~11 GB raw dataset (RAID-class run, archived in `life/areas/infrastructure/gpu-training-workflow.md`); cache and packages more than tripled the raw footprint. When the footprint is genuinely unknown, err large and mark the size unmeasured rather than inventing a floor.

### Labels

Always label instances for identification:
```bash
vastai label instance <id> "project-name-gpu1"
```

</details>

## Single SSH Launch

<details>
<summary>Single SSH Launch</summary>

The preferred pattern for GPU experiments. One SSH call does: full setup, nohup launch, completion marker. No polling, no repeated SSH.

### Why not multiple SSH calls?

Vast.ai proxies SSH. Multiple calls are fragile - connection drops during setup leave the instance in an unknown state. One call that sets up and returns is reliable. Proxy fragility alone justifies the pattern.

### Why not `vastai execute`?

Read the CLI before assuming its limits (checked against CLI 1.4.3, 2026-08-09):

- `vastai execute <id> COMMAND` takes "a bash command surrounded by single quotes", not a fixed verb list. Its help still advertises only `ls`, `rm`, `du` as supported commands, so treat anything beyond those as untested.
- It is request/response: it returns the command's output after a few seconds. It gives you no detached process and no way to keep a training run alive, which is what the nohup + marker pattern exists for.
- It carries server-side scheduling (`--schedule HOURLY|DAILY|WEEKLY`, `--start_date`, `--end_date`, `--day`, `--hour`), as does `vastai cloud copy`.

So `execute` does not replace the SSH launch, but `--schedule` is a real alternative to running your own poller: a scheduled `cloud copy` pushes artifacts off the box without a laptop in the loop. The teardown decision still belongs to the watcher (see Auto-Teardown).

### Pattern

**0. Preflight locally before any paid provision.** Run the generic dry-run gate first — <notes-tree>/lore/references/compute-discipline.md "Dry Runs Before the First Paid Run", triggered from the shared contract **Gate before the spend**. Against the exact code you are about to ship: import-all-modules, dependency-presence (`pip check`), op-coverage, model-availability (HF gating, weights present), runtime-API-surface. (Those classes are generic and belong in the dry-run section; they sit here until that move happens.)

The Vast-specific evidence for why, forensics 2026-06-26: skipped preflights caused 4 wasted box launches, a bad CUDA image, and ~$0.80 of GPU crashes that were all locally detectable before spend. The one Vast-only check to add is image/driver compatibility, because `create instance` does not verify it for you (see Dud-Host Failover step 1).

**1. Write a launch script locally** (keep it in `remote/launch-remote.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail

# Setup. Resolve the framework install line at launch time - do not paste a pinned
# index URL from a doc (the shared contract **Current versions**); CUDA extras get retired.
pip install --quiet "<current framework CUDA install line>"
git clone https://github.com/youruser/your-repo.git /workspace/repo
pip install --quiet -e /workspace/repo

# Verify the GPU is visible to the framework you just installed, and fail here if not
python3 -c "import jax; d=jax.devices(); assert d[0].platform=='gpu'; print('GPU OK:', d)"

# Write the run wrapper. It runs, records the exit code, and STOPS.
# No destroy, no curl DELETE - see Auto-Teardown.
cat > /workspace/run.sh << 'EOF'
#!/usr/bin/env bash
cd /workspace/results
python3 -m your.module ... >> /workspace/run.log 2>&1
EXIT=$?
printf '{"status":"complete","exit":%d,"ts":"%s"}\n' "$EXIT" "$(date -Iseconds)" \
  > /workspace/results/done.json
EOF

chmod +x /workspace/run.sh
mkdir -p /workspace/results
nohup bash /workspace/run.sh </dev/null >> /workspace/run.log 2>&1 &
echo "PID: $! - SSH session done, experiment running"
```

Key points:
- Outer script uses `set -euo pipefail` so any setup error aborts immediately
- The inner heredoc is quoted (`<< 'EOF'`), so `$EXIT` and `$(date …)` evaluate on the box at runtime. Unquote the delimiter only if you actually need the outer shell to substitute a value, and never substitute an API key that way
- `done.json` carries the exit code: a crashed run must be distinguishable from a clean one by the watcher, or you pull nothing and destroy anyway
- `nohup ... </dev/null ... &` detaches completely from the SSH session
- No credentials are shipped to the box. The instance never destroys itself

**2. Create the instance** (--ssh flag required for SSH access):

```bash
OFFER_ID=$(vastai search offers 'gpu_name=RTX_4090 num_gpus=1 disk_space>=100 inet_up>=100' \
  --order dph_base --limit 1 --raw | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
vastai create instance $OFFER_ID \
  --image <current pytorch image> \
  --disk 100 --label "my-experiment" --ssh
# Note the instance ID from the JSON response
```

Resolve the image tag at launch time, then read its CUDA version and use that as the `cuda_max_good` floor in the offer filter. A stale tag pinned in a doc silently shrinks the pool of offers that pass the filter, and every month it ages it shrinks further.

**3. Wait for the instance to be running**:

```bash
# 16 polls x 30s = the 8-minute dud budget from Dud-Host Failover
for i in $(seq 1 16); do
  STATUS=$(vastai show instance $INSTANCE_ID --raw | python3 -c "import json,sys; print(json.load(sys.stdin).get('actual_status','?'))")
  echo "[$i] $STATUS"
  [ "$STATUS" = "running" ] && break
  sleep 30
done
```

Falling out of this loop still `loading` means the host is a dud, not that you should wait longer. Destroy and take the next offer.

**4. Get the SSH URL and fire one SSH call**:

```bash
SSH_URL=$(vastai ssh-url $INSTANCE_ID)
# SSH_URL format: ssh://root@<host>:<port>
HOST=$(echo $SSH_URL | sed 's|ssh://root@||' | cut -d: -f1)
PORT=$(echo $SSH_URL | cut -d: -f3)

ssh -o StrictHostKeyChecking=no -p $PORT root@$HOST bash -s \
  < remote/launch-remote.sh
```

The SSH call returns once setup is done and nohup is launched. The experiment runs in the background and stops at `done.json`. Nothing on the box destroys anything.

**5. Put the completion chain somewhere that outlives the session.** There is no cron on this laptop (`cronie` is not installed, `crontab` is not on PATH, verified 2026-08-09), and a laptop-side poller is the wrong place for the data-safety path anyway. Pick by run length:

| Run shape | Mechanism |
|-----------|-----------|
| >1h, must survive the laptop dying | VPS watcher: detached job → hash-verified pull → `PULL_DONE` → destroy. Full contract in <notes-tree>/lore/references/compute-discipline.md "Laptop-Independent Completion Chains" |
| Session-scoped, you are watching | Background Bash + the Monitor tool (`/monitor`): a health-check script reports, the session acts only on a problem |
| Recurring local poll you want on this machine | systemd user timer (`<user-systemd>/*.timer`) — the pattern actually in use here |
| Artifact push with no local process at all | `vastai cloud copy --schedule` server-side (see CLI Basics) |

Whichever you pick, the poll body is the same: `vastai copy C.$INSTANCE_ID:/workspace/results/done.json ./` to detect completion, pull results, verify them, then destroy.

### Timing notes

Measured across the 2026-06 Vast runs (RTX 3090/4090, ~6 GB images). Re-measure when the image or GPU tier changes.

- Healthy instance goes from "loading" to "running" in 90-180 seconds; treat >8 min as a dud host (see Dud-Host Failover)
- A CUDA framework install on top of the base image takes ~2-3 minutes
- Full SSH call (setup + nohup launch) takes ~5 minutes

</details>

## Data Transfer

<details>
<summary>Data Transfer</summary>

### Priority order for moving data

1. **`vastai copy`** - optimized for Vast.ai infra, resumable, handles auth
2. **rsync over SSH** - resumable, checksummed, good fallback
3. **`hf download`** - for model and dataset pulls specifically
4. **`vastai cloud copy`** - instance ↔ cloud connection, no laptop in the path
5. **scp** - simple but not resumable

### Model downloads on Vast.ai

HuggingFace downloads are often slow on Vast.ai due to shared IPs and rate limiting.

The CLI is `hf`, not `huggingface-cli`: `huggingface_hub` 1.x ships the `hf` binary and the old entry point is gone (local check 2026-08-09: `huggingface_hub` 1.8.0, `huggingface-cli` not on PATH).

```bash
export HF_TOKEN=<token>
hf download <repo_id>
```

Acceleration backend, verified locally 2026-08-09: `hf_xet` is installed, `hf_transfer` is not. The two are different backends and `HF_HUB_ENABLE_HF_TRANSFER=1` does nothing unless `hf_transfer` is present, so check what the box actually has before exporting anything:

```bash
hf version
python3 -c 'import hf_xet' 2>&1 | tail -1
python3 -c 'import hf_transfer' 2>&1 | tail -1
```

A Vast image ships whatever its build date gave it. Re-run this check on the box; do not carry an answer over from the laptop.

**Retry rule**: a large pull that times out once is usually a transient rate limit on the shared IP — retry once. If it fails twice, stop blaming the network and check disk space and token auth.

### Reusing models across instances

If one instance already has a model cached, transfer it rather than re-downloading:
```bash
# Instance-to-instance via vastai copy
vastai copy C.<src_id>:<model-cache>/models--<org>--<model>/ \
            C.<dst_id>:<model-cache>/

# Verify size after transfer
ssh -p <port> root@<host> 'du -sh <model-cache>/models--*/'
```

### Why SSH tar pipes fail on Vast.ai

Vast.ai proxies SSH connections. Large binary transfers via `tar cf - | ssh ... tar xf -` frequently fail silently due to:
- SSH proxy buffer limits causing backpressure
- `.bashrc` output on remote corrupting binary streams
- No error propagation through pipes

**Never use tar pipes for large transfers on Vast.ai.** Use `vastai copy` or rsync instead.

</details>

## Auto-Teardown

<details>
<summary>Auto-Teardown</summary>

### CRITICAL: Never self-destruct from the run script

**NEVER** put `vastai destroy` or `curl DELETE` in the remote run script. Data has been lost THREE times from premature self-destruct. The run script writes `done.json` and STOPS. Destruction happens from the watcher, AFTER the results are pulled and verified.

This is the same rule as the shared contract **Paid compute** ("data priority overrides every timer") and <notes-tree>/lore/references/compute-discipline.md's requirement that teardown fires only behind a hash-verified pull. One doctrine, stated here in Vast terms.

### Pattern: watcher-based auto-destroy

Auto-destroy lives in the watcher loop, never on the box. For any run over an hour the watcher belongs on the VPS, not the laptop — full contract in <notes-tree>/lore/references/compute-discipline.md "Laptop-Independent Completion Chains".

```bash
# In the watcher poll, after detecting the completion marker:
if [ "$ALL_DONE" = "true" ]; then
    vastai copy C.<id>:/workspace/results/ ./results/   # pull first
    verify_inventory ./results/ || exit 1               # hashes match, or keep the box alive
    echo y | vastai destroy instance <id>               # only now
fi
```

The order is the whole pattern: pull, verify, destroy. A hash mismatch keeps the hardware billing while you recover it by hand — that is the cheap outcome.

### Pattern: multi-instance completion markers

Wave runner scripts on the instance signal completion via marker files. The watcher waits for every marker before it tears anything down.

```bash
# On instance (end of wave script):
echo '{"status":"complete","timestamp":"'$(date -Iseconds)'"}' > /workspace/results/gpu1_wave2_complete.json

# In the watcher poll:
vastai copy C.<id>:/workspace/results/*complete*.json ./results/ 2>/dev/null
if [ -f ./results/gpu1_wave2_complete.json ] && [ -f ./results/gpu2_wave2_complete.json ]; then
    # pull + verify + destroy
fi
```

### What to pull before destroying

- Best checkpoint — can be large; check its size before pulling
- Training log and metrics JSON
- Exported artifacts (ONNX or equivalent)
- Every completion marker

Skip intermediate checkpoints, pip caches, and anything under `<ephemeral-cache>`. Write the run's hypothesis into your experiment log before the pull; the checkpoint does not record what you were testing.

### Billing safety rules

- Teardown fires on the first watcher poll after the verified pull. Worst-case billing overhang is one poll interval, so state the interval you set rather than a number carried from another run
- Always log destroy failures with "MANUAL CLEANUP NEEDED"
- After destroy, verify with `vastai show instances-v1` that the instance is gone
- Keep polling `vastai show instances-v1` after destroy to catch zombies

</details>

## Dud-Host Failover

<details>
<summary>Dud-Host Failover</summary>

Host quality at the cheap consumer-GPU tier is rough: in one 2026-06-10 run, 3 of 5 verified ≥0.98-reliability RTX 3090 offers were duds, each in a different way. Launch scripts must detect failure fast and rotate offers automatically instead of waiting on one host. Reference implementation: a GPU research project's `.local/phase1/launch.sh`.

### Read the fields that carry the failure signal

`vastai show instance <id> --raw` per poll; the three load-bearing fields:

| Field | Meaning |
|-------|---------|
| `actual_status` | What the instance is doing now. Stays `loading` forever on several failure modes; never watch it alone. |
| `intended_status` | What the scheduler wants. Flips to `stopped` when the host gives your GPU away mid-load (`vastai start` then returns "Required resources are currently unavailable, state change queued"). Unrecoverable until the other renter leaves: destroy and move on. |
| `status_msg` | Live Docker pull progress (`<layer>: Pull complete`, `Retrying in Ns`, …). Distinguishes "pulling, slow" from "frozen". |

### Failure taxonomy + budgets (all observed in production)

| Symptom | Diagnosis | Action |
|---------|-----------|--------|
| `loading` >8 min, `status_msg` stuck/retrying | Dead or rate-limited image pull (a ~6GB image pulls in <2 min on a healthy host) | Destroy, next offer |
| `intended_status` flips to `stopped` after create | Host double-booked the GPU | Destroy immediately, exclude the machine_id, next offer |
| `running` but SSH-proxy `Connection refused` >4 min | Container never actually came up | Destroy, next offer |
| sshd up but `Permission denied (publickey)` persists ~90s | Host-side key injection broken (`vastai attach ssh` says "already associated" yet auth still fails) | Try `vastai attach ssh <id> "$(cat <ssh-public-key>)"` once, retry ~90s with explicit `-i`; still denied → destroy, next offer |
| rsync `mkdir /workspace/... No such file or directory` | Some hosts lack `/workspace` at container start | `ssh ... 'mkdir -p /workspace/<dir>'` before rsync (NOT a dud host; do not destroy) |

### Failover loop shape

1. Search offers sorted by `dph`, filter `cuda_max_good >= <image CUDA>` (CLI create does NOT check driver compatibility), exclude machine_ids that burned you (`machine_id` is in both offer and instance records).
2. Per offer: create → poll every 15s with the budgets above → on failure destroy + continue to next offer; on success proceed to setup.
3. `ssh` calls inside a `while read` offer loop need `-n`, or they swallow the remaining offers from stdin and silently gut the failover.
4. Each properly-detected dud costs ≤8 min and ~$0.02; the failure mode worth engineering against is the silent hour-long wait.

</details>

## Gotchas

<details>
<summary>Gotchas</summary>

| Issue | Cause | Fix |
|-------|-------|-----|
| SSH timeout during transfer | Vast.ai proxy connection limits | Use `vastai copy` instead |
| HF download crawling | Rate limiting on shared Vast.ai IPs | Set `HF_TOKEN`, confirm the box's accel backend (`hf_xet` / `hf_transfer`), or transfer from another instance |
| tar pipe silent truncation | SSH proxy buffer overflow | Never use tar pipes; use `vastai copy` or rsync |
| Instance unreachable after create | SSH takes 30-60s to initialize | Retry with `ConnectTimeout=10`, wait 60s after create |
| Stuck in `loading` / flips to stopped / no sshd | Dud host (common at cheap tiers) | See Dud-Host Failover section: budgets + auto-rotate offers |
| `/workspace` missing at container start | Host/image variance | `mkdir -p` over SSH before any rsync into it |
| CUDA-incompatible host accepted at create | CLI create skips driver checks | Filter offers with `cuda_max_good >= <image CUDA version>` |
| Model cache location varies | Docker image differences | Check both `<model-cache>/` and `/workspace/.cache/` |
| Disk full mid-run | 40 GB disk, dataset + Arrow cache + checkpoints | `du -sh <model-cache>/*/`, drop unused models; still stuck → migrate to a 100 GB box |
| Run must move mid-epoch (throttling, disk, price) | Host-level problem, not a code problem | Interrupt, `vastai copy` the checkpoint dir out, destroy, create the replacement, copy the checkpoints back in, resume |
| Instance still billing after experiments | No watcher owns the teardown | Every paid launch names its watcher before it starts; see Auto-Teardown |

</details>
