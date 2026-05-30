"""
Mobile viewport emulation for browser-use.

Sets the browser viewport to emulate a mobile device using CDP.
Configuration is read from Python namespace variables (set before running this file):
  DEVICE  - Device preset name or "custom" or "desktop" (default: iphone-14)
  WIDTH   - Custom viewport width (only with DEVICE="custom")
  HEIGHT  - Custom viewport height (only with DEVICE="custom")
  DPR     - Custom device pixel ratio (only with DEVICE="custom")

Usage:
  browser-use python "DEVICE='iphone-14'" && browser-use python --file mobile-viewport.py
  browser-use python "DEVICE='desktop'" && browser-use python --file mobile-viewport.py
  browser-use python "DEVICE='custom'; WIDTH=390; HEIGHT=844; DPR=3" && browser-use python --file mobile-viewport.py
"""

DEVICE_PRESETS = {
    "iphone-se": {
        "width": 375,
        "height": 667,
        "dpr": 2.0,
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    "iphone-14": {
        "width": 393,
        "height": 852,
        "dpr": 3.0,
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    "iphone-14-max": {
        "width": 430,
        "height": 932,
        "dpr": 3.0,
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    "pixel-7": {
        "width": 412,
        "height": 915,
        "dpr": 2.6,
        "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    },
    "galaxy-s23": {
        "width": 360,
        "height": 780,
        "dpr": 3.0,
        "ua": "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    },
    "ipad-mini": {
        "width": 768,
        "height": 1024,
        "dpr": 2.0,
        "ua": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    "ipad-air": {
        "width": 820,
        "height": 1180,
        "dpr": 2.0,
        "ua": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
}

# Read device name from namespace variable, fall back to default
try:
    device_name = DEVICE.lower().strip()
except NameError:
    device_name = "iphone-14"

if device_name == "desktop":
    # Reset to desktop: clear device metrics override, user agent, and touch
    session = browser._session

    async def reset_viewport():
        if not session.agent_focus_target_id:
            return False
        cdp_session = await session.get_or_create_cdp_session(
            session.agent_focus_target_id, focus=False
        )
        await cdp_session.cdp_client.send.Emulation.clearDeviceMetricsOverride(
            session_id=cdp_session.session_id
        )
        await cdp_session.cdp_client.send.Emulation.setUserAgentOverride(
            params={"userAgent": ""},
            session_id=cdp_session.session_id,
        )
        await cdp_session.cdp_client.send.Emulation.setTouchEmulationEnabled(
            params={"enabled": False},
            session_id=cdp_session.session_id,
        )
        return True

    if browser._run(reset_viewport()):
        print("Viewport reset to desktop")
    else:
        print("ERROR: No active page. Open a page first.")

elif device_name == "custom":
    # Read custom dimensions from namespace variables
    try:
        _w = WIDTH
    except NameError:
        _w = 393
    try:
        _h = HEIGHT
    except NameError:
        _h = 852
    try:
        _d = DPR
    except NameError:
        _d = 3.0

    browser._run(
        browser._session._cdp_set_viewport(int(_w), int(_h), device_scale_factor=float(_d), mobile=True)
    )
    print(f"Viewport set to custom: {int(_w)}x{int(_h)} @ {float(_d)}x DPR (mobile=true)")

elif device_name in DEVICE_PRESETS:
    preset = DEVICE_PRESETS[device_name]
    _w, _h, _d = preset["width"], preset["height"], preset["dpr"]
    _ua = preset["ua"]

    # Set viewport dimensions
    browser._run(
        browser._session._cdp_set_viewport(_w, _h, device_scale_factor=_d, mobile=True)
    )

    # Set user agent and touch emulation
    session = browser._session

    async def apply_mobile_overrides():
        if session.agent_focus_target_id:
            cdp_session = await session.get_or_create_cdp_session(
                session.agent_focus_target_id, focus=False
            )
            await cdp_session.cdp_client.send.Emulation.setUserAgentOverride(
                params={"userAgent": _ua},
                session_id=cdp_session.session_id,
            )
            await cdp_session.cdp_client.send.Emulation.setTouchEmulationEnabled(
                params={"enabled": True, "maxTouchPoints": 5},
                session_id=cdp_session.session_id,
            )

    browser._run(apply_mobile_overrides())

    label = device_name.replace("-", " ").title()
    print(f"Viewport set to {label}: {_w}x{_h} @ {_d}x DPR (mobile=true, touch=on)")
    print(f"User agent: {_ua[:80]}...")

else:
    print(f"ERROR: Unknown device '{device_name}'")
    print(f"Available presets: {', '.join(sorted(DEVICE_PRESETS.keys()))}")
    print("Use DEVICE='custom' with WIDTH, HEIGHT, DPR for custom dimensions")
    print("Use DEVICE='desktop' to reset")
