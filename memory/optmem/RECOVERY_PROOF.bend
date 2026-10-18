import Base
import ./CONTRACT.bend as K
import ./selection.bend as S
import ./RECOVERY.bend as B
import ./GEOMETRY.bend as G
import ./REFINE.bend as R

law add_right_succ:
  for n: Nat
  for +d: Nat
  {Nat.add(n, 1n+d) == 1n+Nat.add(n, d) : Nat}

def add_right_succ(n, d):
  match n:
    case 0n:
      {==}
    case 1n+p:
      %add_right_succ(p, d) : {1n+Nat.add(p, 1n+d) == 1n+_ : Nat}
      {==}

law add_zero:
  for n: Nat
  {Nat.add(n, 0n) == n : Nat}

def add_zero(n):
  match n:
    case 0n:
      {==}
    case 1n+p:
      %add_zero(p) : {1n+Nat.add(p, 0n) == 1n+_ : Nat}
      {==}

law even_go:
  for n: Nat
  for +d: Nat
  {Nat.divmod.go(Nat.double(n), 1n, d, 0n) == (Nat.add(n, d), 0n) : Nat & Nat}

def even_go(n, d):
  match n:
    case 0n:
      {==}
    case 1n+p:
      +q = p
      %add_right_succ(q, d) :
        {Nat.divmod.go(Nat.double(p), 1n, 1n+d, 0n) == (_, 0n) : Nat & Nat}
      even_go(q, 1n+d)

law odd_go:
  for n: Nat
  for +d: Nat
  {Nat.divmod.go(Nat.double(n), 0n, d, 1n) == (Nat.add(n, d), 1n) : Nat & Nat}

def odd_go(n, d):
  match n:
    case 0n:
      {==}
    case 1n+p:
      +q = p
      %add_right_succ(q, d) :
        {Nat.divmod.go(Nat.double(p), 0n, 1n+d, 1n) == (_, 1n) : Nat & Nat}
      odd_go(q, 1n+d)

law even_divmod:
  for n: Nat
  {Nat.divmod(Nat.double(n), 2n) == (n, 0n) : Nat & Nat}

def even_divmod(n):
  +m = n
  %add_zero(m) : {Nat.divmod.go(Nat.double(m), 1n, 0n, 0n) == (_, 0n) : Nat & Nat}
  even_go(m, 0n)

law odd_divmod:
  for n: Nat
  {Nat.divmod(1n+Nat.double(n), 2n) == (n, 1n) : Nat & Nat}

def odd_divmod(n):
  +m = n
  %add_zero(m) : {Nat.divmod.go(Nat.double(m), 0n, 0n, 1n) == (_, 1n) : Nat & Nat}
  odd_go(m, 0n)

law even_mod:
  for n: Nat
  {Nat.mod(Nat.double(n), 2n) == 0n : Nat}

def even_mod(n):
  +m = n
  %Equal.sym(Nat & Nat, Nat.divmod(Nat.double(m), 2n), (m, 0n), even_divmod(m)) :
    {Nat.mod.fin(_) == 0n : Nat}
  {==}

law even_div:
  for n: Nat
  {Nat.div(Nat.double(n), 2n) == n : Nat}

def even_div(n):
  +m = n
  %Equal.sym(Nat & Nat, Nat.divmod(Nat.double(m), 2n), (m, 0n), even_divmod(m)) :
    {Nat.div.fin(_) == m : Nat}
  {==}

law odd_mod:
  for n: Nat
  {Nat.mod(1n+Nat.double(n), 2n) == 1n : Nat}

def odd_mod(n):
  +m = n
  %Equal.sym(Nat & Nat, Nat.divmod(1n+Nat.double(m), 2n), (m, 1n), odd_divmod(m)) :
    {Nat.mod.fin(_) == 1n : Nat}
  {==}

law odd_div:
  for n: Nat
  {Nat.div(1n+Nat.double(n), 2n) == n : Nat}

def odd_div(n):
  +m = n
  %Equal.sym(Nat & Nat, Nat.divmod(1n+Nat.double(m), 2n), (m, 1n), odd_divmod(m)) :
    {Nat.div.fin(_) == m : Nat}
  {==}


law minimum_word:
  for n: Nat
  for +word: Word(n)
  {K.minimum(n, Word.to_nat(n, word)) == B.bitcount(n, word) : Nat}

