#!/bin/sh
# Richtet die Python-Umgebung ein.  Aufruf:   sh bootstrap.sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
PY=""
for p in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 \
         /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/3.1*/bin/python3 python3; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PY=$p; break
    fi
done
[ -n "$PY" ] || { echo "Kein python3 >= 3.10 gefunden (brew install python)." >&2; exit 1; }
echo "Interpreter: $PY" >&2
[ -d "$HERE/.venv" ] || "$PY" -m venv "$HERE/.venv"
"$HERE/.venv/bin/pip" install -q --upgrade pip
"$HERE/.venv/bin/pip" install -q -e "$HERE[test]"
echo "Fertig. Start:  $HERE/.venv/bin/dticket-refund"
