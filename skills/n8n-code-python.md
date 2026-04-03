# n8n Code Node - Python

Write correct Python in n8n's Code node environment.

## Data Access

### Current node input
```python
# Run Once for All Items
items = _input.all()                    # List of dicts with 'json' key
first = _input.first()                  # First item

# Run Once for Each Item
data = _input.item.json                 # Current item's JSON data
```

### Previous node data
```python
webhook_data = _node["Webhook"].item.json       # Each Item mode
all_data = _node["Webhook"].all()               # All Items mode
```

## Output Format

```python
# Run Once for All Items - return list of dicts
return [{"json": {**item.json, "processed": True}} for item in _input.all()]

# Run Once for Each Item - return single dict
return {"json": {"name": data["name"], "processed": True}}
```

## Available Libraries

Standard library modules are available. Common useful ones:
- `json` - JSON parsing/serialization
- `datetime` - Date/time operations
- `re` - Regular expressions
- `math` - Mathematical functions
- `hashlib` - Hashing
- `base64` - Encoding/decoding
- `urllib.parse` - URL manipulation

**Not available**: `requests`, `pandas`, `numpy`, or any pip-installed packages.
Use the JavaScript Code node with `$http.request()` if you need HTTP requests.

## Common Patterns

### Filter items
```python
items = _input.all()
return [item for item in items if item.json.get("status") == "active"]
```

### Aggregate
```python
items = _input.all()
total = sum(item.json.get("amount", 0) for item in items)
return [{"json": {"total": total, "count": len(items)}}]
```

### Date handling
```python
from datetime import datetime, timedelta

now = datetime.now()
yesterday = now - timedelta(days=1)
formatted = now.strftime("%Y-%m-%d")
```

## Limitations

- No third-party packages (requests, pandas, etc.)
- No file system access
- No subprocess/os.system calls
- Limited memory and execution time
- No HTTP requests (use JavaScript Code node instead)

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| `import requests` | Not available in sandbox | Use JS Code node for HTTP |
| `return {"key": "value"}` | Missing `json` wrapper | `return {"json": {"key": "value"}}` |
| `print(data)` | Output not captured | Return debug data in the output |
| `_input.item.json` in All Items mode | Undefined in batch mode | `_input.all()` |
