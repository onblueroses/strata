# How to read this snapshot

Snapshot of 2026-11-12. This is an anonymized copy; names, hosts and numbers are placeholders.

## What a reader should assume

- Code is kept as it runs. Private values are placeholders or environment variables documented in an
  `.example` file next to the code.
- Rulings keep their dates and reasons.
- Private services appear as their interface: the contract the code depends on, plus the portable
  implementation where one exists in this tree.
- Security-relevant parts (guards, gates, approvals, privileges, the routes from outside text into an agent,
  backups) appear as design only: a README that says what the part is for, which parts it talks to and what
  it guarantees. Their code and configuration stay private.
- The operator is "the operator"; the two machines are `laptop` and `vps`; the team is "the company"; the
  messaging assistant is "the assistant".
- Ticket references appear as the ruling's date or as `ABC-1`.
- Public products are named where they are the method: Claude Code, Codex, DeepSeek, Kimi, OptMem, Obsidian,
  Linear, GitHub, systemd, ntfy, Bend, a tailnet.
- Model names are the vendors' public names and change with the vendors.
- Installed does not mean running. The example units and registrations are shapes; enabling any of them is the
  adopter's deliberate step.

## Validation

`scripts/check_setup.py` checks the tree's structure and links; `scripts/test_adapters.py` and the test files
beside each component run offline with stubs. A private check runs before publication.
