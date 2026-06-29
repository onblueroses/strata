#!/usr/bin/env python3
"""Per-channel true-cost ledger for a session, computed downstream from captured tokens.

Dollars are never stored in events; they are derived here from a correctable rate table
(model_rates.json). Three channels are summed bottom-up:
  - main_loop   : session-metrics.jsonl record .tok_by_model
  - subagents   : same record .subagents.tok_by_model
  - delegations : events.jsonl delegation events joined by sid (.tokens or .tokens_total)

Reports cost_notional (ALL channels priced at reference rates — the comparable yardstick) and
cost_real (only channels whose rate table marks billing="marginal", i.e. actual cash). Any
other billing value (e.g. a flat-plan "subscription") contributes to notional only, never to
real. Output is the 3-row ledger plus cap_pct (main_loop share) and invisible_leg_pct
(delegations share, the compute that runs outside the main loop).

Telemetry is opt-in: it is written only when STRATA_TELEMETRY=1 at emit time. This reader runs
on demand over whatever the sink already contains and never assumes telemetry is enabled.

Usage:
  cost_rollup.py <sid>        # one session
  cost_rollup.py --aggregate  # totals across session-metrics.jsonl
"""

import sys
import os
import json

# Runtime path contract — matches telemetry-emit.sh. STRATA_HOME defaults to the parent of this
# script's directory (the script ships at $STRATA_HOME/telemetry/cost_rollup.py).
_HERE = os.path.dirname(os.path.abspath(__file__))
STRATA_HOME = os.environ.get("STRATA_HOME") or os.path.dirname(_HERE)
KB_DIR = os.environ.get("KB_DIR") or os.path.join(STRATA_HOME, "workspace")
STATE_DIR = os.environ.get("STATE_DIR") or os.path.join(KB_DIR, "state")
TEL_DIR = os.environ.get("STRATA_TELEMETRY_DIR") or os.path.join(STATE_DIR, "telemetry")

# Live event/metric streams live under the runtime telemetry sink; the rate table is a tracked
# template shipped in the install tree.
RATES_PATH = os.path.join(STRATA_HOME, "telemetry", "model_rates.json")
METRICS = os.path.join(TEL_DIR, "session-metrics.jsonl")
EVENTS = os.path.join(TEL_DIR, "events.jsonl")

# Fallback when a model is absent from model_rates.json. Rates are placeholder zeros: populate
# model_rates.json with your provider's per-million-token numbers. billing defaults to the
# non-cash value so an unknown model never inflates cost_real (actual cash).
DEFAULT_RATE = {
    "in": 0.0,
    "cache_read": 0.0,
    "cache_write": 0.0,
    "out": 0.0,
    "billing": "subscription",
}


def load_rates():
    try:
        with open(RATES_PATH) as fh:
            return json.load(fh)
    except Exception:
        return {}  # basis: missing rate table -> DEFAULT_RATE everywhere, still produces a ledger


def rate_for(model, rates):
    if not model:
        return DEFAULT_RATE
    if model in rates:
        return {**DEFAULT_RATE, **rates[model]}
    for (
        k,
        v,
    ) in (
        rates.items()
    ):  # prefix match (e.g. "<model-id>-<date-suffix>" -> "<model-id>")
        if model.startswith(k) or k.startswith(model):
            return {**DEFAULT_RATE, **v}
    return DEFAULT_RATE


def _cost_split(t, r):
    """Token dict {input,cache_read,cache_creation,output} -> $ at per-million rates."""
    return (
        t.get("input", 0) / 1e6 * r["in"]
        + t.get("cache_read", 0) / 1e6 * r["cache_read"]
        + t.get("cache_creation", 0) / 1e6 * r["cache_write"]
        + t.get("output", 0) / 1e6 * r["out"]
    )


def cost_by_model(by_model, rates):
    notional = real = 0.0
    for model, t in (by_model or {}).items():
        r = rate_for(model, rates)
        c = _cost_split(t, r)
        notional += c
        if r.get("billing") == "marginal":
            real += c
    return notional, real


