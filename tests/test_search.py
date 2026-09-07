from datetime import date, datetime, timedelta

import pytest

from dticket_refund.models import Fahrt, Pendelstrecke, Station, Ticket
from dticket_refund.search import ergaenze_ersatzankunft, im_fenster, suche_verspaetungen


def _f(ab_h, ab_m, dauer=45, versp=0, ausgefallen=False, tag=date(2026, 8, 3), richtung="hin"):
    ab = datetime(tag.year, tag.month, tag.day, ab_h, ab_m)
    an = ab + timedelta(minutes=dauer)
    return Fahrt(tag, richtung, "RE 1", "A", "B", ab, an,
                 ist_an=None if ausgefallen else an + timedelta(minutes=versp), ausgefallen=ausgefallen)


def test_ersatzankunft_aus_folgezug():
    ausfall = _f(7, 30, ausgefallen=True)
    folge = _f(8, 0, versp=12)
    frueher = _f(7, 0)
    ergaenze_ersatzankunft([folge, ausfall, frueher])
    assert ausfall.ersatz_an == folge.ist_an
    assert ausfall.verspaetung_min == 42
    einsam = _f(7, 30, ausgefallen=True, tag=date(2026, 8, 4))
    ergaenze_ersatzankunft([einsam])
    assert einsam.ersatz_an is None and einsam.verspaetung_min == 60


def test_zeitfenster():
    strecke = Pendelstrecke(Station("1", "A"), Station("2", "B"), hin_ab="07:30", rueck_ab="17:00",
                            toleranz=timedelta(minutes=60))
    assert im_fenster(_f(6, 30), strecke) and im_fenster(_f(8, 30), strecke)
    assert not im_fenster(_f(8, 31), strecke)
    assert im_fenster(_f(17, 59, richtung="rueck"), strecke) and not im_fenster(_f(7, 30, richtung="rueck"), strecke)


class _Provider:
    name = "test"

    def __init__(self):
        self.aufrufe = []

    async def fahrten(self, start, ziel, tag, richtung):
        self.aufrufe.append((start.id, ziel.id, tag, richtung))
        if tag.day == 5:
            raise RuntimeError("Quelle weg")
        if richtung == "hin":
            return [_f(7, 32, versp=70, tag=tag), _f(12, 0, versp=90, tag=tag)]   # 12 Uhr ausserhalb
        return [_f(17, 5, versp=5, tag=tag, richtung="rueck")]


async def test_suche_ueber_den_monat(monkeypatch):
    import dticket_refund.search as s
    class _Heute(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 7)
    monkeypatch.setattr(s, "date", _Heute)
    strecke = Pendelstrecke(Station("1", "A"), Station("2", "B"), wochentage=(1,),
                            ausgeschlossene_tage=frozenset({date(2026, 8, 10)}))
    p = _Provider()
    fahrten, fehler = await suche_verspaetungen(p, Ticket(monat=date(2026, 8, 1)), strecke)
    montage = [date(2026, 8, 3), date(2026, 8, 17), date(2026, 8, 24), date(2026, 8, 31)]
    assert sorted({a[2] for a in p.aufrufe}) == montage
    assert ("2", "1", date(2026, 8, 3), "rueck") in p.aufrufe          # Rueckweg vertauscht
    assert len(fahrten) == 2 * len(montage) and fehler == []
    assert sum(f.erstattungsfaehig for f in fahrten) == len(montage)
