<!-- keywords: agent-bridge, hcom, Connectome, Astra, Fable, peer messaging, local agents, custom compaction -->
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

`http://localhost:4747` is the main interface for hcom since 2026-09-12; it
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
server, so the operator can watch and steer it at `http://localhost:4747`. `open`
refuses unless `claude` is signed in with the claude.ai subscription. Codex
loads the `fable-peer` skill (`<hcom-web-repo>/skills/fable-peer`). Codex
subagents can't use it: their workspace-write sandbox can't write `<hcom-state>` or
reach loopback or the systemd user bus, so they return the request to the
primary.

### Joining and introducing yourself

Sessions launched through hcom join automatically. An ordinary native Claude or
Codex session can opt in by running these commands **inside that agent's session**:

```bash
hcom start
hcom list -v
```

The hooks must be loaded in that native session. Confirm that the session is
registered and receives a reply before relying on delivery; older sessions may
need a restart/resume to load newly installed hooks. Running `hcom start` in an
unrelated terminal does not connect another conversation. Do not join hcom from
an agent-bridge session.

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

The local wrapper preserves the native Codex sandbox profile and disables
automatic workspace trust by default. The user can override these explicitly.
Its own hooks may be installed in native config, but must be inactive outside an
hcom session. Preserve existing hook order, commands, and trusted hashes when
updating. Source: `<hcom-repo>`; the binary is `target/release/hcom`. Runtime state is in `<hcom-state>`,
with setup snapshots under the checkout’s `.local/`. Do not enable MQTT relay
as part of ordinary local use.
The installed build includes local fixes for the managed Codex hook symlink and
preserving existing hook positions. Before replacing it with an upstream update,
verify those fixes are present and rerun the managed-link/trust checks.

### Persistent Sol session (queue worker)

One Codex session with the tag `sol` (name `sol-<word>`, model gpt-6.1-sol) is kept alive on the laptop by the
user timer `worker-laptop.timer` (`<agent-config>/scripts/queue-worker/`, mode `hcom`): each tick relaunches it if it is
gone and hands it one claimed `for:codex` ticket as a message from `sol-keeper`. `sol-keeper` is an external
label with no inbox; the session reports on the Linear ticket, not by reply. Watch or steer it in hcom-web like
any agent; a peer may message it, but it owns whatever ticket it holds. Stop the worker with
`systemctl --user stop worker-laptop.timer` before `hcom kill tag:sol`, or the next tick relaunches the session.
Keeper state: `<worker-state>/state.json`. The VPS counterpart has no hcom and runs `codex exec`
per ticket (`vps-operations.md`).

## Connectome lab

`<connectome-repo>` is a separate runtime and memory experiment. It does not
attach to an existing native conversation or inherit that runtime's full tool
catalog. Start the local interface with:

```bash
connectome-lab
```

The default is a **mock provider**, not a reasoning model. Its UI binds to
`http://127.0.0.1:7340` while the process runs. `--headless` uses a Unix socket;
no persistent service is installed. See `<connectome-repo>/lab/README.md`
for available profiles and explicit state-directory controls. Stop the process
after the experiment.

For the live, tool-free Astra profile:

```bash
connectome-lab --codex
```

This explicitly uses your existing Codex subscription with `gpt-6-astra`, low
reasoning, and no tools or speculative compression. The launcher clears ambient
model, endpoint, CLI, and credential-directory overrides. It does not attach
Fable to this environment. Each launch starts fresh; set `DATA_DIR` deliberately
to keep and resume one experiment's history. Native collaboration belongs in
the bridge or hcom; this profile is for testing the alternate runtime.

The lab contains a custom autobiographical strategy extension and a two-host
mock messaging/compaction smoke test. This tests that the compaction code path
runs; mock summaries do not establish memory quality. The current upstream
`summarySystemPrompt`/`summaryUserPrompt` fields are declared but not consumed
by its autobiographical implementation. Customize through the lab extension's
active instruction methods instead.

Do not configure Connectome's Claude OAuth identity-spoofing path. Use the native
Claude bridge for Fable. Any live profile must use a verified subscription-backed
provider, with no API-billing or Prime Inference fallback. Exact adapter behavior
and model availability must be checked when upgrading.

## Verification and maintenance

Verified with Codex 0.154.0 (`gpt-6-astra`), Claude Code 2.1.269 (Fable 5.1),
and Node 25.8.0:

- Bridge syntax checks and 10 transport/lifecycle tests passed.
- Actual Astra → Fable → Astra exchange returned nonce AB-A7 and result 1591.
- Astra implemented clamp; Fable wrote 15 tests; Astra received the handoff and
  ran all 15 successfully.
- BUSY-C9 queued during a foreground command and arrived on the next turn.
- Sending to a closed Fable peer returned ENOENT; both pilot launchers stopped.
- Codex `hooks/list` confirmed the bridge's session-flag hooks append alongside
  the original trusted OptMem, continuity, and privacy hooks.
- Connectome's mock two-host relay and custom compaction path passed; full host
  suite: 806 passed. TypeScript and the web build passed. Chrome UI send/reply
  was verified through the official Chrome integration.
- hcom's native Astra → Fable → Astra exchange returned 1591 with nonce
  `HCOM-D4`. Its dashboard opened and exited; both test peers were stopped.
  Managed hook symlinks, existing hook positions, and all five original Codex
  trust entries were preserved after the local hcom fixes.
- The live Connectome Codex profile returned `CONNECTOME_ASTRA_READY` and exited
  normally after a local timer/listener cleanup fix. That establishes a real
  subscription-backed turn, not long-run memory quality.

Bridge pilot evidence: `<agent-bridge-repo>/.local/pilot-evidence.json` and
`hooks-probe.json`. hcom evidence is in `<hcom-repo>/.local/live-pilot-evidence.json`;
Connectome evidence is in `<connectome-repo>/.local/live-smoke-evidence.json`.
The bridge has no declared upstream license; Connectome host
also has no root license declaration. Treat those checkouts as local evaluation
material rather than assuming permission to redistribute them.

The comparison is in
`<notes-tree>/lore/research/agent-communication.md`.
Recheck native CLI delivery contracts after upgrades; transport tests alone are
not proof that a live model received a message.