def minimum_word(n, word):
  match n word:
    case 0n WNil{}:
      {==}
    case 1n+p WCon{False{}, tail}:
      +q = p
      +t = tail
      +m = Word.to_nat(q, t)
      %Equal.sym(Nat, Nat.mod(Nat.double(m), 2n), 0n, even_mod(m)) :
        {Nat.add(_, K.minimum(q, Nat.div(Nat.double(m), 2n))) == B.bitcount(q, t) : Nat}
      %Equal.sym(Nat, Nat.div(Nat.double(m), 2n), m, even_div(m)) :
        {K.minimum(q, _) == B.bitcount(q, t) : Nat}
      minimum_word(q, t)
    case 1n+p WCon{True{}, tail}:
      +q = p
      +t = tail
      +m = Word.to_nat(q, t)
      %Equal.sym(Nat, Nat.mod(1n+Nat.double(m), 2n), 1n, odd_mod(m)) :
        {Nat.add(_, K.minimum(q, Nat.div(1n+Nat.double(m), 2n))) == 1n+B.bitcount(q, t) : Nat}
      %Equal.sym(Nat, Nat.div(1n+Nat.double(m), 2n), m, odd_div(m)) :
        {1n+K.minimum(q, _) == 1n+B.bitcount(q, t) : Nat}
      %minimum_word(q, t) : {1n+K.minimum(q, m) == 1n+_ : Nat}
      {==}

# Low-to-high Word recursion; higher chunks are emitted first.
def word_seed(n: Nat, +bit: Nat, word: Word(n)) -> S.Chunks:
  match n word:
    case 0n WNil{}:
      S.End{}
    case 1n+p WCon{False{}, tail}:
      word_seed(p, 1n+bit, tail)
    case 1n+p WCon{True{}, tail}:
      S.concat(word_seed(p, 1n+bit, tail), S.More{bit, S.End{}})

law add_one:
  for n: Nat
  {Nat.add(n, 1n) == 1n+n : Nat}

def add_one(n):
  match n:
    case 0n:
      {==}
    case 1n+p:
      %add_one(p) : {1n+Nat.add(p, 1n) == 1n+_ : Nat}
      {==}

law concat_length:
  for +xs: S.Chunks
  for +ys: S.Chunks
  {K.length(S.concat(xs, ys)) == Nat.add(K.length(xs), K.length(ys)) : Nat}

def concat_length(xs, ys):
  match xs:
    case S.End{}:
      {==}
    case S.More{d, rest}:
      %concat_length(rest, ys) :
        {1n+K.length(S.concat(rest, ys)) == 1n+_ : Nat}
      {==}

law append_length:
  for +xs: S.Chunks
  for +bit: Nat
  {K.length(S.concat(xs, S.More{bit, S.End{}})) == 1n+K.length(xs) : Nat}

def append_length(xs, bit):
  %add_one(K.length(xs)) : {K.length(S.concat(xs, S.More{bit, S.End{}})) == _ : Nat}
  concat_length(xs, S.More{bit, S.End{}})

law word_seed_length:
  for n: Nat
  for +bit: Nat
  for +word: Word(n)
  {K.length(word_seed(n, bit, word)) == B.bitcount(n, word) : Nat}

def word_seed_length(n, bit, word):
  match n word:
    case 0n WNil{}:
      {==}
    case 1n+p WCon{False{}, tail}:
      word_seed_length(p, 1n+bit, tail)
    case 1n+p WCon{True{}, tail}:
      +q = p
      +b = bit
      +t = tail
      %word_seed_length(q, 1n+b, t) :
        {K.length(S.concat(word_seed(q, 1n+b, t), S.More{b, S.End{}})) == 1n+_ : Nat}
      %append_length(word_seed(q, 1n+b, t), b) :
        {K.length(S.concat(word_seed(q, 1n+b, t), S.More{b, S.End{}})) == _ : Nat}
      {==}

law scale_length:
  for +xs: S.Chunks
  {K.length(B.scale(xs)) == K.length(xs) : Nat}

def scale_length(xs):
  match xs:
    case S.End{}:
      {==}
    case S.More{d, rest}:
      %scale_length(rest) : {1n+K.length(B.scale(rest)) == 1n+_ : Nat}
      {==}

law append_raw_length:
  for +xs: S.Chunks
  {K.length(B.append_raw(xs)) == 1n+K.length(xs) : Nat}

def append_raw_length(xs):
  match xs:
    case S.End{}:
      {==}
    case S.More{d,rest}:
      Equal.cong(Nat, Nat, n => 1n+n,
        K.length(B.append_raw(rest)), 1n+K.length(rest), append_raw_length(rest))

law seed_word_length:
  for n: Nat
  for +word: Word(n)
  {K.length(B.seed_word(n, word)) == B.bitcount(n, word) : Nat}

