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
  cost_rollup.py --aggregate  # totals across recorded sessions
"""

import sys
import os
import json
import gzip
import glob
import re

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

DATE_SUFFIX_RE = re.compile(r"^-\d{4}-\d{2}-\d{2}$")


def load_rates():
    try:
        with open(RATES_PATH) as fh:
            rates = json.load(fh)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {RATES_PATH}: {e}") from e
    if not isinstance(rates, dict):
        raise ValueError(f"invalid rate table in {RATES_PATH}: expected object")
    return validate_rates(rates)


def validate_rates(rates):
    valid = {}
    for model, row in rates.items():
        if not isinstance(row, dict):
            continue
        for key in ("in", "cache_read", "cache_write", "out"):
            value = row.get(key, DEFAULT_RATE[key])
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"invalid rate {key!r} for model {model!r} in {RATES_PATH}: expected number"
                )
        billing = row.get("billing", DEFAULT_RATE["billing"])
        if not isinstance(billing, str):
            raise ValueError(
                f"invalid rate 'billing' for model {model!r} in {RATES_PATH}: expected string"
            )
        valid[model] = row
    return valid


def rate_for(model, rates):
    if not model:
        return DEFAULT_RATE
    if isinstance(rates.get(model), dict):
        return {**DEFAULT_RATE, **rates[model]}
    best = None
    for k, v in rates.items():
        if not isinstance(v, dict):
            continue
        suffix = model[len(k) :] if model.startswith(k) else ""
        if DATE_SUFFIX_RE.fullmatch(suffix) and (best is None or len(k) > len(best[0])):
            best = (k, v)
    if best:
        return {**DEFAULT_RATE, **best[1]}
    return DEFAULT_RATE


def jsonl_paths(path):
    base = os.path.splitext(os.path.basename(path))[0]
    archive = os.path.join(os.path.dirname(path), "archive", f"{base}-*.jsonl.gz")
    return sorted(glob.glob(archive)) + ([path] if os.path.exists(path) else [])


def open_jsonl(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt")
    return open(path)


def iter_jsonl(path):
    for jsonl_path in jsonl_paths(path):
        try:
            with open_jsonl(jsonl_path) as fh:
                for line in fh:
                    try:
                        yield json.loads(line)
                    except Exception:
                        continue  # basis: skip one malformed JSONL line; a read-time tool never aborts
        except Exception as exc:
            print(
                f"cost_rollup.py: skipping unreadable telemetry stream {jsonl_path}: {exc}",
                file=sys.stderr,
            )
            continue


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


def cost_delegations(sid, rates, delegations_by_sid=None):
    """Delegation-lane cost for this sid from events.jsonl. An event carrying a full token-split
    dict (.tokens) is costed exactly; an event carrying only a total (.tokens_total) is estimated
    at the output rate and flagged."""
    if not sid:
        return 0.0, 0.0, 0, False
    if delegations_by_sid is None:
        delegations_by_sid = load_delegations()
    notional = real = 0.0
    n = 0
    estimated = False
    for ev in delegations_by_sid.get(sid, ()):
        r = rate_for(ev.get("model"), rates)
        tk = ev.get("tokens")
        if isinstance(tk, dict):  # full token split -> exact cost
            c = _cost_split(tk, r)
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


def round_cost(value, enabled):
    return round(value, 4) if enabled else value


def ledger_for(rec, rates, round_costs=True, delegations_by_sid=None):
    sid = rec.get("sid")
    main_n, main_r = cost_by_model(rec.get("tok_by_model"), rates)
    sub = rec.get("subagents") or {}
    sub_n, sub_r = cost_by_model(sub.get("tok_by_model"), rates)
    dl_n, dl_r, dl_count, dl_est = cost_delegations(sid, rates, delegations_by_sid)
    total_n = main_n + sub_n + dl_n
    return {
        "sid": sid,
        "project": rec.get("project"),
        "channels": {
            "main_loop": {
                "cost_notional": round_cost(main_n, round_costs),
                "cost_real": round_cost(main_r, round_costs),
            },
            "subagents": {
                "n_agents": sub.get("n_agents", 0),
                "cost_notional": round_cost(sub_n, round_costs),
                "cost_real": round_cost(sub_r, round_costs),
            },
            "delegations": {
                "n_dispatches": dl_count,
                "cost_notional": round_cost(dl_n, round_costs),
                "cost_real": round_cost(dl_r, round_costs),
                "estimated": dl_est,
            },
        },
        "total_cost_notional": round_cost(total_n, round_costs),
        "total_cost_real": round_cost(main_r + sub_r + dl_r, round_costs),
        "cap_pct": round(100 * main_n / total_n, 1) if total_n else 0.0,
        "invisible_leg_pct": round(100 * dl_n / total_n, 1) if total_n else 0.0,
        "headline_output_tok": rec.get("tok_output", 0),
    }


def load_metrics():
    recs = {}
    for r in iter_jsonl(METRICS):
        sid = r.get("sid")
        if sid:
            recs[sid] = r  # last wins (dedup)
    return recs


def load_delegations():
    delegations_by_sid = {}
    for ev in iter_jsonl(EVENTS):
        if ev.get("kind") != "delegation":
            continue
        sid = ev.get("sid")
        if sid:
            delegations_by_sid.setdefault(sid, []).append(ev)
    return delegations_by_sid


def main(argv):
    if not argv:
        sys.stderr.write(__doc__ or "")
        return 1
    rates = load_rates()
    recs = load_metrics()
    delegations_by_sid = load_delegations()
    delegation_sids = set(delegations_by_sid)
    if argv[0] == "--aggregate":
        agg = {"main": 0.0, "sub": 0.0, "deleg": 0.0, "real": 0.0, "n": 0}
        for sid in sorted(set(recs) | delegation_sids):
            rec = recs.get(sid) or {"sid": sid}
            led = ledger_for(
                rec, rates, round_costs=False, delegations_by_sid=delegations_by_sid
            )
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
    if not rec and sid in delegation_sids:
        rec = {"sid": sid}
    if not rec:
        sys.stderr.write(f"no session_metrics for sid {sid}\n")
        return 1
    print(
        json.dumps(
            ledger_for(rec, rates, delegations_by_sid=delegations_by_sid), indent=2
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
