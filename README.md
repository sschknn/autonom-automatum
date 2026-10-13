# autonom-automatum

**Trading-Framework für Bybit EU mit deutscher Oberfläche, LLM-Assistenten und Paper-Trading-Backtest.**

Kein Signalverkäufer. Kein Gewinnversprechen. Ein Werkzeug, mit dem du Strategien
an echten Marktdaten testest, **bevor** du eigenes Geld riskierst.

```
Status:  v0.1 (früh) · 0 belegte Trades · MIT-Lizenz
```

---

## Warum es das gibt

Die meisten Trading-Bots, die man findet, sind eine von drei Sätzen:
„ Kauft wenn der MA kreuzt", „100 % Gewinn", „nur ausprobieren".

Dieses Projekt ist das Gegenteil. Es sagt dir vorher, wie teuer ein Trade ist,
bevor du ihn platzierst — und es lässt dich die Strategie wochenlang auf echten
Daten laufen, bis du eine Trefferquote **gemessen** statt **behauptet** hast.

---

## Funktionsumfang

### Echte Börsenanbindung (Bybit EU)
- V5-REST-API mit HMAC-SHA256-Signierung
- **Automatischer Zeitversatz-Ausgleich** — lokale Uhr gegen Serverzeit
- Orderbuch, Kerzendaten, Ticker, Kontostand
- Spot-Market- und Limit-Orders mit Bybit-Handelsregeln (Lot-Größe, Mindestbetrag, Tick-Größe)
- **Standard ist immer `dry_run=True`** — es wird nichts gesendet, was du nicht ausdrücklich freigibst

> 📘 **[docs/BYBIT-EU.md](docs/BYBIT-EU.md)** — die gesammelten API-Fallen der
> EU-Entity: falsche Endpunktnamen, MiCA-Paarbesonderheiten, Zeitversatz,
> Berechtigungen. Alles live verifiziert, nicht aus der Doku abgeleitet.

### Analyse
- RSI, EMA 9/21, ATR auf echten Kerzendaten
- Multi-Timeframe-Auswertung (5 min / 15 min / 1 h / 4 h)
- Ein Signal nur, wenn Zeitebenen **übereinstimmen** — sonst HALTEN

### Paper-Trading
- Vollständige Simulation mit pessimistischer Ausführung
  (Kauf immer zum Ask, Verkauf immer zum Bid, plus Slippage und Gebühren)
- Persistenter Track-Record: Equity-Kurve, Trefferquote, Profit-Faktor, Drawdown, Gebühren
- **Technisch erzwungener Schutz:** `core/paper_trader.py` enthält keinen Aufruf
  zu echten Orders — es gibt keinen Code-Pfad dorthin, auch nicht über einen Bug

### Oberfläche (deutsch)
- Kursdiagramm mit echten Kerzendaten, umschaltbarer Zeitraum
- Live-Werte, Signal mit Begründung, Risiko-Limits
- Assistent-Chat auf Deutsch mit Live-Kontext

### Assistent
- Sprachbedienung über OpenRouter
- Befehle: `%status%`, `%analyse%`, `%paper%`, `%kosten%`, `%reset%`
- **Alle Zahlen werden im Code berechnet, nicht vom Modell erfunden.**
  Das Sprachmodell formuliert, die Fakten stammen aus der Berechnung.

---

## Installation

```bash
git clone https://github.com/sschknn/autonom-automatum.git
cd autonom-automatum
pip install -r requirements.txt
```

### Am einfachsten: `start.bat`

Unter Windows genügt ein Doppelklick auf **`start.bat`**. Das Menü fragt ab,
was du willst, und prüft vorher, ob Python überhaupt installiert ist:

```
  [1] Grafische Oberfläche   [2] Status   [3] Tests   [4] Beenden:
```

### Oder einzeln in der Kommandozeile

Jeder Befehl unten ist **komplett** so einzutippen, inklusive `python`.
Ohne `python` erkennt Windows die `.py`-Datei nicht.

**Grafische Oberfläche:**
```bash
python trading_gui.py
```

**Kommandozeile:**
```bash
python cli.py status        # Zustand
python cli.py analyse       # technische Analyse
python cli.py kosten        # Roundtrip-Kosten
python cli.py paper         # Track-Record
python cli.py tick          # ein Paper-Schritt
python cli.py daemon        # Dauerlauf
python cli.py ask "Wie teuer ist ein Roundtrip? %kosten%"
```

> `cli.py` ohne Unterbefehl zeigt nur die Hilfe. Er braucht immer eines der
> Wörter `status`, `analyse`, `kosten`, `paper`, `tick`, `daemon` oder `ask`.

Python 3.10 oder neuer. Unter Linux zusätzlich `sudo apt install python3-tk`.

**Tests:**
```bash
python tests/test_kern.py
```

30 Tests ohne Netzwerkzugriff.

---

## API-Keys einrichten

Die Anwendung läuft **ohne Keys** im reinen Beobachtungs- und Dry-Run-Modus.
Für einen Verbindungstest brauchst du eigene Keys — niemals fremde.

### Bybit EU

> **Wichtig:** Binance ist seit dem 01.07.2026 ohne MiCA-Lizenz für EU-Bürger
> gesperrt. Verwende eine MiCA-lizenzierte Plattform — Bybit EU, Kraken,
> Coinbase oder OKX.

