"""Lokale Web-Oberflaeche (FastAPI): Daten eingeben -> Monat durchsuchen -> PDF & Mail."""
from __future__ import annotations

import asyncio
import logging
import secrets
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import config
from .mailout import (betreff, eml_datei, mail_app_entwurf, mailtext, mailto_link, pdf_dateiname)
from .models import Antrag, Fahrt, Pendelstrecke, Person, Station, Ticket
from .optimizer import optimiere
from .pdfgen import erzeuge_pdf
from .rules import REGELN, ticketpreis
from .search import suche_verspaetungen
from .sources import standard_provider, standard_stationen

log = logging.getLogger(__name__)


@asynccontextmanager
async def _lebenszyklus(app: FastAPI):
    """Bahnhofsliste (und dafuer den letzten abgeschlossenen Monat) im Hintergrund laden."""
    async def lauf():
        try:
            await standard_stationen().vorbereiten()
        except Exception as e:
            log.warning("Bahnhofsliste konnte nicht vorbereitet werden: %s", e)
    aufgabe = asyncio.create_task(lauf())
    yield
    aufgabe.cancel()


app = FastAPI(title="Deutschlandticket-Refund", lifespan=_lebenszyklus)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["eur"] = lambda x: f"{x:.2f} EUR".replace(".", ",")
templates.env.filters["dt"] = lambda d, fmt="%d.%m.%Y": d.strftime(fmt) if d else "–"


@dataclass
class Job:
    ticket: Ticket
    person: Person
    strecken: list[Pendelstrecke]
    erledigt: int = 0
    gesamt: int = 0
    status: str = "laeuft"
    alle: list[Fahrt] = field(default_factory=list)
    fehler: list[str] = field(default_factory=list)
    antrag: Optional[Antrag] = None
    pdf: Optional[bytes] = None
    abgewaehlt: set[int] = field(default_factory=set)   # Indizes in ``alle``, vom Nutzer gestrichen


JOBS: dict[str, Job] = {}


def _monate_zur_auswahl() -> list[tuple[str, str]]:
    """Abgeschlossene Monate der letzten 12 Monate, neuester zuerst (Frist: 1 Jahr)."""
    monate = []
    m = date.today().replace(day=1)
    for _ in range(13):
        m = (m - timedelta(days=1)).replace(day=1)
        if m < date(2023, 5, 1):
            break
        monate.append((m.isoformat(), Ticket(monat=m).monat_label))
    return monate


MAX_STRECKEN = 3
WOCHENTAGE = [(1, "Mo"), (2, "Di"), (3, "Mi"), (4, "Do"), (5, "Fr"), (6, "Sa"), (7, "So")]


@app.get("/", response_class=HTMLResponse)
async def start(request: Request):
    profil = config.lade_profil()
    strecken = profil.get("strecken") or []
    return templates.TemplateResponse(request, "start.html", {
        "person": profil.get("person", {}), "abonummer": profil.get("abonummer", ""),
        "strecken": strecken + [{}] * (MAX_STRECKEN - len(strecken)), "anzahl_aktiv": max(1, len(strecken)),
        "wochentage_liste": WOCHENTAGE, "gespeichert": bool(profil),
        "monate": _monate_zur_auswahl(), "regeln": REGELN,
        "archiv_monate": [m.isoformat() for m in standard_provider().vorhandene_monate()],
        "quelle": standard_provider().name,
    })


@app.get("/api/stationen")
async def stationen(q: str):
    if len(q.strip()) < 2:
        return JSONResponse([])
    treffer = await standard_stationen().suche(q.strip())
    return JSONResponse([{"id": s.id, "name": s.name} for s in treffer[:8]])


@app.get("/api/archiv")
async def archiv_status():
    """Welche Monate liegen lokal vor, was wird gerade geladen (Bytes, gesamt)?"""
    a = standard_provider()
    return {"monate": [m.isoformat() for m in a.vorhandene_monate()],
            "downloads": {k: {"geladen": g, "gesamt": t} for k, (g, t) in a.download_status.items()},
            "stationen_bereit": standard_stationen().bereit()}


