import Base
import ./selection.bend as S
import ./certificate.bend as C
import ./CONTRACT.bend as K
import ./selection_cli.bend as E
import ./LAWS.bend as Laws
import ./RECOVERY_PROOF.bend as RProof
import ./preference.bend as V
import ./PREFERENCE_CONTRACT.bend as P
import ./PREFERENCE_PROOF.bend as PProof

law add_zero:
  for +a: Nat
  {Nat.add(a, 0n) == a : Nat}

def add_zero(a):
  match a:
    case 0n:
      {==}
    case 1n+p:
      %add_zero(p) : {1n+Nat.add(p, 0n) == 1n+_ : Nat}
      {==}

law add_assoc:
  for +a: Nat
  for +b: Nat
  for +c: Nat
  {Nat.add(Nat.add(a, b), c) == Nat.add(a, Nat.add(b, c)) : Nat}

def add_assoc(a, b, c):
  match a:
    case 0n:
      {==}
    case 1n+p:
      %add_assoc(p, b, c) :
        {1n+Nat.add(Nat.add(p, b), c) == 1n+_ : Nat}
      {==}

law concat_mass:
  for +xs: S.Chunks
  for +ys: S.Chunks
  {S.mass(S.concat(xs, ys)) == Nat.add(S.mass(xs), S.mass(ys)) : Nat}

def concat_mass(xs, ys):
  match xs:
    case S.End{}:
      {==}
    case S.More{d, rest}:
      Equal.trans(Nat, S.mass(S.concat(S.More{d, rest}, ys)),
        Nat.add(S.width(d), Nat.add(S.mass(rest), S.mass(ys))),
        Nat.add(S.mass(S.More{d, rest}), S.mass(ys)),
        Equal.cong(Nat, Nat, n => Nat.add(S.width(d), n),
          S.mass(S.concat(rest, ys)), Nat.add(S.mass(rest), S.mass(ys)),
          concat_mass(rest, ys)),
        Equal.sym(Nat, Nat.add(Nat.add(S.width(d), S.mass(rest)), S.mass(ys)),
          Nat.add(S.width(d), Nat.add(S.mass(rest), S.mass(ys))),
          add_assoc(S.width(d), S.mass(rest), S.mass(ys))))

law add_cong:
  for -a: Nat
  for -b: Nat
  for -c: Nat
  for -d: Nat
  for e: {a == b : Nat}
  for f: {c == d : Nat}
  {Nat.add(a, c) == Nat.add(b, d) : Nat}

def add_cong(a, b, c, d, e, f):
  %e : {Nat.add(a, c) == Nat.add(_, d) : Nat}
  %f : {Nat.add(a, c) == Nat.add(a, _) : Nat}
  {==}

law stayed_mass:
  for +d: Nat
  for +xs: S.Chunks
  {S.mass(S.answer(S.refine_stayed(d, xs))) ==
    Nat.add(S.width(d), S.mass(xs)) : Nat}

def stayed_mass(d, xs):
  match d:
    case 0n:
      {==}
    case 1n+p:
      Equal.sym(Nat,
        Nat.add(Nat.add(S.width(p), S.width(p)), S.mass(xs)),
        Nat.add(S.width(p), Nat.add(S.width(p), S.mass(xs))),
        add_assoc(S.width(p), S.width(p), S.mass(xs)))

law tail_mass:
  for +d: Nat
  for +r: S.Refinement
  {S.mass(S.answer(S.refine_tail(d, r))) ==
    Nat.add(S.width(d), S.mass(S.answer(r))) : Nat}

def tail_mass(d, r):
  match r:
    case S.Split{xs}:
      {==}
    case S.Stayed{xs}:
      stayed_mass(d, xs)

def Laws.refine_conserves(xs):
  match xs:
    case S.End{}:
      {==}
    case S.More{d, rest}:
      Equal.trans(Nat, S.mass(S.answer(S.refine(S.More{d, rest}))),
        Nat.add(S.width(d), S.mass(S.answer(S.refine(rest)))),
        S.mass(S.More{d, rest}), tail_mass(d, S.refine(rest)),
        Equal.cong(Nat, Nat, n => Nat.add(S.width(d), n),
          S.mass(S.answer(S.refine(rest))), S.mass(rest),
          Laws.refine_conserves(rest)))

def Laws.fill_conserves(fuel, xs):
  match fuel:
    case 0n:
      {==}
    case 1n+p:
      Equal.trans(Nat, S.mass(S.fill(p, S.answer(S.refine(xs)))),
        S.mass(S.answer(S.refine(xs))), S.mass(xs),
        Laws.fill_conserves(p, S.answer(S.refine(xs))),
        Laws.refine_conserves(xs))