def seed_word_length(n, word):
  match n word:
    case 0n WNil{}:
      {==}
    case 1n+p WCon{False{}, tail}:
      +q = p
      +t = tail
      %seed_word_length(q, t) : {K.length(B.scale(B.seed_word(q,t))) == _ : Nat}
      scale_length(B.seed_word(q,t))
    case 1n+p WCon{True{}, tail}:
      +q = p
      +t = tail
      %seed_word_length(q,t) :
        {K.length(B.append_raw(B.scale(B.seed_word(q,t)))) == 1n+_ : Nat}
      %scale_length(B.seed_word(q,t)) :
        {K.length(B.append_raw(B.scale(B.seed_word(q,t)))) == 1n+_ : Nat}
      append_raw_length(B.scale(B.seed_word(q,t)))

def RefineFact(+xs: S.Chunks, r: S.Refinement) -> Type:
  match r:
    case S.Stayed{ys}:
      {S.mass(xs) == K.length(xs) : Nat} & {ys == xs : S.Chunks}
    case S.Split{ys}:
      {K.length(ys) == 1n+K.length(xs) : Nat}

law refine_fact:
  for +xs: S.Chunks
  RefineFact(xs, S.refine(xs))

law refine_tail_fact:
  for +d: Nat
  for +xs: S.Chunks
  for r: S.Refinement
  for fact: RefineFact(xs, r)
  RefineFact(S.More{d, xs}, S.refine_tail(d, r))

def refine_tail_fact(d, xs, r, fact):
  match d r:
    case 0n S.Stayed{ys}:
      (m, e) = fact
      (Equal.cong(Nat, Nat, n => 1n+n, S.mass(xs), K.length(xs), m),
        Equal.cong(S.Chunks, S.Chunks, zs => S.More{0n, zs}, ys, xs, e))
    case 1n+p S.Stayed{ys}:
      (m, e) = fact
      Equal.cong(S.Chunks, Nat, zs => K.length(S.More{p, S.More{p, zs}}), ys, xs, e)
    case d S.Split{ys}:
      Equal.cong(Nat, Nat, n => 1n+n, K.length(ys), 1n+K.length(xs), fact)

def refine_fact(xs):
  match xs:
    case S.End{}:
      ({==},{==})
    case S.More{d, rest}:
      refine_tail_fact(d, rest, S.refine(rest), refine_fact(rest))

def IsZero(n: Nat) -> Type:
  match n:
    case 0n:
      Unit
    case 1n+p:
      Empty

def pred(n: Nat) -> Nat:
  match n:
    case 0n:
      0n
    case 1n+p:
      p

law no_add_succ:
  for +a: Nat
  for +b: Nat
  for equal: {Nat.add(a, 1n+b) == a : Nat}
  Empty

def no_add_succ(a, b, equal):
  match a:
    case 0n:
      %Equal.sym(Nat, 1n+b, 0n, equal) : IsZero(_)
      Unit{}
    case 1n+p:
      no_add_succ(p, b,
        Equal.cong(Nat, Nat, pred,
          1n+Nat.add(p, 1n+b), 1n+p, equal))

law stayed_impossible:
  for +xs: S.Chunks
  for +ys: S.Chunks
  for +fuel: Nat
  for +spare: Nat
  for fact: RefineFact(xs, S.Stayed{ys})
  for bound: {S.mass(xs) == Nat.add(K.length(xs), 1n+Nat.add(fuel, spare)) : Nat}
  Empty

def stayed_impossible(xs, ys, fuel, spare, fact, bound):
  (m, e) = fact
  no_add_succ(K.length(xs), Nat.add(fuel, spare),
    Equal.trans(Nat,
      Nat.add(K.length(xs), 1n+Nat.add(fuel, spare)),
      S.mass(xs), K.length(xs),
      Equal.sym(Nat, S.mass(xs), Nat.add(K.length(xs), 1n+Nat.add(fuel, spare)), bound),
      m))

law split_bound:
  for +xs: S.Chunks
  for +ys: S.Chunks
  for +fuel: Nat
  for +spare: Nat
  for count: RefineFact(xs, S.Split{ys})
  for conserved: {S.mass(ys) == S.mass(xs) : Nat}
  for bound: {S.mass(xs) == Nat.add(K.length(xs), 1n+Nat.add(fuel, spare)) : Nat}
  {S.mass(ys) == Nat.add(K.length(ys), Nat.add(fuel, spare)) : Nat}

