---
name: visualize
description: |
  Generate high-quality SVG diagrams, Chart.js charts, interactive HTML widgets, and
  data visualizations. Applies Anthropic's production design system (reverse-engineered
  from claude.ai's generative UI) for color, typography, layout, and streaming-safe patterns.
  Auto-trigger: when generating SVG, HTML visualizations, Chart.js charts, diagrams,
  interactive explainers, or any visual artifact rendered in a browser.
---

# Visualize

Generate production-quality visual artifacts: SVG diagrams, Chart.js charts, interactive HTML widgets.

Rules below are distilled from Anthropic's internal design system for generative UI. They solve real problems (streaming DOM flicker, dark mode failures, arrow routing, Chart.js sizing bugs) that you'd otherwise hit through trial and error.

## Module Selection

Read only the reference file(s) that match the task. Don't load all of them.

| Task | Reference file | Size |
|------|---------------|------|
| Flowcharts, architecture, structural diagrams | `references/diagram.md` | ~125 lines |
| Chart.js charts, dashboards, data viz | `references/chart.md` | ~75 lines |
| Interactive explainers, sliders, calculators | `references/interactive.md` | ~80 lines |
| SVG illustration, generative art, creative | `references/art.md` | ~30 lines |

Always read `references/core.md` (~90 lines) - it contains the design system, color palette, and universal rules that apply to every module.

## Workflow

1. Read `references/core.md`
2. Read the module-specific reference(s) that match the task
3. Generate the artifact following the loaded rules
4. Self-check against the quality checklist in core.md

## Diagram Type Selection

Route on the user's *intent*, not the subject:

| User says | Type |
|-----------|------|
| "how does X work" / "explain X" / "I don't get X" | Illustrative (visual metaphor) |
| "what's the architecture" / "show the structure" | Structural (containment) |
| "what are the steps" / "walk me through" | Flowchart (sequence) |
| "show the data" / "compare these numbers" | Chart |
| "create a calculator" / "interactive explainer" | Interactive HTML |

When in doubt between flowchart and illustrative: illustrative is the more ambitious choice. Default to it for "how does X work" questions.

## DO NOT

- Put explanatory prose inside the visual artifact - text goes in your response, visuals go in the code
- Use gradients, drop shadows, blur, glow, or neon effects (they flash during streaming)
- Use emoji in SVG/HTML - use CSS shapes or SVG paths
- Hardcode colors without considering dark mode
- Draw cycles as rings (use steppers or linear flow with return arrow)
- Cram 6+ components into one diagram (decompose into multiple)
- Stack multiple visuals back-to-back without prose between them
