#!/usr/bin/env python3
"""Offline tests for the approval path: the page server (approve-gate) and the keeper's use of its records.
Run: python3 -m unittest discover -s scripts/worker -p 'test_*.py'"""
import importlib.machinery
import importlib.util
import json
import tempfile
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, filename):
    loader = importlib.machinery.SourceFileLoader(name, str(HERE / filename))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(mod)
    return mod


approve = load("sol_approve", "approve-gate")
ASK_ID = "11111111-2222-3333-4444-555555555555"
ACTION = "deploy commit abc1234 of example-app to production with scripts/deploy.sh"
ASK_BODY = f"Built and tested; the deploy is yours to allow.\n\nAPPROVAL NEEDED: {ACTION}\n\n(worker-laptop run-abcdef, 2026-10-01)"
WORKER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OWNER_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
FOREIGN_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def comment(cid, at, body, user_id=WORKER_ID):
    return dict(id=cid, createdAt=at, body=body,
                user={"id": user_id, "name": "Fixture worker"} if user_id else None)


def ticket(comments, state="Backlog"):
    return dict(identifier="EXAMPLE-999", title="Generic fixture", url="https://example.invalid/i", state=dict(name=state),
                team=dict(key="ABC"), labels=dict(nodes=[dict(name="for:operator")]), description="",
                comments=dict(nodes=list(comments), pageInfo=dict(hasNextPage=False)))


class Rig(unittest.TestCase):
    comments = [comment(ASK_ID, "2026-10-01T10:00:00Z", ASK_BODY)]
    state_name = "Backlog"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.comments = list(type(self).comments)
        self.state_name = type(self).state_name
        self.team_key = "ABC"
        policy = self.tmp / "worker-identities.json"
        policy.write_text(json.dumps({"version": 1, "signatures": {
            "worker-laptop": [WORKER_ID], "worker-vps": [WORKER_ID], "claude": [OWNER_ID],
            "codex": [OWNER_ID], "kimi": [OWNER_ID], "ds": [OWNER_ID],
        }}))
        approve.C.clear()
        approve.C.update(bind="127.0.0.1", port=0, hosts=[], approvers=["127.0.0.1"],
                         records=str(self.tmp / "records"), state=str(self.tmp / "state"),
                         worker_identities_file=str(policy))
        (self.tmp / "records").mkdir()
        (self.tmp / "state").mkdir()
        approve._cache["at"] = 0.0
        self.said = []
        for target, fake in ((approve, self.fake_gql), ):
            p = patch.object(target, "gql", side_effect=fake); p.start(); self.addCleanup(p.stop)
        p = patch.object(approve, "discuss", side_effect=lambda k, b: self.said.append((k, b))); p.start(); self.addCleanup(p.stop)

    def fake_gql(self, query, variables=None):
        if "comments(first:100" in query:
            return {"comments": {"nodes": [{"id": c["id"], "issue": {"identifier": "EXAMPLE-999"}}
                                           for c in self.comments if "APPROVAL NEEDED:" in c["body"]],
                                 "pageInfo": {"hasNextPage": False, "endCursor": None}}}
        issue = ticket(self.comments, self.state_name)
        issue["team"]["key"] = self.team_key
        return {"issue": issue}


