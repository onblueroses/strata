# Art & Illustration Reference

## When to Use

SVG illustration, generative art, creative visual patterns. "Draw me a sunset", "create a geometric pattern", "illustrate how X looks".

## Aesthetic (differs from diagrams)

- Fill the canvas - art should feel rich, not sparse
- Bold colors: mix across ramps freely (info blue, success green, warning amber)
- Custom color choices are fine here - freestyle colors, `prefers-color-scheme` for dark mode variants
- Layer overlapping opaque shapes for depth
- Organic forms with `<path>` curves, `<ellipse>`, `<circle>`
- Texture via repetition (parallel lines, dots, hatching) - not raster effects
- Geometric patterns with `<g transform="rotate()">` for radial symmetry

## SVG Setup

Same setup as diagrams (see diagram.md SVG Setup section), but:
- viewBox should fill generously - art benefits from breathing room
- Custom `<style>` color blocks are acceptable (unlike diagrams which use ramp classes)
- No markers/arrows typically needed

## Rules

- No gradients, drop shadows, blur, glow, or neon (streaming artifacts)
- No emoji
- For illustrative diagrams that are more "art" than "reference": map colors to physical properties (warm ramps for heat/energy, cool for cold/calm, green for organic, gray for structural)
