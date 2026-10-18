import Base
import ./selection.bend as S
import ./CONTRACT.bend as K

# Semantic helpers live in this frozen module, so selector implementation
# changes cannot redefine the quality rule through a shared helper.
def branch(-A: Type,flag: Bool,yes: Unit -> A,no: Unit -> A) -> A:
  match flag:
    case True{}:
      yes(Unit{})
    case False{}:
      no(Unit{})

def concat(xs: S.Chunks,ys: S.Chunks) -> S.Chunks:
  match xs:
    case S.End{}:
      ys
    case S.More{d,rest}:
      S.More{d,concat(rest,ys)}

def raws(n: Nat) -> S.Chunks:
  match n:
    case 0n:
      S.End{}
    case 1n+p:
      S.More{0n,raws(p)}

# Exact reciprocal of compressed-block width / remaining history.
type Cut is Data:
  Cut{depth: Nat, age: Nat}

# Compare dyadic reciprocals without a width*age cross-product.
# For valid U32 blocks every intermediate scaled remainder is <2^31.
def less(+a: Cut, +b: Cut) -> Bool:
  match a b:
    case Cut{+da,+aa} Cut{+db,+ab}:
      +wa=K.width(da)
      +wb=K.width(db)
      +qa=Nat.div(aa,wa)
      +qb=Nat.div(ab,wb)
      +scale=Nat.max(da,db)
      Nat.is_lt(qa,qb) || (Nat.is_eq(qa,qb) &&
        Nat.is_lt(Nat.mul(Nat.mod(aa,wa),K.width(Nat.sub(scale,da))),
          Nat.mul(Nat.mod(ab,wb),K.width(Nat.sub(scale,db)))))

def same(+a: Cut,+b: Cut) -> Bool:
  Bool.not(less(a,b)) && Bool.not(less(b,a))

def minimum(+a: Cut, other: Maybe<&2,Cut>) -> Cut:
  match other:
    case None{}:
      a
    case Some{+b}:
      branch(Cut,less(a,b),u=>a,u=>b)

# Smallest reciprocal is the worst compressed leaf; unit leaves are excluded.
def worst(xs: S.Chunks,+age: Nat) -> Maybe<&2,Cut>:
  match xs:
    case S.End{}:
      None{}
    case S.More{0n,rest}:
      worst(rest,Nat.sub(age,1n))
    case S.More{1n+ +d,rest}:
      Some{minimum(Cut{1n+d,age},worst(rest,Nat.sub(age,K.width(1n+d))))}

# Independent structural U32 dyadic decomposition.
def scale(xs: S.Chunks) -> S.Chunks:
  match xs:
    case S.End{}:
      S.End{}
    case S.More{d,rest}:
      S.More{1n+d,scale(rest)}

def append_raw(xs: S.Chunks) -> S.Chunks:
  match xs:
    case S.End{}:
      S.More{0n,S.End{}}
    case S.More{d,rest}:
      S.More{d,append_raw(rest)}

def seed_word(n: Nat,word: Word(n)) -> S.Chunks:
  match n word:
    case 0n WNil{}:
      S.End{}
    case 1n+p WCon{False{},tail}:
      scale(seed_word(p,tail))
    case 1n+p WCon{True{},tail}:
      append_raw(scale(seed_word(p,tail)))

def seed_u32(total: U32) -> S.Chunks:
  match total:
    case U32{word}:
      seed_word(32n,word)

def seed(total: Nat) -> S.Chunks:
  seed_u32(U32.from_nat(total))

def split(+depth: Nat,+age: Nat,+cut: Cut,strict: Bool) -> Bool:
  match strict:
    case False{}:
      less(Cut{depth,age},cut)
    case True{}:
      less(Cut{depth,age},cut) || same(Cut{depth,age},cut)

def tree(depth: Nat,+age: Nat,+cut: Cut) -> S.Chunks:
  match depth:
    case 0n:
      S.More{0n,S.End{}}
    case 1n+ +d:
      branch(S.Chunks,split(1n+d,age,cut,False{}),
        u=>concat(tree(d,age,cut),tree(d,Nat.sub(age,K.width(d)),cut)),
        u=>S.More{1n+d,S.End{}})

def forest(xs: S.Chunks,+age: Nat,+cut: Cut) -> S.Chunks:
  match xs:
    case S.End{}:
      S.End{}
    case S.More{+d,rest}:
      concat(tree(d,age,cut),forest(rest,Nat.sub(age,K.width(d)),cut))

