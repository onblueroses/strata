# Rendering techniques

The mark-drawing code: exact CSS and JS for DOM grids, canvas heatmaps, SVG sparklines and three.js
voxels, each with the gotcha that breaks it. Anchors point at `the reference visualization repository` @ `ac3fcec`.

## Dense DOM grids

Up to a few thousand marks that carry text or need hit-testing. The mark-bearing CSS lives in the
page's own style block, not the shared shell (`model.html:109-130`):

```css
#board { display: grid; gap: 2px; width: max-content; }
.bcell {
  width: 60px; height: 22px; line-height: 22px;
  font-size: 11px; text-align: center; border-radius: 2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding: 0 3px;
}
.bcell.rl {                                     /* row label */
  width: auto; min-width: 58px; text-align: right; color: var(--muted);
  position: sticky; left: 0; background: var(--card); z-index: 1; padding-right: 8px;
}
.bcell.th {                                     /* column header, clickable */
  color: var(--ink-2); font-weight: 600; cursor: pointer;
  border: 1px solid transparent; line-height: 20px;
}
.bcell.th:hover { border-color: var(--hairline); }
.bcell.th.on { border-color: var(--muted); color: var(--ink); }
.bcell.c { color: var(--ink); cursor: pointer; }
.bcell.c.sel   { outline: 1px solid var(--ink); outline-offset: -1px; }
.bcell.c.oncol { box-shadow: inset 0 0 0 1px var(--colshadow); }
```

The 11px-row variant puts a label column, the heatmap and per-row bars in one three-column grid;
they register to each other purely by sharing `gap: 1px` and `height: 11px` (`kv.html:109-132`):

```css
#stage { display: grid; width: max-content;
         grid-template-columns: max-content max-content max-content; column-gap: 10px; }
#grid, #rls, #bars { display: grid; gap: 1px; width: max-content; }
.cell  { width: 50px; height: 11px; border-radius: 1px; background: var(--mid); }
.rl    { font-size: 9.5px; color: var(--muted); text-align: right; height: 11px;
         line-height: 11px; padding-right: 6px; font-variant-numeric: tabular-nums; }
.bar   { height: 11px; display: flex; align-items: center; }
.bar i { display: block; height: 7px; background: var(--orange); border-radius: 1px; }
.tok   { width: 50px; font-size: 10.5px; text-align: center; overflow: hidden;
         text-overflow: ellipsis; white-space: pre; }   /* pre: a leading-space token stays one */
```

- **`width: max-content` on the grid pairs with `overflow-x: auto` on a wrapper; neither works
  alone.** A grid is a block box, so without `max-content` a 117-column board compresses into the
  card and every 60px cell collapses; without the wrapper the overflow has nothing to scroll in. The
  pairing is exact here: `max-content` eight times, and `.scroll { overflow-x: auto; padding-bottom:
  4px; }` once per flat viewer (`model.html:107`, `kv.html:90`, `transmission.html:109`).
- **Sticky row labels need the opaque `background`.** Without it the scrolling cells show *through*
  the label; that smear is why people conclude sticky columns do not work.
- **Selection is `outline` and `box-shadow: inset`, never `border`.** Both paint inside the box, so a
  class toggle on one cell cannot reflow the other 1,399. Where a border is unavoidable, pay for it
  in the same rule: `border-bottom: 2px solid var(--orange); line-height: 20px;` holds 22px.
- Text fitting needs all three of `overflow: hidden`, `text-overflow: ellipsis`, suppressed wrapping;
  `background: var(--mid)` as the `.cell` default makes the grid read as "all zero" before the first
  `recolor()`.

### Build once, recolor by one property

~1.4k cells in one `innerHTML` write, never rebuilt (`model.html:383-398`, `:401-414`):

