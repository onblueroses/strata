# The viewer stack

Everything under the browser: one shared localhost server, name-as-URL pages that reload themselves
when you re-publish, the payload contract, and the numpy layer that builds it honestly.

```
capture_*()/prepare_*() -> payload dict (+ full arrays, kept in Python)
  -> template.read_text().replace("__PAYLOAD__", blob)
  -> publish(name, html, arrays) -> (url, first_seen)
       bind 127.0.0.1:8123..8142 in a daemon thread, or, if that port is busy and
       answers /__health__ with our magic bytes, POST pages through that sibling
  -> pages[name] = {html, arrays, ver}
     /<name>/ the stored HTML  ·  /<name>/ver polled every 1500 ms, reload on change
     /<name>/fiber exact stats from the FULL array  ·  / 302s to the newest name
```

Only two things cross the Python/JS boundary: the one-shot inlined payload, and `/fiber` for the
numbers decimation cannot answer honestly.

## The whole server

Runnable as written; 23-assertion suite green, including the two-process adoption path. Drop it in as
`viewserve.py` next to your templates.

```python
"""One shared localhost page registry: publish(name, html) -> (url, first_seen)."""

import base64, io, json, math, os, threading, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import numpy as np

HEALTH = b"myproj-viz"   # this string IS the identity; change it per project
_srv = _port = _remote = None
pages = {}               # name -> {"html", "arrays", "ver"}
last = {"name": None}
_lock = threading.Lock() # threaded server + read-modify-write on ver

def _register(name, html, arrays):
    with _lock:
        first = name not in pages
        ver = 1 if first else pages[name]["ver"] + 1
        pages[name] = {"html": html, "arrays": arrays or {}, "ver": ver}
        last["name"] = name
    return first

def _sig(v, d=5):        # significant figures, not decimal places
    v = float(v)
    return float(f"{v:.{d}g}") if math.isfinite(v) else None

def _line_stats(line):
    f = line[np.isfinite(line)]
    return {"n": int(line.size),          # TRUE length, never the drawn one
            "mean": _sig(f.mean()) if f.size else None,
            "std": _sig(f.std()) if f.size else None,
            "min": _sig(f.min()) if f.size else None, "max": _sig(f.max()) if f.size else None}

class _H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # honest only because every response is sized

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/__health__":
            return self._send(200, "text/plain", HEALTH)
        if u.path == "/":
            if last["name"] is None:
                return self._empty(204)
            return self._redirect(302, "/" + quote(last["name"], safe="") + "/")
        parts = u.path.strip("/").split("/")
        name = unquote(parts[0])
        if name not in pages:
            return self._empty(204)              # favicon and friends
        if len(parts) == 1:
            if not u.path.endswith("/"):         # /name -> /name/ so the page's
                return self._redirect(301, u.path + "/")  # relative fetches hit
            return self._send(200, "text/html; charset=utf-8", pages[name]["html"])
        if len(parts) == 2 and parts[1] == "ver":
            return self._send(200, "application/json",
                              json.dumps({"ver": pages[name]["ver"]}).encode())
        if len(parts) == 2 and parts[1] == "fiber":
            return self._fiber(name, u)
        self._empty(204)

    def do_POST(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))  # drain first
        if len(parts) != 1 or self.headers.get("Origin"):
            return self._empty(404)              # never accept a cross-origin write
        try:
            body = json.loads(raw); html = body["html"].encode()
        except (ValueError, KeyError, AttributeError):
            return self._empty(400)              # a malformed publish is not a crash
        first = _register(unquote(parts[0]), html, _decode(body.get("npz")))
        self._send(200, "application/json", json.dumps({"first": first}).encode())

    def _fiber(self, name, u):
        q = parse_qs(u.query)
        try:
            arr = pages[name]["arrays"][q["a"][0]]
            idx = [int(v) for v in q["i"]]       # ?a=w&i=3&i=7: one i per axis
        except (KeyError, ValueError):
            return self._empty(400)
        if len(idx) != arr.ndim or not all(0 <= v < d for v, d in zip(idx, arr.shape)):
            return self._empty(400)
        axes = []
        for ax in range(arr.ndim):
            sl = list(idx); sl[ax] = slice(None)
            axes.append({"axis": ax, **_line_stats(arr[tuple(sl)])})
        self._send(200, "application/json",
                   json.dumps({"value": _sig(arr[tuple(idx)]), "axes": axes}).encode())

    def _send(self, code, ctype, body):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")   # same URL, new document
        self.end_headers(); self.wfile.write(body)

    def _redirect(self, code, loc):
        self.send_response(code); self.send_header("Location", loc)
        self.send_header("Content-Length", "0")   # or HTTP/1.1 hangs the client
        self.end_headers()

    def _empty(self, code):
        self.send_response(code)
        self.send_header("Content-Length", "0"); self.end_headers()

    def log_message(self, *a):
        pass                                     # do not spam the notebook

def _encode(arrays):
    if not arrays:
        return None
    buf = io.BytesIO(); np.savez_compressed(buf, **arrays)
    return base64.b64encode(buf.getvalue()).decode()

def _decode(blob):
    if not blob:
        return {}
    with np.load(io.BytesIO(base64.b64decode(blob))) as z:
        return {k: z[k] for k in z.files}

def _alive(p):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{p}/__health__", timeout=0.5) as r:
            return r.read() == HEALTH   # exact magic bytes: another copy of me
    except OSError:
        return False

def _connect(port):
    global _srv, _port, _remote
    for p in range(port, port + 20):
        try:
            _srv = ThreadingHTTPServer(("127.0.0.1", p), _H)   # never 0.0.0.0
        except OSError:
            if _alive(p):                # busy AND ours: publish through it
                _remote = p; return
            continue                     # busy with a foreign app: next port
        _port = p
        threading.Thread(target=_srv.serve_forever, daemon=True).start()
        return
    raise OSError(f"no free port in {port}..{port + 19}")

def _post(p, name, html, arrays):
    body = {"html": html.decode(), "npz": _encode(arrays)}
    req = urllib.request.Request(f"http://127.0.0.1:{p}/{quote(name, safe='')}",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["first"]

def publish(name, html, arrays=None, port=8123):
    """Register/replace one named page; returns (url, first_time_seen)."""
    global _remote
    if _srv is None and _remote is None:
        _connect(port)
    while _remote is not None:           # loop, never fall through
        try:
            return (f"http://127.0.0.1:{_remote}/{quote(name, safe='')}/",
                    _post(_remote, name, html, arrays))
        except OSError:                  # the sibling died: become the server
            _remote = None
            _connect(port)
    return (f"http://127.0.0.1:{_port}/{quote(name, safe='')}/",
            _register(name, html, arrays))

def _blob(payload):
    return (json.dumps(payload, allow_nan=False)  # NaN is not JSON; catch it here
            .replace("</", "<\\/")                # would close the <script> element
            .replace("<!--", "<\\u0021--"))       # flips the tokenizer, same result

def serve(payload, template, name="view", port=8123, open_browser=True, arrays=None):
    """Render one template around `payload` and publish it; returns the URL."""
    payload["name"] = name
    html = Path(template).read_text().replace("__PAYLOAD__", _blob(payload)).encode()
    url, first = publish(name, html, arrays, port)
    print(f"viewer: {url}", flush=True)          # the receipt, browser or not
    if open_browser and first and not os.environ.get("VIZ_NO_BROWSER"):
        webbrowser.open(url)
    return url
```

