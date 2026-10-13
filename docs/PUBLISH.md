# Veröffentlichungsfertige Texte

Drei Formate aus `BYBIT-EU.md`. Alle Angaben sind gegen die Live-API verifiziert.
Kein Marketing-Versprechen — der Inhalt ist die Dokumentation selbst.

---

## 1. X / Twitter (Thread, 5 Posts)

**Post 1**
> Ich habe 10 API-Fallen bei Bybit EU (MiCA) gefunden, die einen tagelang
> blockieren. Keine davon steht in der offiziellen Doku. Ein Thread. 🧵

**Post 2**
> Falle 1: Es gibt zwei verschiedene „Bybit".
>
> `api.bybit.com` (Bybit Ltd.) und `api.bybit.eu` (Bybit EU GmbH, FMA Österreich).
> Getrennte Konten, getrennte Wallets, Guthaben wandert nicht automatisch.
>
> Und: EU hat **keine USDT-Paare**.

**Post 3**
> Falle 2: `/v5/market/klines` → **404 mit leerem Body.**
> Es heißt `/v5/market/kline`, Singular.
>
> Der 404 ohne Fehlermeldung ist das Schlimmste daran — du denkst an einen
> Rate-Limit oder einen falschen Key. Es ist einfach eine andere Entity.

**Post 4**
> Falle 3: `lotSizeFilter` liefert auf EU **kein `qtyStep`**. Es gibt `basePrecision`.
>
> ```python
> step = lot.get("qtyStep") or lot.get("basePrecision") or "0"
> ```
>
> Und `minOrderAmt` liegt bei **5 USDC** — nicht `minOrderQty`. Kleinere Orders
> werden abgelehnt, auch wenn die Menge passt.

**Post 5**
> Falle 4: Deine Systemuhr 15 Sekunden daneben, und **jede** signierte Anfrage
> ist tot. `retCode 10002`.
>
> Lösung: Versatz gegen `/v5/market/time` messen und **in die Signatur einrechnen**.
> Und `recv_window` max. 5000 — 30000 wird ignoriert.
>
> 5 weitere Fallen + Checkliste: github.com/sschknn/autonom-automatum

---

## 2. Hacker News / Reddit r/algotrading / dev.to

**Titel:** Bybit EU (MiCA) API: 10 verified pitfalls that the official docs don't cover

**Text:**

I spent a while getting a spot bot working against Bybit EU. Here are ten things
that block you, all verified against the live API — not inferred from docs.

**1. There are two different "Bybit".**
`api.bybit.com` (Bybit Ltd.) vs `api.bybit.eu` (Bybit EU GmbH, FMA Austria,
MiCA licence). Different accounts, separate wallets, no automatic transfer.
Context: Binance withdrew its MiCA application on 24.06.2026 and has been
unlicensed for EU users since 01.07.2026. `api.binance.com` is no longer a
legal target here.

**2. Endpoints that 404 on EU.**
`/v5/market/klines` (plural) returns **HTTP 404 with an empty body**. The
working one is `/v5/market/kline`, singular. Same for `trading-history`
(dead) vs `recent-trade` (works). A 404 with no message sends you hunting for
rate limits and bad keys. It's just a different entity.

**3. No USDT pairs.**
`ETHUSDT` appears in the ticker but is a phantom market: 0.25 USD notional,
9.3 ETH daily volume. Orders never fill. Use `ETHUSDC` (~669 ETH/day,
0.0004 % spread).

**4. `basePrecision`, not `qtyStep`.**
`lotSizeFilter` on EU returns no `qtyStep`. Also `minOrderAmt` is 5 USDC —
a minimum notional, separate from `minOrderQty`.

**5. `instruments-info` ignores the symbol filter.**
Query `symbol=ETHUSDT` and you get `retCode: 0` with `result.list: []`.
Success with an empty result. Not an error condition — filter client-side.

**6. Only `accountType=UNIFIED`.**
`SPOT` and `FUND` are rejected. The practical consequence, which is easy to
miss: **the Funding account is invisible via API.** If the UI says 6.27 EUR and
the API says 0, the money is in another wallet section — transfer it to
Unified Trading in the UI. `totalAvailableBalance` is unreliable; the per-coin
values are correct.

