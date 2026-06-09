# Context Doc Router v2 Eval Results

Matcher: `router-combo` (mirrors the shipped hook `hooks/context-doc-router.py`)
Split: `score`
Fixtures: 26 score / 12 tune

## Score

| Metric | Value |
|---|---:|
| Aggregate macro F1 | 0.859 |
| p95 latency | ~20 ms |
| Cost | $0 (no network, no embedding service) |

Baseline for comparison: the keyword-only matcher (prompt-vocabulary match, the previous router) scores far lower on these realistic keyword-sparse prompts — work-context routing is the lift.

## Per-Family F1

| Family | F1 |
|---|---:|
| agent-architecture | 1.00 |
| agent-taxonomy | 1.00 |
| claude-code | 1.00 |
| codex | 0.89 |
| dmux | 1.00 |
| eval-methodology | 1.00 |
| gpu-training | 0.89 |
| knowledge-management | 1.00 |
| mcp-development | 1.00 |
| model-delegation | 0.67 |
| node | 0.67 |
| null | 1.00 |
| rust | 0.67 |
| skill-design | 0.67 |

`null` = prompts that should route nothing; F1 1.00 means the router stays correctly silent (no false fires — the precision floor matters most: a mis-fire trains the reader to ignore the channel).

## Why Router-Combo Wins

`router-combo` unions three cheap signals that cover different failure modes: cwd paths catch project-local intent, recent edits catch terse follow-up prompts, and pure-Python lexical routing (TF-IDF cosine with a ≥2-token corroboration guard + a strong-solo single-token bypass) catches explicit topic requests without network calls or paid embedding infrastructure. The result is free, deterministic, and fast enough for hook-time use (p95 ~20 ms). The lexical branch here is byte-for-byte the logic the live hook runs, so this number describes the router that actually ships.

## Tuning the router for your own docs

The highest-leverage lever is each doc's line-1 `<!-- keywords: ... -->`: fill it with the natural vocabulary a user would actually type (not just the doc's title words). After editing keywords or `INDEX.md`, run `build-lex-cache.py` to rebuild `.lex-cache.json` (the hook reads the committed cache; it does not self-rebuild). Add fixtures to `fixtures.jsonl` for any routing you care about and re-run `run-eval.py router-combo` to catch regressions.