law branch_mass:
  for flag: Bool
  for -yes: Unit -> S.Chunks
  for -no: Unit -> S.Chunks
  for +target: Nat
  for y: {S.mass(yes(Unit{})) == target : Nat}
  for n: {S.mass(no(Unit{})) == target : Nat}
  {S.mass(S.branch(S.Chunks, flag, yes, no)) == target : Nat}

def branch_mass(flag, yes, no, target, y, n):
  match flag:
    case True{}:
      y
    case False{}:
      n

def Laws.threshold_conserves(depth, age, ratio):
  match depth:
    case 0n:
      {==}
    case 1n+p:
      branch_mass(S.split_here(1n+p, age, ratio),
        u => S.concat(S.expand(p, age, ratio),
          S.expand(p, U32.sub(age, S.width32(p)), ratio)),
        u => S.More{1n+p, S.End{}}, S.width(1n+p),
        Equal.trans(Nat,
          S.mass(S.concat(S.expand(p, age, ratio),
            S.expand(p, U32.sub(age, S.width32(p)), ratio))),
          Nat.add(S.mass(S.expand(p, age, ratio)),
            S.mass(S.expand(p, U32.sub(age, S.width32(p)), ratio))),
          S.width(1n+p),
          concat_mass(S.expand(p, age, ratio),
            S.expand(p, U32.sub(age, S.width32(p)), ratio)),
          add_cong(S.mass(S.expand(p, age, ratio)), S.width(p),
            S.mass(S.expand(p, U32.sub(age, S.width32(p)), ratio)), S.width(p),
            Laws.threshold_conserves(p, age, ratio),
            Laws.threshold_conserves(p, U32.sub(age, S.width32(p)), ratio))),
        add_zero(S.width(1n+p)))

def Laws.forest_threshold_conserves(xs, age, ratio):
  match xs:
    case S.End{}:
      {==}
    case S.More{d, rest}:
      Equal.trans(Nat,
        S.mass(S.concat(S.expand(d, age, ratio),
          S.expand_all(rest, U32.sub(age, S.width32(d)), ratio))),
        Nat.add(S.mass(S.expand(d, age, ratio)),
          S.mass(S.expand_all(rest, U32.sub(age, S.width32(d)), ratio))),
        S.mass(S.More{d, rest}),
        concat_mass(S.expand(d, age, ratio),
          S.expand_all(rest, U32.sub(age, S.width32(d)), ratio)),
        add_cong(S.mass(S.expand(d, age, ratio)), S.width(d),
          S.mass(S.expand_all(rest, U32.sub(age, S.width32(d)), ratio)), S.mass(rest),
          Laws.threshold_conserves(d, age, ratio),
          Laws.forest_threshold_conserves(rest, U32.sub(age, S.width32(d)), ratio)))

law finish_mass:
  for +q: U32
  for +total: U32
  for +budget: Nat
  for +xs: S.Chunks
  for target: Maybe<&2, Nat>
  {S.mass(S.finish_target(q, total, budget, xs, target)) == S.mass(xs) : Nat}

def finish_mass(q, total, budget, xs, target):
  match target:
    case None{}:
      {==}
    case Some{+d}:
      +coarse = S.expand_all(xs, total, S.Threshold{q, d, total})
      Equal.trans(Nat, S.mass(S.fill(Nat.sub(budget, S.length(coarse)), coarse)),
        S.mass(coarse), S.mass(xs),
        Laws.fill_conserves(Nat.sub(budget, S.length(coarse)), coarse),
        Laws.forest_threshold_conserves(xs, total, S.Threshold{q, d, total}))

def Laws.selection_conserves(root, fuel, budget, total, xs):
  +base = U32.from_nat(S.length(xs))
  +b = U32.from_nat(budget)
  branch_mass(U32.is_le(b, base), u => xs, u => (
    +q = S.find_q(root, fuel, 0, b, total, base, b)
    S.finish_target(q, total, budget, xs,
      S.find_fraction(root, root, total, q, base, b, None{}))),
    S.mass(xs), {==},
    (
      +q = S.find_q(root, fuel, 0, b, total, base, b)
      finish_mass(q, total, budget, xs,
        S.find_fraction(root, root, total, q, base, b, None{}))))

