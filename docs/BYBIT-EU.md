# Bybit EU (MiCA) — API-Fallen

Erfahrungen aus der Entwicklung von `autonom-automatum`, Stand Oktober 2026.

Diese Datei sammelt alles, was einen tagelang blockiert, weil die offizielle
Dokumentation die EU-Entity nicht abdeckt. **Alle Angaben wurden gegen die
live API verifiziert**, nicht aus der Dokumentation abgeleitet.

---

## 1. Es gibt zwei verschiedene „Bybit"

Das ist die Grundursache fast aller Probleme.

| | Global | EU |
|---|---|---|
| Domain | `api.bybit.com` | `api.bybit.eu` |
| Betreiber | Bybit Ltd. | Bybit EU GmbH (FMA Österreich) |
| Rechtsgrundlage | außerhalb EU | MiCA-Lizenz seit 28.05.2025 |
| USDT-Paare | ja | **nein** |
| Futures/Derivate | ja | **nein** (nicht lizenziert) |

Ein Konto auf `bybit.com` und ein Konto auf `bybit.eu` sind **verschiedene
Konten mit getrennten Wallets**. Guthaben wandert nicht automatisch.

### Warum das wichtig ist

Binance hat seine MiCA-Antrag in Griechenland am 24.06.2026 zurückgezogen und
ist seit dem 01.07.2026 **ohne Lizenz für EU-Bürger**. Bestandsguthaben sind
nur noch auszahlbar. Wer seinen Key auf `api.binance.com` zeigt, hat in der EU
kein legales Produkt mehr.

MICA-lizenzierte Alternativen: **Bybit EU, Kraken, Coinbase, OKX, Crypto.com,
Bitpanda, Bitvavo, Gate, Bitstamp.**

---

## 2. Endpunkte, die es auf EU nicht gibt

Die globale API-Dokumentation beschreibt Endpunkte, die auf `api.bybit.eu`
mit **HTTP 404 und leerem Body** antworten — nicht mit einer Fehlermeldung.
Das macht die Fehlersuche unnötig langweilig.

| Endpunkt | Global | EU |
|---|---|---|
| `/v5/market/klines` | ✅ | ❌ **404** |
| `/v5/market/kline` | ✅ | ✅ funktioniert |
| `/v5/market/trading-history` | ✅ | ❌ 404 |
| `/v5/market/recent-trade` | ✅ | ✅ funktioniert |
| `/v5/account/constraints` | ✅ | ❌ liefert kein JSON |
| `/v5/user/query-api` | ✅ | ✅ funktioniert |

### `/v5/market/kline` — der häufigste 404

**Singular, nicht Plural.** Der Endpunkt liefert Kerzendaten als Liste, neueste
Kerze zuerst:

```
["startMs", "open", "high", "low", "close", "volume", "turnover"]
```

Also **umkehren**, bevor du rechnest — die Zeitreihe muss aufsteigend sortiert
werden, sonst drehen sich EMA und ATR gegen den Trend.

---

## 3. Keine USDT-Paare — nur USDC und Fiat

Das ist die Überraschung, die den meisten den ersten Trade vermißt.

`ETHUSDT` wird im Ticker zwar angezeigt, ist aber ein **Phantom-Markt**:
0,25 Dollar Notional, 9,3 ETH Volumen pro Tag, Spread 0,024 %. Eine Order
wird nie ausgeführt.

Handelbare ETH-Paare auf Bybit EU:

| Paar | Volumen 24 h | Spread | Bemerkung |
|---|---|---|---|
| **ETHUSDC** | ~669 ETH | 0,0004 % | **beste Wahl** |
| ETHEUR | ~44 ETH | 0,003 % | direkter EUR-Kurs |
| ETHPLN | — | — | PLN-Paar |
| BTCUSDC | ~96 BTC | 0,000 % | |
| BTCEUR | ~5 BTC | 0,027 % | dünn |

`minOrderAmt` für ETHUSDC liegt bei **5 USDC**. Kleinere Orders werden
abgelehnt, auch wenn `minOrderQty` passt.

---

## 4. `basePrecision` statt `qtyStep`

`lotSizeFilter` liefert auf EU **kein** `qtyStep`. Wer danach greift, bekommt
einen `KeyError` — oder schlimmer, rechnet still mit unrunden Mengen.

```python
# falsch (global gedacht)
step = lot.get("qtyStep")

# richtig
step = lot.get("qtyStep") or lot.get("basePrecision") or "0"
```

Vollständige Struktur von `lotSizeFilter` auf EU:

```json
{
  "basePrecision": "0.0001",
  "quotePrecision": "0.000001",
  "minOrderQty": "0.0001",
  "maxOrderQty": "3605.879219",
  "minOrderAmt": "5",
  "maxOrderAmt": "1200000"
}
```

---

## 5. `instruments-info` ignoriert den Symbolfilter

