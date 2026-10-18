import Base
import ./selection.bend as S
import ./certificate.bend as C
import ./CONTRACT.bend as K
import ./PREFERENCE_CONTRACT.bend as P

def equal(xs: S.Chunks,ys: S.Chunks) -> Bool:
  match xs ys:
    case S.End{} S.End{}:
      True{}
    case S.End{} S.More{d,rest}:
      False{}
    case S.More{d,rest} S.End{}:
      False{}
    case S.More{d,rest} S.More{e,tail}:
      Nat.is_eq(d,e) && equal(rest,tail)

def check_witness(witness: Maybe<&2,P.Cut>,+xs: S.Chunks,+total: Nat,+target: Nat) -> Bool:
  match witness:
    case None{}:
      Nat.is_eq(target,total) && equal(xs,P.raws(total))
    case Some{+cut}:
      +base=P.complete(total,cut)
      C.guarded(Nat.is_le(K.length(base),target),u=>
        C.guarded(Nat.is_eq(P.strict_count(total,cut,target),1n+target),u=>
          equal(xs,P.fill(Nat.sub(target,K.length(base)),base))))

def valid(+xs: S.Chunks,+total: Nat,target: Nat) -> Bool:
  check_witness(P.worst(xs,total),xs,total,target)
