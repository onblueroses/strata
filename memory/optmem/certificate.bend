import Base
import ./selection.bend as S
import ./CONTRACT.bend as K

# The executable contract: consecutive prefix-sum intervals, exact final end,
# aligned powers of two, and widths never growing toward recent memories.
def guarded(flag: Bool, next: Unit -> Bool) -> Bool:
  match flag:
    case False{}:
      False{}
    case True{}:
      next(Unit{})

def layout(xs: S.Chunks, +lo: Nat, +total: Nat, +previous: Nat) -> Bool:
  match xs:
    case S.End{}:
      Nat.is_eq(lo, total)
    case S.More{+d, rest}:
      guarded(Nat.is_le(d, 31n) && Nat.is_le(d, previous), u => (
        +w = K.width(d)
        +end = Nat.add(lo, w)
        guarded(Nat.is_eq(Nat.mod(lo, w), 0n) && Nat.is_le(end, total),
          u => layout(rest, end, total, d))))

def valid(+xs: S.Chunks, +total: Nat, budget: Nat) -> Bool:
  layout(xs, 0n, total, 31n) && Nat.is_eq(K.length(xs), K.expected(total, budget))

def gate(+xs: S.Chunks, accepted: Bool) -> Maybe<&2, S.Chunks>:
  match accepted:
    case False{}:
      None{}
    case True{}:
      Some{xs}

def certify(+xs: S.Chunks, total: Nat, budget: Nat) -> Maybe<&2, S.Chunks>:
  gate(xs, valid(xs, total, budget))
