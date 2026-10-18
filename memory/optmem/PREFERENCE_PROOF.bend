import Base
import ./selection.bend as S
import ./certificate.bend as C
import ./CONTRACT.bend as K
import ./PREFERENCE_CONTRACT.bend as P
import ./preference.bend as V

def FalseDisc(flag: Bool) -> Data:
  match flag:
    case False{}:
      Unit
    case True{}:
      Empty

def false_true(e: {False{} == True{} : Bool}) -> Empty:
  %e : FalseDisc(_)
  Unit{}

def absurd(-A: Type,e: Empty) -> A:
  match e:

law eq_sound:
  for +a: Nat
  for +b: Nat
  for e: {Nat.is_eq(a,b) == True{} : Bool}
  {a == b : Nat}
def eq_sound(a,b,e):
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+p:
      absurd({0n == 1n+p : Nat},false_true(e))
    case 1n+p 0n:
      absurd({1n+p == 0n : Nat},false_true(e))
    case 1n+p 1n+q:
      Equal.cong(Nat,Nat,n=>1n+n,p,q,eq_sound(p,q,e))

law le_sound:
  for +a: Nat
  for +b: Nat
  for e: {Nat.is_le(a,b) == True{} : Bool}
  K.Le(a,b)
def le_sound(a,b,e):
  match a b:
    case 0n _:
      Unit{}
    case 1n+p 0n:
      false_true(e)
    case 1n+p 1n+q:
      le_sound(p,q,e)

law and_sound:
  for +a: Bool
  for +b: Bool
  for e: {Bool.and(a,b) == True{} : Bool}
  {a == True{} : Bool} & {b == True{} : Bool}
def and_sound(a,b,e):
  match a:
    case False{}:
      absurd({False{} == True{} : Bool} & {b == True{} : Bool},false_true(e))
    case True{}:
      ({==},e)

law guarded_sound:
  for +flag: Bool
  for -next: Unit -> Bool
  for e: {C.guarded(flag,next) == True{} : Bool}
  {flag == True{} : Bool} & {next(Unit{}) == True{} : Bool}
def guarded_sound(flag,next,e):
  match flag:
    case False{}:
      absurd({False{} == True{} : Bool} & {next(Unit{}) == True{} : Bool},false_true(e))
    case True{}:
      ({==},e)

def equal_more(+d: Nat,+e: Nat,+rest: S.Chunks,+tail: S.Chunks,
  checks: {Nat.is_eq(d,e) == True{} : Bool} & {V.equal(rest,tail) == True{} : Bool},
  ih: {V.equal(rest,tail) == True{} : Bool} -> {rest == tail : S.Chunks}) ->
  {S.More{d,rest} == S.More{e,tail} : S.Chunks}:
  (head,body)=checks
  %eq_sound(d,e,head) : {S.More{d,rest} == S.More{_,tail} : S.Chunks}
  %ih(body) : {S.More{d,rest} == S.More{d,_} : S.Chunks}
  {==}

law equal_sound:
  for +xs: S.Chunks
  for +ys: S.Chunks
  for checked: {V.equal(xs,ys) == True{} : Bool}
  {xs == ys : S.Chunks}
def equal_sound(xs,ys,checked):
  match xs ys:
    case S.End{} S.End{}:
      {==}
    case S.End{} S.More{d,rest}:
      absurd({S.End{} == S.More{d,rest} : S.Chunks},false_true(checked))
    case S.More{d,rest} S.End{}:
      absurd({S.More{d,rest} == S.End{} : S.Chunks},false_true(checked))
    case S.More{+d,+rest} S.More{+e,+tail}:
      equal_more(d,e,rest,tail,and_sound(Nat.is_eq(d,e),V.equal(rest,tail),checked),
        proof=>equal_sound(rest,tail,proof))

def finish_witness(+cut: P.Cut,+xs: S.Chunks,+total: Nat,+target: Nat,
  checks: {Nat.is_eq(P.strict_count(total,cut,target),1n+target) == True{} : Bool} &
    {V.equal(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut))) == True{} : Bool}) ->
  {P.strict_count(total,cut,target) == 1n+target : Nat} &
    {xs == P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut)) : S.Chunks}:
  (strict,choice)=checks
  (eq_sound(P.strict_count(total,cut,target),1n+target,strict),
    equal_sound(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut)),choice))

def outer_witness(+cut: P.Cut,+xs: S.Chunks,+total: Nat,+target: Nat,
  checks: {Nat.is_le(K.length(P.complete(total,cut)),target) == True{} : Bool} &
    {C.guarded(Nat.is_eq(P.strict_count(total,cut,target),1n+target),u=>
      V.equal(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut)))) == True{} : Bool}) ->
  P.Requirement(Some{cut},xs,total,target):
  (fits,rest)=checks
  (le_sound(K.length(P.complete(total,cut)),target,fits),
    finish_witness(cut,xs,total,target,
      guarded_sound(Nat.is_eq(P.strict_count(total,cut,target),1n+target),u=>
        V.equal(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut))),rest)))

def raw_sound(+xs: S.Chunks,+total: Nat,+target: Nat,
  checks: {Nat.is_eq(target,total) == True{} : Bool} & {V.equal(xs,P.raws(total)) == True{} : Bool}) ->
  {target == total : Nat} & {xs == P.raws(total) : S.Chunks}:
  (count,raw)=checks
  (eq_sound(target,total,count),equal_sound(xs,P.raws(total),raw))

law witness_sound:
  for +witness: Maybe<&2,P.Cut>
  for +xs: S.Chunks
  for +total: Nat
  for +target: Nat
  for checked: {V.check_witness(witness,xs,total,target) == True{} : Bool}
  P.Requirement(witness,xs,total,target)
