import Base
import ./CONTRACT.bend as K
import ./selection.bend as S
import ./RECOVERY.bend as B

def double_remainder(qr: Nat & Nat) -> Nat & Nat:
  (q, r) = qr
  (q, Nat.double(r))

law double_go:
  for +n: Nat
  for +m: Nat
  for +d: Nat
  for +r: Nat
  {Nat.divmod.go(Nat.double(n), 1n+Nat.double(m), d, Nat.double(r)) ==
    double_remainder(Nat.divmod.go(n, m, d, r)) : Nat & Nat}

def double_go(n, m, d, r):
  match n m:
    case 0n _:
      {==}
    case 1n+p 0n:
      double_go(p, r, 1n+d, 0n)
    case 1n+p 1n+q:
      double_go(p, q, d, 1n+r)

law pair_double:
  for qr: Nat & Nat
  {Nat.mod.fin(double_remainder(qr)) == Nat.double(Nat.mod.fin(qr)) : Nat}

def pair_double(qr):
  (q, r) = qr
  {==}

law modulo_double:
  for +a: Nat
  for +b: Nat
  {Nat.mod(Nat.double(a), Nat.double(b)) == Nat.double(Nat.mod(a, b)) : Nat}

def modulo_double(a, b):
  match b:
    case 0n:
      {==}
    case 1n+p:
      Equal.trans(Nat,
        Nat.mod.fin(Nat.divmod.go(Nat.double(a), 1n+Nat.double(p), 0n, 0n)),
        Nat.mod.fin(double_remainder(Nat.divmod.go(a, p, 0n, 0n))),
        Nat.double(Nat.mod.fin(Nat.divmod.go(a, p, 0n, 0n))),
        Equal.cong(Nat & Nat, Nat, qr => Nat.mod.fin(qr),
          Nat.divmod.go(Nat.double(a), 1n+Nat.double(p), 0n, 0n),
          double_remainder(Nat.divmod.go(a, p, 0n, 0n)), double_go(a, p, 0n, 0n)),
        pair_double(Nat.divmod.go(a, p, 0n, 0n)))


law add_succ_right:
  for +a: Nat
  for +b: Nat
  {Nat.add(a, 1n+b) == 1n+Nat.add(a, b) : Nat}

def add_succ_right(a, b):
  match a:
    case 0n:
      {==}
    case 1n+p:
      Equal.cong(Nat, Nat, x => 1n+x,
        Nat.add(p, 1n+b), 1n+Nat.add(p, b), add_succ_right(p, b))

law add_self_double:
  for +a: Nat
  {Nat.add(a, a) == Nat.double(a) : Nat}

def add_self_double(a):
  match a:
    case 0n:
      {==}
    case 1n+p:
      Equal.trans(Nat, 1n+Nat.add(p, 1n+p), 2n+Nat.add(p, p), 2n+Nat.double(p),
        Equal.cong(Nat, Nat, x => 1n+x, Nat.add(p, 1n+p), 1n+Nat.add(p, p), add_succ_right(p, p)),
        Equal.cong(Nat, Nat, x => 2n+x, Nat.add(p, p), Nat.double(p), add_self_double(p)))

law double_add:
  for +a: Nat
  for +b: Nat
  {Nat.double(Nat.add(a, b)) == Nat.add(Nat.double(a), Nat.double(b)) : Nat}

def double_add(a, b):
  match a:
    case 0n:
      {==}
    case 1n+p:
      Equal.cong(Nat, Nat, x => 2n+x,
        Nat.double(Nat.add(p, b)), Nat.add(Nat.double(p), Nat.double(b)), double_add(p, b))

law modulo_one_go:
  for +n: Nat
  for +d: Nat
  {Nat.mod.fin(Nat.divmod.go(n, 0n, d, 0n)) == 0n : Nat}

def modulo_one_go(n, d):
  match n:
    case 0n:
      {==}
    case 1n+p:
      modulo_one_go(p, 1n+d)

law modulo_one:
  for +n: Nat
  {Nat.mod(n, 1n) == 0n : Nat}

def modulo_one(n):
  modulo_one_go(n, 0n)

law le_trans:
  for a: Nat
  for b: Nat
  for c: Nat
  for ab: K.Le(a, b)
  for bc: K.Le(b, c)
  K.Le(a, c)

def le_trans(a, b, c, ab, bc):
  match a b c:
    case 0n _ _:
      Unit{}
    case 1n+p 0n _:
      match ab:
    case 1n+p 1n+q 0n:
      match bc:
    case 1n+p 1n+q 1n+r:
      le_trans(p, q, r, ab, bc)

