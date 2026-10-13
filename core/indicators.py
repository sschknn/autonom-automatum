"""Technische Indikatoren auf echten Kerzendaten (Bybit EU).

Kein Zufall, keine Heuristik: RSI, EMA und ATR werden Standardformeln
auf realen Close-/High-/Low-Reihen berechnet.
"""
from core import logger

_log = logger.DualLogger()


def ema(values, period):
    if not values:
        return None
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes, period=14):
    """Wilder-RSI."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag, al = sum(gains[:period]) / period, sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return 100 - (100 / (1 + rs))


def atr(klines, period=14):
    """Average True Range - misst die echte Volatilitaet."""
    if len(klines) < period + 1:
        return None
    trs = []
    for i in range(1, len(klines)):
        h, l, pc = klines[i]["high"], klines[i]["low"], klines[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:period]) / period
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / period
    return a


def analyze(klines):
    """Wertet Kerzendaten aus und liefert ein Signal mit Begruendung."""
    if not klines or len(klines) < 20:
        return {"action": "HOLD", "confidence": 0.0,
                "reason": f"Zu wenig Kerzendaten ({len(klines) if klines else 0}/20)."}

    # Bybit liefert neueste zuerst -> umdrehen fuer Zeitreihe
    k = sorted(klines, key=lambda x: x["start"])
    closes = [c["close"] for c in k]
    last = closes[-1]
    r = rsi(closes)
    e9, e21 = ema(closes, 9), ema(closes, 21)
    a = atr(k)

    reasons, score = [], 0.0

    if r is not None:
        if r < 30:
            score += 0.35; reasons.append(f"RSI {r:.1f} ueberverkauft")
        elif r > 70:
            score -= 0.35; reasons.append(f"RSI {r:.1f} ueberkauft")
        else:
            reasons.append(f"RSI {r:.1f} neutral")
    else:
        reasons.append("RSI nicht berechenbar")

    if e9 and e21:
        if e9 > e21:
            score += 0.25; reasons.append(f"EMA9 {e9:.1f} > EMA21 {e21:.1f} (Aufwaertstrend)")
        else:
            score -= 0.25; reasons.append(f"EMA9 {e9:.1f} < EMA21 {e21:.1f} (Abwaertstrend)")

    if a and last:
        vol_pct = a / last * 100
        reasons.append(f"ATR {a:.2f} ({vol_pct:.2f}% Volatilitaet)")
        if vol_pct > 1.5:
            reasons.append("erhoehte Volatilitaet - Positionsgroesse reduzieren")

    action = "BUY" if score > 0.2 else ("SELL" if score < -0.2 else "HOLD")
    confidence = min(0.95, abs(score)) if action != "HOLD" else 0.4
    return {
        "action": action,
        "confidence": round(confidence, 2),
        "score": round(score, 2),
        "rsi": round(r, 1) if r else None,
        "ema9": round(e9, 2) if e9 else None,
        "ema21": round(e21, 2) if e21 else None,
        "atr": round(a, 4) if a else None,
        "price": last,
        "candles": len(k),
        "reason": " | ".join(reasons),
    }
