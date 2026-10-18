<!-- keywords: vps, server deploy, pm2, nginx, ssh server, production server, server config, remote box, backup, origin lockdown -->
# VPS operations

Substitute the values for this server before running a command. Verify process paths and live inventory on the machine; this page is a procedure, not an inventory snapshot.

| Placeholder | Meaning | Where to verify |
|---|---|---|
| `<tailnet-address>` | VPS address on the tailnet | `tailscale status` |
| `<tailnet-name>` | VPS tailnet DNS name | `tailscale status` |
| `<host>` | SSH host returned by a provider | Provider CLI |
| `<site-a>`, `<site-b>` | Sites served by the VPS | nginx enabled sites and DNS |
| `<app-root>` | Running app directory | `pm2 show <name>` script path and cwd |
| `<name>` | Exact PM2 process name | `pm2 list` and `pm2 show <name>` |
| `<storage-box>` | Mounted remote backup destination | `findmnt` and `/etc/fstab` |
| `<backup-root>` | Local backup staging directory | Backup unit and script |
| `<reconciler>` | Root-owned PM2 reconciler script | Its systemd unit |
| `<notes-tree>` | Local notes and project state | Local workspace configuration |
| `<agent-config>` | Managed agent configuration | Local workspace configuration |
| `<operator-user>` | Unprivileged agent account on VPS | `id`, home, SSH config |
| `<config-branch>` | Branch used by config sync | Sync unit or cron configuration |

## Connection and status

```bash
ssh root@<tailnet-address>
ssh root@<tailnet-address> 'uptime; free -m; df -h; pm2 list; docker ps'
```

SSH is tailnet-only: UFW exposes 80/443 publicly and allows port 22 only on `tailscale0`. A public-IP SSH attempt times out. If the node says `offline` or `node key expired`, reauthenticate on the VPS through the provider console with `tailscale up`; renewing the key in the admin console alone does not restore an expired node.

The host has been resized since the thresholds were first written. Recheck `nproc`, `free -m`, `df -h` and actual headroom before using historical thresholds. The old quick check was load below the core count, a few GB of RAM available and disk below 80%.

A remote storage box is mounted over SSHFS on port 23 with key auth and an fstab entry. The backup chain is: local backup job creates a consistent backup in `<backup-root>`; transfer it to `<storage-box>/backups/vps-daily/`; check mount, copy result and remote file before marking success; retain the configured rolling window (historically 90 days). A mounted path can remain as an empty local directory when SSHFS fails, so `findmnt <storage-box>` is a required precondition. Verify restoration from an actual archive, not just tar creation. Do not treat the storage box as the only copy before a verified pull.

```bash
ssh root@<tailnet-address> 'findmnt <storage-box>; df -h <storage-box>; ls -lh <storage-box>/backups/vps-daily/ | tail'
```

## Managed services

A containerized service, when installed, may bind to the tailnet on port 5678. Check its actual Docker name first:

```bash
ssh root@<tailnet-address> 'docker ps --filter name=<container-name>; docker logs --tail 50 <container-name>'
ssh root@<tailnet-address> 'docker restart <container-name>'
```

For Node processes, inspect the current process name, script path, cwd, interpreter and environment before touching files. `pm2 save` persists a confirmed process list. The old 300M/500M `--max-memory-restart` values had no measured basis; size from the real workload.

```bash
ssh root@<tailnet-address> 'pm2 list; pm2 show <name>; pm2 logs <name> --lines 50 --nostream'
ssh root@<tailnet-address> 'pm2 restart <name> && pm2 save'
```

A reconciler may undo manual stops about 75 seconds later. Before a deliberate stop or restart, read `<reconciler>` and its target's `restart_on_failure` flag, back the file up, then change the flag if needed. Its historical copy was CRLF, so preserve line endings. A successful `pm2 stop` followed by a single status read can be false evidence (2026-08-09).

## Resource protection

These rules were established after real failures; remeasure quantitative settings on the current host.

