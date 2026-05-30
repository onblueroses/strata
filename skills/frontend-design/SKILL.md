---
name: frontend-design
description: |
  Senior UI/UX engineer that enforces premium, non-generic frontend code. Overrides LLM
  biases toward "AI slop" with metric-based design rules, strict component architecture,
  CSS hardware acceleration, and controlled design dials. Includes project-specific
  knowledge for Tailwind v4, German copy, and text legibility.
  Auto-trigger: when building any web UI - components, pages, layouts, or applications.
---

# High-Agency Frontend Skill

## 1. ACTIVE BASELINE CONFIGURATION

* DESIGN_VARIANCE: 8 (1=Perfect Symmetry, 10=Artsy Chaos)
* MOTION_INTENSITY: 6 (1=Static/No movement, 10=Cinematic/Magic Physics)
* VISUAL_DENSITY: 4 (1=Art Gallery/Airy, 10=Pilot Cockpit/Packed Data)

**AI Instruction:** Baseline is strictly set to these values (8, 6, 4). Adapt dynamically based on what the user explicitly requests. Use these as global variables driving Sections 4-7.

---

## 2. SKIP CONDITIONS & PRIORITY MODE

**Skip if:**
- The task is purely backend (API routes, database, CLI) - no visual component
- The user explicitly wants a quick prototype/wireframe with no styling concern
- Editing an existing design system where the aesthetic is already locked - follow the existing system

**Quick mode** (small additions to existing pages): Verify font isn't banned, palette isn't banned, no forbidden patterns. Skip full design thinking.

**Full mode (default):** Complete design thinking + all sections. Use for new pages, new sites, significant redesigns.

---

## 3. DEFAULT ARCHITECTURE & CONVENTIONS

<details>
<summary>3. DEFAULT ARCHITECTURE & CONVENTIONS</summary>

* **Dependency verification:** Before importing any 3rd party library (framer-motion, lucide-react, etc.), check `package.json`. If missing, output the install command first. Importing a missing dependency causes a build failure that the user has to debug manually - checking first takes 2 seconds and prevents a 10-minute detour.
* **Framework:** React or Next.js. Default to Server Components (RSC).
  * **RSC SAFETY:** Global state works ONLY in Client Components. Wrap providers in `"use client"` components.
  * **INTERACTIVITY ISOLATION:** If using Framer Motion magnetic effects or continuous animations, extract as isolated leaf component with `'use client'` at the top. Server Components render only static layouts.
* **Styling:** Tailwind CSS (check `package.json` for v3 vs v4 - do NOT mix syntax).
  * **T4 CONFIG GUARD:** For v4, do NOT use `tailwindcss` plugin in `postcss.config.js`. Use `@tailwindcss/postcss` or the Vite plugin.
* **No emojis in UI:** Emojis render differently across OS/browser combinations and look unprofessional in production UIs. Use icons (Radix, Phosphor) or SVG primitives instead - they render consistently and can be styled.
* **Viewport stability:** Use `min-h-[100dvh]` instead of `h-screen` for hero sections. `h-screen` uses `100vh` which doesn't account for mobile browser chrome (address bar, toolbar), causing content to be hidden behind the UI on iOS Safari and Android Chrome.
* **Grid over flex-math:** Use CSS Grid (`grid grid-cols-1 md:grid-cols-3 gap-6`) instead of `w-[calc(33%-1rem)]`. Calc-based widths break at edge cases (rounding, subpixel rendering) and require manual gap math. Grid handles gaps natively and is more readable.
* **Icons:** Use `@phosphor-icons/react` or `@radix-ui/react-icons` (check installed). Standardize `strokeWidth` (1.5 or 2.0 project-wide).
* **Container queries over viewport hacks:** Use `@container` for component-level responsiveness. A card in a sidebar adapts to its container, not the viewport. Parent: `container-type: inline-size`. Child: `@container (min-width: 400px)` instead of `@media`.

</details>

---

## 4. DESIGN ENGINEERING DIRECTIVES (Bias Correction)

<details>
<summary>4. DESIGN ENGINEERING DIRECTIVES (Bias Correction)</summary>

**Rule 1: Deterministic Typography**

Banned fonts (overused AI defaults): **Inter** (BANNED), Roboto, Arial, Helvetica, system-ui, Open Sans, Lato, Montserrat, Poppins, Space Grotesk.

Display fonts to rotate through:

