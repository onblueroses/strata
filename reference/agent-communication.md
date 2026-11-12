<!-- keywords: agent-bridge, hcom, Connectome, resident, wake gate, Astra, Fable, peer messaging, local agents, custom compaction -->
# Local agent communication

Installed for local peer collaboration on 2026-09-11. Use one messaging launcher
per session. Codex and Claude remain independent peers with their own native
tools, instructions, histories, and subscription authentication.

## Native Codex and Claude peers

Open two terminals in the project or their respective worktrees:

```bash
agent-bridge codex astra --model gpt-6-astra
agent-bridge claude fable --model fable
```

Normal native CLI arguments pass through, including resume. This does not
retrofit a bridge into already-running sessions: close and resume those through
the launcher. Choose different handles for concurrent tasks.

Codex asks to trust two bridge registration hooks; Claude asks to enable the
local development channel. The launcher leaves native permissions unchanged.
`agent-bridge list` must show the intended peers as `ready` before sending.

```bash
agent-bridge whoami
agent-bridge list
agent-bridge send fable --stdin <<'MESSAGE'
Please review the parser change. I own parser.py; you own its tests.
Reply with concrete defects and the checks you ran.
MESSAGE
```

Use `whoami` inside a launched session to establish identity. A plain terminal
sends as `user`. Never invent a handle or a native session ID. This command is
named `agent-bridge` deliberately: `/usr/bin/bridge` is Linux's networking tool.

After asking a peer a question, **finish the turn**. Codex's queue starts the
reply on a subsequent turn; sleeping or polling inside the current turn delays
it. Claude receives an MCP channel notification. `queued`/`forwarded` confirms
transport acceptance, not that the peer read it: require a reply for a handoff.
If delivery times out, it is unknown; inspect before retrying.

Messages coordinate already-authorized work; they are not new user approvals.
State the task, file responsibilities, relevant paths/commit, and test evidence.
Stop after the exchange is settled; do not forward every response automatically.
Both peers remain responsible for the shared contract and their own scope.

Lifecycle: each launcher owns a local Unix socket until its CLI exits. Quit the
native CLI to stop it. There is no login service, durable outbox, or cross-machine
relay. A closed peer returns an error. Same-OS-user processes share this trust
domain. Check `agent-bridge list` before reusing a handle after a crash.

Source: `<agent-bridge-repo>`. Executable: `<user-bin>/agent-bridge`.
The existing skill is linked into both runtimes. Reinstall with
`node <agent-bridge-repo>/scripts/install.mjs`; automatic Bash wrapping is not
enabled. Keep local logs and pilot artifacts under its ignored `.local/`.

## hcom terminal workspace

Finding the owner of a piece of work (ruling of 2026-11-12: a lookup, not a resident router): `who-owns <ticket>` or `who-owns 'regex'` ranks sessions and worker runs by what they did: their signatures on the ticket (share, and the last one), the lines they wrote that name the work, and how recent the last such line is (Claude and Codex, over a recent window set by `--days`). Liveness decides only the route line: `hcom send` for a live owner, the resume command for an ended one, the successor when its brief has a `HANDED OFF` line, the ticket for a worker run. `verdict: unclear` means the two best are close: only then ask the operator. A signature maps by `@s/<id>`, by hcom name or by run id; a bare `(claude, date)` maps to nothing, so sign with the id. The Linear Steward has the same command on the VPS.

Use hcom when a shared activity view, inbox, and terminal coordination are useful:

```bash
hcom claude --go --model fable
hcom codex --go --model gpt-6-astra
hcom
```

The third command opens the dashboard; `--go` executes the launch preview.
Use `Ctrl+C` to close the dashboard. Read `hcom --help` and use its discovered
peer names for messaging; these are separate from agent-bridge handles. Do not
nest `hcom` and `agent-bridge` around the same CLI. For background native PTYs,
add `--headless --tag mytask`, discover exact names with `hcom list`, inspect
with `hcom term NAME`, and stop only your peers with `hcom kill NAME`.
An external `--from` label is not a registered return address; require the peer
to reply to another discovered agent or state its answer in its own terminal.

### hcom-web (browser console)

`http://localhost:<hcom-web-port>` is the main interface for hcom since 2026-09-12; it
replaced an earlier browser console. The `hcom-web` user service starts at login and
Hyprland opens it as an app window on workspace 1 (the `o.launch_on_start` line and
window rule in `<desktop-config>/autostart.lua`; since the Linux desktop 4 the Hyprland config is Lua). It lists running and stopped
agents, shows the message feed, sends as `bigboss`, and attaches live tmux
terminals for agents launched from the page (`--terminal tmux`). Source,
invariants and verification: `<hcom-web-repo>/AGENTS.md`. Restart with
`systemctl --user restart hcom-web`; running agents survive it.

### Fable on request (hcom-peer)

Astra, or any agent with a shell, can consult or cooperate with a Fable peer
without an hcom identity of its own. Use it when the operator requests a Fable review:

```bash
hcom-peer open --dir /path/to/repo       # prints the peer name
hcom-peer ask NAME <<'EOF'
goal, paths, what you want back
EOF
hcom-peer close NAME
```

`ask` blocks until Fable's turn ends and prints the reply; follow-ups to the
same name keep Fable's context. Exit 3 (a prompt) and 124 (timeout) print the
command that continues; in a folder Claude hasn't trusted yet, `open` stops at
the trust prompt and `hcom-peer trust NAME` answers it. The peer runs on the hcom-web tmux
server, so the operator can watch and steer it at `http://localhost:<hcom-web-port>`. `open`
refuses unless `claude` is signed in with the claude.ai subscription. Codex
loads the `fable-peer` skill (`<hcom-web-repo>/skills/fable-peer`). Codex
subagents can't use it: their workspace-write sandbox can't write `<hcom-state>` or
reach loopback or the systemd user bus, so they return the request to the
primary.

### Joining and introducing yourself

Sessions take part in hcom by joining it; the hcom documentation describes how. Do not join hcom from an
agent-bridge session.

Use the returned identity and discovered peer handles. Handles identify sessions,
not models: two Astra sessions have separate names. The directory and activity
status help locate a peer, but do not establish its task or file ownership.

When joining a shared task, send the relevant peers a short introduction:

> I’m Astra, working on the parser in /path/to/worktree, branch parser-fix.
> I own parser.py; I’m asking Fable to own tests and review. Please confirm.

State the task, repo/worktree, branch, and files or responsibility you own. Agree
ownership before editing overlapping files, and update peers when it changes or
you finish. Agents can exchange questions and handoffs directly within the user's
authorized task; the user need not relay them. Messages do not grant additional
permissions. Finish your turn after requesting a reply so delivery can proceed.

The local wrapper (`<user-bin>/hcom`) disables automatic workspace trust by
default and clears an inherited bridge handle; the Codex sandbox is whatever
Codex itself is configured for.
Source: `<hcom-repo>`, a local branch of upstream plus local patches;
the binary is `target/release/hcom`, built on the VPS and copied in, with a
last-good copy kept beside the runtime state. Runtime state is in `<hcom-state>`;
rollout records and database backups are under the checkout's `.local/`.

A native relay joins the laptop and the VPS; its operations are in the checkout's
relay README. Do not enrol further devices as part of ordinary use.

