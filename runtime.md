# How this snapshot was made

Snapshot date: 2026-10-17. This repository is a derived copy of one operator's agent estate. A derivation step
copies the estate's files, applies a consistent pseudonym map, and the result is read file by file before it is
published. The estate is the source; this tree follows it.

## What the derivation does

- Keeps code as it runs, with private values (accounts, hosts, addresses, topics, folders under a home)
  replaced by placeholders or environment variables documented in an `.example` file next to the code.
- Keeps rulings with their dates and reasons.
- Replaces private services by their interface: the contract the live code depends on, plus the portable
  implementation where one exists in this tree.
- Carries the method and the glue: contracts, code, units, rules and the reasons behind them. Where a
  component needs data to run, its shape is described beside the code and an `.example` file shows it.

## What a reader should assume

- The operator is "the operator"; the two machines are `laptop` and `vps`; the team is "the company"; the
  messaging assistant is "the assistant". These names are consistent across the tree.
- Ticket references appear as the ruling's date or as `ABC-1`.
- Public products are named where they are the method: Claude Code, Codex, DeepSeek, Kimi, OptMem, Obsidian,
  Linear, GitHub, systemd, ntfy, Bend, a tailnet.
- Model names are the vendors' public names and change with the vendors.
- Installed does not mean running. The example units and registrations are the shapes the live estate uses;
  enabling any of them is the adopter's deliberate step.

## Validation

`scripts/check_setup.py` validates the tree's structure and links; `scripts/test_adapters.py` and the test
files beside each component run offline with stubs. Privacy checks on the operator's side gate every publish;
they complement review and are not a proof that arbitrary future content is safe to publish.