def _person_aus(form) -> Person:
    g = lambda k: (form.get(k) or "").strip()
    return Person(g("vorname"), g("nachname"), g("strasse"), g("plz"), g("ort"), g("email"),
                  iban=g("iban").replace(" ", "").upper(), kontoinhaber=g("kontoinhaber"),
                  geburtsdatum=g("geburtsdatum"))


def _strecken_aus(form) -> tuple[list[Pendelstrecke], list[dict]]:
    """Liest bis zu MAX_STRECKEN nummerierte Streckenbloecke; leere Bloecke werden uebersprungen."""
    strecken, roh = [], []
    for n in range(1, MAX_STRECKEN + 1):
        g = lambda k, n=n: (form.get(f"{k}_{n}") or "").strip()
        if not (g("start_id") and g("ziel_id")):
            continue
        wochentage = tuple(sorted({int(x) for x in form.getlist(f"wochentage_{n}")})) or (1, 2, 3, 4, 5)
        frei = frozenset(date.fromisoformat(t.strip()) for t in g("frei").replace("\n", ",").split(",") if t.strip())
        toleranz = max(15, min(720, int(g("toleranz") or 90)))
        d = {"start_id": g("start_id"), "start_name": g("start_name"), "ziel_id": g("ziel_id"),
             "ziel_name": g("ziel_name"), "hin_ab": g("hin_ab") or "07:30", "rueck_ab": g("rueck_ab") or "17:00",
             "toleranz": toleranz, "wochentage": list(wochentage), "nur_hin": bool(g("nur_hin")), "frei": g("frei")}
        roh.append(d)
        strecken.append(Pendelstrecke(Station(d["start_id"], d["start_name"]), Station(d["ziel_id"], d["ziel_name"]),
                                      hin_ab=d["hin_ab"], rueck_ab=d["rueck_ab"], toleranz=timedelta(minutes=toleranz),
                                      wochentage=wochentage, ausgeschlossene_tage=frei, nur_hin=d["nur_hin"]))
    return strecken, roh


@app.post("/profil")
async def profil_speichern(request: Request):
    """Expliziter 'Profil speichern'-Knopf (die Suche speichert ebenfalls)."""
    form = await request.form()
    _, roh = _strecken_aus(form)
    config.speichere_profil(_person_aus(form), (form.get("abonummer") or "").strip(), roh or None)
    return {"ok": True}


@app.post("/suche")
async def suche(request: Request):
    form = await request.form()
    person = _person_aus(form)
    strecken, roh = _strecken_aus(form)
    if not strecken:
        raise HTTPException(400, "Bitte mindestens eine Strecke mit Bahnhöfen aus der Vorschlagsliste angeben.")
    ticket = Ticket(monat=date.fromisoformat(form["monat"]), abonummer=(form.get("abonummer") or "").strip(),
                    ticketnummer=(form.get("ticketnummer") or "").strip())
    config.speichere_profil(person, ticket.abonummer, roh)
    job_id = secrets.token_urlsafe(8)
    job = Job(ticket=ticket, person=person, strecken=strecken)
    JOBS[job_id] = job
    asyncio.create_task(_laufe(job))
    return RedirectResponse(f"/ergebnis/{job_id}", status_code=303)


async def _laufe(job: Job):
    def fortschritt(n, gesamt, _):
        job.erledigt, job.gesamt = n, gesamt
    try:
        job.alle, job.fehler = await suche_verspaetungen(standard_provider(), job.ticket, job.strecken, fortschritt)
        _berechne(job)
        job.status = "fertig"
    except Exception as e:
        log.exception("Suche fehlgeschlagen")
        job.fehler.append(str(e))
        job.status = "fehler"


