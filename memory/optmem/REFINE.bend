import Base
import ./CONTRACT.bend as K
import ./selection.bend as S
import ./GEOMETRY.bend as G

def Down(d: Nat) -> Type:
  @q: Nat -> {Nat.mod(q, K.width(1n+d)) == 0n : Nat} -> {Nat.mod(q, K.width(d)) == 0n : Nat}

def down_case(+lo: Nat, +p: Nat, +q: Nat,
  shape: Or({lo == Nat.double(q) : Nat}, {lo == 1n+Nat.double(q) : Nat}),
  ih: Down(p)) ->
  {Nat.mod(lo, K.width(2n+p)) == 0n : Nat} -> {Nat.mod(lo, K.width(1n+p)) == 0n : Nat}:
  match shape:
    case Inl{even}:
      %Equal.sym(Nat, lo, Nat.double(q), even) :
        ({Nat.mod(_, K.width(2n+p)) == 0n : Nat} -> {Nat.mod(_, K.width(1n+p)) == 0n : Nat})
      aligned => G.aligned_double(q, p, ih(q, G.even_aligned_reduce(q, 1n+p, aligned)))
    case Inr{odd}:
      %Equal.sym(Nat, lo, 1n+Nat.double(q), odd) :
        ({Nat.mod(_, K.width(2n+p)) == 0n : Nat} -> {Nat.mod(_, K.width(1n+p)) == 0n : Nat})
      aligned => G.absurd({Nat.mod(1n+Nat.double(q), K.width(1n+p)) == 0n : Nat}, G.odd_unaligned(q, 1n+p, aligned))

def down_shape(+lo: Nat, +p: Nat,
  qr: Exists(Nat, q => Or({lo == Nat.double(q) : Nat}, {lo == 1n+Nat.double(q) : Nat})),
  ih: Down(p)) ->
  {Nat.mod(lo, K.width(2n+p)) == 0n : Nat} -> {Nat.mod(lo, K.width(1n+p)) == 0n : Nat}:
  (q, shape) = qr
  down_case(lo, p, q, shape, ih)

law alignment_down:
  for +d: Nat
  for +lo: Nat
  for aligned: {Nat.mod(lo, K.width(1n+d)) == 0n : Nat}
  {Nat.mod(lo, K.width(d)) == 0n : Nat}

def alignment_down(d, lo, aligned):
  match d:
    case 0n:
      G.modulo_one(lo)
    case 1n+p:
      down_shape(lo, p, G.parity(lo), q => e => alignment_down(p, q, e))(aligned)

def Shift(d: Nat) -> Type:
  @q: Nat -> {Nat.mod(q, K.width(d)) == 0n : Nat} -> {Nat.mod(Nat.add(q, K.width(d)), K.width(d)) == 0n : Nat}

def shift_even(+p: Nat, +q: Nat,
  ih: Shift(p), aligned: {Nat.mod(Nat.double(q), K.width(1n+p)) == 0n : Nat}) ->
  {Nat.mod(Nat.add(Nat.double(q), K.width(1n+p)), K.width(1n+p)) == 0n : Nat}:
  Equal.trans(Nat,
    Nat.mod(Nat.add(Nat.double(q), K.width(1n+p)), K.width(1n+p)),
    Nat.mod(Nat.double(Nat.add(q, K.width(p))), K.width(1n+p)), 0n,
    Equal.cong(Nat, Nat, x => Nat.mod(x, K.width(1n+p)),
      Nat.add(Nat.double(q), K.width(1n+p)), Nat.double(Nat.add(q, K.width(p))), G.extent_double(q, p)),
    G.aligned_double(Nat.add(q, K.width(p)), p, ih(q, G.even_aligned_reduce(q, p, aligned))))