def Laws.raw_stays(n):
  match n:
    case 0n:
      {==}
    case 1n+p:
      %Laws.raw_stays(p) :
        {S.refine_tail(0n, S.refine(S.raws(p))) == S.refine_tail(0n, _) : S.Refinement}
      {==}

def Laws.recent_split(depth, raw_tail):
  %Laws.raw_stays(raw_tail) :
    {S.refine_tail(1n+depth, S.refine(S.raws(raw_tail))) ==
      S.refine_tail(1n+depth, _) : S.Refinement}
  {==}

# Boolean claims are converted to equality / inductive order witnesses.
def FalseDisc(flag: Bool) -> Data:
  match flag:
    case False{}:
      Unit
    case True{}:
      Empty

def false_true(e: {False{} == True{} : Bool}) -> Empty:
  %e : FalseDisc(_)
  Unit{}

def absurd(-A: Type, e: Empty) -> A:
  match e:

law eq_sound:
  for +a: Nat
  for +b: Nat
  for e: {Nat.is_eq(a, b) == True{} : Bool}
  {a == b : Nat}

def eq_sound(a, b, e):
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+p:
      absurd({0n == 1n+p : Nat}, false_true(e))
    case 1n+p 0n:
      absurd({1n+p == 0n : Nat}, false_true(e))
    case 1n+p 1n+q:
      Equal.cong(Nat, Nat, n => 1n+n, p, q, eq_sound(p, q, e))

law le_sound:
  for +a: Nat
  for +b: Nat
  for e: {Nat.is_le(a, b) == True{} : Bool}
  K.Le(a, b)

def le_sound(a, b, e):
  match a b:
    case 0n _:
      Unit{}
    case 1n+p 0n:
      false_true(e)
    case 1n+p 1n+q:
      le_sound(p, q, e)

law and_sound:
  for +a: Bool
  for +b: Bool
  for e: {Bool.and(a, b) == True{} : Bool}
  {a == True{} : Bool} & {b == True{} : Bool}

def and_sound(a, b, e):
  match a:
    case False{}:
      absurd({False{} == True{} : Bool} & {b == True{} : Bool}, false_true(e))
    case True{}:
      ({==}, e)

law guarded_sound:
  for +flag: Bool
  for -next: Unit -> Bool
  for e: {C.guarded(flag, next) == True{} : Bool}
  {flag == True{} : Bool} & {next(Unit{}) == True{} : Bool}

def guarded_sound(flag, next, e):
  match flag:
    case False{}:
      absurd({False{} == True{} : Bool} & {next(Unit{}) == True{} : Bool}, false_true(e))
    case True{}:
      ({==}, e)

# Helpers unpack only proof parameters, never computed expressions.
def partition_witness(+lo: Nat, +total: Nat, +previous: Nat, +d: Nat, -rest: S.Chunks,
  depth: {Nat.is_le(d, 31n) == True{} : Bool} & {Nat.is_le(d, previous) == True{} : Bool},
  body: {Nat.is_eq(Nat.mod(lo, K.width(d)), 0n) == True{} : Bool} &
    {Nat.is_le(Nat.add(lo, K.width(d)), total) == True{} : Bool},
  tail: {C.layout(rest, Nat.add(lo, K.width(d)), total, d) == True{} : Bool},
  ih: {C.layout(rest, Nat.add(lo, K.width(d)), total, d) == True{} : Bool} ->
    K.Partition(rest, Nat.add(lo, K.width(d)), total, d)) ->
  K.Partition(S.More{d, rest}, lo, total, previous):
  (bounded, ordered) = depth
  (aligned, contained) = body
  (le_sound(d, 31n, bounded),
    (le_sound(d, previous, ordered),
      (eq_sound(Nat.mod(lo, K.width(d)), 0n, aligned),
        (le_sound(Nat.add(lo, K.width(d)), total, contained), ih(tail)))))

def partition_body(+lo: Nat, +total: Nat, +previous: Nat, +d: Nat, -rest: S.Chunks,
  depth: {Nat.is_le(d, 31n) == True{} : Bool} & {Nat.is_le(d, previous) == True{} : Bool},
  body: {Bool.and(Nat.is_eq(Nat.mod(lo, K.width(d)), 0n),
    Nat.is_le(Nat.add(lo, K.width(d)), total)) == True{} : Bool} &
    {C.layout(rest, Nat.add(lo, K.width(d)), total, d) == True{} : Bool},
  ih: {C.layout(rest, Nat.add(lo, K.width(d)), total, d) == True{} : Bool} ->
    K.Partition(rest, Nat.add(lo, K.width(d)), total, d)) ->
  K.Partition(S.More{d, rest}, lo, total, previous):
  (condition, tail) = body
  partition_witness(lo, total, previous, d, rest, depth,
    and_sound(Nat.is_eq(Nat.mod(lo, K.width(d)), 0n),
      Nat.is_le(Nat.add(lo, K.width(d)), total), condition), tail, ih)