def _berechne(job: Job):
    fahrten = [f for i, f in enumerate(job.alle) if i not in job.abgewaehlt]
    job.antrag = optimiere(job.person, job.ticket, job.strecken, fahrten)
    job.antrag.hinweise.extend(job.fehler[:5])
    job.pdf = erzeuge_pdf(job.antrag)


def _job(job_id: str) -> Job:
    if job_id not in JOBS:
        raise HTTPException(404, "Unbekannte Suche – bitte neu starten.")
    return JOBS[job_id]


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    j = _job(job_id)
    return {"status": j.status, "erledigt": j.erledigt, "gesamt": j.gesamt}


@app.get("/ergebnis/{job_id}", response_class=HTMLResponse)
async def ergebnis(request: Request, job_id: str):
    j = _job(job_id)
    if j.status == "laeuft":
        return templates.TemplateResponse(request, "warten.html", {"job_id": job_id, "job": j})
    kandidaten = [(i, f) for i, f in enumerate(j.alle) if f.sammelbar]
    a = j.antrag
    gruppe = lambda liste: {i for i, f in enumerate(j.alle) if any(f is g for g in liste)}
    return templates.TemplateResponse(request, "ergebnis.html", {
        "job_id": job_id, "job": j, "antrag": a, "kandidaten": kandidaten,
        "gewaehlt": gruppe(a.fahrten) if a else set(), "reserve": gruppe(a.reserve) if a else set(),
        "regeln": REGELN, "mailto": mailto_link(j.antrag, config.EMPFAENGER_EMAIL) if j.antrag else "",
        "empfaenger": config.EMPFAENGER_EMAIL, "online_formular": config.ONLINE_FORMULAR_URL,
        "betreff": betreff(j.antrag) if j.antrag else "",
        "mailtext": mailtext(j.antrag) if j.antrag else "", "mac": sys.platform == "darwin",
        "puenktlich": len(j.alle) - len(kandidaten),
    })


@app.post("/ergebnis/{job_id}/abwaehlen")
async def abwaehlen(request: Request, job_id: str):
    """Der Nutzer streicht Fahrten, die er nicht gefahren ist (nur echte Fahrten einreichen!)."""
    j = _job(job_id)
    form = await request.form()
    gefahren = {int(i) for i in form.getlist("gefahren")}
    kandidaten = {i for i, f in enumerate(j.alle) if f.sammelbar}
    j.abgewaehlt = kandidaten - gefahren
    _berechne(j)
    return RedirectResponse(f"/ergebnis/{job_id}", status_code=303)


@app.get("/ergebnis/{job_id}/antrag.pdf")
async def pdf(job_id: str):
    j = _job(job_id)
    if not j.pdf:
        raise HTTPException(409, "Noch kein Ergebnis.")
    return Response(j.pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{pdf_dateiname(j.antrag)}"'})


@app.get("/ergebnis/{job_id}/antrag.eml")
async def eml(job_id: str):
    j = _job(job_id)
    if not j.pdf:
        raise HTTPException(409, "Noch kein Ergebnis.")
    name = pdf_dateiname(j.antrag).replace(".pdf", ".eml")
    return Response(eml_datei(j.antrag, j.pdf, config.EMPFAENGER_EMAIL), media_type="message/rfc822",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/ergebnis/{job_id}/mail-app")
async def mail_app(job_id: str):
    j = _job(job_id)
    if not j.pdf:
        raise HTTPException(409, "Noch kein Ergebnis.")
    try:
        pfad = await asyncio.to_thread(mail_app_entwurf, j.antrag, j.pdf, config.EMPFAENGER_EMAIL)
    except Exception as e:
        return JSONResponse({"ok": False, "fehler": str(e)}, status_code=500)
    return {"ok": True, "pfad": str(pfad)}


def main():
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    port = 8765
    print(f"Deutschlandticket-Refund laeuft: http://127.0.0.1:{port}/", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
