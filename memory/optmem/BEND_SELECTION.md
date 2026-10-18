# Checked Bend selection

This source checkout uses Bend automatically for `memo wake`. Every returned
selection passes a proved Bend certificate before crossing the native boundary.
Persistence, locking, record IO, summary content and merge scheduling stay in
Python. The upstream installer still downloads upstream's standalone Python
tool; it does not install this checkout or provide these guarantees.

## Use and extend

Run `python3 memo wake` normally. Missing or changed builds trigger proof,
compilation and independent ABI smoke automatically. Failure produces a
controlled error, with no silent fallback. The explicit recovery command
`OPTMEM_SELECTION=python python3 memo wake` does not provide Bend guarantees.

Development needs CPython with its GIL, Clang >=16, Python development headers,
and Lean 4.34.0 for the kernel verdict. Bend **2.0.32**'s executable, Base and
BendTT source hashes are pinned in `BEND_TOOLCHAIN.json`. Builds use that
installed release or an exactly verified compiler snapshot retained in an
immutable native generation. The global installer or `bend update` can replace
the release; a fresh checkout without either copy needs the pinned version.
No tools are downloaded or replaced automatically. There is no documented
public Bend C embedding API; this bridge pins private emitted-C behavior.
The previous 2.0.4 generation is retained under `.local/` for comparison.

```sh
BEND_NO_TELEMETRY=1 bend guide
python3 bend_selection.py --check
python3 test_bend.py --benchmark
```

The check command proves, builds, tests synthetic native/host behavior, and
installs this repo's pre-commit hook without replacing another configured hook.
Commits affecting verification inputs check their exact staged snapshot,
including its staged checker. Existing semantic definitions, named claims,
import bindings and chunk representation are preserved against HEAD. New
definitions, imports and laws are allowed; changing an existing requirement
needs explicit review. The first authorized migration establishes
`CONTRACT.bend` as that baseline. Runtime rebuilds enforce this baseline too.

Add a compatible law in `LAWS.bend`, implement its check, prove soundness and
completeness in `PROOF.bend`, and add successful and violating controls in
`test_bend.py`. `CONTRACT.bend` and `PREFERENCE_CONTRACT.bend` hold frozen
semantic requirements. Changing an established requirement needs an explicitly
reviewed, versioned migration; quietly narrowing a validator breaks its
completeness law. Add new inputs to `SOURCES` and verification `FILES`.
Unfrozen imports and unsafe/hole markers are rejected. Run the one check command.

The host domain is **0 <= T <= 2^32-1**, **1 <= budget <= 2^32-1**, with
**min(T,budget) <= 65535** requested blocks. Unsupported requests are errors.
The previous compressed-budget-1000 limit is gone. An aligned dyadic cover
needs at least `popcount(T)` blocks; infeasible budgets retain complete coverage.
For example 7/1 returns `[0,4), [4,6), [6,7)`.

## Guarantees and boundary

`CONTRACT.bend` defines adjacent prefix-sum intervals with no gaps or overlaps,
final end T, aligned powers of two with depths <=31, and widths nonincreasing
toward recent memories. Its exact U32 count policy is
`max(popcount(T), min(T,budget))`: feasible budgets are met exactly.

The named laws check against the executable:

- Actual refinement and threshold selection preserve mass.
- Successful certificates imply the inductive partition/count contract.
- Every semantic contract witness passes the certificate.
- For every positive-budget U32 request, the actual entry returns a cover
  satisfying the full partition/count contract. Its native status is proved
  to be one of 0, 1, or 2.
- Status 0 means the result also satisfies the independent preference contract:
  the finest complete reciprocal-ratio cutoff fitting the target, with the
  remaining budget spent on newest-first splits. Its validator is proved both
  sound and complete. Recovery statuses 1 and 2 satisfy geometry/count but do
  not assert preference.
- Raw refinement and recent splitting behave correctly; empty, nonempty raw,
  compressed, and preferred positive entry examples succeed.

