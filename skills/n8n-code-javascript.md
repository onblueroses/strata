# n8n Code Node - JavaScript

Write correct JavaScript in n8n's Code node environment.

## Execution Modes

| Mode | When to use | `$input` behavior |
|------|-------------|-------------------|
| **Run Once for All Items** | Transform a batch, aggregate, filter | `$input.all()` returns all items as array |
| **Run Once for Each Item** | Per-item logic, API calls per row | `$input.item.json` is current item |

## Data Access

### Current node input
```javascript
// Run Once for All Items
const items = $input.all();           // Array of {json: {...}, binary?: {...}}
const firstItem = $input.first();     // First item
const lastItem = $input.last();       // Last item

// Run Once for Each Item
const data = $input.item.json;        // Current item's JSON data
const index = $input.item.index;      // Current item index (0-based, only in Each Item mode)
```

### Previous node data
```javascript
// By node name
const webhookData = $('Webhook').item.json;          // Each Item mode
const allWebhookData = $('Webhook').all();            // All Items mode
const firstWebhookItem = $('Webhook').first();        // First item from node

// Current workflow execution context
const executionId = $execution.id;
const workflowId = $workflow.id;
const isTestExecution = $execution.mode === 'manual';
```

### Accessing parameters and variables
```javascript
const myParam = $('Set').params.values;      // Node parameters
const envVar = $env.MY_VARIABLE;             // Environment variable (if allowed)
```

## HTTP Requests

Use the built-in helpers - do NOT use `fetch` or `axios`:

```javascript
const response = await $http.request({
  method: 'GET',
  url: 'https://api.example.com/data',
  headers: { 'Authorization': 'Bearer ' + $('Set Credentials').item.json.token },
  qs: { page: 1, limit: 50 },           // Query string parameters
  body: { key: 'value' },               // For POST/PUT
  json: true,                            // Parse response as JSON
  returnFullResponse: false,             // true to get headers + status code
});
```

## Date/Time with Luxon

n8n includes Luxon. Use `DateTime` (already available, no import needed):

```javascript
const now = DateTime.now();
const formatted = now.toFormat('yyyy-MM-dd');
const yesterday = now.minus({ days: 1 });
const parsed = DateTime.fromISO('2026-03-25T10:00:00');
const diff = DateTime.now().diff(parsed, 'hours').hours;
```

## Output Format

Always return an array of objects with `json` property:

```javascript
// Run Once for All Items - return array
return items.map(item => ({
  json: {
    ...item.json,
    processed: true,
    timestamp: DateTime.now().toISO(),
  }
}));

// Run Once for Each Item - return single object
return {
  json: {
    ...data,
    processed: true,
  }
};
```

## Common Patterns

### Filter items
```javascript
const items = $input.all();
return items.filter(item => item.json.status === 'active');
```

### Aggregate/reduce
```javascript
const items = $input.all();
const total = items.reduce((sum, item) => sum + item.json.amount, 0);
return [{ json: { total, count: items.length } }];
```

### Error handling
```javascript
try {
  const response = await $http.request({ url: 'https://api.example.com/data', json: true });
  return [{ json: response }];
} catch (error) {
  // Don't swallow errors silently - let n8n handle them or provide context
  throw new Error(`API request failed: ${error.message}`);
}
```

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| `const axios = require('axios')` | Not available in Code node sandbox | Use `$http.request()` |
| `return { key: 'value' }` | Missing `json` wrapper | `return { json: { key: 'value' } }` |
| `$input.item.json` in All Items mode | Undefined - no single "item" in batch mode | `$input.all()` or `$input.first()` |
| `new Date()` for formatting | Inconsistent across environments | Use Luxon `DateTime` |
| `console.log(data)` | Output goes nowhere useful in n8n | Use `$execution.customData.set()` or return debug data |
