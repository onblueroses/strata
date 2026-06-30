<!-- keywords: optimization, optimizer, autooptimize, autooptimization, SA, simulated annealing, packing, search, metaheuristic, Monte Carlo, MCMC -->
# Optimization Philosophy

Principles for automated numerical optimization. Applies to any combinatorial/continuous optimization where you're running SA, MCMC, evolutionary, or similar metaheuristic search.

## Quick Nav

| Section | Jump to |
|---------|---------|
| Core principles | #core-principles |
| Diagnostics-first | #diagnose-before-you-compute |
| Adaptive search | #adaptive-beats-fixed |
| Archive strategy | #large-diverse-archive |
| Chaos pulses | #frequent-chaos-pulses |
| Boundary targeting | #target-the-bottleneck |
| Systematic sweeps | #coordinate-descent-for-endgame |
| Anti-patterns | #anti-patterns |

## Core Principles

1. **Diagnose before you compute.** More hours on a broken algorithm is waste. When stuck, analyze *why* workers can't improve - is the step size wrong? Are moves targeting the wrong degrees of freedom? Is the landscape flat or are you in a basin?

2. **Adaptive beats fixed.** Fixed hyperparameters (step size, temperature) are a guess. Adaptive mechanisms (target acceptance rate, self-tuning step sizes) find the right operating point automatically. Target ~23% acceptance for random-walk Metropolis.

3. **Frequent restarts from a diverse archive beat rare catastrophes.** A chaos pulse every 5 stale rounds with 20 archived solutions massively outperforms a catastrophe every 18 hours with 5 archived solutions. The cost of restarting is low; the cost of grinding in a dead basin is high.

4. **Target the bottleneck.** In packing problems, only boundary objects determine the score. Moving interior objects is wasted compute. Identify what constrains your objective and focus moves there.

5. **Systematic sweeps complement stochastic search.** Coordinate descent (try +/- delta for each variable) finds improvements that random perturbation misses, especially in the endgame where the improvement corridor is narrow.

## Diagnose Before You Compute

<details>
<summary>Diagnose Before You Compute</summary>

Before adding compute time, answer these questions:

- **What's the gap between per-round worker scores and global best?** If workers consistently reach X but can't beat Y, the issue is either step size (too coarse to navigate the corridor) or basin structure (need to escape entirely).
- **Which worker types are producing valid improvements?** If hot explorers score 4.x when the best is 2.95x, they're wasting cycles. Reallocate to what works.
- **Are invalid solutions close to valid ones?** If elastic/soft-constraint workers produce scores below the best but solutions fail verification, the optimizer is finding better arrangements that just need constraint resolution. That's a sign to invest in constraint-aware moves.
- **Is the improvement rate decelerating?** Plot improvements per hour. Exponential decay means you're approaching a basin floor. Linear means the algorithm is working but slow. Flat means it's stuck.

### The Step Size Diagnostic

The single most impactful diagnostic: compare your step size to the improvement you need. If you need 0.003 improvement and your smallest step is 0.002, the search can only find improvements by lucky combinations of moves. Reduce step sizes to be ~10x smaller than the target improvement.

</details>

## Adaptive Beats Fixed

<details>
<summary>Adaptive Beats Fixed</summary>

### Acceptance Rate Targeting

Track acceptance rate in rolling windows (~10,000 iterations). Adjust step size:
- Rate > target: increase step by 10%
- Rate < target: decrease step by 10%
- Target: 23.4% for single-variable Metropolis (optimal for Gaussian proposals)
- Step bounds: [0.0001, 0.5] prevents degenerate behavior

### Temperature Schedules

Geometric cooling (`temp *= (1 - rate)`) is fine for initial exploration. But for long runs, use **reheating** after stagnation rather than continuous cooling to zero.

### Why This Matters

Fixed step sizes are a bet on the landscape scale. At score 3.0, step=0.02 is fine. At score 2.955, it's 10x too large. Adaptive sizing automatically transitions from exploration to exploitation as the optimizer converges.

</details>

## Large Diverse Archive

<details>
<summary>Large Diverse Archive</summary>

### Archive Design