| Font | Vibe | Source |
|------|------|--------|
| Cabinet Grotesk | Clean, premium | Fontshare |
| Satoshi | Clean, modern | Fontshare |
| Geist | Technical, minimal | Google Fonts |
| Clash Display | Bold, contemporary | Fontshare |
| Playfair Display | Editorial, luxury | Google Fonts |
| Fraunces | Organic, soft serif | Google Fonts |
| Syne | Geometric, modern | Google Fonts |
| Bricolage Grotesque | Quirky, characterful | Google Fonts |
| Cormorant Garamond | Refined, literary | Google Fonts |
| Instrument Serif | Elegant, editorial | Google Fonts |

Body fonts: Source Serif 4, General Sans, Literata, Outfit, Switzer.

**Technical UI Rule:** Serif fonts are BANNED for Dashboard/Software UIs. Use `Geist` + `Geist Mono` or `Satoshi` + `JetBrains Mono`.

Display defaults: `text-4xl md:text-6xl tracking-tighter leading-none`. Body: `text-base text-gray-600 leading-relaxed max-w-[65ch]`.

**Numeric typography:** `font-variant-numeric: tabular-nums` on any aligned numbers (tables, calculators, prices). Proportional digits misalign columns.
* Abbreviations: `font-variant-caps: all-small-caps` for acronyms in running text (AfA, KfW, GmbH).
* **CLS prevention:** Set `size-adjust`, `ascent-override`, `descent-override` on fallback `@font-face` to match primary font metrics.
* **Light-on-dark:** Increase `line-height` by 0.05-0.1 vs dark-on-light. Perceived weight is lower.

**Rule 2: Color Calibration**

* Max 1 Accent Color. Saturation < 80%.
* **THE LILA BAN:** "AI Purple/Blue" is BANNED. No purple glows, no neon gradients. Use Zinc/Slate neutrals with high-contrast singular accents (Emerald, Electric Blue, or Deep Rose).
* COLOR CONSISTENCY: One palette for the entire output. No fluctuation between warm and cool grays.
* Build a token system:
  ```css
  @theme {
    --color-accent: #C5945A;
    --color-accent-soft: #C5945A1a;
    --color-bg: #0A0A0F;
    --color-text: #E8E4E0;
  }
  ```

**OKLCH over HSL.** Define palettes in OKLCH:
* Reduce chroma toward extremes: full chroma at L~60%, near-zero at L<15% or L>90%.
* Tint neutrals: `oklch(L 0.01 <brand-hue>)` not `oklch(L 0 0)`. Zero-chroma grays look dead.
* Pure gray (chroma 0) is BANNED. Minimum chroma for any neutral: 0.005.
* Never use pure black (`#000`) or pure white (`#fff`). Tint both. `oklch(0.12 0.01 250)` for near-black.

**Rule 3: Layout Diversification**

* **ANTI-CENTER BIAS:** Centered Hero/H1 sections are BANNED when DESIGN_VARIANCE > 4. Force Split Screen (50/50), Left Aligned content/Right Aligned asset, or Asymmetric Whitespace.
* Dial 1-3: Flexbox `justify-center`, strict 12-column grids.
* Dial 4-7: `margin-top: -2rem` overlapping, varied image aspect ratios, left-aligned headers.
* Dial 8-10: Masonry layouts, `grid-template-columns: 2fr 1fr 1fr`, massive empty zones (`padding-left: 20vw`).
* **MOBILE OVERRIDE:** For levels 4-10, asymmetric layouts above `md:` MUST fall back to single-column (`w-full px-4 py-8`) at `< 768px`.

**Rule 4: Anti-Card Overuse**

* DASHBOARD HARDENING: For VISUAL_DENSITY > 7, generic card containers are BANNED. Use `border-t`, `divide-y`, or negative space.
* Use cards ONLY when elevation communicates hierarchy. Tint shadows to the background hue.

**Rule 5: Full Interaction Cycles**

Every interactive element MUST handle all 8 states:

| State | Requirement |
|-------|-------------|
| Default | Communicates affordance. Not blank. |
| Hover | Visual change within 100ms. Never color-only (a11y). |
| Focus | `focus-visible:ring-2 ring-offset-2`. NEVER remove without replacement. |
| Active | `-translate-y-[1px]` or `scale-[0.98]`. User must feel the click. |
| Disabled | Opacity 0.5 + `cursor-not-allowed` + `pointer-events-none`. |
| Loading | Skeleton matching layout dimensions. No generic spinners. Disable re-submission. |
| Error | Inline below element. Red border. `aria-invalid="true"`. Clear recovery path. |
| Success | Confirmation (checkmark, color flash, toast). Transitions to next state within 1-2s. |

**Empty states** are Default with no data: guide users toward action, don't just say "nothing here."

**Rule 6: Forms**

