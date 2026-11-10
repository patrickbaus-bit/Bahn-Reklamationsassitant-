# Anleitung für KI-Assistenten: Bahn-Bonus einrichten

> Aktuelle Fassung dieser Anleitung: https://raw.githubusercontent.com/patrickbaus-bit/Bahn-Reklamationsassitant-/main/AGENTS.md
> Repository: https://github.com/patrickbaus-bit/Bahn-Reklamationsassitant-
> Kannst du keine Befehle selbst ausführen (z. B. ein Chat im Browser), führe die Person durch dieselben Schritte: Gib ihr jeweils einen Befehl zum Kopieren ins Terminal und lass dir die Ausgabe zurückschicken, bevor du weitermachst.

Diese Datei richtet sich an KI-Assistenten (Claude Code, Claude, Codex, Cursor, Copilot …), die einer Person helfen, Bahn-Bonus auf ihrem Rechner zu installieren. Bahn-Bonus findet die Verspätungen auf der Pendelstrecke eines Deutschlandticket-Abos und erstellt daraus den Entschädigungsantrag (PDF + fertige E-Mail). Die Person hat oft wenig Terminal-Erfahrung. Sprich Deutsch mit ihr (außer sie schreibt in einer anderen Sprache), erkläre kurz, was du tust, und führe die Befehle selbst aus, soweit du ein Terminal hast.

## Regeln, die immer gelten

1. **Frag nie nach IBAN, Adresse, Abonummer oder anderen persönlichen Daten und gib sie nirgends ein.** Die Person trägt sie selbst in die Oberfläche der App ein; gespeichert wird nur lokal in `~/.config/dticket-refund/`. Schreibt sie dir solche Daten in den Chat, benutze sie nicht.
2. **Schick keinen Antrag ab.** Den Klick auf „Senden“ in Mail macht die Person selbst, nachdem sie die Fahrten geprüft hat. Eingereicht werden darf nur, was sie wirklich gefahren ist.
3. Ändere den Programmcode nicht, um ein Problem „wegzuhacken“. Funktioniert etwas nicht, nutze die Fehlerbehebung unten oder schlage vor, ein GitHub-Issue anzulegen.
4. Lege keine persönlichen Dateien (Profil, PDFs, Downloads) im Repository ab und committe sie nie.
5. Die Doppelklick-App gibt es nur auf **macOS**. Auf Linux oder Windows (WSL) läuft die Browser-Variante (`.venv/bin/dticket-refund`); „In Apple Mail öffnen“ geht dort nicht, .eml-Datei und PDF schon.

## Ablauf

Führe die Schritte der Reihe nach aus. Prüfe nach jedem Schritt die Ausgabe, bevor du weitermachst.

### 1. Voraussetzungen prüfen

```zsh
sw_vers -productVersion   # macOS 11 oder neuer
```

Homebrew, Git oder ein vorinstalliertes Python sind **nicht** nötig. Findet der Installer kein Python 3.10 oder neuer, holt er Python 3.12 über das Werkzeug `uv` in den Benutzerordner, ohne Admin-Passwort.

Für die Verspätungssuche braucht es Internet und **pro Monat einmal etwa 600 MB** Download sowie rund 2 GB freien Platz. Sag der Person das vorher, falls sie gerade im Mobilfunknetz ist.

### 2. Repository holen

Wenn du nicht schon im Projektordner bist (erkennbar an `bootstrap.sh` und dieser Datei), lade es ohne Git herunter (Git würde auf frischen Macs erst die Xcode-Entwicklerwerkzeuge installieren wollen):

```zsh
cd ~
curl -L -o bahn-bonus.zip https://github.com/patrickbaus-bit/Bahn-Reklamationsassitant-/archive/refs/heads/main.zip
unzip -q -o bahn-bonus.zip && rm bahn-bonus.zip
rm -rf ~/Bahn-Bonus-App && mv Bahn-Reklamationsassitant--main ~/Bahn-Bonus-App
cd ~/Bahn-Bonus-App
```

Gibt es `~/Bahn-Bonus-App` schon mit einer funktionierenden `.venv`, frag vor dem Überschreiben nach (oder aktualisiere nur, siehe „Aktualisieren“). Ist Git vorhanden (`git --version` funktioniert ohne Dialog), geht auch `git clone https://github.com/patrickbaus-bit/Bahn-Reklamationsassitant-.git ~/Bahn-Bonus-App`. Merke dir den absoluten Pfad (`pwd`).

### 3. Installieren

```zsh
sh bootstrap.sh
```

Dauert beim ersten Mal ein paar Minuten. Am Ende muss „Installation abgeschlossen“ stehen.

### 4. Prüfen, dass alles läuft

```zsh
.venv/bin/python -m pytest -q
```

Alle Tests müssen grün sein („passed“, kein „failed“).

### 5. App anlegen (macOS)

```zsh
sh app-erstellen.sh
```

