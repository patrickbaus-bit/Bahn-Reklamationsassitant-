"""Archiv-Provider gegen eine kleine synthetische Parquet-Datei im Archivformat."""
from datetime import date, datetime

import duckdb
import pytest

from dticket_refund.models import Station
from dticket_refund.sources.archiv import ArchivQuelle, ArchivStationen

SPALTEN = ("station_name", "xml_station_name", "eva", "train_number", "line_number", "final_destination_station",
           "delay_in_min", "time", "arrival_is_canceled", "departure_is_canceled", "train_type",
           "train_line_ride_id", "train_line_station_num", "arrival_planned_time", "arrival_change_time",
           "departure_planned_time", "departure_change_time", "id")


def _halt(station, eva, nr, linie, typ, ride, pos, an_soll=None, an_ist=None, ab_soll=None, ab_ist=None,
          an_x=False, ab_x=False, tag="2608030700"):
    return (station, station, eva, nr, linie, "Ziel", 0, ab_soll or an_soll, an_x, ab_x, typ, ride, pos,
            an_soll, an_ist, ab_soll, ab_ist, f"{ride}-{tag}-{pos}")


@pytest.fixture
def archiv(tmp_path):
    d = lambda h, m, tag=3: datetime(2026, 8, tag, h, m)
    zeilen = [
        # RE 4655: A ab 07:31, B an 07:51, 65 min spaet in B
        _halt("A Hbf", "08000001", "4655", "RE60", "RE", "-1111", 2, ab_soll=d(7, 31), ab_ist=d(7, 40)),
        _halt("A Hbf", "08000001", "4655", "RE60", "RE", "-1111", 2, ab_soll=d(7, 31), ab_ist=d(7, 45)),  # Doppel-Poll
        _halt("B Hbf", "08000002", "4655", "RE60", "RE", "-1111", 5, an_soll=d(7, 51), an_ist=d(8, 56)),
        # S-Bahn-Teil von A (andere EVA), puenktlich
        _halt("A Hbf", "08098001", "36611", "S6", "S", "2222", 1, ab_soll=d(7, 47)),
        _halt("B Hbf", "08000002", "36611", "S6", "S", "2222", 9, an_soll=d(8, 26)),
        # Ausfall in B
        _halt("A Hbf", "08000001", "15307", "RB68", "RB", "-3333", 3, ab_soll=d(7, 6)),
        _halt("B Hbf", "08000002", "15307", "RB68", "RB", "-3333", 7, an_soll=d(7, 25), an_x=True),
        # ICE zaehlt nicht
        _halt("A Hbf", "08000001", "77", None, "ICE", "4444", 1, ab_soll=d(7, 0)),
        _halt("B Hbf", "08000002", "77", None, "ICE", "4444", 2, an_soll=d(7, 15), an_ist=d(9, 0)),
        # Gegenrichtung B -> A (darf bei hin nicht auftauchen)
        _halt("B Hbf", "08000002", "4656", "RE60", "RE", "5555", 1, ab_soll=d(7, 20)),
        _halt("A Hbf", "08000001", "4656", "RE60", "RE", "5555", 4, an_soll=d(7, 40)),
        # Anderer Tag
        _halt("A Hbf", "08000001", "4655", "RE60", "RE", "-1111", 2, ab_soll=d(7, 31, 4), tag="2608040700"),
        _halt("B Hbf", "08000002", "4655", "RE60", "RE", "-1111", 5, an_soll=d(7, 51, 4), an_ist=d(7, 53, 4), tag="2608040700"),
    ]
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t ({', '.join(f'{c} ' + typ for c, typ in zip(SPALTEN, ['VARCHAR']*6 + ['INTEGER', 'TIMESTAMP', 'BOOLEAN', 'BOOLEAN', 'VARCHAR', 'VARCHAR', 'INTEGER'] + ['TIMESTAMP']*4 + ['VARCHAR']))})")
    con.executemany(f"INSERT INTO t VALUES ({', '.join('?' * len(SPALTEN))})", zeilen)
    q = ArchivQuelle(cache_dir=tmp_path)
    con.execute(f"COPY t TO '{q.datei(date(2026, 8, 1))}' (FORMAT PARQUET)")
    return q


