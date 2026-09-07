# Design system

Real token values for both themes, the theme mechanism, the type and space scales, the ramp math, and
the small interactions that carry the whole impression. Anchors point at `the reference visualization repository` @
`ac3fcec`, whose five viewers plus one dashboard share one system. The full copy-paste block is at the
bottom.

## Tokens: shared values, per-page sets

Every page declares only what it uses. The `:root` blocks are **not** identical; the *values* are.
That is what makes six pages read as one system while each stays minimal. The eight every page
declares (`--page --surface --hairline --ink --ink-2 --muted --scroll --scroll-hover`), plus:

| page | `:root` | adds | notably lacks |
|---|---|---|---|
| `model.html` | `:8` | `--card --mid --blue --red --orange --colshadow` | `--green` |
| `transmission.html` | `:8` | `--card --mid --blue --green --orange --colshadow` | `--red` |
| `kv.html` | `:8` | `--card --mid --blue --green --orange` | `--red --colshadow` |
| `tensor.html` | `:8` | `--mid --neg --pos --seq` | `--card`, every named hue |
| `arch.html` | `:8` | `--attn --mlp` | `--card --mid`, every named hue |
| `apps/arena/static/index.html` | `:8` | `--card --mid --blue --green --orange --violet --bad` | `--red --colshadow` |

- **`--card` is absent on the two WebGL pages**, where the canvas *is* the background and panels use
  `--surface` + `backdrop-filter`. On flat pages `--card` exists for one concrete reason: `position:
  sticky` row labels need something opaque to occlude the cells scrolling under them
  (`model.html:119`).
- **`arch.html` names its hues `--attn` / `--mlp`, `tensor.html` uses `--neg` / `--pos` / `--seq`.**
  Same hexes as `--blue` / `--red`. The token name states what the color means on that page, so a
  reader of the CSS learns the encoding.

The values, byte-identical wherever two pages share a token. Dark is the authored state; the light
column is what `:root[data-theme="light"]` overrides.

| token | dark | light | role |
|---|---|---|---|
| `--page` | `#0d0d0d` | `#f2f1ec` | the ground |
| `--card` | `#161615` | `#faf9f5` | opaque panel, over the page |
| `--surface` | `rgba(21,21,20,0.62)` | `rgba(252,251,247,0.72)` | translucent panel, over a canvas |
| `--hairline` | `rgba(255,255,255,0.09)` | `rgba(0,0,0,0.12)` | every border, divider, empty bar track |
| `--mid` | `#383835` | `#c9c7c0` | the zero point of every ramp (`tensor.html`: `#d8d6ce`, it sits on a lit scene) |
| `--ink` | `#f2f1ea` | `#1c1b18` | values, headings, selection ring |
| `--ink-2` | `#c3c2b7` | `#3c3b37` | table cells, tooltip body, buttons |
| `--muted` | `#8a8881` | `#77756e` | labels, captions, axis ticks |
| `--scroll` | `rgba(255,255,255,0.17)` | `rgba(0,0,0,0.19)` | scrollbar thumb (`-hover`: `0.32` / `0.36`) |
| `--colshadow` | `rgba(255,255,255,0.16)` | `rgba(0,0,0,0.22)` | inset ring marking a selected column |
| `--blue` `--green` `--orange` `--red` | `#3987e5` `#3fa46a` `#d95926` `#e66767` | unchanged | semantic hues |

**Publish the union, declare the subset.** Paste the block at the bottom into a new page and delete
what you do not use. An undeclared `var(--x)` is invalid-at-computed-value-time: the property falls
back to `unset` and the mark goes transparent or inherits, with no console error.

**The hue anchors never move; only the neutral does.** That "unchanged" row is the law. The four hues
are mid-lightness by construction, so `#3987e5` holds contrast against both `#0d0d0d` and `#f2f1ec`
and one string is correct in both themes, while the neutral tracks the page so near-zero marks stay
recessive in both. Scene code states it the same way (`arch.html:225,227`):

```js
const COL = { attn: '#3987e5', mlp: '#e66767' };            // never themed
const c = { ...COL, embed: TC.gray, head: TC.neutral, norms: TC.norm };
```