def split_bound(xs, ys, fuel, spare, count, conserved, bound):
  Equal.trans(Nat,
    S.mass(ys), Nat.add(K.length(xs), 1n+Nat.add(fuel, spare)),
    Nat.add(K.length(ys), Nat.add(fuel, spare)),
    Equal.trans(Nat, S.mass(ys), S.mass(xs),
      Nat.add(K.length(xs), 1n+Nat.add(fuel, spare)), conserved, bound),
    Equal.trans(Nat,
      Nat.add(K.length(xs), 1n+Nat.add(fuel, spare)),
      1n+Nat.add(K.length(xs), Nat.add(fuel, spare)),
      Nat.add(K.length(ys), Nat.add(fuel, spare)),
      add_right_succ(K.length(xs), Nat.add(fuel, spare)),
      Equal.cong(Nat, Nat, n => Nat.add(n, Nat.add(fuel, spare)),
        1n+K.length(xs), K.length(ys),
        Equal.sym(Nat, K.length(ys), 1n+K.length(xs), count))))

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

law refine_mass:
  for +xs: S.Chunks
  {S.mass(S.answer(S.refine(xs))) == S.mass(xs) : Nat}

def refine_mass(xs):
  match xs:
    case S.End{}:
      {==}
    case S.More{d, rest}:
      Equal.trans(Nat, S.mass(S.answer(S.refine(S.More{d, rest}))),
        Nat.add(S.width(d), S.mass(S.answer(S.refine(rest)))),
        S.mass(S.More{d, rest}), tail_mass(d, S.refine(rest)),
        Equal.cong(Nat, Nat, n => Nat.add(S.width(d), n),
          S.mass(S.answer(S.refine(rest))), S.mass(rest),
          refine_mass(rest)))


law fill_bound:
  for +fuel: Nat
  for +spare: Nat
  for +xs: S.Chunks
  for bound: {S.mass(xs) == Nat.add(K.length(xs), Nat.add(fuel, spare)) : Nat}
  {K.length(S.fill(fuel, xs)) == Nat.add(K.length(xs), fuel) : Nat}

law fill_bound_step:
  for +xs: S.Chunks
  for r: S.Refinement
  for +fuel: Nat
  for +spare: Nat
  for fact: RefineFact(xs, r)
  for count_again: RefineFact(xs, r)
  for conserved: {S.mass(S.answer(r)) == S.mass(xs) : Nat}
  for bound: {S.mass(xs) == Nat.add(K.length(xs), 1n+Nat.add(fuel, spare)) : Nat}
  for cont: @ys: S.Chunks ->
    {S.mass(ys) == Nat.add(K.length(ys), Nat.add(fuel, spare)) : Nat} ->
    {K.length(S.fill(fuel, ys)) == Nat.add(K.length(ys), fuel) : Nat}
  {K.length(S.fill(fuel, S.answer(r))) == Nat.add(K.length(xs), 1n+fuel) : Nat}

def absurd(-A: Type, empty: Empty) -> A:
  match empty:

def fill_bound_step(xs, r, fuel, spare, fact, count_again, conserved, bound, cont):
  match r:
    case S.Stayed{ys}:
      absurd({K.length(S.fill(fuel,ys)) == Nat.add(K.length(xs),1n+fuel) : Nat},
        stayed_impossible(xs,ys,fuel,spare,fact,bound))
    case S.Split{+ys}:
      Equal.trans(Nat,
        K.length(S.fill(fuel,ys)), Nat.add(K.length(ys),fuel),
        Nat.add(K.length(xs),1n+fuel),
        cont(ys,split_bound(xs,ys,fuel,spare,fact,conserved,bound)),
        Equal.trans(Nat,
          Nat.add(K.length(ys),fuel), Nat.add(1n+K.length(xs),fuel),
          Nat.add(K.length(xs),1n+fuel),
          Equal.cong(Nat,Nat,n => Nat.add(n,fuel),K.length(ys),1n+K.length(xs),count_again),
          Equal.sym(Nat,Nat.add(K.length(xs),1n+fuel),1n+Nat.add(K.length(xs),fuel),
            add_right_succ(K.length(xs),fuel))))

def fill_bound(fuel, spare, xs, bound):
  match fuel:
    case 0n:
      %Equal.sym(Nat, Nat.add(K.length(xs), 0n), K.length(xs),
        add_zero(K.length(xs))) : {K.length(xs) == _ : Nat}
      {==}
    case 1n+p:
      fill_bound_step(xs, S.refine(xs), p, spare,
        refine_fact(xs), refine_fact(xs), refine_mass(xs), bound,
        ys => next => fill_bound(p, spare, ys, next))

law sub_zero:
  for +n: Nat
  {Nat.sub(n, 0n) == n : Nat}