law le_double:
  for a: Nat
  for b: Nat
  for ab: K.Le(a, b)
  K.Le(Nat.double(a), Nat.double(b))

def le_double(a, b, ab):
  match a b:
    case 0n _:
      Unit{}
    case 1n+p 0n:
      match ab:
    case 1n+p 1n+q:
      le_double(p, q, ab)

law width_double:
  for +d: Nat
  {K.width(1n+d) == Nat.double(K.width(d)) : Nat}

def width_double(d):
  add_self_double(K.width(d))

law extent_double:
  for +lo: Nat
  for +d: Nat
  {Nat.add(Nat.double(lo), K.width(1n+d)) == Nat.double(Nat.add(lo, K.width(d))) : Nat}

def extent_double(lo, d):
  Equal.trans(Nat,
    Nat.add(Nat.double(lo), K.width(1n+d)), Nat.add(Nat.double(lo), Nat.double(K.width(d))),
    Nat.double(Nat.add(lo, K.width(d))),
    Equal.cong(Nat, Nat, x => Nat.add(Nat.double(lo), x), K.width(1n+d), Nat.double(K.width(d)), width_double(d)),
    Equal.sym(Nat, Nat.double(Nat.add(lo, K.width(d))), Nat.add(Nat.double(lo), Nat.double(K.width(d))), double_add(lo, K.width(d))))

law aligned_double:
  for +lo: Nat
  for +d: Nat
  for aligned: {Nat.mod(lo, K.width(d)) == 0n : Nat}
  {Nat.mod(Nat.double(lo), K.width(1n+d)) == 0n : Nat}

def aligned_double(lo, d, aligned):
  Equal.trans(Nat,
    Nat.mod(Nat.double(lo), K.width(1n+d)), Nat.mod(Nat.double(lo), Nat.double(K.width(d))), 0n,
    Equal.cong(Nat, Nat, x => Nat.mod(Nat.double(lo), x), K.width(1n+d), Nat.double(K.width(d)), width_double(d)),
    Equal.trans(Nat,
      Nat.mod(Nat.double(lo), Nat.double(K.width(d))), Nat.double(Nat.mod(lo, K.width(d))), 0n,
      modulo_double(lo, K.width(d)),
      Equal.cong(Nat, Nat, x => Nat.double(x), Nat.mod(lo, K.width(d)), 0n, aligned)))

law scaled_partition:
  for +xs: S.Chunks
  for +lo: Nat
  for +total: Nat
  for +previous: Nat
  for bound: K.Le(previous, 30n)
  for partition: K.Partition(xs, lo, total, previous)
  K.Partition(B.scale(xs), Nat.double(lo), Nat.double(total), 1n+previous)

def scaled_partition(xs, lo, total, previous, bound, partition):
  match xs:
    case S.End{}:
      Equal.cong(Nat, Nat, x => Nat.double(x), lo, total, partition)
    case S.More{d, rest}:
      (cap, (order, (aligned, (extent, tail)))) = partition
      +ord = order
      +small = le_trans(d, previous, 30n, ord, bound)
      %Equal.sym(Nat, Nat.add(Nat.double(lo), K.width(1n+d)), Nat.double(Nat.add(lo, K.width(d))), extent_double(lo, d)) :
        (K.Le(d, 30n) & (K.Le(d, previous) &
          ({Nat.mod(Nat.double(lo), K.width(1n+d)) == 0n : Nat} &
            (K.Le(_, Nat.double(total)) & K.Partition(B.scale(rest), _, Nat.double(total), 1n+d)))))
      (small, (ord, (aligned_double(lo, d, aligned),
        (le_double(Nat.add(lo, K.width(d)), total, extent),
          scaled_partition(rest, Nat.add(lo, K.width(d)), total, d, small, tail)))))

law le_refl:
  for a: Nat
  K.Le(a, a)

def le_refl(a):
  match a:
    case 0n:
      Unit{}
    case 1n+p:
      le_refl(p)

law le_right_succ:
  for a: Nat
  for b: Nat
  for ab: K.Le(a, b)
  K.Le(a, 1n+b)

def le_right_succ(a, b, ab):
  match a b:
    case 0n _:
      Unit{}
    case 1n+p 0n:
      match ab:
    case 1n+p 1n+q:
      le_right_succ(p, q, ab)

law add_one:
  for +a: Nat
  {Nat.add(a, 1n) == 1n+a : Nat}