def partition_outer(+lo: Nat, +total: Nat, +previous: Nat, +d: Nat, -rest: S.Chunks,
  outer: {Bool.and(Nat.is_le(d, 31n), Nat.is_le(d, previous)) == True{} : Bool} &
    {C.guarded(Nat.is_eq(Nat.mod(lo, K.width(d)), 0n) &&
      Nat.is_le(Nat.add(lo, K.width(d)), total),
      u => C.layout(rest, Nat.add(lo, K.width(d)), total, d)) == True{} : Bool},
  ih: {C.layout(rest, Nat.add(lo, K.width(d)), total, d) == True{} : Bool} ->
    K.Partition(rest, Nat.add(lo, K.width(d)), total, d)) ->
  K.Partition(S.More{d, rest}, lo, total, previous):
  (depth, body) = outer
  partition_body(lo, total, previous, d, rest,
    and_sound(Nat.is_le(d, 31n), Nat.is_le(d, previous), depth),
    guarded_sound(Nat.is_eq(Nat.mod(lo, K.width(d)), 0n) &&
      Nat.is_le(Nat.add(lo, K.width(d)), total),
      u => C.layout(rest, Nat.add(lo, K.width(d)), total, d), body), ih)

def Laws.layout_sound(xs, lo, total, previous, checked):
  match xs:
    case S.End{}:
      eq_sound(lo, total, checked)
    case S.More{d, rest}:
      partition_outer(lo, total, previous, d, rest,
        guarded_sound(Nat.is_le(d, 31n) && Nat.is_le(d, previous), u => (
          +w = K.width(d)
          +end = Nat.add(lo, w)
          C.guarded(Nat.is_eq(Nat.mod(lo, w), 0n) && Nat.is_le(end, total),
            u => C.layout(rest, end, total, d))), checked),
        e => Laws.layout_sound(rest, Nat.add(lo, K.width(d)), total, d, e))

def valid_witness(+xs: S.Chunks, +total: Nat, +budget: Nat,
  checks: {C.layout(xs, 0n, total, 31n) == True{} : Bool} &
    {Nat.is_eq(K.length(xs), K.expected(total, budget)) == True{} : Bool}) ->
  K.Contract(xs, total, budget):
  (shape, count) = checks
  (Laws.layout_sound(xs, 0n, total, 31n, shape),
    eq_sound(K.length(xs), K.expected(total, budget), count))

law gate_contract:
  for +flag: Bool
  for +xs: S.Chunks
  for +total: Nat
  for +budget: Nat
  for e: {flag == C.valid(xs, total, budget) : Bool}
  K.AllCertified(C.gate(xs, flag), total, budget)

def gate_contract(flag, xs, total, budget, e):
  match flag:
    case False{}:
      Unit{}
    case True{}:
      valid_witness(xs, total, budget,
        and_sound(C.layout(xs, 0n, total, 31n),
          Nat.is_eq(K.length(xs), K.expected(total, budget)),
          Equal.sym(Bool, True{}, C.valid(xs, total, budget), e)))

def Laws.certificate_sound(xs, total, budget):
  gate_contract(C.valid(xs, total, budget), xs, total, budget, {==})

def Laws.accepted_contract(xs, total, budget, accepted):
  %accepted : K.AllCertified(_, total, budget)
  Laws.certificate_sound(xs, total, budget)

law branch_contract:
  for flag: Bool
  for -yes: Unit -> Maybe<&2, S.Chunks>
  for -no: Unit -> Maybe<&2, S.Chunks>
  for +total: Nat
  for +budget: Nat
  for y: K.AllCertified(yes(Unit{}), total, budget)
  for n: K.AllCertified(no(Unit{}), total, budget)
  K.AllCertified(S.branch(Maybe<&2, S.Chunks>, flag, yes, no), total, budget)

def branch_contract(flag, yes, no, total, budget, y, n):
  match flag:
    case True{}:
      y
    case False{}:
      n

law recovery_contract_u32:
  for +total: U32
  for +budget: U32
  K.Contract(E.recover(total,budget),U32.to_nat(total),U32.to_nat(budget))

