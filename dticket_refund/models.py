"""Datenmodell: Person, Ticket, Strecke und gefundene Verspaetungen."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass
class Person:
    vorname: str
    nachname: str
    strasse: str
    plz: str
    ort: str
    email: str
    iban: str = ""            # Auszahlung per Ueberweisung; leer = Gutschein/Abo-Konto
    kontoinhaber: str = ""    # leer = Antragsteller selbst
    geburtsdatum: str = ""    # optional, manche Formulare fragen danach


@dataclass
class Ticket:
    """Das Deutschlandticket fuer den Gueltigkeitsmonat."""
    monat: date               # immer der 1. des Monats
    abonummer: str = ""       # Abo-/Auftragsnummer (bleibt ueber die Monate gleich)
    ticketnummer: str = ""    # Ticketnummer des Monats (optional)
    ausgestellt_von: str = "DB Vertrieb GmbH"   # Verkaeufer des Tickets

    @property
    def monat_label(self) -> str:
        monate = ["Januar", "Februar", "Maerz", "April", "Mai", "Juni", "Juli",
                  "August", "September", "Oktober", "November", "Dezember"]
        return f"{monate[self.monat.month - 1]} {self.monat.year}"

    @property
    def erster_tag(self) -> date:
        return self.monat.replace(day=1)

    @property
    def letzter_tag(self) -> date:
        naechster = (self.monat.replace(day=28) + timedelta(days=4)).replace(day=1)
        return naechster - timedelta(days=1)


@dataclass
class Station:
    id: str          # EVA-Nummer(n), z.B. "8000105" oder "8000105,8098105" (Fern- und S-Bahn-Teil)
    name: str

    @property
    def evas(self) -> list[str]:
        return [e.strip() for e in self.id.split(",") if e.strip()]


@dataclass
class Pendelstrecke:
    """Hin- und Rueckweg des Pendlers.

    ``hin_ab`` / ``rueck_ab`` sind die ungefaehren Abfahrtszeiten ("HH:MM");
    ``toleranz`` bestimmt, wie weit vor/nach dieser Zeit noch Zuege gesucht werden.
    ``wochentage`` sind ISO-Wochentage (1 = Montag ... 7 = Sonntag).
    """
    start: Station
    ziel: Station
    hin_ab: str = "07:30"
    rueck_ab: str = "17:00"
    toleranz: timedelta = timedelta(minutes=90)
    wochentage: tuple[int, ...] = (1, 2, 3, 4, 5)
    ausgeschlossene_tage: frozenset[date] = frozenset()   # Urlaub, Feiertage, Homeoffice
    nur_hin: bool = False     # einfache Fahrt, kein Rueckweg suchen

    @property
    def label(self) -> str:
        return f"{self.start.name} – {self.ziel.name}"

    def fahrtage(self, von: date, bis: date):
        tag = von
        while tag <= bis:
            if tag.isoweekday() in self.wochentage and tag not in self.ausgeschlossene_tage:
                yield tag
            tag += timedelta(days=1)


@dataclass
class Fahrt:
    """Eine konkrete Zugfahrt (ein Leg) mit Soll- und Ist-Zeiten."""
    datum: date
    richtung: str                     # "hin" oder "rueck"
    zug: str                          # z.B. "RE 4562"
    start: str
    ziel: str
    soll_ab: datetime
    soll_an: datetime
    ist_ab: Optional[datetime] = None
    ist_an: Optional[datetime] = None
    ausgefallen: bool = False
    quelle: str = ""                  # welche Datenquelle das geliefert hat
    ersatz_an: Optional[datetime] = None   # bei Ausfall: Ankunft mit naechster Verbindung

    @property
    def verspaetung_min(self) -> int:
        """Verspaetung am Zielbahnhof in Minuten.

        Bei einem Ausfall zaehlt die Ankunft mit der naechsten nutzbaren Verbindung;
        ist die unbekannt, wird der Ausfall als >= 60 min gewertet (konservativ nach
        Art. 19 VO (EU) 2021/782: der Fahrgast kommt erst mit dem Folgezug an).
        """
        if self.ausgefallen:
            if self.ersatz_an is None:
                return 60
            return max(0, int((self.ersatz_an - self.soll_an).total_seconds() // 60))
        if self.ist_an is None:
            return 0
        return max(0, int((self.ist_an - self.soll_an).total_seconds() // 60))

    @property
    def erstattungsfaehig(self) -> bool:
        """Einzelfallregel: ab 60 Minuten am Ziel."""
        return self.verspaetung_min >= 60

    @property
    def sammelbar(self) -> bool:
        """Sammelregel: ab 20 Minuten zaehlen die Minuten mit."""
        return self.verspaetung_min >= 20


@dataclass
class Antrag:
    """Das fertige Ergebnis: ausgewaehlte Fahrten plus Betrag."""
    person: Person
    ticket: Ticket
    strecken: list[Pendelstrecke]
    fahrten: list[Fahrt] = field(default_factory=list)      # die eingereichten
    verworfen: list[Fahrt] = field(default_factory=list)    # >= 60 min, aber ueber der Kappung
    betrag_eur: float = 0.0
    ticketpreis_eur: float = 0.0
    rechenweg: str = "einzelfall"     # "einzelfall" (ab 60 min je Fall) oder "sammeln" (ab 20 min addiert)
    einheiten: int = 0                # Anzahl 1,50-EUR-Einheiten vor Kappung
    hinweise: list[str] = field(default_factory=list)
