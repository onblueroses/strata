# Chart Reference (Chart.js)

## Setup Pattern

```html
<div style="position: relative; width: 100%; height: 300px;">
  <canvas id="myChart"></canvas>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js" onload="initChart()"></script>
<script>
  function initChart() {
    new Chart(document.getElementById('myChart'), {
      type: 'bar',
      data: { labels: ['Q1','Q2','Q3','Q4'], datasets: [{ label: 'Revenue', data: [12,19,8,15] }] },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }
  if (window.Chart) initChart();
</script>
```

## Critical Rules

- Canvas cannot resolve CSS variables. Use hardcoded hex values.
- Set height ONLY on the wrapper div, never on the canvas element itself.
- Wrapper div needs `position: relative`. Chart options need `responsive: true, maintainAspectRatio: false`.
- For horizontal bar charts: wrapper height >= (number_of_bars * 40) + 80 pixels.
- Multiple charts: unique IDs (`myChart1`, `myChart2`), each gets own canvas+div pair.
- Script load ordering: always use `onload="initChart()"` on CDN script tag. Add `if (window.Chart) initChart();` as fallback at end of inline script.
- For bubble/scatter: pad scale range ~10% beyond data range to prevent clipping. Or `layout: { padding: 20 }`.
- For <= 12 categories where all labels matter: `scales.x.ticks: { autoSkip: false, maxRotation: 45 }`.

## Number Formatting

Negative values: `-$5M` not `$-5M` (sign before currency symbol).

```js
(v) => (v < 0 ? '-' : '') + '$' + Math.abs(v) + 'M'
```

## Custom Legends (always use instead of Chart.js default)

Disable the built-in legend:
```js
plugins: { legend: { display: false } }
```

Build HTML legend with small squares (not dots) and values:
```html
<div style="display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 8px; font-size: 12px; color: var(--color-text-secondary,#666);">
  <span style="display: flex; align-items: center; gap: 4px;">
    <span style="width: 10px; height: 10px; border-radius: 2px; background: #3266ad;"></span>Chrome 65%
  </span>
  <span style="display: flex; align-items: center; gap: 4px;">
    <span style="width: 10px; height: 10px; border-radius: 2px; background: #73726c;"></span>Safari 18%
  </span>
</div>
```

Include value/percentage in each label for categorical data (pie, donut, single-series bar). Position above (`margin-bottom`) or below (`margin-top`) the chart.

## Dashboard Layout

Wrap summary numbers in metric cards above the chart. Chart canvas flows below without a card wrapper.

Metric card pattern:
```html
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px;">
  <div style="background: var(--color-background-secondary,#f8f8f8); border-radius: 12px; padding: 16px; border: 0.5px solid var(--color-border-tertiary,#e0e0e0);">
    <div style="font-size: 12px; color: var(--color-text-secondary,#666); margin-bottom: 4px;">Total revenue</div>
    <div style="font-size: 24px; font-weight: 500;">$2.4M</div>
  </div>
</div>
```
