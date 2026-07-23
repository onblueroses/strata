# bin/ conventions

Symbolic model-lane wrappers (`strong`, `fast`, `grader`, `breadth`) plus
`strata-init` and `dmux-dispatch.sh`. The wrappers are thin shims over
`lib/agent.py`. The lane contract they must honor (interface, exit codes,
stdout/stderr split, provider routing) is specified in repository-root
`CONFIG.md`; keep the shims faithful to it.

## Local invariants

- **`lib/agent.py` is outside the lint and type baseline.** `ruff.toml` and
  `pyrightconfig.json` both exclude it, so the write-time lint hook, `ruff check
  .`, and scoped `pyright` all skip it. Editing it means no automatic feedback;
  change it conservatively and smoke-test a wrapper by hand.
- **Exit codes are load-bearing.** Callers branch on them: 0 success, 3 =
  throttle or quota exhausted (fall back to a sibling lane). `timeout(124)` is
  remapped to 3 on purpose so callers see one quota-or-timeout signal. Preserve
  the semantics table in repository-root `CONFIG.md`.
- **No model ids, no keys in the shims.** Provider is selected by model-id prefix
  inside `lib/agent.py`; bindings live in `config/model-map.toml`; API keys
  resolve from `.local/.env` (gitignored). Reference the symbolic lane, never a
  concrete model.

## Local checks

```
./bin/strong --help                                  # wrapper smoke test
python3 -m pytest tests/test_agent_prompt_file_error.py -q   # agent prompt-file path
```
