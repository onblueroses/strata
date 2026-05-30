# Core Design System

## Philosophy

- Flat: no gradients, mesh backgrounds, noise textures, or decorative effects
- Compact: show the essential visually, explain the rest in text
- Text goes in your response, visuals go in the artifact - never put paragraphs of explanation inside the HTML/SVG
- Streaming-safe: output streams token-by-token, so structure code for early useful content

## Streaming Order

- HTML: `<style>` (short) -> content HTML -> `<script>` last
- SVG: `<defs>` (markers) -> visual elements immediately
- Prefer inline `style="..."` over `<style>` blocks - inputs/controls must look correct mid-stream
- Keep `<style>` under ~15 lines
- Gradients, shadows, and blur flash during streaming DOM diffs - use solid flat fills

## Typography

- Default font: system-ui, -apple-system, sans-serif
- h1 = 22px, h2 = 18px, h3 = 16px - all font-weight: 500
- Body text = 16px, weight 400, line-height: 1.7
- Two weights only: 400 regular, 500 bold. Never 600 or 700
- Sentence case always. Never Title Case, never ALL CAPS (including SVG labels)
- No font-size below 11px
- No mid-sentence bolding. Entity names go in `code style`, not **bold**

## Color Palette

9 ramps, 7 stops each. 50 = lightest fill, 800-900 = text on light fills.

| Name | 50 | 100 | 200 | 400 | 600 | 800 | 900 |
|------|-----|-----|-----|-----|-----|-----|-----|
| Purple | #EEEDFE | #CECBF6 | #AFA9EC | #7F77DD | #534AB7 | #3C3489 | #26215C |
| Teal | #E1F5EE | #9FE1CB | #5DCAA5 | #1D9E75 | #0F6E56 | #085041 | #04342C |
| Coral | #FAECE7 | #F5C4B3 | #F0997B | #D85A30 | #993C1D | #712B13 | #4A1B0C |
| Pink | #FBEAF0 | #F4C0D1 | #ED93B1 | #D4537E | #993556 | #72243E | #4B1528 |
| Gray | #F1EFE8 | #D3D1C7 | #B4B2A9 | #888780 | #5F5E5A | #444441 | #2C2C2A |
| Blue | #E6F1FB | #B5D4F4 | #85B7EB | #378ADD | #185FA5 | #0C447C | #042C53 |
| Green | #EAF3DE | #C0DD97 | #97C459 | #639922 | #3B6D11 | #27500A | #173404 |
| Amber | #FAEEDA | #FAC775 | #EF9F27 | #BA7517 | #854F0B | #633806 | #412402 |
| Red | #FCEBEB | #F7C1C1 | #F09595 | #E24B4A | #A32D2D | #791F1F | #501313 |

### Color Assignment Rules

- Color encodes **meaning**, not sequence. Don't cycle through colors like a rainbow.
- Group nodes by category - all nodes of the same type share one color.
- 2-3 colors per diagram max. More = visual noise.
- Gray for neutral/structural nodes (start, end, generic steps).
- Prefer purple, teal, coral, pink for general categories.
- Reserve blue/green/amber/red for semantic meaning (info/success/warning/error).

### Light/Dark Mode

- Light mode: 50 fill + 600 stroke + 800 title / 600 subtitle
- Dark mode: 800 fill + 200 stroke + 100 title / 200 subtitle
- Text on colored backgrounds: always use the 800 or 900 stop from the same ramp. Never black or generic gray.
- Title and subtitle on same background must use different stops (title darker, subtitle lighter).

### CSS Variables (when rendering in a host that provides them)

- Backgrounds: `--color-background-primary` (white), `-secondary` (surfaces), `-tertiary` (page bg)
- Text: `--color-text-primary` (black), `-secondary` (muted), `-tertiary` (hints)
- Borders: `--color-border-tertiary` (default), `-secondary` (hover), `-primary` (strong)
- Layout: `--border-radius-md` (8px), `--border-radius-lg` (12px), `--border-radius-xl` (16px)

When CSS variables aren't available, use the hex values from the palette directly.

## Universal Rules

- No HTML comments or CSS comments (waste tokens, break streaming)
- No emoji - use CSS shapes or SVG paths
- No `position: fixed` (breaks iframe/viewport sizing)
- No tabs, carousels, or `display: none` during streaming - show all content stacked vertically
- No nested scrolling - auto-fit height
- Border-radius: 8px default, 12px for cards. No rounded corners on single-sided borders.
- When placing text on colored backgrounds (badges, pills), use darkest shade from same color family
- Icon sizing: 16px explicit for inline, 24px max for decorative
- Scripts execute after streaming - load libraries via CDN `<script src>`, then use globals in a following `<script>`
- CDN sources: cdnjs.cloudflare.com, esm.sh, cdn.jsdelivr.net, unpkg.com

## Quality Self-Check

Before finalizing:
- [ ] Every text element readable on both light and dark backgrounds?
- [ ] No gradients, shadows, blur, or glow effects?
- [ ] Content structured for streaming (style -> content -> scripts)?
- [ ] Font sizes >= 11px, weights only 400 or 500?
- [ ] Colors encode meaning, not sequence? Max 2-3 ramps?
- [ ] Explanatory text is in the response, not in the artifact?
