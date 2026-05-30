<!-- keywords: free gpu, kaggle, lightning ai, modal, compute budget, free compute, gpu quota, serverless gpu -->
# Free Compute Catalog

Free GPU and CPU tiers across all major providers. No trials, no startup programs - only
genuinely free tiers that don't expire (or renew monthly/weekly). Updated 2026-03-27.

**Rule**: Any project that consumes free GPU quota (training, inference, benchmarks) MUST
log usage in `$KB_DIR/areas/infrastructure/compute-budget.md`. Format:
`| date | provider | gpu-hours used | remaining estimate | project | what ran |`
This keeps all instances aware of remaining capacity across projects.

## Quick Nav

| Task | Section |
|------|---------|
| Find best free GPU for training | GPU Notebook Platforms |
| Find free GPU for serverless/code deploys | Serverless GPU |
| Find free inference APIs | Inference-Only APIs |
| Find always-free persistent server | Always-Free CPU |
| Find cloud dev environment | Dev Environments |
| Check current capacity/usage | Capacity Tracking |
| Look up a specific provider | Provider Details |

## GPU Notebook Platforms

Best free GPU access. All provide Jupyter-style notebooks.

| Provider | GPU | VRAM | Limit | CC? | Link |
|----------|-----|------|-------|-----|------|
| Kaggle | T4 x2 or P100 | 32/16 GB | 30h GPU/week + 20h TPU/week | No (phone verify) | kaggle.com |
| Google Colab | T4 | 16 GB | Opaque, ~12h sessions, throttled | No | colab.research.google.com |
| Lightning AI | T4/L4/A10G | 16-24 GB | 22h GPU/month | No (phone verify) | lightning.ai |
| Paperspace Gradient | M4000 (reliable) | 8 GB | 6h sessions, 1 concurrent | No | paperspace.com/gradient |
| SageMaker Studio Lab | T4 | 16 GB | 4h GPU/day, 15 GB persistent | No (waitlist) | studiolab.sagemaker.aws |

<details>
<summary>Provider Details</summary>

### Kaggle Notebooks

Best raw GPU quota of any free tier. Dual T4 or P100, 30h/week GPU + 20h/week TPU.

- **CPU/RAM**: ~4 vCPU, 29-32 GB RAM
- **Storage**: 73 GB (20 GB dataset + 20 GB working + dataset access)
- **Session**: max 9h, background execution supported (browser can close)
- **Weekly reset**: 30 GPU-hours hard cap, resets weekly not monthly
- **TPU**: 20h/week TPU v3-8 (separate quota)
- **Requirements**: Google account + phone verification for GPU unlock
- **Gotcha**: Internet access must be enabled manually per notebook
- **URL**: kaggle.com/docs/efficient-gpu-usage

### Google Colab

Fastest to start, but unreliable allocation.

- **GPU**: T4 16 GB (not guaranteed; sometimes K80 during peak)
- **CPU/RAM**: ~2 vCPU, 12-13 GB RAM
- **Storage**: 100 GB temporary (wiped on session end)
- **Session**: max 12h, ~90 min idle timeout
- **Quota**: Opaque "compute unit" system. Heavy users throttled within a week. No published number
- **Concurrent**: up to 2 notebooks
- **Requirements**: Google account, no CC
- **Gotcha**: GPU availability degrades with heavy use. Peak hours may yield CPU-only
- **URL**: colab.research.google.com/signup

### Lightning AI Studios

Real VS Code IDE (not just Jupyter). 22h GPU/month shared across GPU types.

- **GPU options**: T4, L4 (24 GB), A10G (24 GB)
- **CPU**: 1 free 4-CPU studio (always available, no time limit)
- **GPU hours**: 22h/month shared across all GPU types
- **Storage**: 10 GB Drive storage
- **Requirements**: Account + phone verification for GPU hours, no CC
- **Gotcha**: 22h is shared - using A10G burns the same pool as T4
- **URL**: lightning.ai

### Paperspace Gradient (DigitalOcean)

Higher VRAM GPUs listed but rarely available on free tier.

- **Reliable GPU**: M4000 (8 GB VRAM)
- **Listed but rare**: A4000 (16 GB), A5000 (24 GB), A6000 (48 GB) - capacity-dependent
- **CPU/RAM**: 8 vCPU, 30 GB RAM minimum on all GPU instances
- **Storage**: 5 GB persistent, up to 5 projects
- **Session**: 6h max, can restart immediately
- **Concurrent**: 1 notebook
- **Requirements**: Paperspace account, no CC
- **Gotcha**: A4000+ frequently shows "no free instances available". M4000 is the realistic option
- **URL**: paperspace.com/gradient/free-gpu

### SageMaker Studio Lab

Only free tier with persistent storage (15 GB survives across sessions).

