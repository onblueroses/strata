---
name: vercel-react-best-practices
description: |
  React and Next.js performance optimization guidelines from Vercel Engineering.
  Auto-trigger: when writing, reviewing, or refactoring React/Next.js components, pages, data fetching, or bundle optimization code.
license: MIT
metadata:
  author: vercel
  version: "1.0.0"
---

# Vercel React Best Practices

Comprehensive performance optimization guide for React and Next.js applications, maintained by Vercel. Contains 45 rules across 8 categories, prioritized by impact to guide automated refactoring and code generation.

## Skip Conditions

- **Skip if** the project is not React or Next.js (check for `react` in package.json dependencies)
- **Skip if** the change is purely content/copy - no component or data flow changes
- **Skip if** the file being edited is a config file (next.config, tailwind.config, etc.) with no component logic

## Priority Mode

**When to use:** Quick code review, single-component changes, or time-constrained work.

**Quick mode:** Check only CRITICAL rules (Categories 1-2: Waterfalls + Bundle Size). These catch the highest-impact issues. Skip Categories 3-8.

**Full mode (default):** Check all applicable categories based on what the code touches.

| Code touches... | Check categories |
|-----------------|-----------------|
| `async`/`await`, `fetch`, data loading | 1 (Waterfalls) |
| `import`, `dynamic`, third-party libs | 2 (Bundle Size) |
| Server components, `cache()`, streaming | 3 (Server-Side) |
| `useSWR`, client-side fetching | 4 (Client Data) |
| `useState`, `useEffect`, `useMemo` | 5 (Re-renders) |
| JSX, SVG, CSS-in-JS, animations | 6 (Rendering) |
| Loops, lookups, data transforms | 7 (JS Perf) |
| Refs, custom hooks, advanced patterns | 8 (Advanced) |

## When to Apply

Reference these guidelines when:
- Writing new React components or Next.js pages
- Implementing data fetching (client or server-side)
- Reviewing code for performance issues
- Refactoring existing React/Next.js code
- Optimizing bundle size or load times

## Rule Categories by Priority

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Eliminating Waterfalls | CRITICAL | `async-` |
| 2 | Bundle Size Optimization | CRITICAL | `bundle-` |
| 3 | Server-Side Performance | HIGH | `server-` |
| 4 | Client-Side Data Fetching | MEDIUM-HIGH | `client-` |
| 5 | Re-render Optimization | MEDIUM | `rerender-` |
| 6 | Rendering Performance | MEDIUM | `rendering-` |
| 7 | JavaScript Performance | LOW-MEDIUM | `js-` |
| 8 | Advanced Patterns | LOW | `advanced-` |

## Quick Reference

<details>
<summary>Quick Reference</summary>

### 1. Eliminating Waterfalls (CRITICAL)

- `async-defer-await` - Move await into branches where actually used
- `async-parallel` - Use Promise.all() for independent operations
- `async-dependencies` - Use better-all for partial dependencies
- `async-api-routes` - Start promises early, await late in API routes
- `async-suspense-boundaries` - Use Suspense to stream content

### 2. Bundle Size Optimization (CRITICAL)

- `bundle-barrel-imports` - Import directly, avoid barrel files
- `bundle-dynamic-imports` - Use next/dynamic for heavy components
- `bundle-defer-third-party` - Load analytics/logging after hydration
- `bundle-conditional` - Load modules only when feature is activated
- `bundle-preload` - Preload on hover/focus for perceived speed

### 3. Server-Side Performance (HIGH)

- `server-cache-react` - Use React.cache() for per-request deduplication
- `server-cache-lru` - Use LRU cache for cross-request caching
- `server-serialization` - Minimize data passed to client components
- `server-parallel-fetching` - Restructure components to parallelize fetches
- `server-after-nonblocking` - Use after() for non-blocking operations

### 4. Client-Side Data Fetching (MEDIUM-HIGH)

- `client-swr-dedup` - Use SWR for automatic request deduplication
- `client-event-listeners` - Deduplicate global event listeners

### 5. Re-render Optimization (MEDIUM)

- `rerender-defer-reads` - Don't subscribe to state only used in callbacks
- `rerender-memo` - Extract expensive work into memoized components
- `rerender-dependencies` - Use primitive dependencies in effects
- `rerender-derived-state` - Subscribe to derived booleans, not raw values
- `rerender-functional-setstate` - Use functional setState for stable callbacks
- `rerender-lazy-state-init` - Pass function to useState for expensive values
- `rerender-transitions` - Use startTransition for non-urgent updates

### 6. Rendering Performance (MEDIUM)

- `rendering-animate-svg-wrapper` - Animate div wrapper, not SVG element
- `rendering-content-visibility` - Use content-visibility for long lists
- `rendering-hoist-jsx` - Extract static JSX outside components
- `rendering-svg-precision` - Reduce SVG coordinate precision
- `rendering-hydration-no-flicker` - Use inline script for client-only data
- `rendering-activity` - Use Activity component for show/hide
- `rendering-conditional-render` - Use ternary, not && for conditionals

### 7. JavaScript Performance (LOW-MEDIUM)

- `js-batch-dom-css` - Group CSS changes via classes or cssText
- `js-index-maps` - Build Map for repeated lookups
- `js-cache-property-access` - Cache object properties in loops
- `js-cache-function-results` - Cache function results in module-level Map
- `js-cache-storage` - Cache localStorage/sessionStorage reads
- `js-combine-iterations` - Combine multiple filter/map into one loop
- `js-length-check-first` - Check array length before expensive comparison
- `js-early-exit` - Return early from functions
- `js-hoist-regexp` - Hoist RegExp creation outside loops
- `js-min-max-loop` - Use loop for min/max instead of sort
- `js-set-map-lookups` - Use Set/Map for O(1) lookups
- `js-tosorted-immutable` - Use toSorted() for immutability

### 8. Advanced Patterns (LOW)

- `advanced-event-handler-refs` - Store event handlers in refs
- `advanced-use-latest` - useLatest for stable callback refs

</details>

## How to Use

Read individual rule files for detailed explanations and code examples:

```
rules/async-parallel.md
rules/bundle-barrel-imports.md
rules/_sections.md
```

Each rule file contains:
- Brief explanation of why it matters
- Incorrect code example with explanation
- Correct code example with explanation
- Additional context and references

## DO NOT

- Apply low-priority optimizations (Categories 5-8) before fixing CRITICAL issues (Categories 1-2) - waterfall elimination and bundle size have 10x more impact than re-render optimization
- Add `useMemo`/`useCallback` everywhere "just in case" - memoization has a cost; only apply when profiling shows a bottleneck or when passing callbacks to memoized children
- Convert working client components to server components without checking if they use hooks, event handlers, or browser APIs - these will break silently or require `"use client"` anyway
- Optimize code you haven't measured - "this looks slow" is not a finding; use React DevTools Profiler or browser performance tools first
- Apply `React.cache()` in client components - it only works in server components within a single request

## Quality Self-Check

After applying optimizations or reviewing code against these rules:
1. **No regressions** - does the component still render correctly? (check with browser-use if available)
2. **Rules matched to code** - did you only flag rules relevant to what the code actually does?
3. **Priority respected** - are CRITICAL issues (Categories 1-2) addressed before MEDIUM/LOW?
4. **No premature optimization** - is every change addressing a real pattern, not a hypothetical?

## Full Compiled Document

For the complete guide with all rules expanded: `AGENTS.md`
