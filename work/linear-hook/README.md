# Linear webhook receiver

`linear-hook.py` listens behind a reverse proxy on loopback. It accepts Linear Issue, Comment and IssueLabel deliveries, checks the raw-body HMAC signature and timestamp, deduplicates retries, and appends each accepted event as one fsynced JSON line. The dispatcher tails that log. The receiver also forwards the same body to the steering agent off the request thread; it does not decide which events should create or claim work. A periodic dispatcher poll reconciles missed notifications.

Set secrets and endpoints through [env.example](deploy/env.example), and install [linear-hook.service](deploy/linear-hook.service) with its state directory writable by the service account. The webhook signing secret and steering token are separate protected files. The event log path must be readable by the dispatcher. The receiver exposes `/health` for local monitoring.