## The page's half of the protocol

```html
<script>
const D = __PAYLOAD__;          // object literal, parsed with the script itself
document.title = D.name;        // one tab per name; the tab strip is the index

// re-publish -> self-reload. Relative 'ver', which is why /<name> must 301 to /<name>/.
fetch('ver').then(r => r.json()).then(({ ver }) => {
  setInterval(() => fetch('ver').then(r => r.json())
    .then(v => { if (v.ver !== ver) location.reload(); })
    .catch(() => {}), 1500);
}).catch(() => {});
</script>
```

Both `.catch`es are load-bearing: a dead kernel makes the poll fail forever in silence, so the viewer
degrades to a static snapshot instead of an error page. Same posture on the `/fiber` fetch
(`reference-viz/viz/tensor.html:417-424`, "kernel gone: leave the page usable"). A version *decrease* also
reloads, which is what a restarted kernel counting from 1 produces.

## Why each piece is there

**`first_seen` is the only state gating `webbrowser.open`.** `_register` answers it in the four lines
that also define the naming model (`reference-viz/viz/server.py:42-48`); every caller uses it the same way
(`tensor.py:44-47`, identically `model.py:29-32`). Re-running a cell forty times prints forty URLs and
opens exactly one tab. Re-execution is the notebook's basic verb, so a tool that spawns a tab per
execution is unusable by cell 20. The print runs unconditionally, and `flush=True` is what keeps that
receipt visible under a pipe.

