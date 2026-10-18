import Base
import ./selection.bend as S

# Human-owned semantic requirements. These definitions, import bindings and
# chunk representation are protected by the commit check independently of the
# implementation. Changing a rule needs an explicit reviewed requirement edit.
def width(depth: Nat) -> Nat:
  match depth:
    case 0n:
      1n
    case 1n+p:
      +w = width(p)
      Nat.add(w, w)

def length(xs: S.Chunks) -> Nat:
  match xs:
    case S.End{}:
      0n
    case S.More{d, rest}:
      1n+length(rest)

# Minimum aligned cover count is the number of set bits. This ordinary natural
# definition is also the precise policy used by the executable certificate.
def minimum(fuel: Nat, +total: Nat) -> Nat:
  match fuel:
    case 0n:
      0n
    case 1n+p:
      Nat.add(Nat.mod(total, 2n), minimum(p, Nat.div(total, 2n)))

def expected(+total: Nat, budget: Nat) -> Nat:
  Nat.max(minimum(32n, total), Nat.min(total, budget))

# Structural meaning of layout; unlike its Boolean test this contains actual
# equality witnesses and an inductive order relation.
def Le(a: Nat, b: Nat) -> Data:
  match a b:
    case 0n _:
      Unit
    case 1n+p 0n:
      Empty
    case 1n+p 1n+q:
      Le(p, q)

def Partition(xs: S.Chunks, +lo: Nat, +total: Nat, +previous: Nat) -> Type:
  match xs:
    case S.End{}:
      {lo == total : Nat}
    case S.More{+d, rest}:
      +w = width(d)
      Le(d, 31n) & (Le(d, previous) &
        ({Nat.mod(lo, w) == 0n : Nat} &
          (Le(Nat.add(lo, w), total) & Partition(rest, Nat.add(lo, w), total, d))))

def Contract(+xs: S.Chunks, +total: Nat, budget: Nat) -> Type:
  Partition(xs, 0n, total, 31n) & {length(xs) == expected(total, budget) : Nat}

def AllCertified(result: Maybe<&2, S.Chunks>, total: Nat, budget: Nat) -> Type:
  match result:
    case None{}:
      Unit
    case Some{xs}:
      Contract(xs, total, budget)

# A stronger host-facing contract: absence is impossible for supported inputs.
def Success(result: Maybe<&2, S.Chunks>, total: Nat, budget: Nat) -> Type:
  match result:
    case None{}:
      Empty
    case Some{xs}:
      Contract(xs,total,budget)