Universal fast-search preference, global minimax optimality, equivalence to
Python's 60-step floating search, compiler correctness, machine lowering,
persistence and summary semantics are **not** proved. The independent exact
rational oracle checks preferred output on a finite corpus; an exhaustive
partition oracle checks the minimax/lexicographic objective through 48 entries.
The universal proof establishes valid output and bounded status, not a bound
on evaluation time or resource use.

The algorithm counts split nodes across at most 31 depth groups, binary-searches
the integer reciprocal threshold, compares dyadic fractional parts with shifts,
and expands once. It avoids repeated quadratic expansion and overflowing cross
products. Remaining ties split from the recent end as in the Python selector.

The C bridge contains no selection algorithm. It calls only the certified
numeric entry, reads the pinned status/option/chunk layout, rejects unknown
statuses, converts to Python intervals and defensively rechecks count, extent,
alignment and recency. Status 1 or 2 raises a Python warning so a change in the
preferred path cannot silently degrade quality. Three exact runtime
adaptations turn fail-stop into Python errors, bound CPU stack frames and cap
evaluation at 200 million segments while polling Python signals. The cap can
refuse a valid request; it is a resource guard, not a universal runtime bound.
A sparse 1 GiB virtual arena and 8 MiB stack replace
standalone reservations; pages become resident only as used. No daemon,
threads or signal handlers are installed. A reentrant callback is rejected
before it can reset the active arena. The GIL stays held; subinterpreters
and free-threaded builds are rejected. Fork/errors reset the arena; teardown
releases it. Loaded generations remain cached for the process lifetime;
ordinary memo commands are short-lived.

Builds snapshot all own inputs and pinned compiler, check all proofs and run
Lean-backed `--verdict` before emitting C,
compile and smoke-test in a separate process, check sources again, then publish
an immutable `.local/bend/native/` generation atomically. Every request hashes
source contents and the selected binary against its strict receipt before
loading that resolved generation. Receipt hashes use BLAKE2b-256; compiler
provenance uses SHA-256. These bind trusted artifacts to source; they are not
signatures against a hostile filesystem owner. Failed builds and fixtures are
retained under `.local/`.

## Evidence

The full existing default suite passes **193941 checks, zero failures**.
The native suite verifies **10045** Python/native partitions through U32 edges,
realistic 5324/30, high budgets and infeasible budgets. Independent exact
rational and exhaustive partition oracles test the preference semantics.
Positive proof controls pass; mutations accepting bad layouts, dropping
alignment/end checks, breaking the seed, changing status 1 to 3, rejecting
all preferred candidates with an adapted vacuous soundness proof, or returning
blanket None fail. Further controls cover
stale-source reproving with preserved mtime, failed publication, requirement
weakening, native bounds, 2000-call allocator reuse, GIL-serialized threads,
fork reset, unchanged signal handlers, pending signal delivery, reentrant
signal callbacks with interruption and later reuse, memory refusal,
and unchanged synthetic stores. Synthetic suites disable telemetry.

Representative interleaved medians on 2026-09-28 with Bend 2.0.32, including
certificate, source hashing, loading and conversion:

| Workload | Python | Checked native |
|---|---:|---:|
| warm selector 5324/30 | 0.363 ms | 0.440 ms |
| warm selector 5318/208 | 2.359 ms | 0.603 ms |
| warm selector 1000000/208 | 2.531 ms | 0.732 ms |
| warm selector U32 maximum/208 | 3.025 ms | 0.925 ms |
| complete cold wake 5324/30 | 37.338 ms | 40.806 ms |
| complete cold wake 5324/208 | 41.426 ms | 42.077 ms |

Startup/IO dominate normal 30-line wake. The independent preference check
makes that small selector slower than Python, and the cold command is about
3.5 ms slower in this run; the 208-line cold wake is about 0.7 ms slower.
An earlier run under machine contention measured 88.4/103.0 ms at 30 lines,
so cold-command timing is sensitive to concurrent load. These measurements do
not support an order-of-magnitude whole-wake speed claim. The healthy native
65535/65534 case completes in tens of milliseconds, replacing the prior
ten-second timeout. A forced slow recovery at that edge reaches the native
resource limit and reports a controlled error. Rerun the benchmark on the
target host.
