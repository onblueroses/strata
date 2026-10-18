import Base
import ./Policy.bend as P
import ./LAWS.bend as Laws

def Laws.acknowledged(publishes, visibility, scan):
  {==}

def Laws.nonpublication(ack, visibility, scan):
  match ack:
    case False{}:
      {==}
    case True{}:
      {==}

def Laws.private_scan():
  {==}

def Laws.unproven_scan():
  {==}

def Laws.clean_publication(visibility):
  match visibility:
    case P.Private{}:
      {==}
    case P.Unproven{}:
      {==}

def Laws.findings_refuse(visibility):
  match visibility:
    case P.Private{}:
      {==}
    case P.Unproven{}:
      {==}

def Laws.scan_failure_refuses(visibility):
  match visibility:
    case P.Private{}:
      {==}
    case P.Unproven{}:
      {==}

def Laws.absent_scan_refuses(visibility):
  match visibility:
    case P.Private{}:
      {==}
    case P.Unproven{}:
      {==}


def Laws.unproven_sticky(evidence):
  match evidence:
    case Nil{}:
      {==}
    case h <> t:
      Laws.unproven_sticky(t)

def Laws.all_private_success(count):
  match count:
    case 0n:
      {==}
    case 1n+p:
      Laws.all_private_success(p)

def Laws.uncertain_target_refuses_private_class(state, tail):
  match state:
    case P.Private{}:
      Laws.unproven_sticky(tail)
    case P.Unproven{}:
      Laws.unproven_sticky(tail)

def Laws.fold_private_private():
  {==}

def Laws.fold_private_unproven():
  {==}

def Laws.fold_unproven_private():
  {==}

def Laws.fold_unproven_unproven():
  {==}

def Laws.aggregate_exact(evidence):
  match evidence:
    case Nil{}:
      {==}
    case P.Private{} <> tail:
      Laws.aggregate_exact(tail)
    case P.Unproven{} <> tail:
      Laws.unproven_sticky(tail)

def Laws.all_rejects_secrets_evidence(scan):
  {==}

def Laws.secrets_rejects_all_evidence(scan):
  {==}

def Laws.all_rejects_missing_evidence():
  {==}

def Laws.secrets_rejects_missing_evidence():
  {==}

def Laws.all_accepts_matching_clean():
  {==}

def Laws.secrets_accepts_matching_clean():
  {==}

def Laws.all_refuses_matching_findings():
  {==}

def Laws.secrets_refuses_matching_findings():
  {==}

def Laws.all_refuses_matching_failure():
  {==}

def Laws.secrets_refuses_matching_failure():
  {==}
