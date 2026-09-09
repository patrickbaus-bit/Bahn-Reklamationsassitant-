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
MIN_KURZE = 3   # so viele Faelle von 20-59 min sollen (wenn vorhanden) immer dabei sein


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


def _auswahl(kandidaten: list[Fahrt], regeln: Regelwerk, preis: float, rechenweg: str,
             erzwungen: list[Fahrt], auffuellen: bool) -> tuple[list[Fahrt], list[Fahrt], int, list[Fahrt]]:
    """(eingereicht, reserve, einheiten, unplausibel) fuer einen Rechenweg.

    ``erzwungen`` (vom Nutzer angehakt) wird zuerst uebernommen - in der Reihenfolge der
    laengsten Verspaetung, damit bei Konflikten die wertvollere Fahrt bleibt; was nicht zu
    den anderen passt, landet in ``unplausibel``. Mit ``auffuellen`` wird danach bis zur
    Kappung automatisch ergaenzt.
    """
    schwelle = regeln.schwelle_einzelfall_min if rechenweg == "einzelfall" else regeln.schwelle_sammeln_min
    zaehle = regeln.einheiten_einzelfall if rechenweg == "einzelfall" else regeln.einheiten_sammeln
    passende = [f for f in kandidaten if f.verspaetung_min >= schwelle]
    ziel = regeln.max_einheiten(preis)
    gewaehlt: list[Fahrt] = []
    unplausibel: list[Fahrt] = []
    for f in sorted(erzwungen, key=lambda f: (-f.verspaetung_min, f.datum, f.soll_ab)):
        if f.verspaetung_min < regeln.schwelle_sammeln_min:
            continue
        (gewaehlt if vertraeglich(f, gewaehlt) else unplausibel).append(f)
    if auffuellen:
        if rechenweg == "sammeln":
            # Ein paar kurze Faelle (20-59 min) gehoeren immer dazu - sie werden zusammengerechnet.
            kurze = [f for f in passende if f.verspaetung_min < regeln.schwelle_einzelfall_min]
            anzahl_kurze = lambda g: sum(1 for f in g if f.verspaetung_min < regeln.schwelle_einzelfall_min)
            _greedy(kurze, gewaehlt, lambda g: anzahl_kurze(g) >= MIN_KURZE, MIN_KURZE)
        _greedy(passende, gewaehlt, lambda g: zaehle([f.verspaetung_min for f in g]) >= ziel, len(passende))
    eingereicht = list(gewaehlt)
    # Reserve aus allen Kandidaten ab 20 min: faellt eine lange Verspaetung weg, kann die
    # Neuberechnung auf die Sammelregel wechseln und kurze Faelle brauchen.
    reserve = _greedy(kandidaten, gewaehlt, lambda g: False, RESERVE)
    return eingereicht, reserve, zaehle([f.verspaetung_min for f in eingereicht]), unplausibel


def optimiere(person: Person, ticket: Ticket, strecken: Pendelstrecke | list[Pendelstrecke],
              fahrten: list[Fahrt], regeln: Regelwerk = REGELN,
              preis_eur: float | None = None, erzwungen: list[Fahrt] | None = None,
              auffuellen: bool = True) -> Antrag:
    if isinstance(strecken, Pendelstrecke):
        strecken = [strecken]
    preis = preis_eur if preis_eur is not None else ticketpreis(ticket.monat)
    kandidaten = [f for f in fahrten if f.verspaetung_min >= regeln.schwelle_sammeln_min]
    erzwungen = erzwungen or []

    varianten = {w: _auswahl(kandidaten, regeln, preis, w, erzwungen, auffuellen) for w in ("einzelfall", "sammeln")}
    betraege = {w: regeln.betrag(v[2], preis) for w, v in varianten.items()}
    # Bei Gleichstand gewinnt die Sammelregel, damit auch kurze Faelle in den Antrag kommen.
    rechenweg = "sammeln" if betraege["sammeln"] >= betraege["einzelfall"] else "einzelfall"
    eingereicht, reserve, einheiten, unplausibel = varianten[rechenweg]
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
    minuten = [f.verspaetung_min for f in eingereicht]
    kurz = regeln.kurze_minuten(minuten)
    if rechenweg == "sammeln" and kurz:
        lange = regeln.einheiten_einzelfall(minuten)
        anzahl_kurz = sum(1 for m in minuten if m < regeln.schwelle_einzelfall_min)
        hinweise.append(
            f"Sammelregel (Teil C Nr. 8.1 Deutschlandtarif): {lange} Fälle ab 60 Minuten je eine Einheit, dazu "
            f"{anzahl_kurz} Fälle zwischen 20 und 59 Minuten mit zusammen {kurz} Minuten = {kurz // 60} weitere "
            f"Einheit(en)" + (f", {kurz % 60} Minuten Rest" if kurz % 60 else "") + ".")
    if unplausibel:
        hinweise.append(
            f"{len(unplausibel)} angehakte Fahrt(en) wurden nicht übernommen, weil sie nicht zu anderen Fahrten "
            f"desselben Tages passen (zweite Fahrt gleicher Richtung, Rückfahrt vor Ankunft oder andere Strecke): "
            + ", ".join(f"{f.datum:%d.%m.} {f.zug}" for f in unplausibel[:6]) + ("…" if len(unplausibel) > 6 else "."))
    if auffuellen and (reserve or rest):
        hinweise.append(
            f"{len(eingereicht)} Fahrten reichen für den Betrag; sie sind möglichst weit über den Monat verteilt. "
            f"Weitere {len(reserve) + len(rest)} gefundene Verspätungen stehen ohne Haken in der Liste.")
    return Antrag(person=person, ticket=ticket, strecken=strecken, fahrten=eingereicht, reserve=reserve,
                  verworfen=rest, betrag_eur=betrag, ticketpreis_eur=preis, rechenweg=rechenweg,
                  einheiten=einheiten, hinweise=hinweise)