```js
board.style.gridTemplateColumns = `max-content repeat(${seq}, 60px)`;
let html = '';
for (let d = N; d >= 0; d--) {
  html += `<div class="bcell rl" title="${rowTitle(d)}">${rowLabel(d)}</div>`;
  for (let p = 0; p < seq; p++)
    html += `<div class="bcell c" data-d="${d}" data-p="${p}">${disp(D.top[d][p][0])}</div>`;
}
board.innerHTML = html;
const cells = board.querySelectorAll('.bcell.c');   // captured ONCE, reused for life

function recolor() {
  const m = M[metric];
  cells.forEach(c => {
    const t = mT(m, m.v(+c.dataset.d, +c.dataset.p));
    c.style.background = t === null ? 'transparent' : ramp(BLUE, t);
  });
  document.querySelectorAll('#metrics button')
    .forEach(b => b.classList.toggle('on', b.dataset.m === metric));
  document.getElementById('bar').style.background =
    `linear-gradient(90deg, ${ramp(BLUE, 0)}, ${ramp(BLUE, 1)})`;   // legend from the mark's own fn
  document.getElementById('lmin').textContent = fmt(m.lo) + m.unit;
  document.getElementById('lmax').textContent = fmt(m.hi) + m.unit + (m.log ? ' (log)' : '');
  document.getElementById('mdesc').textContent = m.desc;
}
```

One grid-template declaration, no per-cell positioning, no measurement pass; `dataset` carries the
coordinates; hit testing is three delegated listeners on `board`, and the *absence* of an attribute
is the type tag (`c.dataset.d === undefined` separates a data cell from a column header). Because
recolor writes one property, text, order, scroll position and selection all survive a metric switch,
so the reader's spatial memory ("the cell that said ` Paris` is three up and two right") holds across
every channel. A grid that re-lays out on channel switch destroys the model it just built.

```js
const ramp = (rgb, t) => `rgba(${rgb}, ${(0.06 + 0.88 * Math.max(0, Math.min(1, t))).toFixed(3)})`;
```

`rgba` over an opaque card is correct in both themes with no theme hook. Copy the rule, not the
numbers: `transmission.html:281` uses `0.07 + 0.68 * p` because its cell text is 10.5px monospace,
and `kv.html:297` spends the whole range as `(v / max) ** 0.7` because its cells hold no text,
falling back to `var(--mid)` at zero so "no data" stays distinct from "tiny value".

## The metric table

One object per channel drives buttons, color, legend endpoints, unit suffix and help text, so adding
a channel is one entry and nothing else (`model.html:331-378`):

```js
const M = {
  prob: { label: 'lens confidence', unit: '', lo: 0, hi: 1,        // fixed domain, declared
          desc: 'probability the lens gives its top token: how settled the guess already is',
          v: (d, p) => D.topP[d][p][0] },
  kl:   { label: 'KL to final', unit: ' bits',                     // domain observed below
          desc: "how far this depth still is from the final distribution; 0 means settled",
          v: (d, p) => D.kl[d][p] },
  attn: { label: 'attention write', unit: '', log: true,
          desc: "L2 of what this block's attention added (embeddings row has none)",
          v: (d, p) => d > 0 ? D.attnWrite[d - 1][p] : null },     // null = no value here
};
for (const m of Object.values(M)) {            // observed range where not fixed
  if (m.lo !== undefined) continue;
  let lo = Infinity, hi = -Infinity;
  for (let d = 0; d <= N; d++) for (let p = 0; p < seq; p++) {
    const x = m.v(d, p);
    if (x === null) continue;
    lo = Math.min(lo, x); hi = Math.max(hi, x);
  }
  m.lo = lo; m.hi = hi;
}
const mT = (m, x) => {                         // value -> 0..1 ramp position
  if (x === null) return null;
  if (m.log) {
    const lo = Math.log10(Math.max(m.lo, 1e-9)), hi = Math.log10(Math.max(m.hi, 1e-9));
    return hi > lo ? (Math.log10(Math.max(x, 1e-9)) - lo) / (hi - lo) : 0.5;
  }
  return m.hi > m.lo ? (x - m.lo) / (m.hi - m.lo) : 0.5;
};
document.getElementById('metrics').innerHTML = Object.entries(M)
  .map(([k, m]) => `<button data-m="${k}">${m.label}</button>`).join('');
document.getElementById('metrics').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (b) { metric = b.dataset.m; recolor(); }
});
```