class PendingTests(Rig):
    def test_other_team_cannot_present_an_ask(self):
        self.team_key = "OTHER"
        self.assertEqual(approve.find_pending(), [])

    def test_open_ask_is_pending_with_its_exact_text(self):
        (p,) = approve.find_pending()
        self.assertEqual((p["comment_id"], p["ticket"], p["action"], p["worker"]), (ASK_ID, "EXAMPLE-999", ACTION, "worker-laptop run-abcdef"))

    def test_not_pending_when_superseded_unsigned_closed_or_in_progress(self):
        later = comment("x", "2026-10-01T11:00:00Z", "Done without it. (worker-laptop run-abcdef, 2026-10-01)")
        forged_unsigned = comment(ASK_ID, "2026-10-01T10:00:00Z", f"APPROVAL NEEDED: {ACTION}")
        for name, comments, state in [("superseded", self.comments + [later], "Backlog"), ("unsigned", [forged_unsigned], "Backlog"),
                                      ("done", self.comments, "Done"), ("live", self.comments, "In Progress")]:
            with self.subTest(name):
                self.comments, self.state_name = comments, state
                self.assertEqual(approve.find_pending(), [])

    def test_configured_worker_signatures_count(self):
        for signer, uid in (("claude", OWNER_ID), ("worker-vps run-abcdef", WORKER_ID),
                            ("worker-laptop run-abcdef", WORKER_ID), ("codex run-7f3a", OWNER_ID)):
            with self.subTest(signer):
                self.comments = [comment(ASK_ID, "2026-10-01T10:00:00Z", f"APPROVAL NEEDED: {ACTION}\n({signer}, 2026-10-01)", uid)]
                (p,) = approve.find_pending()
                self.assertEqual((p["action"], p["worker"]), (ACTION, signer))

    def test_signature_without_matching_authenticated_author_is_rejected(self):
        for signer, uid in (("worker-laptop", FOREIGN_ID), ("worker-laptop", None),
                            ("claude", WORKER_ID), ("steering", WORKER_ID),
                            ("dispatcher run-7f3a", WORKER_ID), ("unknown", WORKER_ID)):
            with self.subTest(signer=signer, uid=uid):
                self.comments = [comment(ASK_ID, "2026-10-01T10:00:00Z", f"APPROVAL NEEDED: {ACTION}\n({signer}, 2026-10-01)", uid)]
                self.assertEqual(approve.find_pending(), [])

    def test_unavailable_or_invalid_policy_fails_closed(self):
        path = Path(approve.C["worker_identities_file"])
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            approve.find_pending()
        path.write_text('{"version": 1, "signatures": {"worker-laptop": []}}')
        with self.assertRaises(ValueError):
            approve.find_pending()

    def test_matching_author_is_shown_separately_from_claimed_signature(self):
        (p,) = approve.find_pending()
        self.assertEqual(p["worker"], "worker-laptop run-abcdef")
        self.assertEqual(p["verified_actor"], "Fixture worker (aaaaaaaa)")

    def test_ask_line_after_the_signature_still_counts(self):      # EXAMPLE-512: the first live ask was written this way
        self.comments = [comment(ASK_ID, "2026-10-01T10:00:00Z", f"Blocked on the operator.\n\n(worker-vps run-abcdef, 2026-10-01)\n\nAPPROVAL NEEDED: {ACTION}")]
        (p,) = approve.find_pending()
        self.assertEqual((p["action"], p["worker"]), (ACTION, "worker-vps run-abcdef"))

    def test_a_reply_after_the_ask_keeps_it_pending(self):
        self.comments = self.comments + [comment("r", "2026-10-01T10:05:00Z", "what does this deploy change?")]
        self.assertEqual(len(approve.find_pending()), 1)

    def test_decide_binds_text_and_fires_once(self):
        good = approve.sha(ACTION)
        self.assertEqual(approve.decide(ASK_ID, "0" * 16, "approve", "t")[0], 409)       # text differs from what was shown
        self.assertEqual(approve.decide(ASK_ID, good, "maybe", "t")[0], 400)
        self.assertEqual(approve.decide("../../etc/passwd", good, "approve", "t")[0], 400)
        self.assertFalse(list((self.tmp / "records").iterdir()))
        self.assertEqual(approve.decide(ASK_ID, good, "approve", "t"), (200, "approved"))
        rec = json.loads((self.tmp / "records" / f"{ASK_ID}.json").read_text())
        self.assertEqual((rec["ticket"], rec["action"], rec["decision"]), ("EXAMPLE-999", ACTION, "approve"))
        self.assertTrue(self.said[0][1].endswith(f"(approve-gate, {approve.dt.date.today().isoformat()})"))
        self.assertNotIn("APPROVAL NEEDED:", self.said[0][1])                           # the note is not itself an ask
        self.assertEqual(approve.decide(ASK_ID, good, "deny", "t")[0], 409)               # decided: gone from pending
        self.assertEqual(approve.find_pending(), [])

    def test_push_once_per_ask(self):
        with patch.object(approve, "push", return_value={"state": "accepted", "accepted_at": "2026-10-01T10:00:00Z", "message_id": "fixture"}) as push:
            self.assertEqual(approve.poll_once(), 1)
            self.assertEqual(approve.poll_once(), 0)
            self.assertEqual(push.call_count, 1)
            self.assertNotIn("ABC", push.call_args[0][0])                                # content-free


