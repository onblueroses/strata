import Base
import ./selection.bend as S
import ./certificate.bend as C
import ./CONTRACT.bend as K
import ./selection_cli.bend as E
import ./PREFERENCE_CONTRACT.bend as P
import ./preference.bend as V

# These quantify over every chunk forest / depth / iteration count, not samples.
# A forest renders as consecutive prefix-sum intervals. Conservation therefore
# preserves its covered extent; host checks also establish initial alignment.
law refine_conserves:
  for +xs: S.Chunks
  {S.mass(S.answer(S.refine(xs))) == S.mass(xs) : Nat}

law fill_conserves:
  for fuel: Nat
  for +xs: S.Chunks
  {S.mass(S.fill(fuel, xs)) == S.mass(xs) : Nat}

law threshold_conserves:
  for +depth: Nat
  for +age: U32
  for +ratio: S.Threshold
  {S.mass(S.expand(depth, age, ratio)) == S.width(depth) : Nat}

law forest_threshold_conserves:
  for +xs: S.Chunks
  for +age: U32
  for +ratio: S.Threshold
  {S.mass(S.expand_all(xs, age, ratio)) == S.mass(xs) : Nat}

law selection_conserves:
  for +root: Nat
  for +fuel: Nat
  for +budget: Nat
  for +total: U32
  for +xs: S.Chunks
  {S.mass(S.choose(root, fuel, budget, total, xs)) == S.mass(xs) : Nat}

# Successful refinement, and the no-work case, are requirements too.
law raw_stays:
  for +n: Nat
  {S.refine(S.raws(n)) == S.Stayed{S.raws(n)} : S.Refinement}

law recent_split:
  for +depth: Nat
  for +raw_tail: Nat
  {S.refine(S.More{1n+depth, S.raws(raw_tail)}) ==
    S.Split{S.More{depth, S.More{depth, S.raws(raw_tail)}}} : S.Refinement}

# Proof of the mandatory executable certificate, with inductive witnesses:
# no gaps/overlaps or missing end; aligned dyadic nodes; widths nonincreasing;
# exact feasible count, or the unavoidable minimum when budget is impossible.
law layout_sound:
  for +xs: S.Chunks
  for +lo: Nat
  for +total: Nat
  for +previous: Nat
  for checked: {C.layout(xs, lo, total, previous) == True{} : Bool}
  K.Partition(xs, lo, total, previous)

law certificate_sound:
  for +xs: S.Chunks
  for +total: Nat
  for +budget: Nat
  K.AllCertified(C.certify(xs, total, budget), total, budget)

law accepted_contract:
  for +xs: S.Chunks
  for +total: Nat
  for +budget: Nat
  for accepted: {C.certify(xs, total, budget) == Some{xs} : Maybe<&2, S.Chunks>}
  K.Contract(xs, total, budget)

law executable_sound:
  for fuel: Nat
  for +root: Nat
  for +search: Nat
  for +total: U32
  for +budget: U32
  K.AllCertified(E.entry(fuel, root, search, total, budget), U32.to_nat(total), U32.to_nat(budget))

# A true validator flag is accepted; semantic completeness is a separate law.
law flag_acceptance:
  for +xs: S.Chunks
  for +total: Nat
  for +budget: Nat
  for valid: {C.valid(xs, total, budget) == True{} : Bool}
  {C.certify(xs, total, budget) == Some{xs} : Maybe<&2, S.Chunks>}

# Input-only successful path. This fails if the executable becomes blanket None.
law empty_entry_success:
  for +root: Nat
  for +search: Nat
  {E.entry(1n, root, search, 0, 1) == Some{S.End{}} : Maybe<&2, S.Chunks>}

law unit_entry_success:
  for +root: Nat
  for +search: Nat
  {E.entry(1n, root, search, 1, 1) == Some{S.More{0n, S.End{}}} : Maybe<&2, S.Chunks>}

law compressed_entry_success:
  {E.entry(1n, 2n, 32n, 7, 3) == Some{S.More{2n, S.More{1n, S.More{0n, S.End{}}}}} : Maybe<&2, S.Chunks>}

# Every semantic partition/count witness passes the executable validator.
law layout_complete:
  for +xs: S.Chunks
  for +lo: Nat
  for +total: Nat
  for +previous: Nat
  for witness: K.Partition(xs, lo, total, previous)
  {C.layout(xs, lo, total, previous) == True{} : Bool}

law certificate_completeness:
  for +xs: S.Chunks
  for +total: Nat
  for +budget: Nat
  for witness: K.Contract(xs, total, budget)
  {C.certify(xs, total, budget) == Some{xs} : Maybe<&2, S.Chunks>}

# Supported host requests always return a fully certified cover.
law supported_entry_success:
  for +root: Nat
  for +search: Nat
  for +total: U32
  for +budget: U32
  for positive: {U32.is_gt(budget,0) == True{} : Bool}
  K.Success(E.entry(1n,root,search,total,budget),U32.to_nat(total),U32.to_nat(budget))

# The native decoder accepts exactly the three executable success tags.
law supported_status_domain:
  for +root: Nat
  for +search: Nat
  for +total: U32
  for +budget: U32
  for positive: {U32.is_gt(budget,0) == True{} : Bool}
  {U32.is_le(Pair.fst(U32,Maybe<&2,S.Chunks>,E.entry_status(1n,root,search,total,budget)),2) == True{} : Bool}

law status_projection:
  for fuel: Nat
  for +root: Nat
  for +search: Nat
  for +total: U32
  for +budget: U32
  {Pair.snd(U32,Maybe<&2,S.Chunks>,E.entry_status(fuel,root,search,total,budget)) ==
    E.entry(fuel,root,search,total,budget) : Maybe<&2,S.Chunks>}

law preferred_sound:
  for +xs: S.Chunks
  for +total: U32
  for +target: Nat
  for checked: {V.valid(xs,U32.to_nat(total),target) == True{} : Bool}
  P.Preferred(xs,U32.to_nat(total),target)

law preferred_complete:
  for +xs: S.Chunks
  for +total: U32
  for +target: Nat
  for witness: P.Preferred(xs,U32.to_nat(total),target)
  {V.valid(xs,U32.to_nat(total),target) == True{} : Bool}

law status_preferred:
  for +root: Nat
  for +search: Nat
  for +total: U32
  for +budget: U32
  for positive: {U32.is_gt(budget,0) == True{} : Bool}
  P.Marked(E.entry_status(1n,root,search,total,budget),
    U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget)))

# An input-only positive witness prevents a blanket "recover everything" tag.
law preferred_entry_example:
  {Pair.fst(U32,Maybe<&2,S.Chunks>,E.entry_status(1n,3n,32n,9,6)) == 0 : U32}

law preferred_raw_budget_rejection:
  {V.valid(S.raws(9n),9n,6n) == False{} : Bool}

law preferred_raw_full_acceptance:
  {V.valid(S.raws(9n),9n,9n) == True{} : Bool}
