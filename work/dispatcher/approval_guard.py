"""Revalidate immutable approval text immediately before dispatcher consumption.

This module has no mutation, networking or execution authority of its own.
The supplied gql function performs read-only queries under the dispatcher's identity.
"""
import hashlib
import re
import os

ASK_RE = re.compile(r"^APPROVAL NEEDED:[ \t]*(\S.*?)[ \t]*$", re.M)
WORKER_RE = re.compile(r"\(([a-z][\w-]*(?:[ :/@][\w./@-]+)*), \d{4}-\d{2}-\d{2}\)[ \t]*$", re.M)
NON_WORKERS = {"steering", "dispatcher", "approve-gate"}


def matches(rec, issue, trusted_author):
    """Validate the latest authenticated worker ask in an already complete snapshot."""
    if issue.get('team', {}).get('key') != os.environ.get('DISPATCHER_TEAM_KEY', 'ABC'):
        return False
    workers = []
    for c in sorted(issue['comments']['nodes'], key=lambda c: (c['createdAt'], c['id'])):
        sig = WORKER_RE.search(c['body'].strip())
        if (sig and sig.group(1).split(' ', 1)[0] not in NON_WORKERS
                and trusted_author(c, sig.group(1))):
            workers.append(c)
    if not workers:
        return False
    last = workers[-1]
    asks = ASK_RE.findall(last['body'])
    return last['id'] == rec.get('comment_id') and len(asks) == 1 and asks[0] == rec.get('action')


def current(rec, gql, trusted_author):
    """True = unchanged; False = invalidated; None = source unavailable, defer."""
    if not re.fullmatch(r"[A-Z]{2,8}-\d+", str(rec.get("ticket", ""))):
        return False
    if not isinstance(rec.get('action'), str):
        return False
    if rec.get("source") == "general" and rec.get("action_digest") != hashlib.sha256(rec.get("action", "").encode()).hexdigest():
        return False
    try:
        comments, cursor = [], None
        while True:
            issue = gql("""query($id:String!, $cursor:String){issue(id:$id){team{key} state{name}
              comments(first:250,after:$cursor){nodes{id createdAt body user{id name}}pageInfo{hasNextPage endCursor}}}}""",
                        {"id": rec["ticket"], "cursor": cursor})["issue"]
            if issue['state']['name'] in ('Done', 'Canceled', 'Cancelled'):
                return False  # cancellation consumes no action and revokes this saved ask
            if issue["state"]["name"] not in ("Backlog", "Todo"):
                return None  # a running/reviewed ticket retains its approval for a later tick
            comments.extend(issue["comments"]["nodes"])
            page = issue["comments"]["pageInfo"]
            if not page["hasNextPage"]:
                break
            if not page["endCursor"] or page["endCursor"] == cursor:
                return None
            cursor = page["endCursor"]
        issue['comments']['nodes'] = comments
        return matches(rec, issue, trusted_author)
    except Exception:
        return None