def recovery_contract_u32(total,budget):
  match total:
    case U32{word}:
      RProof.recovery_contract(word,U32.to_nat(budget))

law checked_fast_or_slow_sound:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  for witness: K.AllCertified(result,U32.to_nat(total),U32.to_nat(budget))
  K.AllCertified(E.checked_fast_or_slow(result,total,budget),U32.to_nat(total),U32.to_nat(budget))

def checked_fast_or_slow_sound(result,total,budget,witness):
  match result:
    case Some{xs}:
      witness
    case None{}:
      Laws.certificate_sound(E.recover(total,budget),U32.to_nat(total),U32.to_nat(budget))

law checked_or_recover_sound:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  for witness: K.AllCertified(result,U32.to_nat(total),U32.to_nat(budget))
  K.AllCertified(E.checked_or_recover(result,total,budget),U32.to_nat(total),U32.to_nat(budget))

def checked_or_recover_sound(result,total,budget,witness):
  match result:
    case Some{xs}:
      branch_contract(V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))),
        u=>Some{xs},
        u=>E.checked_fast_or_slow(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget),
        U32.to_nat(total),U32.to_nat(budget),witness,
        checked_fast_or_slow_sound(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget,
          Laws.certificate_sound(E.recover_fast(total,budget),
            U32.to_nat(total),U32.to_nat(budget))))
    case None{}:
      checked_fast_or_slow_sound(C.certify(E.recover_fast(total,budget),
        U32.to_nat(total),U32.to_nat(budget)),total,budget,
        Laws.certificate_sound(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)))

def Laws.executable_sound(fuel, root, search, total, budget):
  match fuel:
    case 0n:
      Unit{}
    case 1n+p:
      branch_contract(U32.is_gt(budget, 0), u => (
        +result = S.branch(S.Chunks, U32.is_ge(budget, total),
          u => S.raws(U32.to_nat(total)),
          u => S.choose(root, search, U32.to_nat(budget), total, E.seed(root, total)))
        E.checked_or_recover(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget)),
        u => E.entry(p, root, search, total, budget), U32.to_nat(total), U32.to_nat(budget),
        (
          +result = S.branch(S.Chunks, U32.is_ge(budget, total),
            u => S.raws(U32.to_nat(total)),
            u => S.choose(root, search, U32.to_nat(budget), total, E.seed(root, total)))
          checked_or_recover_sound(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),
            total,budget,Laws.certificate_sound(result,U32.to_nat(total),U32.to_nat(budget)))),
        Laws.executable_sound(p, root, search, total, budget))

def Laws.flag_acceptance(xs, total, budget, valid):
  %Equal.sym(Bool, C.valid(xs, total, budget), True{}, valid) :
    {C.gate(xs, _) == Some{xs} : Maybe<&2, S.Chunks>}
  {==}

def Laws.empty_entry_success(root, search):
  {==}

def Laws.unit_entry_success(root, search):
  {==}

def Laws.compressed_entry_success():
  {==}

law eq_refl:
  for +n: Nat
  {Nat.is_eq(n, n) == True{} : Bool}

def eq_refl(n):
  match n:
    case 0n:
      {==}
    case 1n+p:
      eq_refl(p)

law eq_complete:
  for +a: Nat
  for +b: Nat
  for e: {a == b : Nat}
  {Nat.is_eq(a, b) == True{} : Bool}

def eq_complete(a, b, e):
  %e : {Nat.is_eq(a, _) == True{} : Bool}
  eq_refl(a)

law le_complete:
  for +a: Nat
  for +b: Nat
  for witness: K.Le(a, b)
  {Nat.is_le(a, b) == True{} : Bool}

def le_complete(a, b, witness):
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+q:
      {==}
    case 1n+p 0n:
      match witness:
    case 1n+p 1n+q:
      le_complete(p, q, witness)

law and_complete:
  for +a: Bool
  for +b: Bool
  for left: {a == True{} : Bool}
  for right: {b == True{} : Bool}
  {Bool.and(a, b) == True{} : Bool}

def and_complete(a, b, left, right):
  %Equal.sym(Bool, a, True{}, left) : {Bool.and(_, b) == True{} : Bool}
  right

law guarded_complete:
  for +flag: Bool
  for -next: Unit -> Bool
  for yes: {flag == True{} : Bool}
  for done: {next(Unit{}) == True{} : Bool}
  {C.guarded(flag, next) == True{} : Bool}