async def test_direktverbindungen_mit_mehreren_evas(archiv):
    a, b = Station("8000001,8098001", "A Hbf"), Station("8000002", "B Hbf")
    fahrten = await archiv.fahrten(a, b, date(2026, 8, 3), "hin")
    assert [f.zug for f in fahrten] == ["RB68 (RB 15307)", "RE60 (RE 4655)", "S6 (S 36611)"]
    re = fahrten[1]
    assert re.verspaetung_min == 65 and re.ist_ab == datetime(2026, 8, 3, 7, 40)
    assert fahrten[0].ausgefallen and fahrten[0].ist_an is None
    assert fahrten[2].verspaetung_min == 0 and fahrten[2].ist_an == fahrten[2].soll_an
    naechster = await archiv.fahrten(a, b, date(2026, 8, 4), "hin")
    assert len(naechster) == 1 and naechster[0].verspaetung_min == 2


async def test_gegenrichtung(archiv):
    fahrten = await archiv.fahrten(Station("8000002", "B Hbf"), Station("8000001", "A Hbf"), date(2026, 8, 3), "rueck")
    assert [f.zug for f in fahrten] == ["RE60 (RE 4656)"] and fahrten[0].richtung == "rueck"


async def test_fehlender_monat_meldet_verstaendlich(archiv, monkeypatch):
    import dticket_refund.sources.archiv as m
    monkeypatch.setattr(m, "BASIS_URL", "https://huggingface.co/datasets/piebro/deutsche-bahn-data/resolve/main/gibts-nicht")
    with pytest.raises(Exception) as e:
        await archiv.fahrten(Station("8000001", "A"), Station("8000002", "B"), date(2019, 1, 7), "hin")
    assert "01/2019" in str(e.value) or "404" in str(e.value)


async def test_stationsliste_fasst_gleichnamige_zusammen(archiv):
    st = ArchivStationen(archiv)
    await st.vorbereiten()
    treffer = await st.suche("a hbf")
    assert [(s.id, s.name) for s in treffer] == [("8000001,8098001", "A Hbf")]
    assert archiv.stationen_datei().exists()
    assert (await st.suche("hbf"))[0].name in ("A Hbf", "B Hbf")


async def test_luecken_erkennung(archiv):
    luecken = await archiv.luecken(date(2026, 8, 1))
    # Testdaten haben Halte am 3.8. (06:xx-08:xx) und 4.8. 07:xx -> dazwischen fehlen Stunden
    assert luecken and all(l.minute == 0 for l in luecken)
    assert datetime(2026, 8, 3, 12, 0) in luecken and datetime(2026, 8, 3, 7, 0) not in luecken


async def test_aufraeumen_behaelt_nur_juengste_monate(archiv):
    for m in ("2025-09", "2025-10", "2026-05", "2026-06"):
        (archiv.cache_dir / f"data-{m}.parquet").write_bytes(b"alt")
    (archiv.cache_dir / "data-2026-07.parquet.part").write_bytes(b"abgebrochen")
    geloescht = archiv.aufraeumen(behalte=3)
    bleiben = sorted(p.name for p in archiv.cache_dir.glob("data-*.parquet"))
    assert bleiben == ["data-2026-05.parquet", "data-2026-06.parquet", "data-2026-08.parquet"]
    assert not list(archiv.cache_dir.glob("*.part")) and len(geloescht) == 3


async def test_beschaedigte_datei_wird_entfernt(archiv):
    kaputt = archiv.datei(date(2026, 8, 1))
    kaputt.write_bytes(b"kein parquet")
    with pytest.raises(RuntimeError, match="gelöscht"):
        await archiv.fahrten(Station("8000001", "A"), Station("8000002", "B"), date(2026, 8, 3), "hin")
    assert not kaputt.exists()


async def test_geloeschte_datei_wird_neu_geladen(archiv, monkeypatch):
    a, b = Station("8000001,8098001", "A Hbf"), Station("8000002", "B Hbf")
    assert len(await archiv.fahrten(a, b, date(2026, 8, 3), "hin")) == 3   # fuellt den Zwischenspeicher
    archiv.datei(date(2026, 8, 1)).unlink()
    aufrufe = []
    async def fake_download(monat, ziel):
        aufrufe.append(monat); raise FileNotFoundError("Archiv nicht da")
    monkeypatch.setattr(archiv, "_download", fake_download)
    with pytest.raises(FileNotFoundError):
        await archiv.fahrten(a, b, date(2026, 8, 3), "hin")
    assert aufrufe == [date(2026, 8, 1)]                                    # Download wurde neu angestossen
