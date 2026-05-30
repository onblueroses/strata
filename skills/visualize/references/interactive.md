# Interactive Reference

## When to Use

Interactive HTML widgets for explainers with sliders, calculators, live-updating values, tabbed content. Best for "show me how X works" where the user should be able to adjust parameters and see results change.

## Structure

Style first (inline preferred, `<style>` under 15 lines), then HTML controls, then `<script>` last.

## Input Styling (must look correct mid-stream)

```html
<input type="range" min="0" max="100" value="50"
  style="width: 100%; accent-color: #534AB7; margin: 8px 0;"
  oninput="update()">
```

Always use inline styles on inputs and controls - they must render correctly before `<style>` finishes streaming.

## Metric Cards

```html
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px;">
  <div style="background: var(--color-background-secondary,#f8f8f8); border-radius: 12px; padding: 16px; border: 0.5px solid var(--color-border-tertiary,#e0e0e0);">
    <div style="font-size: 12px; color: var(--color-text-secondary,#666); margin-bottom: 4px;">Monthly payment</div>
    <div id="payment" style="font-size: 24px; font-weight: 500;">$1,200</div>
  </div>
</div>
```

## Live Calculation Pattern

```html
<div style="padding: 1rem 0;">
  <label style="font-size: 14px; color: var(--color-text-secondary,#666);">
    Interest rate: <span id="rateLabel">5%</span>
  </label>
  <input type="range" id="rate" min="1" max="15" value="5"
    style="width: 100%; accent-color: #534AB7;" oninput="update()">

  <!-- Metric cards here showing computed values -->
</div>

<script>
function update() {
  const rate = +document.getElementById('rate').value;
  document.getElementById('rateLabel').textContent = rate + '%';
  // Compute and update metric card values
}
</script>
```

## Steppers (for cycles and multi-stage processes)

Don't use SVG rings for cycles. Use an HTML stepper:

```html
<div id="stepper">
  <div style="display: flex; gap: 8px; margin-bottom: 16px;">
    <!-- Step indicators -->
    <span class="dot active" style="width: 8px; height: 8px; border-radius: 50%; background: #534AB7;"></span>
    <span class="dot" style="width: 8px; height: 8px; border-radius: 50%; background: #D3D1C7;"></span>
  </div>
  <div id="panel">
    <!-- Current step content -->
  </div>
  <button onclick="next()" style="margin-top: 12px; padding: 8px 16px; border-radius: 8px; border: 0.5px solid var(--color-border-tertiary,#ddd); background: var(--color-background-secondary,#f8f8f8); cursor: pointer;">
    Next
  </button>
</div>
```

## Rules

- No `display: none` during streaming - hidden content streams invisibly. Show all content stacked.
- Post-streaming JS-driven steppers/tabs are fine (scripts run after streaming completes).
- No `position: fixed` - breaks viewport sizing.
- No nested scrolling - auto-fit height.
- Buttons: 0.5px border, 8px border-radius, no gradients or shadows.