def sub_zero(n):
  match n:
    case 0n:
      {==}
    case 1n+p:
      {==}

law seed_partition:
  for n: Nat
  for +word: Word(n)
  for +bounded: K.Le(n, 32n)
  K.Partition(B.seed_word(n, word), 0n, Word.to_nat(n, word), Nat.sub(n, 1n))

law seed_partition_tail:
  for q: Nat
  for +tail: Word(1n+q)
  for ih: K.Partition(B.seed_word(1n+q, tail), 0n, Word.to_nat(1n+q, tail),
    Nat.sub(1n+q, 1n))
  K.Partition(B.seed_word(1n+q, tail), 0n, Word.to_nat(1n+q, tail), q)

def seed_partition_tail(q, tail, ih):
  %sub_zero(q) : K.Partition(B.seed_word(1n+q, tail), 0n, Word.to_nat(1n+q, tail), _)
  ih

def seed_partition(n, word, bounded):
  match n word:
    case 0n WNil{}:
      {==}
    case 1n WCon{False{}, WNil{}}:
      {==}
    case 1n WCon{True{}, WNil{}}:
      (Unit{}, (Unit{}, (G.modulo_one(0n), (G.le_refl(1n), {==}))))
    case 2n+q WCon{False{}, tail}:
      +z = q
      +p = {1n+z : Nat}
      +t = tail
      G.scaled_partition(B.seed_word(p,t),0n,Word.to_nat(p,t),z,bounded,
        seed_partition_tail(z,t,
          seed_partition(p,t,
            G.le_trans(p,2n+z,32n,G.le_right_succ(p,p,G.le_refl(p)),bounded))))
    case 2n+q WCon{True{}, tail}:
      +z = q
      +p = {1n+z : Nat}
      +t = tail
      G.append_raw_partition(B.scale(B.seed_word(p,t)),0n,
        Nat.double(Word.to_nat(p,t)),p,
        G.scaled_partition(B.seed_word(p,t),0n,Word.to_nat(p,t),z,bounded,
          seed_partition_tail(z,t,
            seed_partition(p,t,
              G.le_trans(p,2n+z,32n,G.le_right_succ(p,p,G.le_refl(p)),bounded)))))

law selection_width_double:
  for +d: Nat
  {S.width(1n+d) == Nat.double(S.width(d)) : Nat}

def selection_width_double(d):
  G.add_self_double(S.width(d))

law scale_mass:
  for +xs: S.Chunks
  {S.mass(B.scale(xs)) == Nat.double(S.mass(xs)) : Nat}

def scale_mass(xs):
  match xs:
    case S.End{}:
      {==}
    case S.More{d,rest}:
      Equal.trans(Nat,
        S.mass(B.scale(S.More{d,rest})),
        Nat.add(S.width(1n+d), Nat.double(S.mass(rest))),
        Nat.double(S.mass(S.More{d,rest})),
        Equal.cong(Nat,Nat,n => Nat.add(S.width(1n+d),n),
          S.mass(B.scale(rest)),Nat.double(S.mass(rest)),scale_mass(rest)),
        Equal.trans(Nat,
          Nat.add(S.width(1n+d), Nat.double(S.mass(rest))),
          Nat.add(Nat.double(S.width(d)), Nat.double(S.mass(rest))),
          Nat.double(Nat.add(S.width(d),S.mass(rest))),
          Equal.cong(Nat,Nat,n => Nat.add(n,Nat.double(S.mass(rest))),
            S.width(1n+d),Nat.double(S.width(d)),selection_width_double(d)),
          Equal.sym(Nat,Nat.double(Nat.add(S.width(d),S.mass(rest))),
            Nat.add(Nat.double(S.width(d)),Nat.double(S.mass(rest))),
            G.double_add(S.width(d),S.mass(rest)))))

law append_raw_mass:
  for +xs: S.Chunks
  {S.mass(B.append_raw(xs)) == 1n+S.mass(xs) : Nat}

def append_raw_mass(xs):
  match xs:
    case S.End{}:
      {==}
    case S.More{d,rest}:
      Equal.trans(Nat,
        S.mass(B.append_raw(S.More{d,rest})),
        Nat.add(S.width(d),1n+S.mass(rest)),
        1n+S.mass(S.More{d,rest}),
        Equal.cong(Nat,Nat,n => Nat.add(S.width(d),n),
          S.mass(B.append_raw(rest)),1n+S.mass(rest),append_raw_mass(rest)),
        G.add_succ_right(S.width(d),S.mass(rest)))

law seed_word_mass:
  for n: Nat
  for +word: Word(n)
  {S.mass(B.seed_word(n,word)) == Word.to_nat(n,word) : Nat}