@unittest.skipUnless(os.environ.get("STRATA_HTTP_TESTS") == "1", "loopback sockets unavailable in the offline sandbox; set STRATA_HTTP_TESTS=1 where allowed")
class HttpRig(Rig):
    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), approve.Handler)
        self.host = f"127.0.0.1:{self.srv.server_address[1]}"
        approve.C["hosts"] = [self.host]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown)

    def call(self, path, body=None, headers=None):
        req = urllib.request.Request(f"http://{self.host}{path}", data=json.dumps(body).encode() if body else None,
                                     headers=headers or {}, method="POST" if body else "GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()


class HttpTests(HttpRig):

    def test_page_and_decision_from_an_approver(self):
        self.assertEqual(self.call("/")[0], 200)
        p = json.loads(self.call("/api/pending")[1])["pending"][0]
        body = dict(comment_id=p["comment_id"], action_sha=p["action_sha"], decision="deny")
        ok = {"Content-Type": "application/json", "X-approve-gate": "1"}
        for name, headers in [("no marker header", {"Content-Type": "application/json"}),
                              ("form post", {"Content-Type": "application/x-www-form-urlencoded", "X-approve-gate": "1"}),
                              ("foreign origin", dict(ok, Origin="http://evil.example")),
                              ("rebound host", dict(ok, Host="evil.example"))]:
            with self.subTest(name):
                self.assertEqual(self.call("/api/decide", body, headers)[0], 403)
        self.assertFalse(list((self.tmp / "records").iterdir()))
        self.assertEqual(self.call("/api/decide", body, dict(ok, Origin=f"http://{self.host}"))[0], 200)
        self.assertEqual(json.loads(self.call("/api/pending")[1])["decided"][0]["decision"], "deny")

    def test_everyone_else_is_refused(self):
        approve.C["approvers"] = ["other.phone.invalid"]
        ok = {"Content-Type": "application/json", "X-approve-gate": "1"}
        self.assertEqual(self.call("/")[0], 403)
        self.assertEqual(self.call("/api/pending")[0], 403)
        self.assertEqual(self.call("/api/decide", dict(comment_id=ASK_ID, action_sha=approve.sha(ACTION), decision="approve"), ok)[0], 403)
        self.assertFalse(list((self.tmp / "records").iterdir()))


class CurrentApprovalTests(HttpRig):
    def test_general_page_requires_authenticated_phone_and_shows_verified_author(self):
        self.assertEqual(self.call("/general")[0], 403)
        with patch.object(approve, "phone_identity", return_value={"user_id": "fixture", "node_id": "fixture"}):
            self.assertEqual(self.call("/general")[0], 200)
            code, raw = self.call("/api/general")
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(raw)["pending"][0]["verified_actor"], "Fixture worker (aaaaaaaa)")

    def test_general_post_requires_origin_and_bound_digest(self):
        identity = {"user_id": "fixture", "node_id": "fixture"}
        data = {"comment_id": ASK_ID, "action_digest": approve.digest(ACTION), "decision": "deny"}
        base = {"Content-Type": "application/json", "X-approve-gate": "1"}
        with patch.object(approve, "phone_identity", return_value=identity):
            self.assertEqual(self.call("/api/general/decide", data, base)[0], 403)
            good = dict(base, Origin=f"http://{self.host}")
            self.assertEqual(self.call("/api/general/decide", {**data, "action_digest": "0" * 64}, good)[0], 409)
            self.assertFalse(list((self.tmp / "records").glob("*.json")))
            self.assertEqual(self.call("/api/general/decide", data, good)[0], 200)
            rec = json.loads((self.tmp / "records" / f"{ASK_ID}.json").read_text())
            self.assertEqual((rec["source"], rec["identity"]), ("general", identity))

    def test_linear_or_identity_policy_outage_disables_new_decisions(self):
        with patch.object(approve, "phone_identity", return_value={"user_id": "fixture", "node_id": "fixture"}):
            Path(approve.C["worker_identities_file"]).unlink()
            self.assertEqual(self.call("/api/general")[0], 502)
            data = {"comment_id": ASK_ID, "action_digest": approve.digest(ACTION), "decision": "approve"}
            headers = {"Content-Type": "application/json", "X-approve-gate": "1", "Origin": f"http://{self.host}"}
            self.assertEqual(self.call("/api/general/decide", data, headers)[0], 502)
            self.assertFalse(list((self.tmp / "records").glob("*.json")))

    def test_existing_record_cannot_be_overwritten(self):
        (p,) = approve.find_pending()
        path = self.tmp / "records" / f"{ASK_ID}.json"
        path.write_text('{"sentinel":true}')
        with patch.object(approve, "pending", return_value=[p]):
            self.assertEqual(approve.decide(ASK_ID, p["action_sha"], "approve", "fixture")[0], 409)
        self.assertEqual(json.loads(path.read_text()), {"sentinel": True})