The one exception: the arena redeclares two hues in light mode (`index.html:29-30`), `--violet:
#8b6bd6 → #6d4fc4` and `--bad: #e66767 → #c73e3e`. A hue earns a light-mode twin when it is too light
to hold against `#f2f1ec`, or when its job is to read as *alarming* rather than merely visible. Four
hues plus two twins is the entire palette across six pages. Corollary for 2D marks: **prefer
`rgba(fixedHue, alpha)` over a computed color** and let the mark composite over the page, so the
string stays correct in both themes with no recomputation and no theme hook at all.

## Theme: tri-state on one key

One `localStorage` key, `reference-viz-viz-theme`, shared by every page: set it in any tab and all of them
honor it forever. The cycle is `dark → light → system`, and the button icon *is* the state readout
(moon / sun / half-circle), so there is no label. From `model.html:758-781`, icon SVGs elided:

```js
let themeMode = localStorage.getItem('reference-viz-viz-theme');
if (!['dark', 'light', 'system'].includes(themeMode)) themeMode = 'dark';
const sysDark = matchMedia('(prefers-color-scheme: dark)');
const THEME_ICONS = { dark: '<svg …moon…>', light: '<svg …sun…>', system: '<svg …half…>' };

function applyTheme() {
  document.documentElement.dataset.theme = themeMode === 'system'
    ? (sysDark.matches ? 'dark' : 'light') : themeMode;
  const btn = document.getElementById('theme');
  btn.innerHTML = THEME_ICONS[themeMode];
  btn.title = 'theme: ' + themeMode + ' (click to change)';
  localStorage.setItem('reference-viz-viz-theme', themeMode);
  onTheme();                                   // repaint hook; see below
}
document.getElementById('theme').onclick = () => {
  themeMode = { dark: 'light', light: 'system', system: 'dark' }[themeMode];
  applyTheme();
};
sysDark.addEventListener('change', () => { if (themeMode === 'system') applyTheme(); });
applyTheme();
```

- **`system` resolves to a concrete `data-theme` on the root.** CSS then needs only
  `:root[data-theme="light"]` and never a media query, and JS reads its own resolved state off
  `document.documentElement.dataset.theme` (`model.html:667`). Two sources of truth for "am I dark" is
  how a canvas ends up disagreeing with its own legend.
- **`matchMedia` re-applies only in system mode**, so an explicit choice survives an OS change, and
  **the persisted value is validated on read**, so a stale key cannot write `null` into the dataset.
- **`color-scheme` is declared for both states** (`model.html:39-40`). It themes the chrome CSS cannot
  reach: native form controls, and the overlay scrollbar Firefox draws over the page.
- Accept a theme from the query string when the page gets linked to (`index.html:1503`):
  `new URLSearchParams(location.search).get('theme') || localStorage…`.

## The repaint law, in three tiers

Declarative marks (DOM, CSS custom properties, inline SVG whose `fill`/`stroke` are `var(--…)`)
retheme for free. Immediate-mode marks (canvas 2D, WebGL, sprite atlases baked from canvas) are
snapshots of the palette at paint time. The repo pays three different prices, decided by how the mark
gets its color.

**Tier 0, no hook.** `transmission.html` and `kv.html` define `applyTheme` with *no* `onTheme()` call,
because every canvas mark is a fixed RGB with a varying alpha over the themed page
(`transmission.html:393-397`):

```js
img.data[4*i] = 217; img.data[4*i+1] = 89; img.data[4*i+2] = 38;   // --orange, fixed
img.data[4*i+3] = Math.round(255 * Math.sqrt(Math.min(1, Math.abs(v) / vmax)));
```

**Tier 1, one function.** `model.html:666-671` needs opaque cells, so it mixes toward the card color
and must re-mix on every theme change:

```js
let onTheme = () => {};                        // module scope, so any view can claim the hook
const surfOf = () => document.documentElement.dataset.theme === 'light'
  ? [250, 249, 245] : [22, 22, 21];            // --card, duplicated into JS
const mix = t => { const s = surfOf(); const org = [217, 89, 38];
  return `rgb(${s.map((v, i) => Math.round(v + (org[i] - v) * t)).join(',')})`; };
onTheme = drawHeat;                            // model.html:738, once the canvas exists
```

Same repo, same author, two answers to one problem; the alpha one is right, and this one exists only
because the mark had to be opaque.