def seed_word_mass(n,word):
  match n word:
    case 0n WNil{}:
      {==}
    case 1n+p WCon{False{},tail}:
      +q=p
      +t=tail
      %seed_word_mass(q,t) : {S.mass(B.scale(B.seed_word(q,t))) == Nat.double(_) : Nat}
      scale_mass(B.seed_word(q,t))
    case 1n+p WCon{True{},tail}:
      +q=p
      +t=tail
      %seed_word_mass(q,t) : {S.mass(B.append_raw(B.scale(B.seed_word(q,t)))) == 1n+Nat.double(_) : Nat}
      %scale_mass(B.seed_word(q,t)) : {S.mass(B.append_raw(B.scale(B.seed_word(q,t)))) == 1n+_ : Nat}
      append_raw_mass(B.scale(B.seed_word(q,t)))

law le_add_right:
  for +a: Nat
  for +b: Nat
  K.Le(a, Nat.add(a,b))

def le_add_right(a,b):
  match a:
    case 0n:
      Unit{}
    case 1n+p:
      le_add_right(p,b)

law le_double:
  for +a: Nat
  K.Le(a, Nat.double(a))

def le_double(a):
  %G.add_self_double(a) : K.Le(a, _)
  le_add_right(a,a)

law bitcount_le_value:
  for n: Nat
  for +word: Word(n)
  K.Le(B.bitcount(n,word), Word.to_nat(n,word))

def bitcount_le_value(n,word):
  match n word:
    case 0n WNil{}:
      Unit{}
    case 1n+p WCon{False{},tail}:
      +q=p
      +t=tail
      G.le_trans(B.bitcount(q,t),Word.to_nat(q,t),Nat.double(Word.to_nat(q,t)),
        bitcount_le_value(q,t),le_double(Word.to_nat(q,t)))
    case 1n+p WCon{True{},tail}:
      +q=p
      +t=tail
      G.le_trans(B.bitcount(q,t),Word.to_nat(q,t),Nat.double(Word.to_nat(q,t)),
        bitcount_le_value(q,t),le_double(Word.to_nat(q,t)))

def OrderLt(+a: Nat,+b: Nat,flag: Bool) -> Data:
  match flag:
    case True{}:
      K.Le(a,b)
    case False{}:
      K.Le(b,a)

law order_succ:
  for +a: Nat
  for +b: Nat
  for flag: Bool
  for order: OrderLt(a,b,flag)
  OrderLt(1n+a,1n+b,flag)

def order_succ(a,b,flag,order):
  match flag:
    case True{}:
      order
    case False{}:
      order

law order_lt:
  for +a: Nat
  for +b: Nat
  OrderLt(a,b,Nat.is_lt(a,b))

def order_lt(a,b):
  match a b:
    case 0n 0n:
      Unit{}
    case 0n 1n+q:
      Unit{}
    case 1n+p 0n:
      Unit{}
    case 1n+p 1n+q:
      order_succ(p,q,Nat.is_lt(p,q),order_lt(p,q))

law max_ge_left:
  for +a: Nat
  for +b: Nat
  K.Le(a,Nat.max(a,b))

law max_ge_left_flag:
  for +a: Nat
  for +b: Nat
  for flag: Bool
  for order: OrderLt(a,b,flag)
  K.Le(a,Bool.pick(Nat,flag,b,a))

def max_ge_left_flag(a,b,flag,order):
  match flag:
    case True{}:
      order
    case False{}:
      G.le_refl(a)

def max_ge_left(a,b):
  match a b:
    case 0n _:
      Unit{}
    case 1n+p 0n:
      G.le_refl(1n+p)
    case 1n+p 1n+q:
      max_ge_left(p,q)


law min_le_left_flag:
  for +a: Nat
  for +b: Nat
  for flag: Bool
  for order: OrderLt(a,b,flag)
  K.Le(Bool.pick(Nat,flag,a,b),a)

def min_le_left_flag(a,b,flag,order):
  match flag:
    case True{}:
      G.le_refl(a)
    case False{}:
      order

law min_le_left:
  for +a: Nat
  for +b: Nat
  K.Le(Nat.min(a,b),a)

def min_le_left(a,b):
  match a b:
    case 0n _:
      Unit{}
    case 1n+p 0n:
      Unit{}
    case 1n+p 1n+q:
      min_le_left(p,q)

law max_upper_flag:
  for +a: Nat
  for +b: Nat
  for +c: Nat
  for flag: Bool
  for left: K.Le(a,c)
  for right: K.Le(b,c)
  K.Le(Bool.pick(Nat,flag,b,a),c)