def guarded_complete(flag, next, yes, done):
  %Equal.sym(Bool, flag, True{}, yes) : {C.guarded(_, next) == True{} : Bool}
  done

def Laws.layout_complete(xs, lo, total, previous, witness):
  match xs:
    case S.End{}:
      eq_complete(lo, total, witness)
    case S.More{+d, +rest}:
      (bounded, body) = witness
      (ordered, body) = body
      (aligned, body) = body
      (contained, tail) = body
      guarded_complete(Nat.is_le(d, 31n) && Nat.is_le(d, previous), u => (
        +w = K.width(d)
        +end = Nat.add(lo, w)
        C.guarded(Nat.is_eq(Nat.mod(lo, w), 0n) && Nat.is_le(end, total),
          u => C.layout(rest, end, total, d))),
        and_complete(Nat.is_le(d, 31n), Nat.is_le(d, previous),
          le_complete(d, 31n, bounded), le_complete(d, previous, ordered)),
        guarded_complete(Nat.is_eq(Nat.mod(lo, K.width(d)), 0n) &&
          Nat.is_le(Nat.add(lo, K.width(d)), total),
          u => C.layout(rest, Nat.add(lo, K.width(d)), total, d),
          and_complete(Nat.is_eq(Nat.mod(lo, K.width(d)), 0n),
            Nat.is_le(Nat.add(lo, K.width(d)), total),
            eq_complete(Nat.mod(lo, K.width(d)), 0n, aligned),
            le_complete(Nat.add(lo, K.width(d)), total, contained)),
          Laws.layout_complete(rest, Nat.add(lo, K.width(d)), total, d, tail)))

def Laws.certificate_completeness(xs, total, budget, witness):
  (shape, count) = witness
  Laws.flag_acceptance(xs, total, budget,
    and_complete(C.layout(xs, 0n, total, 31n),
      Nat.is_eq(K.length(xs), K.expected(total, budget)),
      Laws.layout_complete(xs, 0n, total, 31n, shape),
      eq_complete(K.length(xs), K.expected(total, budget), count)))

law checked_fast_or_slow_success:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  for witness: K.AllCertified(result,U32.to_nat(total),U32.to_nat(budget))
  K.Success(E.checked_fast_or_slow(result,total,budget),
    U32.to_nat(total),U32.to_nat(budget))

def checked_fast_or_slow_success(result,total,budget,witness):
  match result:
    case Some{xs}:
      witness
    case None{}:
      +r=E.recover(total,budget)
      +t=U32.to_nat(total)
      +b=U32.to_nat(budget)
      %Equal.sym(Maybe<&2,S.Chunks>,C.certify(r,t,b),Some{r},
        Laws.certificate_completeness(r,t,b,recovery_contract_u32(total,budget))) :
        K.Success(_,t,b)
      recovery_contract_u32(total,budget)

law checked_or_recover_success:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  for witness: K.AllCertified(result,U32.to_nat(total),U32.to_nat(budget))
  K.Success(E.checked_or_recover(result,total,budget),
    U32.to_nat(total),U32.to_nat(budget))

law branch_success:
  for flag: Bool
  for -yes: Unit -> Maybe<&2,S.Chunks>
  for -no: Unit -> Maybe<&2,S.Chunks>
  for +total: Nat
  for +budget: Nat
  for y: K.Success(yes(Unit{}),total,budget)
  for n: K.Success(no(Unit{}),total,budget)
  K.Success(S.branch(Maybe<&2,S.Chunks>,flag,yes,no),total,budget)

def branch_success(flag,yes,no,total,budget,y,n):
  match flag:
    case True{}:
      y
    case False{}:
      n

def checked_or_recover_success(result,total,budget,witness):
  match result:
    case Some{xs}:
      branch_success(V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))),
        u=>Some{xs},
        u=>E.checked_fast_or_slow(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget),
        U32.to_nat(total),U32.to_nat(budget),witness,
        checked_fast_or_slow_success(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget,
          Laws.certificate_sound(E.recover_fast(total,budget),
            U32.to_nat(total),U32.to_nat(budget))))
    case None{}:
      checked_fast_or_slow_success(C.certify(E.recover_fast(total,budget),
        U32.to_nat(total),U32.to_nat(budget)),total,budget,
        Laws.certificate_sound(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)))