**Tier 2, rebuild the scene.** Baked sprite labels cannot be re-tinted, so `arch.html:891-910` gives
`applyTheme` a `rebuild` flag, swaps a `TC` theme-constants object, sets `scene.background`, re-runs
`renderShares()`, and calls the level builder again. The boot call passes `false`, since nothing is
built yet. `tensor.html:637-643` pays less, because its labels are *tinted* rather than re-rasterized:
sprite canvases are baked once in light gray, then multiplied through `SpriteMaterial.color`.

```js
mid.set(T.mid);                     // shared Color object, so the ramp re-derives instead of forking
if (gizmo) gizmo.gScene.traverse(o => { if (o.isSprite) o.material.color.set(T.sprite); });
// THEMES holds only neutrals (tensor.html:616-619), keeping the hues out of the repaint entirely:
// dark: { page:'#0d0d0d', mid:'#383835', sel:0xf2f1ea, sprite:0xffffff }
// light:{ page:'#f2f1ec', mid:'#d8d6ce', sel:0x1c1b18, sprite:0x6b6a64 }
```

Aim for tier 0 whenever the mark can be alpha over the page.

## Ramps, and the ceiling that depends on what sits on the mark

```js
const ramp = (rgb, t) => `rgba(${rgb}, ${(0.06 + 0.88 * Math.max(0, Math.min(1, t))).toFixed(3)})`;
```

`model.html:327`. The `0.06` floor keeps a zero-valued cell faintly present instead of invisible; the
clamp makes a metric that overshoots its declared domain saturate rather than throw. Three variants
exist, and each is a decision about the mark:

| ceiling | where | why |
|---|---|---|
| `0.06 + 0.88t` → 0.94 | `model.html:327`, cells carrying **system-sans** text at 11px | strokes thick enough to survive a near-opaque fill |
| `0.07 + 0.68t` → 0.75 | `transmission.html:281`, cells carrying **monospace** at 10.5px | thin strokes and open counters lose against a saturated fill |
| `(v/max) ** 0.7` | `kv.html:297`, bare 50×11px cells, no text | gamma lifts a heavy tail into view; no floor needed, zero falls back to `--mid` |

The kv fallback is the part people skip: `if (!max || v === 0) d.style.background = 'var(--mid)'`
(`kv.html:298`), overwriting the empty string the ramp would otherwise leave. Transparent reads as
"no data"; `--mid` reads as "measured, and it is zero". Different claims.

**Emit the legend by calling the mark's own color function at the domain endpoints**
(`model.html:408-409`, `:721`):

```js
document.getElementById('bar').style.background =
  `linear-gradient(90deg, ${ramp(BLUE, 0)}, ${ramp(BLUE, 1)})`;
document.querySelector('#alegend .bar2').style.background =   // canvas view: the same mix()
  `linear-gradient(90deg, ${mix(0)}, ${mix(1)})`;             // the cells were painted with
```

The endpoint labels beside it come from the same metric descriptor that drove the scale
(`model.html:410-411`), so changing a domain updates the swatch and both numbers at once. A
hand-written gradient survives a ramp refactor and silently labels one scale with another.

## Typography

One family (`12.5px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif`, with `ui-monospace,
SFMono-Regular, Menlo, monospace` on `.mono`), no webfont, no icon font, and a scale living almost
entirely below the browser default.

**12.5px** base (body, panel rows, and `h1`/`h2`, which are base size at weight 600) · **11px** grid
cells, distribution rows, badges · **10.5px** monospace board cells, token labels · **10px** wire
captions, tick labels · **9.5px** SVG text and canvas labels · **9px** the one sub-label under a chip.

There is no scale in the usual sense: a base and four steps down for chrome. **Weight does the
promotion, not size.** `600` marks headings, selected states, and the one string carrying the
argument; everything else unset. No italics, no `text-transform: uppercase` in the five viewers, and
`letter-spacing` appears three times in ~3400 lines. The prose-bearing arena dashboard adds 11.5px for
subheadings and reserves **17px for exactly one thing, the value in a stat tile**
(`index.html:257`), plus 18px for a headline number inside a tooltip. One large number per tile is the
entire budget for large type.

