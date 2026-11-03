# FNB58 Monitor for macOS

`FNB58 Monitor.app` is the web monitor packaged as a normal Mac app: double-click it and the
dashboard opens in its own window. Python and every dependency are bundled, and the dashboard's
JavaScript libraries are vendored, so it needs no network connection.

## Build

```bash
brew install uv              # once
macos/build_app.sh           # tests, then dist/FNB58 Monitor.app
macos/build_app.sh --dmg     # ...plus dist/FNB58-Monitor-<version>.dmg
```

The script creates its own environment in `build/macos-venv` (uv-managed Python 3.13; override
with `PYTHON_VERSION=3.12`), runs the test suite, runs PyInstaller with
[`FNB58Monitor.spec`](FNB58Monitor.spec), and checks the result. A build takes under half a minute.

To use it, drag the app to `/Applications` (or open the DMG and drag it onto the Applications link).

## How it works

[`desktop.py`](../desktop.py) is the entry point. It:

- starts the Flask/Socket.IO server on `127.0.0.1` only (port 5001, or any free port if that's
  taken), so the monitor is not reachable from your network;
- shows the dashboard in a WKWebView window ([pywebview](https://pywebview.flowrl.com/));
- keeps sessions and exports in `~/Library/Application Support/FNB58 Monitor/` and logs to
  `~/Library/Logs/FNB58 Monitor/monitor.log`;
- on quit (close button or ⌘Q) saves a recording in progress and releases the meter.

The **Monitor** menu has *Open Dashboard in Browser*, *Show Sessions in Finder* and
*Show Log in Finder*. Exports open a normal Save dialog.

**USB** goes through the macOS HID API (`hidapi`), not libusb: the kernel's HID driver owns the
meter's interface, and libusb can only take it over as root. No driver or permission is needed.
**Bluetooth** asks for permission the first time you scan or connect.

## Notes

- **Requires macOS 14 or later**, and runs on the architecture it was built on (Apple Silicon
  here). Build on an Intel Mac for an Intel copy.
- **Ad-hoc signed, not notarized.** On your own Mac it just opens. On another Mac, Gatekeeper
  blocks the first launch: right-click → Open, or System Settings → Privacy & Security →
  Open Anyway. Because each build has a new signature, macOS may ask for Bluetooth permission
  again after a rebuild.
- **Debugging:** `FNB58_DEBUG=1 "dist/FNB58 Monitor.app/Contents/MacOS/FNB58 Monitor"` runs it
  with the Web Inspector enabled and the log on the terminal. `python desktop.py` runs the same
  launcher unbundled (after `pip install -r requirements.txt -r macos/requirements.txt`).
- **Icon:** `icon.icns` is generated from `icon.svg`. To change it, render the SVG to an
  `icon.iconset/` (16–1024 px PNGs, e.g. with `rsvg-convert`) and run
  `iconutil -c icns icon.iconset -o icon.icns`.
