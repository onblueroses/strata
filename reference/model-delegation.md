# Model Delegation

## Coequal operators

Primary Claude, Codex, and the user-facing DeepSeek primary have equal task coverage and authority. A delegated role receives only the authority granted in its brief.

## Native subscription tiers

Use the current native Codex catalog through the subscription-backed OpenAI provider. The inspected installation reported ChatGPT authentication with the default OpenAI provider on the snapshot date; treat that as dated evidence and verify the provider before each launch or spawn. Do not use or silently fall back to a disallowed provider.

Choose the tier by work:

| Work | Tier |
| --- | --- |
| Load-bearing implementation or adversarial review | strong |
| Bounded implementation or systems research | bounded |
| Mechanical work or focused lookup | mechanical |

If a named role is unavailable, use an available native agent with the same tier and an explicit role brief. Runtime mechanics and model names are deployment details, not portable assumptions.

## Brief and acceptance

Begin with the goal and a checkable success condition. Include the relevant evidence, exact file ownership, allowed side effects, known failure modes, and a stopping condition. Require the artifact or findings, verification evidence, and unresolved gaps.

Keep research and review read-only unless implementation is authorized. Assign independent work disjoint scopes. Recheck the working tree and shared task state after an interruption or handoff. The primary checks the result against the actual objective; a passing command or confident report is evidence, not acceptance.

Scale independent review to the failure cost. For security, permissions, production behavior, data integrity, or hard-to-reverse changes, return findings as P0 to P3 with file, line range, failure mode, and fix. Use proportionate checks for ordinary reversible work.

## Memory and task boundaries

Delegates return canonical memory candidates to the primary. They do not settle append-only memory or task-ledger state. The primary resolves conflicts using the current exact record and records material follow-through in the operator-supplied task ledger.

Check sealed decisions before reopening a direction. Reopen only when the recorded trigger fires and new evidence beats the recorded reason.
