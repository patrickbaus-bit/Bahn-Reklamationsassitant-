"""Schnittstelle fuer Verspaetungs-Datenquellen.

Ein Provider liefert fuer einen Tag und eine Richtung alle direkten Nahverkehrszuege
zwischen zwei Bahnhoefen mit Soll-/Ist-Zeiten. Die konkreten Anbindungen liegen in
``sources/``; die Suche (``search.py``) kombiniert sie und filtert auf das Zeitfenster
des Pendlers.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol

from .models import Fahrt, Station


class DelayProvider(Protocol):
    name: str

    async def fahrten(self, start: Station, ziel: Station, tag: date, richtung: str) -> list[Fahrt]:
        """Alle direkten Zuege start -> ziel am Tag ``tag`` mit Echtzeitdaten."""
        ...


class StationProvider(Protocol):
    async def suche(self, text: str) -> list[Station]:
        ...
