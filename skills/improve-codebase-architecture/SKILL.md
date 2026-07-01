---
name: improve-codebase-architecture
description: "Survey a codebase for deepening opportunities (shallow modules that should collapse into deep ones), present the candidates as a self-contained HTML report with before/after visualisations and Strong / Worth-exploring / Speculative badges, then map the design of whichever one the user picks. Grounded in the /codebase-design architecture vocabulary (module, interface, depth, seam, adapter, leverage, locality) and the project's domain language in CONTEXT.md. Manual: invoke when the user wants an architecture review, asks where a codebase is shallow or hard to test, or wants deepening candidates ranked before refactoring."
disable-model-invocation: true
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities**: refactors that turn shallow modules into deep ones. The aim is testability and AI-navigability.

```
Goal: Hand the user a ranked set of deepening candidates as a visual HTML report,
      then walk the chosen candidate into a concrete design while keeping the
      domain model current.

Success means:
  - HTML report written to the OS temp dir (never the repo), opened, absolute path returned
  - Each candidate carries Files / Problem / Solution / Benefits / before-after diagram / strength badge
  - Every suggestion uses the /codebase-design vocabulary exactly and the CONTEXT.md domain nouns
  - The user picks a candidate and /decision-mapping walks its design tree to resolution
  - CONTEXT.md and ADRs reflect any naming or decisions that crystallized during the walk

Stop when: the chosen candidate's design tree is resolved or deferred-with-criteria,
           and the domain model reflects what the conversation changed.
```

This command is _informed_ by the project's domain model and built on a shared design vocabulary. Read both before surveying:

- Run `/codebase-design` for the architecture vocabulary (**module**, **interface**, **depth**, **seam**, **adapter**, **leverage**, **locality**) and its principles (the deletion test; "the interface is the test surface"; "one adapter = hypothetical seam, two = real"). Use these terms exactly in every suggestion; stay out of "component", "service", "API", and "boundary".
- The domain language in `CONTEXT.md` gives names to good seams; ADRs in `docs/adr/` record decisions this command leaves alone.

## Process

### 1. Survey

Read the project's domain glossary (`CONTEXT.md`) and any ADRs in the area you are touching first.

Then dispatch a read-only survey with the Agent tool, `subagent_type=Explore`, to walk the codebase. (Explore is the sanctioned read-only code-search subagent; it burns no generation quota.) Explore organically and note where you feel friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow**: interface nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, while the real bugs hide in how they are called (no **locality**)?
- Where do tightly-coupled modules leak across their seams?
- Which parts are untested, or hard to test through their current interface?

Apply the **deletion test** to anything you suspect is shallow: would deleting it concentrate complexity, or just move it around? A "yes, concentrates" is the signal you want.

### 2. Present candidates as an HTML report

Write a self-contained HTML file to the OS temp directory so nothing lands in the repo. Resolve the temp dir from `$TMPDIR`, falling back to `/tmp`, and write to `<tmpdir>/architecture-review-<timestamp>.html` so each run gets a fresh file. Open it for the user with the platform's open command (`xdg-open <path>` on Linux, `open <path>` on macOS) and report the absolute path. Design candidates land as an HTML explorer the user can see in context, not as a wall of prose.

The report pulls **Tailwind via CDN** for layout and **Mermaid via CDN** for graph-shaped diagrams. Mix Mermaid with hand-built CSS/SVG: use Mermaid when relationships are graph-shaped (call graphs, dependencies, sequences), and hand-drawn divs/SVG for editorial visuals (mass diagrams, cross-sections, collapse animations). Each candidate gets a **before/after visualisation**. Be visual.

For each candidate, render a card with:

- **Files**: which files/modules are involved
- **Problem**: why the current architecture causes friction (one sentence)
- **Solution**: plain-English description of what changes (one sentence)
- **Benefits**: stated in terms of locality and leverage, and how tests improve
- **Before / After diagram**: side by side, custom-drawn, illustrating the shallowness and the deepening
- **Recommendation strength**: one of `Strong`, `Worth exploring`, `Speculative`, rendered as a badge

End the report with a **Top recommendation** section: which candidate you would tackle first and why.

**Use CONTEXT.md vocabulary for the domain, /codebase-design vocabulary for the architecture.** If `CONTEXT.md` defines "Order", write "the Order intake module", not "the FooBarHandler" and not "the Order service".

**ADR conflicts**: when a candidate contradicts an existing ADR, surface it only when the friction is real enough to warrant reopening the ADR. Mark it clearly in the card (an amber warning callout: _"contradicts ADR-0007, worth reopening because…"_). Skip the theoretical refactors an ADR merely forbids.

Hold the interface design back at this stage. After the file is written, ask the user: "Which of these would you like to explore?"

The HTML scaffold, diagram patterns, and styling guidance live inline below under **HTML report template**.

### 3. Design-walk loop

Once the user picks a candidate, run `/decision-mapping` to walk the design tree with them: constraints, dependencies, the shape of the deepened module, what sits behind the seam, which tests survive.

Side effects happen inline as decisions crystallize; run `/domain-modeling` to keep the domain model current as you go:

- **Naming a deepened module after a concept absent from `CONTEXT.md`?** Add the term to `CONTEXT.md`. Create the file lazily when it does not exist.
- **Sharpening a fuzzy term mid-conversation?** Update `CONTEXT.md` right there.
- **User rejects the candidate with a load-bearing reason?** Offer an ADR: _"Want me to record this as an ADR so future reviews stop re-suggesting it?"_ Offer only when the reason would genuinely help a future explorer avoid re-suggesting the same thing; skip ephemeral reasons ("not worth it right now") and self-evident ones.
- **Want to explore alternative interfaces for the deepened module?** Run `/codebase-design` and use its design-it-twice parallel sub-agent pattern.

