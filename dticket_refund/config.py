"""Lokale Einstellungen und das gespeicherte Nutzerprofil (einmal eingeben, dann merken)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .models import Person

KONFIG_DIR = Path(os.environ.get("DTICKET_REFUND_HOME", Path.home() / ".config" / "dticket-refund"))
PROFIL_DATEI = KONFIG_DIR / "profil.json"

# Empfaenger. Die DB nennt offiziell nur den Postweg (DB Fernverkehr AG, Servicecenter
# Fahrgastrechte, 60647 Frankfurt am Main) und das Online-Formular im Kundenkonto; eine
# offizielle E-Mail-Adresse des Servicecenters gibt es nicht (Auskunft EBA via FragDenStaat).
# Antraege per E-Mail gelten trotzdem als wirksam gestellt (AG Frankfurt, 29 C 599/23) und
# werden intern weitergeleitet. Voreingestellt ist die Adresse des Zentralen Kundendialogs
# (DB Dialog GmbH betreibt auch das Servicecenter), die u.a. ronnyrefund.de verwendet.
# Ueberschreibbar per Umgebungsvariable, z.B. fuer ein anderes Verkehrsunternehmen.
EMPFAENGER_EMAIL = os.environ.get("DTICKET_REFUND_EMPFAENGER", "zentralerkundendialog@bahn.de")
ONLINE_FORMULAR_URL = "https://www.bahn.de/service/informationen-buchung/fahrgastrechte"


def lade_profil() -> dict:
    """Personendaten + zuletzt benutzte Strecke; leeres Dict, wenn noch nichts gespeichert."""
    try:
        return json.loads(PROFIL_DATEI.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def speichere_profil(person: Person, abonummer: str = "", strecken: list[dict] | None = None) -> None:
    """Person, Abonummer und die zuletzt benutzten Strecken merken."""
    KONFIG_DIR.mkdir(parents=True, exist_ok=True)
    alt = lade_profil()
    daten = {"person": asdict(person), "abonummer": abonummer,
             "strecken": strecken if strecken is not None else alt.get("strecken", [])}
    PROFIL_DATEI.write_text(json.dumps(daten, ensure_ascii=False, indent=2))
    try:
        PROFIL_DATEI.chmod(0o600)   # IBAN und Adresse: nur der Nutzer selbst
    except OSError:
        pass
