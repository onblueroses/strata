import Base

# Only evidence collected by the surrounding gate enters this pure policy.
# Unproven includes public, unknown, failed lookup and mixed destinations.
type Visibility is Data:
  Private{}
  Unproven{}

type Plan is Data:
  Skip{}
  Secrets{}
  All{}

# This is the outcome of the scan selected by Plan, not an arbitrary raw scan.
type Scan is Data:
  NotScanned{}
  Clean{}
  Findings{}
  Failed{}

# A scan result is usable only with evidence of the classes actually selected by
# the scanner. NoEvidence covers malformed/missing scanner reports as well.
type Evidence is Data:
  NoEvidence{}
  SecretsEvidence{scan: Scan}
  AllEvidence{scan: Scan}

type Verdict is Data:
  Allow{}
  DenyFinding{}
  DenyFailure{}

def plan(ack: Bool, publishes: Bool, visibility: Visibility) -> Plan:
  match ack publishes visibility:
    case True{} _ _:
      Skip{}
    case False{} False{} _:
      Skip{}
    case False{} True{} Private{}:
      Secrets{}
    case False{} True{} Unproven{}:
      All{}

def checked_finish(plan: Plan, evidence: Evidence) -> Verdict:
  match plan evidence:
    case Skip{} _:
      Allow{}
    case Secrets{} SecretsEvidence{Clean{}}:
      Allow{}
    case All{} AllEvidence{Clean{}}:
      Allow{}
    case Secrets{} SecretsEvidence{Findings{}}:
      DenyFinding{}
    case All{} AllEvidence{Findings{}}:
      DenyFinding{}
    case Secrets{} _:
      DenyFailure{}
    case All{} _:
      DenyFailure{}

# Keep the original semantic decide laws as requirements. The exported runtime
# uses checked_finish, whose evidence coverage is independently reported.
def finish(plan: Plan, scan: Scan) -> Verdict:
  match plan:
    case Skip{}:
      checked_finish(Skip{}, NoEvidence{})
    case Secrets{}:
      checked_finish(Secrets{}, SecretsEvidence{scan})
    case All{}:
      checked_finish(All{}, AllEvidence{scan})

def decide(ack: Bool, publishes: Bool, visibility: Visibility, scan: Scan) -> Verdict:
  finish(plan(ack, publishes, visibility), scan)


def fold(state: Visibility, target: Visibility) -> Visibility:
  match state target:
    case Private{} Private{}:
      Private{}
    case _ _:
      Unproven{}

def targets(evidence: List<Visibility>, state: Visibility) -> Visibility:
  match evidence:
    case Nil{}:
      state
    case h <> t:
      targets(t, fold(state, h))

def private_targets(n: Nat) -> List<Visibility>:
  match n:
    case 0n:
      Nil{}
    case 1n+p:
      Private{} <> private_targets(p)