- **`v(i, j)` is uniform across channels and returns `null` for "no value here"**, never `NaN` or `0`;
  `null` survives to `background: transparent`, so an absent cell is visibly absent.
- **Declare the domain where it is semantic, observe it otherwise**, skipping nulls; the legend reads
  the same `m.lo`/`m.hi` the color reads, so no refactor can paint one scale and label another.
- **A degenerate domain collapses to 0.5, never 0**: "no variation here" is true, "all minimum" is not.
- **`log` is a property of the quantity**, applied in `mT` and suffixed onto the legend from the same
  flag.

## Canvas 2D dense heatmaps

Past ~10k marks (an N×N attention map at N ≥ 100). Nine lines carry the DPR contract
(`model.html:678-685`):

```js
const cs = Math.max(6, Math.min(22, Math.floor(560 / seq)));  // solve for a target width, then clamp
const lw = cs >= 9 ? 64 : 0, lt = cs >= 9 ? 46 : 0;           // chrome, or none at all
const Wc = lw + seq * cs, Hc = lt + seq * cs;
const dpr = devicePixelRatio || 1;
canvas.width  = Wc * dpr;  canvas.height = Hc * dpr;               // backing store
canvas.style.width = Wc + 'px'; canvas.style.height = Hc + 'px';   // CSS box
const ctx = canvas.getContext('2d');
ctx.scale(dpr, dpr);                                               // now think in CSS px
```

- **Assigning `canvas.width` every draw resets the transform and clears the bitmap.** Hence no
  `clearRect`, and hence the repeated `ctx.scale(dpr, dpr)` does not compound. A refactor that hoists
  sizing out of the draw breaks it twice, silently: stale pixels plus a compounding scale.
- **Solve cell size for a target width, then clamp**: `[6, 22]` stops a 3-token prompt producing
  186px blocks and a 117-token prompt producing 4px slivers.
- **Drop chrome below a legibility threshold instead of shrinking it.** Gutter and rotated header go
  to zero at `cs < 9`; 9.5px text in an 8px row is worse than no text, and the tooltip still names
  both tokens.

```js
for (let q = 0; q < seq; q++)
  for (let k = 0; k <= q; k++) {                 // only the causal triangle
    ctx.fillStyle = mix(A[q][k] / hi);
    ctx.fillRect(lw + k * cs, lt + q * cs, cs - 1, cs - 1);   // cs-1: gaps without grid lines
  }
ctx.strokeStyle = document.documentElement.dataset.theme === 'light'
  ? 'rgba(28, 27, 24, 0.55)' : 'rgba(242, 241, 234, 0.55)';
ctx.lineWidth = 1;
ctx.strokeRect(lw - 0.5, lt + selP * cs - 0.5, (selP + 1) * cs, cs);   // -0.5: crisp hairline

ctx.textBaseline = 'alphabetic';                // canvas state is global; reset between passes
for (let k = 0; k < seq; k++) {                 // rotated column labels
  ctx.save();
  ctx.translate(lw + k * cs + cs / 2, lt - 4);  // translate to the anchor, THEN rotate
  ctx.rotate(-Math.PI / 4);
  ctx.textAlign = 'left';                       // label END lands at the column centre
  ctx.fillText(D.tokens[k].trim().slice(0, 8) || JSON.stringify(D.tokens[k]), 0, 0);
  ctx.restore();
}
```

The `cs - 1` gap is unpainted background, and on integer `cs` at integer offsets every edge lands on
an integer CSS pixel, so nothing smears at dpr 1 and it doubles cleanly at dpr 2. Leaving the masked
half as page background makes the triangular silhouette carry "this is causal attention" with zero
ink. A 1px stroke is centred on its path, so a path at integer x covers x−0.5 … x+0.5 and greys two
pixel columns; the −0.5 offset puts it on one, and the width `(selP + 1) * cs` hugs live cells
instead of boxing masked area (`model.html:689-715`).