Four rules keep it legible. Three ink tiers used semantically (`--ink` for values and the current
selection, `--ink-2` for supporting data, `--muted` for labels; a row is a `--muted` key left,
`--ink-2` value right). `font-variant-numeric: tabular-nums` on every column of figures, tooltips
included, since a 10px column without it shimmers on each hover update and reads as noise.
`line-height: 1.5` on the base, but a fixed pixel `line-height` equal to the cell height inside grids
(`22px` on a 22px cell), so text centers optically with no padding math. And `overflow: hidden;
text-overflow: ellipsis; white-space: nowrap` on every cell that can overflow, because a token can be
arbitrary text and a truncating cell keeps the grid rectangular.

## Space and structure

1 / 2 / 4 / 6 / 8 / 12 / 14 / 24 px, and the numbers are related, not coincidental. **1px** grid gap
when cells are 11px tall (`kv.html:112`) and every border · **2px** grid gap at 22px cells, plus
`border-radius` on essentially everything · **4 / 6 / 8px** intra-panel gaps and `.sect` padding ·
**12px** the universal margin, every fixed panel at `top/left/right/bottom: 12px` · **14px** card
horizontal padding, giving `.card { padding: 12px 14px }` · **24px** gutter between two blocks that
must read as separate regions · **236 / 248px** fixed panel width, 236 floating over a scene and 248
on a flat page · **272px** `#main { margin-left: 272px }` = 248 panel + 12 margin + 12 gutter.

**Radii are near-zero on purpose.** 52 of 68 declarations are `2px`; the `1px` ones are the smallest
marks; `5px` appears only on the scrollbar thumb, `50%` only on legend dots. Nothing is pill-shaped.
At this density a 6px radius eats a visible fraction of an 11px cell and the grid stops reading as one.

**The hairline idiom.** One token is every border, every divider (`.sect { border-top: 1px solid
var(--hairline) }`), and the fill of every empty bar track (`.dtrack { background: var(--hairline) }`).
Structure is drawn by contrast steps of a few percent, never by boxes inside boxes.

**Density.** Fixed-size cells on `width: max-content` grids inside `overflow-x: auto` wrappers; panels
pinned with `position: fixed` so the data region owns all the scroll. Grids are sized to the data, not
the container. Two panels describing the same thing share a metric rather than being laid out
independently: the distribution panel beside the board reuses the board's 22px rows and 2px gaps, so
its rows land on the same horizontal lines (`model.html:151-163`).

## Micro-interactions

Every one is 120ms on a single property, with no declared easing.

**Hover reveals a border that already exists.** The element ships with `border: 1px solid
transparent`; hover sets `border-color`. Zero layout shift, no shadow:

```css
.hcell { border: 1px solid transparent; transition: border-color 120ms; }
.hcell:hover { border-color: var(--muted); }
.hcell.on { border-color: var(--ink); }        /* selected is a stronger border, not a fill */
```

**Selection is an inset outline, never a fill.** `outline: 1px solid var(--ink); outline-offset: -1px`
(`model.html:129`) draws inside the box, so it cannot disturb a 2px grid gap and it survives whatever
the ramp painted. The column-level version is `box-shadow: inset 0 0 0 1px var(--colshadow)`, which is
why `--colshadow` is its own token: it must stay visible over a saturated cell and an empty one.

**One delegated tooltip per page.** A single `#tip`, `pointer-events: none` so it cannot capture its
own hover. Two ways to fill it, and the choice is cardinality.

*Baked at build* suits a bounded set of cells; each element carries its own text in `data-tip` (arena,
`index.html:1322`, `:1483`):

```js
document.addEventListener("mousemove", (e) => {
  const el = e.target.closest("[data-tip]");
  if (!el || !el.dataset.tip) { if (shown) { tip.style.display = "none"; shown = null; } return; }
  if (el !== shown) { tip.innerHTML = el.dataset.tip; shown = el; }   // swap only on change
  tip.style.display = "block";
  const w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = Math.max(6, Math.min(e.clientX + 14, innerWidth - w - 10)) + "px";
  tip.style.top = (e.clientY + 18 + h > innerHeight
    ? Math.max(6, e.clientY - h - 12) : e.clientY + 18) + "px";   // flip above near the bottom
});
```

Delegated, so re-rendering a table never re-attaches handlers, which is what lets that surface use
`innerHTML` wholesale.

*Lazy via closure* is required past a few hundred marks and is better whenever the tooltip is rich.
`model.html:426-441` keeps a builder closed over the payload and calls it on hover:

