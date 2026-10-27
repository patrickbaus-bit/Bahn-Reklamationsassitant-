# Deutschlandticket-Refund

Wer mit dem Deutschlandticket pendelt, hat bei Verspätungen Anspruch auf Entschädigung, muss
dafür aber jede verspätete Fahrt selbst heraussuchen und beantragen. Dieses Programm macht das
automatisch: Du gibst einmal deine Daten und deine Pendelstrecke ein, wählst den Monat, und die
App sucht alle Verspätungen heraus, stellt den Antrag als PDF zusammen und öffnet eine fertige
E-Mail an die Bahn. Du musst nur noch auf „Senden“ klicken.

Das Programm läuft komplett auf deinem eigenen Rechner. Es gibt keinen Server im Internet, dem
du deine Daten anvertraust.

## Schnellstart

Einmalig einrichten (installiert alles Nötige in einen Unterordner `.venv`):

```sh
sh bootstrap.sh
```

Danach jedes Mal starten mit:

```sh
.venv/bin/dticket-refund
```

Dann im Browser `http://127.0.0.1:8765/` öffnen. Voraussetzung ist Python 3.10 oder neuer,
auf dem Mac zum Beispiel über `brew install python`.

### Im eigenen App-Fenster statt im Browser (Mac)

```sh
.venv/bin/python -m dticket_refund.fenster
```

Öffnet die Oberfläche in einem eigenen Fenster. Schließt man das Fenster, wird das Programm
komplett beendet. PDF und .eml landen im Download-Ordner und öffnen sich direkt in Vorschau
bzw. Mail.

Wer das per Doppelklick starten möchte, legt sich ein kleines App-Bundle an, zum Beispiel
`Bahn-Bonus.app` auf dem Schreibtisch. Darin liegt unter `Contents/MacOS/Bahn-Bonus` ein
ausführbares Skript, das in den Projektordner wechselt und diesen Befehl startet. Mit
`--icon pfad/zum/icon.icns` zeigt das Dock ein eigenes Symbol.

## So funktioniert die Bedienung

1. **Persönliche Daten** eingeben: Name, Adresse, E-Mail, IBAN, Abonummer des Tickets.
   Mit „Profil speichern“ merkt sich die App alles für das nächste Mal. Gespeichert wird nur
   lokal in einer kleinen Datei unter `~/.config/dticket-refund/`.
2. **Monat** wählen. Beantragt werden kann immer nur ein abgeschlossener Monat, höchstens
   zwölf Monate zurück.
3. **Strecken** eintragen: Start und Ziel (aus der Vorschlagsliste auswählen), ungefähre
   Abfahrtszeit hin und zurück, wie groß das Zeitfenster darum sein soll, an welchen Wochentagen
   du fährst und an welchen Tagen nicht (Urlaub, Homeoffice). Bis zu drei Strecken sind möglich,
   etwa für Wochenendfahrten oder einen zweiten Arbeitsort.
4. **Verspätungen suchen.** Die App prüft jeden Fahrtag in beide Richtungen. Beim ersten Mal
   lädt sie dafür die Daten des Monats herunter, das dauert je nach Verbindung ein bis zwei Minuten.
5. **Ergebnis prüfen.** Du siehst den Erstattungsbetrag und eine Liste aller gefundenen
   Verspätungen. Die App hat bereits eine sinnvolle Auswahl angehakt. **Haken bedeutet: wird
   eingereicht.** Entferne den Haken bei Fahrten, die du an dem Tag nicht gefahren bist, und
   klicke „Neu berechnen“. Es darf nur eingereicht werden, was du wirklich gefahren bist.
6. **Versenden.** „In Apple Mail öffnen“ erzeugt eine fertige E-Mail mit Empfänger, Text und
   dem Antrag als PDF im Anhang. Alternativ kannst du das PDF herunterladen, eine .eml-Datei
   für Outlook oder Thunderbird erzeugen oder einen mailto-Link nutzen.

## Wie die Entschädigung berechnet wird

Grundlage sind die Tarifbedingungen des Deutschlandtarifs (Teil C, Nr. 8.1) und die
EU-Fahrgastrechteverordnung. In Kurzform:

| Regel | Was sie bedeutet |
|---|---|
| Verspätungsfall | Kommt dein Zug am Ziel 60 Minuten oder mehr zu spät an oder fällt aus, gibt es 1,50 EUR. Egal wie lang die Verspätung war, ein Fall ist ein Fall. |
| Kurze Verspätungen | Verspätungen zwischen 20 und 59 Minuten dürfen im Monat zusammengerechnet werden. Je volle 60 Minuten dieser Summe gibt es 1,50 EUR extra. |
| Obergrenze | Mehr als 25 % des Ticketpreises gibt es pro Monat nicht. Bei 63 EUR sind das 15,75 EUR. |
| Bagatellgrenze | Ausgezahlt wird nur, wenn der Anspruch über 4 EUR liegt. Dafür braucht man mindestens drei Fälle. |
| Ticketpreis | 49 EUR bis Ende 2024, 58 EUR in 2025, 63 EUR seit 2026. Die App setzt ihn automatisch. |
| Frist | Am besten innerhalb von drei Monaten einreichen; die Bahn nimmt Anträge bis zu zwölf Monate an. |

Bei einem Zugausfall zählt die Ankunft mit dem nächsten Zug, der tatsächlich gefahren ist.
Findet die App keinen Folgezug, setzt sie pauschal 60 Minuten an und markiert den Fall.

## Wie die App die Fahrten auswählt

Damit der Antrag glaubwürdig ist und nicht mehr Fahrten enthält als nötig, gelten Regeln:

- Pro Tag höchstens eine Hinfahrt und eine Rückfahrt. Die Rückfahrt muss nach der Ankunft der
  Hinfahrt abfahren und auf derselben Strecke liegen.
- Die Fahrten werden möglichst gleichmäßig über den Monat verteilt statt an wenigen Tagen gehäuft.
- Es kommen immer auch ein paar kurze Verspätungen (20 bis 59 Minuten) in den Antrag, die
  zusammengerechnet werden, sofern es welche gibt.
- Eingereicht wird nur so viel, wie für die Obergrenze nötig ist. Alle weiteren gefundenen
  Verspätungen stehen ohne Haken in der Liste und lassen sich bei Bedarf anhaken.
- Fälle, die die Bahn anders bewerten könnte, sind mit ⚠ markiert: Verspätungen knapp über
  20 oder 60 Minuten und pauschal angesetzte Ausfälle. Die App bevorzugt robuste Fälle.

## Woher die Verspätungsdaten kommen

Die Bahn bietet keine Schnittstelle an, über die man Verspätungen rückwirkend für einen ganzen
Monat abfragen kann. Deshalb nutzt die App ein frei verfügbares Archiv: Der Datensatz
[piebro/deutsche-bahn-data](https://huggingface.co/datasets/piebro/deutsche-bahn-data)
(Lizenz CC BY 4.0, Daten der Deutschen Bahn) fragt rund um die Uhr die offizielle Echtzeit-
Schnittstelle der Bahn ab, also dieselben Daten, die auch die Anzeigetafeln an den Bahnhöfen
speisen, und stellt daraus für jeden Monat eine Datei mit allen Zughalten in Deutschland bereit.

Was das für dich bedeutet:

- **Download nur einmal pro Monat.** Die Datei eines Monats ist etwa 600 MB groß (für Monate
  vor November 2025 etwa 100 MB) und wird unter `~/.cache/dticket-refund/` gespeichert. Alle
  weiteren Suchen in diesem Monat dauern nur Sekunden.
- **Automatisches Aufräumen.** Es bleiben immer nur die drei zuletzt geladenen Monate liegen.
  Ältere Dateien löscht die App nach einem neuen Download selbst. Wer mehr behalten möchte,
  setzt die Umgebungsvariable `DTICKET_REFUND_BEHALTE_MONATE`, zum Beispiel auf 6.
- **Selbst löschen ist erlaubt.** Du kannst den Ordner `~/.cache/dticket-refund/` jederzeit
  leeren. Fehlt eine Datei, lädt die App sie beim nächsten Suchen einfach neu. Beschädigte
  oder halb heruntergeladene Dateien erkennt sie, löscht sie und meldet, dass die Suche
  wiederholt werden soll.
- **Der Vormonat ist erst nach ein paar Tagen komplett.** Wer am 1. des Monats sucht, bekommt
  eventuell noch die Meldung, dass die Daten noch nicht vorliegen.
- **Grenzen der Daten.** Vor November 2025 enthält das Archiv nur die rund 100 größten Bahnhöfe.
  Vereinzelt fehlen ganze Stunden; die App zeigt an, wenn eine solche Lücke in dein Pendelfenster
  fällt. Es werden nur Direktverbindungen gefunden, keine Umsteigeverbindungen.

Für Entwickler: Die Auswertung läuft lokal mit DuckDB direkt auf der Parquet-Datei
(`dticket_refund/sources/archiv.py`). Andere Datenquellen lassen sich über das
`DelayProvider`-Protokoll in `provider.py` ergänzen.

## Wohin der Antrag geht

Die Bahn nennt offiziell nur zwei Wege: das Online-Formular im DB-Kundenkonto und den Postweg
an das Servicecenter Fahrgastrechte, 60647 Frankfurt am Main. Eine offizielle E-Mail-Adresse
des Servicecenters gibt es nicht. Anträge per E-Mail sind trotzdem wirksam (Amtsgericht
Frankfurt, Urteil 29 C 599/23) und werden intern weitergeleitet. Voreingestellt ist deshalb
die Adresse des Zentralen Kundendialogs der Bahn, `zentralerkundendialog@bahn.de`, die auch
andere Tools nutzen. Wer auf Nummer sicher gehen will, überträgt die Fahrten aus dem PDF ins
Online-Formular oder schickt das PDF per Post.

Hast du das Ticket nicht bei der Bahn, sondern bei einem Verkehrsverbund gekauft, ist dieser
zuständig. Den Empfänger kannst du beim Start ändern:

```sh
DTICKET_REFUND_EMPFAENGER=fahrgastrechte@beispiel-verbund.de .venv/bin/dticket-refund
```

## Apple Mail

Der Knopf „In Apple Mail öffnen“ steuert Mail per AppleScript. Beim ersten Mal fragt macOS,
ob Python das Programm Mail steuern darf. Diesen Dialog bestätigen und noch einmal klicken.
Wer kein Apple Mail nutzt, nimmt die .eml-Datei.

## Für Entwickler

```sh
.venv/bin/python -m pytest -q                                   # Tests
.venv/bin/dticket-refund suche "Frankfurt Hbf" "Darmstadt Hbf" 2026-08   # Suche im Terminal
```

Aufbau: `models.py` (Datenmodell), `rules.py` (Tarifregeln), `optimizer.py` (Auswahl der
Fahrten), `search.py` (Monatssuche), `sources/archiv.py` (Datenquelle), `pdfgen.py`,
`mailout.py`, `web.py` (Oberfläche), `fenster.py` (eigenes App-Fenster), `cli.py`.