def add_one(a):
  match a:
    case 0n:
      {==}
    case 1n+p:
      Equal.cong(Nat, Nat, x => 1n+x, Nat.add(p, 1n), 1n+p, add_one(p))

law append_raw_partition:
  for +xs: S.Chunks
  for +lo: Nat
  for +total: Nat
  for +previous: Nat
  for partition: K.Partition(xs, lo, total, previous)
  K.Partition(B.append_raw(xs), lo, 1n+total, previous)

def append_raw_partition(xs, lo, total, previous, partition):
  match xs:
    case S.End{}:
      %partition : K.Partition(S.More{0n, S.End{}}, lo, 1n+_, previous)
      %add_one(lo) : K.Partition(S.More{0n, S.End{}}, lo, _, previous)
      (Unit{}, (Unit{}, (modulo_one(lo), (le_refl(Nat.add(lo, 1n)), {==}))))
    case S.More{d, rest}:
      (cap, (order, (aligned, (extent, tail)))) = partition
      (cap, (order, (aligned,
        (le_right_succ(Nat.add(lo, K.width(d)), total, extent),
          append_raw_partition(rest, Nat.add(lo, K.width(d)), total, d, tail)))))

def odd_remainder(qr: Nat & Nat) -> Nat & Nat:
  (q, r) = qr
  (q, 1n+Nat.double(r))

law odd_double_go:
  for +n: Nat
  for +m: Nat
  for +d: Nat
  for +r: Nat
  {Nat.divmod.go(Nat.double(n), Nat.double(m), d, 1n+Nat.double(r)) ==
    odd_remainder(Nat.divmod.go(n, m, d, r)) : Nat & Nat}

def odd_double_go(n, m, d, r):
  match n m:
    case 0n _:
      {==}
    case 1n+p 0n:
      odd_double_go(p, r, 1n+d, 0n)
    case 1n+p 1n+q:
      odd_double_go(p, q, d, 1n+r)

law pair_odd:
  for qr: Nat & Nat
  {Nat.mod.fin(odd_remainder(qr)) == 1n+Nat.double(Nat.mod.fin(qr)) : Nat}

def pair_odd(qr):
  (q, r) = qr
  {==}

law modulo_odd:
  for +a: Nat
  for +b: Nat
  {Nat.mod(1n+Nat.double(a), Nat.double(1n+b)) == 1n+Nat.double(Nat.mod(a, 1n+b)) : Nat}

def modulo_odd(a, b):
  Equal.trans(Nat,
    Nat.mod.fin(Nat.divmod.go(Nat.double(a), Nat.double(b), 0n, 1n)),
    Nat.mod.fin(odd_remainder(Nat.divmod.go(a, b, 0n, 0n))),
    1n+Nat.double(Nat.mod.fin(Nat.divmod.go(a, b, 0n, 0n))),
    Equal.cong(Nat & Nat, Nat, qr => Nat.mod.fin(qr),
      Nat.divmod.go(Nat.double(a), Nat.double(b), 0n, 1n),
      odd_remainder(Nat.divmod.go(a, b, 0n, 0n)), odd_double_go(a, b, 0n, 0n)),
    pair_odd(Nat.divmod.go(a, b, 0n, 0n)))

def parity_step(+p: Nat, +q: Nat,
  shape: Or({p == Nat.double(q) : Nat}, {p == 1n+Nat.double(q) : Nat})) ->
  Exists(Nat, r => Or({2n+p == Nat.double(r) : Nat}, {2n+p == 1n+Nat.double(r) : Nat})):
  match shape:
    case Inl{even}:
      (1n+q, Inl{Equal.cong(Nat, Nat, x => 2n+x, p, Nat.double(q), even)})
    case Inr{odd}:
      (1n+q, Inr{Equal.cong(Nat, Nat, x => 2n+x, p, 1n+Nat.double(q), odd)})

def parity_lift(+p: Nat, qr: Exists(Nat, q => Or({p == Nat.double(q) : Nat}, {p == 1n+Nat.double(q) : Nat}))) ->
  Exists(Nat, r => Or({2n+p == Nat.double(r) : Nat}, {2n+p == 1n+Nat.double(r) : Nat})):
  (q, shape) = qr
  parity_step(p, q, shape)

law parity:
  for +n: Nat
  exs q: Nat
  Or({n == Nat.double(q) : Nat}, {n == 1n+Nat.double(q) : Nat})

def parity(n):
  match n:
    case 0n:
      (0n, Inl{{==}})
    case 1n:
      (0n, Inr{{==}})
    case 2n+p:
      parity_lift(p, parity(p))

