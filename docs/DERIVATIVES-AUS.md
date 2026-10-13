# DerivativesTrade widerrufen (Bybit EU)

**Zeit:** 2 Minuten. Benötigt: deinen Bybit-EU-Login und 2FA-Code.

---

## Schritt-für-Schritt

### 1. Dashboard öffnen

Browser öffnen und eingeben (oder klicken):

```
https://www.bybit.eu/app/user/api-management
```

---

### 2. Auf "API Management" klicken

Oben im Menü: **User Center** → **API Management**.

---

### 3. Den Key "autonom-automatum" finden

In der Liste den Eintrag suchen, der **"autonom-automatum"** als Note hat
(das hast du bei der Anlage angegeben).

Daneben auf **Edit** klicken (Bleistift-Symbol).

---

### 4. Rechte ändern

Im Formular siehst du eine Tabelle mit Berechtigungen. Dort steht:

| Bereich | Aktuelles Häkchen | Muss werden |
|---|---|---|
| **Spot → Trade** | ✅ | **✅ lässt an** |
| **Derivatives → Trade** | ✅ | **❌ entfernen** |
| Account Transfer | ⬜ | ⬜ lässt aus |

**Nur bei `Derivatives` das Häkchen entfernen.** Spot lässt du drin.

---

### 5. Speichern

Unten auf **Save** klicken.

---

### 6. Bestätigen

Von Bybit:
1. Bestätigungs-E-Mail (Link klicken) **ODER**
2. 2FA-Code (Google Authenticator / SMS) eingeben

---

### 7. Prüfen (optional)

Nochmal auf den Key klicken → **View API Key**.

Dort sollte jetzt stehen:

```
Derivatives: []      ← leer, nichts angehakt
Spot: [SpotTrade]    ← bleibt aktiv
Wallet: []           ← bleibt leer (kein Auszahlen)
```

---

## WICHTIG

- Nach dem Speichern wird der **alte API-Key ungültig** und du brauchst
  einen **neuen Secret** — den musst du in `wallet/bybit_keys.json`
  eintragen.
- `SpotTrade` bleibt erhalten, der Bot funktioniert weiter.
- `Wallet: []` ist schon jetzt so eingestellt — der Key kann
  **auch ohne Derivatives keinen Cent von Bybit abheben**.

---

## Hilfe

Falls die Seite anders aussieht: Im Menü nach **"API-Management"**,
**"API-Keys"** oder **"API-Verwaltung"** suchen.