**The caller-chosen name is the URL.** No id allocation, no session token, no registry object. Two
names are two tabs; the same name twice is one tab whose content was replaced. `quote(name, safe="")`
matters: the default `safe="/"` lets a name containing a slash produce `/a/b/`, which `do_GET` splits
into two segments, misses in `pages`, and answers 204, i.e. a blank tab with no error anywhere.

**Templates are re-read from disk on every call** (`tensor.py:40`): no caching, no
`importlib.resources`, no module-level constant. That line separates the expensive state (model in
memory, captured tensors) from the cheap state (the page): edit the HTML, re-run one cell, and the
open tab reloads itself off the version poll. One file read per call buys a 1-second frontend loop.

**The payload is a JS object literal in source position, not `JSON.parse`.** The engine parses it
while parsing the script: no second request, no loading state, no race, and the served HTML is a
self-describing snapshot. The price is that the HTML tokenizer sees it first, so two escapes are
mandatory and neither is about JSON. `</` would end the `<script>` element mid-payload, and a label
like `</s>` or pasted HTML produces it; inside a JSON string `\/` is a legal escape for `/`, so the
value is unchanged. `<!--` flips the tokenizer into script-data-double-escaped state, where the
template's own `</script>` stops terminating the block; `!` is `!`, so again the value survives.
reference-viz escapes only the first (`tensor.py:42-43`). `ensure_ascii=True` is the default and already
neutralizes U+2028/U+2029.

**The NaN consequence of that choice.** `NaN` and `Infinity` are JS global identifiers, so in source
position they parse fine: no exception, no console error. One `NaN` then poisons `maxAbs`, the color
domain, and every `lerp` downstream until the view goes neutral; `JSON.parse` would have thrown.
`allow_nan=False` turns that silence into a `ValueError` at the boundary. Keep it, and make prep
responsible for never sending one.

**HTTP/1.1 plus `Content-Length` on every response, redirects included.**
`BaseHTTPRequestHandler.protocol_version` defaults to `"HTTP/1.0"`, under which the server closes the
socket after every response whatever headers you send (measured: raw socket gets EOF after one reply),
so five tabs polling `ver` at 1.5 s open a fresh TCP connection and thread every ~300 ms forever. The
1.1 line is half the fix; the other half is a correct `Content-Length` everywhere, because under 1.1 a
response with no length and no chunking leaves the client waiting for a body that never ends
(measured: `read()` on an unsized 301 raises `TimeoutError`). reference-viz sets neither
(`server.py:101-115`). With keep-alive on, `do_POST` must also drain the body before rejecting, or one
refused POST corrupts every later request on that connection.

**Security, both items.** Reject any POST carrying an `Origin` header: without it a page open in the
user's browser can POST arbitrary HTML that then runs on the localhost origin and can read every other
published page. Bind `127.0.0.1`, never `0.0.0.0`.

**The port is a rendezvous, not a resource.** Walk 20 candidates; on `EADDRINUSE` ask the occupant
`GET /__health__` and compare against exact magic bytes. A match means another copy of you, so become
its client and POST pages through it; a miss means a foreign app, so take the next port. Whoever owns
`pages` answers `first`, which is why `_post` returns the server's answer rather than computing one
locally: a fresh process publishing a known name gets `False` and opens no second tab. `publish` must
**loop** rather than fall through: reference-viz drops `_remote_port` on a failed POST, re-runs `_connect`
(which re-adopts the same live sibling and leaves `_server_port` as `None`), falls through to the
local branch, and returns a URL with the literal text `None` as the port (`server.py:121-134`). The
mechanism buys one scenario, a live kernel holding 8123 while a headless run executes the same cells;
skip it if that never happens to you, keep everything else.

## capture / show, and testing the numbers without a browser

Enforce the split with module boundaries, not discipline. In reference-viz the capture modules import
torch and the library and import **nothing** from `server.py`; no HTML string appears in any of them,
and `prep.py` imports only `math` and `numpy`. `model.py` is then 115 lines of glue over one 14-line
`_serve` and four wrappers that each read `payload = capture_x(...)` then `_serve(payload, template,
...)` (`model.py:46-48`), so a whole new viewer costs one capture module, one template, one wrapper.

Export `capture_*`/`prepare_*` next to the `show_*` wrappers: the payload is the contract, and the
contract is testable without a browser. For end-to-end checks, run the server in-process with the
browser hard-disabled and read the payload back out of the served bytes.

