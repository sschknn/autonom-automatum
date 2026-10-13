# Installations-Anleitung (deutsch)

## 1. Voraussetzungen

- **Python 3.10 oder neuer**
  Prüfen: `python --version`
- **Git** (optional, wenn du das Archiv herunterlädst)
- Windows, macOS oder Linux

## 2. Programm holen

```bash
git clone https://github.com/sschknn/autonom-automatum.git
cd autonom-automatum
```

## 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

**Unter Linux zusätzlich:**

```bash
sudo apt install python3-tk
```

Ohne `python3-tk` startet die grafische Oberfläche nicht.

## 4. Starten

```bash
python trading_gui.py
```

Die Anwendung startet **sofort** im Beobachtungsmodus. Es werden keine
Keys benötigt, es wird nichts geordert.

## 5. Optional: Bybit-Keys einrichten

Nur nötig, wenn du dein echtes Konto abfragen oder Order-Dry-Runs gegen
echte Handelsregeln prüfen willst.

### 5.1 Konto bei einer MiCA-lizenzierten Börse

> **Binance ist seit 01.07.2026 für EU-Bürger gesperrt** (keine MiCA-Lizenz).
> Nutze **Bybit EU**, Kraken, Coinbase, OKX oder Crypto.com.
> Diese Anwendung ist für `api.bybit.eu` entwickelt.

### 5.2 API-Key anlegen

Auf `bybit.eu` → **API Management** → **Create New Key**

| Schritt | Einstellung | Begründung |
|---|---|---|
| Typ | System-generated | HMAC, passt zum Programm |
| Name | z. B. `autonom-automatum` | Wiedererkennbar |
| Permissions | Read-Write | Orders müssen möglich sein |
| IP-Restriktion | deine öffentliche IP | Schlüssel nur von deinem Rechner |
| **Spot → Trade** | **haken** | die einzige benötigte Berechtigung |
| Account Transfer | **nicht haken** | sonst könnte ein Schlüssel-Leak Geld abziehen |
| Subaccount Transfer | **nicht haken** | wird nicht gebraucht |
| Derivatives | **nicht haken** | für EU nicht lizenziert |
| Withdraw | **nicht haken** | niemals |

> **Sicherheitshinweis:** Das Secret wird **genau einmal** angezeigt.
> Sofort sichern. Trage es **nicht** in offene Chat-Fenster oder Issues ein.

### 5.3 Key eintragen

In der Anwendung oben rechts auf **API-KEYS** klicken und beide Felder
ausfüllen. Die Daten landen in `wallet/bybit_keys.json`, das in `.gitignore`
steht und **niemals** mit committed wird.

Der Knopf **SPEICHERN + TESTEN** prüft sofort, ob der Schlüssel gültig ist.

## 6. Optional: Assistent einrichten

Der Sprachassistent nutzt OpenRouter.

1. Konto auf `openrouter.ai` anlegen, API-Key erzeugen
2. In `wallet/openrouter_key.json` eintragen:

```json
{
  "provider": "openrouter",
  "api_key": "sk-or-v1-DEIN_KEY",
  "status": "ACTIVE",
  "base_url": "https://openrouter.ai/api/v1"
}
```

3. Anwendung neu starten

## 7. Häufige Probleme

**„Keine Marktdaten"**
Bybit EU unter `/v5/market/klines` (mit s) antwortet mit HTTP 404. Das Programm
nutzt korrekt `/v5/market/kline` (ohne s). Bei Fremdfehlern: Internetverbindung prüfen.

**„retCode 10002" (Zeitstempel)**
Deine Systemuhr weicht von der Serverzeit ab. Das Programm misst den Versatz
selbst und korrigiert die Signatur. Sollte das dauerhaft auftreten: Windows-Zeit
synchronisieren.

**„Qubitcoin qhash ... KeyError"**
Bybit EU liefert `basePrecision`, nicht `qtyStep`. Das Programm berücksichtigt
beides seit v0.1.

**Assistent antwortet nicht**
Der kostenlose Router von OpenRouter ist gelegentlich überlastet. Später nochmal
fragen. Der Block „Aus den Live-Daten berechnet" erscheint unabhängig davon.

**Keine Grafik / `TclError`**
`tkinter` fehlt: `sudo apt install python3-tk`

---

*Haftungsausschluss: Diese Software stellt keine Finanzberatung dar. Sie
simuliert und analysiert lediglich. Der Nutzer ist allein verantwortlich für
alle Handelsentscheidungen und trägt das volle finanzielle Risiko.*