```js
function cellTip(d, p) { /* top-k table + norm/entropy/KL line, read from D */ }
board.addEventListener('pointermove', e => {
  const c = e.target.closest('.bcell.c');
  if (c) tipShow(e.clientX, e.clientY, cellTip(+c.dataset.d, +c.dataset.p)); else tipHide();
});
```

A depth × position board is easily 1500 cells; baking a ten-row table into each `data-tip` puts
megabytes of escaped markup in the DOM for content nobody will read. For canvas marks the closure is
the only option, since there are no elements to bake into. Take the arena's positioner either way:
`model.html:420-421` clamps but does not flip, so a tooltip near the bottom edge covers the cell it
describes.

**Structure inside the tooltip**: `#tip .h` is `--ink` at weight 600 (the identity of the thing), the
body `--ink-2`, `#tip .m` `--muted` for secondary metrics, and numbers go in a `<table>` with
`td:first-child` left-aligned and the rest right. Three lines of CSS between a tooltip and a readout.

## The scrollbar

Rules are in the block below; the mechanism is what matters. The `::-webkit-scrollbar` track is 10px
wide, but a **3px transparent border plus `background-clip: content-box`** keeps the paint inside the
padding box, so the visible thumb is a 4px pill floating in a transparent gutter. Hover drops the
border to 2px, which *thickens* the thumb under the cursor without changing layout. Firefox takes
`scrollbar-width: thin` plus `scrollbar-color: var(--scroll) transparent` instead, and `color-scheme`
handles its overlay bar. Repeat `background-clip` in the `:hover` rule: re-declaring the `background`
shorthand resets it, and dropping it makes the thumb jump to full width on hover.

## Tab identity: the favicon is half the design

One tab per named page, several open at once, so the tab strip is the real navigation surface, and six
identical globe icons destroy it. Every page carries a **data-URI SVG favicon that is a miniature of
what the page draws, in the page's own palette**. One line in `<head>`, no file, no request, no build
step (`tensor.html:6`, wrapped here; one unbroken attribute in the file):

```html
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'
 viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%230d0d0d'/%3E
 %3Crect x='6' y='6' width='9' height='9' fill='%233987e5'/%3E
 %3Crect x='17' y='17' width='9' height='9' fill='%23e66767'/%3E%3C/svg%3E">
```

Each is a compressed statement of its page: a 2×2 blue/gray/gray/red swatch (the diverging ramp
itself) for `tensor`; a 3×3 board with a lit diagonal for `model`; a spine carrying three plates for
`arch`; blue block, orange pill, green block for `transmission`; four orange cache rows feeding a
green box for `kv`; two bars and an orange dot for the arena.

- **Percent-encode every `#` as `%23`**, or the URL truncates at the fragment and you silently get no
  icon at all. **Use single quotes inside the SVG** so the `href="…"` attribute survives.
- **Paint an explicit background rect** (`fill='%230d0d0d' rx='6'`) rather than leaving it
  transparent: browsers composite favicons against tab chrome whose color you do not control. So the
  icon does not follow the theme toggle, which is correct. It is an identity mark, and an identity
  that changes appearance is not one.

`document.title = D.name + ' · tensor'` (`tensor.html:265`) closes the loop. **Name → URL → tab →
title → favicon is one identity chain**, every link set from the same caller-chosen name that
addressed the page (`/<name>/`, `viz/server.py:3`). That is why one-tab-per-name is ergonomic: after a
re-publish the tab you want is the one with the right icon and the right name, still where you left it.

## What is deliberately absent

No CSS framework, no utility classes, no component library, no icon font, no webfont: the three theme
icons are inline SVG strings in a `THEME_ICONS` map, everything else is a `<div>` with a background.
No JS dependency except `three` on the two WebGL pages, via importmap (`tensor.html:215-219`).

**Almost no shadows.** Four `box-shadow` declarations exist in ~3400 lines; three are `inset 0 0 0
1px`, a selection ring. The single real drop shadow is on the arena's floating tooltip
(`index.html:345`), where a layer genuinely floats. Elevation is otherwise the hairline border and
translucency over a scene.

What that buys: one file, no build step, instant load from a localhost server, survives being emailed
as an attachment, nothing that can go stale or fail to resolve, and density as high as the data
demands because no component's opinions about padding are in the way. The cost is writing the
interactions yourself, which is why this file is long.

## The block

Union of tokens plus the shell. Delete the tokens you do not use; keep the rest.

