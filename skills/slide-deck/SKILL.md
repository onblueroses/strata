---
name: slide-deck
description: "Build pitch decks and presentation slides as a single-file HTML (reveal.js via CDN, zero deps). Inherits frontend-design rules: banned fonts/colors, warm-neutral palettes, asymmetric whitespace, one-idea-per-slide; supports four structure templates (Standard / Demo-First / Contrast / Question-Driven). Triggers on: 'slide deck', 'pitch deck', 'presentation', 'slides for', 'hackathon pitch', 'demo deck', 'investor deck', 'build a deck', 'reveal.js deck', 'fellowship pitch'. Also triggers when: user names a project and asks for slides/pitch/deck deliverable; user wants HTML slides (not Beamer/PDF); user references a hackathon or investor audience. Pairs with /latex-presentation (Beamer alternative for academic/print-grade decks — pick this when user wants PDF/print output), /visualize (charts and diagrams to embed in slides), /frontend-design (parent skill — banned fonts/colors and visual rules inherit from here), /humanizer (slop-check slide copy before showing). Manual: /slide-deck [topic or project name]."
---

# Slide Deck

Build single-file HTML presentations using reveal.js (CDN-loaded, zero dependencies).
Outputs one `.html` file that opens in any browser. Optimized for hackathon pitches
and short demo-centric decks but works for any presentation.

**Inherits from `frontend-design` skill.** All banned fonts, banned patterns, color
rules, and AI tells from that skill apply here. When in doubt, check frontend-design.

## Skip Conditions

- **Skip if** the user wants LaTeX/Beamer (use `latex-presentation` skill instead)
- **Skip if** editing a single slide's text content - just edit the HTML directly
- **Skip if** the user already has a reveal.js deck and just wants content changes

---

## Phase 0: Context Gathering

Before writing any slides, interview the user. If project files exist (STRATEGY.md,
README.md, kb/, CONTINGENCIES.md), read them first and pre-fill what you can, then
confirm with the user.

### Questionnaire

Ask these via AskUserQuestion (batch into 2-3 calls max):

**Content questions:**
1. What's the one sentence that captures what you're building?
2. Who is the audience? (judges, investors, users, peers)
3. What's the problem you're solving - in the audience's language?
4. Do you have a live demo? If yes, what does it show? If no, what's the visual?
5. What's the "how it works" summary - 3 bullet points max?
6. What's the ask or next step? (vote for us, try the beta, fund us, hire us)

**Structure questions:**
7. Present the 4 structure options (A-D) via AskUserQuestion with previews.
   Include a one-line pitch for each. Recommend B or C for hackathons, D for fellowships.
8. How many slides? (default depends on chosen structure)

**Style questions:**
9. Any existing brand colors or visual identity to match?
10. Tone: cinematic/atmospheric, clean/minimal, warm/approachable, bold/startup?

Pre-fill answers from project files when possible. Show the user what you found and
let them correct before proceeding.

---

## Phase 1: Design System

<details>
<summary>Design System</summary>

### Foundational Rules (from frontend-design)

These are non-negotiable. Violating any of them produces a generic-looking deck.

**Banned fonts:** Inter, Roboto, Arial, Helvetica, system-ui, Open Sans, Lato,
Montserrat, Poppins, Space Grotesk. These are AI defaults and look like it.

