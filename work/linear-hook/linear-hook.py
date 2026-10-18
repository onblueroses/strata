#!/usr/bin/env python3 -I
"""Linear webhook receiver: verify, append to a durable event log, forward to the steering agent.

Runs on the VPS behind nginx (loopback only). Linear signs the raw body with HMAC-SHA256 under the webhook's
signing secret (`Linear-Signature`) and stamps `webhookTimestamp` (ms); a delivery older than a minute is replayed
and refused. Every accepted event is one fsynced JSON line in the log, which the dispatcher reads; the steering agent gets the
same event by POST, off the request thread, so Linear's 5 s deadline is never at risk. Nothing here interprets the
event: the steering agent decides what wakes it, the dispatcher decides what is claimable.

Env: LINEAR_HOOK_SECRET_FILE (0600), LINEAR_HOOK_LOG, LINEAR_HOOK_BIND (default 127.0.0.1), LINEAR_HOOK_PORT (4762),
STEERING_EVENT_URL, STEERING_EVENT_TOKEN_FILE (0600). Optional LINEAR_HOOK_FORWARD_LOG for forwarding failures.
"""
import hashlib
import hmac
import http.server
import json
import os
import sys
import threading
import time
import urllib.request
from collections import OrderedDict

MAX_BODY = 1_000_000
TOLERANCE_MS = 60_000
FORWARD_RETRIES = (1, 5, 20, 60)


def read_secret(path: str) -> str:
    st = os.stat(path)
    if st.st_mode & 0o077:
        raise SystemExit(f"{path} must be mode 0600")
    return open(path, encoding="utf-8").read().strip()


class Dedupe:
    """Linear retries a delivery up to three times; the body hash tells them apart from new events."""

    def __init__(self, n: int = 2048):
        self.seen: "OrderedDict[str, float]" = OrderedDict()
        self.n = n
        self.lock = threading.Lock()

    def first(self, digest: str) -> bool:
        with self.lock:
            if digest in self.seen:
                return False
            self.seen[digest] = time.time()
            while len(self.seen) > self.n:
                self.seen.popitem(last=False)
            return True


class Hook(http.server.BaseHTTPRequestHandler):
    server_version = "linear-hook/1"
    sys_version = ""
    secret = b""
    log_path = ""
    forward_url = ""
    forward_token = ""
    forward_log = ""
    dedupe = Dedupe()
    log_lock = threading.Lock()

    def log_message(self, fmt, *args):  # journald gets one line per decision from `note`, not the access log
        return

    def note(self, msg: str) -> None:
        sys.stderr.write(f"[linear-hook {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {msg}\n")
        sys.stderr.flush()

    def reply(self, code: int, text: str) -> None:
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200 if self.path == "/health" else 404, "ok" if self.path == "/health" else "not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self.reply(413, "body size")
        body = self.rfile.read(length)
        sig = self.headers.get("Linear-Signature", "")
        want = hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        if not sig or not hmac.compare_digest(sig, want):
            self.note(f"refused: bad signature from {self.client_address[0]}")
            return self.reply(401, "signature")
        try:
            event = json.loads(body)
            ts = int(event.get("webhookTimestamp") or 0)
        except (ValueError, TypeError):
            return self.reply(400, "json")
        now_ms = int(time.time() * 1000)
        if abs(now_ms - ts) > TOLERANCE_MS:
            self.note(f"refused: timestamp off by {(now_ms - ts) / 1000:.0f}s")
            return self.reply(400, "timestamp")
        digest = hashlib.sha256(body).hexdigest()
        if not self.dedupe.first(digest):
            return self.reply(200, "duplicate")
        row = {"received": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "digest": digest[:16], "event": event}
        line = json.dumps(row, ensure_ascii=False) + "\n"
        with self.log_lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        self.reply(200, "ok")
        what = f"{event.get('type')}.{event.get('action')} {((event.get('data') or {}).get('identifier') or (event.get('data') or {}).get('issue', {}).get('identifier') or '')}"
        self.note(f"accepted {what} {digest[:8]}")
        if self.forward_url:
            threading.Thread(target=self.forward, args=(body, digest), daemon=True).start()

    def forward(self, body: bytes, digest: str) -> None:
        req = urllib.request.Request(self.forward_url, data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {self.forward_token}", "X-Event-Digest": digest})
        for i, delay in enumerate((0,) + FORWARD_RETRIES):
            if delay:
                time.sleep(delay)
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    r.read()
                return
            except Exception as e:  # noqa: BLE001
                err = str(e)
        self.note(f"forward failed {digest[:8]}: {err}")
        if self.forward_log:
            with open(self.forward_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": time.time(), "digest": digest, "error": err}) + "\n")


def main() -> None:
    Hook.secret = read_secret(os.environ["LINEAR_HOOK_SECRET_FILE"]).encode()
    Hook.log_path = os.environ["LINEAR_HOOK_LOG"]
    Hook.forward_url = os.environ.get("STEERING_EVENT_URL", "")
    if Hook.forward_url:
        Hook.forward_token = read_secret(os.environ["STEERING_EVENT_TOKEN_FILE"])
    Hook.forward_log = os.environ.get("LINEAR_HOOK_FORWARD_LOG", "")
    bind = os.environ.get("LINEAR_HOOK_BIND", "127.0.0.1")
    if bind in ("0.0.0.0", "::", ""):
        raise SystemExit("refusing a public bind; nginx fronts this")
    port = int(os.environ.get("LINEAR_HOOK_PORT", "4762"))
    os.makedirs(os.path.dirname(Hook.log_path), exist_ok=True)
    srv = http.server.ThreadingHTTPServer((bind, port), Hook)
    sys.stderr.write(f"[linear-hook] listening on {bind}:{port}, log {Hook.log_path}, forward {'on' if Hook.forward_url else 'off'}\n")
    srv.serve_forever()


if __name__ == "__main__":
    main()
