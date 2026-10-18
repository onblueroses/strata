import Base
import ./Policy.bend as P

def bit(s: String) -> Maybe<&2, Bool>:
  match s:
    case SCon{'0', SNil{}}:
      Some{False{}}
    case SCon{'1', SNil{}}:
      Some{True{}}
    case _:
      None{}

def visibility(b: Bool) -> P.Visibility:
  match b:
    case False{}:
      P.Unproven{}
    case True{}:
      P.Private{}

def show_plan(p: P.Plan) -> String:
  match p:
    case P.Skip{}:
      "skip"
    case P.Secrets{}:
      "secrets"
    case P.All{}:
      "all"

def show_verdict(v: P.Verdict) -> String:
  match v:
    case P.Allow{}:
      "allow"
    case P.DenyFinding{}:
      "finding"
    case P.DenyFailure{}:
      "failure"

def show_visibility(v: P.Visibility) -> String:
  match v:
    case P.Private{}:
      "1"
    case P.Unproven{}:
      "0"

def read_plan(s: String) -> Maybe<&2, P.Plan>:
  match s:
    case SCon{'0', SNil{}}:
      Some{P.Skip{}}
    case SCon{'1', SNil{}}:
      Some{P.Secrets{}}
    case SCon{'2', SNil{}}:
      Some{P.All{}}
    case _:
      None{}

def read_scan(s: String) -> Maybe<&2, P.Scan>:
  match s:
    case SCon{'0', SNil{}}:
      Some{P.NotScanned{}}
    case SCon{'1', SNil{}}:
      Some{P.Clean{}}
    case SCon{'2', SNil{}}:
      Some{P.Findings{}}
    case SCon{'3', SNil{}}:
      Some{P.Failed{}}
    case _:
      None{}

def read_evidence(s: String, scan: P.Scan) -> Maybe<&2, P.Evidence>:
  match s:
    case SCon{'0', SNil{}}:
      Some{P.NoEvidence{}}
    case SCon{'1', SNil{}}:
      Some{P.SecretsEvidence{scan}}
    case SCon{'2', SNil{}}:
      Some{P.AllEvidence{scan}}
    case _:
      None{}

# Exact, finite wire grammar. Nothing from command text or file content is sent here.
def request(fields: List<&2, String>) -> Maybe<&2, String>:
  match fields:
    case SCon{'p', SNil{}} <> a <> b <> c <> Nil{}:
      do Maybe<&2, String>:
        ack : Bool <- bit(a)
        publishes : Bool <- bit(b)
        private : Bool <- bit(c)
        return show_plan(P.plan(ack, publishes, visibility(private)))
    case SCon{'f', SNil{}} <> p <> c <> s <> Nil{}:
      do Maybe<&2, String>:
        plan : P.Plan <- read_plan(p)
        scan : P.Scan <- read_scan(s)
        evidence : P.Evidence <- read_evidence(c, scan)
        return show_verdict(P.checked_finish(plan, evidence))
    case SCon{'q', SNil{}} <> a <> b <> Nil{}:
      do Maybe<&2, String>:
        state : Bool <- bit(a)
        target : Bool <- bit(b)
        return show_visibility(P.fold(visibility(state), visibility(target)))
    case _:
      None{}

def emit(result: Maybe<&2, String>) -> IO(Unit):
  match result:
    case None{}:
      IO.die(Unit, 3, "invalid privacy request")
    case Some{text}:
      IO.print(text)

def main() -> IO(Unit):
  do IO<Unit>:
    text : String <- IO.try(String, IO.get_env("PRIVACY_BEND_REQUEST"))
    emit(request(String.split(text, ':')))