**Gotchas.** Bind hover to the canvas, not `window`, and write the geometry object at the *end* of
the draw (`geo = { cs, lw, lt }`, `:722`) so a throwing draw leaves the previous consistent value.
Cache what the hover handler recomputes: `:730` calls `meanMap(selL)` inside `pointermove`, so every
mouse move allocates a seq×seq array and runs H·seq² additions.

## Sparklines in SVG

A per-depth or per-step series beside the grid it explains; 320×84 CSS px (`model.html:453-495`):

```js
const W = 320, H = 84, pl = 8, pr = 8, pt = 12, pb = 16;
const ys = values.map(v => opts.log ? Math.log10(Math.max(v, 1e-9)) : v);   // log BEFORE min/max
const lo = Math.min(...ys), hi = Math.max(...ys);
const X = i => pl + i * (W - pl - pr) / (values.length - 1);
const Y = v => hi > lo ? pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo)) : H / 2;
const path = ys.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join(' ');
const iMax = ys.indexOf(Math.max(...ys));
// in the SVG: peak label at x="${Math.min(Math.max(X(iMax), 24), W - 24)}"   (clamped)
//   plus a full-box hit target: <rect class="hit" x=0 y=0 width=W height=H fill="transparent"/>
el.querySelector('.hit').addEventListener('pointermove', e => {
  const r = svg.getBoundingClientRect();
  const i = Math.max(0, Math.min(values.length - 1,          // nearest-point snap, no dead zones
    Math.round((e.clientX - r.left - pl) / ((W - pl - pr) / (values.length - 1)))));
  cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i));   // pre-created hidden elements,
  dot.setAttribute('cx', X(i)); dot.setAttribute('cy', Y(ys[i]));   // moved, never re-created
  cross.setAttribute('visibility', 'visible'); dot.setAttribute('visibility', 'visible');
  tipShow(e.clientX, e.clientY, `<span class="m">${opts.name} ${i}</span> ${fmt(values[i])}`);
});
```

- **Min/max fit, not zero-anchored.** A line encodes shape; magnitude returns through the in-place
  peak label and hover. Bars take the opposite rule in the same file (`writesChart`, `:532`): length
  encodes magnitude, so `Y` is zero-anchored and the max is printed top-right, no y-axis drawn.
- **`hi > lo ? … : H/2`** draws a constant series as a centred flat line instead of dividing by zero.
- `.toFixed(1)` on every coordinate; two axis ticks total; guard `values.length === 1`, since `X`
  divides by `length - 1`.

## three.js instanced voxels

A 3D tensor or weight layout up to ~100k marks. Nothing runs without the preamble, and the preamble
is the entire runtime dependency (`tensor.html:215-225`, identical at `arch.html:187-197`):

```html
<script type="importmap">
{ "imports": {
  "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
  "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
} }
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const D = __PAYLOAD__;
```

1. **The importmap must precede the module script that resolves against it**; it is consumed when the
   first bare specifier resolves, so declared after you get `Failed to resolve module specifier
   "three"`. One importmap per document, and `type="module"` is mandatory for bare specifiers.
2. **`OrbitControls` is not in the core bundle**, hence the second mapping; trailing slashes on both
   sides make it a prefix map. To go offline, drop the files beside the template and map relative
   paths; only the importmap changes. Pin the version: `three@latest` breaks on someone else's
   release schedule.
3. **`__PAYLOAD__` lands inside a module, so `D` is module-scoped, not global.** No console poking at
   `D`, no second `<script>` reading it, no `onclick="…"` attribute handlers; attach every listener
   from inside the module. The flat DOM viewers use a classic `<script>` and are not subject to this,
   which is exactly the inconsistency that eats an afternoon.