- **20 slots** (not 5). More diversity = more escape routes from basins.
- **L2 distance threshold** of 0.5 between solutions (lower than typical). Allows structurally similar but scoring-different solutions.
- **Sorted by score.** Best solutions at index 0.
- **Exponential bias for seeding:** `index = int(random^2 * len(archive))` favors better solutions but still samples worse ones occasionally.

### Seeding From Archive

Every worker round, seed workers from the archive instead of always from global best:
- **Exploiters (Type A):** Exponential bias toward best archive entries, small perturbation
- **Explorers (Type B):** Uniform or reverse-biased sampling, larger perturbation
- **Specialists (boundary, coord descent):** Always from best (need valid starting point)

### Archive Maintenance

On chaos pulse: perturb some archive entries (never the best) with large kicks. This refreshes the archive's diversity without losing the best solutions.

</details>

## Frequent Chaos Pulses

<details>
<summary>Frequent Chaos Pulses</summary>

### Timing

Every 5 stale rounds, not every 18 hours. Round-based is better than time-based because it adapts to round duration (which varies with problem difficulty and worker count).

### What a Chaos Pulse Does

1. **Inject new seeds** into the archive from global best with increasing kick sizes (0.03, 0.07, 0.11, ...)
2. **Perturb archive entries** (except the best) with large random kicks. Bias toward worse entries.
3. **Re-sort archive** by score.
4. **Escalate kick sizes** with each successive pulse (pulse #1 uses smaller kicks than pulse #5). If the optimizer hasn't escaped after 5 pulses, it needs bigger perturbations.

### Why Frequent

The cost of a chaos pulse is one round of slightly worse worker seeds. The benefit is escaping a dead basin. At 5 rounds per pulse with ~5 min/round, you get 12 escape attempts per hour vs. the old approach of 1 per 18 hours.

</details>

## Target the Bottleneck

<details>
<summary>Target the Bottleneck</summary>

### Boundary-Aware Moves

For packing problems (minimize enclosing circle/rectangle):
1. Compute the enclosing shape (MEC center + radius)
2. Identify which objects have sample points on/near the boundary (within epsilon)
3. 75% of moves target boundary objects, 25% random
4. Bias boundary object moves **toward the center** (40% directional + 60% random)
5. Recompute boundary every ~100K iterations (it shifts as objects move)

### General Principle

Every optimization problem has a bottleneck - the constraint or variable that most limits the objective. Standard SA treats all variables equally. Bottleneck-targeting focuses compute where it matters.

Examples:
- **Packing:** boundary objects determine enclosing size
- **Scheduling:** critical path tasks determine makespan
- **Routing:** longest edge determines tour length

</details>

## Coordinate Descent for Endgame

<details>
<summary>Coordinate Descent for Endgame</summary>

When stochastic search plateaus, systematic sweeps find improvements it misses:

1. For each object, for each coordinate (x, y, angle):
   - Try +step, accept if improves
   - Try -step, accept if improves
2. Repeat with decreasing steps: [0.005, 0.002, 0.001, 0.0005, 0.0002, 0.0001]
3. At each step level, repeat passes until no improvement found (max 10 passes)

This is deterministic and exhaustive at each scale. It won't escape basins (that's what chaos pulses are for) but it will find every micro-improvement within the current basin.

**When to use:** Allocate 1-2 workers to coordinate descent, not all. It complements stochastic search, doesn't replace it.

</details>

## Anti-Patterns

- **"Just add more compute"** - 25 hours at fixed step=0.02 produced zero improvement. 30 minutes at step=0.0005 found 3 improvements. Diagnose first.
- **Rare catastrophes** - An 18-hour stall timer means the optimizer spends most of its time grinding in dead basins. 5-round chaos pulses are 200x more responsive.
- **Tiny diverse pool** - 5 slots means 5 escape routes. 20 slots means 20. The memory cost is negligible.
- **Uniform worker seeding** - Always starting from global best means all workers explore the same basin. Archive-biased seeding with varying perturbation sizes ensures parallel diversity.
- **Ignoring worker diagnostics** - If Type B (hot explorer) scores 4.x when best is 2.95x, those workers are wasting CPU. Reallocate to types that produce competitive scores.
- **Fixed temperature schedules** - A schedule designed for 120 hours is wrong after a restart at hour 80. Adaptive mechanisms don't have this problem.
