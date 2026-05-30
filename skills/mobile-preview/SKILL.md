---
name: mobile-preview
version: 1.0.0
description: |
  Quick mobile viewport screenshots. Opens a URL (or uses current page),
  sets a mobile viewport, takes screenshots, and optionally resets to desktop.
  Manual: user invokes to check mobile responsiveness of a specific URL.
allowed-tools:
  - Bash
  - Read
---

# Mobile Preview

Take mobile viewport screenshots of any URL with a single command.

## Skip Conditions

- **Skip if** no URL provided AND no active browser session - ask the user what to preview
- **Skip if** browser-use is not installed (`browser-use --version` fails)
- **Skip if** the task has no visual component (e.g. backend API work, CLI tools)

## Priority Mode

**When to use:** `--quick` flag, or user just wants a fast sanity check.

**Quick mode:** Single device (iphone-14), top-of-page screenshot only, no scroll shots, no viewport reset. Skip steps 6-7.

---

## Common Mistakes (with reasoning)

- **Don't screenshot before page load** - React hydration, lazy images, and web fonts all load asynchronously. A screenshot taken during load captures a broken intermediate state that doesn't reflect what users see.
- **Don't leave the viewport in mobile mode** - the browser session persists. If the next task opens the same session, it silently inherits the mobile viewport, producing confusing results that are hard to debug.
- **Don't assume localhost is running** - check first with curl or browser-use open. A screenshot of a connection-refused page wastes time and looks like a tool failure.
- **Don't take more than 2 scroll-depth screenshots per device** - diminishing returns. Above-fold + one scroll captures the critical responsive breakpoints; more just burns tokens reviewing similar content.
- **Don't report "looks good" without checking specifics** - overflow, text truncation, and touch target sizes are the three things that break on mobile but look fine on desktop. If you don't check these, the preview is theater, not testing.

---

## Instructions

<details>
<summary>Instructions</summary>

When `/mobile-preview` is invoked, follow this workflow:

### 1. Parse Arguments

The user may provide:
- A URL to open (or nothing, to use the current page)
- A device name (default: `iphone-14`)
- Multiple devices separated by commas (e.g., `iphone-14,ipad-mini`)

Examples:
- `/mobile-preview http://localhost:3000` - iPhone 14 preview of localhost
- `/mobile-preview http://localhost:3000 pixel-7` - Pixel 7 preview
- `/mobile-preview iphone-se,ipad-air` - Two devices, current page
- `/mobile-preview http://localhost:3000 iphone-14,ipad-mini,pixel-7` - Multiple devices

### 2. Open Page (if URL provided)

```bash
browser-use open <url>
```

If no URL given and no browser session is active, ask the user for a URL.

### 3. Set Mobile Viewport

For each device requested:

```bash
browser-use python "DEVICE='<device-name>'" && browser-use python --file $HOME/$STRATA_HOME/skills/browser-use/mobile-viewport.py
```

### 4. Reload and Wait

After setting the viewport, reload the page so responsive CSS recalculates:

```bash
browser-use eval "location.reload()"
```

Wait briefly for rendering to settle:

```bash
browser-use wait text ""
```

### 5. Take Screenshots

Take above-the-fold screenshot:

```bash
browser-use screenshot $HOME/temp/mobile-<device>-top.png
```

Then scroll down and capture below the fold:

```bash
browser-use scroll down
browser-use screenshot $HOME/temp/mobile-<device>-scroll.png
```

Use the Read tool to view each screenshot immediately after taking it.

### 6. Multiple Devices

If multiple devices were requested, repeat steps 3-5 for each device. Use the device name in the filename to differentiate.

### 7. Restore Desktop

After all screenshots are taken, reset the viewport:

```bash
browser-use python "DEVICE='desktop'" && browser-use python --file $HOME/$STRATA_HOME/skills/browser-use/mobile-viewport.py
```

### 8. Report

Summarize what was captured using this format:

```
MOBILE PREVIEW: [URL]
====================
Devices: [list]
Screenshots: [count] saved to $HOME/temp/

Issues found:
  [HIGH] Horizontal overflow on [element] at [device] viewport
  [MEDIUM] Text truncated in [element] - needs line-clamp or responsive font
  [LOW] Touch target too small: [element] is [N]px (min 44px recommended)

No issues found. / [N] issues need attention.
```

</details>

---

## Quality Self-Check

After taking all screenshots and before reporting:
1. **Screenshots captured** - did you actually save files, not just describe what you'd do?
2. **Page fully loaded** - did you wait for dynamic content (React hydration, lazy images, fonts)?
3. **Viewport reset** - is the browser back to desktop mode? (skip check if `--quick`)
4. **Overflow checked** - did you look for horizontal scroll bars or content clipping?
5. **Touch targets checked** - are buttons/links at least 44px tap target?

---

## Available Device Presets

| Preset | Width | Height | DPR | Type |
|--------|-------|--------|-----|------|
| `iphone-se` | 375 | 667 | 2 | Phone |
| `iphone-14` | 393 | 852 | 3 | Phone |
| `iphone-14-max` | 430 | 932 | 3 | Phone |
| `pixel-7` | 412 | 915 | 2.6 | Phone |
| `galaxy-s23` | 360 | 780 | 3 | Phone |
| `ipad-mini` | 768 | 1024 | 2 | Tablet |
| `ipad-air` | 820 | 1180 | 2 | Tablet |

## Notes

- The browser session persists after the preview. Run `browser-use close` when fully done.
- For custom dimensions: `browser-use python "DEVICE='custom'; WIDTH=390; HEIGHT=844; DPR=3" && browser-use python --file $HOME/$STRATA_HOME/skills/browser-use/mobile-viewport.py`
- Screenshots go to `$HOME/temp/` - check that this directory exists.
- If testing a local dev server, make sure it's running before invoking this skill.