Label MUST sit above input. Helper text optional. Error text below input. `gap-2` for input blocks.

</details>

---

## 5. MOTION ENGINE

<details>
<summary>5. MOTION ENGINE</summary>

* MOTION 1-3: No animations. CSS `:hover`/`:active` only.
* MOTION 4-7: `transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1)`. **400ms with cubic-bezier(0.4, 0, 0.2, 1)** is the sweet spot for UI transitions. `animation-delay` cascades for load-ins. Only `transform` and `opacity`.
* MOTION 8-10: Framer Motion hooks. NEVER `window.addEventListener('scroll')`.

**Magnetic Micro-physics (MOTION_INTENSITY > 5):** NEVER use `useState` for magnetic hover. Use EXCLUSIVELY `useMotionValue` and `useTransform` outside the render cycle.

**Staggered Orchestration:** Do not mount lists instantly. Use `staggerChildren` (Framer) or `animation-delay: calc(var(--index) * 100ms)`. Parent and children MUST be in the same Client Component tree.

**Slide distance:** 16px translateX looks polished; 24px+ looks jumpy.

**Duration categories:**
* 100-150ms: instant feedback (hover, active, toggle)
* 200-300ms: state changes (tab switch, accordion, dropdown)
* 300-500ms: layout changes (modal, page transition, card expand)
* 500-800ms: cinematic entrances (hero reveal, staggered load-in)

**Exit = 75% of entrance.** 400ms entrance -> 300ms exit. Arrivals are events; departures should be fast.

</details>

---

## 6. PERFORMANCE GUARDRAILS

* **Hardware Acceleration:** Never animate `top`, `left`, `width`, or `height`. Animate exclusively via `transform` and `opacity`.
* **DOM Cost:** Apply grain/noise filters ONLY to `fixed inset-0 z-50 pointer-events-none` pseudo-elements. NEVER to scrolling containers.
* **Z-Index:** NEVER spam `z-50` or `z-10` unprompted. Use only for systemic contexts (Sticky Navbars, Modals, Overlays).

---

## 7. THE AI TELLS (Forbidden Patterns)

<details>
<summary>7. THE AI TELLS (Forbidden Patterns)</summary>

### Visual
* NO Neon/Outer Glows: Use inner borders or tinted shadows instead
* NO Pure Black (`#000000`): Use Off-Black, Zinc-950, or Charcoal
* NO Oversaturated Accents

### Typography
* NO Inter Font (banned, see above)
* NO Oversized H1s that scream - control hierarchy with weight and color

### Layout
* **NO 3-Column Card Layouts:** BANNED. Use 2-column Zig-Zag, asymmetric grid, or horizontal scrolling
* **Grid over flex-math** (see Section 3)

### Content & Data
* **NO Generic Names:** "John Doe", "Sarah Chan" banned. Use realistic-sounding creative names
* **NO Generic Avatars:** No SVG egg/Lucide user icons. Creative photo placeholders or styled initials
* **NO Fake Numbers:** No `99.99%`, `50%`, basic phone numbers. Use organic data: `47.2%`, `+1 (312) 847-1928`
* **NO Startup Slop Names:** "Acme", "Nexus", "SmartFlow" - invent premium contextual brand names
* **NO Filler Words:** Elevate, Seamless, Unleash, Next-Gen - use concrete verbs

### External Resources
* **NO Unsplash:** Use `https://picsum.photos/seed/{random_string}/800/600` for placeholders
* **shadcn/ui:** Never in generic default state. Always customize radii, colors, and shadows