- **GPU**: T4 16 GB
- **CPU sessions**: 2 vCPU, 4 GB RAM, 12h max
- **GPU sessions**: 4 vCPU, 15 GB RAM, 4h max, 4 GPU-hours/24h hard cap
- **Storage**: 15 GB persistent filesystem
- **Requirements**: Separate from AWS account. No CC. Waitlist exists
- **Gotcha**: No AWS integration (can't access S3 etc.). Purely standalone
- **URL**: studiolab.sagemaker.aws

</details>

## Serverless GPU

Code-first platforms (not notebooks). Deploy real Python functions on GPUs.

| Provider | GPU Access | Free Quota | CC? | Link |
|----------|-----------|------------|-----|------|
| Modal | Any (A10G-H100) | $30/month credits | No | modal.com |
| HF Spaces ZeroGPU | H200 (70-141 GB) | 3.5 min/day | No | huggingface.co/docs/hub/spaces-zerogpu |

<details>
<summary>Provider Details</summary>

### Modal

$30/month in compute credits. Real serverless GPU - deploy Python functions, not notebooks.

- **GPU access**: Credits apply to any GPU: A10G (~$1.10/h = ~27h), A100 (~$3.73/h = ~8h), H100 (~$10/h = ~3h)
- **Concurrency**: 100 containers, 10 GPU concurrency on free tier
- **Log retention**: 1 day only on free tier
- **Requirements**: GitHub/Google account, no CC
- **Best for**: Inference endpoints, scheduled batch jobs, anything requiring real code deployment
- **URL**: modal.com/pricing

### Hugging Face Spaces ZeroGPU

Massive VRAM but tiny daily quota. Inference demos only.

- **GPU**: Half H200 (70 GB VRAM) or full H200 (141 GB VRAM)
- **Free quota**: 3.5 minutes GPU time/day (rolling 24h window)
- **CPU Basic (free hosting)**: 2 vCPU, 16 GB RAM, 50 GB disk - sleeps after ~2 days
- **Requirements**: Free HF account, no CC
- **Gotcha**: Gradio SDK only (no Streamlit). 3.5 min/day is a few inference calls, not training
- **URL**: huggingface.co/docs/hub/en/spaces-zerogpu

</details>

## Inference-Only APIs

Not raw compute - just API endpoints for running models. No training.

| Provider | Limit | Speed | Link |
|----------|-------|-------|------|
| Cerebras API | 1M tokens/day | ~1000+ tok/s | cerebras.ai |
| Cloudflare Workers AI | 10K neurons/day | Edge latency | developers.cloudflare.com/workers-ai |

<details>
<summary>Provider Details</summary>

### Cerebras API
- 1M tokens/day free, no sign-up fee, API key only
- Very fast inference (~1000+ tok/s on supported models)
- Now Nvidia-owned (acquired early 2026)
- Model selection limited to Cerebras-optimized models

### Cloudflare Workers AI
- 10K neurons/day bundled with Workers free tier
- Curated open models (Llama, Mistral, etc.) at Cloudflare edge
- Inference API only - no custom training or model hosting
- Per-account limit

</details>

## Always-Free CPU

Persistent servers that don't expire. No GPU.

| Provider | Specs | CC? | Link |
|----------|-------|-----|------|
| Oracle Cloud ARM | 4 OCPU, 24 GB RAM, 200 GB disk | Yes (verify) | cloud.oracle.com/free |
| Google Cloud e2-micro | 2 vCPU burst, 1 GB RAM, 30 GB disk | Yes (verify) | cloud.google.com/free |

<details>
<summary>Provider Details</summary>

### Oracle Cloud Always Free (ARM)

Best free CPU tier available. 4 ARM cores, 24 GB RAM - enough for llama.cpp inference.

- **Compute**: VM.Ampere.A1.Flex - up to 4 OCPU + 24 GB RAM, split across up to 4 instances
- **Storage**: 200 GB block storage, 2 object storage buckets (20 GB each)
- **Network**: 10 TB/month outbound
- **Architecture**: ARM (not x86) - most ML frameworks work, some libraries need ARM builds
- **Requirements**: CC for identity verification (not charged)
- **Gotcha**: ARM Ampere capacity frequently exhausted in popular regions. Provisioning often fails with "out of capacity". Try less popular regions
- **URL**: docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

### Google Cloud e2-micro

Tiny but always-on. US regions only.

- **Compute**: 1x e2-micro (2 vCPU burst, 1 GB RAM)
- **Storage**: 30 GB standard persistent disk, 5 GB snapshot
- **Network**: 1 GB outbound/month
- **Region**: US only (Oregon, Iowa, South Carolina)
- **Requirements**: CC for verification
- **Gotcha**: 1 GB RAM too small for any ML work. Good for lightweight APIs or cron jobs only
- **URL**: cloud.google.com/free/docs/free-cloud-features

</details>

## Dev Environments

Cloud IDEs with free CPU compute. No GPU.

| Provider | Free Limit | RAM | CC? | Link |
|----------|-----------|-----|-----|------|
| GitHub Codespaces | 120 core-hours/mo (60h on 2-core) | 8 GB+ | No | github.com/features/codespaces |
| Gitpod/Ona | 50h/month | Varies | No | gitpod.io |
| Replit | 20h/month dev time | 512 MB | No | replit.com |

## Dead/Removed Free Tiers

Don't waste time on these - they no longer have free compute:

- **Fly.io** - free tier removed for new users (2024)
- **Intel Developer Cloud** - free Gaudi access discontinued post-beta
- **Lambda Cloud** - paid only (research grant up to $5K for academics)
- **RunPod** - paid only
- **Vast.ai** - paid only (startup program $2,500 for qualifying startups)
- **Railway** - $5 one-time trial + $1/month after (not meaningfully free)

## Research/Academic Programs

Not recurring free tiers but worth noting for qualifying work:

- **Google TPU Research Cloud** - free TPU clusters (v2/v3/v4), must publish results. Apply: sites.research.google/trc
- **Azure for Students** - $100 credit, 12 months, .edu email, no CC
- **Lambda Research Grant** - up to $5,000 GPU credits, academic only

## Capacity Tracking

**Rule**: Before consuming free GPU hours on any provider, check and update
`$KB_DIR/areas/infrastructure/compute-budget.md`. This prevents multiple Claude Code
instances from unknowingly burning the same weekly/monthly quota.

<details>
<summary>Capacity Tracking</summary>

### Self-Healing Reset Protocol

The tracking file is self-healing - no cron job or external process needed. Each provider
section has a `period_start` date and a `reset` interval. Any instance that reads the
file is responsible for resetting stale periods.

**Before consuming GPU time:**
1. Read `$KB_DIR/areas/infrastructure/compute-budget.md`
2. For the provider you're about to use, check if `period_start` is stale:
   - `weekly`: period_start is 7+ days ago
   - `monthly`: period_start is in a previous calendar month
   - `daily`: period_start is not today's date
3. If stale: move current-period rows to `### History`, reset `period_start` to today,
   set `used` to `0`
4. If remaining quota is insufficient, pick a different provider or warn the user
5. Add your row with estimated duration BEFORE starting the job
6. After the job completes, update your row with actual duration

**After consuming GPU time:**
- Update the `Used this period` total
- Correct your row's duration if the estimate was off

### Tracked Providers (hard caps)

| Provider | Quota | Reset | Why Track |
|----------|-------|-------|-----------|
| Kaggle | 30h GPU/week | Weekly | Hard cap, best free GPU |
| Lightning AI | 22h GPU/month | Monthly | Hard cap |
| Modal | $30/month | Monthly | Credit-based, shared across GPU types |
| SageMaker Studio Lab | 4h GPU/day | Daily | Tight daily cap |
| HF ZeroGPU | 3.5 min/day | Daily | Very small daily cap |

### NOT Tracked (no actionable cap)

- **Google Colab** - opaque throttling, no published number to track against
- **Paperspace Gradient** - session-limited (6h max), not quota-limited

</details>

## Vast.ai Setup (Configured)

API key stored at `~/.config/vastai/vast_api_key` (also set in vastai CLI via `vastai set api-key`).
SSH key registered on account (key ID 727695, ed25519 from `~/.ssh/`).
CLI installed via `uv tool install vastai`. Account credit: $7.41 as of 2026-04-01.

```bash
# Search for cheap GPU offers
vastai search offers 'gpu_name=RTX_4090 num_gpus=1' --order dph_total
vastai search offers 'gpu_name=A10G num_gpus=1' --order dph_total

# Launch an instance (returns instance ID)
vastai create instance <OFFER_ID> --image pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime --disk 20

# SSH into it
vastai ssh-url <INSTANCE_ID>  # prints ssh command
ssh -p <PORT> root@<HOST>

# Destroy when done
vastai destroy instance <INSTANCE_ID>
```

**For training jobs**: search offers → create instance → scp notebook → run → scp results back → destroy.
No MCP, no browser. Full CLI control.

## Recommendations by Use Case

| Use Case | First Choice | Fallback |
|----------|-------------|----------|
| Training runs (< 9h) | Kaggle (30h/week, dual T4) | Lightning AI (22h/month, A10G) |
| Quick experiments | Google Colab (fastest start) | Kaggle |
| Persistent dev environment | SageMaker Studio Lab (15 GB persist) | GitHub Codespaces (CPU only) |
| Serverless GPU functions | Modal ($30/month) | - |
| Inference demos | HF ZeroGPU (H200 access) | Cerebras API (1M tok/day) |
| Large model inference (CPU) | Oracle Cloud ARM (24 GB RAM) | - |
| Persistent free server | Oracle Cloud ARM | Google Cloud e2-micro |
| High-VRAM experiments | Paperspace (A6000 48 GB if available) | HF ZeroGPU (141 GB, 3.5 min/day) |

---

*Last verified: 2026-03-27. Review quarterly - free tiers change often.*
