# Diagram Reference

## Two Rules That Cause Most Failures

1. **Arrow intersection check**: before writing any `<line>` or `<path>`, trace its coordinates against every box. If the line crosses any rect's interior, use an L-shaped `<path>` detour: `<path d="M x1 y1 L x1 ymid L x2 ymid L x2 y2"/>`.

2. **Box width from longest label**: `rect_width = max(title_chars * 8, subtitle_chars * 7) + 24`. A 100px-wide box holds at most a 10-char subtitle. If your subtitle is "Files, APIs, streams" (20 chars), the box needs 164px minimum.

## SVG Setup

Standard boilerplate for diagram SVGs:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 WIDTH HEIGHT"
     font-family="system-ui,-apple-system,sans-serif" font-size="14">
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="var(--color-text-secondary,#888)"/>
  </marker>
</defs>
<style>
  .arr{stroke:var(--color-text-secondary,#888);stroke-width:1.2;fill:none}
  .box rect{fill:var(--color-background-secondary,#f5f5f5);stroke:var(--color-border-tertiary,#ddd);stroke-width:0.5;rx:8}
  .node{cursor:pointer}
  .node:hover rect,.node:hover circle{filter:brightness(0.95)}
  .th{font-weight:500;font-size:14px;fill:var(--color-text-primary,#1a1a1a)}
  .ts{font-size:12px;fill:var(--color-text-secondary,#666)}
  /* Color ramp classes - light mode fills, auto dark mode text */
  .c-blue rect,.c-blue circle{fill:#E6F1FB;stroke:#185FA5;stroke-width:0.5}
  .c-blue .th{fill:#0C447C} .c-blue .ts{fill:#185FA5}
  .c-teal rect,.c-teal circle{fill:#E1F5EE;stroke:#0F6E56;stroke-width:0.5}
  .c-teal .th{fill:#085041} .c-teal .ts{fill:#0F6E56}
  .c-purple rect,.c-purple circle{fill:#EEEDFE;stroke:#534AB7;stroke-width:0.5}
  .c-purple .th{fill:#3C3489} .c-purple .ts{fill:#534AB7}
  .c-coral rect,.c-coral circle{fill:#FAECE7;stroke:#993C1D;stroke-width:0.5}
  .c-coral .th{fill:#712B13} .c-coral .ts{fill:#993C1D}
  .c-gray rect,.c-gray circle{fill:#F1EFE8;stroke:#5F5E5A;stroke-width:0.5}
  .c-gray .th{fill:#444441} .c-gray .ts{fill:#5F5E5A}
  .c-amber rect,.c-amber circle{fill:#FAEEDA;stroke:#854F0B;stroke-width:0.5}
  .c-amber .th{fill:#633806} .c-amber .ts{fill:#854F0B}
  .c-red rect,.c-red circle{fill:#FCEBEB;stroke:#A32D2D;stroke-width:0.5}
  .c-red .th{fill:#791F1F} .c-red .ts{fill:#A32D2D}
  .c-green rect,.c-green circle{fill:#EAF3DE;stroke:#3B6D11;stroke-width:0.5}
  .c-green .th{fill:#27500A} .c-green .ts{fill:#3B6D11}
  .c-pink rect,.c-pink circle{fill:#FBEAF0;stroke:#993556;stroke-width:0.5}
  .c-pink .th{fill:#72243E} .c-pink .ts{fill:#993556}
</style>
```

## Diagram Types

### Flowchart

For sequential processes, cause-and-effect, decision trees.

**Spacing**: 60px minimum between boxes, 24px padding inside boxes, 12px between text and edges. 10px gap between arrowheads and box edges.

**Node heights**: Single-line = 44px. Two-line (title + subtitle) = 56px with 22px between lines. Keep all same-type nodes the same height.

**Vertical text placement**: Every `<text>` inside a box needs `dominant-baseline="central"` with y at the center of its slot. Formula: `<text x={x+w/2} y={y+h/2} text-anchor="middle" dominant-baseline="central">`.

**Layout**: Prefer single-direction flows (top-down or left-right). Max 4-5 nodes per diagram. ~680px safe width.

**Tier packing**: Compute total width BEFORE placing. Example - 4 boxes:
- WRONG: x=40,160,260,360 w=160 -> overlaps (4x160=640 > available)
- RIGHT: x=50,200,350,500 w=130 gap=20 -> fits (4x130 + 3x20 = 580)

**Special characters are wider**: Chemical formulas, math notation, Unicode symbols. Add 30-50% extra width.

**When over budget (6+ components)**: Don't cram into one diagram. Make a stripped overview (boxes only, 1-2 main arrows), then one diagram per interesting sub-flow (3-4 nodes each).

**Single-line node** (44px):
```svg
<g class="node c-blue">
  <rect x="100" y="20" width="180" height="44" rx="8" stroke-width="0.5"/>
  <text class="th" x="190" y="42" text-anchor="middle" dominant-baseline="central">T-cells</text>
</g>
```

**Two-line node** (56px):
```svg
<g class="node c-blue">
  <rect x="100" y="20" width="200" height="56" rx="8" stroke-width="0.5"/>
  <text class="th" x="200" y="38" text-anchor="middle" dominant-baseline="central">Dendritic cells</text>
  <text class="ts" x="200" y="56" text-anchor="middle" dominant-baseline="central">Detect foreign antigens</text>
</g>
```

**Connector**:
```svg
<line x1="200" y1="76" x2="200" y2="120" class="arr" marker-end="url(#arrow)"/>
```

**Arrows**: Must not cross any box or label. If direct path crosses something, route around with L-bend.

**Feedback loops**: Don't draw physical arrows traversing the layout. Use `<text>↻ returns to start</text>` near the cycle point instead.

### Structural Diagram

For containment: things inside other things (VPC/subnet/instance, cell organelles, file system blocks).

Large rounded rects are containers. Smaller rects inside are regions. Text labels describe what happens in each region. Arrows show flow between regions.

### Illustrative Diagram

For building intuition with visual metaphors. The goal isn't a correct map - it's the right mental model.

- Physical things get cross-sections (engines, lungs, water heaters)
- Abstract things get spatial metaphors: LLM = stack of layers with attention threads, gradient descent = ball on loss surface, hash table = row of buckets
- Fill the canvas - illustrative diagrams should feel rich
- Bold colors, layer overlapping shapes for depth
- Organic forms with `<path>` curves, `<ellipse>`, `<circle>`

### Cycles

Never draw as rings. The ring layout causes collisions between satellite boxes, labels on the circle, and tangential arrows.

Instead: build an HTML stepper (one panel per stage, dots showing position, Next wraps from last to first). Or a linear SVG with a curved return arrow.

## Multiple Diagrams

- Break complex explanations into a series of smaller diagrams
- Always add prose between diagrams - never stack tool calls back-to-back
- If your text promises N diagrams, deliver all N
