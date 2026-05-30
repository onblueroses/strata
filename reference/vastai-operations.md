<!-- keywords: vastai, vast.ai, gpu instance, gpu rental, vastai cli, instance launch, vast instance -->
# Vast.ai Operations

Quick reference for Vast.ai GPU instance management. CLI is the primary interface.

**Read this doc when**: spinning up any GPU instance on Vast.ai, launching overnight experiments, running GPU training, or doing data transfer between instances.

## Quick Nav

| Section | Jump to |
|---------|---------|
| CLI Basics | Instance lifecycle, listing, labels |
| Single SSH Launch | Full setup + launch + teardown in one SSH call |
| Data Transfer | `vastai copy`, model caching, HF downloads |
| Auto-Teardown | Patterns for automatic instance destruction |
| Gotchas | SSH proxy limits, model downloads, billing |

> **Local scripts rule**: Launch scripts, teardown scripts, .env files, and anything with API keys must go in `.local/` within the repo (globally gitignored). Never commit provider-specific scripts to tracked directories.

---

## CLI Basics

<details>
<summary>CLI Basics</summary>

The `vastai` CLI is installed at `~/.local/bin/vastai`. Always use it over raw SSH for instance management.

```bash
# List running instances
vastai show instances

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

### Labels

Always label instances for identification:
```bash
vastai label instance <id> "project-name-gpu1"
```

</details>

## Single SSH Launch

<details>
<summary>Single SSH Launch</summary>

The preferred pattern for GPU experiments. One SSH call does: full setup, nohup launch, self-destruct on completion. No polling, no repeated SSH.

### Why not multiple SSH calls?

Vast.ai proxies SSH. Multiple calls are fragile - connection drops during setup leave the instance in an unknown state. One call that sets up and returns is reliable.

### Why not `vastai execute`?

`vastai execute` only supports `ls`, `rm`, `du`. Not useful for running experiments.

### Pattern

**1. Write a launch script locally** (keep it in `remote/launch-remote.sh`):

```bash
#!/usr/bin/env bash
# Expects VAST_API_KEY and VAST_INSTANCE_ID to be set in environment.
set -euo pipefail

# Setup
pip install --quiet "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
git clone https://github.com/youruser/your-repo.git /workspace/repo
pip install --quiet -e /workspace/repo

# Verify GPU
python3 -c "import jax; d=jax.devices(); assert d[0].platform=='gpu'; print('GPU OK:', d)"

# Write run-teardown wrapper with creds baked in (uses heredoc substitution)
cat > /workspace/run-teardown.sh << EOF
#!/usr/bin/env bash
cd /workspace/results
python3 -m your.module ... >> /workspace/run.log 2>&1
echo '{"status":"complete"}' > /workspace/results/done.json
curl -s -X DELETE "https://console.vast.ai/api/v0/instances/${VAST_INSTANCE_ID}/?api_key=${VAST_API_KEY}" \
  || echo "WARNING: destroy failed" >> /workspace/run.log
EOF

