"""Erzeugt den Entschaedigungsantrag als PDF (fpdf2, Standardschriften -> latin-1)."""
from __future__ import annotations

from datetime import date

from fpdf import FPDF

from .models import Antrag

# Adresse des DB Servicecenters Fahrgastrechte (wird bei Recherche ggf. aktualisiert).
# Anschrift laut DB-Fahrgastrechte-Formular 2025 (ME/08/25); Nahverkehrsfaelle werden dort mitbearbeitet.
DB_FAHRGASTRECHTE_ANSCHRIFT = ["DB Fernverkehr AG", "Servicecenter Fahrgastrechte", "60647 Frankfurt am Main"]


def _t(s: str) -> str:
    """Zeichen ausserhalb latin-1 (z.B. Gedankenstrich) fuer die Core-Fonts ersetzen."""
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'").replace("\u20ac", "EUR")
    return s.encode("latin-1", "replace").decode("latin-1")


class _Pdf(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, _t("Antrag auf Fahrgastrechte-Entschädigung – Deutschlandticket"), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(100)
        self.cell(0, 5, _t("gemäß Art. 19 VO (EU) 2021/782 i.V.m. Tarifbedingungen des Deutschlandtarifs Teil C Nr. 8.1 (Zeitkarten)"),
                  new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0)
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120)
        self.cell(0, 6, _t(f"Seite {self.page_no()}/{{nb}}"), align="C")


def _abschnitt(pdf: FPDF, titel: str):
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _t(titel), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)


def _zeile(pdf: FPDF, label: str, wert: str):
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(48, 6, _t(label))
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _t(wert), new_x="LMARGIN", new_y="NEXT")