def witness_sound(witness,xs,total,target,checked):
  match witness:
    case None{}:
      raw_sound(xs,total,target,and_sound(Nat.is_eq(target,total),V.equal(xs,P.raws(total)),checked))
    case Some{+cut}:
      outer_witness(cut,xs,total,target,
        guarded_sound(Nat.is_le(K.length(P.complete(total,cut)),target),u=>
          C.guarded(Nat.is_eq(P.strict_count(total,cut,target),1n+target),u=>
            V.equal(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut)))),checked))

law preferred_sound:
  for +xs: S.Chunks
  for +total: Nat
  for +target: Nat
  for checked: {V.valid(xs,total,target) == True{} : Bool}
  P.Preferred(xs,total,target)
def preferred_sound(xs,total,target,checked):
  witness_sound(P.worst(xs,total),xs,total,target,checked)

law eq_refl:
  for +n: Nat
  {Nat.is_eq(n,n) == True{} : Bool}
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
  {Nat.is_eq(a,b) == True{} : Bool}
def eq_complete(a,b,e):
  %e : {Nat.is_eq(a,_) == True{} : Bool}
  eq_refl(a)

law le_complete:
  for +a: Nat
  for +b: Nat
  for witness: K.Le(a,b)
  {Nat.is_le(a,b) == True{} : Bool}
def le_complete(a,b,witness):
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+q:
      {==}
    case 1n+p 0n:
      match witness:
    case 1n+p 1n+q:
      le_complete(p,q,witness)

law and_complete:
  for +a: Bool
  for +b: Bool
  for left: {a == True{} : Bool}
  for right: {b == True{} : Bool}
  {Bool.and(a,b) == True{} : Bool}
def and_complete(a,b,left,right):
  %Equal.sym(Bool,a,True{},left) : {Bool.and(_,b) == True{} : Bool}
  right

law guarded_complete:
  for +flag: Bool
  for -next: Unit -> Bool
  for yes: {flag == True{} : Bool}
  for done: {next(Unit{}) == True{} : Bool}
  {C.guarded(flag,next) == True{} : Bool}
def guarded_complete(flag,next,yes,done):
  %Equal.sym(Bool,flag,True{},yes) : {C.guarded(_,next) == True{} : Bool}
  done

law equal_refl:
  for +xs: S.Chunks
  {V.equal(xs,xs) == True{} : Bool}
def equal_refl(xs):
  match xs:
    case S.End{}:
      {==}
    case S.More{+d,+rest}:
      and_complete(Nat.is_eq(d,d),V.equal(rest,rest),eq_refl(d),equal_refl(rest))

law equal_complete:
  for +xs: S.Chunks
  for +ys: S.Chunks
  for e: {xs == ys : S.Chunks}
  {V.equal(xs,ys) == True{} : Bool}
def equal_complete(xs,ys,e):
  %e : {V.equal(xs,_) == True{} : Bool}
  equal_refl(xs)

def finish_complete(+cut: P.Cut,+xs: S.Chunks,+total: Nat,+target: Nat,
  witness: {P.strict_count(total,cut,target) == 1n+target : Nat} &
    {xs == P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut)) : S.Chunks}) ->
  {C.guarded(Nat.is_eq(P.strict_count(total,cut,target),1n+target),u=>
    V.equal(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut)))) == True{} : Bool}:
  (strict,choice)=witness
  guarded_complete(Nat.is_eq(P.strict_count(total,cut,target),1n+target),u=>
    V.equal(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut))),
    eq_complete(P.strict_count(total,cut,target),1n+target,strict),
    equal_complete(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut)),choice))

def outer_complete(+cut: P.Cut,+xs: S.Chunks,+total: Nat,+target: Nat,
  witness: P.Requirement(Some{cut},xs,total,target)) ->
  {V.check_witness(Some{cut},xs,total,target) == True{} : Bool}:
  (fits,rest)=witness
  guarded_complete(Nat.is_le(K.length(P.complete(total,cut)),target),u=>
    C.guarded(Nat.is_eq(P.strict_count(total,cut,target),1n+target),u=>
      V.equal(xs,P.fill(Nat.sub(target,K.length(P.complete(total,cut))),P.complete(total,cut)))),
    le_complete(K.length(P.complete(total,cut)),target,fits),
    finish_complete(cut,xs,total,target,rest))

def raw_complete(+xs: S.Chunks,+total: Nat,+target: Nat,
  witness: {target == total : Nat} & {xs == P.raws(total) : S.Chunks}) ->
  {Bool.and(Nat.is_eq(target,total),V.equal(xs,P.raws(total))) == True{} : Bool}:
  (count,raw)=witness
  and_complete(Nat.is_eq(target,total),V.equal(xs,P.raws(total)),
    eq_complete(target,total,count),equal_complete(xs,P.raws(total),raw))

law witness_complete:
  for +cut: Maybe<&2,P.Cut>
  for +xs: S.Chunks
  for +total: Nat
  for +target: Nat
  for witness: P.Requirement(cut,xs,total,target)
  {V.check_witness(cut,xs,total,target) == True{} : Bool}
def witness_complete(cut,xs,total,target,witness):
  match cut:
    case None{}:
      raw_complete(xs,total,target,witness)
    case Some{+c}:
      outer_complete(c,xs,total,target,witness)

law preferred_complete:
  for +xs: S.Chunks
  for +total: Nat
  for +target: Nat
  for witness: P.Preferred(xs,total,target)
  {V.valid(xs,total,target) == True{} : Bool}
def preferred_complete(xs,total,target,witness):
  witness_complete(P.worst(xs,total),xs,total,target,witness)
