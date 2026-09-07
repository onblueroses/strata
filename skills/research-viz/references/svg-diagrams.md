# Hand-authored SVG diagrams

Everything needed to type a research figure by hand: the file skeleton, the full light→dark hex map,
what the shapes and colors mean, how to lay out a fixed canvas without crowding, and two complete
skeletons that pass the theme linter. Evidence is `the reference visualization repository` @ `ac3fcec`: 44 files in
`doc/img/`, ~256 KB, no editor fingerprints, no build step.

## The file skeleton

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 170" width="960"
     font-family="ui-sans-serif, -apple-system, 'Helvetica Neue', sans-serif"
     font-size="12.5">
```
(`doc/img/k-pipeline.svg:1`)

- `width` equals the viewBox width and **`height` is absent on the root**, in all 44 files. The browser
  derives height from the ratio, so `max-width: 100%` scales the figure into the markdown column with
  no distortion and no second number to keep in sync.
- Root `font-size` is `13` in 43 files, `12.5` in one. The mono stack is
  `ui-monospace, Menlo, monospace`, applied per element.
- Absent everywhere: `<?xml?>`, `<!DOCTYPE>`, `preserveAspectRatio`, `<title>`, `<desc>`, `class=`,
  `style=`, gradients, filters, clip paths, `foreignObject`, `dominant-baseline`, `inkscape:`.
- Element census: `rect` 932, `text` 903, `line` 172, `path` 119, `marker` 60, `g` 51, `circle` 9,
  `tspan` 6. Austerity is the point: a rounded rect, a straight line, some text, sometimes an elbow.

## The dark-mode block

Copy it verbatim from Skeleton A below; it is byte-identical to `doc/img/k-pipeline.svg:2-26`. An md5
census over the `<style>` span of all 44 files: **37 identical copies**, 4 that add one rule, 2 that add
a hue family, 1 that wrongly subsets it. **Extend it, never subset it**; the three real extensions:

| extension | rules | why |
|---|---|---|
| cache orange | `[fill="#fed7aa"] { fill: #7c2d12; }` | a denser orange than the payload, for KV-cache cells (`v2-kv-channel.svg:10`, 4 files) |
| orange-800 as a **stroke** | `[stroke="#9a3412"] { stroke: #fdba74; }` | the canonical block maps `#9a3412` as a fill only (`v2-lossless.svg:26`) |
| a red tier | `[fill="#fef2f2"]→#450a0a`, `[fill="#dc2626"]→#f87171`, `[fill="#991b1b"]→#fca5a5`, `[stroke="#dc2626"]→#f87171` | one figure needed a fourth actor that is neither sender, receiver, nor message (`v1-run-belt.svg:10-26`) |

Insert new rules in hue order (grays, blues, oranges, greens, then the new family) so diffs stay
readable. `v1-causal-view.svg` is the one file that dropped the green rules it did not happen to use,
which is how a later edit acquires an unmapped green.

## Exactly what the remap reaches

Figures are referenced as external images (`![alt](img/x.svg)`), so they load as their own documents and
page CSS cannot enter; theming from inside is the only option. `[attr="value"]` matches the
**presentation attribute** as a literal string, while the declaration sets the **computed property**.
Two separate layers, which is why `[fill="#f9fafb"] { fill: #1f2937; }` and `[fill="#1f2937"] { fill:
#e5e7eb; }` coexist as a swap pair with no cascade loop: the attribute never changes, so nothing
re-matches. Probe rendered with `rsvg-convert` and read back pixel by pixel:

| markup | rule present | rendered RGB | remapped |
|---|---|---|---|
| `fill="#f9fafb"` | `[fill="#f9fafb"]` | `(31,41,55)` = `#1f2937` | yes |
| `fill="#1f2937"` | `[fill="#1f2937"]` | `(229,231,235)` = `#e5e7eb` | yes: the swap pair does not loop |
| `<g fill="#1f2937"><rect/>` | `[fill="#1f2937"]` | `(229,231,235)` | yes: children inherit the computed value |
| `<text>` with no fill anywhere | `svg { fill: #e5e7eb; }` | `(229,231,235)` | yes: this is the fall-through |
| `style="fill:#f9fafb"` | `[fill="#f9fafb"]` | `(249,250,251)` unchanged | **no**: the style attribute outranks the sheet |
| `fill="#FFF7ED"` | `[fill="#fff7ed"]` | `(255,247,237)` unchanged | **no**: value match is case-sensitive |
| `fill="#fff"` | `[fill="#ffffff"]` | `(255,255,255)` unchanged | **no**: literal string, not a color comparison |
| `stroke="#fff7ed"` | `[fill="#fff7ed"]` only | `(255,247,237)` unchanged | **no**: fill and stroke are separate properties |
| `stroke="#ea580c"` | `[stroke="#ea580c"]` | `(251,146,60)` = `#fb923c` | yes |

- **`svg { fill: #e5e7eb; }` is load-bearing.** Text with no fill up its ancestor chain inherits SVG's
  initial `fill: black`, invisible on `#111827`. `k-pipeline.svg:33-50` is a whole diagram relying on it.
- **Markers remap only because the marker `<path>` carries a literal `fill` attribute.** Keep it that way.
- **`fill="url(#grad)"` never matches**, and stops carry `stop-color`, a different property. Map each
  `<stop>` by hand, or do what the corpus does and use no gradients.
- **`opacity` bypasses the scheme**: it composites against a ground that flips from white to `#111827`,
  so effective contrast inverts. Three uses in the corpus, all where the flip does not matter.
- **`prefers-color-scheme` follows the OS, not the host page's toggle.** GitHub dark plus OS light gives
  a white figure on a dark page. That is the ceiling of the trick inside `<img>`; the only escape is to
  inline the SVG into HTML and key on `data-theme`, which no longer works from markdown.

## Palette with roles

Tailwind's default scale: light uses the 50/600/800 rungs, dark the 950/400/300 rungs of the same hue,
so every contrast relation survives the flip for free.

| light | Tailwind | role | dark |
|---|---|---|---|
| `#ffffff` | white | canvas rect; also "empty / not yet written" boxes, with a dashed `#d1d5db` outline | `#111827` |
| `#f9fafb` | gray-50 | neutral machinery: blocks, harness, panels, anything with no side | `#1f2937` |
| `#eff6ff` | blue-50 | **sender A** surfaces, A's token cells | `#172554` |
| `#ecfdf5` | emerald-50 | **receiver B** surfaces, answers | `#022c22` |
| `#fff7ed` | orange-50 | **the message / payload / tap** | `#431407` |
| `#fed7aa` | orange-200 | KV-cache cells: a denser orange than the payload | `#7c2d12` |
| `#d1d5db` | gray-300 | faded "not yet visible" text, inert bar fills | `#4b5563` |
| `#1f2937` | gray-800 | primary body text | `#e5e7eb` |
| `#6b7280` | gray-500 | secondary text, captions, footers, arrowheads, axis ticks | `#9ca3af` |
| `#e5e7eb` | gray-200 | **stroke only**: panel outlines, grid cell borders, gridlines | `#374151` |
| `#2563eb` | blue-600 | A's stroke and A's accent text | `#60a5fa` |
| `#1e40af` | blue-800 | A's text *inside* a blue box | `#93c5fd` |
| `#ea580c` | orange-600 | message stroke and accent text | `#fb923c` |
| `#9a3412` | orange-800 | message text *inside* an orange box | `#fdba74` |
| `#059669` | emerald-600 | B's stroke and B's accent text | `#34d399` |
| `#065f46` | emerald-800 | B's text *inside* a green box | `#6ee7b7` |
| `#fef2f2`/`#dc2626`/`#991b1b` | red-50/600/800 | a fourth actor, only when it is neither A, B, nor the message | `#450a0a`/`#f87171`/`#fca5a5` |

`#e5e7eb` is the most frequent stroke in the corpus and the quietest: structure you should not look at.
Make it the default outline; use a colored stroke only when the outline carries an argument.

**Two-tier text keeps colored boxes readable.** Box gets the `-50` fill and `-600` stroke; text *inside*
it gets `-800`; text *outside* referring to it gets `-600`. Both tiers remap to `-300` and `-400`.

**Never author a dark-mode hex.** `#9ca3af` is the *output* of `[fill="#6b7280"]`; written by hand it
matches no selector and renders as pale gray on white. Six corpus files carry exactly this defect.

## Visual vocabulary

Radius says what kind of thing a rect is:

| `rx` | thing | uses |
|---|---|---|
| 3 | a grid cell, 34×18 or similar | 513 |
| 8 | a box: a stage, a module, a callout | 138 |
| 10 | a panel or an agent | 29 |
| 5–6 | a token, a bar | 49 |
| `height/2` | a **payload pill**, the one shape reserved for "a message in flight" | 6 |

Stroke width says bandwidth: `1.5` default (163 uses), `2` for a latent wire carrying the state you care
about (34), `3` for a whole cache (4). Dashes mean hypothetical, removed, replaced, or a side channel;
`4 3` and `4 4` are the common values, `3 2` for a small cell.

| object | how it is drawn |
|---|---|
| a tensor / a state | rounded box labelled with its shape in mono, `[ 768 ]` or `768 numbers`, in the owner's hue; never a 3D slab, never isometric |
| a matrix / table | outlined `#f9fafb` rect, a few real rows drawn, the rest elided as `#d1d5db` rows of `· · · · ·`, dimensions labelled outside (`k-embedding-tables.svg:32-40`) |
| a stack of layers | repeated boxes on one row, `block 1`…`block 12` as `#6b7280` labels *above* the connectors; repeat a row template per token with `<g transform="translate(0, dy)">` (`k-residual-stream.svg:41-49`) |
| a token sequence | mono text, always: a run of `rx=5` pills, or one mono string with brackets underneath. Tokens are the one thing never set in sans |
| a KV cache | squared-off `#fed7aa` cells with no `rx`, one column per position, a solid slab so it reads as bulk rather than as values (`v2-kv-channel.svg:47-50`) |
| a wire | `<line>` with `marker-end`; gray `#6b7280` at `1.5` is plumbing, the owner's hue at `2` is the thing carried |
| a residual / skip | dashed cubic bezier in the owner's hue: `<path d="M 52 80 C 52 120, 488 120, 494 92" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="5 4"/>` (`k-block-wiring.svg:47`) |
| an add junction | `<circle r="14">` in the hue's `-50` fill with its `-600` stroke, bold `+` at `cy + 5` (`k-block-wiring.svg:44-45`) |
| a tap | a filled `r=4` dot **on** the wire, never a break in it, with the payload pill next to it: "read here, nothing removed" |
| an agent | a lane, not a box: one bold letter at `font-size="15" font-weight="700"` in the lane's hue in the left margin, then that actor's whole pipeline at one y |
| flow | left to right, one lane per actor, lanes stacked in the order the reader meets them; a crossing between lanes is vertical and in the message hue |
| a verdict | `✓` / `✗` at `font-weight="700"` in the owner's `-800`, appended to the label it judges; five uses in 44 files, and scarcity is what makes them read |

## Layout grammar for a fixed canvas

**Budget the width once per document, then hold it.** Corpus widths run 680 to 960 and cluster by
document prefix (`m-`/`n-`/`p-` at 920–940, `v1-`/`v2-` at 740–920, `k-` at 700–960). The number does
not matter; the constancy does, because a reader scrolling then sees figures sharing a left edge and a
scale. Heights are content-driven: as short as the content allows.

**Inside that width.** On a 320-tall canvas: 34 for the title, ~200 for the artwork, 24 for an axis or
brace label, the last 18 to 22 for the footer (corpus footer baselines sit 8 to 24 px above the bottom
edge, most often 18 to 20). In a flow: box height 36, connector gaps 44, boxes sized to their text plus
about 20 px. Do not equalize box widths; a box that needs 180 px gets 180 px.

**Label placement.** A box label goes at `(x + w/2, y + h/2 + 4)` with `text-anchor="middle"`. The `+4`
is an optical baseline shift for 12–13 px type, exact across the corpus; there is no
`dominant-baseline` anywhere. Hoist repeated `text-anchor`, `fill`, `font-family`, `font-size` onto a
wrapping `<g>` (`k-pipeline.svg:33`, `v2-meter.svg:42`).

**Markers.** One `<marker>` per arrow color (see either skeleton), with ids encoding file plus color
(`kvg`/`kvo`, `pdg`/`pdo`/`pdb`), because ids are document-global and two figures end up on one page.
`refX="9"` pulls the tip almost to the line end so the arrow lands **on** the target instead of
overlapping it; end the `<line>` about 2 px short and let the marker close the gap. `markerWidth` 7 is
standard, 6.5 for a finer head (`k-pipeline.svg:28`).

**Six anti-crowding moves, all in the corpus:**

1. **Leader line into a tinted callout box** in empty space, never a balloon over the artwork:
   horizontal, in the callout's hue, with the matching marker.
2. **An annotation gutter**: one vertical strip, usually the right third, reserved for prose, with every
   leader into it parallel.
3. **Rotate axis labels about their own anchor**, `text-anchor="end"` so the right edge stays pinned to
   its column: `transform="rotate(-40, 246, 364)"` where `246,364` is that text's own x,y.
4. **Two-line labels are two `<text>` elements** on the same x, 16 to 18 px apart for 12 px type (49
   instances at 18, 37 at 16). Never `<tspan dy>`, never `foreignObject`.
5. **Give the crowded side more canvas.** Panels are sized to contents, not made symmetric.
6. **Let the quiet stroke separate.** `#e5e7eb` borders on a `#eff6ff` grid separate hundreds of cells
   with no noise; a second color there is the usual mistake.

**Write the data-to-pixel mapping as an XML comment next to the pixels.** The highest-leverage habit in
the corpus, and almost no hand-authored chart has it:

```xml
<!-- decade gridlines: 1 B at x=180, 105 px per decade, up to 1 MB at x=810 -->
<!-- bar lengths = 105 * log10(bytes): 55 B -> 183, 4096 B -> 379, 552960 B -> 603 -->
<rect x="180" y="56" width="183" height="26" rx="5" fill="#d1d5db" stroke="#6b7280"/>
```
(`v2-meter.svg:32,48`. `105 × log10(55) = 182.6` and the bar is `width="183"`, so a reader can re-check
every bar from the comment alone.) The same habit at `k-pipeline.svg:32` lists the diagram's boxes in
reading order, so you find the one to edit without counting `<rect>`s.

**Positioning inside a monospace string.** A monospace advance is `0.6 × font-size` (measured 0.594 em
for this stack via `rsvg-convert`), so character *n* of a string starting at `x0` sits at
`x0 + 0.6 · fs · n`. That is how a dashed box or a brace lands exactly under a substring of a prompt:
`<!-- the prompt, 16px mono ≈ 9.6px/char, start x=60 -->` (`v1-run-prompt.svg:32`).

## Typography inside SVG

| px | job |
|---|---|
| 9–9.5 | axis tick labels, cell indices |
| 10–11 | rotated token labels, dense annotations |
| 11.5–12 | callouts, connector labels, footers, legends |
| 12.5–13 | body labels inside boxes (the root default) |
| 15–16 | agent badges, occasional titles |

`font-weight="600"` for a callout's first line or a title; `700` for agent badges, verdict glyphs, and
mono tokens that are the answer. Nothing else is bold; emphasis inside a running line is a `<tspan>`
with its own `fill` and `font-weight`, the only reason `<tspan>` appears at all.

Mono is reserved for tokens, tensor shapes, identifiers, and model outputs: if a string could be typed
into the model it is mono, if it describes the model it is sans.

## The captioning contract

| layer | carries |
|---|---|
| prose above | the *why*: the analogy, the misconception being killed, every term defined |
| **markdown alt text** | the *what*, as one declarative sentence containing the finding, written to stand alone with the image unloaded |
| the picture | the *shape*: adjacency, proportion, direction, what is inside what, what is dashed |
| **footer `<text>` inside the SVG** | the *therefore*, specifically the **negative claim** a picture is structurally incapable of making |
| prose below | consequences, numbers, the next question |

**The best alt text states the finding as a full sentence.** Not "pipeline diagram", not "figure 3":

```markdown
![A's fact becomes one 768-dim vector, never decoded, spliced mid-forward into B,
  which answers " Berlin."](doc/img/v1-overview.svg)
```
(`README.md:11`.) It is a property of the figure, not of the paragraph: byte-identical at every reuse
site. `v1-norm-gap.svg` is referenced from two documents with the same 137-character sentence both
times (`doc/knowledge.md:361`, `doc/notes.md:100`).

**The footer is the distinctive move.** One or two `#6b7280` 12 px lines at the bottom of the canvas,
always a negation, a scope limit, or a counterfactual:

```
v1-norm-gap.svg:45     Both are 768 numbers wide, so a mismatched splice raises no error.
                       It just returns garbage.
v1-splice-hook.svg:72  The hook fires right after block j writes its output and before
                       block j+1 reads it: mid-pass, not before, not after.
```

If the footer restates what the picture already shows, delete it and find the negation instead.

## Skeleton A: pipeline flow, 880 × 320

Distilled from `v1-overview.svg`, `v1-splice-hook.svg`, `k-pipeline.svg`; style block canonical,
unextended.

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 320" width="880" font-family="ui-sans-serif, -apple-system, 'Helvetica Neue', sans-serif" font-size="13">
  <style>
    @media (prefers-color-scheme: dark) {
      svg { fill: #e5e7eb; }
      [fill="#ffffff"] { fill: #111827; }
      [fill="#f9fafb"] { fill: #1f2937; }
      [fill="#eff6ff"] { fill: #172554; }
      [fill="#ecfdf5"] { fill: #022c22; }
      [fill="#fff7ed"] { fill: #431407; }
      [fill="#d1d5db"] { fill: #4b5563; }
      [fill="#1f2937"] { fill: #e5e7eb; }
      [fill="#6b7280"] { fill: #9ca3af; }
      [fill="#2563eb"] { fill: #60a5fa; }
      [fill="#1e40af"] { fill: #93c5fd; }
      [fill="#ea580c"] { fill: #fb923c; }
      [fill="#9a3412"] { fill: #fdba74; }
      [fill="#059669"] { fill: #34d399; }
      [fill="#065f46"] { fill: #6ee7b7; }
      [stroke="#6b7280"] { stroke: #9ca3af; }
      [stroke="#d1d5db"] { stroke: #4b5563; }
      [stroke="#e5e7eb"] { stroke: #374151; }
      [stroke="#2563eb"] { stroke: #60a5fa; }
      [stroke="#ea580c"] { stroke: #fb923c; }
      [stroke="#059669"] { stroke: #34d399; }
    }
  </style>
  <defs>
    <marker id="fg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#6b7280"/></marker>
    <marker id="fo" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#ea580c"/></marker>
  </defs>
  <rect width="880" height="320" fill="#ffffff"/>

  <text x="40" y="34" fill="#1f2937" font-weight="700">A's fact crosses as one vector; B answers without ever seeing A's text</text>

  <!-- lane A (sender). boxes h=36 at y=90, connector gaps 44, text baseline = y + h/2 + 4 -->
  <text x="24" y="112" fill="#2563eb" font-weight="700" font-size="15">A</text>
  <rect x="44" y="90" width="180" height="36" rx="8" fill="#eff6ff" stroke="#2563eb"/>
  <text x="134" y="112" text-anchor="middle" fill="#1f2937" font-family="ui-monospace, Menlo, monospace" font-size="12">"Tom is in Berlin."</text>

  <line x1="224" y1="108" x2="268" y2="108" stroke="#6b7280" stroke-width="1.5" marker-end="url(#fg)"/>

  <rect x="270" y="90" width="110" height="36" rx="8" fill="#f9fafb" stroke="#6b7280"/>
  <text x="325" y="112" text-anchor="middle" fill="#1f2937">blocks 1..k</text>

  <line x1="380" y1="108" x2="424" y2="108" stroke="#6b7280" stroke-width="1.5" marker-end="url(#fg)"/>

  <!-- the tap is a dot ON the wire, not a break in it; payload is a pill (rx = h/2) -->
  <circle cx="426" cy="108" r="4" fill="#ea580c"/>
  <rect x="432" y="90" width="150" height="36" rx="18" fill="#fff7ed" stroke="#ea580c" stroke-width="1.5"/>
  <text x="507" y="112" text-anchor="middle" fill="#9a3412" font-weight="600">one 768-dim vector</text>
  <!-- gray-500, NOT #9ca3af: #9ca3af is the dark-mode OUTPUT of this rule -->
  <text x="596" y="112" fill="#6b7280" font-size="12">(never decoded)</text>

  <line x1="507" y1="126" x2="507" y2="196" stroke="#ea580c" stroke-width="1.5" marker-end="url(#fo)"/>
  <text x="519" y="166" fill="#ea580c" font-size="12">spliced mid-forward</text>

  <!-- lane B (receiver): same box metrics one lane down, lane pitch 126 -->
  <text x="24" y="238" fill="#059669" font-weight="700" font-size="15">B</text>
  <rect x="44" y="216" width="180" height="36" rx="8" fill="#ecfdf5" stroke="#059669"/>
  <text x="134" y="238" text-anchor="middle" fill="#1f2937" font-family="ui-monospace, Menlo, monospace" font-size="12">"Q: Where is Tom? A:"</text>

  <line x1="224" y1="234" x2="268" y2="234" stroke="#6b7280" stroke-width="1.5" marker-end="url(#fg)"/>

  <rect x="270" y="216" width="110" height="36" rx="8" fill="#f9fafb" stroke="#6b7280"/>
  <text x="325" y="238" text-anchor="middle" fill="#1f2937">blocks 1..j</text>

  <line x1="380" y1="234" x2="424" y2="234" stroke="#6b7280" stroke-width="1.5" marker-end="url(#fg)"/>

  <!-- dashed = replaced, not added -->
  <rect x="432" y="216" width="150" height="36" rx="8" fill="#fff7ed" stroke="#ea580c" stroke-width="1.5" stroke-dasharray="5 3"/>
  <text x="507" y="239" text-anchor="middle" fill="#9a3412" font-size="12">overwrite last position</text>

  <line x1="582" y1="234" x2="626" y2="234" stroke="#6b7280" stroke-width="1.5" marker-end="url(#fg)"/>

  <rect x="628" y="216" width="118" height="36" rx="8" fill="#f9fafb" stroke="#6b7280"/>
  <text x="687" y="238" text-anchor="middle" fill="#1f2937">blocks j+1..12</text>

  <line x1="746" y1="234" x2="782" y2="234" stroke="#6b7280" stroke-width="1.5" marker-end="url(#fg)"/>
  <text x="790" y="239" fill="#065f46" font-family="ui-monospace, Menlo, monospace" font-weight="700" font-size="13">" Berlin."</text>

  <!-- underbrace: open path, label centred beneath -->
  <path d="M 270 262 v 8 h 312 v -8" fill="none" stroke="#059669" stroke-width="1.5"/>
  <text x="426" y="288" text-anchor="middle" fill="#059669" font-size="12">one ordinary forward pass, one position changed</text>

  <!-- footer: the negative claim the drawing cannot make -->
  <text x="40" y="308" fill="#6b7280" font-size="12">Nothing is added to B's stack and nothing is removed: one slot of one vector is different.</text>
</svg>
```

Metrics to keep: box height 36, `rx=8` for a box and `rx = h/2` for a payload pill, 44 px connector gaps,
lane pitch 126, agent badge at `font-size=15 font-weight=700` in the lane's hue, footer at `y = H − 12`
in `#6b7280` at 12 px.

## Skeleton B: grid / matrix, 880 × 320

Distilled from `n-grid-axes.svg`, `n-transfer.svg`, `v2-kv-channel.svg`. Its style block carries two
rules the canonical one lacks, which is the lesson: the captured cell is outlined `stroke="#9a3412"` and
the canonical block maps `#9a3412` as a **fill** only. Left unmapped, the single mark carrying the whole
argument renders as a near-black outline on `#111827`: invisible, in one of the two modes you ship.

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 320" width="880" font-family="ui-sans-serif, -apple-system, 'Helvetica Neue', sans-serif" font-size="13">
  <style>
    @media (prefers-color-scheme: dark) {
      svg { fill: #e5e7eb; }
      [fill="#ffffff"] { fill: #111827; }
      [fill="#f9fafb"] { fill: #1f2937; }
      [fill="#eff6ff"] { fill: #172554; }
      [fill="#ecfdf5"] { fill: #022c22; }
      [fill="#fff7ed"] { fill: #431407; }
      [fill="#fed7aa"] { fill: #7c2d12; }
      [fill="#d1d5db"] { fill: #4b5563; }
      [fill="#1f2937"] { fill: #e5e7eb; }
      [fill="#6b7280"] { fill: #9ca3af; }
      [fill="#2563eb"] { fill: #60a5fa; }
      [fill="#1e40af"] { fill: #93c5fd; }
      [fill="#ea580c"] { fill: #fb923c; }
      [fill="#9a3412"] { fill: #fdba74; }
      [fill="#059669"] { fill: #34d399; }
      [fill="#065f46"] { fill: #6ee7b7; }
      [stroke="#6b7280"] { stroke: #9ca3af; }
      [stroke="#d1d5db"] { stroke: #4b5563; }
      [stroke="#e5e7eb"] { stroke: #374151; }
      [stroke="#2563eb"] { stroke: #60a5fa; }
      [stroke="#ea580c"] { stroke: #fb923c; }
      [stroke="#059669"] { stroke: #34d399; }
      [stroke="#9a3412"] { stroke: #fdba74; }
    }
  </style>
  <defs>
    <marker id="gg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#6b7280"/></marker>
    <marker id="go" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#ea580c"/></marker>
  </defs>
  <rect width="880" height="320" fill="#ffffff"/>

  <text x="40" y="30" fill="#1f2937" font-weight="600">one cell per (token, depth): the grid every activation figure sits on</text>

  <!-- cells 34x18 rx=3, pitch 38 x 22, origin (140, 172), depth increases UPWARD.
       9 columns x 7 rows = 63 cells. One stroke declaration hoisted to the <g>. -->
  <g stroke="#e5e7eb">
    <rect x="140" y="172" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="178" y="172" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="216" y="172" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="254" y="172" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="292" y="172" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="330" y="172" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="368" y="172" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="406" y="172" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="444" y="172" width="34" height="18" rx="3" fill="#eff6ff"/>
    <rect x="140" y="150" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="178" y="150" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="216" y="150" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="254" y="150" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="292" y="150" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="330" y="150" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="368" y="150" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="406" y="150" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="444" y="150" width="34" height="18" rx="3" fill="#eff6ff"/>
    <rect x="140" y="128" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="178" y="128" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="216" y="128" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="254" y="128" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="292" y="128" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="330" y="128" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="368" y="128" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="406" y="128" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="444" y="128" width="34" height="18" rx="3" fill="#eff6ff"/>
    <rect x="140" y="106" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="178" y="106" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="216" y="106" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="254" y="106" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="292" y="106" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="330" y="106" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="368" y="106" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="406" y="106" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="444" y="106" width="34" height="18" rx="3" fill="#eff6ff"/>
    <rect x="140" y="84" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="178" y="84" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="216" y="84" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="254" y="84" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="292" y="84" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="330" y="84" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="368" y="84" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="444" y="84" width="34" height="18" rx="3" fill="#eff6ff"/>
    <rect x="140" y="62" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="178" y="62" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="216" y="62" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="254" y="62" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="292" y="62" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="330" y="62" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="368" y="62" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="406" y="62" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="444" y="62" width="34" height="18" rx="3" fill="#eff6ff"/>
    <rect x="140" y="40" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="178" y="40" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="216" y="40" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="254" y="40" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="292" y="40" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="330" y="40" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="368" y="40" width="34" height="18" rx="3" fill="#eff6ff"/><rect x="444" y="40" width="34" height="18" rx="3" fill="#eff6ff"/>
  </g>

  <!-- the two cells that carry the argument. solid = captured, dashed = written into.
       Drawn after the <g> so they paint over it and keep their own stroke. -->
  <rect x="406" y="84" width="34" height="18" rx="3" fill="#ea580c" stroke="#9a3412"/>
  <rect x="406" y="40" width="34" height="18" rx="3" fill="#fff7ed" stroke="#ea580c" stroke-dasharray="3 2"/>

  <!-- y axis: ticks right-aligned 8px off the grid, arrow outside the ticks -->
  <g fill="#6b7280" font-size="9.5" text-anchor="end">
    <text x="132" y="185">0</text><text x="132" y="163">1</text><text x="132" y="141">2</text>
    <text x="132" y="119">3</text><text x="132" y="97">4</text><text x="132" y="75">5</text>
    <text x="132" y="53">6</text>
  </g>
  <line x1="104" y1="190" x2="104" y2="34" stroke="#6b7280" stroke-width="1.5" marker-end="url(#gg)"/>
  <text x="92" y="112" text-anchor="middle" fill="#1f2937" font-size="12" transform="rotate(-90, 92, 112)">depth: blocks run</text>

  <!-- x axis: token labels rotated -40 about their OWN anchor; text-anchor=end pins the right edge -->
  <g fill="#1f2937" font-family="ui-monospace, Menlo, monospace" font-size="10">
    <text x="160" y="210" text-anchor="end" transform="rotate(-40, 160, 210)">Q</text>
    <text x="198" y="210" text-anchor="end" transform="rotate(-40, 198, 210)">:</text>
    <text x="236" y="210" text-anchor="end" transform="rotate(-40, 236, 210)">Where</text>
    <text x="274" y="210" text-anchor="end" transform="rotate(-40, 274, 210)">is</text>
    <text x="312" y="210" text-anchor="end" transform="rotate(-40, 312, 210)">Tom</text>
    <text x="350" y="210" text-anchor="end" transform="rotate(-40, 350, 210)">?</text>
    <text x="388" y="210" text-anchor="end" transform="rotate(-40, 388, 210)">A</text>
    <text x="426" y="210" text-anchor="end" transform="rotate(-40, 426, 210)">:</text>
    <text x="464" y="210" text-anchor="end" transform="rotate(-40, 464, 210)">Tom</text>
  </g>
  <line x1="140" y1="234" x2="490" y2="234" stroke="#6b7280" stroke-width="1.5" marker-end="url(#gg)"/>
  <text x="310" y="252" text-anchor="middle" fill="#1f2937" font-size="12">which token</text>

  <!-- callout: leader out to empty space, then a tinted box. never a balloon over the art -->
  <line x1="482" y1="93" x2="530" y2="93" stroke="#ea580c" stroke-width="1.5" marker-end="url(#go)"/>
  <rect x="534" y="60" width="306" height="66" rx="8" fill="#fff7ed" stroke="#ea580c" stroke-width="1.5"/>
  <text x="548" y="82" fill="#9a3412" font-size="12" font-weight="600">one cell = one vector of 768 numbers</text>
  <text x="548" y="100" fill="#9a3412" font-size="12">not a word: this column's running guess at</text>
  <text x="548" y="118" fill="#9a3412" font-size="12">the next token, sharpening as you go up</text>

  <text x="534" y="152" fill="#6b7280" font-size="12">solid: the cell that is captured</text>
  <text x="534" y="170" fill="#6b7280" font-size="12">dashed: the cell it is written into</text>

  <text x="40" y="302" fill="#6b7280" font-size="12">The grid is 9 tokens x 7 depths. A splice replaces exactly one of these 63 cells; every other cell is untouched.</text>
</svg>
```

Metrics to keep: cell `34 × 18 rx=3` with the stroke hoisted to the wrapping `<g>`, pitch `38 × 22`, tick
labels 9.5 px right-aligned 8 px off the grid, axis arrows outside the ticks, callout leader horizontal
into an `rx=8` box in the callout's hue. The `#fed7aa` rule rides along although this figure has no cache
cells: extending is free, subsetting is how the next edit breaks.

## Checking a new SVG renders

`rsvg-convert` ignores `@media`, which turns into the dark check rather than a problem (the source repo
states this as a project rule at `CLAUDE.md:112-129`):

```bash
# light
rsvg-convert -o fig.png fig.svg

# dark: strip the @media wrapper on a COPY, keeping the rules inside it
mkdir -p .local
python3 - fig.svg > .local/fig-dark.svg <<'PY'
import sys
s = open(sys.argv[1]).read()
i = s.index('@media')
j = s.index('{', i)             # opening brace of the @media block
d, k = 1, j + 1
while d:                         # walk to the matching close
    d += (s[k] == '{') - (s[k] == '}')
    k += 1
sys.stdout.write(s[:i] + s[j+1:k-1] + s[k:])
PY
rsvg-convert -o fig-dark.png .local/fig-dark.svg
```

Brace-counting beats the `sed`-then-`perl` recipe that circulates for this: `sed` deletes the `@media`
line and leaves an orphaned `}`, so a second substitution has to absorb it, which breaks the moment you
extend the block and move the brace. Then look at both PNGs; only the render shows text overflowing its
box, a rotated label colliding with a tick, an arrowhead inside a rect, or a dashed cell whose dash
phase reads as solid at 1x.

**Lint before committing:**

```bash
python3 skills/research-viz/scripts/svg_theme_lint.py doc/img/*.svg
```

It reports every `fill=`/`stroke=` value missing from that file's own dark block and exits 1 on any
failure, so it drops into a pre-commit hook. **Both skeletons above were extracted from this file, run
through it (`ok`, exit 0), and rendered light and dark before it shipped**, because the earlier version
of this material shipped two "copy me" skeletons that each failed that linter. Against the source corpus
it reports 7 of 44 files failing: six with an authored `#9ca3af`, one with an unmapped
`stroke="#9a3412"`. A hand-authored corpus cannot hold this invariant by attention.