```css
:root {
  --page: #0d0d0d; --card: #161615; --surface: rgba(21, 21, 20, 0.62);
  --hairline: rgba(255, 255, 255, 0.09); --mid: #383835;
  --ink: #f2f1ea; --ink-2: #c3c2b7; --muted: #8a8881;
  --scroll: rgba(255, 255, 255, 0.17); --scroll-hover: rgba(255, 255, 255, 0.32);
  --blue: #3987e5; --green: #3fa46a; --orange: #d95926; --red: #e66767;
  --violet: #8b6bd6; --bad: #e66767; --colshadow: rgba(255, 255, 255, 0.16);
}
:root[data-theme="light"] {
  --page: #f2f1ec; --card: #faf9f5; --surface: rgba(252, 251, 247, 0.72);
  --hairline: rgba(0, 0, 0, 0.12); --mid: #c9c7c0;
  --ink: #1c1b18; --ink-2: #3c3b37; --muted: #77756e;
  --scroll: rgba(0, 0, 0, 0.19); --scroll-hover: rgba(0, 0, 0, 0.36);
  --violet: #6d4fc4; --bad: #c73e3e; --colshadow: rgba(0, 0, 0, 0.22);
  /* blue/green/orange/red hold in both themes: do not redeclare them */
}
:root { color-scheme: dark; }
:root[data-theme="light"] { color-scheme: light; }

html { scrollbar-width: thin; scrollbar-color: var(--scroll) transparent; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track, ::-webkit-scrollbar-corner { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--scroll); background-clip: content-box;
  border: 3px solid transparent; border-radius: 5px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--scroll-hover); background-clip: content-box; border-width: 2px;
}

* { margin: 0; box-sizing: border-box; }
body {
  background: var(--page); color: var(--ink);
  font: 12.5px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
/* flat page. Over a canvas, swap the fill for --surface + the backdrop-filter pair below */
.card {
  background: var(--card); border: 1px solid var(--hairline);
  border-radius: 2px; padding: 12px 14px;
}

h1, h2 { font-size: 12.5px; font-weight: 600; }
.sub { color: var(--muted); margin: 2px 0 10px; max-width: 720px; }
.row { display: flex; justify-content: space-between; gap: 8px; padding: 1.5px 0; }
.row .k { color: var(--muted); white-space: nowrap; }
.row .v {
  color: var(--ink-2); font-variant-numeric: tabular-nums;
  text-align: right; overflow: hidden; text-overflow: ellipsis;
}
.sect { border-top: 1px solid var(--hairline); margin-top: 8px; padding-top: 8px; }
.scroll { overflow-x: auto; padding-bottom: 4px; }   /* wrap every max-content grid in this */
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

button {
  background: none; border: 1px solid var(--hairline); border-radius: 2px;
  color: var(--ink-2); font: inherit; padding: 0 8px; cursor: pointer;
  line-height: 1.7; transition: border-color 120ms, color 120ms;
}
button:hover, button.on { border-color: var(--muted); }
button.on { color: var(--ink); }
button:disabled { opacity: 0.4; cursor: default; border-color: var(--hairline); }

#theme, #tip {                             /* the two floating layers */
  background: var(--surface);
  backdrop-filter: blur(14px) saturate(1.1);
  -webkit-backdrop-filter: blur(14px) saturate(1.1);
  border: 1px solid var(--hairline); border-radius: 2px; color: var(--ink-2);
}
#theme {                                   /* fixed toggle, top-right, icon-only */
  position: fixed; top: 12px; right: 12px; z-index: 5;
  width: 27px; height: 27px; padding: 0; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: border-color 120ms, color 120ms;
}
#theme:hover { border-color: var(--muted); color: var(--ink); }
#tip {
  position: fixed; display: none; pointer-events: none; z-index: 10;
  padding: 5px 9px; font-variant-numeric: tabular-nums; white-space: nowrap;
}
#tip table { border-collapse: collapse; }
#tip td { padding: 0 0 0 10px; text-align: right; }
#tip td:first-child { padding: 0; text-align: left; color: var(--ink); }
#tip .h { color: var(--ink); font-weight: 600; }
#tip .m { color: var(--muted); }

/* inline SVG inherits the palette, so charts retheme for free */
svg text { font: 9.5px system-ui, sans-serif; fill: var(--muted); }
svg .val { fill: var(--ink-2); }
```