Mit `symbol=ETHUSDT` liefert EU `retCode: 0` und **`result.list: []`** — also
Erfolg mit leerem Ergebnis. Kein Fehler, kein Hinweis.

```python
# Aufrufen und clientseitig filtern
d = self._get("/v5/market/instruments-info", {"category": "spot"})  # alle 128
instrumente = {i["symbol"]: i for i in d["result"]["list"]}
```

Ein leeres Ergebnis bei gesetztem Filter ist also **kein** Fehlerfall.

---

## 6. Nur `accountType=UNIFIED`

```json
{"retCode": 10001, "retMsg": "accountType only support UNIFIED."}
```

`SPOT` und `FUND` werden abgelehnt. Das hat eine praktische Folge, die leicht
übersehen wird:

> **Das Funding-Konto ist über die API nicht sichtbar.**
> Guthaben, das im Funding-Account liegt, erscheint in keiner
> `wallet-balance`-Antwort.

Wer im Frontend „Assets = 6,27 EUR" sieht und über die API `0` bekommt, hat
nicht zwingend einen Fehler — das Geld liegt in einem anderen Walletbereich
und muss im Frontend erst per **Transfer → Unified Trading Account** verschoben
werden.

Auch `totalAvailableBalance` ist unzuverlässig; verlässlich sind die Werte
pro Coin im `coin`-Array.

---

## 7. Zeitversatz killt jeden privaten Aufruf

Wenn deine Systemuhr auch nur 15 Sekunden danebenliegt, ist **jede**
signierte Anfrage tot:

```
retCode 10002 — req_timestamp[1791866135074],
               server_timestamp[1791866150198],
               recv_window[5000]
```

Der Versatz muss korrigiert werden, bevor signiert wird:

```python
def sync_time(self):
    server_ms = int(self._get("/v5/market/time")["result"]["timeSecond"]) * 1000
    self.time_offset_ms = server_ms - int(time.time() * 1000)

# in _sign():
ts = str(int(time.time() * 1000) + self.time_offset_ms)
recv = "5000"     # Bybit akzeptiert maximal 5000, nicht mehr
```

`recv_window` auf 30.000 zu setzen ist verlockend und falsch — die API
ignoriert oder verweigert Werte über 5000.

---

## 8. Rechte prüfen: `/v5/user/query-api`

Damit siehst du, was dein Key tatsächlich kann — und was Bybit von selbst
aktiviert hat:

```json
{
  "readOnly": 0,
  "ips": ["93.206.245.73"],
  "permissions": {
    "Spot": ["SpotTrade"],
    "Derivatives": ["DerivativesTrade"],
    "Wallet": []
  }
}
```

**`DerivativesTrade` war aktiv, obwohl im Formular nie angehakt.** Bybit
setzt es bei Read-Write offenbar standardmäßig. Für einen reinen Spot-Bot
unerwünscht und im Dashboard abschaltbar.

`Wallet: []` heißt: Der Key kann **keine** Überweisungen auslösen. Das ist die
wichtigste Zeile der ganzen Datei — sie ist der Grund, warum ein Bybit-Key
mit Spot-Recht strukturell kein Guthaben abziehen kann.

---

## 9. IP-Whitelist und ihre Nebenwirkung

Mit Whitelist funktioniert der Key **nur** von der eingetragenen IP. Fällt
bei einem DSL-Anschluss die öffentliche Adresse, ist der Key tot — Bybit
erlaubt nachträgliches Ändern, aber erst nach erneuter Verifizierung.

Ohne Whitelist zeigt Bybit ausdrücklich: *„unable to select coin withdrawal
option"*. Das ist kein Zufall, sondern Absicht.

---

## 10. Gebühren und der Mindestbetrag, der alles entscheidet

Spot-Taker: **0,1 % je Seite**, ein Roundtrip also 0,2 % — vor Spread.

Bei 6,79 USDC Kapital:

```
Gebühren Roundtrip : 0,0136 USDC = 0,20 %
Kursbewegung für 5 %: 5,2 %
```

Ab `minOrderAmt = 5 USDC` ist die Positionsgröße zusätzlich gedeckelt. Wer
weniger als 5 USDC Guthaben im Handelskonto hat, **kann technisch nicht
handeln**, egal wie gut das Signal ist.

---

## Checkliste vor dem ersten Order

- [ ] `api.bybit.eu`, nicht `.com`
- [ ] Paar enthält USDC oder Fiat, kein USDT
- [ ] `/v5/market/kline` (ohne s)
- [ ] `time_offset_ms` gemessen und in der Signatur verwendet
- [ ] `recv_window` = 5000
- [ ] `basePrecision` statt `qtyStep`
- [ ] `accountType=UNIFIED`
- [ ] Guthaben im **Unified Trading Account**, nicht nur im Funding
- [ ] Notional ≥ `minOrderAmt` (5 USDC)
- [ ] `/v5/user/query-api` zeigt nur `SpotTrade`
- [ ] `dry_run=True` beim ersten Test
