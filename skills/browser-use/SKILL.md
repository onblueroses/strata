---
name: browser-use
version: 0.11.9
description: |
  Browser automation via browser-use CLI. Navigate, click, type, screenshot.
  Supports headless, headed, real Chrome (with logins), and cloud browsers.
  Auto-trigger: when the task requires reusing an existing Chrome session with your logins (use --browser real), OR when an AI agent must reason over an unknown/dynamic page structure. For simple screenshots and visual validation, use Playwright MCP instead (mcp__playwright__*).
allowed-tools:
  - Bash
  - Read
---

# Browser Automation with browser-use CLI

## Common Flag Mistakes (all cause silent failures)

<details>
<summary>Common Flag Mistakes (all cause silent failures)</summary>

These mistakes happen frequently because the CLI's syntax differs from typical tools:

```
WRONG: browser-use https://example.com          # Missing 'open' subcommand!
RIGHT: browser-use open https://example.com      # 'open' is REQUIRED

WRONG: browser-use --headless open <url>         # --headless does NOT exist
RIGHT: browser-use open <url>                    # Headless is the default

WRONG: browser-use --headed --headless open <url># --headless is NOT a flag
RIGHT: browser-use --headed open <url>           # --headed opts INTO visible mode

WRONG: browser-use --url <url>                   # --url does NOT exist
RIGHT: browser-use open <url>                    # URL is a positional arg to 'open'

WRONG: browser-use screenshot --output file.png  # --output does NOT exist
RIGHT: browser-use screenshot file.png           # Path is a positional arg

WRONG: browser-use screenshot --path file.png    # --path does NOT exist
RIGHT: browser-use screenshot file.png           # Path is a positional arg

WRONG: browser-use --save screenshot.png         # --save does NOT exist
RIGHT: browser-use screenshot screenshot.png     # Path is a positional arg to 'screenshot'
```

The ONLY global flags are: `--session`, `--browser`, `--headed`, `--profile`, `--json`, `--api-key`.
Global flags go BEFORE the subcommand. Do NOT invent any other flags.

</details>

## Command Syntax

Every invocation follows this pattern:
```
browser-use [global-options] <SUBCOMMAND> [subcommand-args]
```

The subcommand is ALWAYS required (except `--help`). Never pass a URL directly to `browser-use` without a subcommand.

## Tool Selection - Use the Right Tool

Four browser tools exist. Pick before starting:

| Need | Use |
|------|-----|
| Screenshot or visual validation | **Playwright MCP** (`mcp__playwright__*`) - spawns fresh browser, no extension needed |
| Page requires YOUR login session | **`browser-use --browser real`** (this skill, real mode) |
| AI must reason over unknown/dynamic UI | **`browser-use` CLI** (this skill, default mode) |

Only proceed with this skill if one of the bottom two rows matches. For simple screenshots, use Playwright MCP instead.

## Skip Conditions

- **Skip if** just taking a screenshot or doing visual validation - use Playwright MCP (`mcp__playwright__*`) instead
- **Skip if** browser-use is not installed - tell user to install it first
- **Skip if** the URL is localhost and no dev server is running - start the server first

## Quick Start

<details>
<summary>Quick Start</summary>

```bash
browser-use open https://example.com           # Navigate to URL
browser-use state                              # Get page elements with indices
browser-use click 5                            # Click element by index
browser-use type "Hello World"                 # Type text
browser-use screenshot $HOME/temp/shot.png  # Save screenshot
browser-use close                              # Close browser
```

</details>

## Core Workflow

1. **Navigate**: `browser-use open <url>` - Opens URL (starts browser if needed)
2. **Inspect**: `browser-use state` - Returns clickable elements with indices
3. **Interact**: Use indices from state to interact (`browser-use click 5`, `browser-use input 3 "text"`)
4. **Verify**: `browser-use screenshot <path>` to confirm visual state
5. **Repeat**: Browser stays open between commands
6. **Cleanup**: `browser-use close` when done

## All Commands Reference

<details>
<summary>All Commands Reference</summary>