## HTML report template

<details>
<summary>HTML report template</summary>

Render the review as one self-contained HTML file in the OS temp directory. Tailwind and Mermaid both come from CDNs. Mermaid handles graph-shaped diagrams reliably; hand-built divs and inline SVG handle the editorial visuals (mass diagrams, cross-sections). Mix the two; leaning on Mermaid for everything reads generic.

### Scaffold

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Architecture review: {{repo name}}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    </script>
    <style>
      /* small custom layer for what Tailwind doesn't cover cleanly:
         dashed seam lines, hand-drawn arrow heads, deep-module fill */
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: linear-gradient(135deg, #0f172a, #1e293b); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="candidates" class="space-y-10">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

### Header

Repo name, date, and a compact legend: solid box = module, dashed line = seam, red arrow = leakage, thick dark box = deep module. Skip the intro paragraph; go straight into the candidates.

### Candidate card

The diagrams carry the weight. Prose stays sparse and plain, using the glossary terms without ceremony. Each candidate is one `<article>`:

- **Title**: short, names the deepening (e.g. "Collapse the Order intake pipeline").
- **Badge row**: recommendation strength (`Strong` = emerald, `Worth exploring` = amber, `Speculative` = slate), plus a tag for the dependency category (`in-process`, `local-substitutable`, `ports & adapters`, `mock`).
- **Files**: monospaced list, `font-mono text-sm`.
- **Before / After diagram**: the centrepiece. Two columns, side by side. See patterns below.
- **Problem**: one sentence. What hurts.
- **Solution**: one sentence. What changes.
- **Wins**: bullets, six words or fewer each, e.g. "Tests hit one interface", "Pricing logic stops leaking", "Delete 4 shallow wrappers".
- **ADR callout** (when applicable): one line in an amber-tinted box.

When a diagram needs a paragraph to be understood, redraw the diagram.

### Diagram patterns

Pick the pattern that fits the candidate and mix them; uniform diagrams defeat the point.

- **Mermaid graph** (the workhorse for dependencies / call flow): use a `flowchart` or `graph` when the point is "X calls Y calls Z, look at the mess". Wrap it in a Tailwind card. Use `classDef` to colour leakage edges red and the deep module dark. Sequence diagrams suit "before: 6 round-trips; after: 1".

  ```html
  <div class="rounded-lg border border-slate-200 bg-white p-4">
    <pre class="mermaid">
      flowchart LR
        A[OrderHandler] --> B[OrderValidator]
        B --> C[OrderRepo]
        C -.leak.-> D[PricingClient]
        classDef leak stroke:#dc2626,stroke-width:2px;
        class C,D leak
    </pre>
  </div>
  ```

- **Hand-built boxes-and-arrows** (when Mermaid's layout fights you): modules as bordered `<div>`s, arrows as inline SVG `<line>`/`<path>` positioned over a relative container. Reach for this when the "after" should feel like one thick-bordered deep module with greyed-out internals.
- **Cross-section** (layered shallowness): stack horizontal bands (`h-12 border-l-4`) for layers a call passes through. Before: 6 thin layers each doing nothing. After: 1 thick band naming the consolidated responsibility.
- **Mass diagram** ("interface as wide as implementation"): two rectangles per module, one for interface surface area, one for implementation. Before: interface nearly as tall as implementation (shallow). After: interface short, implementation tall (deep).
- **Call-graph collapse**: before, a tree of calls as nested boxes; after, the same tree collapsed into one box with the now-internal calls faded inside it.

### Style guidance

- Lean editorial, not corporate-dashboard. Generous whitespace; `font-serif` headings pair well with stone/slate.
- Colour sparingly: one accent (emerald or indigo) plus red for leakage and amber for warnings.
- Keep diagrams around 320px tall so before/after sits side by side without scrolling.
- Use `text-xs uppercase tracking-wider` for in-diagram module labels; they should read schematic, not as UI.
- The only scripts are the Tailwind CDN and the Mermaid ESM import; the report is otherwise static.

### Top recommendation section

One larger card: candidate name, one sentence on why, anchor link to its card. That is it.

### Tone and vocabulary

Plain English, concise; the architectural nouns and verbs come straight from `/codebase-design`. Concision is no excuse to drift.

**Use exactly:** module, interface, implementation, depth, deep, shallow, seam, adapter, leverage, locality.

**Avoid the substitutions:** component, service, unit (for module); API, signature (for interface); boundary (for seam); layer, wrapper (for module, when you mean module).

**Phrasings that fit:**

- "Order intake module is shallow; interface nearly matches the implementation."
- "Pricing leaks across the seam."
- "Deepen: one interface, one place to test."
- "Two adapters justify the seam: HTTP in prod, in-memory in tests."

**Wins bullets** name the gain in glossary terms: _"locality: bugs concentrate in one module"_, _"leverage: one interface, N call sites"_, _"interface shrinks; implementation absorbs the wrappers"_. Skip "easier to maintain" and "cleaner code"; those are not in the glossary and do not earn their place.

No hedging, no throat-clearing, no "it's worth noting that…". When a sentence could be a bullet, make it a bullet. When a bullet could be cut, cut it. When a term is missing from the `/codebase-design` glossary, reach for one that is there before inventing a new one.

</details>
