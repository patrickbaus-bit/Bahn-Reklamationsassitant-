#!/bin/sh
# Legt „Bahn-Bonus.app“ an, die man per Doppelklick startet (nur macOS).
# Aufruf:   sh app-erstellen.sh              → ~/Desktop/Bahn-Bonus.app
#           sh app-erstellen.sh /Applications → /Applications/Bahn-Bonus.app
# Die App merkt sich den Pfad dieses Projektordners. Wird der Ordner verschoben,
# das Skript einfach noch einmal ausführen.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ZIEL="${1:-$HOME/Desktop}"
APP="$ZIEL/Bahn-Bonus.app"

[ "$(uname)" = "Darwin" ] || { echo "Die App gibt es nur für macOS. Start sonst mit: .venv/bin/dticket-refund" >&2; exit 1; }
[ -x "$HERE/.venv/bin/python" ] || { echo "Bitte zuerst einrichten: sh $HERE/bootstrap.sh" >&2; exit 1; }

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$HERE/assets/Bahn.icns" "$APP/Contents/Resources/Bahn.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Bahn-Bonus</string>
  <key>CFBundleDisplayName</key><string>Bahn-Bonus</string>
  <key>CFBundleIdentifier</key><string>local.$(id -un).bahn-bonus</string>
  <key>CFBundleExecutable</key><string>Bahn-Bonus</string>
  <key>CFBundleIconFile</key><string>Bahn</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/Bahn-Bonus" <<LAUNCHER
#!/bin/sh
# Startet Bahn-Bonus im eigenen Fenster (dticket_refund/fenster.py).
PROJEKT="$HERE"
RES="\$(cd "\$(dirname "\$0")/../Resources" && pwd)"
if [ ! -x "\$PROJEKT/.venv/bin/python" ]; then
  osascript -e 'display dialog "Bahn-Bonus ist nicht (mehr) eingerichtet. Bitte im Projektordner einmal sh bootstrap.sh ausführen." buttons {"OK"} with icon stop'
  exit 1
fi
cd "\$PROJEKT" && exec "\$PROJEKT/.venv/bin/python" -m dticket_refund.fenster --icon "\$RES/Bahn.icns" >> "\$HOME/Library/Logs/bahn-bonus.log" 2>&1
LAUNCHER
chmod +x "$APP/Contents/MacOS/Bahn-Bonus"
codesign --force --deep -s - "$APP" >/dev/null 2>&1 || true
touch "$APP"
echo "Angelegt: $APP"
