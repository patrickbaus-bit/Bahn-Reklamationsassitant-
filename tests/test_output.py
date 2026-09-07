from datetime import date, datetime, timedelta
from email import message_from_bytes

from dticket_refund.mailout import betreff, eml_datei, mailto_link, mailtext, pdf_dateiname
from dticket_refund.models import Antrag, Fahrt, Pendelstrecke, Person, Station, Ticket
from dticket_refund.pdfgen import erzeuge_pdf


def _antrag():
    person = Person("Erika", "Mustermann", "Heidestr. 17", "51147", "Köln", "erika@example.org",
                    iban="DE02120300000000202051")
    ticket = Ticket(monat=date(2026, 8, 1), ticketnummer="DT-4711")
    strecke = Pendelstrecke(Station("8000105", "Frankfurt(Main)Hbf"), Station("8000068", "Darmstadt Hbf"))
    fahrten = []
    for tag in (3, 4, 5, 10):
        ab = datetime(2026, 8, tag, 7, 32)
        an = datetime(2026, 8, tag, 7, 51)
        fahrten.append(Fahrt(date(2026, 8, tag), "hin", "RE 4572", "Frankfurt(Main)Hbf", "Darmstadt Hbf",
                             ab, an, ist_an=an + timedelta(minutes=64 + tag)))
    fahrten.append(Fahrt(date(2026, 8, 11), "rueck", "RB 68", "Darmstadt Hbf", "Frankfurt(Main)Hbf",
                         datetime(2026, 8, 11, 17, 5), datetime(2026, 8, 11, 17, 30), ausgefallen=True))
    return Antrag(person, ticket, strecke, fahrten=fahrten, betrag_eur=7.5, ticketpreis_eur=63.0, einheiten=5)


def test_pdf_wird_erzeugt():
    pdf = erzeuge_pdf(_antrag(), heute=date(2026, 9, 7))
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000


def test_mail_bausteine():
    a = _antrag()
    assert "August 2026" in betreff(a) and "DT-4711" in betreff(a)
    assert "7,50 EUR" in mailtext(a) and "DE02120300000000202051" in mailtext(a)
    assert mailto_link(a).startswith("mailto:zentralerkundendialog@bahn.de?subject=")
    assert pdf_dateiname(a) == "Fahrgastrechte_Deutschlandticket_2026-08_Mustermann.pdf"


def test_eml_enthaelt_pdf_anhang():
    a = _antrag()
    pdf = erzeuge_pdf(a)
    msg = message_from_bytes(eml_datei(a, pdf))
    assert msg["To"] == "zentralerkundendialog@bahn.de" and msg["X-Unsent"] == "1"
    anhaenge = [p for p in msg.walk() if p.get_content_type() == "application/pdf"]
    assert len(anhaenge) == 1 and anhaenge[0].get_payload(decode=True) == pdf
