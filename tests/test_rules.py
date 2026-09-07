from datetime import date, datetime, timedelta

from dticket_refund.models import Fahrt, Pendelstrecke, Person, Station, Ticket
from dticket_refund.optimizer import optimiere
from dticket_refund.rules import REGELN, ticketpreis


def test_ticketpreis_historie():
    assert ticketpreis(date(2023, 5, 1)) == 49.0
    assert ticketpreis(date(2024, 12, 1)) == 49.0
    assert ticketpreis(date(2025, 6, 1)) == 58.0
    assert ticketpreis(date(2026, 8, 1)) == 63.0


def test_kappung_und_bagatellgrenze():
    assert REGELN.kappung_eur(63.0) == 15.75
    assert REGELN.max_einheiten(63.0) == 11       # 11 x 1,50 = 16,50 -> gedeckelt 15,75
    assert REGELN.max_einheiten(48.0) == 8        # 8 x 1,50 = 12,00 = Kappung exakt
    assert REGELN.min_einheiten() == 3            # 3 x 1,50 = 4,50 > 4,00
    assert REGELN.betrag(2, 63.0) == 0.0
    assert REGELN.betrag(3, 63.0) == 4.5
    assert REGELN.betrag(25, 63.0) == 15.75
    assert REGELN.betrag(10, 63.0) == 15.0


def test_zwei_rechenwege():
    assert REGELN.einheiten_einzelfall([65, 95, 30, 19]) == 2
    assert REGELN.einheiten_sammeln([65, 95, 30, 19]) == 3        # 190 min -> 3 volle Stunden


def _fahrt(tag, richtung, minuten, ausgefallen=False):
    soll_ab = datetime(2026, 8, tag, 7, 30)
    soll_an = datetime(2026, 8, tag, 8, 15)
    return Fahrt(datum=date(2026, 8, tag), richtung=richtung, zug="RE 1", start="A", ziel="B",
                 soll_ab=soll_ab, soll_an=soll_an,
                 ist_an=None if ausgefallen else soll_an + timedelta(minutes=minuten),
                 ausgefallen=ausgefallen)


def _rahmen():
    person = Person("Max", "Muster", "Weg 1", "60311", "Frankfurt", "max@example.org")
    ticket = Ticket(monat=date(2026, 8, 1), ticketnummer="123")
    strecke = Pendelstrecke(Station("1", "A"), Station("2", "B"))
    return person, ticket, strecke


def test_optimierer_nimmt_eine_fahrt_pro_tag_und_richtung_und_kappt():
    fahrten = [_fahrt(1, "hin", 70), _fahrt(1, "hin", 95), _fahrt(1, "rueck", 61)]
    fahrten += [_fahrt(t, "hin", 60 + t) for t in range(2, 20)]     # 18 weitere Tage
    fahrten.append(_fahrt(20, "hin", 19))                           # zu wenig, auch zum Sammeln
    fahrten.append(_fahrt(21, "hin", 0, ausgefallen=True))          # Ausfall zaehlt
    antrag = optimiere(*_rahmen(), fahrten)
    assert antrag.rechenweg == "einzelfall"
    assert len(antrag.fahrten) == 11
    assert antrag.betrag_eur == 15.75
    assert antrag.ticketpreis_eur == 63.0
    # Die laengsten Verspaetungen werden bevorzugt: 95 min statt 70 min am 1.8.
    am_ersten = [f for f in antrag.fahrten if f.datum == date(2026, 8, 1) and f.richtung == "hin"]
    assert len(am_ersten) == 1 and am_ersten[0].verspaetung_min == 95
    assert antrag.fahrten == sorted(antrag.fahrten, key=lambda f: (f.datum, f.soll_ab))
    assert len(antrag.verworfen) == 21 - 11
    assert any("Kappung" in h for h in antrag.hinweise)


def test_optimierer_unter_bagatellgrenze():
    antrag = optimiere(*_rahmen(), [_fahrt(1, "hin", 65), _fahrt(2, "hin", 65)])
    assert antrag.betrag_eur == 0.0
    assert len(antrag.fahrten) == 2
    assert any("Bagatellgrenze" in h for h in antrag.hinweise)


def test_sammelregel_gewinnt_bei_vielen_kurzen_verspaetungen():
    # 2 Faelle >= 60 (65+95) = 3,00 EUR einzeln; gesammelt mit 4 x 30 min: 280 min -> 4 Std = 6,00 EUR
    fahrten = [_fahrt(1, "hin", 65), _fahrt(2, "hin", 95)] + [_fahrt(t, "hin", 30) for t in (3, 4, 5, 6)]
    fahrten.append(_fahrt(7, "hin", 15))   # zaehlt nirgends
    antrag = optimiere(*_rahmen(), fahrten)
    assert antrag.rechenweg == "sammeln"
    assert antrag.einheiten == 4 and antrag.betrag_eur == 6.0
    assert len(antrag.fahrten) == 6 and all(f.verspaetung_min >= 20 for f in antrag.fahrten)
    assert any("Sammelregel" in h for h in antrag.hinweise)


def test_sammelregel_stoppt_an_der_kappung():
    fahrten = [_fahrt(t, "hin", 45) for t in range(1, 29)]       # 28 x 45 min = 1260 min
    antrag = optimiere(*_rahmen(), fahrten)
    assert antrag.rechenweg == "sammeln" and antrag.betrag_eur == 15.75
    assert sum(f.verspaetung_min for f in antrag.fahrten) >= 11 * 60
    assert len(antrag.fahrten) == 15                             # 15 x 45 = 675 >= 660
    assert len(antrag.verworfen) == 13


def test_ausfall_ohne_ersatz_gilt_als_60_min():
    f = _fahrt(3, "hin", 0, ausgefallen=True)
    assert f.verspaetung_min == 60 and f.erstattungsfaehig


def test_fahrtage_und_monatsgrenzen():
    ticket = Ticket(monat=date(2026, 2, 1))
    assert ticket.letzter_tag == date(2026, 2, 28)
    strecke = Pendelstrecke(Station("1", "A"), Station("2", "B"),
                            ausgeschlossene_tage=frozenset({date(2026, 2, 2)}))
    tage = list(strecke.fahrtage(ticket.erster_tag, ticket.letzter_tag))
    assert date(2026, 2, 2) not in tage and date(2026, 2, 1) not in tage   # 1.2.2026 ist Sonntag
    assert len(tage) == 19
