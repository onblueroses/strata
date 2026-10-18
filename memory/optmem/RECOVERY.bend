import Base
import ./selection.bend as S

# Set-bit forest in descending width order. The representation itself gives
# the canonical aligned binary decomposition of a U32 total.
def bitcount(n: Nat, word: Word(n)) -> Nat:
  match n word:
    case 0n WNil{}:
      0n
    case 1n+p WCon{False{}, tail}:
      bitcount(p, tail)
    case 1n+p WCon{True{}, tail}:
      1n+bitcount(p, tail)

def scale(xs: S.Chunks) -> S.Chunks:
  match xs:
    case S.End{}:
      S.End{}
    case S.More{d, rest}:
      S.More{1n+d, scale(rest)}

def append_raw(xs: S.Chunks) -> S.Chunks:
  match xs:
    case S.End{}:
      S.More{0n, S.End{}}
    case S.More{d, rest}:
      S.More{d, append_raw(rest)}

def seed_word(n: Nat, word: Word(n)) -> S.Chunks:
  match n word:
    case 0n WNil{}:
      S.End{}
    case 1n+p WCon{False{}, tail}:
      scale(seed_word(p, tail))
    case 1n+p WCon{True{}, tail}:
      append_raw(scale(seed_word(p, tail)))

def recover_word(+word: Word(32n), +budget: Nat) -> S.Chunks:
  +total=Word.to_nat(32n,word)
  +minimum=bitcount(32n,word)
  +target=Nat.max(minimum,Nat.min(total,budget))
  S.fill(Nat.sub(target,minimum),seed_word(32n,word))

# Construct one aligned block with exactly the requested number of pieces.
# Once the newer half is raw, spend any remaining pieces in the older half.
def block(depth: Nat, +pieces: Nat) -> S.Chunks:
  match depth:
    case 0n:
      S.More{0n,S.End{}}
    case 1n+p:
      +d=p
      S.branch(S.Chunks,Nat.is_le(pieces,1n),
        u => S.More{1n+d,S.End{}},
        u => (
          +right=Nat.min(S.width(d),Nat.sub(pieces,1n))
          +left=Nat.sub(pieces,right)
          S.concat(block(d,left),block(d,right))))

# Traverse the small set-bit forest once, allocating splits from newest to
# oldest. Work scales with output size rather than rescanning every raw tail.
def fill_fast(xs: S.Chunks, +fuel: Nat) -> S.Chunks:
  match xs:
    case S.End{}:
      S.End{}
    case S.More{+d,+rest}:
      +capacity=Nat.sub(S.mass(rest),S.length(rest))
      +recent=Nat.min(fuel,capacity)
      +older=Nat.sub(fuel,recent)
      S.concat(block(d,1n+older),fill_fast(rest,recent))

def recover_fast_word(+word: Word(32n), +budget: Nat) -> S.Chunks:
  +total=Word.to_nat(32n,word)
  +minimum=bitcount(32n,word)
  +target=Nat.max(minimum,Nat.min(total,budget))
  fill_fast(seed_word(32n,word),Nat.sub(target,minimum))
