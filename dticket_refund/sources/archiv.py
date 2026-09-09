"""Datenquelle: Open-Data-Archiv der DB-Echtzeitdaten (piebro/deutsche-bahn-data, CC BY 4.0).

Das Archiv pollt die DB-Timetables-API (IRIS) fuer alle Bahnhoefe und legt pro Monat eine
Parquet-Datei mit allen Halten (Soll-/Ist-Ankunft und -Abfahrt, Ausfaelle) ab:
https://huggingface.co/datasets/piebro/deutsche-bahn-data

Die Datei eines Monats (ca. 600 MB) wird einmal heruntergeladen und lokal gecacht; danach
laufen alle Abfragen in Sekundenbruchteilen ueber DuckDB. Direktverbindungen ergeben sich
aus dem Join von Abfahrt am Startbahnhof und Ankunft am Zielbahnhof ueber den Fahrt-Schluessel
(Prefix der ``id``: Zuglauf-ID + Datum/Uhrzeit der ersten Abfahrt).

Einschraenkungen: bis 10/2025 nur die ~100 groessten Bahnhoefe; einzelne Stunden fehlen
(Poll-Luecken); der Monat wird erst in den ersten Tagen des Folgemonats vollstaendig.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import httpx

from ..models import Fahrt, Station

log = logging.getLogger(__name__)

BASIS_URL = "https://huggingface.co/datasets/piebro/deutsche-bahn-data/resolve/main/monthly_processed_data"
CACHE_DIR = Path(os.environ.get("DTICKET_REFUND_CACHE", Path.home() / ".cache" / "dticket-refund"))
# So viele Monatsdateien bleiben im Cache; aeltere werden nach einem neuen Download geloescht.
BEHALTE_MONATE = int(os.environ.get("DTICKET_REFUND_BEHALTE_MONATE", "3"))

# Fernverkehr und Nicht-Zuege sind nicht mit dem Deutschlandticket nutzbar; alles andere
# (RE, RB, S, HLB, VIA, ME, NWB, ...) gilt als Nahverkehr.
KEIN_NAHVERKEHR = ("ICE", "IC", "EC", "ECE", "EN", "NJ", "FLX", "UEX", "RJ", "RJX", "TGV", "D", "IR",
                   "EUR", "Bus", "SBB", "TER", "REX", "WB", "ÖBA")

Fortschritt = Callable[[int, int], None]


def _evas(station: Station) -> list[str]:
    """Archiv-EVA-Nummern sind 8-stellig mit fuehrender Null ('08000105')."""
    return [e.zfill(8) for e in station.evas]


class ArchivQuelle:
    name = "DB-Echtzeitarchiv (piebro/deutsche-bahn-data)"

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._monat_cache: dict[tuple, list[Fahrt]] = {}
        self._downloads: dict[str, asyncio.Task] = {}
        self.download_status: dict[str, tuple[int, int]] = {}   # "2026-08" -> (bytes, gesamt)

    # ---- Dateien -------------------------------------------------------------------------
    def datei(self, monat: date) -> Path:
        return self.cache_dir / f"data-{monat:%Y-%m}.parquet"

    def vorhanden(self, monat: date) -> bool:
        return self.datei(monat).exists()

    def vorhandene_monate(self) -> list[date]:
        monate = []
        for p in sorted(self.cache_dir.glob("data-????-??.parquet")):
            j, m = p.stem.split("-")[1:]
            monate.append(date(int(j), int(m), 1))
        return monate

    async def lade_monat(self, monat: date) -> Path:
        """Laedt die Monatsdatei (einmalig, auch bei parallelen Aufrufen)."""
        ziel = self.datei(monat)
        if ziel.exists():
            return ziel
        key = f"{monat:%Y-%m}"
        if key not in self._downloads:
            self._downloads[key] = asyncio.create_task(self._download(monat, ziel))
        try:
            return await self._downloads[key]
        finally:
            self._downloads.pop(key, None)

    async def _download(self, monat: date, ziel: Path) -> Path:
        url = f"{BASIS_URL}/data-{monat:%Y-%m}.parquet"
        tmp = ziel.with_suffix(".part")
        key = f"{monat:%Y-%m}"
        log.info("Lade Archiv %s", url)
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60, read=120)) as client:
            async with client.stream("GET", url) as r:
                if r.status_code == 404:
                    raise FileNotFoundError(
                        f"Archivdaten fuer {monat:%m/%Y} liegen noch nicht vor (erscheinen in den ersten "
                        f"Tagen des Folgemonats).")
                r.raise_for_status()
                gesamt = int(r.headers.get("content-length", 0))
                geladen = 0
                with tmp.open("wb") as f:
                    async for chunk in r.aiter_bytes(1 << 20):
                        f.write(chunk)
                        geladen += len(chunk)
                        self.download_status[key] = (geladen, gesamt)
        self._pruefe_datei(tmp)          # beschaedigte/abgebrochene Downloads nicht uebernehmen
        tmp.replace(ziel)
        self.download_status.pop(key, None)
        self.aufraeumen()
        return ziel

    @staticmethod
    def _pruefe_datei(pfad: Path) -> None:
        import duckdb
        try:
            duckdb.connect().execute("SELECT count(*) FROM parquet_schema(?)", [str(pfad)]).fetchone()
        except Exception as e:
            pfad.unlink(missing_ok=True)
            raise RuntimeError(f"Archivdatei {pfad.name} ist beschädigt und wurde gelöscht - bitte Suche wiederholen. ({e})")

    def aufraeumen(self, behalte: int = BEHALTE_MONATE) -> list[Path]:
        """Loescht alte Monatsdateien (nur die juengsten ``behalte`` bleiben) und Download-Reste."""
        geloescht = []
        for rest in self.cache_dir.glob("*.part"):
            rest.unlink(missing_ok=True)
            geloescht.append(rest)
        monate = self.vorhandene_monate()
        for monat in monate[:-behalte] if behalte > 0 else []:
            pfad = self.datei(monat)
            pfad.unlink(missing_ok=True)
            self._monat_cache = {k: v for k, v in self._monat_cache.items() if k[0] != monat and k[-1] != monat}
            geloescht.append(pfad)
            log.info("Alte Archivdatei geloescht: %s", pfad.name)
        return geloescht

    # ---- Abfragen --------------------------------------------------------------------------
    def _abfrage(self, pfad: Path, start: Station, ziel: Station, richtung: str) -> list[Fahrt]:
        import duckdb
        typen = ", ".join(f"'{t}'" for t in KEIN_NAHVERKEHR)
        s_evas, z_evas = _evas(start), _evas(ziel)
        ph = lambda n: ", ".join("?" * n)
        sql = f"""
        WITH h AS (
            SELECT regexp_extract(id, '^(-?[0-9]+-[0-9]{{10}})', 1) AS fahrt, *
            FROM read_parquet(?)
            WHERE eva IN ({ph(len(s_evas) + len(z_evas))}) AND train_type NOT IN ({typen})
        ),
        ab AS (
            SELECT fahrt, train_type, train_number, line_number, train_line_station_num AS pos,
                   departure_planned_time AS soll_ab, departure_change_time AS ist_ab,
                   departure_is_canceled AS ab_ausfall
            FROM h WHERE eva IN ({ph(len(s_evas))}) AND departure_planned_time IS NOT NULL
        ),
        an AS (
            SELECT fahrt, train_line_station_num AS pos, arrival_planned_time AS soll_an,
                   arrival_change_time AS ist_an, arrival_is_canceled AS an_ausfall
            FROM h WHERE eva IN ({ph(len(z_evas))}) AND arrival_planned_time IS NOT NULL
        )
        SELECT ab.train_type, ab.train_number, ab.line_number, ab.soll_ab, ab.ist_ab, ab.ab_ausfall,
               an.soll_an, an.ist_an, an.an_ausfall
        FROM ab JOIN an USING (fahrt)
        WHERE fahrt <> '' AND an.pos > ab.pos AND an.soll_an > ab.soll_ab
        ORDER BY ab.soll_ab
        """
        try:
            rows = duckdb.connect().execute(sql, [str(pfad), *s_evas, *z_evas, *s_evas, *z_evas]).fetchall()
        except Exception as e:   # z.B. von Hand halb geloescht oder beschaedigt
            pfad.unlink(missing_ok=True)
            raise RuntimeError(f"Archivdatei {pfad.name} war nicht lesbar und wurde gelöscht - bitte Suche wiederholen. ({e})")
        fahrten: list[Fahrt] = []
        gesehen: set[tuple] = set()
        for typ, nr, linie, soll_ab, ist_ab, ab_ausfall, soll_an, ist_an, an_ausfall in rows:
            key = (soll_ab, nr)
            if key in gesehen:          # doppelte Halte-Eintraege (mehrere Polls) zusammenfassen
                continue
            gesehen.add(key)
            zug = f"{linie or typ} ({typ} {nr})" if linie and linie != typ else f"{typ} {nr}"
            fahrten.append(Fahrt(
                datum=soll_ab.date(), richtung=richtung, zug=zug, start=start.name, ziel=ziel.name,
                soll_ab=_dt(soll_ab), soll_an=_dt(soll_an), ist_ab=_dt(ist_ab) if ist_ab else _dt(soll_ab),
                ist_an=None if (ab_ausfall or an_ausfall) else (_dt(ist_an) if ist_an else _dt(soll_an)),
                ausgefallen=bool(ab_ausfall or an_ausfall), quelle="Archiv"))
        return fahrten

    def _stunden_ohne_daten(self, pfad: Path) -> list[datetime]:
        import duckdb
        rows = duckdb.connect().execute(
            "SELECT min(time), max(time), list(DISTINCT date_trunc('hour', time)) FROM read_parquet(?)",
            [str(pfad)]).fetchone()
        von, bis, vorhanden = rows
        if von is None:
            return []
        vorhanden = {h for h in vorhanden}
        h = von.replace(minute=0, second=0, microsecond=0)
        fehlend = []
        while h <= bis:
            if h not in vorhanden:
                fehlend.append(h)
            h += timedelta(hours=1)
        return fehlend

    async def luecken(self, monat: date) -> list[datetime]:
        """Stunden des Monats, fuer die das Archiv gar keine Halte enthaelt (Poll-Luecken)."""
        key = ("luecken", monat)
        if key not in self._monat_cache:
            pfad = await self.lade_monat(monat)
            self._monat_cache[key] = await asyncio.to_thread(self._stunden_ohne_daten, pfad)
        return self._monat_cache[key]

    async def fahrten(self, start: Station, ziel: Station, tag: date, richtung: str) -> list[Fahrt]:
        monat = tag.replace(day=1)
        if not self.vorhanden(monat):             # von Hand geloescht? -> Zwischenspeicher verwerfen, neu laden
            self._monat_cache = {k: v for k, v in self._monat_cache.items() if k[0] != monat and k[-1] != monat}
        pfad = await self.lade_monat(monat)
        key = (monat, start.id, ziel.id)
        if key not in self._monat_cache:
            self._monat_cache[key] = await asyncio.to_thread(self._abfrage, pfad, start, ziel, richtung)
        return [f for f in self._monat_cache[key] if f.datum == tag]

    # ---- Bahnhoefe -------------------------------------------------------------------------
    def stationen_datei(self) -> Path:
        return self.cache_dir / "stationen.json"

    def baue_stationsliste(self, pfad: Path) -> list[Station]:
        import duckdb
        rows = duckdb.connect().execute(
            "SELECT eva, arg_max(station_name, n) FROM (SELECT eva, station_name, count(*) n "
            "FROM read_parquet(?) GROUP BY 1, 2) GROUP BY eva", [str(pfad)]).fetchall()
        # Gleichnamige Bahnhofsteile (z.B. Fernbahn 8000105 und S-Bahn 8098105 in Frankfurt Hbf)
        # werden zu einem Eintrag mit mehreren EVA-Nummern zusammengefasst.
        nach_name: dict[str, list[str]] = {}
        for eva, name in rows:
            if name:
                nach_name.setdefault(name, []).append(eva.lstrip("0"))
        stationen = sorted((Station(",".join(sorted(evas)), name) for name, evas in nach_name.items()),
                           key=lambda s: s.name)
        self.stationen_datei().write_text(json.dumps([[s.id, s.name] for s in stationen], ensure_ascii=False))
        return stationen

    def lade_stationsliste(self) -> Optional[list[Station]]:
        try:
            return [Station(i, n) for i, n in json.loads(self.stationen_datei().read_text())]
        except (FileNotFoundError, json.JSONDecodeError):
            return None


def _dt(ts) -> datetime:
    """DuckDB liefert datetime (naiv, Europe/Berlin) - nur Nanosekunden-Reste abschneiden."""
    return ts.replace(microsecond=0) if isinstance(ts, datetime) else ts


class ArchivStationen:
    """Bahnhofssuche ueber die Namen im Archiv (kein Netzzugriff noetig, sobald ein Monat da ist)."""

    def __init__(self, archiv: ArchivQuelle):
        self.archiv = archiv
        self._liste: Optional[list[Station]] = archiv.lade_stationsliste()

    def bereit(self) -> bool:
        return self._liste is not None

    async def vorbereiten(self, monat: Optional[date] = None) -> None:
        if self._liste is not None:
            return
        monate = self.archiv.vorhandene_monate()
        pfad = self.archiv.datei(monate[-1]) if monate else await self.archiv.lade_monat(monat or _letzter_monat())
        self._liste = await asyncio.to_thread(self.archiv.baue_stationsliste, pfad)

    async def suche(self, text: str) -> list[Station]:
        await self.vorbereiten()
        woerter = _norm(text).split()
        if not woerter:
            return []
        treffer = []
        for s in self._liste or []:
            n = _norm(s.name)
            if all(w in n for w in woerter):
                # Praefix-Treffer und exakte Wortfolge zuerst, dann kurze Namen
                treffer.append(((not n.startswith(woerter[0])), (" ".join(woerter) not in n), len(n), s))
        treffer.sort(key=lambda t: t[:3])
        return [t[3] for t in treffer[:15]]


def _norm(s: str) -> str:
    return (s.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            .replace("(", " ").replace(")", " ").replace("-", " ").replace("  ", " ").strip())


def _letzter_monat() -> date:
    heute = date.today().replace(day=1)
    return (heute - timedelta(days=1)).replace(day=1)