### Navigation
```bash
browser-use open <url>                    # Navigate to URL (REQUIRED subcommand)
browser-use back                          # Go back in history
browser-use scroll down                   # Scroll down
browser-use scroll up                     # Scroll up
```

### Page State & Screenshots
```bash
browser-use state                         # Get URL, title, and clickable elements
browser-use screenshot                    # Take screenshot (outputs base64)
browser-use screenshot path.png           # Save screenshot to file
browser-use screenshot --full path.png    # Full page screenshot
browser-use get title                     # Get page title
browser-use get html                      # Get page HTML
browser-use get text <index>              # Get element text
browser-use get value <index>             # Get input value
browser-use get bbox <index>              # Get element bounding box
```

### Interactions (use indices from `browser-use state`)
```bash
browser-use click <index>                 # Click element
browser-use dblclick <index>              # Double-click element
browser-use rightclick <index>            # Right-click element
browser-use hover <index>                 # Hover over element
browser-use type "text"                   # Type text into focused element
browser-use input <index> "text"          # Click element, then type text
browser-use keys "Enter"                  # Send keyboard keys
browser-use keys "Control+a"              # Send key combination
browser-use select <index> "option"       # Select dropdown option
```

### Waiting
```bash
browser-use wait selector "div.loaded"    # Wait for CSS selector
browser-use wait text "Success"           # Wait for text to appear
```

### Tab Management
```bash
browser-use switch <tab>                  # Switch to tab by index
browser-use close-tab                     # Close current tab
browser-use close-tab <tab>               # Close specific tab
```

### JavaScript & Data
```bash
browser-use eval "document.title"         # Execute JavaScript, return result
browser-use extract "all product prices"  # Extract data using LLM (requires API key)
```

### Cookies
```bash
browser-use cookies get                   # Get all cookies
browser-use cookies set                   # Set a cookie
browser-use cookies clear                 # Clear cookies
browser-use cookies export file.json      # Export cookies
browser-use cookies import file.json      # Import cookies
```

### Session Management
```bash
browser-use sessions                      # List active sessions
browser-use close                         # Close current session
browser-use close --all                   # Close all sessions
```

</details>

## Global Options

<details>
<summary>Global Options</summary>

These go BEFORE the subcommand:

| Option | Description |
|--------|-------------|
| `--session NAME` | Use named session (default: "default") |
| `--browser MODE` | Browser mode: chromium, real, remote |
| `--headed` | Show browser window (chromium only) |
| `--profile NAME` | Chrome profile (real mode only) |
| `--json` | Output as JSON |
| `--api-key KEY` | Browser-Use API key (for remote/extract/run) |

</details>

## Browser Modes

<details>
<summary>Browser Modes</summary>

```bash
browser-use open <url>                            # Default: headless Chromium
browser-use --headed open <url>                   # Visible Chromium window
browser-use --browser real open <url>             # User's Chrome with login sessions
browser-use --browser remote open <url>           # Cloud browser (requires API key)
```

- **chromium** (default): Fast, isolated, headless by default
- **real**: Uses your Chrome with cookies, extensions, logged-in sessions
- **remote**: Cloud-hosted browser with proxy support (requires BROWSER_USE_API_KEY)

</details>

## Screenshot Best Practices

Always save to a file path (not base64) so the Read tool can display it:
```bash
browser-use screenshot $HOME/temp/myshot.png
```

For full-page captures:
```bash
browser-use screenshot --full $HOME/temp/full.png
```

Use the Read tool to view the screenshot after saving it.

## Examples

<details>
<summary>Examples</summary>

### Form Submission
```bash
browser-use open https://example.com/contact
browser-use state
# Shows: [0] input "Name", [1] input "Email", [2] button "Submit"
browser-use input 0 "John Doe"
browser-use input 1 "john@example.com"
browser-use click 2
browser-use state  # Verify success
```

### Visual Verification of Local Dev Server
```bash
browser-use open http://localhost:3000
browser-use screenshot $HOME/temp/homepage.png
# Use Read tool to view the screenshot
browser-use scroll down
browser-use screenshot $HOME/temp/below-fold.png
browser-use close
```

### Using Real Browser (Logged-In Sessions)
```bash
browser-use --browser real open https://gmail.com
# Uses your actual Chrome with existing login sessions
browser-use state  # Already logged in!
```

