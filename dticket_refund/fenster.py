"""Eigenes App-Fenster statt Browser-Tab: startet die Web-Oberflaeche im selben Prozess und zeigt sie
in einem nativen macOS-Fenster (pywebview/WKWebView). Fenster schliessen beendet auch den Server.

Aufruf:  .venv/bin/python -m dticket_refund.fenster [--icon pfad.icns]
"""
from __future__ import annotations

import argparse
import logging
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

PORT = 8765
ADRESSE = f"http://127.0.0.1:{PORT}/"
DOWNLOADS = Path.home() / "Downloads"

# Links, die WKWebView nicht selbst sinnvoll behandelt (mailto, PDF/.eml-Downloads), an Python weiterreichen
KLICK_JS = """
document.addEventListener('click', e => {
  const a = e.target.closest('a[href]'); if (!a) return;
  const h = a.href;
  if (h.startsWith('mailto:') || /\\/antrag\\.(pdf|eml)$/.test(h) || (a.target === '_blank')) {
    e.preventDefault(); window.pywebview.api.extern(h);
  }
}, true);
"""


class Api:
    def extern(self, url: str):
        if url.startswith("mailto:") or not url.startswith(ADRESSE):
            subprocess.run(["open", url])
            return
        # PDF/.eml in den Download-Ordner legen und mit der Standard-App oeffnen (Vorschau bzw. Mail)
        with urllib.request.urlopen(url) as r:
            name = r.headers.get_filename() or url.rsplit("/", 1)[-1]
            ziel = DOWNLOADS / name
            ziel.write_bytes(r.read())
        subprocess.run(["open", str(ziel)])


def _port_belegt() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def _starte_server() -> None:
    import uvicorn
    from .web import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if _port_belegt():
            return
        time.sleep(0.1)
    raise RuntimeError("Server ist nicht gestartet.")


def _mac_auftritt(icon: str | None) -> None:
    """Name im Menue und Icon im Dock (sonst erscheint die App als 'Python')."""
    try:
        import AppKit
        from Foundation import NSBundle
        info = NSBundle.mainBundle().localizedInfoDictionary() or NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = "Bahn-Bonus"
        if icon and Path(icon).exists():
            AppKit.NSApplication.sharedApplication().setApplicationIconImage_(
                AppKit.NSImage.alloc().initWithContentsOfFile_(icon))
    except Exception as e:
        logging.getLogger(__name__).warning("Dock-Name/Icon nicht gesetzt: %s", e)


def main(argv=None):
    p = argparse.ArgumentParser(prog="dticket-refund-fenster")
    p.add_argument("--icon")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import webview
    if not _port_belegt():          # laeuft schon eine Instanz (z. B. im Terminal), wird sie mitbenutzt
        _starte_server()
    _mac_auftritt(args.icon)
    fenster = webview.create_window("Bahn-Bonus – Deutschlandticket-Entschädigung", ADRESSE, js_api=Api(),
                                    width=1100, height=850, min_size=(720, 600), text_select=True)
    fenster.events.loaded += lambda: fenster.evaluate_js(KLICK_JS)
    fenster.events.shown += _nach_vorne
    webview.start()


def _nach_vorne():
    try:
        import AppKit
        from PyObjCTools import AppHelper
        AppHelper.callAfter(lambda: AppKit.NSApp.activateIgnoringOtherApps_(True))
    except Exception:
        pass


if __name__ == "__main__":
    main()
