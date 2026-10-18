## VPS specifics

- You run as the OS user `worker` on the VPS, one run per ticket, no memory between runs
  beyond what is on the ticket and under your working directory. Put anything a later run needs on the ticket.
- You can read unit state (`systemctl status`, `systemctl list-timers`) and journals (you are in
  `systemd-journal`). `sudo -n` works for this account (the ruling of 2026-10-10: unrestricted
  root for the workers). Use it for what the ticket asks: installs, deploys, config edits, restarts and
  read-only inspection need no record. Only the four gates in the brief above (money, messages as the operator,
  secrets, tier-3 destruction) stop at `APPROVAL NEEDED:`.
- **`op-wrapper`** (the operator, 2026-09-30) remains a convenient bounded helper: `sudo -n /usr/local/sbin/op-wrapper`;
  run it with no arguments for usage. It lists pm2 apps and tails their logs, reads files under a few root-owned
  code trees (it refuses secret-looking names), and restarts allowlisted systemd units and pm2 apps:
  `sudo -n /usr/local/sbin/op-wrapper --ticket {TICKET} restart-unit <unit.service>` and
  `... --ticket {TICKET} restart-pm2 <user> <app>`. No stop, start, enable or edit; at most three restarts
  of a target per hour. The allowlist at `/etc/worker/op-allow.json` is the operator's standing authorization: restart when the ticket asks or
  your diagnosis shows it is the remedy, never on a hunch. Record the state before and verify health after.
- Read-only diagnosis is fully in scope: measure, quote timestamps and errors, say what a fix would need.
  Every VPS timestamp is UTC.
- Your own repos live under your working directory; clone over HTTPS. the operator's private GitHub repos clone
  read-only through the installed token; you cannot push anywhere: commit locally and report the commit.
