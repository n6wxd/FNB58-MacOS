#!/bin/bash
# Build "dist/FNB58 Monitor.app" from this checkout.
#
#   macos/build_app.sh          # tests + app bundle
#   macos/build_app.sh --dmg    # ...plus a drag-to-Applications disk image
#
# Needs uv (brew install uv). PYTHON_VERSION (default 3.13) picks the
# uv-managed Python that gets bundled.
set -euo pipefail

cd "$(dirname "$0")/.."
APP_NAME="FNB58 Monitor"
APP="dist/$APP_NAME.app"
VENV=build/macos-venv
PYTHON_VERSION="${PYTHON_VERSION:-3.13}"

make_dmg=false
case "${1:-}" in
    --dmg) make_dmg=true ;;
    "") ;;
    *) echo "usage: $0 [--dmg]" >&2; exit 2 ;;
esac

die() { echo "error: $*" >&2; exit 1; }

command -v uv >/dev/null || die "uv not found (brew install uv)"

echo "==> Python $PYTHON_VERSION build environment ($VENV)"
uv venv --allow-existing --quiet --managed-python --python "$PYTHON_VERSION" "$VENV"
uv pip install --quiet --python "$VENV/bin/python" -r requirements.txt -r macos/requirements.txt

echo "==> Tests"
"$VENV/bin/python" -m pytest -q

echo "==> PyInstaller"
# The app reads USB through hidapi; skip the pyusb hook's libusb probe (the spec drops libusb).
export PYINSTALLER_USB_HOOK_SKIP_PYUSB_DISCOVERY=1
"$VENV/bin/python" -m PyInstaller --noconfirm --clean --log-level WARN \
    --distpath dist --workpath build/pyinstaller macos/FNB58Monitor.spec

echo "==> Verifying"
app_arch=$(lipo -archs "$APP/Contents/MacOS/$APP_NAME")
[[ -n $(find "$APP/Contents" -name 'hid.cpython-*.so') ]] || die "hidapi (USB transport) was not bundled"
codesign --verify --deep --strict "$APP"
version=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")
echo "    $APP_NAME $version ($app_arch), $(du -sh "$APP" | cut -f1), ad-hoc signed"

if $make_dmg; then
    dmg="dist/FNB58-Monitor-$version.dmg"
    echo "==> Disk image"
    staging=build/dmg
    rm -rf "$staging" "$dmg"
    mkdir -p "$staging"
    ditto "$APP" "$staging/$APP_NAME.app"
    ln -s /Applications "$staging/Applications"
    hdiutil create -quiet -volname "$APP_NAME" -srcfolder "$staging" -format UDZO "$dmg"
    echo "    $dmg"
fi

echo
echo "Done: open \"$APP\""
