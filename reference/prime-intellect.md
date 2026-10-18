<!-- keywords: prime intellect, primeintellect, prime cli, prime-rl, verifiers, environments hub, lab, intellect-1, intellect-2, intellect-3, opendiloco, toploc, shardcast, rl training, agentic rl, lora, rubric reward, rl environment, cluster, fine-tune, finetune, training run, reward model, hosted training, rl run, gpu cluster -->
# Prime Intellect

ML / RL training stack: open-source frameworks (`verifiers`, `prime-rl`), an environments registry, a hosted training platform (Lab), a GPU compute exchange, and open-weight reasoning models (INTELLECT-1/2/3).

## Quick Nav

| Section | When to read |
|---------|--------------|
| [Account State](#account-state) | Confirm whose account / team / wallet you're operating as |
| [Mental Model](#mental-model) | Decide whether PI applies to a given task |
| [The Five Layers](#the-five-layers) | Pick which layer fits the work |
| [CLI Surface](#cli-surface) | Run prime commands |
| [URLs](#urls) | Open dashboards, docs, repos |
| [Pricing Snapshot](#pricing-snapshot) | Cost-check before launching |
| [Gotchas](#gotchas) | Avoid known footguns |
| [Project Mapping](#project-mapping) | Map PI to task types |
| [Integration Recipes](#integration-recipes) | Common task-shaped workflows |

## Account State

Before any operation, run `prime --plain whoami`, `prime --plain teams list`, and `prime --plain wallet`. Confirm the intended account and team; never infer current wallet balance from this page. CLI 0.6.1 was checked on 2026-08-09, but the surface changes: inspect `prime --help` after upgrades. Environment packages publish under `<team-slug>/<env>` for a team account. `prime switch <team-slug>` selects the active namespace. The token had full read/write scopes and billing read-only; verify the current scopes before use.

## Mental Model

Prime Intellect is, at its core, an **RL fine-tuning company**. The flagship workflow is:

> Open base model → verifiable reward → RL → better model on that task.

Decentralized training is research aesthetic, not the product. INTELLECT-3, their flagship open-weight reasoning model, was trained centrally on 512×H200. The product surface that matters is post-training.

**Use PI when** the task has a verifiable reward signal (bits recovered, answer matches, code compiles, multi-turn objective achieved).
**Don't reach for PI when** the work is supervised-only, exploratory research, or has no reward to score against.

<details>
<summary>Comparison to alternatives (~30 lines)</summary>

| Need | PI offering | Alternative |
|------|-------------|-------------|
| Cheapest raw GPU | Compute exchange ($3.29+/hr H100, measured 2026-08-11) | **Vast.ai** wins on raw $/hr |
| RL framework | `prime-rl` | TRL (general, messy multi-turn), OpenRLHF (pretraining-flavored) |
| Env abstraction | `verifiers` library | DIY harness; nothing equivalent in cleanliness right now |
| Env registry | Environments Hub | None at this scale |
| Hosted RL training | Lab | DIY on Modal/Runpod/Vast |
| Reasoning base model | INTELLECT-3 (106B MoE) | open-weight reasoning models from the Qwen / GLM / DeepSeek lines — generations turn over fast, resolve current names at read time |

**Where PI is genuinely differentiated**: `verifiers` + `prime-rl` is the cleanest agentic-RL abstraction in OSS. The Hub can publish an environment and run distributed evaluation. Lab eats the cluster-management tax for RL-LoRA workflows.

**Where it's not**: GPU pricing, base-model training (use real clusters), supervised fine-tuning (not the focus).

</details>

## The Five Layers

### 1. Compute Exchange

GPU broker aggregating providers (Vast, Lambda, Akash, io.net) under one CLI. On-demand and spot both available where inventory supports (verify with `prime availability list`). Pricing competitive but not lowest. Value is integration with Lab/prime-rl, not the rate.

### 2. `verifiers` (open-source library)

[github.com/PrimeIntellect-ai/verifiers](https://github.com/PrimeIntellect-ai/verifiers). Defines an RL environment as `(dataset, harness, async rubric)`. Reward functions are `async def`, return floats in `[0, 1]`, can be weighted/composed.

**Target v1 for anything new.** Upstream `docs/overview.md` states plainly: v1 (`verifiers.v1`, built
around tasksets, harnesses, and traces) "is what new environments should target", while v0
(`import verifiers as vf`) "is considered deprecated and will be fully removed in a future release."
The example below is **v0** and is kept only for reading existing envs; write new ones against
`docs/v1/overview.md`. `prime-rl` configs have moved with it — current configs reference
`env.taskset.id`, not `load_environment`.

<details>
<summary>Minimal env example (v0 — deprecated, for reading old envs)</summary>

```python
import verifiers as vf

def load_environment(dataset_name: str = "gsm8k") -> vf.Environment:
    dataset = vf.load_example_dataset(dataset_name)

    async def correct_answer(completion, answer) -> float:
        return 1.0 if completion[-1]["content"] == answer else 0.0

    rubric = vf.Rubric(funcs=[correct_answer])
    return vf.SingleTurnEnv(dataset=dataset, rubric=rubric)
```

Multi-criteria rubric:

```python
@vf.reward(weight=1.0)
async def exact_match(task, state) -> float: ...

@vf.reward(weight=0.2)
async def valid_xml(task, state) -> float: ...
```

`load_environment` is the contract `prime-rl` consumes.

</details>

### 3. `prime-rl` (open-source framework)

[github.com/PrimeIntellect-ai/prime-rl](https://github.com/PrimeIntellect-ai/prime-rl). Async RL trainer. FSDP2 trainer + vLLM inference server, **min 2 GPUs for RL** (1 GPU SFT). Scales to 1000+ GPUs. MoE via expert parallelism. Self-contained — runs on any GPU pool.

Configs: three TOMLs — `train.toml`, `orch.toml`, `inference.toml`. Launch: `uv run rl --trainer @train.toml --orchestrator @orch.toml`. Multi-node needs **shared filesystem** (no built-in DFS).

When using PI compute, select the **"Prime RL (RFT)"** image — preloaded with CUDA + prime-rl + verifiers + prime CLI.

### 4. Environments Hub

[app.primeintellect.ai/dashboard/environments](https://app.primeintellect.ai/dashboard/environments). Package registry for `verifiers` envs; get the live count and roster with `prime --plain env list`. Envs are Python wheels.

```bash
prime env list --plain                       # browse hub
prime env info <owner>/<name>                # details
prime env install <owner>/<name>             # consume
prime env init my-env                        # scaffold local
prime env push --visibility PUBLIC                    # publish (auth required)
prime fork <owner>/<name>                    # fork into your namespace
```

**Why publish**: public distribution and evaluation against community models. Publication requires the operator's authorization.

### 5. Lab (hosted training, launched 2026-02-10)

Managed RL training. Define training as TOML, push, get dashboard with reward curves + rubric scores + rollout replay. Orchestrator handles GPU allocation, rollout workers, multi-tenant LoRA serving.

**Training mode**: agentic RL with LoRA adapters.

**Shipped surface** (CLI v0.6.1, checked 2026-08-09): `lab`, `env`, `eval`, `gepa`, `train`, `fork`, `deployments`. GEPA prompt optimization is a top-level command, not a roadmap item. The roadmap moves faster than this file — re-derive the split from `prime lab --help`, `prime train --help`, and `prime --plain train configs` rather than trusting a written roster.

**Billing**: token-based (input/output/training-token rates per model size), not hourly. Bounded cost = bounded tokens.

**Models available**: enumerate with `prime --plain train models`; per-size pricing lives at the models-and-pricing URL in [§URLs](#urls).

### Plus: INTELLECT models + protocol primitives

Open-weight reasoning models on HuggingFace: INTELLECT-1 (10B, decentralized PoC), INTELLECT-2 (32B QwQ-based), **INTELLECT-3 (106B MoE on GLM-4.5-Air)**, INTELLECT-3.1 (continued-training successor to INTELLECT-3). Check HuggingFace for the current head of the line before picking one.

Decentralized training primitives, with their state checked 2026-08-11:

- **TOPLOC** (verifies untrusted rollouts via locality-sensitive hashing) — live, standalone.
- **OpenDiLoCo** (DiLoCo impl, ~500× less inter-node bandwidth) — **unmaintained.** Its README says so
  outright and redirects to [`prime`](https://github.com/PrimeIntellect-ai/prime). Read it as a paper
  artifact, not a dependency.
- **SHARDCAST** (HTTP-tree weight broadcast) — **no standalone repo.** Absent from all repos in the
  PrimeIntellect-ai org; the only surviving code is `shardcast_downloader.py` inside `toploc-validator`.

Third-party compute contribution was unavailable as of 2026-05; recheck current offerings.

## CLI Surface

List-style queries take `--output json` and pipe to `jq`; `--help` prints the JSON schema for any list command. Every other invocation takes `--plain`, the CLI's standing instruction to AI agents; without it, output arrives as boxed tables.

<details>
<summary>Top-level commands</summary>

**Lab / training**: `lab`, `env`, `eval`, `train`, `gepa`, `fork`, `deployments`
**Account**: `whoami`, `login`, `switch`, `wallet`, `teams`, `config`, `secret`, `upgrade`, `feedback`
**Compute**: `availability`, `pods`, `disks`, `sandbox`, `images`, `registry`, `tunnel` (`inference` exists but is prohibited by the shared contract)

</details>

<details>
<summary>Common workflows</summary>

```bash
# Auth
prime login
prime --plain whoami
prime --plain teams list
prime switch <team-slug>
prime --plain wallet

# Browse
prime --plain availability list
prime --plain availability list --gpu-type H100_80GB
prime --plain env list
prime --plain env info <owner>/<name>

# Pods (paid)
prime --plain pods list
prime pods create --id <provider-id> --name <name> --disks <disk-id>
prime pods ssh <pod-id>
prime pods terminate <pod-id>

# Disks (paid, persistent, immutable size, billed continuously)
prime --plain disks list
prime disks create --id <provider-id> --size 500 --name <name>
prime disks terminate <disk-id>      # PERMANENT, no recovery

# Environments
prime env init my-env
prime env push --visibility PUBLIC
prime env install <owner>/<name>

# Hosted training (Lab)
prime lab setup
prime train configs/rl/<name>.toml
```

</details>

## URLs

| What | URL |
|------|-----|
| Marketing site | https://www.primeintellect.ai |
| App / dashboard | https://app.primeintellect.ai |
| Docs | https://docs.primeintellect.ai |
| LLM-friendly doc index | https://docs.primeintellect.ai/llms.txt |
| API reference intro | https://docs.primeintellect.ai/api-reference/introduction |
| Hosted training docs | https://docs.primeintellect.ai/hosted-training/getting-started |
| Models & pricing | https://docs.primeintellect.ai/hosted-training/models-and-pricing |
| GitHub org | https://github.com/PrimeIntellect-ai |
| `prime` CLI repo | https://github.com/PrimeIntellect-ai/prime |
| `prime-rl` | https://github.com/PrimeIntellect-ai/prime-rl |
| `verifiers` | https://github.com/PrimeIntellect-ai/verifiers |
| `OpenDiLoCo` | https://github.com/PrimeIntellect-ai/OpenDiloco |
| Environments Hub UI | https://app.primeintellect.ai/dashboard/environments |
| INTELLECT-3 weights | https://huggingface.co/PrimeIntellect/INTELLECT-3 |
| INTELLECT-2 paper | https://arxiv.org/abs/2505.07291 |
| Lab launch post | https://www.primeintellect.ai/blog/lab |
| Compute launch post | https://www.primeintellect.ai/blog/compute |
| Environments Hub blog | https://www.primeintellect.ai/blog/environments |
| `prime` on PyPI | https://pypi.org/project/prime |

## Pricing Snapshot

**Measure before every spend; this table is a shape, not a quote.** The 2026-05-07 version of it
was off by 2x within three months — it read "~$1.65/hr H100" when the cheapest live H100 was $3.29.

```bash
prime availability list --gpu-type H100_80GB --output json   # GPU $/hr, live inventory
prime --plain train models                                   # the models Lab actually offers
```

Measured 2026-08-11 (re-run the commands above rather than trusting these):

| Resource | Cost |
|----------|------|
| H100 80GB | $3.29–4.29/hr on-demand, 1x; $31.92/hr for 8x. 4 configs listed, all lambdalabs |
| A100 80GB | $1.20–1.79/hr on-demand |
| RTX 4090 | **No inventory** — the GPU type returns zero offers, so it has no price |
| Spot | available on supported inventory (`prime availability list`) |
| Disk storage | per-unit, billed continuously, not resizable |
| Lab training (small 0.8B–3B) | $0.02–0.05/1M input, $0.06–0.15/1M output, same for training tokens |
| Lab training (mid 9B–35B) | $0.20–0.25/1M input, $0.60–0.75/1M output |
| Free tier | none documented (event-based credits exist) |

The Lab catalog tops out at **35B-A3B**. A prior row here priced a "large 122B–397B MoE" tier that
the platform does not offer at any size; do not plan around it. **Historical inference evidence (2026-08-11):** INTELLECT-3 was absent from the catalog and an attempted chat returned HTTP 404 `model_not_found`. This is not an authorized route.

Vast.ai still wins raw $/hr. Don't move bulk compute off Vast for cost reasons.

## Gotchas

- **Disks immutable**: size cannot be changed after creation. Plan ahead. Termination permanent, no recovery.
- **Disks bill continuously** even when no pod is attached. Terminate when done.
- **Multi-node needs shared FS**: no built-in DFS. Provision shared volume or use Kubernetes with appropriate storage class.
- **RL minimum 2 GPUs** (trainer + inference are separate processes). SFT works on 1.
- **Async reward functions required**: `verifiers` rubric funcs must be `async def`, return floats in [0, 1].
- **Flash Attention required for prime-rl**: H100 uses FA3, validation checklist calls this out.
- **No native cost alerts in UI**. Spend audit runs on `prime --plain wallet` plus the `<notes-tree>/areas/infrastructure/compute-budget.md` log; W&B covers run-level monitoring. Nothing pages you — lifecycle discipline is manual.
- **No native code-sync** (no rsync/watch tool). Code lives in env packages on the Hub. Iterate locally with `uv run vf-eval`, push when ready.
- **GPU availability is exchange-based**: H100 supply varies. Check `prime availability list` before planning runs.
- **Lab is young** (launched 2026-02-10; 2026-05-07 is an account creation date, which an earlier note confused with the launch) and still moving. `prime deployments` self-describes as experimental. Read `prime lab --help` for the current command set instead of trusting any written roster, this one included.
- **Decentralized framing is partly aspirational**. INTELLECT-3 was centrally trained. Don't pitch external work as "decentralized via PI" without checking.
- **Teardown wires in at launch**, not after — `<notes-tree>/lore/references/compute-discipline.md` §Paid Compute Cleanup owns the rule. The PI-specific part: teardown covers two objects, the pod and its disk, because the disk keeps billing alone.

## Project Mapping

These are fit criteria, not a shortlist. Enumerate the current entity set with `<notes-tree>/areas/agent-setup/state/optmem/cross-entity-discovery.md`, then score each entity against the three bands. A written roster of project names rots faster than the criteria do.

**Native fit (RL-shaped, rubric-shaped)**: the objective carries a verifiable reward — an encode/decode round-trip that either recovers the payload or does not, an answer that matches, code that compiles, a multi-turn goal that completes. Multi-agent objectives land here too. These are the Hub publication candidates.

**Tangential fit (use the framework, not the cloud)**: research ML with no reward to optimize against. `verifiers` can still structure rubric evals outside RL, and the INTELLECT models serve as reference architectures for MoE work.

**No fit**: web, content and lead-gen work; anything supervised-only or purely exploratory.

## Integration Recipes

### A. Hub-only (zero spend, half day)

Wrap an existing rubric-shaped task with `verifiers`, push to Hub, claim namespace. Eligible for public evaluation.

```bash
prime env init <name>
# edit ./environments/<name>/, write load_environment + rubric
uv run vf-eval                    # local sanity check, no API key needed
prime env push --visibility PUBLIC
```

### B. Local prime-rl on existing compute (zero PI spend, ~1 day)

Use `prime-rl` standalone on Vast or Lambda. No PI cloud commitment, get the framework benefit. An older local host was offline for 13 days as of 2026-08-09; check `tailscale status` before planning around it.

```bash
git clone https://github.com/PrimeIntellect-ai/prime-rl
cd prime-rl && uv sync --all-extras
# follow validation sequence: SFT debug → RL debug → toy reverse_text run
```

### C. Hosted Lab run (bounded token cost, ~1 day)

End-to-end LoRA fine-tune via Lab against a small base (Qwen3.5-3B). Token-priced, bounded.

```bash
prime lab setup
# write train.toml, orch.toml, inference.toml referencing your env
prime train configs/rl/<name>.toml
```

### D. Prime Inference boundary

The shared contract prohibits Prime Inference and all `prime-inference/*` selectors. Do not launch or use that API. Historical availability evidence from 2026-08-11: INTELLECT-3 returned HTTP 404 `model_not_found` and was absent from the catalog. Use an authorized subscription-backed provider for inference. The open weights may be evaluated on authorized local or rented compute.

## Training pod protocol

Project-neutral training-pod discipline. Data always takes priority over teardown; the shared contract Constraints keep only the one-line data-priority invariant and point here.

- **Launch protocol**: DATA ALWAYS TAKES PRIORITY; pod termination is blocked until `PULL_DONE` exists, and no timer, wallet check, or runtime override may kill the pod first.
- **Watcher**: always start the auto-finish watcher (`nohup bash <pod-dir>/auto-finish.sh > /tmp/auto-finish-<label>.out 2>&1 &`) immediately after any pod launch path returns (launch scripts do not start it), then verify `auto-finish.log` appears within ~30s.
- **Wallet**: never set `WALLET_FLOOR_USD` to a non-zero value; the operator manages cost.

## Cross-References

- `<notes-tree>/areas/infrastructure/free-compute-catalog.md` — broader compute landscape
- [vastai-operations.md](vastai-operations.md) — Vast.ai (still preferred for raw GPU)
- `<notes-tree>/lore/references/compute-discipline.md` — teardown, saturation, dry-run gates
- `<notes-tree>/areas/infrastructure/gpu-training-workflow.md` — generic GPU training discipline (archived)
- the local credentials map — where the PI API key lives