def cost_delegations(sid, rates):
    """Delegation-lane cost for this sid from events.jsonl. An event carrying a full token-split
    dict (.tokens) is costed exactly; an event carrying only a total (.tokens_total) is estimated
    at the output rate and flagged."""
    notional = real = 0.0
    n = 0
    estimated = False
    try:
        fh = open(EVENTS)
    except Exception:
        return (
            0.0,
            0.0,
            0,
            False,
        )  # basis: no events file -> zero delegation cost, ledger still valid
    with fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except Exception:
                continue  # basis: skip one malformed JSONL line; a read-time tool never aborts
            if ev.get("kind") != "delegation" or ev.get("sid") != sid:
                continue
            r = rate_for(ev.get("model"), rates)
            tk = ev.get("tokens")
            if isinstance(tk, dict):  # full token split -> exact cost
                c = (
                    tk.get("input", 0) / 1e6 * r["in"]
                    + tk.get("cache_read", 0) / 1e6 * r["cache_read"]
                    + tk.get("output", 0) / 1e6 * r["out"]
                )
                n += 1
            elif ev.get("tokens_total"):  # total only -> estimate at output rate
                c = ev["tokens_total"] / 1e6 * r["out"]
                estimated = True
                n += 1
            else:
                continue  # event without token counts (e.g. duration-only); skip
            notional += c
            if r.get("billing") == "marginal":
                real += c
    return notional, real, n, estimated


def ledger_for(rec, rates):
    sid = rec.get("sid")
    main_n, main_r = cost_by_model(rec.get("tok_by_model"), rates)
    sub = rec.get("subagents") or {}
    sub_n, sub_r = cost_by_model(sub.get("tok_by_model"), rates)
    dl_n, dl_r, dl_count, dl_est = cost_delegations(sid, rates)
    total_n = main_n + sub_n + dl_n
    return {
        "sid": sid,
        "project": rec.get("project"),
        "channels": {
            "main_loop": {
                "cost_notional": round(main_n, 4),
                "cost_real": round(main_r, 4),
            },
            "subagents": {
                "n_agents": sub.get("n_agents", 0),
                "cost_notional": round(sub_n, 4),
                "cost_real": round(sub_r, 4),
            },
            "delegations": {
                "n_dispatches": dl_count,
                "cost_notional": round(dl_n, 4),
                "cost_real": round(dl_r, 4),
                "estimated": dl_est,
            },
        },
        "total_cost_notional": round(total_n, 4),
        "total_cost_real": round(main_r + sub_r + dl_r, 4),
        "cap_pct": round(100 * main_n / total_n, 1) if total_n else 0.0,
        "invisible_leg_pct": round(100 * dl_n / total_n, 1) if total_n else 0.0,
        "headline_output_tok": rec.get("tok_output", 0),
    }


def load_metrics():
    recs = {}
    try:
        for line in open(METRICS):
            try:
                r = json.loads(line)
            except Exception:
                continue  # basis: skip one malformed JSONL line; a read-time tool never aborts
            recs[r.get("sid")] = r  # last wins (dedup)
    except Exception:
        pass  # basis: unreadable metrics file -> empty dict, caller reports "no session_metrics"
    return recs


def main(argv):
    if not argv:
        sys.stderr.write(__doc__ or "")
        return 1
    rates = load_rates()
    recs = load_metrics()
    if argv[0] == "--aggregate":
        agg = {"main": 0.0, "sub": 0.0, "deleg": 0.0, "real": 0.0, "n": 0}
        for rec in recs.values():
            led = ledger_for(rec, rates)
            agg["main"] += led["channels"]["main_loop"]["cost_notional"]
            agg["sub"] += led["channels"]["subagents"]["cost_notional"]
            agg["deleg"] += led["channels"]["delegations"]["cost_notional"]
            agg["real"] += led["total_cost_real"]
            agg["n"] += 1
        tot = agg["main"] + agg["sub"] + agg["deleg"]
        print(
            json.dumps(
                {
                    "sessions": agg["n"],
                    "notional_usd": {
                        "main_loop": round(agg["main"], 2),
                        "subagents": round(agg["sub"], 2),
                        "delegations": round(agg["deleg"], 2),
                        "total": round(tot, 2),
                    },
                    "real_usd_total": round(agg["real"], 2),
                    "cap_pct": round(100 * agg["main"] / tot, 1) if tot else 0.0,
                    "note": "delegation costs are joined by session id; events lacking a sid are not attributed.",
                },
                indent=2,
            )
        )
        return 0
    sid = argv[0]
    rec = recs.get(sid)
    if not rec:
        sys.stderr.write(f"no session_metrics for sid {sid}\n")
        return 1
    print(json.dumps(ledger_for(rec, rates), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
