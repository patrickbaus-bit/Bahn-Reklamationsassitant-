"""Sucht fuer jeden Fahrtag des Monats die Zuege im Pendel-Zeitfenster heraus."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from .models import Fahrt, Pendelstrecke, Ticket
from .provider import DelayProvider

log = logging.getLogger(__name__)

Fortschritt = Callable[[int, int, str], None]


def _fenster(tag: date, uhrzeit: str, toleranz: timedelta) -> tuple[datetime, datetime]:
    h, m = (int(x) for x in uhrzeit.split(":"))
    mitte = datetime(tag.year, tag.month, tag.day, h, m)
    return mitte - toleranz, mitte + toleranz


def im_fenster(f: Fahrt, strecke: Pendelstrecke) -> bool:
    uhrzeit = strecke.hin_ab if f.richtung == "hin" else strecke.rueck_ab
    von, bis = _fenster(f.datum, uhrzeit, strecke.toleranz)
    return von <= f.soll_ab <= bis


def ergaenze_ersatzankunft(fahrten: list[Fahrt]) -> None:
    """Fuer ausgefallene Zuege die Ankunft mit dem naechsten gefahrenen Zug derselben Relation
    eintragen (Sollabfahrt nach dem Ausfall, tatsaechliche Ankunft nach dessen Sollankunft).
    Ohne Folgezug bleibt ``ersatz_an`` leer und der Ausfall zaehlt pauschal als 60 Minuten.
    """
    nach_tag: dict[tuple, list[Fahrt]] = {}
    for f in fahrten:
        nach_tag.setdefault((f.datum, f.richtung), []).append(f)
    for gruppe in nach_tag.values():
        gruppe.sort(key=lambda f: f.soll_ab)
        for f in gruppe:
            if not f.ausgefallen or f.ersatz_an is not None:
                continue
            for g in gruppe:
                if g.ausgefallen or g.soll_ab < f.soll_ab:
                    continue
                ankunft = g.ist_an or g.soll_an
                if ankunft > f.soll_an:
                    f.ersatz_an = ankunft
                    break


async def suche_verspaetungen(provider: DelayProvider, ticket: Ticket,
                              strecken: Pendelstrecke | list[Pendelstrecke],
                              fortschritt: Optional[Fortschritt] = None,
                              parallel: int = 4) -> tuple[list[Fahrt], list[str]]:
    """Liefert alle Fahrten im Zeitfenster (auch puenktliche) plus Fehlermeldungen."""
    if isinstance(strecken, Pendelstrecke):
        strecken = [strecken]
    heute = date.today()
    auftraege = []
    for strecke in strecken:
        tage = [t for t in strecke.fahrtage(ticket.erster_tag, ticket.letzter_tag) if t < heute]
        richtungen = ("hin",) if strecke.nur_hin else ("hin", "rueck")
        auftraege += [(strecke, t, r) for t in tage for r in richtungen]
    sem = asyncio.Semaphore(parallel)
    fehler: list[str] = []
    ergebnis: list[Fahrt] = []
    erledigt = 0

    async def hole(strecke: Pendelstrecke, tag: date, richtung: str):
        nonlocal erledigt
        a, b = (strecke.start, strecke.ziel) if richtung == "hin" else (strecke.ziel, strecke.start)
        async with sem:
            try:
                fahrten = await provider.fahrten(a, b, tag, richtung)
            except Exception as e:  # eine fehlende Quelle soll den Rest nicht kippen
                log.warning("%s %s %s: %s", provider.name, tag, richtung, e)
                fehler.append(f"{tag:%d.%m.%Y} {richtung}: {e}")
                fahrten = []
        ergaenze_ersatzankunft(fahrten)   # ueber alle Zuege des Tages, nicht nur im Fenster
        ergebnis.extend(f for f in fahrten if im_fenster(f, strecke))
        erledigt += 1
        if fortschritt:
            fortschritt(erledigt, len(auftraege), f"{tag:%d.%m.} {richtung}")

    await asyncio.gather(*(hole(s, t, r) for s, t, r in auftraege))
    ergebnis.sort(key=lambda f: (f.datum, f.soll_ab))
    return ergebnis, fehler