def Laws.supported_entry_success(root,search,total,budget,positive):
  +result=S.branch(S.Chunks,U32.is_ge(budget,total),
    u => S.raws(U32.to_nat(total)),
    u => S.choose(root,search,U32.to_nat(budget),total,E.seed(root,total)))
  %Equal.sym(Bool,U32.is_gt(budget,0),True{},positive) :
    K.Success(S.branch(Maybe<&2,S.Chunks>,_,
      u => E.checked_or_recover(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget),
      u => E.entry(0n,root,search,total,budget)),
      U32.to_nat(total),U32.to_nat(budget))
  checked_or_recover_success(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),
    total,budget,Laws.certificate_sound(result,U32.to_nat(total),U32.to_nat(budget)))

law checked_fast_status_domain:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  {U32.is_le(Pair.fst(U32,Maybe<&2,S.Chunks>,E.checked_fast_status(result,total,budget)),2) == True{} : Bool}

def checked_fast_status_domain(result,total,budget):
  match result:
    case Some{xs}:
      {==}
    case None{}:
      {==}

law branch_status_domain:
  for flag: Bool
  for -yes_pair: Unit -> U32 & Maybe<&2,S.Chunks>
  for -no_pair: Unit -> U32 & Maybe<&2,S.Chunks>
  for y: {U32.is_le(Pair.fst(U32,Maybe<&2,S.Chunks>,yes_pair(Unit{})),2) == True{} : Bool}
  for n: {U32.is_le(Pair.fst(U32,Maybe<&2,S.Chunks>,no_pair(Unit{})),2) == True{} : Bool}
  {U32.is_le(Pair.fst(U32,Maybe<&2,S.Chunks>,S.branch(U32 & Maybe<&2,S.Chunks>,flag,yes_pair,no_pair)),2) == True{} : Bool}

def branch_status_domain(flag,yes_pair,no_pair,y,n):
  match flag:
    case True{}:
      y
    case False{}:
      n

law checked_status_domain:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  {U32.is_le(Pair.fst(U32,Maybe<&2,S.Chunks>,E.checked_status(result,total,budget)),2) == True{} : Bool}

def checked_status_domain(result,total,budget):
  match result:
    case Some{xs}:
      branch_status_domain(V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))),
        u=>(0,Some{xs}),
        u=>E.checked_fast_status(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget),
        {==},
        checked_fast_status_domain(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget))
    case None{}:
      checked_fast_status_domain(C.certify(E.recover_fast(total,budget),
        U32.to_nat(total),U32.to_nat(budget)),total,budget)

def Laws.supported_status_domain(root,search,total,budget,positive):
  +result=S.branch(S.Chunks,U32.is_ge(budget,total),
    u=>S.raws(U32.to_nat(total)),
    u=>S.choose(root,search,U32.to_nat(budget),total,E.seed(root,total)))
  %Equal.sym(Bool,U32.is_gt(budget,0),True{},positive) :
    {U32.is_le(Pair.fst(U32,Maybe<&2,S.Chunks>,S.branch(U32 & Maybe<&2,S.Chunks>,_,
      u=>E.checked_status(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget),
      u=>E.entry_status(0n,root,search,total,budget))),2) == True{} : Bool}
  checked_status_domain(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget)

law checked_fast_status_projection:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  {Pair.snd(U32,Maybe<&2,S.Chunks>,E.checked_fast_status(result,total,budget)) ==
    E.checked_fast_or_slow(result,total,budget) : Maybe<&2,S.Chunks>}

def checked_fast_status_projection(result,total,budget):
  match result:
    case Some{xs}:
      {==}
    case None{}:
      {==}

law branch_status_projection:
  for flag: Bool
  for -yes_pair: Unit -> U32 & Maybe<&2,S.Chunks>
  for -no_pair: Unit -> U32 & Maybe<&2,S.Chunks>
  for -yes_maybe: Unit -> Maybe<&2,S.Chunks>
  for -no_maybe: Unit -> Maybe<&2,S.Chunks>
  for y: {Pair.snd(U32,Maybe<&2,S.Chunks>,yes_pair(Unit{})) == yes_maybe(Unit{}) : Maybe<&2,S.Chunks>}
  for n: {Pair.snd(U32,Maybe<&2,S.Chunks>,no_pair(Unit{})) == no_maybe(Unit{}) : Maybe<&2,S.Chunks>}
  {Pair.snd(U32,Maybe<&2,S.Chunks>,S.branch(U32 & Maybe<&2,S.Chunks>,flag,yes_pair,no_pair)) ==
    S.branch(Maybe<&2,S.Chunks>,flag,yes_maybe,no_maybe) : Maybe<&2,S.Chunks>}

def branch_status_projection(flag,yes_pair,no_pair,yes_maybe,no_maybe,y,n):
  match flag:
    case True{}:
      y
    case False{}:
      n

