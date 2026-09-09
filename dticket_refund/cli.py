"""Kommandozeile: ``dticket-refund`` startet die Web-Oberflaeche, ``dticket-refund suche``
durchsucht einen Monat direkt im Terminal (praktisch zum Testen der Datenquelle)."""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta

from .models import Pendelstrecke, Station, Ticket
from .search import suche_verspaetungen
from .sources import standard_provider, standard_stationen


async def _suche(args):
    stationen = standard_stationen()
    # Bahnhofsliste aus dem gewuenschten Monat bauen, damit nicht zusaetzlich der letzte Monat geladen wird
    await stationen.vorbereiten(date.fromisoformat(args.monat + "-01"))
    start = (await stationen.suche(args.von))[0]
    ziel = (await stationen.suche(args.nach))[0]
    print(f"{start.name} ({start.id}) -> {ziel.name} ({ziel.id})", file=sys.stderr)
    strecke = Pendelstrecke(start, ziel, hin_ab=args.hin, rueck_ab=args.rueck,
                            toleranz=timedelta(minutes=args.toleranz))
    ticket = Ticket(monat=date.fromisoformat(args.monat + "-01"))

    def fortschritt(n, gesamt, was):
        print(f"\r{n}/{gesamt} {was}     ", end="", file=sys.stderr, flush=True)

    fahrten, fehler = await suche_verspaetungen(standard_provider(), ticket, [strecke], fortschritt)
    print(file=sys.stderr)
    for f in fahrten:
        if f.verspaetung_min >= args.ab or f.ausgefallen:
            if f.ausgefallen:
                an = "AUSFALL" if f.ersatz_an is None else f"AUSFALL, Ersatz {f.ersatz_an:%H:%M}"
            else:
                an = f"{f.ist_an:%H:%M}"
            print(f"{f.datum:%d.%m.} {f.richtung:5} {f.zug:10} {f.soll_ab:%H:%M}->{f.soll_an:%H:%M} "
                  f"ist {an}  +{f.verspaetung_min:3d} min  [{f.quelle}]")
    print(f"{len(fahrten)} Fahrten im Zeitfenster, {sum(f.erstattungsfaehig for f in fahrten)} davon >= 60 min",
          file=sys.stderr)
    for e in fehler:
        print("Fehler:", e, file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(prog="dticket-refund", description=__doc__)
    sub = p.add_subparsers(dest="befehl")
    s = sub.add_parser("suche", help="Monat im Terminal durchsuchen")
    s.add_argument("von"); s.add_argument("nach"); s.add_argument("monat", help="JJJJ-MM")
    s.add_argument("--hin", default="07:30"); s.add_argument("--rueck", default="17:00")
    s.add_argument("--toleranz", type=int, default=90, help="Minuten um die Abfahrtszeit")
    s.add_argument("--ab", type=int, default=20, help="Nur Fahrten ab so vielen Minuten anzeigen")
    sub.add_parser("web", help="Web-Oberflaeche starten (Standard)")
    args = p.parse_args(argv)
    if args.befehl == "suche":
        asyncio.run(_suche(args))
    else:
        from .web import main as web_main
        web_main()


if __name__ == "__main__":
    main()
