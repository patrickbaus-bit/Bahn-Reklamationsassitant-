#!/bin/sh
# Richtet Bahn-Bonus ein bzw. aktualisiert es.   Aufruf:   sh bootstrap.sh
#
# Braucht weder Homebrew noch Admin-Rechte: Ist kein Python 3.10 oder neuer vorhanden,
# holt das Werkzeug „uv“ (https://docs.astral.sh/uv/) Python 3.12 in den eigenen Benutzerordner.
# Alles landet im Unterordner .venv dieses Projekts.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
VENV="$HERE/.venv"

if [ ! -x "$VENV/bin/python" ]; then
    PY=""
    for p in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 \
             /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/3.1*/bin/python3 python3; do
        if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            PY=$p; break
        fi
    done
    if [ -n "$PY" ]; then
        echo "Python gefunden: $PY" >&2
        "$PY" -m venv "$VENV"
    else
        UV=""
        for c in "$(command -v uv 2>/dev/null || true)" "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
            if [ -n "$c" ] && [ -x "$c" ]; then UV=$c; break; fi
        done
        if [ -z "$UV" ]; then
            echo "Kein Python 3.10+ gefunden. Installiere das Werkzeug uv nach ~/.local/bin …" >&2
            curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
            UV="$HOME/.local/bin/uv"
        fi
        [ -x "$UV" ] || { echo "uv konnte nicht installiert werden. Alternative: brew install python, dann erneut sh bootstrap.sh" >&2; exit 1; }
        echo "Hole Python 3.12 über uv (einmalig, ca. 1 Minute) …" >&2
        "$UV" venv --quiet --seed --python 3.12 "$VENV"
    fi
fi

echo "Installiere Pakete (beim ersten Mal 1 bis 3 Minuten) …" >&2
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q -e "$HERE[test]"
"$VENV/bin/python" -c "import dticket_refund.web, duckdb, fpdf, webview" \
    || { echo "Installation unvollständig, bitte Ausgabe oben prüfen." >&2; exit 1; }

echo ""
echo "Installation abgeschlossen."
echo "  App auf dem Schreibtisch anlegen:  sh $HERE/app-erstellen.sh"
echo "  Oder im Browser starten:           $VENV/bin/dticket-refund   →  http://127.0.0.1:8765/"
