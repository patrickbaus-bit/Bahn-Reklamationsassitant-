# Deutschlandticket-Refund

Findet für eine Pendlerstrecke automatisch alle Verspätungen eines Gültigkeitsmonats und
erzeugt den Fahrgastrechte-Antrag für das Deutschlandticket als PDF plus fertige E-Mail.
Anders als bei [ronnyrefund.de](https://ronnyrefund.de/) muss man nicht jeden Tag einzeln
anklicken: Strecke, Pendelzeiten und Wochentage eingeben, der Monat wird komplett durchsucht.

## Nutzung

```sh
sh bootstrap.sh          # legt .venv an und installiert die Abhängigkeiten
.venv/bin/dticket-refund # öffnet http://127.0.0.1:8765/
```

1. **Persönliche Daten** einmal eingeben (Name, Adresse, E-Mail, IBAN). Sie werden lokal in
   `~/.config/dticket-refund/profil.json` gespeichert und beim nächsten Start vorbelegt.
2. **Ticket**: Gültigkeitsmonat (nur abgeschlossene Monate der letzten 12 Monate) und Ticket-/Abonummer.
3. **Pendlerstrecke**: Start, Ziel, ungefähre Abfahrtszeiten hin und zurück, Zeitfenster,
   Pendeltage und Ausnahmetage (Urlaub, Homeoffice).
4. Die App fragt für jeden Pendeltag beide Richtungen ab und listet alle Verspätungen ab 20 Minuten.
   Fahrten, die man nicht gefahren ist, werden per Haken gestrichen. **Es darf nur eingereicht werden, was tatsächlich gefahren wurde.**
5. **Versenden**: „In Apple Mail öffnen“ erzeugt einen Entwurf mit Empfänger, Betreff, Text und PDF-Anhang.
   Nur noch auf Senden klicken. Alternativ .eml-Datei (Outlook/Thunderbird), PDF-Download oder mailto-Link.

Terminal-Variante zum Testen der Datenquelle:

```sh
.venv/bin/dticket-refund suche "Frankfurt Hbf" "Darmstadt Hbf" 2026-08 --hin 07:30 --rueck 17:00
```

## Rechenregeln (Tarifbedingungen Deutschlandtarif Teil C Nr. 8.1, Stand 12/2025)

| Regel | Wert |
|---|---|
| Einzelfall ab 60 min Verspätung am Ziel (auch Ausfall, Anschlussverlust) | 1,50 EUR je Fall |
| Sammelregel: Verspätungen ab 20 min im Monat addiert | 1,50 EUR je volle 60 min |
| Kappung | 25 % des Ticketpreises (63 EUR → 15,75 EUR) |
| Bagatellgrenze | Auszahlung nur, wenn Anspruch > 4,00 EUR (ab 3 Einheiten) |
| Ticketpreis | 49 EUR (05/2023–12/2024), 58 EUR (2025), 63 EUR (2026) |
| Frist | Beschwerde binnen 3 Monaten (Art. 28 VO 2021/782); DB akzeptiert 12 Monate; Verjährung 1 Jahr |

Die App berechnet beide Rechenwege und nimmt den mit dem höheren Betrag. Pro Tag und Richtung
zählt eine Fahrt. Bei Zugausfällen wird die Ankunft mit dem nächsten gefahrenen Zug angesetzt,
ohne Folgezug pauschal 60 Minuten.

## Empfänger

Die DB nennt offiziell nur den Postweg (DB Fernverkehr AG, Servicecenter Fahrgastrechte,
60647 Frankfurt am Main) und das Online-Formular im DB-Kundenkonto. Eine offizielle
E-Mail-Adresse des Servicecenters existiert nicht. Anträge per E-Mail sind wirksam
(AG Frankfurt a. M., 29 C 599/23) und werden intern weitergeleitet; voreingestellt ist
`zentralerkundendialog@bahn.de`. Anderer Empfänger, z. B. bei einem Verbund-Ticket:

```sh
DTICKET_REFUND_EMPFAENGER=fahrgastrechte@beispiel-verbund.de .venv/bin/dticket-refund
```

## Datenquelle

Historische Echtzeitdaten gibt es bei der DB nicht per API: transport.rest, bahn.de und die
DB-Marketplace-APIs liefern nur Live-Daten, bahn.expert maximal 7 Tage zurück, zugfinder.net
nur gegen Bezahlung und ohne öffentliche API. Die App nutzt deshalb das Open-Data-Archiv
[piebro/deutsche-bahn-data](https://huggingface.co/datasets/piebro/deutsche-bahn-data)
(CC BY 4.0, Daten: Deutsche Bahn), das die DB-Timetables-API für alle Bahnhöfe pollt und pro
Monat eine Parquet-Datei mit Soll-/Ist-Zeiten und Ausfällen bereitstellt.

- Pro Monat wird die Datei einmal nach `~/.cache/dticket-refund/` geladen (100 MB bis 10/2025,
  danach ca. 600 MB) und mit DuckDB in unter zwei Sekunden für die ganze Strecke ausgewertet.
- Direktverbindungen ergeben sich aus dem Join von Abfahrt am Start und Ankunft am Ziel über
  den Fahrt-Schlüssel; gleichnamige Bahnhofsteile (Fernbahn/S-Bahn) werden zusammengefasst.
- Fernverkehr (ICE/IC/EC/FLX …) wird ausgeschlossen, alle übrigen Zuggattungen gelten als Nahverkehr.
- Bis 10/2025 enthält das Archiv nur die rund 100 größten Bahnhöfe; einzelne Stunden fehlen
  (Poll-Lücken). Der Vormonat ist in den ersten Tagen des Folgemonats vollständig.
- Die Bahnhofsliste für die Autovervollständigung wird aus dem zuletzt geladenen Monat gebaut.

Andere Datenquellen lassen sich über das `DelayProvider`-Protokoll in `provider.py` ergänzen.

## Apple Mail

„In Apple Mail öffnen“ steuert Mail per AppleScript. Beim ersten Mal fragt macOS, ob Python
Mail steuern darf; den Dialog bestätigen (Systemeinstellungen → Datenschutz & Sicherheit →
Automation) und erneut klicken. Ohne Mail.app die .eml-Datei nutzen.

## Tests

```sh
.venv/bin/python -m pytest -q
```