```python
payload, arrays = prepare_grid(board, name="probe", max_cells=1600)
assert payload["channels"]["norm"]["series"]["n"] == POSITIONS      # full row, not drawn
assert payload["channels"]["write"]["values"][0][0] is None         # absent stays absent

os.environ["VIZ_NO_BROWSER"] = "1"      # plus: stub webbrowser.open to raise, so a
import webbrowser                       # regressed guard fails loudly, not silently
webbrowser.open = lambda *a, **k: (_ for _ in ()).throw(AssertionError("headless broken"))

def payload_of(html):        # the inlined literal, un-escaped back to JSON
    lit = html.split(b"const D = ", 1)[1].split(b";\n", 1)[0]
    return json.loads(lit.replace(rb"<\/", b"</"))
```

Assert: same URL after re-publish, `ver` incremented, no second page created, `/` 302s to the last
name, `/name` 301s to `/name/`, a payload holding `</script><!--<script` survives intact, a name
holding `/` percent-encodes into one segment, a POST with `Origin` is refused, `/fiber` matches numpy.

## prep: numpy to payload

**Coerce duck-typed, then collapse rank once.** `hasattr(a, "detach")` handles torch on any device
without importing torch, and recursing into tuples accepts a raw `hidden_states` return directly
(`prep.py:11-19`). Then map any rank onto one fixed shape by padding with `1`s and merging leading
axes (`as_slices`, `prep.py:22-37`), so rank-specific behavior ("1D draws as a line, 2D as a plane")
falls out of where the `1`s land instead of being a case analysis in JS.

**Decimate, never average** (`prep.py:40-50`):

```python
def stride_plan(shape, max_cells):          # greedy on the currently-largest axis
    strides = [1] * len(shape)
    kept = lambda i: math.ceil(shape[i] / strides[i])
    while math.prod(kept(i) for i in range(len(shape))) > max_cells:
        strides[int(np.argmax([kept(i) for i in range(len(shape))]))] += 1
    return strides                          # arr[tuple(slice(None, None, s) for s in strides)]
```

`::k` keeps every drawn cell a real element at a real index, which is what makes click-to-fiber
reconstructible; greedy-largest keeps the kept block roughly isotropic instead of crushing one axis
flat. Ship the strides and disclose them in the UI: they are the only bridge between grid coordinate
and array coordinate.

**Precision is a wire decision, made once per quantity, in significant figures.** `round(v, 5)` is
absolute rounding on a quantity whose scale is unknown, so an array living at 1e-6 sends a page full
of `0.0` while the sidebar prints a correct nonzero std, and the page contradicts itself with no
warning (`float(f"{1.2e-7:.5g}")` is `1.2e-07`; `round(1.2e-7, 5)` is `0.0`). reference-viz ships
`round(float(v), 5)` (`tensor.py:38`) and survives only because residual streams sit near unit scale.
Pick digits by how the number is read: values 5, probabilities 4, bits 3, norms 2.

**Two arrays: raw for statistics, scrubbed for rendering** (`tensor.py:26-29`).

```python
arr  = to_numpy(tensor)
raw  = as_slices(arr)                                                   # stats, /fiber
grid = as_slices(np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0))   # what gets drawn
```

Skipping the scrub poisons the renderer silently. Applying it to both is worse: `nan_to_num` maps NaN
to `0.0`, a legal value in the data, so scrubbed statistics report a mean and a density that quietly
absorb the corruption. Count what you scrubbed (`nans`, `infs` as their own fields) and render those
rows only when non-zero (`tensor.html:277-278`).

**Absence is not zero, and the wire has a token for it.** In cell grids and per-row series ship JSON
`null` where nothing was measured; it survives `allow_nan=False`, the page leaves the cell unpainted,
the sparkline breaks its line, the tooltip says `n/a`. On a log channel a fabricated `0` is worse than
a gap, because it reads as "smallest" and pins the auto-fit to the floor.

**Robust color range, computed on the full array, with the clamp disclosed** (`prep.py:53-64`): the
q-th percentile of `|value|`, because a few outlier channels at 40x the bulk std paint every ordinary
cell neutral under a max-based scale. Ship `cmax`, `maxAbs` and a `clipped` boolean so the legend can
prefix its top endpoint with `≥`; a robust scale that hides its clamping is a lying legend. Copy the
habit, not the constant: a normalization number is defensible only when its docstring states the
measurement that chose it.

**Degrade loudly when a field is too big to ship.** `capture.py:131-132` drops full attention maps past
`max_attn_values` (default 2e6, i.e. seq ≤ 117 for 12x12 heads), keeps the cheap per-head entropy grid,
sets the field to `None`, and the page reads it as a boolean and says so.