**7. Clock offset kills every signed call.**
15 seconds of drift is enough for `retCode 10002`. Measure the offset against
`/v5/market/time` and apply it inside the signature. And `recv_window` maxes
at 5000 — setting 30000 looks reasonable and fails.

**8. Check what Bybit actually granted: `/v5/user/query-api`.**
My key came back with `Derivatives: ["DerivativesTrade"]` enabled, though I
never ticked it in the form. Default-on for read-write keys.

The line that matters most:
```
"Wallet": []
```
That's why a Spot-only Bybit key structurally cannot withdraw funds. Check it
before you write the code that moves money.

**9. IP whitelist has a real failure mode.**
With a whitelist the key only works from that IP. If your DSL address changes,
the key is dead — Bybit allows changes but re-verifies first. Without a
whitelist, Bybit states outright: *"unable to select coin withdrawal option."*
Not an accident.

**10. Fees and the minimum that decides everything.**
0.1 % taker per side, so 0.2 % per roundtrip before spread. At 6.79 USDC
capital that's 0.0136 USDC per cycle — you'd need a 5.2 % move for a 5 % profit.
And below the 5 USDC `minOrderAmt` you cannot trade at all, signal quality
irrelevant.

Full document with code snippets and a pre-first-order checklist:
`docs/BYBIT-EU.md` in github.com/sschknn/autonom-automatum

*Disclosure: I built the repo. It has no proven edge — 0 trades so far. This
writeup is the part of the project that has actual value, which is the
documentation.*

---

## 3. LinkedIn / Kurzfassung (deutsch)

> **Warum dein Bybit-Bot in der EU nicht läuft**
>
> Ich habe zwei Wochen gegen die Bybit-EU-API programmiert (MiCA, FMA Österreich)
> und zehn Fallen dokumentiert, die einen tagelang blockieren — keine davon steht
> in der offiziellen Doku.
>
> Die wichtigsten drei:
>
> **1.** `api.bybit.eu` ist eine andere Firma als `api.bybit.com`. Getrennte
> Konten, getrennte Wallets. Und: **keine USDT-Paare.** Wer `ETHUSDT` handelt,
> handelt ein Phantom-Markt mit 9 ETH Tagesvolumen.
>
> **2.** `/v5/market/klines` gibt **404 mit leerem Body.** Es heißt `kline`,
> Singular. Man sucht dann stundenlang nach Rate-Limits.
>
> **3.** Deine Systemuhr muss stimmen. **15 Sekunden** Versatz, und jede
> signierte Anfrage ist tot (`retCode 10002`). Muss in die Signatur eingerechnet
> werden.
>
> Dazu kommen `basePrecision` statt `qtyStep`, ein `minOrderAmt` von 5 USDC,
> und ein Funding-Konto, das über die API **unsichtbar** ist — wer im Frontend
> Guthaben sieht und über die API `0` bekommt, hat meistens keinen Bug.
>
> Seit dem 01.07.2026 ist Binance für EU-Bürger ohne Lizenz. Wer jetzt seinen
> Key auf `api.binance.com` zeigt, hat kein legales Produkt mehr.
>
> Vollständige Liste mit Code und Checkliste:
> `github.com/sschknn/autonom-automatum` → `docs/BYBIT-EU.md`
>
> *Transparenz: Der Bot selbst hat bisher 0 Trades und keinen nachgewiesenen
> Edge. Verkauft wird hier kein Gewinnversprechen, sondern eine Dokumentation.*

---

## Wo posten (Reihenfolge nach Aufwand)

| Kanal | Aufwand | Erwartete Resonanz |
|---|---|---|
| **Hacker News** (`Show HN: ...`) | hoch (Zeitfenster beobachten) | hoch, aber ungnädig bei Marketing |
| **r/algotrading** | niedrig | mittel — dort werden MiCA-Themen gern aufgenommen |
| **dev.to** | niedrig | mittel |
| **LinkedIn** | niedrig | gering, aber direkt |
| **X** | niedrig | gering, aber das Netzwerk-Teil entsteht fast gratis |

**Wichtig für HN:** Der Titel darf nicht nach Produkt klingen. „Show HN" funktioniert
bei Doku-Inhalten schlecht — dort funktioniert ein Technical-Post ohne Anmeldung
als Produkt besser. Also ohne „Show HN" posten, sondern als Erfahrungsbericht.