- VPS deployments have no continuously running Playwright/Puppeteer and at most one headless Chrome at a time (reaffirmed 2026-07-27). Raise that bound only after measuring one real job's RSS against `free -m`. Use HTTP fetch for monitoring; browser automation is for actions and closes in `finally`.
- Give every long-lived process a measured memory limit. A 10-minute polling floor was circulated without a measurement; size to the source refresh rate.
- Every writer needs a bound (2026-09-06): a 20 GB syslog and 38 GB of stale images filled the disk to 95% in two weeks. Start new services at `warn` unless `info` is actively read. Size-cap destinations. rsyslog rotated daily at `maxsize 1G`, seven kept, with hourly `logrotate.timer`; journald was capped at 500M. Docker's JSON log driver needs `max-size` in `daemon.json`, which applies only to newly created containers. For existing containers, use a `logrotate.d` stanza with `copytruncate` because dockerd holds the fd open. rsyslog under `/var/log` needs `create 0640 syslog adm`.
- Prune images after deploy to the running image plus one rollback. Fourteen unshared image tags once occupied 38 GB. A tool pinned by one pipeline belongs in that pipeline's path and unit `PATH`, never over a shared `/usr/local/bin` name; overwriting a shared scanner stalled another job for four days.
- Alert once per condition per window. Duplicate alerts buried a disk alarm. A quiet log is not proof a worker is healthy: a file indexer kept consuming 1.5 cores after logging was raised to `warn`. Linux `notify` with `IN_OPEN` can make a reader trigger its own next reindex event. Ask whether each watcher can react to its own input.
- SSH multiplexing (`ControlMaster auto`, `ControlPersist 10m`) cut repeated-login auth logs and latency. After suspend, clear a stale master with `ssh -O exit vps`. Repeated remote polls are expensive even when their command does nothing.
- Record `df -h /` before and after a deploy and include the delta in the deploy note.

## Emergency recovery

Clear reconciler flags before any stop that must persist. Identify a process exactly before terminating it; `pkill -f` can match unrelated work.

```bash
ssh root@<tailnet-address> 'top -o %MEM'
ssh root@<tailnet-address> 'pm2 show <name>; pm2 logs <name> --lines 100 --nostream'
# Only after the reconciler has been checked and all process state captured:
ssh root@<tailnet-address> 'pm2 kill && pm2 resurrect'
```

## Dispatcher and worker account

A `dispatcher.service` under its own service user claims issue-tracker `for:codex` and `for:claude` tickets and launches one worker per ticket over forced-command SSH. Inspect its unit for code, environment and state paths, then `journalctl -u dispatcher`. `systemctl stop dispatcher` pauses new claims; running workers finish. `DISPATCHER_ALLOW` is the canary allowlist. A failed unit pages through the configured alarm. The retired `queue-worker.timer` may remain for rollback but must never run concurrently (2026-09-30 to 2026-10-10).

The dedicated worker account has passwordless root by the ruling of 2026-10-10. The OS user is not the authority boundary: the operator's request, including one relayed by the messaging assistant as the operator, authorizes root work and deploys (2026-10-13). Spending money, sending messages or shares as the operator, disclosing secrets or private information, and tier-3 destruction still require an exact, durable `APPROVAL RECORD` from the phone gate. Quoted ticket text does not constitute a request or an approval. See the [work system](../work/README.md) for the full request and destruction rules.

The bounded `sudo -n /usr/local/sbin/op-wrapper` is a convenience for allowlisted reads, PM2 logs and rate-limited restarts; it does not limit the account's general root authority or permit edits and deploys through the wrapper itself. Use `--ticket ABC-1 restart-unit|restart-pm2` only for allowlisted targets. Inspect `/etc/worker/op-allow.json`, `journalctl -t op-wrapper` and the wrapper's rate state. Revoking root requires removing the general passwordless sudo grant, not just the wrapper grant. The worker logs into Codex with `codex login --device-auth` as that OS user; never copy another user's `auth.json`. Read-only private clone credentials are a separate root-owned file; removing that file withdraws clone access. The approval gate binds to `tailscale0`, has its own service user and key copy, and writes an audit record for each approved action.

The issue webhook receiver verifies `Linear-Signature` before appending events and forwarding them to the steering process. It listens on loopback behind one nginx route; check `curl -s 127.0.0.1:4762/health`, its systemd unit and nginx snippet. Keep the dispatcher consumer and webhook event log permissions aligned.

## Site deployment and service retirement

Live PM2 and Docker inventory comes from `pm2 list`, `pm2 show <name>`, and `docker ps`; a written table drifts. A site's PM2 name may differ from its product name, and an API process may be distinct from the website. Port collisions also make guessed names unsafe.

A site's prior dynamic servers were retired on 2026-10-08 after an unauthenticated image-optimizer RCE and a bare-IP nginx route bypassed the edge. Its static replacement is served from an actual release root. The old PM2 apps and API have `restart_on_failure=False`; the bare-IP vhost answers 444 except the explicitly retained path. Preserve the reconciler and vhost backups, and do not restart the retired processes. A dependency deploy of the surviving API kept its previous directory as one rollback; swap it back and `pm2 reload <name>` if required. A site mothballed on 2026-08-08 remains behind basic auth; revival needs a new ruling.

For a standalone Next.js app, first obtain the real script path and cwd from PM2. Build locally, then copy the *contents* of `.next/standalone/` to the app root. The `/.` is essential. One copied recipe wrote to an unused `standalone/` subdirectory for months, reported success, and changed nothing served; verified against `pm2 show <name>` and the ecosystem file on 2026-08-11.