class TaskApprovalTests(HttpRig):
    scope = {"outcome": "Deploy a fixture", "resources": ["fixture-service"],
             "steps": [{"id": "restart", "effect": "restart", "resource": "fixture-service", "action": "Restart fixture service"}],
             "rollback": "Restore fixture service"}

    def setUp(self):
        super().setUp()
        approve.C["task_scopes"] = True
        self.identity = {"user_id": "fixture", "node_id": "fixture"}
        self.issue = {"identifier": "EXAMPLE-999", "title": "Fixture", "url": "https://example.invalid/i",
                      "description": "BEGIN TASK SCOPE\n" + json.dumps(self.scope) + "\nEND TASK SCOPE",
                      "state": {"name": "Backlog"}}
        for name, value in (("phone_identity", self.identity), ("task_issue", self.issue)):
            p = patch.object(approve, name, return_value=value); p.start(); self.addCleanup(p.stop)

    def test_task_request_approve_status_close_and_terminal_grant(self):
        with patch.object(approve, "gql", return_value={"issues": {"nodes": [self.issue],
                                                      "pageInfo": {"hasNextPage": False, "endCursor": None}}}):
            rows = approve.task_requests()
        self.assertEqual(len(rows), 1)
        scope_digest = approve.task_approval.digest(self.scope)
        self.assertEqual(approve.task_decide("EXAMPLE-999", scope_digest, "approve", "fixture"), (200, "approved"))
        self.assertTrue(approve.task_status("EXAMPLE-999")["active"])
        with patch.object(approve, "task_worker", return_value=None):
            self.assertEqual(approve.task_close("EXAMPLE-999", scope_digest, "fixture"), (200, "task authority closed"))
        self.assertFalse(approve.task_status("EXAMPLE-999")["active"])
        self.assertEqual(approve.task_decide("EXAMPLE-999", scope_digest, "approve", "fixture")[0], 409)

    def test_task_scope_change_and_foreign_worker_are_rejected(self):
        self.assertEqual(approve.task_decide("EXAMPLE-999", "0" * 64, "approve", "fixture")[0], 409)
        self.assertEqual(list((self.tmp / "records" / "tasks").glob("*.json")), [])
        self.assertEqual(self.call("/api/task-status/EXAMPLE-999")[0], 403)
        body = {"ticket": "EXAMPLE-999", "scope_digest": approve.task_approval.digest(self.scope)}
        headers = {"Content-Type": "application/json", "X-approve-gate": "1"}
        self.assertEqual(self.call("/api/task-close", body, headers)[0], 403)

    def test_authorized_task_status_close_and_revoke(self):
        scope_digest = approve.task_approval.digest(self.scope)
        self.assertEqual(approve.task_decide("EXAMPLE-999", scope_digest, "approve", "fixture")[0], 200)
        with patch.object(approve, "task_worker", return_value=None):
            status = json.loads(self.call("/api/task-status/EXAMPLE-999")[1])
            self.assertTrue(status["active"])
            body = {"ticket": "EXAMPLE-999", "scope_digest": scope_digest}
            headers = {"Content-Type": "application/json", "X-approve-gate": "1"}
            self.assertEqual(self.call("/api/task-close", body, headers)[0], 200)
            self.assertFalse(json.loads(self.call("/api/task-status/EXAMPLE-999")[1])["active"])
        self.assertEqual(approve.task_decide("EXAMPLE-999", scope_digest, "revoke", "fixture")[0], 409)

    def test_task_mode_stays_off_by_default(self):
        approve.C["task_scopes"] = False
        self.assertEqual(approve.task_decide("EXAMPLE-999", approve.task_approval.digest(self.scope), "approve", "fixture"),
                         (404, "task approvals are disabled"))



if __name__ == "__main__":
    unittest.main()