def shift_case(+lo: Nat, +p: Nat, +q: Nat,
  shape: Or({lo == Nat.double(q) : Nat}, {lo == 1n+Nat.double(q) : Nat}),
  ih: Shift(p)) ->
  {Nat.mod(lo, K.width(1n+p)) == 0n : Nat} -> {Nat.mod(Nat.add(lo, K.width(1n+p)), K.width(1n+p)) == 0n : Nat}:
  match shape:
    case Inl{even}:
      %Equal.sym(Nat, lo, Nat.double(q), even) :
        ({Nat.mod(_, K.width(1n+p)) == 0n : Nat} -> {Nat.mod(Nat.add(_, K.width(1n+p)), K.width(1n+p)) == 0n : Nat})
      aligned => shift_even(p, q, ih, aligned)
    case Inr{odd}:
      %Equal.sym(Nat, lo, 1n+Nat.double(q), odd) :
        ({Nat.mod(_, K.width(1n+p)) == 0n : Nat} -> {Nat.mod(Nat.add(_, K.width(1n+p)), K.width(1n+p)) == 0n : Nat})
      aligned => G.absurd({Nat.mod(Nat.add(1n+Nat.double(q), K.width(1n+p)), K.width(1n+p)) == 0n : Nat}, G.odd_unaligned(q, p, aligned))

def shift_shape(+lo: Nat, +p: Nat,
  qr: Exists(Nat, q => Or({lo == Nat.double(q) : Nat}, {lo == 1n+Nat.double(q) : Nat})),
  ih: Shift(p)) ->
  {Nat.mod(lo, K.width(1n+p)) == 0n : Nat} -> {Nat.mod(Nat.add(lo, K.width(1n+p)), K.width(1n+p)) == 0n : Nat}:
  (q, shape) = qr
  shift_case(lo, p, q, shape, ih)

law aligned_shift:
  for +d: Nat
  for +lo: Nat
  for aligned: {Nat.mod(lo, K.width(d)) == 0n : Nat}
  {Nat.mod(Nat.add(lo, K.width(d)), K.width(d)) == 0n : Nat}

def aligned_shift(d, lo, aligned):
  match d:
    case 0n:
      G.modulo_one(Nat.add(lo, 1n))
    case 1n+p:
      shift_shape(lo, p, G.parity(lo), q => e => aligned_shift(p, q, e))(aligned)

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
      Equal.cong(Nat, Nat, x => 1n+x,
        Nat.add(Nat.add(p, b), c), Nat.add(p, Nat.add(b, c)), add_assoc(p, b, c))

law split_end:
  for +lo: Nat
  for +d: Nat
  {Nat.add(lo, K.width(1n+d)) == Nat.add(Nat.add(lo, K.width(d)), K.width(d)) : Nat}

def split_end(lo, d):
  Equal.sym(Nat, Nat.add(Nat.add(lo, K.width(d)), K.width(d)), Nat.add(lo, K.width(1n+d)), add_assoc(lo, K.width(d), K.width(d)))

law le_prefix:
  for +a: Nat
  for +b: Nat
  K.Le(a, Nat.add(a, b))

def le_prefix(a, b):
  match a:
    case 0n:
      Unit{}
    case 1n+p:
      le_prefix(p, b)

def rebase_le(+a: Nat, +b: Nat, +total: Nat, e: {a == b : Nat}, value: K.Le(a, total)) -> K.Le(b, total):
  %e : K.Le(_, total)
  value

def rebase_partition(+xs: S.Chunks, +a: Nat, +b: Nat, +total: Nat, +previous: Nat,
  e: {a == b : Nat}, value: K.Partition(xs, a, total, previous)) -> K.Partition(xs, b, total, previous):
  %e : K.Partition(xs, _, total, previous)
  value

law partition_relax:
  for +xs: S.Chunks
  for +lo: Nat
  for +total: Nat
  for +old: Nat
  for +new: Nat
  for order: K.Le(old, new)
  for value: K.Partition(xs, lo, total, old)
  K.Partition(xs, lo, total, new)

def partition_relax(xs, lo, total, old, new, order, value):
  match xs:
    case S.End{}:
      value
    case S.More{d, tail}:
      (cap, (previous, (aligned, (extent, rest)))) = value
      (cap, (G.le_trans(d, old, new, previous, order), (aligned, (extent, rest))))

def Refined(+result: S.Refinement, lo: Nat, total: Nat, previous: Nat) -> Type:
  match result:
    case S.Stayed{xs}:
      K.Partition(xs, lo, total, 0n)
    case S.Split{xs}:
      K.Partition(xs, lo, total, previous)

