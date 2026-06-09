# Matcher interface

A matcher is an executable at `matchers/<name>.{py,sh}`. It reads one JSON object
on **stdin** (the hook's payload) and writes one JSON object on **stdout**.

## Input (stdin)
```json
{ "prompt": "<user prompt>", "cwd": "<absolute path>", "transcript_path": "<path to session JSONL, may be absent>" }
```

## Output (stdout)
```json
{ "docs": [ { "name": "voice.md", "score": 0.82, "signal": "tfidf" } ],
  "matcher": "<name>", "latency_ms": 12 }
```
- `docs`: matched reference files (basename), each with a `score` in [0,1] and the `signal` that fired.
- Empty result is `"docs": []`.
- On internal failure: still `exit 0`, emit `"docs": []` plus `"error": "<msg>"`. Never crash, never write to stderr in the hook path.

## Scoring (run-eval.py)
Set-based precision/recall/F1 of `docs[].name` vs the fixture's `expected_docs`.
- expected == [] (null fixture): F1 = 1.0 iff predicted == []; else F1 = 0.0 (penalizes false fires).
- expected != [], predicted == []: F1 = 0.0.
- otherwise standard set P/R/F1.
Aggregate F1 = macro mean over fixtures. Per-family F1 = macro mean within family.
`oracle` is a built-in sanity matcher (returns expected_docs) — F1 must be 1.0.
