"""Entschaedigungsregeln fuer das Deutschlandticket (Zeitkarte des Nahverkehrs).

Rechtsgrundlage: Art. 19 VO (EU) 2021/782 i.V.m. Tarifbedingungen des Deutschlandtarifs
Teil C (Zeitkarten) Nr. 8.1/8.2 und Teil A Nr. 8 (Stand 12/2025), einbezogen ueber die
Tarifbestimmungen Deutschlandticket Nr. 1.6. Danach gibt es zwei Rechenwege, die der
Fahrgast waehlen kann:

* Einzelfall:  je Zugausfall/Verspaetung/Anschlussversaeumnis ab 60 Minuten am Ziel 1,50 EUR.
* Sammelregel: wiederholte Verspaetungen ab 20 Minuten innerhalb des Gueltigkeitsmonats
  werden zusammengerechnet; je volle 60 Minuten 1,50 EUR.

Beides ist gedeckelt auf 25 % des gezahlten Ticketpreises; ausgezahlt wird nur, wenn der
Anspruch die Bagatellgrenze von 4 EUR ueberschreitet. Antraege werden gesammelt nach
Ablauf des Monats gestellt (Teil C Nr. 8.2).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Regelwerk:
    pauschale_eur: float = 1.50       # je Einzelfall bzw. je volle 60 Sammel-Minuten (2. Klasse)
    bagatellgrenze_eur: float = 4.00  # Anspruch muss diesen Betrag UEBERSCHREITEN
    kappung_anteil: float = 0.25      # max. 25 % des Ticketpreises pro Gueltigkeitsmonat
    schwelle_einzelfall_min: int = 60
    schwelle_sammeln_min: int = 20

    def kappung_eur(self, ticketpreis_eur: float) -> float:
        return round(ticketpreis_eur * self.kappung_anteil, 2)

    def max_einheiten(self, ticketpreis_eur: float) -> int:
        """Wie viele 1,50-EUR-Einheiten bis zur Kappung noch Geld bringen (die letzte ggf. anteilig)."""
        return math.ceil(round(self.kappung_eur(ticketpreis_eur) / self.pauschale_eur, 6))

    def min_einheiten(self) -> int:
        """Wie viele Einheiten noetig sind, um die Bagatellgrenze zu ueberschreiten."""
        n = 1
        while n * self.pauschale_eur <= self.bagatellgrenze_eur:
            n += 1
        return n

    def betrag(self, einheiten: int, ticketpreis_eur: float) -> float:
        roh = einheiten * self.pauschale_eur
        if roh <= self.bagatellgrenze_eur:
            return 0.0
        return round(min(roh, self.kappung_eur(ticketpreis_eur)), 2)

    def einheiten_einzelfall(self, verspaetungen_min: list[int]) -> int:
        return sum(1 for v in verspaetungen_min if v >= self.schwelle_einzelfall_min)

    def einheiten_sammeln(self, verspaetungen_min: list[int]) -> int:
        return sum(v for v in verspaetungen_min if v >= self.schwelle_sammeln_min) // 60


REGELN = Regelwerk()

# Monatspreis des Deutschlandtickets nach Gueltigkeitsbeginn (TB-DTX Nr. 1.4; Stand 09/2026,
# der Preis ab 2027 wird jeweils bis 30.09. des Vorjahres festgelegt).
_PREISE: list[tuple[date, float]] = [
    (date(2023, 5, 1), 49.00),
    (date(2025, 1, 1), 58.00),
    (date(2026, 1, 1), 63.00),
]


def ticketpreis(monat: date) -> float:
    """Regulaerer Preis des Deutschlandtickets fuer den gegebenen Monat."""
    preis = None
    for ab, p in _PREISE:
        if monat >= ab:
            preis = p
    if preis is None:
        raise ValueError(f"Kein Deutschlandticket vor Mai 2023 ({monat:%m/%Y}).")
    return preis
