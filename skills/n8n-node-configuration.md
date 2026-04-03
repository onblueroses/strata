# n8n Node Configuration

Configure nodes correctly on the first try.

## Common Node Patterns

### HTTP Request
| Field | Required | Notes |
|-------|----------|-------|
| Method | Yes | GET, POST, PUT, PATCH, DELETE |
| URL | Yes | Full URL including protocol |
| Authentication | Depends | Use credentials, not hardcoded tokens |
| Headers | Optional | Content-Type auto-set for JSON body |
| Body | POST/PUT/PATCH | JSON, form data, or raw |
| Response Format | Recommended | Set to match API response (JSON, text, binary) |

**Gotcha:** n8n follows redirects by default. Set "Follow Redirects" to false for APIs that use 3xx for status.

### IF Node
| Field | Required | Notes |
|-------|----------|-------|
| Conditions | Yes | Multiple conditions with AND/OR |
| Value 1 | Yes | Expression or fixed value |
| Operation | Yes | equals, not equals, contains, etc. |
| Value 2 | Yes | Comparison value |

**Gotcha:** String comparison is case-sensitive. Use `.toLowerCase()` in expressions for case-insensitive matching.

### Set Node
| Field | Required | Notes |
|-------|----------|-------|
| Mode | Yes | "Manual Mapping" vs "JSON" |
| Fields | Yes | Key-value pairs to set |
| Keep Only Set | Important | false = merge with input, true = replace |

**Gotcha:** "Keep Only Set = true" removes ALL fields not explicitly set. Use false to add/modify fields while preserving the rest.

### Split In Batches
| Field | Required | Notes |
|-------|----------|-------|
| Batch Size | Yes | Number of items per batch (default: 10) |

**Gotcha:** Connect the "loop" output back to the first node in the batch processing chain, NOT back to Split In Batches itself.

### Merge Node
| Mode | Use when |
|------|----------|
| Append | Combine items from two branches into one list |
| Combine by Position | Zip items 1:1 from two branches |
| Combine by Field | Join on a matching field (like SQL JOIN) |
| Choose Branch | Pick one branch based on a condition |

**Gotcha:** "Combine by Position" fails silently when branches have different item counts. The shorter branch's items are padded with empty values.

## Credential Patterns

| Service | Credential type | Notes |
|---------|----------------|-------|
| REST API with token | "Header Auth" or "HTTP Request" | Put token in Authorization header |
| REST API with API key | "Query Auth" or "HTTP Request" | Depends on API (header vs query param) |
| OAuth2 | Service-specific credential | Follow n8n's OAuth setup flow |
| Basic Auth | "HTTP Basic Auth" | Username + password |

**Rule:** Never put credentials in Code nodes or expressions. Always use n8n's credential system.

## Error Handling per Node

Set these in node settings (gear icon):

| Setting | Default | When to change |
|---------|---------|----------------|
| Continue on Fail | false | Set true when failure is expected (e.g., checking if record exists) |
| Retry on Fail | false | Set true for external API calls |
| Max Retries | 3 | Reduce for fast-failing APIs, increase for flaky ones |
| Wait Between Retries | 1000ms | Increase for rate-limited APIs |

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| Hardcoding API keys in HTTP Request URL | Security risk, breaks on rotation | Use credentials |
| Not setting "Continue on Fail" for optional steps | Whole workflow fails if optional step errors | Enable for non-critical paths |
| Using Code node for simple transformations | Overkill, harder to maintain | Use Set node or expressions |
| Ignoring response format setting | n8n guesses wrong, returns raw text | Explicitly set expected format |
