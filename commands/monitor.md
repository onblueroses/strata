---
description: "Autonomous process monitoring with minimal token cost; generates bash health-check scripts, cron-based watchdog, and prescribed repair playbooks. Three-layer architecture: bash does mechanical checks (zero tokens), cron invokes it, Claude only reasons when problems exist. Triggers on: 'monitor this process', 'watch the training run', 'set up health checks', 'watchdog', 'keep an eye on', 'autonomous oversight', 'check periodically', 'monitor a long-running task'. Also triggers when: user asks for unattended supervision of a long-running job; user mentions thermal/disk/GPU health monitoring; user wants a cron-based watcher with formulaic repairs. Pairs with /loop (interval-driven polling — use loop for self-paced re-entry, monitor for cron-tick zero-token health-checking), /status (one-shot cross-project health check vs. monitor's persistent watchdog), /deploy (downstream — monitor confirms green before a deploy proceeds), /overnight (cousin — unattended long-running pattern). Manual: /monitor, /monitor start, /monitor stop, /monitor status."
---

# Monitor

Autonomous monitoring for long-running processes. Three-layer architecture:
1. **Bash script** does all mechanical checks (zero tokens)
2. **Cron** invokes it periodically
3. **Claude** only reasons when problems exist (thin dispatcher with inline repair playbook)

## Quick Nav

| Task | Section |
|------|---------|
| Set up a new monitor | Interview Flow |
| Stop a running monitor | Stop Subcommand |
| Check current health | Status Subcommand |
| Understand exit codes | Exit Code Protocol |
| How repairs work | Circuit Breaker Design |
| What gets checked | Check Taxonomy |
| Cron prompt structure | Cron Prompt Template |
| What to avoid | DO NOT |

## Usage

```
/monitor              # Start new monitor (interview + setup)
/monitor start        # Same as above
/monitor stop         # Stop active monitor, show summary
/monitor status       # Run health check once, show results
```

Arguments via `$ARGUMENTS`. Parse for subcommand before anything else:
- Empty or `start` -> Interview Flow
- `stop` -> Stop Subcommand
- `status` -> Status Subcommand

### Single-Monitor Guard

Before starting a new monitor, check `$KB_DIR/areas/infrastructure/monitors/` for directories
with a `config.json` whose `session` field matches this session ID. If found:
"Active monitor '{name}' already running in this session. Stop it first with `/monitor stop`."

## Safety

- **No secrets** in generated artifacts - health_check.sh must not contain passwords, tokens, or API keys
- **Deletion convention** - `/monitor stop` moves artifacts to `~/to-delete/`, does not delete
- **7-day expiry** - CronCreate jobs auto-expire after 7 days. Warn the user at setup: "Monitor will auto-expire in 7 days. Re-run `/monitor start` to renew."
- **SSH confirmation** - Before running detection commands on remote hosts, confirm the target with the user
- **Single monitor per session** - One active cron per Claude session. Multiple sessions can run different monitors.
- **No open-ended reasoning on cron tick** - Healthy = one-line ack. Problems = prescribed fix. Never exploratory research.

## Exit Code Protocol

| Exit | Meaning | stdout Contract | Claude Action |
|------|---------|----------------|---------------|
| 0 | Healthy | One-line summary: `OK: all N checks passed` | Respond "Monitor {name}: healthy" |
| 1 | Problems | JSON array: `[{"check":"disk","severity":"warn\|crit","detail":"...","repair":"..."}]` | Parse JSON, apply repair playbook, re-run to verify |
| 2 | Complete | Summary: `COMPLETE: {reason}` | Announce completion, CronDelete the job |
| 3 | Escalate | `ESCALATE: {problem} (N attempts, last: {timestamp})` | Alert user, do NOT attempt repair |

## Token Cost Model

