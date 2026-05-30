<!-- keywords: colab, google colab, rclone, gdrive, google drive, gpu training, notebook, jupyter, T4 -->
# Google Colab via rclone + Drive

The only reliable automated path to Colab from Claude Code. Browser automation (surf, Playwright, Chrome DevTools MCP, ydotool) all fail on Colab's heavy DOM + Wayland HiDPI. The Colab MCP only has trace/fail/sleep - no cell execution.

## Quick Nav

| Task | Section |
|------|---------|
| Upload notebook to Colab | [Upload & Open](#upload--open) |
| First-time setup | [Setup](#setup) |
| Upload training data | [Upload & Open](#upload--open) |
| Modify notebook for Drive | [Notebook Pattern](#notebook-pattern) |

## Setup

One-time. rclone is already installed and authenticated.

```bash
# Already done:
sudo pacman -S rclone
rclone config create gdrive drive  # opens browser for Google OAuth
```

Config lives at `~/.config/rclone/rclone.conf`. The `gdrive` remote is ready.

## Upload & Open

```bash
# Upload notebook + data to Drive root
rclone copy path/to/notebook.ipynb gdrive:
rclone copy path/to/data.jsonl gdrive:

# Get file ID
rclone lsjson gdrive: --include "notebook.ipynb" | python -c "import json,sys; print(json.load(sys.stdin)[-1]['ID'])"

# Open in Colab (in user's real Chrome, already logged in)
xdg-open "https://colab.research.google.com/drive/FILE_ID"
```

Then in Colab: Runtime > Change runtime type > T4 GPU > Run all.

## Notebook Pattern

Notebooks that load data from Drive should mount Drive, not use `files.upload()`:

```python
from google.colab import drive
drive.mount('/content/drive')

DATA_PATH = '/content/drive/MyDrive/final.jsonl'
OUT_DIR = '/content/model-output'
```

Save outputs to `/content/model-output/` (local to Colab VM), then download:
```python
from google.colab import files
files.download('/content/model-output/model.onnx')
```

Or save back to Drive:
```python
import shutil
shutil.copy('/content/model-output/model.onnx', '/content/drive/MyDrive/')
```

## Autonomous Execution (colab_runner.py)

The full autonomous path: upload + open + set T4 + run all + handle auth. Requires `--remote-debugging-port=9222` in `~/.config/chromium-flags.conf` (already configured).

```bash
# Full autonomous run (uploads to Drive, opens in Colab, sets T4, runs all)
python Work/hackathon-agora/scripts/colab_runner.py path/to/notebook.ipynb

# Test Chrome CDP connection
python Work/hackathon-agora/scripts/colab_runner.py --test
```

**How it works:**
1. `rclone copy notebook.ipynb gdrive:` (uploads to Drive)
2. Playwright `connect_over_cdp("http://127.0.0.1:9222")` (attaches to real Chrome with Google session)
3. Opens `colab.research.google.com/drive/{file_id}` in new tab
4. Command palette (Ctrl+Shift+P) > "change runtime" > click T4 GPU > Tab*5+Enter (Save)
5. Ctrl+F9 (Run All)
6. Handles Drive auth popup (Continue > Continue on consent page)
7. Monitors cell execution status

**Key gotcha:** Colab uses Material Design web components (`mwc-dialog`) with shadow DOM. Normal Playwright `click("text=Save")` fails because the button is invisible to the DOM walker. Fix: keyboard navigation (Tab to Save button, then Enter).

## What Doesn't Work (Don't Retry)

- **Colab MCP**: only has `trace`, `fail`, `sleep`. No cell editing or execution.
- **surf / agent-browser**: spawns headless Chromium, not logged into Google. Can't authenticate.
- **Playwright MCP plugin**: spawns its own browser, no Google session. Use `connect_over_cdp` to real Chrome instead.
- **ydotool clicks on Colab**: Colab's DOM is too heavy, coordinate-based clicking is unreliable on HiDPI Wayland.
- **Direct DOM click on Save button**: shadow DOM blocks it. Use Tab+Enter keyboard navigation instead.

## Useful rclone Commands

```bash
rclone ls gdrive:                          # list Drive root
rclone lsjson gdrive: --include "*.ipynb"  # JSON with file IDs
rclone copy gdrive:model.onnx ./           # download from Drive
rclone deletefile gdrive:old-notebook.ipynb # delete
rclone mkdir gdrive:hackathon              # create folder
rclone copy file.ipynb gdrive:hackathon/   # upload to folder
```