```js
const stripOK = S > 1 && S * nSlice <= 300000;             // instance-count guard
const geo  = new THREE.BoxGeometry(0.82, 0.82, 0.82);      // 0.82 on a unit-1 pitch: free silhouette
const mesh = new THREE.InstancedMesh(geo, new THREE.MeshBasicMaterial(),
                                     stripOK ? S * nSlice : nSlice);   // capacity = worst case
const neg = new THREE.Color('#3987e5'), mid = new THREE.Color('#383835'),   // scratch + palette,
      pos = new THREE.Color('#e66767'), seq = new THREE.Color('#3987e5'),   // module scope, so the
      c = new THREE.Color(), m4 = new THREE.Matrix4(),                      // hot loop allocates
      zero = new THREE.Vector3(0, 0, 0);                                    // nothing
const posOf = idx => {                                     // row-major decode, centred on origin
  const a = Math.floor(idx / (dB * dC)), b = Math.floor(idx / dC) % dB, k = idx % dC;
  return [k - (dC - 1) / 2, (dA - 1) / 2 - a, b - (dB - 1) / 2];       // A->y negated: row 0 on top
};

function rebuild() {                             // threshold, slice, strip, theme all funnel here
  const t = curThresh(), nS = strip ? S : 1;
  mesh.count = nS * nSlice;
  let shown = 0;
  for (let s = 0; s < nS; s++) {
    const o = (strip ? s : curSlice) * nSlice;
    const [sx, sy, sz] = strip ? stripShift(s) : [0, 0, 0];
    for (let i = 0; i < nSlice; i++) {
      const v = vals[o + i], keep = Math.abs(v) >= t;
      if (keep) shown++;
      const [x, y, z] = posOf(i);
      m4.makeTranslation(x + sx, y + sy, z + sz);
      if (!keep) m4.scale(zero);                 // hide by collapsing to a point
      mesh.setMatrixAt(s * nSlice + i, m4);      // index = s * nSlice + i, everywhere
      const u = signed ? Math.max(-1, Math.min(1, v / cmax)) : Math.min(1, v / cmax);
      signed ? c.copy(mid).lerp(u < 0 ? neg : pos, Math.abs(u)) : c.copy(mid).lerp(seq, u);
      mesh.setColorAt(s * nSlice + i, c);
    }
  }
  mesh.instanceMatrix.needsUpdate = true;
  mesh.instanceColor.needsUpdate  = true;
  mesh.boundingSphere = null;                    // THE FIX; see below
  document.getElementById('tshown').textContent =           // disclose what the threshold removed
    shown.toLocaleString() + ' / ' + (nS * nSlice).toLocaleString()
    + ' (' + (100 * shown / (nS * nSlice)).toFixed(1) + '%)';
}
```

(`tensor.html:352-478`, plus the one line the repo is missing.) **No lights**: `MeshBasicMaterial` is
unlit, so screen color is a pure function of the datum; a lit material multiplies the value-encoded
color by a shading term and one value reads as two on differently-oriented faces. Shape comes back
through the 0.18 inter-voxel gap. **Thresholding is `Matrix4.scale(0,0,0)`, not add/remove**, so
`instanceId` stays a stable function of `(slice, voxel)` and picking is a modulo instead of a reverse
index table.

**The boundingSphere bug, in code.** `grep -c 'boundingSphere\|frustumCulled' tensor.html arch.html`
returns 0 in both. `InstancedMesh.raycast` in r160 does one whole-mesh sphere reject before looping
instances and computes that sphere **only when it is `null`**, so it is built once, on the first
pointermove, from whatever extent existed then (in scrub mode: one slice). Toggling strip mode moves
instances outside it and every floor except the central one goes silently unhoverable, because a
sphere reject looks exactly like a miss. Null it at the end of every rebuild, or call
`mesh.computeBoundingSphere()` and set `mesh.frustumCulled = false`. Same rule for `boundingBox`.

**A threshold slider needs no color rebuild.** The loop above re-uploads both buffers per `input`
tick; at strip scale that is ~12.8 MB of matrices plus 2.4 MB of colors per event on default
`StaticDrawUsage`, and the threshold changes no color at all:

```js
function applyThreshold() {                      // matrices only
  const t = curThresh(), nS = strip ? S : 1;
  for (let s = 0; s < nS; s++) { /* … setMatrixAt only, same s * nSlice + i index … */ }
  mesh.instanceMatrix.needsUpdate = true;
  mesh.boundingSphere = null;
}
let tQueued = false;
thresh.addEventListener('input', () => {         // coalesce to one per frame
  if (tQueued) return;
  tQueued = true;
  requestAnimationFrame(() => { tQueued = false; applyThreshold(); invalidate(); });
});
```

**Picking** resolves back to the original tensor index; the componentwise stride multiply is what
lets the tooltip quote a coordinate in the undownsampled tensor (`tensor.html:660-682`):

```js
function pick([cx, cy]) {
  mouse.set((cx / innerWidth) * 2 - 1, -(cy / innerHeight) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObject(mesh)[0];
  if (!hit) return tipHide();
  const sl = strip ? Math.floor(hit.instanceId / nSlice) : curSlice;
  const i  = hit.instanceId % nSlice;
  if (Math.abs(vals[sl * nSlice + i]) < curThresh()) return tipHide();   // else you hit a collapsed
  const a = Math.floor(i / (dB * dC)), b = Math.floor(i / dC) % dB, k = i % dC;   // point and report
  const full = [sl * D.strides[0], a * D.strides[1],                             // a ghost voxel
                b * D.strides[2], k * D.strides[3]];
  tipShow(cx, cy, idxLabel(full) + ' = ' + fmt(vals[sl * nSlice + i]));
}

let downXY = null;                               // click vs drag, one surface, 5px budget
renderer.domElement.addEventListener('pointerdown', e => downXY = [e.clientX, e.clientY]);
renderer.domElement.addEventListener('pointerup', e => {
  if (!downXY || Math.hypot(e.clientX - downXY[0], e.clientY - downXY[1]) > 5) return;
  /* … raycast, select … */
});
```

Bind to `renderer.domElement`, not `window`, so DOM panels swallow their own clicks;
`tensor.html:657` binds `pointermove` to `window` with no target check and raycasts behind
translucent panels.

## three.js log-scaled layout

For weight matrices drawn at true dimensions when those dimensions span orders of magnitude
(`arch.html:242-245`):

```js
const mats = [...D.embed, ...D.attn, ...D.mlp, D.head].filter(Boolean)
  .filter(e => e.shape.length >= 2);
const dmax = Math.max(2, ...mats.flatMap(e => e.shape));
const len  = d => 1.6 + 6.4 * Math.log(Math.max(d, 2)) / Math.log(dmax);
```

`log(d)/log(dmax)`, not `log(d/dmax)`, plus a floor. For GPT-2 (`dmax = 50257`): 2 → 2.01,
768 → 5.53, 3072 → 6.35, 50257 → 8.00, so a 65× dimension ratio becomes a 1.45× length ratio; without
it the vocab plate is 65× taller than d_model and the block stack is a smear at its foot. Compute
`dmax` once, globally, and call `len()` at every zoom level, so a 768 edge is the same length from
the overview and from inside a block (`tensor.html:503-504` is the same trick at gizmo scale with its
own floor). **Disclose the compression** in the info line and bake exact shape and param counts into
each plate's tooltip at build time (`arch.html:182`, `:294-295`): exact numbers one hover away are
what license a non-metric geometry.

Draw each tensor twice so ~90 mutually transparent plates survive; fill at 0.26 with
`depthWrite: false` never occludes and never z-fights, and the 0.9 wireframe is what the eye reads
(`arch.html:288-292`):

```js
const mesh = new THREE.Mesh(g, new THREE.MeshBasicMaterial(
  { color, transparent: true, opacity: 0.26, depthWrite: false }));
const edge = new THREE.LineSegments(new THREE.EdgesGeometry(g),
  new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 }));
```

## The four-line tween engine

Instead of a tween library, whenever a rAF loop already exists (`arch.html:750-756`, `:866-875`):

