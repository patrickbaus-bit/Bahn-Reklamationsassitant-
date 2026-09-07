"""Konkrete Datenquellen. ``standard_provider()`` liefert die konfigurierte Quelle."""
from __future__ import annotations

from functools import lru_cache

from .archiv import ArchivQuelle, ArchivStationen


@lru_cache(maxsize=1)
def standard_provider() -> ArchivQuelle:
    return ArchivQuelle()


@lru_cache(maxsize=1)
def standard_stationen() -> ArchivStationen:
    return ArchivStationen(standard_provider())