law checked_status_projection:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  {Pair.snd(U32,Maybe<&2,S.Chunks>,E.checked_status(result,total,budget)) ==
    E.checked_or_recover(result,total,budget) : Maybe<&2,S.Chunks>}

def checked_status_projection(result,total,budget):
  match result:
    case Some{xs}:
      branch_status_projection(V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))),
        u=>(0,Some{xs}),
        u=>E.checked_fast_status(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget),
        u=>Some{xs},
        u=>E.checked_fast_or_slow(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget),
        {==},
        checked_fast_status_projection(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget))
    case None{}:
      checked_fast_status_projection(C.certify(E.recover_fast(total,budget),
        U32.to_nat(total),U32.to_nat(budget)),total,budget)

def Laws.status_projection(fuel,root,search,total,budget):
  match fuel:
    case 0n:
      {==}
    case 1n+p:
      +result=S.branch(S.Chunks,U32.is_ge(budget,total),
        u => S.raws(U32.to_nat(total)),
        u => S.choose(root,search,U32.to_nat(budget),total,E.seed(root,total)))
      branch_status_projection(U32.is_gt(budget,0),
        u => E.checked_status(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget),
        u => E.entry_status(p,root,search,total,budget),
        u => E.checked_or_recover(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget),
        u => E.entry(p,root,search,total,budget),
        checked_status_projection(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget),
        Laws.status_projection(p,root,search,total,budget))

def Laws.preferred_sound(xs,total,target,checked):
  PProof.preferred_sound(xs,U32.to_nat(total),target,checked)

def Laws.preferred_complete(xs,total,target,witness):
  PProof.preferred_complete(xs,U32.to_nat(total),target,witness)

law marked_fast_status:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  P.Marked(E.checked_fast_status(result,total,budget),
    U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget)))

def marked_fast_status(result,total,budget):
  match result:
    case Some{xs}:
      Unit{}
    case None{}:
      Unit{}

law marked_choice:
  for flag: Bool
  for +xs: S.Chunks
  for +total: U32
  for +budget: U32
  for e: {flag == V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))) : Bool}
  for fallback: P.Marked(E.checked_fast_status(C.certify(E.recover_fast(total,budget),
      U32.to_nat(total),U32.to_nat(budget)),total,budget),
      U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget)))
  P.Marked(S.branch(U32 & Maybe<&2,S.Chunks>,flag,
      u=>(0,Some{xs}),
      u=>E.checked_fast_status(C.certify(E.recover_fast(total,budget),
        U32.to_nat(total),U32.to_nat(budget)),total,budget)),
      U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget)))

def marked_choice(flag,xs,total,budget,e,fallback):
  match flag:
    case True{}:
      PProof.preferred_sound(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget)),
        Equal.sym(Bool,True{},V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))),e))
    case False{}:
      fallback

law checked_status_marked:
  for result: Maybe<&2,S.Chunks>
  for +total: U32
  for +budget: U32
  P.Marked(E.checked_status(result,total,budget),
    U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget)))

def checked_status_marked(result,total,budget):
  match result:
    case Some{+xs}:
      marked_choice(V.valid(xs,U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget))),
        xs,total,budget,{==},
        marked_fast_status(C.certify(E.recover_fast(total,budget),
          U32.to_nat(total),U32.to_nat(budget)),total,budget))
    case None{}:
      marked_fast_status(C.certify(E.recover_fast(total,budget),
        U32.to_nat(total),U32.to_nat(budget)),total,budget)

def Laws.status_preferred(root,search,total,budget,positive):
  +result=S.branch(S.Chunks,U32.is_ge(budget,total),
    u=>S.raws(U32.to_nat(total)),
    u=>S.choose(root,search,U32.to_nat(budget),total,E.seed(root,total)))
  %Equal.sym(Bool,U32.is_gt(budget,0),True{},positive) :
    P.Marked(S.branch(U32 & Maybe<&2,S.Chunks>,_,
      u=>E.checked_status(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget),
      u=>E.entry_status(0n,root,search,total,budget)),
      U32.to_nat(total),K.expected(U32.to_nat(total),U32.to_nat(budget)))
  checked_status_marked(C.certify(result,U32.to_nat(total),U32.to_nat(budget)),total,budget)

def Laws.preferred_entry_example():
  {==}

def Laws.preferred_raw_budget_rejection():
  {==}

def Laws.preferred_raw_full_acceptance():
  {==}
