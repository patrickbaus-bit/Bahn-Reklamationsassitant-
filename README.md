# Bahn-Bonus – Deutschlandticket-Entschädigung auf Knopfdruck

Wer mit dem Deutschlandticket pendelt, hat bei Verspätungen Anspruch auf Geld zurück, bis zu
**15,75 EUR pro Monat** (25 % von 63 EUR). Kaum jemand holt es sich, weil man dafür jede
verspätete Fahrt selbst heraussuchen, mit Zugnummer und Uhrzeit aufschreiben und beantragen muss.

Bahn-Bonus macht das automatisch: Du gibst einmal deine Daten und deine Pendelstrecke ein,
wählst den Monat, und die App sucht alle Verspätungen heraus, wählt die passenden Fahrten aus,
stellt den Antrag als PDF zusammen und öffnet eine fertige E-Mail an die Bahn. Du prüfst die
Liste und klickst auf „Senden“. Einmal im Monat, etwa fünf Minuten.

- **Läuft komplett auf deinem Rechner.** Kein Konto, kein Server, keine Provision. Name, IBAN
  und Abonummer bleiben in einer Datei auf deinem Mac.
- **Echte Daten statt Schätzung.** Grundlage sind die offiziellen Echtzeitdaten der Bahn
  (dieselben wie auf den Anzeigetafeln), rückwirkend für den ganzen Monat.
- **Kennt die Tarifregeln.** Einzelfälle ab 60 Minuten, Sammelregel für 20 bis 59 Minuten,
  Obergrenze, Bagatellgrenze und Ticketpreis je Jahr sind eingebaut.

**Voraussetzungen:** ein Mac mit macOS 11 oder neuer (Apple Silicon oder Intel) und Internet.
Homebrew, Python oder Admin-Rechte brauchst du nicht. Linux geht auch, dann im Browser statt
als App.

---

## Einrichtung mit KI (empfohlen)

Du musst nichts selbst im Terminal machen: Ein KI-Assistent mit Terminal-Zugriff richtet alles
für dich ein, zum Beispiel **Claude** (Claude-Desktop-App mit Zugriff auf deinen Mac, oder
Claude Code), **Codex** oder **Cursor**. Kopiere einfach diesen Text hinein:

```text
Richte mir bitte Bahn-Bonus (Deutschlandticket-Entschädigung) auf meinem Mac ein. Die komplette Anleitung für dich steht hier:
https://raw.githubusercontent.com/patrickbaus-bit/Bahn-Reklamationsassitant-/main/AGENTS.md
Lies sie zuerst vollständig und folge ihr Schritt für Schritt.
```

Das passiert danach, und das machst du dabei:

1. **Erlauben.** Die KI fragt vor jedem Befehl um Erlaubnis.
2. **Warten.** Die Installation dauert ein paar Minuten. Am Ende liegt **Bahn-Bonus** mit
   Bahn-Symbol auf deinem Schreibtisch, und die App öffnet sich.
3. **Deine Daten trägst du selbst in die App ein**, nicht in den Chat. Die KI fragt nie nach
   IBAN oder Abonummer.

Nutzt du eine KI ohne Terminal-Zugriff (z. B. ChatGPT im Browser), funktioniert der gleiche
Text auch: Dann erklärt sie dir Schritt für Schritt, was du ins Terminal kopieren sollst.

---

## Installation von Hand (einmalig, ca. 5 Minuten)

Öffne das Programm **Terminal** (Cmd + Leertaste → „Terminal“) und kopiere diese Zeilen hinein:

```zsh
cd ~
curl -L -o bahn-bonus.zip https://github.com/patrickbaus-bit/Bahn-Reklamationsassitant-/archive/refs/heads/main.zip
unzip -q -o bahn-bonus.zip && rm bahn-bonus.zip
mv Bahn-Reklamationsassitant--main Bahn-Bonus-App && cd Bahn-Bonus-App
sh bootstrap.sh
sh app-erstellen.sh
```

Das lädt das Programm in den Ordner `Bahn-Bonus-App` in deinem Benutzerordner, installiert
alles Nötige in dessen Unterordner `.venv` und legt **Bahn-Bonus.app** auf den Schreibtisch.
Findet der Installer kein passendes Python, holt er sich selbst eines (über das Werkzeug
[uv](https://docs.astral.sh/uv/), ohne Admin-Passwort). Mit Git geht statt der ersten drei
Zeilen auch `git clone https://github.com/patrickbaus-bit/Bahn-Reklamationsassitant-.git Bahn-Bonus-App`.

Starten per **Doppelklick auf Bahn-Bonus** auf dem Schreibtisch. Meldet macOS beim ersten Mal,
die App könne nicht geöffnet werden: Rechtsklick → **Öffnen** → **Öffnen**. Schließt du das
Fenster, ist das Programm komplett beendet. PDF und .eml landen im Download-Ordner.

Ohne App, im Browser (auch auf Linux):

```zsh
~/Bahn-Bonus-App/.venv/bin/dticket-refund
```

Dann `http://127.0.0.1:8765/` öffnen.

**Aktualisieren:** mit Git `git pull && sh bootstrap.sh`, sonst die Zeilen oben einfach noch
einmal ausführen (vorher den alten Ordner löschen). Dein Profil und die geladenen Bahn-Daten
bleiben erhalten, weil sie nicht im Programmordner liegen.

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
- Angehakt wird nur so viel, wie für die Obergrenze nötig ist: Jede vorausgewählte Fahrt
  trägt zum Betrag bei, streicht man eine, sinkt er. Die App probiert dafür beide Rechenwege
  (nur Fälle ab 60 Minuten oder zusätzlich die Sammelregel) und nimmt die Auswahl mit den
  wenigsten Fahrten.
- Alle weiteren gefundenen Verspätungen stehen ohne Haken in der Liste. Fährst du eine
  angehakte Fahrt doch nicht, hakst du stattdessen eine andere an und klickst „Neu berechnen“.
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
sh bootstrap.sh                                                 # Einrichten / aktualisieren
sh app-erstellen.sh [Ordner]                                    # Doppelklick-App anlegen
.venv/bin/python -m pytest -q                                   # Tests
.venv/bin/dticket-refund suche "Frankfurt Hbf" "Darmstadt Hbf" 2026-08   # Suche im Terminal
```

Aufbau: `models.py` (Datenmodell), `rules.py` (Tarifregeln), `optimizer.py` (Auswahl der
Fahrten), `search.py` (Monatssuche), `sources/archiv.py` (Datenquelle), `pdfgen.py`,
`mailout.py`, `web.py` (Oberfläche), `fenster.py` (eigenes App-Fenster), `cli.py`.

`AGENTS.md` ist die Schritt-für-Schritt-Anleitung, mit der KI-Assistenten das Programm einrichten.

## Hinweis

Bahn-Bonus ist ein privates Projekt und gehört nicht zur Deutschen Bahn. Die App erstellt
den Antrag, prüfen und absenden tust du selbst. Reiche nur Fahrten ein, die du wirklich gefahren bist.
Verspätungsdaten: [piebro/deutsche-bahn-data](https://huggingface.co/datasets/piebro/deutsche-bahn-data), CC BY 4.0.