| Tick Type | Approx. Tokens | When |
|-----------|---------------|------|
| Healthy | ~50 | Exit 0 - one-line response |
| Repair | ~300 | Exit 1 - parse + execute + verify |
| Complete | ~100 | Exit 2 - announce + delete cron |
| Escalate | ~100 | Exit 3 - alert user |

<details>
<summary>Circuit Breaker Design</summary>

### Circuit Breaker Design

State file at `monitors/{name}/state.kv` tracks per-problem repair attempts:

```
# Format: {check}_{severity}.{field}={value}
disk_crit.attempts=2
disk_crit.last_repair=1712345678
disk_crit.backoff=120
thermal_crit.attempts=0
```

**Rules:**
- Max **3 repair attempts** per problem type
- Exponential backoff: **60s, 120s, 240s** between attempts
- After max attempts: health_check.sh promotes the problem from exit 1 to exit 3 (escalate)
- **Reset on clear**: when a check passes that previously failed, reset its attempt counter to 0
- State file is read/written by health_check.sh using simple grep/sed - no jq dependency

**Backoff enforcement**: health_check.sh checks `last_repair` timestamp against current time.
If within backoff window, skip the repair report for that problem (still log it, don't re-trigger Claude).

</details>

## Check Taxonomy

| Category | Check | Local | SSH | HTTP | Default Threshold |
|----------|-------|:-----:|:---:|:----:|-------------------|
| Device | Thermal | x | x | | 80C warn, 90C crit |
| Device | Disk usage | x | x | | 85% warn, 95% crit |
| Device | Memory | x | x | | 90% warn, 95% crit |
| Device | GPU temp/util | x | x | | 85C warn, 95C crit |
| Process | Alive (pgrep/pidfile) | x | x | | - |
| Process | Stalled (log mtime) | x | x | | 10min warn, 30min crit |
| Process | HTTP health | | | x | non-200 = crit |
| Data | File integrity (checksum) | x | x | | mismatch = crit |
| Data | Checkpoint size | x | x | | <1KB = crit (corruption) |
| Completion | Process exited | x | x | | exit = complete |
| Completion | Output file exists | x | x | | exists = complete |
| Completion | Idle (no log writes) | x | x | | 60min = complete |

<details>
<summary>Interview Flow</summary>

## Interview Flow

Four stages: Infer, Confirm, Ask, Generate.

### Stage 1: Infer

Run detection commands to discover what's running and what resources are available.
Execute these in parallel where possible:

**Local detection:**
```bash
# Running processes (filter for user processes, skip system)
ps aux --sort=-%cpu | head -20

# GPU presence and state
nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null

# Disk state
df -h / /tmp /home 2>/dev/null

# Memory
free -m

# Listening ports
ss -tlnp | grep -v '127.0.0.1'
```

**Remote detection (if user mentions SSH/remote/VPS):**
```bash
# Discover Tailscale targets
tailscale status 2>/dev/null

# For each confirmed target, run the same local detection commands via SSH
ssh {target} 'ps aux --sort=-%cpu | head -20; nvidia-smi ... 2>/dev/null; df -h /; free -m'
```

**HTTP detection (if user mentions endpoints/services):**
```bash
# Test endpoint availability
curl -sI -o /dev/null -w "%{http_code}" {url}
```

### Stage 2: Confirm

Present findings via AskUserQuestion. Example:

```
Question: "I detected these on your system. What should I monitor?"
Header: "Targets"
Options:
- "python train.py (PID 12345, 98% CPU, GPU 0)" - "Long-running training process"
- "node server.js (PID 6789, port 3000)" - "Web server process"
- "Disk / at 72%" - "Monitor disk usage"
- "GPU 0: RTX 3090, 78C" - "Monitor GPU temperature"
multiSelect: true
```

For SSH targets, present separately with confirmation before connecting.

### Stage 3: Ask

Only ask what cannot be inferred. Skip questions where defaults suffice.

**Question 1 (always ask):**
```
Question: "What does 'done' look like for this workload?"
Header: "Completion"
Options:
- "Process exits cleanly" - "Monitor stops when the process terminates"
- "Output file appears" - "Specify a file path that signals completion"
- "No completion" - "Run until manually stopped or 7-day expiry"
multiSelect: false
```

**Question 2 (ask if process monitoring selected):**
```
Question: "If the process crashes, how should it be restarted?"
Header: "Restart"
Options:
- "Same command" - "Re-run the original command from the same directory"
- "Custom command" - "Specify a restart command"
- "Don't restart" - "Just alert me"
multiSelect: false
```

**Question 3 (ask if data files detected):**
```
Question: "Which files should be backed up? I'll keep the last 3 copies."
Header: "Backups"
Options (dynamically generated from detected checkpoint/output files):
- "{path/to/checkpoint}" - "{size}, modified {time}"
multiSelect: true
```

**Question 4 (always offer, usually skipped):**
```
Question: "Override any default thresholds?"
Header: "Thresholds"
Options:
- "Use defaults" - "Disk 85%, Memory 90%, Temp 80C, Stale 10min"
- "Customize" - "Set specific thresholds"
multiSelect: false
```

### Stage 4: Generate

Based on interview results, Claude generates:

1. **config.json** - serialized workload profile
2. **health_check.sh** - custom bash script
3. **CronCreate** call with inline repair playbook

See Generate Stage for health_check.sh requirements.

</details>

<details>
<summary>Generate Stage</summary>

## Generate Stage

### config.json Schema

```json
{
  "name": "training-run",
  "created": "2026-04-08T17:00:00Z",
  "session": "71814f04",
  "type": "local|ssh|http|mixed",
  "target": {
    "host": "localhost|user@host|https://...",
    "ssh_via": "tailscale hostname (if SSH)"
  },
  "checks": [
    {
      "category": "process",
      "type": "alive",
      "params": { "pattern": "python train.py", "pidfile": null },
      "thresholds": { "warn": null, "crit": true }
    },
    {
      "category": "device",
      "type": "disk",
      "params": { "mount": "/" },
      "thresholds": { "warn": 85, "crit": 95 }
    }
  ],
  "completion": {
    "type": "process_exit|file_exists|idle|none",
    "params": { "path": "/output/final.pt", "idle_minutes": 60 }
  },
  "repairs": {
    "process_crashed": "cd /path && python train.py --resume",
    "disk_full": "find /path/checkpoints -name '*.pt' | sort | head -n -3 | xargs rm",
    "thermal_critical": "kill -STOP {pid} && sleep 60 && kill -CONT {pid}"
  },
  "backups": {
    "paths": ["/path/checkpoints/latest.pt"],
    "keep": 3,
    "frequency_minutes": 30
  },
  "cron_schedule": "*/5 * * * *",
  "cron_job_id": null
}
```

### health_check.sh Requirements

Claude writes this script tailored to the workload. It MUST:

1. **Shebang**: `#!/usr/bin/env bash` with `set -euo pipefail`
2. **Config**: Read monitor directory from `MONITOR_DIR` variable set at top of script
3. **State**: Read/write `$MONITOR_DIR/state.kv` for circuit breaker
4. **Log**: Append each check result to `$MONITOR_DIR/log.jsonl`
5. **Output format**:
   - Exit 0: `echo "OK: all N checks passed"`
   - Exit 1: `echo '[{"check":"...","severity":"...","detail":"...","repair":"..."}]'`
   - Exit 2: `echo "COMPLETE: {reason}"`
   - Exit 3: `echo "ESCALATE: {problem} ({N} attempts, last: {timestamp})"`
6. **Check functions**: One function per enabled check, each returns a status line
7. **Aggregation**: Collect all check results, determine worst severity, set exit code
8. **Circuit breaker reads**: Before reporting a problem, check state.kv for attempt count and backoff
9. **No external dependencies** beyond: bash, coreutils, grep, sed, curl (for HTTP), ssh (for remote)
10. **Backup function** (if backups configured): Copy files with timestamp suffix, prune old copies

### Example health_check.sh structure

```bash
#!/usr/bin/env bash
set -euo pipefail

MONITOR_DIR="$KB_DIR/areas/infrastructure/monitors/training-run"
STATE_FILE="$MONITOR_DIR/state.kv"
LOG_FILE="$MONITOR_DIR/log.jsonl"
PROBLEMS=()

# --- State helpers ---
get_state() { grep "^${1}=" "$STATE_FILE" 2>/dev/null | cut -d= -f2 || echo "${2:-0}"; }
set_state() { sed -i "/^${1}=/d" "$STATE_FILE" 2>/dev/null; echo "${1}=${2}" >> "$STATE_FILE"; }

# --- Check functions ---
check_process_alive() { ... }
check_disk() { ... }
check_gpu_temp() { ... }
check_completion() { ... }

# --- Backup ---
do_backup() { ... }

# --- Main ---
check_process_alive
check_disk
check_gpu_temp

# Completion check (exit 2 if done)
if check_completion; then
  echo "COMPLETE: process exited cleanly"
  echo "{\"ts\":\"$(date -Is)\",\"status\":\"complete\"}" >> "$LOG_FILE"
  exit 2
fi

# Backup (periodic, based on last backup timestamp in state.kv)
do_backup

# Aggregate results
if [[ ${#PROBLEMS[@]} -eq 0 ]]; then
  echo "OK: all checks passed"
  echo "{\"ts\":\"$(date -Is)\",\"status\":\"ok\"}" >> "$LOG_FILE"
  exit 0
fi

# Check circuit breaker for each problem
ESCALATIONS=()
REPAIRABLE=()
for p in "${PROBLEMS[@]}"; do
  check_name=$(echo "$p" | jq -r .check)
  attempts=$(get_state "${check_name}.attempts" 0)
  if [[ $attempts -ge 3 ]]; then
    ESCALATIONS+=("$p")
  else
    REPAIRABLE+=("$p")
  fi
done

if [[ ${#ESCALATIONS[@]} -gt 0 ]]; then
  # Output escalation
  echo "ESCALATE: ... (details)"
  exit 3
fi

# Output repairable problems as JSON array
echo "[${REPAIRABLE[*]}]"
exit 1
```

This is a structural example. Claude generates the actual script with real check logic
tailored to the interview results.

</details>

<details>
<summary>Cron Prompt Template</summary>

## Cron Prompt Template

The cron prompt is assembled during the Generate stage. Template:

```
Run this command and act on the result:

bash {monitor_dir}/health_check.sh

Based on the exit code:

EXIT 0 (healthy):
Respond with exactly: "Monitor {name}: healthy"
Do nothing else. Do not read files. Do not reason.

EXIT 1 (problems found):
The stdout is a JSON array of problems. For each problem, apply the matching repair:

{repair_table}

After applying repairs, re-run: bash {monitor_dir}/health_check.sh
If still exit 1, update the circuit breaker state and respond with what was attempted.
If exit 0, respond: "Monitor {name}: repaired {what}"

EXIT 2 (work complete):
Respond: "Monitor {name}: complete - {stdout summary}"
Then delete this cron job.

EXIT 3 (escalate):
Respond: "MONITOR ALERT {name}: {stdout}. Automatic repairs exhausted. Needs human intervention."
Do NOT attempt any repair.
```

### Repair Table Format

The `{repair_table}` is generated from config.json repairs:

```
- check="process" severity="crit": Run: cd /path && python train.py --resume
- check="disk" severity="crit": Run: find /checkpoints -name '*.pt' | sort | head -n -3 | xargs rm
- check="thermal" severity="crit": Run: kill -STOP $(pgrep -f 'train.py') && sleep 60 && kill -CONT $(pgrep -f 'train.py')
```

Each line is a direct command. Claude pattern-matches the JSON check field to the repair line
and executes the command. No reasoning required.

</details>

<details>
<summary>Stop Subcommand</summary>

## Stop Subcommand

`/monitor stop` tears down the active monitor.

1. **Find active monitor**: Scan `$KB_DIR/areas/infrastructure/monitors/*/config.json` for one matching this session ID
2. **Delete cron**: Use CronDelete with the job ID from config.json `cron_job_id` field
3. **Parse log**: Read `log.jsonl`, compute summary stats:
   - Total ticks (lines in log)
   - Healthy ticks (status=ok)
   - Repair ticks (status=repair)
   - Escalations (status=escalate)
   - Uptime percentage (healthy / total * 100)
   - Duration (first entry to last entry)
4. **Present summary**:
```
Monitor '{name}' stopped.
Duration: Xh Ym | Ticks: N (M healthy, K repairs, J escalations)
Uptime: XX.X%
Artifacts moved to ~/to-delete/monitors-{name}-{date}/
```
5. **Move artifacts**: Move the entire `monitors/{name}/` directory to `~/to-delete/monitors-{name}-{date}/` and log in `~/to-delete/manifest.txt`

**If no active monitor found**: "No active monitor in this session. Check `$KB_DIR/areas/infrastructure/monitors/` for monitors from other sessions."

</details>

<details>
<summary>Status Subcommand</summary>

## Status Subcommand

`/monitor status` runs a one-shot health check without the cron loop.

1. **Find active monitor**: Same scan as Stop
2. **Run health check**: `bash monitors/{name}/health_check.sh`
3. **Format output** based on exit code:

**Exit 0:**
```
Monitor '{name}': HEALTHY
All N checks passed.
Last 5 ticks: ok, ok, ok, repair(disk), ok
```

**Exit 1:**
```
Monitor '{name}': PROBLEMS DETECTED
- disk (crit): / at 96% - repair: prune checkpoints
- thermal (warn): GPU 0 at 82C - within backoff window (next check in 45s)
Circuit breaker: disk=2/3 attempts, thermal=1/3 attempts
```

**Exit 2/3:**
```
Monitor '{name}': COMPLETE|ESCALATE
{stdout details}
```

4. **Show circuit breaker state**: Parse state.kv, show attempt counts for any non-zero entries
5. **Show recent log**: Last 5 entries from log.jsonl with timestamps

</details>

## DO NOT

- Run health_check.sh without it existing (generate first)
- Store secrets in health_check.sh or config.json
- Attempt repairs after circuit breaker trips (exit 3 = hands off)
- Start a second monitor in the same session
- Delete monitor artifacts directly (use ~/to-delete/ convention)
- Do exploratory reasoning on a cron tick (healthy = one line, problems = prescribed fix)
- Create monitors without user confirming targets via AskUserQuestion
- SSH to remote hosts without user confirmation of the target
- Generate health_check.sh that depends on jq, python, or non-standard tools
- Ignore the 7-day cron expiry - always warn the user at setup

## Good vs Bad

| Aspect | Bad | Good |
|--------|-----|------|
| Interview | "What do you want to monitor?" (open-ended) | Detect 3 processes, GPU at 78C, disk at 72%. Present: "I found these. Which to monitor?" |
| Health check output | `echo "something is wrong"` | `echo '[{"check":"disk","severity":"crit","detail":"/ at 96%","repair":"prune"}]'` |
| Cron tick (healthy) | Read config, check state, reason about results, respond with paragraph | `bash health_check.sh` -> exit 0 -> "Monitor training: healthy" |
| Repair action | "The disk seems full, let me investigate what's using space..." | `find /checkpoints -name '*.pt' \| sort \| head -n -3 \| xargs rm` |
| Stop summary | "Monitor stopped." | "Duration: 4h 22m, 53 ticks (51 healthy, 2 repairs), 96.2% uptime" |
| Circuit breaker | Retry disk cleanup 10 times | 3 attempts with 60/120/240s backoff, then escalate |
