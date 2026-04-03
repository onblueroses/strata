# Browser Automation

Choose the right browser tool, then automate efficiently.

## Tool Selection

| Scenario | Tool | Why |
|----------|------|-----|
| Screenshot / visual check | MCP browser tool | Fastest, lowest token cost |
| Headless testing | Playwright | Reliable, scriptable |
| Form filling / interaction | Playwright or browser-use | Depends on complexity |
| Need logged-in session | Real browser (browser-use) | Preserves cookies/auth |
| AI must reason about dynamic page | browser-use with AI mode | LLM analyzes page content |

## Screenshot Pattern

```
1. Navigate to URL
2. Wait for load (network idle or specific element)
3. Set viewport if needed (mobile: 375x667, desktop: 1440x900)
4. Screenshot
5. Analyze result
```

**Always wait for the page to be ready.** Screenshots of loading states are useless.

## Interaction Pattern

```
1. Navigate to page
2. Wait for target element to be visible
3. Interact (click, type, select)
4. Wait for response (network request, DOM change, navigation)
5. Verify result (screenshot, check element text, check URL)
```

**Always verify after interaction.** "I clicked the button" means nothing if you don't
check what happened next.

## Common Tasks

### Fill and submit a form
1. Navigate to form page
2. Fill each field (use tab order or explicit selectors)
3. Screenshot before submit (for verification)
4. Submit
5. Wait for response
6. Screenshot result

### Extract data from a page
1. Navigate to page
2. Wait for content to load
3. Extract text/attributes from target elements
4. Return structured data

### Test responsive layout
1. Navigate to page at desktop viewport (1440px)
2. Screenshot
3. Resize to tablet (768px)
4. Screenshot
5. Resize to mobile (375px)
6. Screenshot
7. Compare for layout issues

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| Screenshotting before page loads | Captures loading spinner, not content | Wait for network idle or specific element |
| Clicking without verifying | Don't know if the click worked | Check DOM state or screenshot after click |
| Using heavy automation for a simple screenshot | Overkill | Use the simplest tool that works |
| Not setting viewport before screenshot | Get whatever size the browser happens to be | Set explicit viewport dimensions |
| Leaving browser processes running | Resource leak | Close/cleanup after automation |

## Quality Self-Check

1. Chose the right tool for the task?
2. Waited for page load before interacting?
3. Verified results after every interaction?
4. Set viewport dimensions explicitly?
5. Cleaned up browser processes?