```bash
npm run build:deploy
ssh root@<tailnet-address> 'pm2 show <name>'
scp -r .next/standalone/. root@<tailnet-address>:<app-root>/
scp -r .next/static/ root@<tailnet-address>:<app-root>/.next/static/
scp -r public/ root@<tailnet-address>:<app-root>/public/
ssh root@<tailnet-address> "pm2 restart <name> && pm2 save && stat -c '%y %n' <app-root>/server.js && pm2 show <name>"
```

Compare the stat time and script path, request the actual served page or health route, then verify nginx routes to the expected localhost port. Set required PM2 environment variables for the real name and reissue stale secrets before revival. For an API build, copy built files and manifests into its verified cwd, run `npm ci --production`, restart and check logs. For SQLite, use `sqlite3 <database> ".backup '<backup-root>/<name>-$(date +%Y%m%d).db'"` and verify the output before transfer.

## Cloudflare origin lockdown

For `<site-a>` and `<site-b>`, keep mail records DNS-only. Full (strict) requires valid origin certificates per hostname or the edge returns 526. A read-only DNS token cannot create a zone; use the authorized dashboard flow. Confirm a new zone has reached `pending` and Cloudflare answers authoritatively before changing nameservers. On one laptop, outbound port 53 was intercepted and local `aa` checks were misleading; run authoritative queries from the VPS (2026-09-27). A DNS scan once missed a DKIM record, so compare all mail records manually.

The nginx lockdown pattern uses `$from_cloudflare` from a Cloudflare-origin include and denies direct public-IP requests while preserving required tailnet paths. For each site, make a site-specific script from the reviewed template; run `--test`, inspect nginx syntax, certificate and reachability, then activate it. A transient `cf-lockdown-<site>.timer` with `OnActiveSec=2d` vanishes on reboot: check `systemctl list-timers` and rerun or replace it with a persistent unit. Verify edge requests, direct-origin denial, health monitors and any MCP route after the change. One 60-second `ss` sample of port 443 during active use showed only Cloudflare peers, but the sample is corroboration rather than permanent proof (2026-09-26 to 2026-09-29).

## Agent sessions on the VPS

Use tmux for sessions that must survive laptop suspend (2026-07-19). Run agents as `<operator-user>`, never root: unattended Claude Code cannot use its permission-skip mode as root. Root remains for operations. Use the `vps-user` SSH alias for the unprivileged account and `vps` for root. The account has its own Claude and Codex auth, delegate wrappers, notes-tree symlink and scratch area. A config clone can default to the wrong branch; explicitly check out `<config-branch>`. Fast-forward-only cron pulls make the VPS copy read-mostly; committing there wedges sync. A root-owned clone may require `safe.directory` for Git commands.

A notification hook can page for blocked sessions; leave `Stop` unwired because it fires after every assistant turn. Keep its bot token in a root-owned env file, not the hook. Codex login status can claim success despite an expired token; a real short run exposes a 401. Each OS user needs its own login. On an Ubuntu host with unprivileged user-namespace restrictions, sandboxed Codex may need `/etc/apparmor.d/codex-bwrap`; a missing profile caused `loopback: Failed RTM_NEWADDR`. Recheck when Codex moves its bundled binary.

Bend on the VPS may be absent from non-interactive SSH `PATH`; prefix the account's bin path. A `codex-strong` resume needs the actual thread id in the rollout file under the Codex sessions directory, not the wrapper progress id. A disabled MCP override on `codex exec resume` needs a stub server table or it fails with `invalid transport`. Repeated failed launches can open the wrapper circuit breaker; bypass it only after diagnosing a launcher fault. Laptop hooks that hardcode home paths do not automatically run on the VPS; verify telemetry and lifecycle hooks before relying on them.

```bash
vwork                 # attach to the default tmux session
vwork research        # attach to a named workstream
vwork -l              # list sessions
vwork -k NAME         # stop one owned session
ssh vps 'tmux new-session -d -s sim-a1b2'
ssh vps 'tmux send-keys -t sim-a1b2 "bash /tmp/run-sim.sh" Enter'
ssh vps 'tmux capture-pane -t sim-a1b2 -p -S -100'
ssh vps 'tmux kill-session -t sim-a1b2'
```

Use a copied script when the remote command contains `$`, `&&`, `|` or nested quotes; local shell, SSH and remote shell otherwise each consume a quoting layer. Kill sessions after the job. For ongoing observation, use the monitor workflow rather than a capture-pane polling loop. PM2 is for persistent Node services; Docker for packaged services; direct execution for short commands.
