import Base
import ./Policy.bend as P

# Requirements v2: this predicate is specified here rather than by mutable
# Policy.private_targets or the exported Policy.fold.
def all_private(evidence: List<P.Visibility>) -> Bool:
  match evidence:
    case Nil{}:
      True{}
    case P.Private{} <> tail:
      all_private(tail)
    case P.Unproven{} <> _:
      False{}

def private_visibility(known: Bool) -> P.Visibility:
  match known:
    case True{}:
      P.Private{}
    case False{}:
      P.Unproven{}

# Requirements preserve the existing policy, including its successful cases.
law acknowledged:
  for publishes: Bool
  for visibility: P.Visibility
  for scan: P.Scan
  {P.decide(True{}, publishes, visibility, scan) == P.Allow{} : P.Verdict}

law nonpublication:
  for ack: Bool
  for visibility: P.Visibility
  for scan: P.Scan
  {P.decide(ack, False{}, visibility, scan) == P.Allow{} : P.Verdict}

law private_scan:
  {P.plan(False{}, True{}, P.Private{}) == P.Secrets{} : P.Plan}

law unproven_scan:
  {P.plan(False{}, True{}, P.Unproven{}) == P.All{} : P.Plan}

law clean_publication:
  for visibility: P.Visibility
  {P.decide(False{}, True{}, visibility, P.Clean{}) == P.Allow{} : P.Verdict}

law findings_refuse:
  for visibility: P.Visibility
  {P.decide(False{}, True{}, visibility, P.Findings{}) == P.DenyFinding{} : P.Verdict}

law scan_failure_refuses:
  for visibility: P.Visibility
  {P.decide(False{}, True{}, visibility, P.Failed{}) == P.DenyFailure{} : P.Verdict}

law absent_scan_refuses:
  for visibility: P.Visibility
  {P.decide(False{}, True{}, visibility, P.NotScanned{}) == P.DenyFailure{} : P.Verdict}


law unproven_sticky:
  for evidence: List<P.Visibility>
  {P.targets(evidence, P.Unproven{}) == P.Unproven{} : P.Visibility}

law all_private_success:
  for count: Nat
  {P.targets(P.private_targets(count), P.Private{}) == P.Private{} : P.Visibility}

law uncertain_target_refuses_private_class:
  for state: P.Visibility
  for tail: List<P.Visibility>
  {P.targets(P.Unproven{} <> tail, state) == P.Unproven{} : P.Visibility}

# These four transitions protect the operation exported into the shell table.
law fold_private_private:
  {P.fold(P.Private{}, P.Private{}) == P.Private{} : P.Visibility}

law fold_private_unproven:
  {P.fold(P.Private{}, P.Unproven{}) == P.Unproven{} : P.Visibility}

law fold_unproven_private:
  {P.fold(P.Unproven{}, P.Private{}) == P.Unproven{} : P.Visibility}

law fold_unproven_unproven:
  {P.fold(P.Unproven{}, P.Unproven{}) == P.Unproven{} : P.Visibility}

law aggregate_exact:
  for evidence: List<P.Visibility>
  {P.targets(evidence, P.Private{}) == private_visibility(all_private(evidence)) : P.Visibility}

# The exported finish operation must match the scanner's reported coverage.
law all_rejects_secrets_evidence:
  for scan: P.Scan
  {P.checked_finish(P.All{}, P.SecretsEvidence{scan}) == P.DenyFailure{} : P.Verdict}

law secrets_rejects_all_evidence:
  for scan: P.Scan
  {P.checked_finish(P.Secrets{}, P.AllEvidence{scan}) == P.DenyFailure{} : P.Verdict}

law all_rejects_missing_evidence:
  {P.checked_finish(P.All{}, P.NoEvidence{}) == P.DenyFailure{} : P.Verdict}

law secrets_rejects_missing_evidence:
  {P.checked_finish(P.Secrets{}, P.NoEvidence{}) == P.DenyFailure{} : P.Verdict}

law all_accepts_matching_clean:
  {P.checked_finish(P.All{}, P.AllEvidence{P.Clean{}}) == P.Allow{} : P.Verdict}

law secrets_accepts_matching_clean:
  {P.checked_finish(P.Secrets{}, P.SecretsEvidence{P.Clean{}}) == P.Allow{} : P.Verdict}

law all_refuses_matching_findings:
  {P.checked_finish(P.All{}, P.AllEvidence{P.Findings{}}) == P.DenyFinding{} : P.Verdict}

law secrets_refuses_matching_findings:
  {P.checked_finish(P.Secrets{}, P.SecretsEvidence{P.Findings{}}) == P.DenyFinding{} : P.Verdict}

law all_refuses_matching_failure:
  {P.checked_finish(P.All{}, P.AllEvidence{P.Failed{}}) == P.DenyFailure{} : P.Verdict}

law secrets_refuses_matching_failure:
  {P.checked_finish(P.Secrets{}, P.SecretsEvidence{P.Failed{}}) == P.DenyFailure{} : P.Verdict}