def positive_width_step(+p: Nat, qr: Exists(Nat, q => {K.width(p) == 1n+q : Nat})) ->
  Exists(Nat, r => {K.width(1n+p) == 1n+r : Nat}):
  (q, e) = qr
  (1n+Nat.double(q),
    Equal.trans(Nat, K.width(1n+p), Nat.double(K.width(p)), 2n+Nat.double(q),
      width_double(p), Equal.cong(Nat, Nat, x => Nat.double(x), K.width(p), 1n+q, e)))

law positive_width:
  for +d: Nat
  exs p: Nat
  {K.width(d) == 1n+p : Nat}

def positive_width(d):
  match d:
    case 0n:
      (0n, {==})
    case 1n+p:
      positive_width_step(p, positive_width(p))

def ZeroDisc(n: Nat) -> Data:
  match n:
    case 0n:
      Empty
    case 1n+p:
      Unit

def succ_zero(n: Nat, e: {1n+n == 0n : Nat}) -> Empty:
  %e : ZeroDisc(_)
  Unit{}

def absurd(-A: Type, e: Empty) -> A:
  match e:

law double_zero:
  for +n: Nat
  for e: {Nat.double(n) == 0n : Nat}
  {n == 0n : Nat}

def double_zero(n, e):
  match n:
    case 0n:
      {==}
    case 1n+p:
      absurd({1n+p == 0n : Nat}, succ_zero(1n+Nat.double(p), e))

law even_aligned_reduce:
  for +lo: Nat
  for +d: Nat
  for aligned: {Nat.mod(Nat.double(lo), K.width(1n+d)) == 0n : Nat}
  {Nat.mod(lo, K.width(d)) == 0n : Nat}

def even_aligned_reduce(lo, d, aligned):
  double_zero(Nat.mod(lo, K.width(d)),
    Equal.trans(Nat, Nat.double(Nat.mod(lo, K.width(d))), Nat.mod(Nat.double(lo), Nat.double(K.width(d))), 0n,
      Equal.sym(Nat, Nat.mod(Nat.double(lo), Nat.double(K.width(d))), Nat.double(Nat.mod(lo, K.width(d))), modulo_double(lo, K.width(d))),
      Equal.trans(Nat, Nat.mod(Nat.double(lo), Nat.double(K.width(d))), Nat.mod(Nat.double(lo), K.width(1n+d)), 0n,
        Equal.cong(Nat, Nat, w => Nat.mod(Nat.double(lo), w), Nat.double(K.width(d)), K.width(1n+d),
          Equal.sym(Nat, K.width(1n+d), Nat.double(K.width(d)), width_double(d))), aligned)))

def odd_unaligned_width(+lo: Nat, +d: Nat,
  aligned: {Nat.mod(1n+Nat.double(lo), K.width(1n+d)) == 0n : Nat},
  qr: Exists(Nat, q => {K.width(d) == 1n+q : Nat})) -> Empty:
  (q, w) = qr
  +h = q
  eqw = Equal.trans(Nat, K.width(1n+d), Nat.double(K.width(d)), Nat.double(1n+h),
    width_double(d), Equal.cong(Nat, Nat, x => Nat.double(x), K.width(d), 1n+h, w))
  succ_zero(Nat.double(Nat.mod(lo, 1n+h)),
    Equal.trans(Nat, 1n+Nat.double(Nat.mod(lo, 1n+h)), Nat.mod(1n+Nat.double(lo), Nat.double(1n+h)), 0n,
      Equal.sym(Nat, Nat.mod(1n+Nat.double(lo), Nat.double(1n+h)), 1n+Nat.double(Nat.mod(lo, 1n+h)), modulo_odd(lo, h)),
      Equal.trans(Nat, Nat.mod(1n+Nat.double(lo), Nat.double(1n+h)), Nat.mod(1n+Nat.double(lo), K.width(1n+d)), 0n,
        Equal.cong(Nat, Nat, x => Nat.mod(1n+Nat.double(lo), x), Nat.double(1n+h), K.width(1n+d),
          Equal.sym(Nat, K.width(1n+d), Nat.double(1n+h), eqw)), aligned)))

law odd_unaligned:
  for +lo: Nat
  for +d: Nat
  for aligned: {Nat.mod(1n+Nat.double(lo), K.width(1n+d)) == 0n : Nat}
  Empty

def odd_unaligned(lo, d, aligned):
  odd_unaligned_width(lo, d, aligned, positive_width(d))