1. `bybit.eu` öffnen, **API Management → Create New Key**
2. Typ: *System-generated* (HMAC)
3. Berechtigungen:

| Recht | Setting |
|---|---|
| Read-Write | ✅ |
| **Spot → Trade** | ✅ **nur diese eine** |
| Account Transfer | ⬜ aus |
| Subaccount Transfer | ⬜ aus |
| Derivatives | ⬜ aus (nicht lizenziert für EU) |

4. IP-Whitelist setzen (empfohlen)
5. Key und Secret über den Button **API-KEYS** in der GUI eintragen
   → landet in `wallet/bybit_keys.json` (steht in `.gitignore`)

> **Achtung:** Bybit setzt `DerivativesTrade` bei Read-Write-Keys offenbar
> standardmäßig, auch wenn du den Haken nicht gesetzt hast. Prüfe es danach:
> ```powershell
> python cli.py ask "%status%"
> ```
> oder direkt im Dashboard unter API → Edit. Erscheint `Derivatives` nicht als
> leere Liste, ist es trotzdem aktiv. Details in
> [`docs/BYBIT-EU.md`](docs/BYBIT-EU.md), Abschnitt 8.

### OpenRouter (optional, für den Assistenten)

Key in `wallet/openrouter_key.json` eintragen, Modell `openrouter/free`.

---

## Wichtige Einschränkungen

**Dieses Projekt ist kein Finanzberater.** Es trifft keine Anlageempfehlung.
Handelsentscheidungen liegen ausschließlich bei dir.

**Der Bot hat bisher keinen nachgewiesenen Edge.** Stand v0.1: 0 Trades,
0 % Trefferquote gemessen. Die Strategie ist ungetestet. Rechne nicht damit,
dass sie Gewinn bringt.

**Kleines Kapital macht Trading unwirtschaftlich.** Bei 6,79 USDC kostet ein
Roundtrip 0,0136 USDC = **0,2 %**. Fünf Trades am Tag bedeuten 1 % Verlust pro
Tag allein an Gebühren. Für 5 % Gewinn muss der Kurs **5,2 %** laufen.

**Bybit EU führt keine USDT-Paare** (MiCA). Handelbar sind USDC- und
Fiat-Paare; `ETHUSDC` hat die beste Liquidität.

---

## Konfiguration

In `core/config.py` anpassbar:

```python
TICK_RATE = 1.5              # Sekunden zwischen Ticks
MAX_TRADE_QUOTE = 25.0       # Maximale Positionsgröße in USDC
MIN_RESERVE_QUOTE = 10.0     # Mindestreserve
MAX_TRADES_PER_HOUR = 5      # Handelsbremse
```

Risiko-Limits wirken **nur** auf den Exchange-Pfad. Der On-Chain-Pfad hat
getrennte Limits mit Gas-Reserve.

---

## Projektstruktur

> **Das hier ist eine Übersicht, keine Befehlsliste.** Diese Dateinamen werden
> nicht eingegeben. Zum Starten brauchst du `start.bat` oder die Befehle oben.

```
cli.py                 Kommandozeile (status, analyse, kosten, paper, daemon, ask)
trading_gui.py         Grafische Oberfläche (deutsch)
paper_runner.py        Paper-Daemon für den Dauerbetrieb
start.bat              Menü für Windows (doppelklicken)
tests/test_kern.py     30 Tests, ohne Netzwerkzugriff

core/
  bybit_exchange.py    Börsen-API, Signierung, Orders
  trading_bot.py       Signale, Multi-Timeframe, Ausführung
  paper_trader.py      Simulation + Track-Record (kein Pfad zu echten Orders)
  indicators.py        RSI, EMA, ATR
  risk_manager.py      Positions- und Verlustlimits
  assistant.py         Deutscher LLM-Assistent mit Befehlen
  openrouter.py        LLM-Anbindung
  price_feed.py        EUR-Referenzkurs (Fallback)
  wallet.py            On-Chain-Wallet mit ECDSA-Prüfung
  web3_integration.py  On-Chain-Transaktionen
  logger.py            Logging (Datei + Konsole)
  config.py            Konfiguration (alle Werte werden gelesen)
  strategies.py        Strategien

docs/
  BYBIT-EU.md          10 verifizierte API-Fallen der EU-Entity
  PUBLISH.md           Texte für X, Hacker News und LinkedIn
```

**Entfernt in v0.1:** Ein früherer Aufbau enthielt einen „Autonome KI-Firma“-Daemon
mit virtueller Bilanz, Datei-Verkauf und Marketing-Automation. Der Code erzeugte
Hash-Zeilen statt verwertbarer Produkte und wurde ersetzt, weil sich daraus kein
echtes Produkt ergab.

---

## Mitwirken

Issues und Pull Requests willkommen. Besonders interessant:
neue Strategien (`core/strategies.py`), weitere Indikatoren, weitere Börsen.

## Lizenz

MIT — siehe [LICENSE](LICENSE).

---

*Haftungsausschluss: Diese Software stellt keine Finanzberatung dar. Sie
simuliert und analysiert lediglich. Der Nutzer ist allein verantwortlich für
alle Handelsentscheidungen und trägt das volle finanzielle Risiko. Eine Haftung
für finanzielle Verluste wird ausgeschlossen, soweit gesetzlich zulässig.*