## The inverse axis chain: honest tooltips over merged axes

Flattening pads with `1`s and merges leading axes, so the page must say which *original* axis each
scene axis is. Three declarations do it (`tensor.html:240-249`):

```js
// grid order [w, y, z, x]; null where the tensor has no such axis
const axLabel =
  D.ndim <= 1 ? [null, 'y', null, null]
  : D.ndim === 2 ? [null, 'y', 'z', null]
  : D.ndim === 3 ? [null, 'y', 'z', 'x']
  : ['w', 'y', 'z', 'x'];
const axOrig =                       // original tensor axis behind each letter
  D.ndim <= 3 ? [null, 0, 1, 2]
  : [D.ndim > 4 ? `0..${D.ndim - 4}` : 0, D.ndim - 3, D.ndim - 2, D.ndim - 1];
const idxLabel = q => '[' + axLabel
  .map((L, j) => L && `${L} ${q[j]}`).filter(Boolean).join(', ') + ']';
```

- **`null` for axes the tensor does not have**, filtered by `.filter(Boolean)`. Without it a rank-2
  tensor's tooltip reads `[w 0, y 3, z 5, x 0]`: a lie about two axes that a reader cannot detect. The
  padding `1`s must never become visible coordinates.
- **`axOrig` renders a merge as a range**, `0..${D.ndim - 4}`, so a rank-6 tensor's scrub axis
  announces that it is three original axes flattened, not one; it surfaces in the `title` of the fiber
  table's axis column (`tensor.html:428`).
- **`ndim` ships separately from `dims`** (`tensor.py:32` vs `:34`) because `dims` is the
  post-flattening shape and has already lost the information.

Feed every index the user sees through `idxLabel`, in hover and click alike, after multiplying by the
strides: `full = [sl * D.strides[0], a * D.strides[1], ...]` (`tensor.html:665-668`). A drawn index
shown as an array index is the same class of lie.

## /fiber: the numbers a payload cannot hold

Exact statistics along one full row of a 4096-column array are not payload, they are a query. Ship a
decimated view, keep the full array in Python, answer per selection, so no per-row table ever has to
travel. The client is one relative fetch inside a `try`, which is why a dead kernel costs the fiber
panel and nothing else:

```js
const q = [r * D.strides[0], c * D.strides[1]];               // drawn index -> array index
try { f = await (await fetch(`fiber?a=${ch}&i=${q[0]}&i=${q[1]}`)).json(); } catch { return; }
```

Two properties make it honest: `n` per axis is the **true** fiber length, so a page holding every 4th
column still reports `n = 4096`; and the query is in original array coordinates, which only works
because decimation kept real elements.

**Budget for the transport, not the endpoint.** The hard half is that the array must reach whichever
process owns `pages`, and under sibling adoption that crosses a process boundary. The only path
through a JSON body is a byte blob: `np.savez_compressed` (or `np.save` for one array) into a
`BytesIO`, base64 into the body, `np.load(BytesIO(b64decode(...)))` on the far side. That is
`_encode`/`_decode` above; the reference viewer's version is `server.py:82-83` and `:163-168`. Skip it and the
failure is silent in the worst way: the local process works, the adopted-sibling path serves 400
forever, and the page shows no fiber stats because its fetch has a `.catch`. Base64 costs 33% on top
of the compressed bytes and the POST is synchronous, hence `timeout=30` rather than the reference viewer's 10. If
an array is too big to move, keep `/fiber` local-only and say so in the UI rather than letting clicks
do nothing.

## Symptom to cause

| What you see | What it is |
|---|---|
| Blank tab, no error, 204 in the log | name contains `/` and `quote` used the default `safe="/"` |
| `ver` poll and `fiber` 404 | page served at `/name` without the 301; relative fetches hit the root |
| A new thread and connection every ~300 ms | `protocol_version` left at HTTP/1.0, or a response missing `Content-Length` |
| Browser hangs on a redirect | HTTP/1.1 redirect with no `Content-Length: 0` |
| URL contains the literal `None` as the port | `publish` fell through the remote branch instead of looping |
| Whole view goes neutral, console clean | a `NaN` reached the object literal; scrub for rendering, set `allow_nan=False` |
| Flat zeros on the page, real stats in the sidebar | absolute `round(v, 5)` on a small-scale array; use `f"{v:.5g}"` |
| Click does nothing, no error | `/fiber` 400s because the arrays never crossed to the process owning `pages` |
| A second tab per cell run | `first_seen` ignored, or computed locally instead of read from the POST response |