```js
const anims = [];
const ease  = t => t * t * (3 - 2 * t);                                   // smoothstep
const tween = (dur, fn, done) => { anims.push({ t0: performance.now(), dur, fn, done }); fn(0); };
const setOpacity = (root, f) => root.traverse(o => {
  const m = o.material;
  if (m) m.opacity = (m.userData.baseO ??= m.opacity) * f;
});

// inside the loop you already run:
const now = performance.now();
for (let i = anims.length - 1; i >= 0; i--) {         // BACKWARDS, so splice cannot skip
  const a = anims[i];
  const t = a.dur ? Math.min(1, (now - a.t0) / a.dur) : 1;   // dur 0 = jump to end
  a.fn(ease(t));
  if (t >= 1) { anims.splice(i, 1); a.done?.(); }
}
```

Four details make it correct rather than merely short: walking backwards means removing a finished
entry cannot skip the next; `fn(0)` fires synchronously at `tween()` time, so the opening frame is
the animation's own frame-0 state and never a flash of the un-animated pose; `dur: 0` degrades to an
instant apply (so the first view has no camera flight, `:785`); and `done?.()` runs after the splice,
so a callback starting another tween cannot corrupt the iteration. Concurrent tweens are just
multiple entries.

**`setOpacity` is the hard-to-rediscover line.** `??=` captures each material's *authored* opacity
once and never again, so a fade multiplies the relationship instead of flattening it. The naive
`o.material.opacity = f` destroys what makes the level legible: fills are authored at 0.26 and edges
at 0.9, so at `f = 0.6` a flat assignment makes fills *brighter* than authored and the wireframe
reading collapses. The memo also makes fading idempotent; without it, fading out and back in leaves
every material at the last `f` it saw and the scene decays on every zoom.

## kindColor

When marks are named by an upstream vocabulary you do not control (HF module names, ONNX ops, a
metrics namespace), map names to the palette with one regex ladder and a neutral fallback
(`arch.html:248-252`):

```js
const kindColor = s =>
  /attn|attention/i.test(s) ? COL.attn
  : /mlp|fc\b|gate|up_|down_|feed/i.test(s) ? COL.mlp
  : /norm|\bln/i.test(s) ? TC.gray
  : TC.neutral;
```

One function, four call sites, three vocabularies: called on `name + ' ' + cls`, on a path string,
and on a breadcrumb segment. **The fallback arm is load-bearing**: an unrecognised name gets a real
color that reads as "other", never `undefined` and never a crash. Note the mixed return types:
semantic hues (`COL.*`) are theme-invariant, neutrals (`TC.*`) track the page theme.

## Diff marking across four channels

One boolean, four encodings, plus an aggregate (`transmission.html:428-437`, CSS at `:140-141`):

```js
const diff = S.board.top[d][p][0] !== B.board.top[d][p][0];
changed += diff;
c.textContent = show(S.board.top[d][p][0]);
c.style.background = heat(diff ? RGB.o : RGB.b, S.board.topP[d][p][0]);   // 1: hue flips
c.classList.toggle('changed', diff);                                      // 2: inside border
c.classList.toggle('site', d === j && p === B.pos);                       // 4: intervention site
tipOn(c, () => cellTip('B (spliced)', S.board, d, p, diff
  ? `<div class="m">clean run said ${esc(show(B.board.top[d][p][0]))} `   // 3: the counterfactual
    + `(${(B.board.topP[d][p][0] * 100).toFixed(1)}%)</div>` : ''));
```

```css
.bcell.changed { border-bottom: 2px solid var(--orange); line-height: 20px; }
.bcell.site    { outline: 2px solid var(--orange); outline-offset: -2px; }
```

The redundancy is the point. Hue flips green → orange while **alpha keeps carrying confidence**, so
"changed" and "how sure" stay orthogonal; the 2px border survives when that alpha is near zero, and
its `line-height: 20px` holds the box at 22px so a diff on 300 cells reflows nothing; the tooltip
makes the diff legible as a counterfactual rather than merely marked; the site outline separates
"where the message landed" from "what it changed". One aggregate goes in the panel:
`cells changed in B: X of Y` (`:465`). **Make that denominator equal to what could have changed**: it
is `(N+1) × seq` here, but causal masking means only the last column can differ, so the reachable
maximum is `N − j + 1` and the ratio understates by roughly a factor of `seq`. Top-1 identity also
misses a cell whose probability moved 12% → 71% on the same token; say which predicate you diffed.

