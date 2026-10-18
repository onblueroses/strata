import Base

# A chunk denotes exactly 2^depth consecutive memories. Offsets are prefix sums.
type Chunks is Data:
  End{}
  More{depth: Nat, rest: Chunks}

type Refinement is Data:
  Stayed{chunks: Chunks}
  Split{chunks: Chunks}

def width(depth: Nat) -> Nat:
  match depth:
    case 0n:
      1n
    case 1n+p:
      +w = width(p)
      Nat.add(w, w)

def width32(depth: Nat) -> U32:
  U32.shln(1, depth)

def mass(xs: Chunks) -> Nat:
  match xs:
    case End{}:
      0n
    case More{d, rest}:
      Nat.add(width(d), mass(rest))

def length(xs: Chunks) -> Nat:
  match xs:
    case End{}:
      0n
    case More{d, rest}:
      1n+length(rest)

def concat(xs: Chunks, ys: Chunks) -> Chunks:
  match xs:
    case End{}:
      ys
    case More{d, rest}:
      More{d, concat(rest, ys)}

def answer(r: Refinement) -> Chunks:
  match r:
    case Stayed{xs}:
      xs
    case Split{xs}:
      xs

def refine_stayed(d: Nat, xs: Chunks) -> Refinement:
  match d:
    case 0n:
      Stayed{More{0n, xs}}
    case 1n+p:
      +d = p
      Split{More{d, More{d, xs}}}

def refine_tail(d: Nat, r: Refinement) -> Refinement:
  match r:
    case Split{xs}:
      Split{More{d, xs}}
    case Stayed{xs}:
      refine_stayed(d, xs)

# One successful step splits the newest splittable chunk, in place.
def refine(xs: Chunks) -> Refinement:
  match xs:
    case End{}:
      Stayed{End{}}
    case More{d, rest}:
      refine_tail(d, refine(rest))

def fill(fuel: Nat, xs: Chunks) -> Chunks:
  match fuel:
    case 0n:
      xs
    case 1n+p:
      fill(p, answer(refine(xs)))


type Threshold is Data:
  Threshold{whole: U32, depth: Nat, total: U32}

def branch(-A: Type, flag: Bool, yes: Unit -> A, no: Unit -> A) -> A:
  match flag:
    case True{}:
      yes(Unit{})
    case False{}:
      no(Unit{})

# Compare binary fractions without cross products. Every shifted remainder
# stays below the larger power-of-two denominator for depths <=31.
def fraction_lt(+d: Nat, +target: Nat, +total: U32) -> Bool:
  +left = U32.and(total, U32.sub(width32(d), 1))
  +right = U32.and(total, U32.sub(width32(target), 1))
  branch(Bool, Nat.is_ge(d, target),
    u => U32.is_lt(left, U32.shln(right, Nat.sub(d, target))),
    u => U32.is_lt(U32.shln(left, Nat.sub(target, d)), right))

def split_here(+depth: Nat, +age: U32, threshold: Threshold) -> Bool:
  Threshold{+q, target, total} = threshold
  +whole = U32.shrn(age, depth)
  U32.is_lt(whole, q) ||
    (U32.is_eq(whole, q) && fraction_lt(depth, target, total))

def expand(depth: Nat, +age: U32, +threshold: Threshold) -> Chunks:
  match depth:
    case 0n:
      More{0n, End{}}
    case 1n+p:
      +d = p
      branch(Chunks, split_here(1n+d, age, threshold),
        u => concat(expand(d, age, threshold),
          expand(d, U32.sub(age, width32(d)), threshold)),
        u => More{1n+d, End{}})

def expand_all(xs: Chunks, +age: U32, +threshold: Threshold) -> Chunks:
  match xs:
    case End{}:
      End{}
    case More{+d, rest}:
      concat(expand(d, age, threshold),
        expand_all(rest, U32.sub(age, width32(d)), threshold))

# Number of internal nodes through an entire integer reciprocal group.
def groups(depth: Nat, +total: U32, +q: U32) -> U32:
  match depth:
    case 0n:
      0
    case 1n+p:
      +d = p
      U32.add(U32.min(U32.shrn(total, 1n+d), q), groups(d, total, q))

# Count nodes through this fractional reciprocal group (inclusive).
def through(depth: Nat, +total: U32, +q: U32, +target: Nat) -> U32:
  match depth:
    case 0n:
      0
    case 1n+p:
      +d = p
      +bonus = Bool.to_u32(Bool.not(fraction_lt(target, 1n+d, total)))
      U32.add(U32.min(U32.shrn(total, 1n+d), U32.add(U32.sub(q, 1), bonus)),
        through(d, total, q, target))

def find_q(+root: Nat, fuel: Nat, +lo: U32, +hi: U32, +total: U32,
  +base: U32, +budget: U32) -> U32:
  match fuel:
    case 0n:
      hi
    case 1n+p:
      +f = p
      branch(U32, U32.is_le(U32.sub(hi, lo), 1), u => hi, u => (
        +mid = U32.add(lo, U32.shr(U32.sub(hi, lo)))
        branch(U32, U32.is_gt(U32.add(base, groups(root, total, mid)), budget),
          u => find_q(root, f, lo, mid, total, base, budget),
          u => find_q(root, f, mid, hi, total, base, budget))))

def prefer(+depth: Nat, +total: U32, best: Maybe<&2, Nat>) -> Maybe<&2, Nat>:
  match best:
    case None{}:
      Some{depth}
    case Some{+old}:
      Bool.pick(Maybe<&2, Nat>, fraction_lt(depth, old, total), Some{depth}, Some{old})

def find_fraction(+root: Nat, depth: Nat, +total: U32, +q: U32, +base: U32,
  +budget: U32, +best: Maybe<&2, Nat>) -> Maybe<&2, Nat>:
  match depth:
    case 0n:
      best
    case 1n+p:
      +d = p
      +current = {1n+d : Nat}
      +crosses = U32.is_le(q, U32.shrn(total, current)) &&
        U32.is_gt(U32.add(base, through(root, total, q, current)), budget)
      find_fraction(root, d, total, q, base, budget,
        branch(Maybe<&2, Nat>, crosses, u => prefer(current, total, best), u => best))

def finish_target(q: U32, +total: U32, +budget: Nat, +xs: Chunks,
  target: Maybe<&2, Nat>) -> Chunks:
  match target:
    case None{}:
      xs
    case Some{d}:
      +coarse = expand_all(xs, total, Threshold{q, d, total})
      fill(Nat.sub(budget, length(coarse)), coarse)

def choose(+root: Nat, fuel: Nat, +budget: Nat, +total: U32, +xs: Chunks) -> Chunks:
  +base = U32.from_nat(length(xs))
  +b = U32.from_nat(budget)
  branch(Chunks, U32.is_le(b, base), u => xs, u => (
    +q = find_q(root, fuel, 0, b, total, base, b)
    finish_target(q, total, budget, xs,
      find_fraction(root, root, total, q, base, b, None{}))))

def raws(n: Nat) -> Chunks:
  match n:
    case 0n:
      End{}
    case 1n+p:
      More{0n, raws(p)}
