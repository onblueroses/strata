#!/usr/bin/env python3
"""dispatcher: the one claimer of the Linear issue queue (the ruling of 2026-10-10).

the assistant, the operator, the steering agent and agents file tickets. the steering agent steers them (labels, pins, comments) and never claims.
This service is the only thing that claims: it watches the Linear event log the VPS webhook receiver
writes, reconciles against the board every few minutes, and for each claimable ticket spawns one fresh
worker over SSH, on the VPS by default or on the laptop when the ticket is pinned `laptop` or needs the
Claude engine. The worker ends with a signed outcome comment; the dispatcher verifies that one landed,
and otherwise hands the ticket back (twice without a report routes it `for:operator`).

Routing, all by labels, nothing inferred from the text:
  for:codex   Codex (gpt-6.1-sol) through `codex exec`; the default engine, runs on either machine.
  for:claude  Claude Code headless with Chrome (@Chrome) and app connectors; laptop only.
  laptop/vps  non-routing pins: only that machine takes the ticket; both pins mean neither.

Every comment the dispatcher writes is signed `(dispatcher, YYYY-MM-DD)`; a worker signs
`(worker-vps run-xxxxxx, date)` style, so the approval page and the steering agent can tell who said what.
State: $DISPATCHER_STATE/state.json plus one log per run. Exit non-zero only on infrastructure failure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import secrets
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
import task_approval
import approval_guard

ENGINES = {"for:codex": "codex", "for:claude": "claude"}   # route label -> engine
ENGINE_NAME = {"codex": "worker", "claude": "claude"}         # engine -> signature family
ENGINE_WORDS = {"codex": "Codex through codex exec", "claude": "Claude Code with Chrome"}
MACHINES = ("vps", "laptop")
MACHINE_WORDS = {"vps": "the VPS", "laptop": "the laptop"}
CLAIMABLE_STATES = {"Backlog", "Todo"}
CLAIM_GRACE_SEC = 90          # a foreign Starting younger than this is a claim still landing
MAX_ATTEMPTS = 2
PACKET_COMMENT_LIMIT = 12
REPORT_COOLDOWN_SEC = 24 * 3600
FOLLOWUP_WINDOW_SEC = 14 * 24 * 3600
ASK_WINDOW_SEC = 14 * 24 * 3600
POLL_SEC = 300                # full board reconciliation; events carry the rest within seconds
ASK_POLL_SEC = 5              # a tap on the phone should start its run within seconds (measured 11-40 s at 30)
TICK_SEC = 3
RETRY_WAIT_SEC = 60           # a candidate kept for capacity or an unreachable hand is re-read this often, not every tick
PROBE_TTL_SEC = 60            # how long one reachability answer for a hand is trusted
HAND_BACKOFF_SEC = 900        # after a run that never ran (no ssh, or an engine that could not connect), leave the hand alone this long
SEEN_REPLY_GRACE_SEC = 60     # an outcome posted this long after a reply is taken to have seen it (the brief asks for a re-read)
SIGNED_RE = re.compile(r"\([A-Za-z][\w .:/@-]{0,40}, \d{4}-\d{2}-\d{2}\)\s*$")
ASK_RE = re.compile(r"^APPROVAL NEEDED:[ \t]*(\S.*?)[ \t]*$", re.M)
UUID_RE = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
RUN_RE = re.compile(r"^run-[0-9a-f]{6}$")
WORKER_SIG_RE = re.compile(r"\((worker|claude)-(vps|laptop) run-[0-9a-f]{6}, \d{4}-\d{2}-\d{2}\)\s*$")
TICKET_RE = re.compile(r"^[A-Z]{2,8}-\d{1,6}$")
TEAM_KEY = os.environ.get("DISPATCHER_TEAM_KEY", "ABC")


def log(msg: str) -> None:
    print(f"[dispatcher] {msg}", flush=True)


def today() -> str:
    return dt.date.today().isoformat()


def parse_ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def run(cmd: list[str], *, timeout: int = 60, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input_text)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(shlex.quote(c) for c in cmd[:3])} failed rc={proc.returncode}: "
                           f"{proc.stderr.strip()[:400]}")
    return proc


# ---------------------------------------------------------------- Linear (brain-linear, app identity Dispatcher)

def linear_json(args: list[str], *, timeout: int = 60):
    return json.loads(run(["brain-linear", *args], timeout=timeout).stdout)


def gql(query: str, variables: dict | None = None):
    args = ["gql", query] + ([json.dumps(variables)] if variables else [])
    data = linear_json(args)
    if "errors" in data:
        raise RuntimeError(f"gql errors: {json.dumps(data['errors'])[:300]}")
    return data["data"]


def pickup(runtime: str) -> list[dict]:
    return linear_json(["pickup", runtime]).get("issues", [])


def label_names(issue: dict) -> list[str]:
    labels = issue.get("labels") or {}
    nodes = labels.get("nodes", labels) if isinstance(labels, dict) else labels
    return [l["name"] if isinstance(l, dict) else str(l) for l in nodes or []]


def read_issue(key: str) -> dict:
    issue = gql(
        """query($id:String!){ issue(id:$id){ id identifier title url description createdAt updatedAt priority
             creator{id name} state{name} team{key} labels{nodes{name}}
             comments(first:250){ nodes{ id createdAt body user{id name} } pageInfo{hasNextPage} } } }""",
        {"id": key},
    )["issue"]
    if issue["comments"]["pageInfo"]["hasNextPage"]:
        raise RuntimeError(f"{key} has more than 250 comments; refusing to act on incomplete claim evidence")
    issue["comments"]["nodes"].sort(key=lambda c: parse_ts(c["createdAt"]))   # last:N is not newest-N
    return issue


def comments_of(issue: dict) -> list[dict]:
    return issue.get("comments", {}).get("nodes", [])


def discuss(key: str, body: str) -> None:
    run(["brain-linear", "issues", "discuss", key, "--body", body])


def set_status(key: str, status: str) -> None:
    run(["brain-linear", "issues", "update", key, "--status", status])


def label(key: str, name: str, mode: str) -> None:
    run(["brain-linear", "issues", "update", key, "--labels", name, "--label-mode", mode])


def signature(run_id: str, machine: str, engine: str) -> str:
    return f"{ENGINE_NAME[engine]}-{machine} {run_id}"


def is_signed(body: str) -> bool:
    return bool(SIGNED_RE.search(body.strip()))


def signed_by(body: str, sign: str) -> bool:
    return f"({sign}, " in body.rstrip()[-60:]


# ---------------------------------------------------------------- routing

def engine_of(issue: dict) -> str | None:
    routes = [l for l in label_names(issue) if l.startswith("for:")]
    if len(routes) != 1 or routes[0] not in ENGINES:
        return None
    return ENGINES[routes[0]]


def pins_of(issue: dict) -> set[str]:
    return {l for l in label_names(issue) if l in MACHINES}


def choose_machine(issue: dict) -> tuple[str | None, str]:
    """(machine, reason). Pins win; Claude runs only where its login and Chrome are; the VPS is the default."""
    engine = engine_of(issue)
    if engine is None:
        return None, "not routed to a dispatcher engine (needs exactly one of for:codex, for:claude)"
    pins = pins_of(issue)
    if len(pins) == 2:
        return None, "pinned to both machines, so neither takes it"
    if engine == "claude":
        if pins == {"vps"}:
            return None, "for:claude runs on the laptop only (Claude login and Chrome live there); remove the vps pin or use for:codex"
        return "laptop", "for:claude work runs on the laptop (Chrome and app connectors)"
    if pins:
        m = next(iter(pins))
        return m, f"pinned `{m}`"
    return "vps", "no machine pin, so the VPS default"


def claimable(issue: dict) -> bool:
    return (issue.get("team", {}).get("key") == TEAM_KEY
            and (issue.get("state") or {}).get("name") in CLAIMABLE_STATES
            and engine_of(issue) is not None)


def foreign_fresh_claim(issue: dict) -> str | None:
    for c in reversed(comments_of(issue)):
        body = c["body"].strip()
        if body.startswith("Starting") and not signed_by(body, "dispatcher"):
            if time.time() - parse_ts(c["createdAt"]) < CLAIM_GRACE_SEC:
                return body.splitlines()[-1][:120]
            return None
    return None


# ---------------------------------------------------------------- state

class State:
    KEYS = ("runs", "attempts", "reported", "followups", "followed", "asks", "noted", "noted_at", "history", "task_progress")

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "state.json"
        self.data: dict = {k: {} for k in self.KEYS}
        self.data["history"] = []
        self.data.update({"events_offset": None, "poll_at": 0, "ask_at": 0, "followup_checked": 0})
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except json.JSONDecodeError:
                log("state.json unreadable; starting fresh (old copy kept as state.json.bad)")
                self.path.rename(root / "state.json.bad")

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(self.data, f, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def attempts(self, key: str) -> int:
        return int(self.data["attempts"].get(key, 0))

    def bump(self, key: str) -> int:
        n = self.attempts(key) + 1
        self.data["attempts"][key] = n
        return n

    def active_on(self, machine: str, engine: str | None = None) -> int:
        return sum(1 for r in self.data["runs"].values()
                   if r["machine"] == machine and (engine is None or r["engine"] == engine))

    def running_ticket(self, key: str) -> str | None:
        for run_id, r in self.data["runs"].items():
            if r["ticket"] == key:
                return run_id
        return None


# ---------------------------------------------------------------- events (the webhook receiver's log)

def read_events(state: State, path: Path) -> list[dict]:
    """New JSON lines since the stored offset. A first start begins at the end: the poll covers the backlog."""
    if not path.exists():
        return []
    size = path.stat().st_size
    offset = state.data.get("events_offset")
    if offset is None or offset > size:      # first run, or the log was rotated
        state.data["events_offset"] = size
        return []
    events = []
    with path.open("rb") as f:
        f.seek(offset)
        chunk = f.read()
    last_nl = chunk.rfind(b"\n")
    if last_nl < 0:
        return []
    for line in chunk[:last_nl].split(b"\n"):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line)["event"])
        except (json.JSONDecodeError, KeyError, TypeError):
            log("skipping an unreadable event line")
    state.data["events_offset"] = offset + last_nl + 1
    return events


def event_interest(ev: dict, state: State) -> tuple[str, str] | None:
    """('candidate', key) for a ticket worth a fresh look, ('reply', key) for a reply on a watched ticket."""
    d = ev.get("data") or {}
    if ev.get("type") == "Issue":
        if ((d.get("team") or {}).get("key") or d.get("teamKey")) not in (None, TEAM_KEY):
            return None
        key = d.get("identifier")
        if not key or ev.get("action") not in ("create", "update"):
            return None
        return ("candidate", key)
    if ev.get("type") == "Comment" and ev.get("action") == "create":
        issue = d.get("issue") or {}
        key = issue.get("identifier")
        body = d.get("body") or ""
        if not key or is_signed(body):
            return None
        rep = state.data["reported"].get(key)
        if rep and time.time() - rep["at"] < FOLLOWUP_WINDOW_SEC:
            return ("reply", key)
        return None
    return None


# ---------------------------------------------------------------- briefs and packets

def packet(issue: dict) -> str:
    nonce = os.urandom(6).hex()
    shown = comments_of(issue)[-PACKET_COMMENT_LIMIT:]
    data = {"ticket": issue['identifier'], "url": issue['url'], "title": issue['title'],
            "creator": issue.get('creator'), "state": issue['state']['name'],
            "labels": label_names(issue), "description": issue.get('description'),
            "older_comments_omitted": len(comments_of(issue)) - len(shown),
            "comments": [{k: c.get(k) for k in ('id', 'createdAt', 'user', 'body')} for c in shown]}
    # Escape all data, including line separators, so fetched content cannot introduce
    # a structural packet boundary or a top-level approval line. This is framing,
    # not a sandbox or proof of the authority of a request inside a string.
    return (f"BEGIN UNTRUSTED TICKET PACKET {nonce}\n" + json.dumps(data, ensure_ascii=True) +
            f"\nEND UNTRUSTED TICKET PACKET {nonce}")


def load_brief(briefs: Path, machine: str, engine: str, sign: str, run_id: str, key: str, timeout: int) -> str:
    text = (briefs / "BRIEF.md").read_text()
    for part in (f"BRIEF-{machine}.md", f"BRIEF-{engine}.md"):
        if (briefs / part).exists():
            text += "\n" + (briefs / part).read_text()
    return (text.replace("{MACHINE}", machine).replace("{SIGN}", sign).replace("{RUN}", run_id)
                .replace("{TICKET}", key).replace("{ENGINE}", ENGINE_WORDS[engine])
                .replace("{MINUTES}", str(timeout // 60)))


FOLLOWUP_LEAD = ("FOLLOW-UP: a reply arrived on a ticket a previous run already reported on. Read the newest unsigned "
                 "comment as an answer, a correction or a further request, continue from that earlier outcome "
                 "(do not redo finished work), and end with a new signed outcome comment.\n\n")


def approval_lead(rec: dict) -> str:
    return ("APPROVAL RECORD, placed here by the dispatcher from the approval page that only the operator's phone can reach. "
            f"At {rec.get('at', '?')} the operator approved exactly this action on {rec['ticket']}:\n\n"
            f"    {rec['action']}\n\n"
            "Carry out exactly that, once, and nothing wider; anything beyond it needs a new APPROVAL NEEDED "
            "line. Verify the result and end with a signed outcome comment.\n\n")


# ---------------------------------------------------------------- the dispatcher

class Dispatcher:
    def __init__(self, args):
        self.args = args
        self.state = State(Path(args.state))
        self.briefs = Path(args.briefs)
        self.events_path = Path(args.events)
        self.procs: dict[str, subprocess.Popen] = {}
        self.cap = {"vps": args.cap_vps, "laptop": args.cap_laptop}
        self.timeout = {"vps": args.timeout_vps, "laptop": args.timeout_laptop}
        self.host = {"vps": args.ssh_vps, "laptop": args.ssh_laptop}
        self.candidates: dict[str, float] = {}
        self.allow = {t for t in (args.allow or "").replace(",", " ").split() if t}   # canary mode: only these tickets
        self.claude_since = args.claude_since   # for:claude tickets untouched since before this ISO time were filed under the old meaning
        self.probe: dict[str, tuple[float, bool]] = {}   # machine -> (trust this answer until, reachable)
        self.stopping = False

    @property
    def park_reason(self) -> str:
        return (f"this for:claude ticket was last touched before {self.claude_since[:10]}, when for:claude still meant "
                "\"wait for a Claude session\"; now it runs Claude Code headless on the laptop. Any edit or comment re-activates it; "
                "re-label for:codex for Codex, or for:operator to park it")

    def note_once(self, key: str, why: str) -> None:
        """Say why a ticket is not dispatched, once per reason; a launch clears the note so a later outage speaks again."""
        if self.state.data["noted"].get(key) != why:
            discuss(key, f"Not dispatching: {why}. (dispatcher, {today()})")
            self.state.data["noted"][key] = why
            self.state.data["noted_at"][key] = time.time()
            self.state.save()

    def reachable(self, machine: str) -> bool:
        """ssh to the hand with a verb its forced command rejects: rc 255 means no connection, any other answer means a hand.
        A sleeping laptop or a stopped tailnet then keeps its tickets, replies and approvals waiting instead of burning them."""
        until, ok = self.probe.get(machine, (0.0, True))
        if time.time() < until:
            return ok
        try:
            rc = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", self.host[machine], "ping"],
                                capture_output=True, text=True, timeout=30).returncode
        except (subprocess.TimeoutExpired, OSError):
            rc = 255
        ok = rc != 255
        self.probe[machine] = (time.time() + PROBE_TTL_SEC, ok)
        if not ok:
            log(f"{machine} unreachable (ssh rc 255)")
        return ok

    def full(self, machine: str, engine: str) -> bool:
        """Every launch path asks this: the machine cap, and one browser means one Claude worker at a time."""
        return (self.state.active_on(machine) >= self.cap[machine]
                or (engine == "claude" and self.state.active_on("laptop", "claude") >= 1))

    def hand_for(self, key: str, machine: str, engine: str) -> tuple[str, str]:
        """A reply or an approval runs on the hand that reported, unless the ticket's labels now say otherwise."""
        issue = read_issue(key)
        pins = pins_of(issue)
        if len(pins) == 1:
            machine = next(iter(pins))
        engine = engine_of(issue) or engine
        if engine == "claude":
            machine = "laptop"
        return machine, engine

    # ---- claim

    def claim(self, key: str, run_id: str, machine: str, engine: str, why: str, followup: bool = False,
              approval: dict | None = None) -> dict | None:
        issue = read_issue(key)
        if issue.get("team", {}).get("key") != TEAM_KEY:
            return None
        if approval is not None and (issue['state']['name'] not in CLAIMABLE_STATES
                                     or not approval_guard.matches(approval, issue, self.trusted_author)):
            log(f'{key} approved request changed or is no longer open; no claim')
            return None
        if not self.task_ready(issue) and not followup:
            return None
        if not followup and (not claimable(issue) or choose_machine(issue)[0] != machine):
            log(f"{key} changed before the claim; skipping")
            return None
        if issue["state"]["name"] == "In Progress" or (not followup and issue["state"]["name"] not in CLAIMABLE_STATES):
            log(f"{key} not claimable now ({issue['state']['name']})")
            return None
        other = foreign_fresh_claim(issue)
        if other:
            log(f"{key} freshly claimed elsewhere: {other}")
            return None
        route = next((l for l, e in ENGINES.items() if e == engine))
        if followup:   # a reply reopens the ticket whatever its state; bring the route back
            for l in label_names(issue):
                if l.startswith("for:") and l != route:
                    label(key, l, "remove")
            if route not in label_names(issue):
                label(key, route, "add")
        set_status(key, "In Progress")
        sign = signature(run_id, machine, engine)
        try:
            discuss(key, f"Starting {run_id} on {MACHINE_WORDS[machine]} ({ENGINE_WORDS[engine]}, "
                         f"{self.timeout[machine] // 60} min cap): {why}. The worker signs `({sign}, date)` and ends "
                         f"with a signed outcome; milestones come as short signed comments. (dispatcher, {today()})")
        except RuntimeError:
            set_status(key, "Backlog")   # no Starting comment, no claim: do not leave the ticket In Progress
            raise
        try:
            fresh = read_issue(key)
        except RuntimeError as e:   # the claim is on the ticket; a failed re-read must not orphan it
            if approval is not None:
                log(f'{key} approval claim verification unavailable; no launch, claim waits for orphan reconciliation')
                return None
            log(f"{key} claim verification read failed ({e}); proceeding on the claim already posted")
            issue["state"]["name"] = "In Progress"
            return issue
        if fresh["state"]["name"] != "In Progress":
            log(f"{key} claim did not stick, state {fresh['state']['name']}")
            return None
        if approval is not None and not approval_guard.matches(approval, fresh, self.trusted_author):
            set_status(key, issue['state']['name'])
            log(f'{key} approved request changed during claim; no launch')
            return None
        return fresh

    # ---- launch over ssh (forced command `worker-run` on the target account)

    def launch(self, issue: dict, run_id: str, machine: str, engine: str, lead: str, restore: dict | None = None) -> None:
        """`restore` is what a run that never reached its hand gives back: {"ask": …} or {"reply_ts": …}."""
        key = issue["identifier"]
        self.state.data["noted"].pop(key, None)
        sign = signature(run_id, machine, engine)
        timeout = self.timeout[machine]
        try:
            task_lead, grant_id = self.task_handoff(issue, run_id, allow_unapproved=bool(restore))
        except (ValueError, TypeError, KeyError, OSError):
            # A revoke/change after claim must not strand an In Progress ticket.
            if restore and restore.get("ask"):
                self.state.data["asks"][key] = restore["ask"]
            if restore and restore.get("reply_ts"):
                self.state.data["followups"][key] = restore["reply_ts"]
            set_status(key, "Backlog")
            self.state.save()
            return
        lead = task_lead + lead
        prompt = load_brief(self.briefs, machine, engine, sign, run_id, key, timeout) + "\n\n" + lead + packet(issue)
        log_path = self.state.root / "runs" / f"{key}-{run_id}.log"
        log_path.parent.mkdir(exist_ok=True)
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30",
               "-o", "ServerAliveCountMax=4", self.host[machine], f"run {key} {run_id} {engine} {timeout}"]
        lf = open(log_path, "w")
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=lf, stderr=subprocess.STDOUT, text=True,
                                    start_new_session=True)
        except OSError:
            if restore and restore.get("ask"):
                self.state.data["asks"][key] = restore["ask"]
            if restore and restore.get("reply_ts"):
                self.state.data["followups"][key] = restore["reply_ts"]
            set_status(key, "Backlog")
            self.state.save()
            raise
        finally:
            lf.close()  # the SSH child has its own descriptor; failures must not leak ours
        self.procs[run_id] = proc
        self.state.data["runs"][run_id] = {"ticket": key, "machine": machine, "engine": engine, "sign": sign,
                                           "started": time.time(), "pid": proc.pid, "log": str(log_path),
                                           "timeout": timeout, **(restore or {})}
        if grant_id:
            self.state.data["runs"][run_id]["task_grant"] = grant_id
            digest = hashlib.sha256(prompt.encode()).hexdigest()
            self.state.data["runs"][run_id]["packet_digest"] = digest
            self.state.data["task_progress"][key]["deliveries"][run_id].update(
                phase="launch_attempted", packet_digest=digest, receipt="unknown")
        self.state.save()
        # Persist adoption metadata before releasing the prompt to a worker.
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except BrokenPipeError:
            if grant_id:
                self.state.data["runs"][run_id]["delivery_unknown"] = True
                self.state.save()
        log(f"launched {run_id} for {key} on {machine} ({engine}), pid {proc.pid}")

    # ---- completion

    def trusted_author(self, comment: dict, sign: str) -> bool:
        """A body signature is a label; only the pinned Linear user authenticates it."""
        try:
            policy = json.loads(Path(self.args.worker_identities).read_text())
            if policy.get('version') != 1 or not isinstance(policy.get('signatures'), dict):
                raise ValueError('invalid identity policy')
            allowed = policy['signatures'].get(sign.split(' ', 1)[0], [])
            if not isinstance(allowed, list) or any(not isinstance(uid, str) or not UUID_RE.fullmatch(uid) for uid in allowed):
                raise ValueError('invalid worker identities')
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError('worker identity policy unavailable; no report accepted') from exc
        return (comment.get('user') or {}).get('id') in allowed

    def last_report(self, key: str, sign: str, since_ts: float) -> tuple[dict | None, dict]:
        issue = read_issue(key)
        for c in reversed(comments_of(issue)):
            if (parse_ts(c["createdAt"]) > since_ts and signed_by(c["body"], sign)
                    and not c["body"].startswith("Starting") and self.trusted_author(c, sign)):
                return c, issue
        return None, issue

    def finish(self, run_id: str, rc) -> None:
        r = self.state.data["runs"][run_id]
        key, sign = r["ticket"], r["sign"]
        minutes = int(time.time() - r["started"]) // 60
        report, issue = self.last_report(key, sign, r["started"])
        self.state.data['runs'].pop(run_id)
        self.procs.pop(run_id, None)
        if r.get("task_grant"):
            progress = self.state.data["task_progress"][key]
            receipt = self.task_receipt(r, run_id)
            progress["deliveries"][run_id].update(ended=time.time(), reported=report is not None, receipt=receipt)
            if receipt != "finished":
                progress["blocked_delivery"] = run_id
            # Hints support reconciliation, never confer authority or prove side effects.
            if report:
                rec = task_approval.read(self.args.approvals, key)
                allowed = {s["id"] for s in rec["scope"]["steps"]}
                for step_id, evidence in re.findall(r"^TASK STEP VERIFIED: ([a-z0-9-]+) (.+)$", report["body"], re.M):
                    if step_id in allowed:
                        progress["steps"][step_id] = {"evidence": evidence[:1000], "run": run_id,
                                                       "comment": report["id"], "checked_at": time.time()}
                if issue["state"]["name"] in ("Done", "Canceled", "Cancelled"):
                    progress["completed_at"] = time.time()
        entry = {"run": run_id, "ticket": key, "machine": r["machine"], "engine": r["engine"], "rc": rc,
                 "minutes": minutes, "reported": report is not None, "ended": time.time()}
        self.state.data["history"] = (self.state.data["history"] + [entry])[-300:]
        if r.get("task_grant") and self.state.data["task_progress"][key].get("blocked_delivery"):
            discuss(key, f"{run_id} has uncertain task delivery/execution; no authenticated terminal packet receipt. "
                         "No automatic replay. Reconcile the worker receipt, process ownership and real effects before "
                         f"any retry; ambiguity remains gated. (dispatcher, {today()})")
            set_status(key, "Backlog")
        elif report is None and rc == 255 and not self.reached_hand(Path(r["log"])):
            self.never_started(run_id, r, f"could not reach {MACHINE_WORDS[r['machine']]} (asleep or off the tailnet)")
        elif report is None and isinstance(rc, int) and rc != 0 and not self.worker_spoke(issue, sign, r["started"]) \
                and self.last_message(Path(r["log"])) == "(no final message)":
            # the engine itself failed (Codex could not connect three times on 2026-10-11): no session, no comment, no output
            self.never_started(run_id, r, f"started on {MACHINE_WORDS[r['machine']]} but its engine produced nothing (rc={rc})")
        elif report:
            self.state.data["attempts"].pop(key, None)
            self.state.data["reported"][key] = {"at": time.time(), "machine": r["machine"], "engine": r["engine"],
                                                "started": r["started"]}
            ask = ASK_RE.search(report["body"])
            if ask:
                self.state.data["asks"][key] = {"comment": report["id"], "action": ask.group(1), "at": time.time(),
                                                "machine": r["machine"], "engine": r["engine"]}
            else:
                self.state.data["asks"].pop(key, None)
            if issue["state"]["name"] == "In Progress":
                discuss(key, f"{run_id} ended after {minutes} min with a signed outcome but left the ticket In Progress; "
                             f"moving it to Backlog so the outcome gets routed. (dispatcher, {today()})")
                set_status(key, "Backlog")
            log(f"{run_id} reported on {key} (rc={rc}, {minutes} min)")
        else:
            excerpt = self.last_message(Path(r["log"]))
            self.give_back(key, f"{run_id} on {MACHINE_WORDS[r['machine']]} ended (rc={rc}, {minutes} min) without a "
                                f"signed outcome. Last worker message:\n\n{excerpt}\n\n")
        self.state.save()

    @staticmethod
    def task_receipt(r: dict, run_id: str) -> str:
        digest = r.get("packet_digest")
        if not digest:
            return "unknown"
        try:
            lines = Path(r["log"]).read_text(errors="replace").splitlines()
        except OSError:
            return "unknown"
        prefix = f"WORKER RECEIPT {r['ticket']} {run_id} {digest} "
        if prefix + "ACCEPTED" not in lines:
            return "unknown"
        return "finished" if prefix + "FINISHED" in lines else "accepted"

    @staticmethod
    def reached_hand(log_path: Path) -> bool:
        """worker-run prints its banner first; a log without it means ssh never got there."""
        try:
            return "worker-run:" in log_path.read_text(errors="replace")[:4000]
        except OSError:
            return False

    def worker_spoke(self, issue: dict, sign: str, since_ts: float) -> bool:
        return any(signed_by(c["body"], sign) and parse_ts(c["createdAt"]) > since_ts
                   and self.trusted_author(c, sign) for c in comments_of(issue))

    def never_started(self, run_id: str, r: dict, how: str) -> None:
        """Nothing ran, so nothing is consumed: no attempt, and the ask, reply or pick goes back to waiting while the
        hand is left alone for HAND_BACKOFF_SEC."""
        key, machine = r["ticket"], r["machine"]
        self.probe[machine] = (time.time() + HAND_BACKOFF_SEC, False)
        kept = "The approval stays valid and is acted on" if r.get("ask") else "The reply is answered" if r.get("reply_ts") else "The run starts"
        discuss(key, f"{run_id} {how}; nothing ran and no attempt is counted. {kept} when the hand answers again "
                     f"(checked every {HAND_BACKOFF_SEC // 60} min). (dispatcher, {today()})")
        set_status(key, "Backlog")
        if r.get("ask"):
            self.state.data["asks"][key] = r["ask"]
        elif r.get("reply_ts"):
            self.state.data["followups"][key] = r["reply_ts"]
        else:
            self.candidates[key] = time.time() + RETRY_WAIT_SEC
        log(f"{run_id} never reached {machine}; {key} waits")

    @staticmethod
    def last_message(log_path: Path) -> str:
        try:
            text = log_path.read_text(errors="replace")
        except OSError:
            return "(no log)"
        marker = "=== LAST MESSAGE ==="
        if marker in text:
            text = text.split(marker, 1)[1]
        text = re.sub(r"\nWORKER-RUN END rc=\S+\s*$", "", text).strip()
        return text[:1500] if text else "(no final message)"

    def give_back(self, key: str, why: str) -> None:
        n = self.state.bump(key)
        if n >= MAX_ATTEMPTS:
            discuss(key, f"{why}Second attempt without an outcome; routing to the operator. (dispatcher, {today()})")
            for l in label_names(read_issue(key)):
                if l.startswith("for:"):
                    label(key, l, "remove")
            label(key, "for:operator", "add")
            set_status(key, "Backlog")
        else:
            discuss(key, f"{why}Returning to Backlog for one more attempt. (dispatcher, {today()})")
            set_status(key, "Backlog")
        self.state.save()

    def reap(self) -> None:
        for run_id in list(self.state.data["runs"]):
            r = self.state.data["runs"][run_id]
            proc = self.procs.get(run_id)
            if proc is not None:
                rc = proc.poll()
                if rc is None:
                    if time.time() - r["started"] > r["timeout"] + 180:   # the runner's own timeout should have fired
                        log(f"{run_id} overran its cap; killing the ssh session")
                        try:
                            os.killpg(proc.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        rc = proc.wait(timeout=30) if proc.poll() is None else proc.returncode
                        self.finish(run_id, f"killed-after-{r['timeout']}s")
                    continue
                self.finish(run_id, rc)
            elif not Path(f"/proc/{r['pid']}").exists():     # adopted after a restart: the ssh child is gone
                self.finish(run_id, "adopted")
            elif time.time() - r["started"] > r["timeout"] + 180:
                try:
                    os.kill(r["pid"], signal.SIGTERM)
                except ProcessLookupError:
                    pass

    # ---- follow-ups and approvals

    def task_record(self, key: str) -> dict | None:
        if not getattr(self.args, "task_scopes", False):
            return None
        rec = task_approval.read(self.args.approvals, key)
        if not rec or rec["status"] != "approved":
            return None
        pin = rec["identity"]
        if (not self.args.task_phone_node or not self.args.task_phone_user
                or str(pin["node_id"]) != self.args.task_phone_node
                or str(pin["user_id"]) != self.args.task_phone_user):
            raise ValueError("task phone identity does not match dispatcher pin")
        if self.state.data["task_progress"].get(key, {}).get("completed_at"):
            return None
        if self.state.data["task_progress"].get(key, {}).get("blocked_delivery"):
            return None
        return rec

    def task_ready(self, issue: dict) -> bool:
        if not getattr(self.args, "task_scopes", False):
            return True
        key = issue["identifier"]
        try:
            scope = task_approval.draft(issue.get("description"))
            rec = self.task_record(key)
            if rec and (not scope or task_approval.digest(scope) == rec["scope_digest"]):
                if not self.args.task_status_url:
                    raise ValueError("task status URL is not configured")
                return True
            if rec:
                return False  # approved immutable scope differs from the proposed scope
            if not scope and not rec:
                return True  # ordinary preparation/one-shot path retains its gates
        except (ValueError, TypeError, KeyError, OSError):
            pass
        self.note_once(key, "task scope is missing approval, closed, changed, or unavailable; no task authority delivered")
        return False

    def task_handoff(self, issue: dict, run_id: str, allow_unapproved: bool = False) -> tuple[str, str | None]:
        key = issue["identifier"]
        if not self.task_ready(issue):
            if allow_unapproved:
                return "", None  # answer replies/prepare under ordinary gates, without task authority
            raise ValueError("task authority changed before launch")
        rec = self.task_record(key)
        if not rec:
            return "", None
        p = self.state.data["task_progress"].setdefault(key, {
            "grant_id": rec["grant_id"], "scope_digest": rec["scope_digest"], "deliveries": {}, "steps": {}})
        if (p["grant_id"], p["scope_digest"]) != (rec["grant_id"], rec["scope_digest"]):
            raise ValueError("task identity changed")
        text = task_approval.lead(rec, p["deliveries"], p["steps"],
                                  self.args.task_status_url.rstrip('/') + '/' + key)
        # Persist delivery intent before SSH; a crash means unknown delivery, not a completed step.
        p["deliveries"][run_id] = {"prepared_at": time.time(), "phase": "reserved", "execution": "unknown"}
        self.state.save()
        return text, rec["grant_id"]

    def scan_followups(self) -> None:
        now = time.time()
        watched = {k for k, v in self.state.data["reported"].items() if now - v["at"] < FOLLOWUP_WINDOW_SEC}
        since = self.state.data.get("followup_checked") or (now - 3600)
        self.state.data["followup_checked"] = now
        if not watched:
            return
        iso = dt.datetime.fromtimestamp(since - 120, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = gql('query{ issues(first:100, filter:{ team:{key:{eq:"%s"}}, updatedAt:{gt:"%s"} }){ nodes{ identifier } } }' % (TEAM_KEY, iso))
        for key in sorted({n["identifier"] for n in data["issues"]["nodes"]} & watched):
            self.note_reply(key)

    def note_reply(self, key: str) -> None:
        issue = read_issue(key)
        cs = comments_of(issue)
        last_signed = max((i for i, c in enumerate(cs) if is_signed(c["body"]) and not signed_by(c["body"], "dispatcher")
                           and f"run-" in c["body"][-60:]), default=-1)
        after = self.state.data["followed"].get(key, 0)
        replies = [c for c in cs[last_signed + 1:] if not is_signed(c["body"]) and parse_ts(c["createdAt"]) > after]
        if replies:
            self.state.data["followups"][key] = parse_ts(replies[-1]["createdAt"])

    def take_followup(self) -> bool:
        for key in sorted(self.state.data["followups"], key=self.state.data["followups"].get):
            reply_ts = self.state.data["followups"][key]
            rep = self.state.data["reported"].get(key) or {}
            if self.state.running_ticket(key):
                continue
            if rep.get("started", 0) < reply_ts < rep.get("at", 0) - SEEN_REPLY_GRACE_SEC:
                # the reply landed during a run whose outcome came a minute or more later: answered already
                self.state.data["followups"].pop(key)
                self.state.data["followed"][key] = reply_ts
                self.state.save()
                continue
            machine, engine = self.hand_for(key, rep.get("machine", "vps"), rep.get("engine", "codex"))
            if self.full(machine, engine):
                continue
            if not self.reachable(machine):
                self.note_once(key, f"{MACHINE_WORDS[machine]} is not answering (asleep, off the tailnet, or its engine could not connect); the reply is answered when it is back")
                continue
            stamp = dt.datetime.fromtimestamp(reply_ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
            run_id = new_run_id()
            issue = self.claim(key, run_id, machine, engine, f"follow-up on the reply of {stamp}", followup=True)
            self.state.data["followups"].pop(key)
            self.state.data["followed"][key] = reply_ts
            self.state.save()
            if issue:
                self.launch(issue, run_id, machine, engine, FOLLOWUP_LEAD, restore={"reply_ts": reply_ts})
                return True
        return False

    def read_record(self, comment_id: str) -> dict | None:
        if not UUID_RE.match(comment_id):
            return None
        f = Path(self.args.approvals) / f"{comment_id}.json"
        try:
            if not f.is_file():
                return None
            rec = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        return rec if isinstance(rec, dict) else None

    def take_approval(self) -> bool:
        now = time.time()
        for key in sorted(self.state.data["asks"], key=lambda k: self.state.data["asks"][k]["at"]):
            ask = self.state.data["asks"][key]
            if now - ask["at"] > ASK_WINDOW_SEC:
                self.state.data["asks"].pop(key)
                continue
            rec = self.read_record(ask["comment"])
            if rec is None:
                continue
            if (rec.get("comment_id"), rec.get("ticket"), rec.get("action")) != (ask["comment"], key, ask["action"]):
                self.state.data["asks"].pop(key)
                discuss(key, "An approval record exists for the request on this ticket, but its text differs from the "
                             f"request recorded when it was asked, so nothing is acted on. (dispatcher, {today()})")
                continue
            if rec.get("decision") != "approve":
                self.state.data["asks"].pop(key)
                continue
            current = approval_guard.current(rec, gql, self.trusted_author)
            if current is None:
                continue  # source/policy unavailable or ticket currently held: keep the one-shot waiting
            if current is False:
                self.state.data['asks'].pop(key)
                self.state.save()
                discuss(key, 'The saved approval request is closed, changed, superseded or unauthenticated; '
                             f'nothing was executed. A new request needs a new phone decision. (dispatcher, {today()})')
                continue
            if self.state.running_ticket(key):
                continue
            machine, engine = self.hand_for(key, ask.get("machine", "vps"), ask.get("engine", "codex"))
            if self.full(machine, engine):
                continue
            if not self.reachable(machine):
                self.note_once(key, f"{MACHINE_WORDS[machine]} is not answering (asleep, off the tailnet, or its engine could not connect); the approved action runs when it is back")
                continue
            run_id = new_run_id()
            issue = self.claim(key, run_id, machine, engine,
                               f"the operator approved the requested action on the approval page ({rec.get('at', '?')})", followup=True,
                               approval=rec)
            if issue:   # a ticket In Progress elsewhere keeps its approval for a later tick
                self.state.data["asks"].pop(key)
                self.state.save()
                self.launch(issue, run_id, machine, engine, approval_lead(rec), restore={"ask": ask})
                return True
        self.state.save()
        return False

    # ---- fresh picks

    def consider(self, key: str) -> bool:
        """One ticket named by an event or the poll. True when it stays queued (waiting for capacity)."""
        if self.state.running_ticket(key) or (self.allow and key not in self.allow):
            return False
        issue = read_issue(key)
        if not claimable(issue) or self.state.attempts(key) >= MAX_ATTEMPTS:
            return False
        machine, why = choose_machine(issue)
        if machine == "laptop" and engine_of(issue) == "claude" and self.claude_since:
            touched = issue.get("updatedAt") or ""
            # the parking note itself touches the ticket; a touch within a few seconds of our own note is not the operator's
            own_note = (self.state.data["noted"].get(key) == self.park_reason
                        and abs(parse_ts(touched) - self.state.data["noted_at"].get(key, 0)) < 30) if touched else False
            if touched < self.claude_since or own_note:
                machine, why = None, self.park_reason
        if machine is None:
            self.note_once(key, why)
            return False
        rep = self.state.data["reported"].get(key)
        if rep and rep["machine"] == machine and time.time() - rep["at"] < REPORT_COOLDOWN_SEC:
            return False   # the same hand reported recently; a reply or a re-route is what re-picks it
        engine = engine_of(issue)
        if self.full(machine, engine):
            return True    # capacity frees up when a run ends
        if not self.reachable(machine):
            self.note_once(key, f"{MACHINE_WORDS[machine]} is not answering (asleep, off the tailnet, or its engine could not connect); the run starts when it is back")
            return True    # kept, re-read every RETRY_WAIT_SEC
        run_id = new_run_id()
        pri = {1: "urgent", 2: "high", 3: "medium", 4: "low"}.get(issue.get("priority") or 0, "unset")
        claimed = self.claim(key, run_id, machine, engine, f"picked from the queue (priority {pri}); {why}")
        if claimed:
            self.launch(claimed, run_id, machine, engine, "")
        return False

    def poll(self) -> None:
        for runtime in ("codex", "claude"):
            for attempt in (1, 2):   # back-to-back token mints for one app sometimes get a 400/401; one retry clears it
                try:
                    for i in pickup(runtime):
                        if i.get("team", {}).get("key") == TEAM_KEY and (i.get("state") or {}).get("name") in CLAIMABLE_STATES:
                            self.candidates.setdefault(i["identifier"], time.time())
                    break
                except Exception as e:  # noqa: BLE001
                    log(f"poll {runtime} failed (attempt {attempt}): {e}")
                    time.sleep(5)
        self.scan_followups()
        try:
            self.sweep_orphans()
        except Exception as e:  # noqa: BLE001
            log(f"orphan sweep failed: {e}")
        self.state.data["poll_at"] = time.time()
        self.state.save()

    def sweep_orphans(self) -> None:
        """A claim interrupted between its Starting comment and the launch left a ticket In Progress with no run for
        twenty hours (2026-10-10). Any In Progress ticket whose newest dispatcher Starting names a run this service has
        never seen goes back to Backlog; a worker's run, or another agent's claim, is left alone."""
        data = gql('query{ issues(first:100, filter:{ team:{key:{eq:"%s"}}, state:{name:{eq:"In Progress"}}, '
                   'labels:{name:{in:["for:codex","for:claude"]}} }){ nodes{ identifier } } }' % TEAM_KEY)
        known = set(self.state.data["runs"]) | {h["run"] for h in self.state.data["history"]}
        known.update(run_id for p in self.state.data["task_progress"].values() for run_id in p["deliveries"])
        for key in sorted(n["identifier"] for n in data["issues"]["nodes"]):
            if self.state.running_ticket(key):
                continue
            cs = comments_of(read_issue(key))
            idx = max((i for i, c in enumerate(cs) if c["body"].startswith("Starting run-") and signed_by(c["body"], "dispatcher")), default=-1)
            if idx < 0 or any(WORKER_SIG_RE.search(c["body"].strip()) for c in cs[idx + 1:]):
                continue   # no claim of ours, or a worker spoke after it: that run existed
            m = RUN_RE.match(cs[idx]["body"].split()[1])
            if not m or m.group(0) in known or time.time() - parse_ts(cs[idx]["createdAt"]) < CLAIM_GRACE_SEC:
                continue
            discuss(key, f"{m.group(0)} never started: the claim was interrupted before the launch. Returning to Backlog "
                         f"for a fresh run. (dispatcher, {today()})")
            set_status(key, "Backlog")
            self.candidates.setdefault(key, time.time())
            log(f"{key}: orphaned claim {m.group(0)} handed back")

    def tick(self) -> None:
        self.reap()
        for ev in read_events(self.state, self.events_path):
            hit = event_interest(ev, self.state)
            if hit and hit[0] == "candidate":
                self.candidates.setdefault(hit[1], time.time())
            elif hit and hit[0] == "reply":
                self.note_reply(hit[1])
        now = time.time()
        if now - self.state.data.get("poll_at", 0) > POLL_SEC:
            self.poll()
        if now - self.state.data.get("ask_at", 0) > ASK_POLL_SEC and self.state.data["asks"]:
            self.state.data["ask_at"] = now
            while self.take_approval():
                pass
        while self.take_followup():
            pass
        for key in sorted(self.candidates, key=self.candidates.get):
            if self.candidates[key] > now:
                continue   # waiting for capacity or a hand; re-read at its time, not every tick
            try:
                kept = self.consider(key)
            except Exception as e:  # noqa: BLE001
                log(f"consider {key} failed: {type(e).__name__}: {e}")
                kept = False
            if kept:
                self.candidates[key] = time.time() + RETRY_WAIT_SEC
            else:
                self.candidates.pop(key, None)
        self.state.save()

    def serve(self) -> int:
        lock = open(self.state.root / "lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("another dispatcher holds the lock")
            return 1
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stopping", True))
        adopted = list(self.state.data["runs"])
        if adopted:
            log(f"adopting {len(adopted)} run(s) from before the restart: {', '.join(adopted)}")
        log(f"serving; events {self.events_path}, caps {self.cap}, hosts {self.host}"
            + (f", canary allowlist {sorted(self.allow)}" if self.allow else ""))
        while not self.stopping:
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                log(f"tick failed: {type(e).__name__}: {e}")
                time.sleep(10)
            time.sleep(TICK_SEC)
        log("stopping; running workers continue under their ssh sessions and are adopted on restart")
        self.state.save()
        return 0


def new_run_id() -> str:
    return "run-" + secrets.token_hex(3)


def main() -> int:
    env = os.environ.get
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["serve", "status", "once"], help="serve: run the loop; status: print state; once: one tick")
    p.add_argument("--state", default=env("DISPATCHER_STATE", str(Path.home() / ".local/state/dispatcher")))
    p.add_argument("--events", default=env("DISPATCHER_EVENTS", "/var/lib/linear-hook/events.jsonl"))
    p.add_argument("--approvals", default=env("DISPATCHER_APPROVALS", "/var/lib/approve-gate/records"))
    p.add_argument('--worker-identities', default=env('DISPATCHER_WORKER_IDENTITIES', '/etc/dispatcher/worker-identities.json'))
    p.add_argument("--task-scopes", action="store_true", default=env("DISPATCHER_TASK_SCOPES", "0") == "1")
    p.add_argument("--task-status-url", default=env("DISPATCHER_TASK_STATUS_URL", ""))
    p.add_argument("--task-phone-node", default=env("DISPATCHER_TASK_PHONE_NODE", ""))
    p.add_argument("--task-phone-user", default=env("DISPATCHER_TASK_PHONE_USER", ""))
    p.add_argument("--briefs", default=env("DISPATCHER_BRIEFS", str(Path(__file__).resolve().parent)))
    p.add_argument("--ssh-vps", default=env("DISPATCHER_SSH_VPS", "vps-worker"))
    p.add_argument("--ssh-laptop", default=env("DISPATCHER_SSH_LAPTOP", "laptop"))
    p.add_argument("--cap-vps", type=int, default=int(env("DISPATCHER_CAP_VPS", "2")))
    p.add_argument("--cap-laptop", type=int, default=int(env("DISPATCHER_CAP_LAPTOP", "2")))
    p.add_argument("--timeout-vps", type=int, default=int(env("DISPATCHER_TIMEOUT_VPS", str(45 * 60))))
    p.add_argument("--timeout-laptop", type=int, default=int(env("DISPATCHER_TIMEOUT_LAPTOP", str(60 * 60))))
    p.add_argument("--allow", default=env("DISPATCHER_ALLOW", ""), help="canary: only these tickets (space or comma separated)")
    p.add_argument("--claude-since", default=env("DISPATCHER_CLAUDE_SINCE", ""), help="ISO time; older untouched for:claude tickets are parked")
    args = p.parse_args()
    d = Dispatcher(args)
    if args.command == "status":
        s = d.state.data
        print(json.dumps({"runs": s["runs"], "candidates": sorted(d.candidates), "asks": list(s["asks"]),
                          "followups": list(s["followups"]), "reported": {k: v["at"] for k, v in s["reported"].items()},
                          "attempts": s["attempts"], "history": s["history"][-10:]}, indent=1))
        return 0
    if args.command == "once":
        # The one-shot entrypoint shares serve's lock: never race another claimer.
        lock = open(d.state.root / "lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("another dispatcher holds the lock")
            return 1
        d.tick()
        return 0
    return d.serve()


if __name__ == "__main__":
    sys.exit(main())
