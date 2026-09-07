"""Versandweg: Mail.app-Entwurf mit PDF-Anhang (macOS), .eml-Datei und mailto-Link."""
from __future__ import annotations

import subprocess
import tempfile
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

from .models import Antrag

from .config import EMPFAENGER_EMAIL as DB_FAHRGASTRECHTE_EMAIL


def betreff(antrag: Antrag) -> str:
    t = antrag.ticket
    nr = f", Ticket-Nr. {t.ticketnummer}" if t.ticketnummer else ""
    return f"Fahrgastrechte Deutschlandticket {t.monat_label}{nr} – {antrag.person.vorname} {antrag.person.nachname}"


def mailtext(antrag: Antrag) -> str:
    p, t, s = antrag.person, antrag.ticket, antrag.strecke
    zeilen = [
        "Sehr geehrte Damen und Herren,",
        "",
        f"anbei sende ich Ihnen meinen Antrag auf Fahrgastrechte-Entschädigung für mein Deutschlandticket "
        f"im Gültigkeitsmonat {t.monat_label}.",
        "",
        f"Strecke: {s.start.name} – {s.ziel.name}",
        (f"Anzahl Verspätungsfälle ab 60 Minuten: {len(antrag.fahrten)}" if antrag.rechenweg == "einzelfall"
         else f"Zusammengerechnete Verspätungen ab 20 Minuten: {len(antrag.fahrten)} Fahrten, "
              f"{sum(f.verspaetung_min for f in antrag.fahrten)} Minuten = {antrag.einheiten} volle Stunden"),
        f"Beantragter Betrag: {antrag.betrag_eur:.2f} EUR".replace(".", ","),
    ]
    if t.ticketnummer:
        zeilen.append(f"Ticket-/Abonummer: {t.ticketnummer}")
    zeilen += [
        "",
        "Die einzelnen Fahrten mit Soll- und Ist-Zeiten entnehmen Sie bitte dem beigefügten PDF.",
    ]
    if p.iban:
        zeilen.append(f"Bitte überweisen Sie den Betrag auf IBAN {p.iban} "
                      f"(Kontoinhaber: {p.kontoinhaber or p.vorname + ' ' + p.nachname}).")
    zeilen += ["", "Mit freundlichen Grüßen", f"{p.vorname} {p.nachname}", p.strasse, f"{p.plz} {p.ort}"]
    return "\n".join(zeilen)


def mailto_link(antrag: Antrag, empfaenger: str = DB_FAHRGASTRECHTE_EMAIL) -> str:
    return (f"mailto:{empfaenger}?subject={quote(betreff(antrag))}"
            f"&body={quote(mailtext(antrag))}")


def pdf_dateiname(antrag: Antrag) -> str:
    t = antrag.ticket
    name = f"{antrag.person.nachname}".replace(" ", "_")
    return f"Fahrgastrechte_Deutschlandticket_{t.monat:%Y-%m}_{name}.pdf"


def eml_datei(antrag: Antrag, pdf: bytes, empfaenger: str = DB_FAHRGASTRECHTE_EMAIL) -> bytes:
    """Unversendete Nachricht mit Anhang (Outlook/Thunderbird oeffnen sie als Entwurf)."""
    msg = EmailMessage()
    msg["To"] = empfaenger
    msg["Subject"] = betreff(antrag)
    msg["X-Unsent"] = "1"
    msg.set_content(mailtext(antrag))
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=pdf_dateiname(antrag))
    return msg.as_bytes()


def _applescript_str(s: str) -> str:
    """AppleScript-Stringliteral; Zeilenumbrueche als ``linefeed``-Konkatenation."""
    teile = s.split("\n")
    return " & linefeed & ".join('"' + t.replace("\\", "\\\\").replace('"', '\\"') + '"' for t in teile)


def mail_app_entwurf(antrag: Antrag, pdf: bytes, empfaenger: str = DB_FAHRGASTRECHTE_EMAIL,
                     absender: str | None = None) -> Path:
    """Oeffnet in Apple Mail einen fertigen Entwurf mit Empfaenger, Text und PDF-Anhang.

    Der Nutzer muss nur noch auf "Senden" klicken. Gibt den Pfad des Anhangs zurueck.
    """
    ordner = Path(tempfile.mkdtemp(prefix="dticket-refund-"))
    pfad = ordner / pdf_dateiname(antrag)
    pfad.write_bytes(pdf)
    sender_zeile = f"set sender to {_applescript_str(absender)}" if absender else ""
    script = f"""
tell application "Mail"
    set neu to make new outgoing message with properties {{subject:{_applescript_str(betreff(antrag))}, content:{_applescript_str(mailtext(antrag) + chr(10) + chr(10))}, visible:true}}
    tell neu
        {sender_zeile}
        make new to recipient at end of to recipients with properties {{address:{_applescript_str(empfaenger)}}}
        make new attachment with properties {{file name:(POSIX file {_applescript_str(str(pfad))})}} at after the last paragraph
    end tell
    activate
end tell
"""
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Apple Mail hat nicht geantwortet. Beim ersten Mal fragt macOS, ob Python Mail steuern darf - "
            "bitte den Dialog bestaetigen (Systemeinstellungen > Datenschutz & Sicherheit > Automation) "
            "und erneut klicken. Alternativ die .eml-Datei herunterladen.") from None
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Apple Mail meldet: {e.stderr.strip() or e}") from None
    return pfad
