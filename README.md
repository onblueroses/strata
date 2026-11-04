# Strata

One person's working setup for running Claude Code, Codex, DeepSeek and Kimi as a team: the shared
instructions, hooks, memory, ticket queue, delegation routes and skills, plus the reasons behind each rule.
It is a real setup, copied out and anonymized, not a framework written for a demo.

Snapshot of 2026-10-17. [runtime.md](runtime.md) explains how the copy was made.

## Ideas worth taking

You don't need the whole thing. Most visitors will want one or two of these:

- **One contract, four runtimes.** Every agent reads the same [AGENTS.md](AGENTS.md). Each runtime adds only a
  few lines of its own, so changing a rule means editing one file.
- **Privacy gates that fail closed.** Hooks inspect outbound commands (`git push`, `gh` writes) and refuse
  when a scan finds something, fails or times out. A scanner error never counts as a clean result. The verdict
  policy is [proved in Bend](claude/hooks/privacy-decision/README.md) and compiled into a shell table.
- **Memory as one-line notes.** [OptMem](memory/optmem/README.md) stores facts, state, events and pointers as
  280-byte lines in an append-only log. A hook prints the relevant ones when a session starts. Long documents
  live elsewhere, and the log points to them.
- **One claimer for queued work.** Agents, the operator and a messaging assistant file Linear tickets. A single
  [dispatcher](work/README.md) claims each one and starts a fresh worker over a forced-command SSH key. A
  ticket counts as done when the worker posts a signed outcome comment, not when its process exits.
- **Phone approvals only where they matter.** The operator's request is enough for deploys and root work.
  Four things still need a tap on the phone: spending money, sending messages as the operator, disclosing
  secrets, and destruction with no way back.
  [Rulings](decisions/2026-10-13-four-tap-only-gates.md).
- **Free models in a sandbox.** Free-tier harnesses run inside a [bubblewrap silo](decisions/2026-09-27-free-model-silo.md)
  with a fake home directory and a filtered network, because they had been attaching private files to prompts.
- **Rules that say when to drop them.** Each of the [decision records](decisions/README.md) gives the rule,
  the failure that produced it, and the evidence that would justify reopening it.

## How it fits together

```text
              AGENTS.md (one contract)
                        │
     ┌──────────────┬───┴──────────┬──────────────┐
  Claude Code     Codex       DeepSeek         Kimi
     │ hooks: memory wake, privacy gates, compaction restore
     ▼
  OptMem notes ◀── written by primaries, proposed by delegates
     │ points to
     ▼
  notes tree · team Obsidian vault · decision records

  operator / assistant / agents ──ticket──▶ Linear ──webhook──▶ dispatcher ──SSH──▶ worker (laptop | vps)
                                                                     ▲                    │
                                                    phone approval ──┘     signed outcome ┘
```

## What's inside

| Folder | Contents |
|---|---|
| [AGENTS.md](AGENTS.md) | The shared contract: principles, approval boundaries, memory and ledger rules |
| [claude/](claude/README.md) | Agent definitions, hooks, privacy gates and their tests, example settings |
| [codex/](codex/README.md) | Roles, hooks and a link-only installer with an offline `--check` |
| [deepseek/](deepseek/README.md), [kimi/](kimi/README.md) | Primary profile and installer; provider config |
| [memory/](memory/README.md) | OptMem method and Bend selection layer; the team vault's rule book, sweep and MCP server |
| [work/](work/README.md) | Webhook receiver, dispatcher, workers, phone approval gate, alarms |
| [assistant-bridge/](assistant-bridge/README.md) | Gives a messaging-only assistant a reviewed slice of the vault and lets it file tickets and open PRs |
| [delegation/](delegation/README.md) | Codex tiers, DeepSeek routes, the free-model silo, a portable `codex-run.py` |
| [skills/](skills/README.md) | Research atlases, outreach, triage, deployment, session continuity, visuals |
| [reference/](reference/README.md) | The documents the contract opens on cue |
| [decisions/](decisions/README.md) | 29 rulings with reasons and reopening bars |
| [integrations/](integrations/README.md) | Portable hook adapters for wiring the same contracts to your own scripts |

## Using a piece of it

1. Start with [AGENTS.md](AGENTS.md) and change the approval boundaries to fit you: who approves, what counts
   as irreversible, which providers are off limits.
2. Take one layer at a time. Each folder's README lists its dependencies, how its parts talk to each other,
   and which values are placeholders (`.example` files show the shape).
3. Merge settings into your own files rather than replacing them, and approve hook trust in each runtime
   yourself.

Cloning the repo installs nothing and starts nothing. The runtimes, OptMem, Obsidian, Linear, ntfy and the
assistant are external services; this tree holds the contracts and glue around them.

## What to expect

- Names are pseudonyms: "the operator", "the company", "the assistant", machines `laptop` and `vps`.
  Ticket numbers appear as dates or `ABC-1`.
- It is a snapshot. The live setup keeps changing, and model names and versions date quickly.
- Some parts only make sense in context: the work system assumes a VPS and a tailnet, and the vault layer
  assumes a team.

## Validation

Python 3.11+:

```sh
python3 scripts/check_setup.py     # structure and links
python3 scripts/test_adapters.py   # adapter boundaries, offline
```

Components with their own tests name the runner in their README. Everything runs offline with stubs; CI runs
the same checks.

## License

[MIT](LICENSE). Upstream projects are linked, not copied, and keep their own licenses.