def stayed_geometry(+d: Nat, +xs: S.Chunks, +lo: Nat, +total: Nat, +previous: Nat,
  cap: K.Le(d, 31n), order: K.Le(d, previous), aligned: {Nat.mod(lo, K.width(d)) == 0n : Nat},
  extent: K.Le(Nat.add(lo, K.width(d)), total), raw: K.Partition(xs, Nat.add(lo, K.width(d)), total, 0n)) ->
  Refined(S.refine_stayed(d, xs), lo, total, previous):
  match d:
    case 0n:
      (Unit{}, (Unit{}, (aligned, (extent, raw))))
    case 1n+p:
      +depth = p
      +w = K.width(depth)
      +end = Nat.add(Nat.add(lo, w), w)
      +cap_child = G.le_right_succ(depth, 30n, cap)
      +aligned_child = alignment_down(depth, lo, aligned)
      +equal_end = split_end(lo, depth)
      +full_extent = rebase_le(Nat.add(lo, K.width(1n+depth)), end, total, equal_end, extent)
      tail = rebase_partition(xs, Nat.add(lo, K.width(1n+depth)), end, total, 0n, equal_end, raw)
      (cap_child,
        (G.le_trans(depth, 1n+depth, previous, G.le_right_succ(depth, depth, G.le_refl(depth)), order),
          (aligned_child,
            (G.le_trans(Nat.add(lo, w), end, total, le_prefix(Nat.add(lo, w), w), full_extent),
              (cap_child, (G.le_refl(depth), (aligned_shift(depth, lo, aligned_child),
                (full_extent, partition_relax(xs, end, total, 0n, depth, Unit{}, tail)))))))))

def tail_geometry(+d: Nat, +lo: Nat, +total: Nat, +previous: Nat, +result: S.Refinement,
  cap: K.Le(d, 31n), order: K.Le(d, previous), aligned: {Nat.mod(lo, K.width(d)) == 0n : Nat},
  extent: K.Le(Nat.add(lo, K.width(d)), total),
  proof: Refined(result, Nat.add(lo, K.width(d)), total, d)) -> Refined(S.refine_tail(d, result), lo, total, previous):
  match result:
    case S.Split{xs}:
      (cap, (order, (aligned, (extent, proof))))
    case S.Stayed{xs}:
      stayed_geometry(d, xs, lo, total, previous, cap, order, aligned, extent, proof)

law refine_geometry:
  for +xs: S.Chunks
  for +lo: Nat
  for +total: Nat
  for +previous: Nat
  for partition: K.Partition(xs, lo, total, previous)
  Refined(S.refine(xs), lo, total, previous)

def refine_geometry(xs, lo, total, previous, partition):
  match xs:
    case S.End{}:
      partition
    case S.More{d, rest}:
      (cap, (order, (aligned, (extent, next)))) = partition
      +tail = rest
      tail_geometry(d, lo, total, previous, S.refine(tail), cap, order, aligned, extent,
        refine_geometry(tail, Nat.add(lo, K.width(d)), total, d, next))

def forget_refined(+result: S.Refinement, +lo: Nat, +total: Nat, +previous: Nat,
  proof: Refined(result, lo, total, previous)) -> K.Partition(S.answer(result), lo, total, previous):
  match result:
    case S.Stayed{xs}:
      partition_relax(xs, lo, total, 0n, previous, Unit{}, proof)
    case S.Split{xs}:
      proof

law refine_partition:
  for +xs: S.Chunks
  for +lo: Nat
  for +total: Nat
  for +previous: Nat
  for partition: K.Partition(xs, lo, total, previous)
  K.Partition(S.answer(S.refine(xs)), lo, total, previous)

def refine_partition(xs, lo, total, previous, partition):
  forget_refined(S.refine(xs), lo, total, previous, refine_geometry(xs, lo, total, previous, partition))

law fill_partition:
  for fuel: Nat
  for +xs: S.Chunks
  for +lo: Nat
  for +total: Nat
  for +previous: Nat
  for partition: K.Partition(xs, lo, total, previous)
  K.Partition(S.fill(fuel, xs), lo, total, previous)

def fill_partition(fuel, xs, lo, total, previous, partition):
  match fuel:
    case 0n:
      partition
    case 1n+p:
      fill_partition(p, S.answer(S.refine(xs)), lo, total, previous, refine_partition(xs, lo, total, previous, partition))
