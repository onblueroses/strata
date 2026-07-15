---
name: recall
description: "Deep on-demand memory PULL over the user's memory cards and entity summaries. Reformulates a query into concrete search angles, runs the native daemonless engine through recall.py, then dispatches the read-only memory-recall judge to read candidate bodies and return only the genuinely relevant subset with a one-line reason each. Use for conceptual, ambiguous, or paraphrased queries that the SessionStart digest does not surface. Manual: invoke when the user wants to surface a remembered preference, constraint, prior decision, or feedback card whose wording they can describe by intent rather than exact keywords. Triggers on: 'do I have a memory about ...', 'what did I say about ...', 'recall ...', '/recall ...', 'is there a card on ...'."
---

# /recall: Deep memory pull

`/recall <query>` is the query-time retrieval path for the native memory system. It reaches cards the SessionStart digest does not list, including cards that share no distinctive keyword with the query.

The ambient per-prompt router was retired as measured noise. Memory is now PULL-only, and nothing is pushed into a prompt except the SessionStart digest.

**Goal:** Return the memory cards that genuinely answer `<query>`, surfaced by reformulating intent into the cards' vocabulary and confirmed against the card bodies.

**Success means:** Return a short ranked list of real card IDs, each with its `<card_path>` and a one-line reason, or state plainly that there are no relevant cards.

**Stop when:** The judge returns its confirmed subset and you relay that subset to the user.

## How it works

Translate the query's intent into concrete angles because the deterministic engine cannot reformulate it. Run the engine over every angle, then give the deduplicated candidates to the isolated read-only judge. The judge reads the bodies and decides true relevance. Reformulation supplies the semantic vocabulary the engine lacks; body-level judging keeps full card bodies out of the main context.

## Steps

1. **Take the query** from the user's `/recall` argument. When the argument is empty, ask the user what to recall in one line, then proceed.

2. **Reformulate the query into 2-4 concrete angles** phrased in terminology a memory card would use. For example, reformulate "background work keeps retrying forever" as `bounded retry policy`, `background job retry limit`, and `retry backoff cap`. Cover distinct senses when the query is ambiguous.

3. **Run the engine over all angles** to build the candidate set:

   ```bash
   export PYTHONPATH="$STRATA_HOME${PYTHONPATH:+:$PYTHONPATH}"
   python3 $STRATA_HOME/memory/recall.py "<angle 1>" "<angle 2>" "<angle 3>"
   ```

   The command prints one JSON array containing a result object per angle. Each hit carries `id`, `score`, `top_terms_score`, `source`, `title`, `snippet`, `path_root`, and `path`. It uses configured embedding fusion when available and BM25 otherwise. When telemetry is enabled, each search emits the `kb_query` envelope.

   Resolve each readable pointer once and call it `card_path`: combine `path_root: "state"` with `$STATE_DIR/<path>`, or combine `path_root: "kb"` with `$KB_DIR/<path>`. Memory cards resolve under `$STATE_DIR/memory/cards/`; entity summaries resolve under `$KB_DIR/{projects,areas}/<name>/summary.md`. Keep the resulting `card_path` verbatim from this point forward. Drop hits whose path fields are null, then deduplicate hits across angles by `card_path`.

4. **Dispatch the `memory-recall` judge** with `subagent_type: "memory-recall"`. Pass the original query plus the deduplicated candidate list. Include `id`, `card_path`, `title`, `snippet`, and `source` for each candidate. The judge uses only Read, Grep, and Glob. It reads candidate bodies, may grep the card corpus to widen the search, and returns the confirmed subset.

5. **Relay the confirmed subset.** Present the judge's returned cards as a compact list: `card_id` - `<card_path>` - why it matches. Reuse every returned `card_path` verbatim. When the judge reports no relevant cards, say so plainly. Complete the recall by surfacing results without proposing writes.

## Boundaries

- Keep the full path read-only. `/recall` reformulates, searches, and surfaces cards. Manual curation owns memory changes; `/recall` never edits, consolidates, or proposes memory mutations. The judge has no shell or write tools by construction.
- Use `/recall` as the on-demand PULL path whenever the SessionStart digest omits a card the user suspects exists. The SessionStart digest remains the only ambient memory injection.