### Cheap Sophistication Tricks (also banned)
* NO monospace typography as shorthand for "technical vibes"
* NO large rounded-corner icons above every heading (Notion-template energy)
* NO sparklines as decoration (if data isn't real, the chart is a lie)
* NO rounded elements with thick colored border on one side
* NO gradient text for impact (`background-clip: text` looks hacky on 90% of fonts)
* NO default dark mode with glowing accents (most overused "premium" look in AI output)

</details>

---

## 8. TEXT LEGIBILITY

<details>
<summary>8. TEXT LEGIBILITY</summary>

**Text over any busy/image background uses three-layer text-shadow.** Always use this instead of backdrop panels, radial gradient overlays, or backdrop-blur.

```css
/* Body text, labels, inputs, buttons */
p, span, label, a, li, button, input, textarea {
  text-shadow:
    0 1px 4px rgba(8,8,12,0.8),
    0 4px 16px rgba(8,8,12,0.5),
    0 8px 32px rgba(8,8,12,0.25);
}

/* Headings */
h1, h2, h3, h4 {
  text-shadow:
    0 2px 8px rgba(8,8,12,0.9),
    0 8px 30px rgba(8,8,12,0.6),
    0 16px 48px rgba(8,8,12,0.3);
}
```

Apply globally in base styles. Adjust rgba base color to match the background.

</details>

---

## 9. BACKGROUNDS & VISUAL DEPTH

* Gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows
* **Subtle gradients are often invisible.** `#F0EAE4 → #FAFAF9` is imperceptible. Use a solid noticeably different color or skip it.
* **Low-opacity decorative images look broken.** Opacity 0.08 reads as a rendering glitch. Commit or remove.
* **Stock photos need proper showcasing.** Half-visible, heavily cropped, or ghosted = worse than no image.

---

## 10. TAILWIND CSS v4 SPECIFICS

* Custom colors go in `@theme`, not just `:root`. Only `@theme` values generate utility classes.
* **Unlayered CSS overrides ALL Tailwind utilities.** Always wrap in `@layer base`, `@layer components`, or `@layer utilities`.
* Design tokens as CSS custom properties in `@theme`. Reusable patterns (`.btn-accent`, `.gold-line`) in `@layer components`.

---

## 11. CREATIVE ARSENAL (High-End Inspiration)

<details>
<summary>11. CREATIVE ARSENAL (High-End Inspiration)</summary>

Do not default to generic UI. Pull from these:

**Hero:** Stop doing centered text over dark image. Use asymmetric: text left or right, background with stylistic fade.

**Navigation:** Mac OS Dock Magnification, Magnetic Button, Dynamic Island, Floating Speed Dial, Mega Menu Reveal.

**Layout:** Bento Grid, Masonry Layout, Chroma Grid, Split Screen Scroll, Curtain Reveal.

**Cards:** Parallax Tilt Card, Spotlight Border Card, Glassmorphism Panel (inner border `border-white/10` + `shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]`), Holographic Foil Card, Morphing Modal.

**Scroll:** Sticky Scroll Stack, Horizontal Scroll Hijack, Zoom Parallax, Scroll Progress Path SVG.

**Typography:** Kinetic Marquee, Text Mask Reveal, Text Scramble Effect, Gradient Stroke Animation.

**Micro-interactions:** Particle Explosion Button, Skeleton Shimmer, Directional Hover Aware Button, Ripple Click Effect, Mesh Gradient Background.

**Don't mix GSAP/ThreeJS with Framer Motion in the same component tree.** They fight over the same DOM transforms, causing janky animations and hard-to-debug conflicts. Default to Framer Motion for UI interactions. Use GSAP/ThreeJS only for isolated full-page scrolltelling or canvas backgrounds where Framer Motion's React model doesn't reach.

</details>

---

## 12. BENTO 2.0 PARADIGM (SaaS Dashboards)

* **Palette:** Background `#f9fafb`. Cards `#ffffff` with `border-slate-200/50`.
* **Surfaces:** `rounded-[2.5rem]`. Diffusion shadow: `shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]`.
* **Typography:** Geist, Satoshi, or Cabinet Grotesk with `tracking-tight`.
* **Labels:** Titles and descriptions placed outside and below cards (gallery-style).

---

## 13. GERMAN COPY (for German-language interfaces)

* Avoid object-first word order with adverb separating: "Langfristig Vermögen aufbauen" > "Vermögen langfristig aufbauen"
* Break compound nouns: "Steuerersparnispotenzial" → "Steuerersparnis"
* "generieren" is corporate German. Use "erzielen", "aufbauen", "schaffen"
* Don't write presumptuous personalization ("genau Ihr Wunsch") - describe the benefit
* **Always grep for false umlauts after AI text:** `üll|ünz|üe|ürft`

---

## 14. QUALITY SELF-CHECK

After implementing, verify before presenting:
1. **Font check** - is every font loading? (check CDN URL, no 404s)
2. **Banned font check** - grep for: Inter, Roboto, Arial, Helvetica, system-ui, Open Sans
3. **Banned palette check** - purple-to-blue gradient? teal/coral? generic SaaS look?
4. **Tailwind v4 check** - custom styles in `@layer`? custom colors in `@theme`?
5. **RSC safety** - interactive components have `'use client'`? providers wrapped?
6. **Dependency check** - all imported packages present in `package.json`?
7. **Contrast check** - all text readable? (screenshot via `mcp__playwright__browser_screenshot` in Vision mode, or `/browser-use` if Playwright MCP unavailable)
8. **Mobile check** - works at 375px? (check with `/mobile-preview` if available)

**Squint test:** If it could pass for a Vercel/Next.js template or generic SaaS landing page, it's too generic. Start over with a bolder direction.