**Label the null in the same visual language as the win** (`transmission.html:486-497`):

```js
const same = P.spliced[d].answer === B.answer;
html += `<div class="mono ${same ? 'quiet' : ''}">${esc(JSON.stringify(P.spliced[d].answer))}`
      + `${same ? ' <span class="quiet">(= clean run: nothing crossed)</span>' : ''}</div>`;
```

Twelve rows, most usually saying "nothing crossed", in the page's own type, with the reading rule in
the subtitle: "Depths whose answer matches the no-message run carried nothing B could use." A null
rendered as an empty row reads as a bug; a null rendered as a labelled row reads as a result.

## Deep links into a zoom hierarchy

Write as the last thing every view change does (`arch.html:792-793`); read on load, validating before
honoring (`:912-916`):

```js
history.replaceState(null, '',
  '#' + (next.path ? '/' + next.path + (next.leaf ? '/' + next.leaf : '') : ''));

const [hp, hl] = decodeURIComponent(location.hash.replace(/^#\/?/, '')).split('/');
if (hp && nodeAt(hp)) zoomTo(hp, hl || null, null);
else setView(buildOverview(), null);
```

- **`replaceState`, not `pushState`.** State changes on every zoom, so `pushState` makes Back walk the
  zoom history one level at a time; worse, `setView` also runs on theme change (`:902`), so the back
  stack fills with entries nobody navigated to.
- **`nodeAt(hp)` before `zoomTo`.** A hash is untrusted text: hand-typed, truncated by a chat client,
  stale after the model changed. Validating against the real tree turns a bad link into the overview.
- **The `else` fall-through is not optional**; without it a page loaded with no hash renders an empty
  scene. Pair the whole thing with an escape hatch:
  `addEventListener('keydown', e => { if (e.key === 'Escape') zoomUp(); })` (`:859`) plus
  click-empty-space-to-zoom-up (`:855-857`). Neither is discoverable, so both belong in the legend.

## Render-on-demand vs continuous rAF

Both 3D viewers render unconditionally forever (`tensor.html:697-706`, `arch.html:866-880`), two full
renders per frame including the gizmo, no dirty flag, no `document.hidden` check. Fine for a viewer
open for a minute, wrong for anything left in a background tab. Continuous rAF is right only while
something genuinely always moves; otherwise invalidate:

```js
let dirty = true;
const invalidate = () => { dirty = true; };
controls.addEventListener('change', invalidate);     // orbit, zoom, and damping decay all fire this
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));   // re-apply on resize, and clamp
  frame();                                                 // keep the camera fit true
  invalidate();
});
(function loop() {
  requestAnimationFrame(loop);
  if (document.hidden) return;
  if (anims.length) invalidate();          // tweens keep it awake while they run
  if (!dirty) return;
  dirty = false;
  controls.update();                       // with damping on, re-fires 'change' until it settles
  renderer.render(scene, camera);
})();

let hoverXY = null, queued = false;        // raycast at most once per frame
renderer.domElement.addEventListener('pointermove', e => {
  hoverXY = [e.clientX, e.clientY];
  if (queued) return;
  queued = true;
  requestAnimationFrame(() => { queued = false; pick(hoverXY); });
});
```

Every mutation path then ends in `invalidate()`: rebuild, threshold, slice, selection, theme apply.
Miss one and the scene is correct in memory and stale on screen, so wire `invalidate()` into the same
function that sets `needsUpdate`. Throttling the hover matters because `intersectObject` on an
`InstancedMesh` is O(count) with a matrix multiply per instance and no spatial acceleration: at ~200k
instances an unthrottled `pointermove` is ~200k matrix multiplies per event. Same shape for any
slider driving an expensive rebuild; coalescing on rAF rather than a timeout keeps the update aligned
with the frame that displays it. While you are there, `selGroup.clear()` detaches children but
disposes nothing (`tensor.html:391-407` leaks four geometries per selection), so `dispose()` first.