</details>

## Tips

1. **Always run `browser-use state` first** to see available elements and their indices
2. **Use `--headed` for debugging** to see what the browser is doing
3. **Sessions persist** - the browser stays open between commands
4. **Use `--json` for parsing** output programmatically
5. **Save screenshots to files** - base64 output is hard to use
6. **Wait for dynamic content** - use `browser-use wait selector/text` before screenshotting SPAs

## Mobile Viewport Emulation

<details>
<summary>Mobile Viewport Emulation</summary>

Use the `mobile-viewport.py` helper script to emulate mobile and tablet viewports via CDP.

### Setting a Mobile Viewport

The script reads a `DEVICE` variable from the browser-use Python namespace. Set it first, then run the file:

```bash
# Set viewport to a device preset (must have a page open first)
browser-use python "DEVICE='iphone-14'" && browser-use python --file $HOME/$STRATA_HOME/skills/browser-use/mobile-viewport.py

# Custom dimensions
browser-use python "DEVICE='custom'; WIDTH=390; HEIGHT=844; DPR=3" && browser-use python --file $HOME/$STRATA_HOME/skills/browser-use/mobile-viewport.py

# Reset back to desktop
browser-use python "DEVICE='desktop'" && browser-use python --file $HOME/$STRATA_HOME/skills/browser-use/mobile-viewport.py
```

### Device Presets

| Preset | Width | Height | DPR | Type |
|--------|-------|--------|-----|------|
| `iphone-se` | 375 | 667 | 2 | Phone |
| `iphone-14` | 393 | 852 | 3 | Phone |
| `iphone-14-max` | 430 | 932 | 3 | Phone |
| `pixel-7` | 412 | 915 | 2.6 | Phone |
| `galaxy-s23` | 360 | 780 | 3 | Phone |
| `ipad-mini` | 768 | 1024 | 2 | Tablet |
| `ipad-air` | 820 | 1180 | 2 | Tablet |

### Mobile Workflow Example

```bash
# 1. Open the page
browser-use open http://localhost:3000

# 2. Set mobile viewport
browser-use python "DEVICE='iphone-14'" && browser-use python --file $HOME/$STRATA_HOME/skills/browser-use/mobile-viewport.py

# 3. Reload to trigger responsive layout
browser-use eval "location.reload()"
browser-use wait text ""  # brief wait for render

# 4. Screenshot mobile view
browser-use screenshot $HOME/temp/mobile.png

# 5. Scroll and capture more
browser-use scroll down
browser-use screenshot $HOME/temp/mobile-below-fold.png

# 6. Reset to desktop when done
browser-use python "DEVICE='desktop'" && browser-use python --file $HOME/$STRATA_HOME/skills/browser-use/mobile-viewport.py
```

### Inline Alternative (No Script)

For quick one-offs without the helper script:

```bash
browser-use python "browser._run(browser._session._cdp_set_viewport(393, 852, device_scale_factor=3.0, mobile=True))"
```

</details>

## Quality Self-Check

After completing browser automation, verify:
1. **Screenshot captured** - did you save at least one screenshot and view it with the Read tool?
2. **Browser closed** - did you run `browser-use close`? Leaving sessions open wastes memory.
3. **Viewport correct** - if you set a mobile viewport, did you reset to desktop before closing?
4. **Dynamic content loaded** - did you wait for SPAs to render before screenshotting?

**DO NOT:**
- Take screenshots before the page has fully loaded (use `browser-use wait` first)
- Leave browser sessions open after completing the task
- Assume element indices are stable across page navigations - re-run `state` after each navigation
- Use `--headed` in automated workflows - only for debugging

## Cleanup

<details>
<summary>Cleanup</summary>

**Always close the browser when done:**

```bash
browser-use close
```

**If a command fails mid-session**, the browser may be left open. Check for stuck sessions:

```bash
browser-use sessions
```

If sessions are listed, close them:

```bash
browser-use close
```

If `close` fails (process crashed), kill the browser process directly:

```bash
pkill -f chrome 2>/dev/null
```

</details>