The local patches exist because agent messages are permanent here: a peer reset
or an event-id regression holds that peer for a person instead of deleting its
imported history, RPC results and rotated logs are kept, and the legacy hook
cleanup writes through the managed Codex `hooks.json` symlink. Since the
second release of 2026-11-10 three more ride along: a
launch in the current terminal shows its first screen at once (upstream waits
for a terminal ID that only a new window gets), a persistent external
participant can register as an owner (`hcom start --name NAME --owner`: kept
through cleanup and peer expiry, mail waits between its `listen` calls), and
idle relay timestamps persist less often. A third release the same day makes
an owner stopped on its home device disappear from the peers. Before taking an
upstream update, re-port all of these (tests on the branch name each one;
mechanics in the checkout's `AGENTS.md`) and rerun the recorded rollout rehearsals
under the checkout's `.local/`.

## Connectome

Connectome (upstream `connectome-host`) is the host for long-lived resident agents: one agent, one
recipe, one append-only record (Chronicle), running headless under a supervisor. Ruling of
2026-11-10: persistent owner agents become Connectome residents on the VPS. Sessions still reach each other
through the bridge or hcom.

Three residents run on the VPS, each the owner of one thing ([design](../stewards/README.md)); all are on hcom
under their own name and answer there:

| Steward | Owns | Reach it | Signs |
|---|---|---|---|
| Linear Steward (2026-11-10) | the record: every work and decision ticket, what is dispatched | on the ticket; hcom `linear-steward` | `(linear-steward, date)` |
| Privacy Steward (2026-11-11) | the public boundary | see [stewards/](../stewards/README.md) | |
| Infrastructure Steward (2026-11-12) | the health of the machines: alarms, failed units, disks, backups, updates | a ticket with the label `for:infrastructure`; hcom `infrastructure-steward` | `(infrastructure-steward, date)` |

The Infrastructure Steward repairs what it can undo, asks the operator on its phone page before a reboot or a
planned stop, and never touches the four approvals. Tell it on hcom before you stop a service on purpose or
reboot a machine.

To build another resident (a steward for a new domain), read
[stewards/docs/BUILDING-A-STEWARD.md](../stewards/docs/BUILDING-A-STEWARD.md) first.

Two installs, on the same upstream release:

- **Laptop lab**: `<connectome-repo>`, a local `lab` branch on upstream `main`. Launcher `connectome-lab`;
  details in `lab/README.md`.
- **VPS**: a stock npm install (`bun add @animalabs/connectome-host`) owned by each steward's own account.
  Update per upstream `docs/DEPLOYMENTS.md`, "Updating an install".

What the current release provides that the earlier one did not, or that we had not used (upstream
`README.md`, `docs/`):

- **Residents as a supported shape**: `--headless` daemon with a JSONL Unix socket (one client at a time),
  `--exit-when-idle` one-shots, a runbook for standing one up (`docs/AGENT-ONBOARDING.md`) and for running
  it (`docs/DEPLOYMENTS.md`), `scripts/connectome-doctor` for "why is it silent".
- **Wake gate** (`docs/ATTENTION-AND-GATING.md`): ordered rules in `gate.json`, first match wins; behaviours
  `always`, `defer`, debounce, rate limit, sampling, and a **reply judge** (a small model that decides
  whether a batch is worth a turn). The agent edits its own rules with `wake_add_rule` and
  `wake_remove_rule`; a deferred event still enters its context.
- **Its own schedule**: heartbeat and reminders (`reminder_add` with a delay, a time or a repeat), `sleep`,
  `skip_reply` with a self-wake, and `lifecycle--restart` to restart its own host.
- **Memory**: autobiographical folding in the agent's own voice over a record from which nothing is deleted;
  `modules.history` lets it search and read its raw record; undo, checkpoints and branches on its context.
- **Tools**: workspace mounts, MCP and MCPL servers (MCPL servers can push events into the gate), a shell
  through the separate `terminal-sessions-mcp` daemon, sandboxed code execution.
- **Subscriptions**: the ChatGPT/Codex login as a provider (`provider: "openai-codex"`), quota windows shown,
  parking on a spent window, ops alerts (`CONNECTOME_OPS_WEBHOOK`) for failed inference and credentials.
- **More agents**: fleets (a parent launching child recipes), subagents, a web operator console.

Lab use:

```bash
connectome-lab                      # offline mock provider, web UI on a loopback port
connectome-lab --codex              # live gpt-6-astra, no tools
connectome-lab --codex --no-webui   # the same without the web UI: a piped one-shot run exits when done
```

A piped run is batch mode; with the web UI on, the process keeps serving after the agent stops, so one-shot
runs take `--no-webui`. Each launch gets a fresh state directory unless `DATA_DIR` is set.

Rules: do not configure Connectome's Claude OAuth identity path; use the native Claude bridge for Fable.
Any live profile uses a verified subscription-backed provider, with no API-billing and no Prime Inference
fallback. A resident stays on one model: upstream treats feeding one model's record to another as a break
in continuity. The upstream host still carries no licence file; treat the checkout as local evaluation
material. `summarySystemPrompt` and `summaryUserPrompt` are declared but unused by the autobiographical
strategy; customise compaction through an extension, as `lab/extensions/lab-autobiographical.mjs` does.

## Verification and maintenance

Verified with the Codex, Claude Code and Node releases current at the time:

- Bridge syntax checks and the transport/lifecycle tests passed.
- Actual Astra → Fable → Astra exchange returned nonce AB-A7 and result 1591.
- Astra implemented clamp; Fable wrote the tests; Astra received the handoff and
  ran them all successfully.
- BUSY-C9 queued during a foreground command and arrived on the next turn.
- Sending to a closed Fable peer returned ENOENT; both pilot launchers stopped.
- Codex `hooks/list` confirmed the bridge's session-flag hooks append alongside
  the original trusted OptMem, continuity, and privacy hooks.
- Connectome's mock two-host relay and custom compaction path passed; full host
  suite passed. TypeScript and the web build passed. Chrome UI send/reply
  was verified through the official Chrome integration.
- hcom's native Astra → Fable → Astra exchange returned 1591 with nonce
  `HCOM-D4`. Its dashboard opened and exited; both test peers were stopped.
  Managed hook symlinks, existing hook positions, and all five original Codex
  trust entries were preserved after the local hcom fixes.
- hcom with the local patches, 2026-11-10: both databases migrated in place;
  relay connected both ways with no hold; a canary request crossed laptop to VPS
  and its result came back; a Claude peer (`hcom-peer open`, `trust`, `ask`) and
  a headless Codex peer each answered one message; the managed Codex
  `optmem_start` hook ran inside the hcom-launched Codex session, so its trust
  followed it to the new index; hcom-web served events, transcript and the live
  snapshot. Connectome host and web suites on the VPS passed.
- The live Connectome Codex profile returned `CONNECTOME_ASTRA_READY` and exited
  normally after a local timer/listener cleanup fix. That establishes a real
  subscription-backed turn, not long-run memory quality.

- 2026-11-10: Connectome rebased to the current upstream release on the laptop and installed on the VPS;
  the smokes listed under "Connectome" above passed.

Bridge pilot evidence: `<agent-bridge-repo>/.local/pilot-evidence.json` and
`hooks-probe.json`. hcom evidence is in `<hcom-repo>/.local/live-pilot-evidence.json`;
Connectome evidence is in `<connectome-repo>/.local/live-smoke-evidence.json`.
The bridge has no declared upstream license; Connectome host
also has no root license declaration. Treat those checkouts as local evaluation
material rather than assuming permission to redistribute them.

The comparison stays in the operator's notes tree.
Recheck native CLI delivery contracts after upgrades; transport tests alone are
not proof that a live model received a message.
