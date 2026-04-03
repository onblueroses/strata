# n8n Validation Expert

Diagnose and fix workflow validation issues.

## Common Validation Errors

### Connection errors
| Error | Cause | Fix |
|-------|-------|-----|
| "Node has no input connection" | Orphaned node | Connect it or delete it |
| "Node has no output connection" | Dead-end node (unless it's a final node) | Connect to next step or mark as endpoint |
| "Duplicate connection" | Two wires between same nodes | Remove the duplicate |

### Parameter errors
| Error | Cause | Fix |
|-------|-------|-----|
| "Parameter required" | Mandatory field empty | Fill the required field |
| "Invalid expression" | Syntax error in {{ }} expression | Check expression syntax (see n8n-expression-syntax skill) |
| "Reference to unknown node" | `$('Node Name')` references deleted/renamed node | Update the reference |
| "Credential not found" | Credential was deleted or not shared | Recreate or share the credential |

### Execution errors
| Error | Cause | Fix |
|-------|-------|-----|
| "Item has no property" | Accessing `$json.field` that doesn't exist | Add null check or ensure upstream provides the field |
| "Cannot read property of undefined" | Chained access on missing data | Use optional access pattern or Code node with checks |
| "429 Too Many Requests" | API rate limit hit | Add Wait node between iterations, reduce batch size |

## Validation Loop Pattern

When building or modifying workflows:

1. **Save** the workflow
2. **Check** for validation warnings (yellow triangles on nodes)
3. **Test** with pinned data (click "Test Workflow" or test individual nodes)
4. **Fix** errors from innermost nodes outward
5. **Repeat** until clean

**Order matters:** Fix connection errors first, then parameter errors, then execution errors.
Downstream errors often resolve when upstream nodes are fixed.

## False Positives

Some warnings are informational, not errors:

| Warning | When it's OK |
|---------|-------------|
| "Node has no input" | Trigger nodes (Schedule, Webhook) don't need input |
| "Expression references node not connected" | If using `$('Node')` for a node that runs in parallel paths |
| "Credential test failed" | If credentials work in execution but fail in test (some APIs restrict test endpoints) |

## Debugging Strategy

1. **Isolate**: Test one node at a time using "Execute Node"
2. **Pin data**: Pin known-good test data on trigger nodes for reproducibility
3. **Check types**: Expression returns string but node expects number? Use `parseInt()` / `parseFloat()`
4. **Check timing**: Webhook tests require the workflow to be active and listening
5. **Check execution log**: Previous executions show exactly where and why failures occurred