def max_upper_flag(a,b,c,flag,left,right):
  match flag:
    case True{}:
      right
    case False{}:
      left

law max_upper:
  for +a: Nat
  for +b: Nat
  for +c: Nat
  for left: K.Le(a,c)
  for right: K.Le(b,c)
  K.Le(Nat.max(a,b),c)

def max_upper(a,b,c,left,right):
  match a b:
    case 0n _:
      right
    case 1n+p 0n:
      left
    case 1n+p 1n+q:
      match c:
        case 0n:
          left
        case 1n+r:
          max_upper(p,q,r,left,right)

law expected_bounds:
  for +minimum: Nat
  for +total: Nat
  for +budget: Nat
  for bound: K.Le(minimum,total)
  K.Le(minimum,Nat.max(minimum,Nat.min(total,budget))) &
    K.Le(Nat.max(minimum,Nat.min(total,budget)),total)

def expected_bounds(minimum,total,budget,bound):
  (max_ge_left(minimum,Nat.min(total,budget)),
    max_upper(minimum,Nat.min(total,budget),total,bound,min_le_left(total,budget)))

law sub_reconstruct:
  for +a: Nat
  for +b: Nat
  for bound: K.Le(a,b)
  {Nat.add(a,Nat.sub(b,a)) == b : Nat}

def sub_reconstruct(a,b,bound):
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+q:
      {==}
    case 1n+p 0n:
      match bound:
    case 1n+p 1n+q:
      %sub_reconstruct(p,q,bound) :
        {1n+Nat.add(p,Nat.sub(q,p)) == 1n+_ : Nat}
      {==}

law capacity:
  for +minimum: Nat
  for +total: Nat
  for +budget: Nat
  for bounded: K.Le(minimum,total)
  {total == Nat.add(minimum,
    Nat.add(Nat.sub(Nat.max(minimum,Nat.min(total,budget)),minimum),
      Nat.sub(total,Nat.max(minimum,Nat.min(total,budget))))) : Nat}

law capacity_from_bounds:
  for +minimum: Nat
  for +total: Nat
  for +target: Nat
  for lower: K.Le(minimum,target)
  for upper: K.Le(target,total)
  {total == Nat.add(minimum,
    Nat.add(Nat.sub(target,minimum),Nat.sub(total,target))) : Nat}

def capacity_from_bounds(minimum,total,target,lower,upper):
  Equal.trans(Nat,total,
    Nat.add(target,Nat.sub(total,target)),
    Nat.add(minimum,Nat.add(Nat.sub(target,minimum),Nat.sub(total,target))),
    Equal.sym(Nat,Nat.add(target,Nat.sub(total,target)),total,
      sub_reconstruct(target,total,upper)),
    Equal.trans(Nat,
      Nat.add(target,Nat.sub(total,target)),
      Nat.add(Nat.add(minimum,Nat.sub(target,minimum)),Nat.sub(total,target)),
      Nat.add(minimum,Nat.add(Nat.sub(target,minimum),Nat.sub(total,target))),
      Equal.cong(Nat,Nat,n => Nat.add(n,Nat.sub(total,target)),
        target,Nat.add(minimum,Nat.sub(target,minimum)),
        Equal.sym(Nat,Nat.add(minimum,Nat.sub(target,minimum)),target,
          sub_reconstruct(minimum,target,lower))),
      add_assoc(minimum,Nat.sub(target,minimum),Nat.sub(total,target))))

law capacity_from_pair:
  for +minimum: Nat
  for +total: Nat
  for +budget: Nat
  for bounds: K.Le(minimum,Nat.max(minimum,Nat.min(total,budget))) &
    K.Le(Nat.max(minimum,Nat.min(total,budget)),total)
  {total == Nat.add(minimum,
    Nat.add(Nat.sub(Nat.max(minimum,Nat.min(total,budget)),minimum),
      Nat.sub(total,Nat.max(minimum,Nat.min(total,budget))))) : Nat}

def capacity_from_pair(minimum,total,budget,bounds):
  (lower,upper) = bounds
  capacity_from_bounds(minimum,total,Nat.max(minimum,Nat.min(total,budget)),lower,upper)

def capacity(minimum,total,budget,bounded):
  capacity_from_pair(minimum,total,budget,
    expected_bounds(minimum,total,budget,bounded))


