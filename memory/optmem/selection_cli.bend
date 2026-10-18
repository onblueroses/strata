import Base
import ./selection.bend as S
import ./certificate.bend as C
import ./RECOVERY.bend as B
import ./preference.bend as V
import ./CONTRACT.bend as K

# Only this numeric entry is invoked by the pinned native bridge. No host
# selection logic or unchecked result is exposed by the Python extension.
def seed(depth: Nat, +total: U32) -> S.Chunks:
  match depth:
    case 0n:
      S.branch(S.Chunks, U32.is_zero(U32.and(total, 1)),
        u => S.End{}, u => S.More{0n, S.End{}})
    case 1n+p:
      +d = p
      S.branch(S.Chunks, U32.is_zero(U32.and(total, S.width32(1n+d))),
        u => seed(d, total), u => S.More{1n+d, seed(d, total)})

def recover(+total: U32, +budget: U32) -> S.Chunks:
  match total:
    case U32{word}:
      B.recover_word(word, U32.to_nat(budget))

def recover_fast(+total: U32, +budget: U32) -> S.Chunks:
  match total:
    case U32{word}:
      B.recover_fast_word(word, U32.to_nat(budget))

def checked_fast_or_slow(result: Maybe<&2, S.Chunks>, +total: U32, +budget: U32) -> Maybe<&2, S.Chunks>:
  match result:
    case Some{xs}:
      Some{xs}
    case None{}:
      C.certify(recover(total,budget), U32.to_nat(total), U32.to_nat(budget))

def checked_or_recover(result: Maybe<&2, S.Chunks>, +total: U32, +budget: U32) -> Maybe<&2, S.Chunks>:
  match result:
    case Some{+xs}:
      S.branch(Maybe<&2,S.Chunks>,V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))),
        u=>Some{xs},
        u=>checked_fast_or_slow(C.certify(recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget))
    case None{}:
      checked_fast_or_slow(C.certify(recover_fast(total,budget),
        U32.to_nat(total), U32.to_nat(budget)), total, budget)

def entry(fuel: Nat, +root: Nat, +search: Nat, +total: U32, +budget: U32) -> Maybe<&2, S.Chunks>:
  match fuel:
    case 0n:
      None{}
    case 1n+p:
      S.branch(Maybe<&2, S.Chunks>, U32.is_gt(budget, 0), u => (
        +result = S.branch(S.Chunks, U32.is_ge(budget, total),
          u => S.raws(U32.to_nat(total)),
          u => S.choose(root, search, U32.to_nat(budget), total, seed(root, total)))
        checked_or_recover(C.certify(result, U32.to_nat(total), U32.to_nat(budget)), total, budget)),
        u => entry(p, root, search, total, budget))

# Native diagnostics: 0 means a valid candidate; 1 and 2 identify the two
# certified recovery paths. The proof ties the second projection to entry.
def checked_fast_status(result: Maybe<&2, S.Chunks>, +total: U32, +budget: U32) -> U32 & Maybe<&2, S.Chunks>:
  match result:
    case Some{xs}:
      (1,Some{xs})
    case None{}:
      (2,C.certify(recover(total,budget),U32.to_nat(total),U32.to_nat(budget)))

def checked_status(result: Maybe<&2, S.Chunks>, +total: U32, +budget: U32) -> U32 & Maybe<&2, S.Chunks>:
  match result:
    case Some{+xs}:
      S.branch(U32 & Maybe<&2,S.Chunks>,V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))),
        u=>(0,Some{xs}),
        u=>checked_fast_status(C.certify(recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget))
    case None{}:
      checked_fast_status(C.certify(recover_fast(total,budget),
        U32.to_nat(total),U32.to_nat(budget)),total,budget)

def entry_status(fuel: Nat, +root: Nat, +search: Nat, +total: U32, +budget: U32) -> U32 & Maybe<&2, S.Chunks>:
  match fuel:
    case 0n:
      (3,None{})
    case 1n+p:
      S.branch(U32 & Maybe<&2,S.Chunks>,U32.is_gt(budget,0),u => (
        +result=S.branch(S.Chunks,U32.is_ge(budget,total),
          u => S.raws(U32.to_nat(total)),
          u => S.choose(root,search,U32.to_nat(budget),total,seed(root,total)))
        checked_status(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget)),
        u => entry_status(p,root,search,total,budget))

# Keeps the actual numeric entry reachable in emitted C, without IO effects.
def main() -> U32 & Maybe<&2, S.Chunks>:
  entry_status(1n, 12n, 32n, 5318, 208)