chmod +x /workspace/run-teardown.sh
mkdir -p /workspace/results
nohup bash /workspace/run-teardown.sh </dev/null >> /workspace/run.log 2>&1 &
echo "PID: $! - SSH session done, experiment running"
```

Key points:
- Outer script uses `set -euo pipefail` so any setup error aborts immediately
- `${VAST_API_KEY}` and `${VAST_INSTANCE_ID}` in the heredoc are substituted by the outer shell when writing the inner script
- Inner script (run-teardown.sh) uses `\$EXIT` etc. - escaped so they evaluate at runtime
- `nohup ... </dev/null ... &` detaches completely from the SSH session

**2. Create the instance** (--ssh flag required for SSH access):

```bash
OFFER_ID=$(vastai search offers 'gpu_name=RTX_4090 num_gpus=1 disk_space>=30 inet_up>=100' \
  --order dph_base --limit 1 --raw | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
vastai create instance $OFFER_ID \
  --image vastai/pytorch:2.2.0-cuda12.1-py311 \
  --disk 50 --label "my-experiment" --ssh
# Note the instance ID from the JSON response
```

**3. Wait for the instance to be running**:

```bash
for i in $(seq 1 12); do
  STATUS=$(vastai show instance $INSTANCE_ID --raw | python3 -c "import json,sys; print(json.load(sys.stdin).get('actual_status','?'))")
  echo "[$i] $STATUS"
  [ "$STATUS" = "running" ] && break
  sleep 30
done
```

**4. Get the SSH URL and fire one SSH call**:

```bash
SSH_URL=$(vastai ssh-url $INSTANCE_ID)
# SSH_URL format: ssh://root@ssh6.vast.ai:12345
HOST=$(echo $SSH_URL | sed 's|ssh://root@||' | cut -d: -f1)
PORT=$(echo $SSH_URL | cut -d: -f3)
VAST_API_KEY=$(cat ~/.config/vastai/vast_api_key)

ssh -o StrictHostKeyChecking=no -p $PORT root@$HOST \
  "export VAST_API_KEY=$VAST_API_KEY VAST_INSTANCE_ID=$INSTANCE_ID && bash -s" \
  < remote/launch-remote.sh
```

The SSH call returns once setup is done and nohup is launched. The experiment runs in the background. The instance self-destructs when done.

**5. Set up local cron as backup** (in case self-destruct fails):

```bash
chmod +x remote/monitor-7k.sh
(crontab -l 2>/dev/null; echo "*/10 * * * * /path/to/monitor-7k.sh >> /path/to/monitor.log 2>&1") | crontab -
```

The monitor uses `vastai copy C.$INSTANCE_ID:/workspace/results/done.json ./` to check for completion, then copies results and destroys.

### Timing notes

- Instance goes from "loading" to "running" in 90-180 seconds
- pip install JAX takes ~2-3 minutes
- Full SSH call (setup + nohup launch) takes ~5 minutes

</details>

## Data Transfer

<details>
<summary>Data Transfer</summary>

### Priority order for moving data between instances

1. **`vastai copy`** - optimized for Vast.ai infra, resumable, handles auth
2. **rsync over SSH** - resumable, checksummed, good fallback
3. **HuggingFace CLI with `hf_transfer`** - for model downloads specifically
4. **scp** - simple but not resumable

### Model downloads on Vast.ai

HuggingFace downloads are often slow on Vast.ai due to shared IPs and rate limiting. Mitigations:

```bash
# Install fast Rust-based downloader
pip install hf_transfer

# Set environment for fast downloads
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_TOKEN=<token>

# Download with huggingface-cli (preferred over Python API)
huggingface-cli download <repo_id>
```

### Reusing models across instances

If one instance already has a model cached, transfer it rather than re-downloading:
```bash
# Instance-to-instance via vastai copy
vastai copy C.<src_id>:/root/.cache/huggingface/hub/models--<org>--<model>/ \
            C.<dst_id>:/root/.cache/huggingface/hub/

# Verify size after transfer
ssh -p <port> root@<host> 'du -sh /root/.cache/huggingface/hub/models--*/'
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

**NEVER** put `vastai destroy` or `curl DELETE` in the remote run script. Data has been lost THREE times from premature self-destruct. The run script writes `done.json` and STOPS. Destruction happens locally AFTER syncing results.

### Pattern: cron-based auto-destroy

When running overnight or unattended experiments, always build auto-destroy into the LOCAL monitoring loop (never the remote script):

```bash
# In cron check script, after detecting completion:
if [ "$ALL_DONE" = "true" ]; then
    # Final sync first
    vastai copy C.<id>:/workspace/results/ ./results/

    # Then destroy
    vastai destroy instance <id1>
    vastai destroy instance <id2>
fi
```

### Pattern: self-terminating wave scripts

Wave runner scripts on the instance can signal completion via marker files. The local cron job watches for these markers and triggers cleanup.

```bash
# On instance (end of wave script):
echo '{"status":"complete","timestamp":"'$(date -Iseconds)'"}' > /workspace/results/gpu1_wave2_complete.json

# Locally (cron job checks):
vastai copy C.<id>:/workspace/results/*complete*.json ./results/ 2>/dev/null
if [ -f ./results/gpu1_wave2_complete.json ] && [ -f ./results/gpu2_wave2_complete.json ]; then
    # sync + destroy
fi
```

### Billing safety rules

- Max 12-minute delay between completion and teardown (cron interval)
- Always log destroy failures with "MANUAL CLEANUP NEEDED" message
- After destroy, verify with `vastai show instances` that instances are gone
- Keep `vastai show instances` in cron even after destroy to catch zombies

</details>

## Gotchas

<details>
<summary>Gotchas</summary>

| Issue | Cause | Fix |
|-------|-------|-----|
| SSH timeout during transfer | Vast.ai proxy connection limits | Use `vastai copy` instead |
| HF download crawling | Rate limiting on shared Vast.ai IPs | Use `hf_transfer` + auth token, or transfer from another instance |
| tar pipe silent truncation | SSH proxy buffer overflow | Never use tar pipes; use `vastai copy` or rsync |
| Instance unreachable after create | SSH takes 30-60s to initialize | Retry with `ConnectTimeout=10`, wait 60s after create |
| Model cache location varies | Docker image differences | Check both `/root/.cache/huggingface/` and `/workspace/.cache/` |
| Instance still billing after experiments | No auto-teardown set up | Always build `vastai destroy` into completion flow |

</details>
