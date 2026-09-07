"""Waehlt aus den gefundenen Verspaetungen die Menge und den Rechenweg, die den hoechsten
Erstattungsbetrag ergeben.

Pro Tag und Richtung zaehlt nur eine Fahrt (der Pendler sitzt nur in einem Zug); von
mehreren Zuegen im Zeitfenster wird der mit der laengsten Verspaetung angenommen - der
Nutzer streicht anschliessend, was er nicht gefahren ist.

Rechenwege (siehe rules.py): "einzelfall" (1,50 EUR je Fall ab 60 min) und "sammeln"
(alle Faelle ab 20 min addiert, 1,50 EUR je volle 60 min). Die Sammelregel liefert nie
weniger Einheiten als die Einzelfallregel, da jeder 60-Minuten-Fall mindestens eine volle
Stunde beitraegt; bei Gleichstand wird der einfachere Einzelfall-Weg genommen.
"""
from __future__ import annotations

from .models import Antrag, Fahrt, Pendelstrecke, Person, Ticket
from .rules import REGELN, Regelwerk, ticketpreis


def _eur(x: float) -> str:
    return f"{x:.2f} EUR".replace(".", ",")


def _eine_pro_tag_und_richtung(fahrten: list[Fahrt]) -> list[Fahrt]:
    beste: dict[tuple, Fahrt] = {}
    for f in fahrten:
        key = (f.datum, f.richtung)
        if key not in beste or f.verspaetung_min > beste[key].verspaetung_min:
            beste[key] = f
    return list(beste.values())


def _auswahl_einzelfall(kandidaten: list[Fahrt], regeln: Regelwerk, preis: float) -> list[Fahrt]:
    faelle = [f for f in kandidaten if f.verspaetung_min >= regeln.schwelle_einzelfall_min]
    return faelle[:regeln.max_einheiten(preis)]


def _auswahl_sammeln(kandidaten: list[Fahrt], regeln: Regelwerk, preis: float) -> list[Fahrt]:
    """Laengste Verspaetungen zuerst, bis die Kappung erreicht ist."""
    ziel_minuten = regeln.max_einheiten(preis) * 60
    gewaehlt, summe = [], 0
    for f in kandidaten:
        if f.verspaetung_min < regeln.schwelle_sammeln_min:
            break
        if summe >= ziel_minuten:
            break
        gewaehlt.append(f)
        summe += f.verspaetung_min
    return gewaehlt


def optimiere(person: Person, ticket: Ticket, strecke: Pendelstrecke,
              fahrten: list[Fahrt], regeln: Regelwerk = REGELN,
              preis_eur: float | None = None) -> Antrag:
    preis = preis_eur if preis_eur is not None else ticketpreis(ticket.monat)
    kandidaten = [f for f in _eine_pro_tag_und_richtung(fahrten)
                  if f.verspaetung_min >= regeln.schwelle_sammeln_min]
    kandidaten.sort(key=lambda f: (-f.verspaetung_min, f.datum, f.richtung))

    varianten = {
        "einzelfall": _auswahl_einzelfall(kandidaten, regeln, preis),
        "sammeln": _auswahl_sammeln(kandidaten, regeln, preis),
    }
    einheiten = {
        "einzelfall": regeln.einheiten_einzelfall([f.verspaetung_min for f in varianten["einzelfall"]]),
        "sammeln": regeln.einheiten_sammeln([f.verspaetung_min for f in varianten["sammeln"]]),
    }
    betraege = {k: regeln.betrag(n, preis) for k, n in einheiten.items()}
    # Bei Gleichstand gewinnt der Einzelfall-Weg (uebliches Verfahren, weniger Fahrten noetig).
    rechenweg = "einzelfall" if betraege["einzelfall"] >= betraege["sammeln"] else "sammeln"
    gewaehlt = sorted(varianten[rechenweg], key=lambda f: (f.datum, f.soll_ab))
    gewaehlt_ids = {id(f) for f in gewaehlt}
    rest = sorted((f for f in kandidaten if id(f) not in gewaehlt_ids), key=lambda f: (f.datum, f.soll_ab))
    betrag = betraege[rechenweg]

    hinweise: list[str] = []
    if not kandidaten:
        hinweise.append("Keine Verspätung ab 20 Minuten auf dieser Strecke gefunden.")
    elif betrag == 0.0:
        hinweise.append(
            f"Der Anspruch ({einheiten[rechenweg]} x {_eur(regeln.pauschale_eur)}) liegt nicht über der "
            f"Bagatellgrenze von {_eur(regeln.bagatellgrenze_eur)} - es wird nichts ausgezahlt. "
            f"Ab {regeln.min_einheiten()} Einheiten im Monat lohnt sich der Antrag.")
    if rechenweg == "sammeln" and betraege["sammeln"] > betraege["einzelfall"]:
        hinweise.append(
            f"Sammelregel (Teil C Nr. 8.1 Deutschlandtarif) gewählt: alle Verspätungen ab 20 Minuten "
            f"addiert ergeben {sum(f.verspaetung_min for f in gewaehlt)} Minuten = {einheiten['sammeln']} volle "
            f"Stunden. Die Einzelfallregel (nur Fälle ab 60 min) hätte {_eur(betraege['einzelfall'])} ergeben.")
    if rest and betrag >= regeln.kappung_eur(preis):
        hinweise.append(
            f"{len(rest)} weitere Verspätung(en) bringen kein zusätzliches Geld, weil die Kappung von "
            f"{_eur(regeln.kappung_eur(preis))} (25 % von {_eur(preis)}) erreicht ist.")
    return Antrag(person=person, ticket=ticket, strecke=strecke, fahrten=gewaehlt, verworfen=rest,
                  betrag_eur=betrag, ticketpreis_eur=preis, rechenweg=rechenweg,
                  einheiten=einheiten[rechenweg], hinweise=hinweise)