Legt `Bahn-Bonus.app` auf dem Schreibtisch an (mit `sh app-erstellen.sh /Applications` stattdessen im Programme-Ordner). Die App merkt sich den Projektpfad; wird der Ordner verschoben, das Skript noch einmal ausführen.

### 6. Erster Start

```zsh
open ~/Desktop/Bahn-Bonus.app
```

Es öffnet sich ein Fenster „Bahn-Bonus – Deutschlandticket-Entschädigung“. Meldet macOS beim ersten Doppelklick, die App könne nicht geöffnet werden: Rechtsklick auf die App → **Öffnen** → **Öffnen**.

Danach übernimmt die Person selbst. Erklär ihr kurz:

- Oben die eigenen Daten eintragen (Name, Adresse, E-Mail, IBAN, Abonummer) und „Profil speichern“ klicken.
- Monat wählen (nur abgeschlossene Monate, höchstens 12 zurück), Start- und Zielbahnhof aus der Vorschlagsliste wählen, Abfahrtszeiten und Fahrtage eintragen.
- „Verspätungen suchen“: Beim ersten Mal pro Monat dauert das 1 bis 2 Minuten (Download), danach Sekunden.
- Im Ergebnis bedeutet **Haken = wird eingereicht**. Haken bei Fahrten entfernen, die sie nicht gefahren ist, dann „Neu berechnen“.
- „In Apple Mail öffnen“ erzeugt die fertige Mail mit PDF. Fragt macOS, ob Python Mail steuern darf: **OK**, dann noch einmal klicken. Senden tut sie selbst.

### 7. Abschluss

Fasse in wenigen Sätzen zusammen: wo die App liegt, dass sie einmal im Monat (am besten ein paar Tage nach Monatsende) den Vormonat beantragen kann, und dass ihre Daten nur auf ihrem Rechner liegen.

## Befehlsübersicht

| Befehl | Zweck |
|---|---|
| `sh bootstrap.sh` | Installieren bzw. Pakete aktualisieren |
| `sh app-erstellen.sh [Ordner]` | Doppelklick-App anlegen (Standard: Schreibtisch) |
| `.venv/bin/dticket-refund` | Im Browser starten, dann `http://127.0.0.1:8765/` öffnen |
| `.venv/bin/python -m dticket_refund.fenster` | Im eigenen Fenster starten (ohne App) |
| `.venv/bin/dticket-refund suche "Frankfurt Hbf" "Darmstadt Hbf" 2026-08` | Suche im Terminal (Test, ohne Antrag) |
| `.venv/bin/python -m pytest -q` | Tests |

Persönliches liegt außerhalb des Repositorys: Profil in `~/.config/dticket-refund/`, Bahn-Daten-Cache in `~/.cache/dticket-refund/`, Protokoll der App in `~/Library/Logs/bahn-bonus.log`.

## Aktualisieren

Mit Git: `git pull`, dann `sh bootstrap.sh`. Ohne Git: Schritt 2 in einen neuen Ordner ausführen, die alte `.venv` ist nicht nötig. Danach `sh bootstrap.sh` und `sh app-erstellen.sh`. Profil und Cache bleiben erhalten, weil sie nicht im Projektordner liegen.

## Fehlerbehebung

| Meldung / Problem | Lösung |
|---|---|
| `uv konnte nicht installiert werden` | Internet prüfen. Alternativ `brew install python`, dann `sh bootstrap.sh` erneut. |
| `Installation unvollständig` | Ausgabe darüber lesen. Oft fehlt Platz oder Internet. `rm -rf .venv` und `sh bootstrap.sh` erneut. |
| App startet nicht / Fenster bleibt leer | `tail -40 ~/Library/Logs/bahn-bonus.log` lesen. Läuft schon eine Instanz im Terminal, wird sie mitbenutzt. |
| „Bahn-Bonus ist nicht (mehr) eingerichtet“ | Projektordner wurde verschoben oder `.venv` gelöscht: `sh bootstrap.sh`, dann `sh app-erstellen.sh`. |
| „Daten für diesen Monat liegen noch nicht vor“ | Der Vormonat ist erst ein paar Tage nach Monatsende im Archiv. Später erneut versuchen. |
| Datei beschädigt / Suche bricht ab | Die App löscht kaputte Downloads selbst; Suche einfach wiederholen. Notfalls `rm -rf ~/.cache/dticket-refund`. |
| Bahnhof nicht in der Vorschlagsliste | Vor November 2025 enthält das Archiv nur die rund 100 größten Bahnhöfe. Es werden nur Direktverbindungen gefunden. |
| Port 8765 belegt | Eine andere Instanz läuft schon (Terminal oder App). Die schließen oder mitbenutzen. |
| „In Apple Mail öffnen“ tut nichts | Systemeinstellungen → Datenschutz & Sicherheit → Automation: Python darf „Mail“ steuern. Sonst .eml-Datei nehmen. |
