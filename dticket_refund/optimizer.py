"""Waehlt aus den gefundenen Verspaetungen die Fahrten und den Rechenweg, die den
hoechsten Erstattungsbetrag ergeben - und zwar so, dass die Auswahl plausibel ist.

Plausibilitaet (ein Pendler sitzt nur in einem Zug):
* pro Tag hoechstens eine Hinfahrt und eine Rueckfahrt,
* die Rueckfahrt faehrt erst ab, nachdem die Hinfahrt tatsaechlich angekommen ist,
  und gehoert zur selben Strecke (zurueck von dort, wo man hingefahren ist).

Verteilung: statt stur die laengsten Verspaetungen zu nehmen, werden die Fahrten so
gewaehlt, dass zwischen den Fahrtagen moeglichst viele Tage liegen (Farthest-Point-
Greedy). Gewaehlt wird nur so viel, wie fuer die Kappung noetig ist; dazu kommen
RESERVE weitere Fahrten als Ersatz, falls der Nutzer welche streicht. Alles andere
wird verworfen und muss nicht eingereicht werden.

Rechenwege (siehe rules.py): "einzelfall" (1,50 EUR je Fall ab 60 min) und "sammeln"
(zusaetzlich die Faelle von 20 bis 59 min addiert, 1,50 EUR je volle 60 min davon).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .models import Antrag, Fahrt, Pendelstrecke, Person, Ticket
from .rules import REGELN, Regelwerk, ticketpreis

RESERVE = 10


def _eur(x: float) -> str:
    return f"{x:.2f} EUR".replace(".", ",")


def _ankunft(f: Fahrt) -> datetime:
    """Tatsaechliche Ankunft am Ziel (bei Ausfall: Ersatzankunft oder Soll + 60 min)."""
    if f.ausgefallen:
        return f.ersatz_an or f.soll_an + timedelta(minutes=60)
    return f.ist_an or f.soll_an


def vertraeglich(f: Fahrt, gewaehlt: list[Fahrt]) -> bool:
    """Passt ``f`` zu den bereits gewaehlten Fahrten desselben Tages?"""
    for g in gewaehlt:
        if g.datum != f.datum:
            continue
        if g.richtung == f.richtung:
            return False                      # zwei Hin- oder zwei Rueckfahrten am selben Tag
        hin, rueck = (g, f) if g.richtung == "hin" else (f, g)
        if not (rueck.start == hin.ziel and rueck.ziel == hin.start):
            return False                      # andere Strecke zurueck als hin
        if rueck.soll_ab < _ankunft(hin):
            return False                      # Rueckzug faehrt ab, bevor man angekommen ist
    return True


def _abstand(f: Fahrt, gewaehlt: list[Fahrt]) -> int:
    """Kleinster Abstand in Tagen zu einem bereits gewaehlten Fahrtag (gross, wenn keiner)."""
    tage = {g.datum for g in gewaehlt}
    if not tage:
        return 10_000
    return min(abs((f.datum - t).days) for t in tage)


def _greedy(kandidaten: list[Fahrt], gewaehlt: list[Fahrt], fertig, maximal: int) -> list[Fahrt]:
    """Nimmt Fahrten auf, bis ``fertig(gewaehlt)`` gilt oder ``maximal`` neue erreicht sind.

    Bevorzugt den Kandidaten mit dem groessten Tagesabstand zur bisherigen Auswahl,
    bei Gleichstand den mit der laengsten Verspaetung. Unvertraegliche fallen weg.
    """
    offen = [f for f in kandidaten if f not in gewaehlt]
    neu: list[Fahrt] = []
    while offen and len(neu) < maximal and not fertig(gewaehlt):
        offen.sort(key=lambda f: (-_abstand(f, gewaehlt), -f.verspaetung_min, f.datum, f.soll_ab))
        f = offen.pop(0)
        if vertraeglich(f, gewaehlt):
            gewaehlt.append(f)
            neu.append(f)
    return neu


def _auswahl(kandidaten: list[Fahrt], regeln: Regelwerk, preis: float, rechenweg: str
             ) -> tuple[list[Fahrt], list[Fahrt], int]:
    """(eingereicht, reserve, einheiten) fuer einen Rechenweg."""
    schwelle = regeln.schwelle_einzelfall_min if rechenweg == "einzelfall" else regeln.schwelle_sammeln_min
    zaehle = regeln.einheiten_einzelfall if rechenweg == "einzelfall" else regeln.einheiten_sammeln
    passende = [f for f in kandidaten if f.verspaetung_min >= schwelle]
    ziel = regeln.max_einheiten(preis)
    gewaehlt: list[Fahrt] = []
    _greedy(passende, gewaehlt, lambda g: zaehle([f.verspaetung_min for f in g]) >= ziel, len(passende))
    eingereicht = list(gewaehlt)
    # Reserve aus allen Kandidaten ab 20 min: faellt eine lange Verspaetung weg, kann die
    # Neuberechnung auf die Sammelregel wechseln und kurze Faelle brauchen.
    reserve = _greedy(kandidaten, gewaehlt, lambda g: False, RESERVE)
    return eingereicht, reserve, zaehle([f.verspaetung_min for f in eingereicht])


def optimiere(person: Person, ticket: Ticket, strecken: Pendelstrecke | list[Pendelstrecke],
              fahrten: list[Fahrt], regeln: Regelwerk = REGELN,
              preis_eur: float | None = None) -> Antrag:
    if isinstance(strecken, Pendelstrecke):
        strecken = [strecken]
    preis = preis_eur if preis_eur is not None else ticketpreis(ticket.monat)
    kandidaten = [f for f in fahrten if f.verspaetung_min >= regeln.schwelle_sammeln_min]

    varianten = {w: _auswahl(kandidaten, regeln, preis, w) for w in ("einzelfall", "sammeln")}
    betraege = {w: regeln.betrag(v[2], preis) for w, v in varianten.items()}
    # Bei Gleichstand gewinnt der Einzelfall-Weg (uebliches Verfahren, weniger Fahrten noetig).
    rechenweg = "einzelfall" if betraege["einzelfall"] >= betraege["sammeln"] else "sammeln"
    eingereicht, reserve, einheiten = varianten[rechenweg]
    nach_zeit = lambda f: (f.datum, f.soll_ab)
    eingereicht.sort(key=nach_zeit)
    reserve.sort(key=nach_zeit)
    benutzt = {id(f) for f in eingereicht + reserve}
    rest = sorted((f for f in kandidaten if id(f) not in benutzt), key=nach_zeit)
    betrag = betraege[rechenweg]

    hinweise: list[str] = []
    if not kandidaten:
        hinweise.append("Keine Verspätung ab 20 Minuten auf den Strecken gefunden.")
    elif betrag == 0.0:
        hinweise.append(
            f"Der Anspruch ({einheiten} x {_eur(regeln.pauschale_eur)}) liegt nicht über der "
            f"Bagatellgrenze von {_eur(regeln.bagatellgrenze_eur)} - es wird nichts ausgezahlt. "
            f"Ab {regeln.min_einheiten()} Einheiten im Monat lohnt sich der Antrag.")
    if rechenweg == "sammeln" and betraege["sammeln"] > betraege["einzelfall"]:
        minuten = [f.verspaetung_min for f in eingereicht]
        lange = regeln.einheiten_einzelfall(minuten)
        kurz = regeln.kurze_minuten(minuten)
        hinweise.append(
            f"Sammelregel (Teil C Nr. 8.1 Deutschlandtarif) gewählt: {lange} Fälle ab 60 Minuten je eine Einheit, "
            f"dazu {kurz} Minuten aus Verspätungen zwischen 20 und 59 Minuten = {kurz // 60} weitere Einheit(en). "
            f"Nur die Einzelfallregel hätte {_eur(betraege['einzelfall'])} ergeben.")
    if reserve or rest:
        hinweise.append(
            f"{len(eingereicht)} Fahrten reichen für den Betrag; sie sind möglichst weit über den Monat verteilt. "
            f"{len(reserve)} Fahrten stehen als Reserve bereit, falls Sie eingereichte Fahrten streichen"
            + (f"; {len(rest)} weitere wurden verworfen." if rest else "."))
    return Antrag(person=person, ticket=ticket, strecken=strecken, fahrten=eingereicht, reserve=reserve,
                  verworfen=rest, betrag_eur=betrag, ticketpreis_eur=preis, rechenweg=rechenweg,
                  einheiten=einheiten, hinweise=hinweise)