**Approved headline fonts** (rotate, don't always pick the same one):

| Font | Vibe | Source |
|------|------|--------|
| Syne | Geometric, modern | Google Fonts |
| Clash Display | Bold, contemporary | Fontshare |
| Satoshi | Clean, premium | Fontshare |
| Cabinet Grotesk | Clean, premium | Fontshare |
| Fraunces | Organic, soft serif | Google Fonts |
| Instrument Serif | Elegant, editorial | Google Fonts |
| Bricolage Grotesque | Quirky, characterful | Google Fonts |

**Approved body fonts:** Satoshi, Outfit, General Sans, Source Serif 4, Switzer, Literata.

For Fontshare fonts, use the CDN: `https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&display=swap`

**Banned patterns (AI tells):**
- Dark mode + glowing accents (the single most overused "premium" look in AI output)
- Monospace typography as shorthand for "technical vibes"
- Gradient text (`background-clip: text`)
- Purple/blue neon gradients
- Pure black (#000) or pure white (#fff) - always tint
- 3-column card layouts
- Generic names, fake round numbers
- Emoji section headers

**Banned hex colors** (machine-checkable - grep output for these):
`#8b5cf6`, `#7c3aed`, `#d946ef`, `#6366f1`, `#818cf8` (Tailwind violet/indigo/fuchsia
defaults - if any appear, the deck looks AI-generated)

**Font rotation:** Never reuse the same headline+body pairing from a previous generation
in the same session. Rotate through approved pairings. If the user has no preference,
pick the pairing you've used least recently.

**Color rules:**
- Max 1 accent color. Saturation < 80%.
- No pure black or white. Tint neutrals: warm or cool, but not zero-chroma gray.
- If dark theme: the background must be warm (tinted toward brown/navy), not #000/#111.
- If light theme: use warm off-whites (#FAF8F4, #F5F0EB), not sterile #FFFFFF.

### Theme: Warm Light (default)

Light background, warm neutrals, one accent. Approachable, premium, not generic.

```css
:root {
  /* Backgrounds - warm cream, NOT white-adjacent, NOT sandy.
     #FAF8F4 reads as white. #E8DCC9 reads as sand. Sweet spot is cream. */
  --bg-primary: #F2EBE0;         /* warm cream - visibly warm but not sandy */
  --bg-surface: #EAE3D7;         /* slightly darker cream */
  --bg-highlight: #E2DBCE;       /* callout/card bg */

  /* Text */
  --text-primary: #1A1714;       /* warm near-black (never #000) */
  --text-secondary: #6B6560;     /* warm gray */
  --text-tertiary: #9C958E;      /* light label text */

  /* Accent - pick ONE per deck, adapt to brand */
  --accent: #2E5090;             /* deep blue (default) */
  --accent-soft: rgba(46,80,144,0.08); /* accent at low opacity for backgrounds */

  /* Utility */
  --border: #DDD7CE;
  --grain-opacity: 0.025;
}
```

**Alternative accent colors** (pick based on brand/mood):
- `#1D7A4B` - forest green (growth, nature)
- `#A63D2F` - burnt sienna (warmth, energy)
- `#6B4C9A` - muted purple (creativity - use sparingly, avoid neon)
- `#0E7C7B` - dark teal (trust, depth)

### Theme: Warm Dark (use only when explicitly requested)

```css
:root {
  --bg-primary: #1C1917;         /* warm charcoal (stone-950 equivalent) */
  --bg-surface: #28231F;         /* warm dark surface */
  --bg-highlight: #342E29;       /* card bg */

  --text-primary: #F0EDE8;       /* warm off-white */
  --text-secondary: #A8A29E;     /* stone-400 */
  --text-tertiary: #78716C;      /* stone-500 */

  --accent: #C5945A;             /* warm gold */
  --accent-soft: rgba(197,148,90,0.1);

  --border: #3D3835;
  --grain-opacity: 0.03;
}
```

When using dark theme: increase line-height by 0.05-0.1 vs light theme
(perceived weight is lower on dark backgrounds).

### Typography Scale

Presentations are projected. Everything must be readable from meters away.

**CRITICAL: reveal.js sizing.** Reveal.js scales everything inside an internal
viewport (1920x1080 by default). `rem` units reference this viewport's base font
size, NOT the browser's. Use `px` units for predictable sizing at any screen size.
The reveal.js viewport is 1920px wide - size elements proportionally to that.

| Element | Size | Weight | Font |
|---------|------|--------|------|
| Hook headline (slide 1) | 80-96px | 800 | Display font |
| Section headline | 56-64px | 700 | Display font |
| Body text | 32-36px | 400 | Body font |
| Eyebrow / labels | 18-20px | 500-600 | Body font |
| Stat numbers | 96-120px | 800 | Display font |
| Stat labels | 22-24px | 400 | Body font |
| Flow nodes | 22-24px | 400 | Body font |
| Code / data | 22px | 400 | JetBrains Mono (only in code contexts) |
| Closing metadata | 20px | 400 | Body font |

**Never below 18px.** If text is too small to read projected, it shouldn't be on the slide.

`letter-spacing: -0.03em` on headlines. `tracking-tight` equivalent.

`line-height`: 1.1 for headlines, 1.5 for body.

**Component sizing (relative to 1920x1080 viewport):**
- Flow nodes: `padding: 14px 24px`, `border-radius: 8px`
- Stats gap: `80-100px` between stat items
- Insight border-left: `3px solid`
- Demo frame: `width: 85%`, keeps 16:9 ratio
- Section padding: `100px 120px 100px 10%` (generous, asymmetric)

### Layout Rules

- **Left-aligned by default.** Centered text is only for hook slides and closing slides.
- **Asymmetric whitespace.** Don't center content on the slide. Offset with generous
  left padding (8-12% of slide width) and let right side breathe.
- **One idea per slide.** If you need two points, you need two slides.
- **Max 25 words per slide.** Aim for 12-15. The speaker fills the gaps.
- **No bullet lists** on the first 3 slides. Statements, not lists.
- **Generous vertical spacing.** Elements should feel like they're floating, not stacked.
- **16:9 aspect ratio** (`width: 1920, height: 1080` in reveal config).

### Grain Overlay

Subtle noise texture via SVG filter. Apply to `section::after` (not `::before` -
keep it behind content with low z-index). Opacity 0.02-0.03 on light themes,
0.03-0.04 on dark themes. More than that looks dirty.

</details>

---

## Phase 1.5: Content Inventory

Before choosing a structure or designing slides, enumerate every discrete content item
from the source material (project files, user answers, README, strategy docs). This
prevents the common failure mode of polished decks that silently drop 30-40% of content.

**Inventory checklist:**
- Count: sections, subsections, features, decisions, stats/numbers, comparisons, diagrams
- List each item by name (e.g., "3 architecture components, 2 benchmarks, 1 flow diagram, 4 decisions")
- Map each item to a slide or explicitly mark it as "cut" with a reason
- Show the user the inventory and cuts before proceeding to slide design

A source with 7 sections + 4 stats + 1 diagram = ~12 content items. If your deck only
covers 7, you need to either add slides or justify the cuts.

---

## Phase 2: Slide Architecture

<details>
<summary>Slide Architecture</summary>

### Structure A: Standard Pitch (5-7 slides)

The safe default. Works, but is what every other team does.

| # | Slide | Purpose | Max words | Layout |
|---|-------|---------|-----------|--------|
| 1 | **Hook** | Emotional entry. One sentence. | 12 | Centered, large type |
| 2 | **Problem** | The pain, in the audience's language. | 20 | Left-aligned + supporting line |
| 3 | **Demo** | "Let me show you." | 6 | Screenshot or [LIVE DEMO] marker |
| 4 | **How** | Architecture in 3 items max. | 20 | Flow diagram or labeled items |
| 5 | **Validation** | Why this isn't vaporware. | 15 | 2-3 large numbers |
| 6 | **Next** | Where this goes. 2 items max. | 12 | Two items, stacked |
| 7 | **Close** | Name, tagline, contact. | 10 | Centered, clean |

### Structure B: Demo-First (recommended for hackathons)

Open with the working product. Judges remember what they see. Explain after.

| # | Slide | Purpose | Max words |
|---|-------|---------|-----------|
| 1 | **One line** | What this is, in 5 words. Not a hook - a label. | 5 |
| 2 | **Demo** | Live or recorded. 90 seconds. The product speaks. | 0 |
| 3 | **Why this matters** | Now that they've seen it, explain the problem it solves. | 20 |
| 4 | **How** | Technical credibility. What's under the hood. | 20 |
| 5 | **Close** | Name, link, ask. | 10 |

Why it works: proof before promises. No one zones out during a live demo.

### Structure C: Contrast-Driven

Open on a specific failure or gap. Quantify the before. Show the after.

| # | Slide | Purpose | Max words |
|---|-------|---------|-----------|
| 1 | **The world today** | A specific, quantified pain. Not abstract. | 15 |
| 2 | **Why it's broken** | Root cause, not symptoms. | 15 |
| 3 | **The world after** | Same scenario, with your tool. Show the contrast. | 15 |
| 4 | **How** | What makes this possible. | 20 |
| 5 | **Proof** | Numbers, benchmarks, users. | 15 |
| 6 | **Close** | Name, link, ask. | 10 |

### Structure D: Question-Driven

Pose a provocative question. Spend the deck answering it.

| # | Slide | Purpose | Max words |
|---|-------|---------|-----------|
| 1 | **The question** | One question the audience can't ignore. | 10 |
| 2 | **The obvious answer** | What everyone assumes. | 12 |
| 3 | **Why it's wrong** | Break the assumption. | 15 |
| 4 | **The real answer** | Your approach. Demo or screenshot. | 15 |
| 5 | **Proof it works** | Numbers. | 15 |
| 6 | **Close** | Name, link. | 10 |

### Choosing a structure

During the questionnaire, present these options to the user. Don't default to
Structure A unless they specifically want a traditional pitch. For hackathons,
recommend B or C. For fellowship/grant applications, recommend D.

### General Presentation Structure

For talks, workshops, or longer formats: no fixed template. Follow the user's
outline but enforce the design rules (one idea per slide, word limits, font sizes).

</details>

---

## Phase 3: Build the HTML

<details>
<summary>Build the HTML</summary>

### Template Structure

Single HTML file. All CSS inline in `<style>`. Reveal.js loaded from CDN.
No bundled reveal.js themes - they fight custom styles.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TITLE</title>

  <!-- Fonts: pick from approved list, never Inter/Roboto/system-ui -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="GOOGLE_FONTS_URL" rel="stylesheet">

  <!-- Reveal.js (no theme, just core) -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.css">

  <style>
    /* === TOKENS === */
    :root { /* theme vars from Phase 1 */ }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    /* === BASE === */
    /* Body font: pick from approved list. NEVER Inter/Roboto. */
    .reveal {
      font-family: 'BODY_FONT', sans-serif; /* Outfit, Satoshi, General Sans */
      color: var(--text-primary);
      background: var(--bg-primary);
    }
    .reveal .slides { text-align: left; }

    /* Reset all reveal.js default heading styles */
    .reveal h1, .reveal h2, .reveal h3 {
      font-family: 'DISPLAY_FONT', sans-serif;
      font-weight: 700;
      color: var(--text-primary);
      text-transform: none;
      text-shadow: none;
      letter-spacing: -0.03em;
      margin: 0;
      padding: 0;
    }
    .reveal h1 { font-size: 4rem; line-height: 1.08; font-weight: 800; }
    .reveal h2 { font-size: 2.8rem; line-height: 1.12; }
    .reveal p {
      font-size: 1.6rem;
      line-height: 1.6;
      color: var(--text-secondary);
      margin-top: 1.5rem;
      max-width: 70%;
    }

    /* === SLIDES === */
    /* CRITICAL: reveal.js overrides flexbox on sections with absolute
       positioning and its own centering logic. Force our layout with
       !important to actually get vertical centering. */
    .reveal .slides section {
      background: var(--bg-primary);
      padding: 0 120px 0 10%;
      height: 100% !important;
      top: 0 !important;
      display: flex !important;
      flex-direction: column !important;
      justify-content: center !important;
    }

    /* Grain - subtle, on ::after to stay behind content */
    .reveal .slides section::after {
      content: '';
      position: absolute;
      inset: 0;
      background-image: url("data:image/svg+xml,...NOISE_SVG...");
      opacity: var(--grain-opacity);
      pointer-events: none;
      z-index: 0;
      mix-blend-mode: multiply;
    }
    .reveal .slides section > * { position: relative; z-index: 1; }

    /* Hook slide: centered exception */
    .slide-centered {
      align-items: center;
      text-align: center;
      padding: 5rem 10%;
    }
    .slide-centered p { max-width: 60%; }

    /* Accent color for key numbers */
    .accent { color: var(--accent); }

    /* Stats layout: horizontal, not cards */
    .stats {
      display: flex;
      gap: 5rem;
      margin-top: 3rem;
    }
    .stat .number {
      font-family: 'DISPLAY_FONT', sans-serif;
      font-size: 4rem;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
      font-variant-numeric: tabular-nums;
    }
    .stat .label {
      font-size: 1.1rem;
      color: var(--text-tertiary);
      margin-top: 0.5rem;
    }

    /* Flow diagram: horizontal nodes with arrows */
    .flow {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-top: 2.5rem;
      flex-wrap: wrap;
    }
    .flow-node {
      padding: 0.6rem 1.2rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 1.1rem;
      color: var(--text-secondary);
    }
    .flow-node.highlight {
      border-color: var(--accent);
      color: var(--accent);
      background: var(--accent-soft);
    }
    .flow-arrow {
      color: var(--text-tertiary);
      font-size: 1.2rem;
    }

    /* Items: border-top separated, not cards */
    .items {
      margin-top: 2.5rem;
    }
    .items .item {
      padding: 1.5rem 0;
      border-top: 1px solid var(--border);
    }
    .items .item:last-child { border-bottom: 1px solid var(--border); }
    .items .item-label {
      font-size: 1rem;
      font-weight: 600;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .items .item-text {
      font-size: 1.4rem;
      color: var(--text-secondary);
      margin-top: 0.4rem;
    }

    /* Demo placeholder */
    .demo-frame {
      width: 85%;
      aspect-ratio: 16/9;
      border-radius: 8px;
      background: var(--bg-surface);
      border: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-tertiary);
      font-size: 1.1rem;
      margin-top: 2rem;
    }

    /* Closing slide */
    .closing-meta {
      font-size: 1rem;
      color: var(--text-tertiary);
      margin-top: 3rem;
      letter-spacing: 0.03em;
    }
  </style>
</head>
<body>
  <div class="reveal">
    <div class="slides">
      <!-- slides here -->
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.js"></script>
  <script>
    Reveal.initialize({
      width: 1920, height: 1080,
      margin: 0.04,
      hash: true,
      transition: 'fade',
      transitionSpeed: 'slow',
      controls: false,
      progress: false,
      center: false,  /* MUST be false - we handle centering ourselves via
                         flexbox !important on sections. reveal's center:true
                         uses a different mechanism that conflicts. */
    });
  </script>
</body>
</html>
```

### Build Checklist

Before writing the file:

- [ ] All questionnaire answers collected
- [ ] Theme chosen and accent color picked
- [ ] Font pairing chosen from approved list (grep for banned fonts!)
- [ ] Slide count decided
- [ ] Content for each slide drafted (word counts checked)
- [ ] Any screenshots/images identified

After writing the file:

- [ ] Open in browser and screenshot each slide
- [ ] Verify: no banned fonts, no pure black/white, no centered body text
- [ ] Show screenshots to user for review
- [ ] Iterate on content and style based on feedback

### Screenshot Review Loop

After generating the HTML, serve locally and screenshot:

```bash
cd [project-dir] && python3 -m http.server 8787 &
```

Then use Playwright MCP to navigate to `http://localhost:8787/file.html`,
screenshot each slide, advance with ArrowRight, repeat.

Kill the server when done.

</details>

---

## Phase 4: Review and Polish

<details>
<summary>Review and Polish</summary>

### Detection Tests (adapted from visual-explainer)

Run all three before showing the deck to the user. Any failure = rework.

1. **Slop Test** - Grep the HTML for banned hex values (`#8b5cf6`, `#7c3aed`, `#d946ef`,
   `#6366f1`, `#818cf8`) and banned fonts (Inter, Roboto, Arial, Helvetica, system-ui).
   If any hit, the deck reads as AI-generated. Machine-checkable, no judgment needed.

2. **Swap Test** - If you replaced your CSS with a generic dark reveal.js theme and
   nobody would notice a difference, you haven't designed anything. The deck must have
   a visual identity that's specific to this presentation's content and brand.

3. **Squint Test** - View the deck at arm's length (or zoom out to 25%). Can you tell
   which slide is which from shape and color alone? If every slide looks identical at
   a squint, the visual hierarchy is flat and needs contrast between slide types.

### Mechanical Checks

4. **Font loading** - is every font loading? No 404s on CDN URLs?
5. **Color check** - any pure #000 or #fff? Contrast >= 4.5:1 on all text?
6. **Word count** - no slide over 25 words?
7. **Content coverage** - compare finished slides against Phase 1.5 inventory. Every
   item must be covered or explicitly marked as cut. If >30% of inventory was cut
   without user approval, flag it.

### Slide-by-Slide Checklist

| Check | Requirement |
|-------|-------------|
| One idea only | Each slide has exactly one point |
| Word limit | Under 25 words, ideally 12-15 |
| Font size | Nothing below 1rem |
| Layout | Left-aligned body, centered only for hook/close |
| Whitespace | Elements float, not crammed |
| Contrast | Text readable on background |

### Common Fixes

- **Too much text**: Split into two slides or cut to the essential sentence
- **Slide feels empty**: Increase font size. Don't add decorative filler.
- **Tech stack too dense**: Max 4-5 flow nodes. Group related items.
- **Numbers not impactful**: Make them 4rem+, use accent color, add context label

</details>

---

## Anti-Patterns

- **Never** use reveal.js bundled themes (moon, black, white, etc.)
- **Never** use transitions other than `fade`
- **Never** use Inter, Roboto, or any banned font
- **Never** use dark mode + glowing accents (the AI tell)
- **Never** use monospace as "aesthetic" - only for actual code/data
- **Never** use gradient text
- **Never** use 3-column card layouts
- **Never** use pure #000 or #fff
- **Never** center body text (only hook and close slides)
- **Never** use bullet points on hook or problem slides
- **Never** put the logo on every slide
- **Avoid** cards with shadows - use borders or whitespace for separation
- **Avoid** animations beyond reveal.js fragment fades