law seed_capacity:
  for +word: Word(32n)
  for +budget: Nat
  {S.mass(B.seed_word(32n,word)) ==
    Nat.add(K.length(B.seed_word(32n,word)),
      Nat.add(
        Nat.sub(Nat.max(B.bitcount(32n,word),Nat.min(Word.to_nat(32n,word),budget)),
          B.bitcount(32n,word)),
        Nat.sub(Word.to_nat(32n,word),
          Nat.max(B.bitcount(32n,word),Nat.min(Word.to_nat(32n,word),budget))))) : Nat}

def seed_capacity(word,budget):
  +w=word
  +t=Word.to_nat(32n,w)
  +m=B.bitcount(32n,w)
  +s=B.seed_word(32n,w)
  +target=Nat.max(m,Nat.min(t,budget))
  Equal.trans(Nat,S.mass(s),t,
    Nat.add(K.length(s),Nat.add(Nat.sub(target,m),Nat.sub(t,target))),
    seed_word_mass(32n,w),
    Equal.trans(Nat,t,
      Nat.add(m,Nat.add(Nat.sub(target,m),Nat.sub(t,target))),
      Nat.add(K.length(s),Nat.add(Nat.sub(target,m),Nat.sub(t,target))),
      capacity(m,t,budget,bitcount_le_value(32n,w)),
      Equal.cong(Nat,Nat,n => Nat.add(n,Nat.add(Nat.sub(target,m),Nat.sub(t,target))),
        m,K.length(s),Equal.sym(Nat,K.length(s),m,seed_word_length(32n,w)))))

law seed_fill_count:
  for +word: Word(32n)
  for +budget: Nat
  {K.length(S.fill(
    Nat.sub(Nat.max(B.bitcount(32n,word),Nat.min(Word.to_nat(32n,word),budget)),
      B.bitcount(32n,word)), B.seed_word(32n,word))) ==
    Nat.max(B.bitcount(32n,word),Nat.min(Word.to_nat(32n,word),budget)) : Nat}

def seed_fill_count(word,budget):
  +w=word
  +t=Word.to_nat(32n,w)
  +m=B.bitcount(32n,w)
  +s=B.seed_word(32n,w)
  +target=Nat.max(m,Nat.min(t,budget))
  +fuel=Nat.sub(target,m)
  +spare=Nat.sub(t,target)
  Equal.trans(Nat,
    K.length(S.fill(fuel,s)), Nat.add(K.length(s),fuel),target,
    fill_bound(fuel,spare,s,seed_capacity(w,budget)),
    Equal.trans(Nat,
      Nat.add(K.length(s),fuel),Nat.add(m,fuel),target,
      Equal.cong(Nat,Nat,n => Nat.add(n,fuel),K.length(s),m,seed_word_length(32n,w)),
      sub_reconstruct(m,target,max_ge_left(m,Nat.min(t,budget)))))

law seed32_partition:
  for +word: Word(32n)
  K.Partition(B.seed_word(32n,word),0n,Word.to_nat(32n,word),31n)

def seed32_partition(word):
  %sub_zero(31n) : K.Partition(B.seed_word(32n,word),0n,Word.to_nat(32n,word),_)
  seed_partition(32n,word,G.le_refl(32n))

law expected_word:
  for +word: Word(32n)
  for +budget: Nat
  {K.expected(Word.to_nat(32n,word),budget) ==
    Nat.max(B.bitcount(32n,word),Nat.min(Word.to_nat(32n,word),budget)) : Nat}

def expected_word(word,budget):
  Equal.cong(Nat,Nat,n => Nat.max(n,Nat.min(Word.to_nat(32n,word),budget)),
    K.minimum(32n,Word.to_nat(32n,word)),B.bitcount(32n,word),
    minimum_word(32n,word))

law recovery_contract:
  for +word: Word(32n)
  for +budget: Nat
  K.Contract(B.recover_word(word,budget),Word.to_nat(32n,word),budget)

def recovery_contract(word,budget):
  (R.fill_partition(
      Nat.sub(Nat.max(B.bitcount(32n,word),Nat.min(Word.to_nat(32n,word),budget)),
        B.bitcount(32n,word)),
      B.seed_word(32n,word),0n,Word.to_nat(32n,word),31n,
      seed32_partition(word)),
    Equal.trans(Nat,
      K.length(B.recover_word(word,budget)),
      Nat.max(B.bitcount(32n,word),Nat.min(Word.to_nat(32n,word),budget)),
      K.expected(Word.to_nat(32n,word),budget),
      seed_fill_count(word,budget),
      Equal.sym(Nat,
        K.expected(Word.to_nat(32n,word),budget),
        Nat.max(B.bitcount(32n,word),Nat.min(Word.to_nat(32n,word),budget)),
        expected_word(word,budget))))