def erzeuge_pdf(antrag: Antrag, heute: date | None = None) -> bytes:
    heute = heute or date.today()
    p, t = antrag.person, antrag.ticket
    strecken = " sowie ".join(s.label for s in antrag.strecken) or "meinen regelmäßigen Strecken"
    pdf = _Pdf()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Absender / Empfaenger
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 5, _t(f"{p.vorname} {p.nachname}"))
    pdf.cell(0, 5, _t(DB_FAHRGASTRECHTE_ANSCHRIFT[0]), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 5, _t(p.strasse))
    pdf.cell(0, 5, _t(DB_FAHRGASTRECHTE_ANSCHRIFT[1]), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 5, _t(f"{p.plz} {p.ort}"))
    pdf.cell(0, 5, _t(DB_FAHRGASTRECHTE_ANSCHRIFT[2]), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 5, _t(p.email), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.cell(0, 5, _t(f"{p.ort}, {heute:%d.%m.%Y}"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    _abschnitt(pdf, f"Entschädigung für Verspätungen im Gültigkeitsmonat {t.monat_label}")
    betrag = f"{antrag.betrag_eur:.2f} EUR".replace(".", ",")
    kurze = [f for f in antrag.fahrten if 20 <= f.verspaetung_min < 60]
    if antrag.rechenweg == "sammeln" and kurze:
        regel = ("Grundlage ist die pauschale Entschädigung von 1,50 EUR je Fall ab 60 Minuten Verspätung am "
                 "Zielbahnhof; die Verspätungsfälle zwischen 20 und 59 Minuten rechne ich gemäß Teil C Nr. 8.1 "
                 "der Tarifbedingungen des Deutschlandtarifs zusammen (1,50 EUR je volle 60 Minuten).")
    else:
        regel = ("Grundlage ist die pauschale Entschädigung von 1,50 EUR je Fall ab 60 Minuten Verspätung "
                 "am Zielbahnhof (Teil C Nr. 8.1 der Tarifbedingungen des Deutschlandtarifs).")
    pdf.multi_cell(0, 5, _t(
        "Sehr geehrte Damen und Herren,\n\n"
        f"ich bin Inhaber(in) eines Deutschlandtickets (Zeitkarte des Nahverkehrs, 2. Klasse) und beantrage "
        f"gesammelt für den abgelaufenen Gültigkeitsmonat eine Entschädigung in Höhe von {betrag} für die "
        f"unten aufgeführten Fahrten auf {strecken}. {regel}"))
    pdf.ln(3)

    _abschnitt(pdf, "Antragsteller(in)")
    _zeile(pdf, "Name", f"{p.vorname} {p.nachname}")
    _zeile(pdf, "Anschrift", f"{p.strasse}, {p.plz} {p.ort}")
    _zeile(pdf, "E-Mail", p.email)
    if p.geburtsdatum:
        _zeile(pdf, "Geburtsdatum", p.geburtsdatum)
    pdf.ln(2)

    _abschnitt(pdf, "Ticket")
    _zeile(pdf, "Ticket", "Deutschlandticket")
    _zeile(pdf, "Gültigkeitsmonat", t.monat_label)
    if t.abonummer:
        _zeile(pdf, "Abonummer", t.abonummer)
    if t.ticketnummer:
        _zeile(pdf, "Ticketnummer", t.ticketnummer)
    if not (t.abonummer or t.ticketnummer):
        _zeile(pdf, "Ticket-/Abonummer", "– (siehe Anlage)")
    _zeile(pdf, "Ausgestellt von", t.ausgestellt_von)
    _zeile(pdf, "Ticketpreis", f"{antrag.ticketpreis_eur:.2f} EUR".replace(".", ","))
    pdf.ln(2)

    _abschnitt(pdf, f"Verspätete Fahrten ({len(antrag.fahrten)}) – Verspätung jeweils am Zielbahnhof")
    spalten = [("Datum", 19), ("Zug", 30), ("Von", 33), ("Nach", 33), ("Soll ab", 13),
               ("Soll an", 13), ("Ist an", 13), ("Versp.", 14), ("Ausfall", 13)]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230)
    for name, breite in spalten:
        pdf.cell(breite, 6, _t(name), border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for f in antrag.fahrten:
        ist_an = "–" if f.ausgefallen and f.ersatz_an is None else (
            f"{(f.ersatz_an or f.ist_an):%H:%M}" if (f.ersatz_an or f.ist_an) else "–")
        werte = [f"{f.datum:%d.%m.%Y}", f.zug[:20], f.start[:21], f.ziel[:21], f"{f.soll_ab:%H:%M}",
                 f"{f.soll_an:%H:%M}", ist_an, f"{f.verspaetung_min} min", "ja" if f.ausgefallen else ""]
        for (name, breite), wert in zip(spalten, werte):
            pdf.cell(breite, 6, _t(wert), border=1)
        pdf.ln()
    pdf.ln(3)

    _abschnitt(pdf, "Beantragte Entschädigung")
    _zeile(pdf, "Betrag", betrag)
    if p.iban:
        _zeile(pdf, "Auszahlung", f"Überweisung auf IBAN {p.iban}")
        _zeile(pdf, "Kontoinhaber", p.kontoinhaber or f"{p.vorname} {p.nachname}")
    else:
        _zeile(pdf, "Auszahlung", "Überweisung (IBAN wird auf Nachfrage mitgeteilt)")
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _t(
        "Ich versichere, dass ich die aufgeführten Fahrten tatsächlich durchgeführt habe und die angegebene "
        "Verspätung jeweils an meinem Zielbahnhof eingetreten ist. Die Verspätungsdaten stammen aus den "
        "öffentlichen Echtzeitdaten der Deutschen Bahn. Eine Kopie des Tickets liegt bei bzw. kann auf "
        "Wunsch nachgereicht werden.\n\nMit freundlichen Grüßen"))
    pdf.ln(12)
    pdf.cell(80, 5, "", border="B")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(80, 4, _t(f"{p.vorname} {p.nachname}"))
    pdf.ln(6)

    return bytes(pdf.output())