def complete(+total: Nat,cut: Cut) -> S.Chunks:
  forest(seed(total),total,cut)

# A strict cut may contain billions of raw leaves. Saturate at the supplied
# limit, so checking that it exceeds a budget only visits budget+1 leaves.
def count_tree(depth: Nat,+age: Nat,+cut: Cut,+limit: Nat) -> Nat:
  match depth:
    case 0n:
      Nat.min(1n,limit)
    case 1n+ +d:
      branch(Nat,Nat.is_eq(limit,0n),u=>0n,u=>(
        branch(Nat,split(1n+d,age,cut,True{}),u=>(
          +left=count_tree(d,age,cut,limit)
          Nat.add(left,count_tree(d,Nat.sub(age,K.width(d)),cut,Nat.sub(limit,left)))),
          u=>1n)))

def count_forest(xs: S.Chunks,+age: Nat,+cut: Cut,+limit: Nat) -> Nat:
  match xs:
    case S.End{}:
      0n
    case S.More{+d,rest}:
      branch(Nat,Nat.is_eq(limit,0n),u=>0n,u=>(
        +here=count_tree(d,age,cut,limit)
        Nat.add(here,count_forest(rest,Nat.sub(age,K.width(d)),cut,Nat.sub(limit,here)))))

def strict_count(+total: Nat,cut: Cut,+target: Nat) -> Nat:
  count_forest(seed(total),total,cut,1n+target)

# Spend split fuel from newest blocks to oldest, then newest child to oldest.
# This is a structural policy definition, independent of S.fill/refine.
type Filled is Data:
  Filled{unused: Nat, chunks: S.Chunks}

def block(depth: Nat,+pieces: Nat) -> S.Chunks:
  match depth:
    case 0n:
      S.More{0n,S.End{}}
    case 1n+ +d:
      branch(S.Chunks,Nat.is_le(pieces,1n),u=>S.More{1n+d,S.End{}},u=>(
        +right=Nat.min(K.width(d),Nat.sub(pieces,1n))
        concat(block(d,Nat.sub(pieces,right)),block(d,right))))

def fill_head(+depth: Nat,result: Filled) -> Filled:
  match result:
    case Filled{+unused,tail}:
      +spent=Nat.min(unused,Nat.sub(K.width(depth),1n))
      Filled{Nat.sub(unused,spent),concat(block(depth,1n+spent),tail)}

def fill_result(xs: S.Chunks,fuel: Nat) -> Filled:
  match xs:
    case S.End{}:
      Filled{fuel,S.End{}}
    case S.More{d,rest}:
      fill_head(d,fill_result(rest,fuel))

def filled(result: Filled) -> S.Chunks:
  match result:
    case Filled{unused,xs}:
      xs

def fill(fuel: Nat,xs: S.Chunks) -> S.Chunks:
  filled(fill_result(xs,fuel))

# Operational policy: the smallest threshold with a complete cut that fits,
# followed by newest-first refinement to spend the remaining block budget.
# This states the cut rule independently; it is not a minimax optimality proof.
def Requirement(witness: Maybe<&2,Cut>,+xs: S.Chunks,+total: Nat,+target: Nat) -> Type:
  match witness:
    case None{}:
      {target == total : Nat} & {xs == raws(total) : S.Chunks}
    case Some{+cut}:
      +base=complete(total,cut)
      K.Le(K.length(base),target) &
        ({strict_count(total,cut,target) == 1n+target : Nat} &
          {xs == fill(Nat.sub(target,K.length(base)),base) : S.Chunks})

def Preferred(+xs: S.Chunks,+total: Nat,target: Nat) -> Type:
  Requirement(worst(xs,total),xs,total,target)

# Only status zero claims the preference policy. Recovery statuses promise
# geometry/count via K.Success, and are surfaced as diagnostics by the host.
def MarkedFlag(flag: Bool, result: Maybe<&2,S.Chunks>, +total: Nat, +target: Nat) -> Type:
  match flag:
    case False{}:
      Unit
    case True{}:
      match result:
        case None{}:
          Empty
        case Some{xs}:
          Preferred(xs,total,target)

def Marked(outcome: U32 & Maybe<&2,S.Chunks>, +total: Nat, +target: Nat) -> Type:
  (status,result)=outcome
  MarkedFlag(U32.is_zero(status),result,total,target)
