# systemd units

User-level systemd units for optional scheduled maintenance. They ship **disabled**: copy the ones you want into `~/.config/systemd/user/` and enable them by hand.

## memory-eval

Runs the native memory eval probe registry (`memory/eval/probe_runner.py`) on a weekly timer, so retrieval quality is tracked over time. Off by default.

```bash
cp systemd/memory-eval.service systemd/memory-eval.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now memory-eval.timer
```

The unit assumes `STRATA_HOME=~/.strata` (the default). When you install strata elsewhere, edit `WorkingDirectory` and `Environment=STRATA_HOME=` in `memory-eval.service` to match. Eval output lands in `$STATE_DIR/telemetry/memory-eval.jsonl` and the journal (`journalctl --user -u memory-eval`).
