#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backtest-Sweep fuer die Paper-Strategie (Kapital=50.000).

Ziel: Finden wir Parameter, die ueber historische Bybit-ETHUSDC-Kerzen
echt Geld verdienen - statt nur Gebuehren zu verbrennen.

Methode (bewusst gegen Ueberanpassung):
  1. Split der Historie in IN-SAMPLE (Tuning) und OUT-OF-SAMPLE (Test).
  2. Sweep ueber Parameterkombinationen, gerankt NUR nach In-Sample.
  3. Der Gewinner wird anschliessend auf Out-of-Sample geprueft.
     Nur wenn er auch dort positiv ist, ist es echt und nicht Rauschen.

Realitaetsannahmen wie im Live-Paper-Trader:
  - Signal aus Kerze N, Fill zum Open von Kerze N+1 (kein Look-Ahead)
  - Kauf +0,05% Slippage, Verkauf -0,05%
  - Gebuehren 0,1% pro Seite
  - Stop-Loss wird VOR Take-Profit geprueft (schlechtester Fall zuerst)

Aufruf:  python sweep.py [Tage]     (Standard 120)
"""
import sys
import os
import time
import itertools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from core import indicators

API = "https://api.bybit.eu"
SYMBOL = "ETHUSDC"

TAKER_FEE = 0.001
SLIPPAGE = 0.0005
INTERVAL_MS = {"15": 15 * 60 * 1000, "60": 60 * 60 * 1000}


def fetch_klines(interval, days):
    step = INTERVAL_MS[interval]
    end = int(time.time() * 1000)
    start = end - days * 24 * 60 * 60 * 1000
    out, cursor = [], end
    while cursor > start:
        r = requests.get(f"{API}/v5/market/kline", timeout=30, params={
            "category": "spot", "symbol": SYMBOL, "interval": interval,
            "limit": 1000, "end": cursor})
        r.raise_for_status()
        rows = r.json().get("result", {}).get("list", [])
        if not rows:
            break
        oldest = min(int(x[0]) for x in rows)
        out.extend(rows)
        if oldest <= start:
            break
        cursor = oldest - 1
        time.sleep(0.12)
    out.sort(key=lambda x: int(x[0]))
    seen, uniq = set(), []
    for x in out:
        if x[0] not in seen:
            seen.add(x[0])
            uniq.append(x)
    return [dict(start=int(x[0]), open=float(x[1]), high=float(x[2]),
                 low=float(x[3]), close=float(x[4])) for x in uniq]


# ---------------------------------------------------------------- Indikatoren
def ema(v, p):
    if not v:
        return None
    k = 2 / (p + 1)
    e = v[0]
    for x in v[1:]:
        e = x * k + e * (1 - k)
    return e


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    g, l = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        g.append(max(d, 0.0))
        l.append(max(-d, 0.0))
    ag, al = sum(g[:period]) / period, sum(l[:period]) / period
    for i in range(period, len(g)):
        ag = (ag * (period - 1) + g[i]) / period
        al = (al * (period - 1) + l[i]) / period
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return 100 - 100 / (1 + ag / al)


def atr(bars, period=14):
    if len(bars) < period + 1:
        return None
    trs = [max(b["high"] - b["low"], abs(b["high"] - bars[i-1]["close"]),
               abs(b["low"] - bars[i-1]["close"])) for i, b in
          enumerate(bars) if i > 0]
    a = sum(trs[:period]) / period
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / period
    return a


def feats(bars, i):
    """Merkmale aus dem 15m-Fenster bis Kerze i (inklusive)."""
    w = bars[i - 29:i + 1] if i >= 29 else bars[:i + 1]
    closes = [b["close"] for b in w]
    if len(closes) < 30:
        return None
    return {
        "rsi": rsi(closes),
        "e9": ema(closes, 9),
        "e21": ema(closes, 21),
        "e50": ema(closes, 50),
        "atr": atr(w),
        "close": closes[-1],
        "prev_closes": closes,
        "highs": [b["high"] for b in w],
    }


def h1h(bars60, j):
    """Merkmale aus dem 60m-Fenster bis Kerze j."""
    w = bars60[j - 29:j + 1] if j >= 29 else bars60[:j + 1]
    closes = [b["close"] for b in w]
    if len(closes) < 30:
        return None
    return {"rsi": rsi(closes), "e9": ema(closes, 9),
            "e21": ema(closes, 21), "close": closes[-1]}


# ---------------------------------------------------------------- Entry-Logik
def entry_signal(f15, f60, p):
    """Long-Signal nach Variante p. Liefert True/False."""
    mode = p["mode"]

    if mode == "trend_pullback":
        # Nur im Aufwaertstrend, Einstieg auf Rücksetzer:
        # 1h- und 15m-EMA muessen im Aufwaertstrend sein, RSI nicht zu hoch,
        # und der Kurs muss unter dem 15m-EMA9 liegen (Rücksetzer).
        if not f60 or f60["e9"] <= f60["e21"]:
            return False
        if f15["e9"] <= f15["e21"]:
            return False
        if f15["rsi"] > p["rsi_max"]:
            return False
        if f15["close"] >= f15["e9"]:
            return False
        return True

    if mode == "trend_breakout":
        # Trendfolge: Aufwaertstrend + Ausbruch ueber das Hoch der letzten N Kerzen.
        if not f60 or f60["e9"] <= f60["e21"]:
            return False
        if f15["e9"] <= f15["e21"]:
            return False
        look = p["bb"]
        if f15["close"] <= max(f15["highs"][-look - 1:-1]):
            return False
        return True

    if mode == "oversold":
        # Nur stark überverkauft, mit langfristigem Aufwärtstrend als Filter.
        if not f60 or f60["e9"] <= f60["e21"]:
            return False
        if f15["rsi"] > p["rsi_enter"]:
            return False
        return True

    if mode == "hybrid":
        # Rücksetzer im Trend ODER Ausbruch - aber nie beides gleichzeitig.
        up = f60 and f60["e9"] > f60["e21"] and f15["e9"] > f15["e21"]
        if not up:
            return False
        pullback = f15["close"] < f15["e9"] and f15["rsi"] <= p["rsi_max"]
        look = p["bb"]
        breakout = f15["close"] > max(f15["highs"][-look - 1:-1])
        return pullback or breakout

    return False


# ---------------------------------------------------------------- Backtest
def run(start_quote, bars15, bars60, p, lo=None, hi=None):
    n = len(bars15)
    if lo is None:
        lo = 0
    if hi is None:
        hi = n - 1
    idx60 = {b["start"]: i for i, b in enumerate(bars60)}

    quote = start_quote
    pos = 0.0
    entry = peak = 0.0
    trades, fees_tot = [], 0.0
    peak_eq, max_dd = start_quote, 0.0

    for i in range(max(30, lo), min(hi, n - 1)):
        cur, nxt = bars15[i], bars15[i + 1]

        if pos > 0:
            stop = entry * (1 - p["sl"] / 100)
            take = entry * (1 + p["tp"] / 100)
            trail = peak * (1 - p["trail"] / 100) if p["trail"] else 0.0

            ex, kind = None, None
            if cur["low"] <= stop:
                ex, kind = stop, "SL"
            elif trail and cur["low"] <= trail:
                ex, kind = trail, "TRAIL"
            elif cur["high"] >= take:
                ex, kind = take, "TP"

            if ex is not None:
                fill = ex * (1 - SLIPPAGE)
                fee = pos * fill * TAKER_FEE
                quote += pos * fill - fee
                fees_tot += fee
                trades.append({"kind": kind, "entry": entry, "exit": fill,
                               "pnl": (fill - entry) * pos - fee,
                               "pct": (fill / entry - 1) * 100})
                pos = entry = peak = 0.0
            else:
                peak = max(peak, cur["high"])

            eq = quote + pos * cur["close"]
            peak_eq = max(peak_eq, eq)
            max_dd = min(max_dd, (eq - peak_eq) / peak_eq * 100)

        if pos == 0:
            f15 = feats(bars15, i)
            j = idx60.get(cur["start"])
            if f15 and j is not None and j >= 29:
                f60 = h1h(bars60, j)
                if f60 and entry_signal(f15, f60, p):
                    fill = nxt["open"] * (1 + SLIPPAGE)
                    budget = quote * p["frac"]
                    if budget * p["frac"] >= 5.0:
                        fee = budget * TAKER_FEE
                        pos = (budget - fee) / fill
                        entry = fill
                        peak = nxt["high"]
                        quote -= budget
                        fees_tot += fee

    equity = quote + pos * bars15[min(hi, n - 1)]["close"]
    return {"start": start_quote, "equity": equity,
            "ret": (equity / start_quote - 1) * 100,
            "trades": trades, "fees": fees_tot, "max_dd": max_dd}


def score(res):
    """Guete: Rendite, aber mit Strafe fuer uebermaessig viele Trades.
    Gebuehren (2x0,1% je Roundtrip) zehren an der Rendite - wer oft
    handelt, muss pro Trade deutlich mehr erwirtschaften."""
    n = len(res["trades"])
    if n == 0:
        return -999.0
    penalty = max(0, n - 60) * 0.02          # >60 Trades im Fenster = Duellution
    return res["ret"] - penalty


def show(label, res):
    t = res["trades"]
    n = len(t)
    w = [x for x in t if x["pnl"] > 0]
    gw = sum(x["pnl"] for x in w)
    gl = abs(sum(x["pnl"] for x in t if x["pnl"] <= 0))
    wr = len(w) / n * 100 if n else 0.0
    pf = gw / gl if gl else (float("inf") if gw > 0 else 0.0)
    print(f"  {label:<34} Ret {res['ret']:+7.2f}%  Trades {n:>4d}"
          f"  Treffer {wr:5.1f}%  PF {pf:5.2f}  DD {res['max_dd']:6.2f}%"
          f"  Gebuehren {res['fees']:>9,.0f}")


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    print(f"Lade {days} Tage {SYMBOL}-Historie ...")
    b15 = fetch_klines("15", days)
    b60 = fetch_klines("60", days)
    print(f"  {len(b15)} 15m-Kerzen, {len(b60)} 60m-Kerzen")
    if len(b15) < 500:
        print("Zu wenig Daten.")
        return
    t0 = time.strftime("%Y-%m-%d", time.localtime(b15[0]["start"] / 1000))
    t1 = time.strftime("%Y-%m-%d", time.localtime(b15[-1]["start"] / 1000))
    print(f"  Zeitraum {t0} bis {t1}\n")

    # 60% In-Sample (Tuning), 40% Out-of-Sample (Validierung)
    split = int(len(b15) * 0.6)
    print(f"IN-SAMPLE  : Kerzen 30..{split}")
    print(f"OUT-OF-SAMPLE: Kerzen {split}..{len(b15)-1}\n")

    grid = []
    for mode in ("trend_pullback", "trend_breakout", "oversold", "hybrid"):
        for rsi_max in (35, 45, 55):
            for bb in (10, 20):
                for sl, tp in ((1.0, 2.5), (1.2, 2.4), (1.5, 2.0)):
                    for trail in (0.0, 1.5, 2.0):
                        for frac in (1.0, 0.5):
                            grid.append(dict(mode=mode, rsi_max=rsi_max,
                                             rsi_enter=rsi_max, bb=bb,
                                             sl=sl, tp=tp, trail=trail,
                                             frac=frac))
    print(f"Sweeping {len(grid)} Kombinationen auf In-Sample ...")

    scored = []
    for p in grid:
        r = run(50_000.0, b15, b60, p, lo=30, hi=split)
        if r["trades"]:
            scored.append((score(r), p, r))
    scored.sort(key=lambda x: x[0], reverse=True)

    print("\n=== Top 10 auf IN-SAMPLE (Tuning) ===")
    for s, p, r in scored[:10]:
        show(f"{p['mode']} rsi{p['rsi_max']} bb{p['bb']} "
             f"SL{p['sl']} TP{p['tp']} tr{p['trail']} f{int(p['frac']*100)}", r)

    if not scored:
        print("Keine Kombination erzeugte Trades.")
        return

    best = scored[0][1]
    print("\n=== Beste Parameter, geprueft auf OUT-OF-SAMPLE ===")
    print(f"  {best}")
    oos_full = run(50_000.0, b15, b60, best, lo=split, hi=len(b15) - 1)
    show("Out-of-Sample (validiert)", oos_full)
    ins_full = run(50_000.0, b15, b60, best, lo=30, hi=split)
    show("In-Sample (Tuning)", ins_full)

    print("\n=== Kontrolle: weniger, selektivere Signale ===")
    for p in grid:
        if p["mode"] != best["mode"]:
            continue
        if p["sl"] != best["sl"] or p["tp"] != best["tp"]:
            continue
        if p["trail"] != best["trail"] or p["frac"] != best["frac"]:
            continue
        if p["rsi_max"] != best["rsi_max"] and p["bb"] != best["bb"]:
            continue
        r = run(50_000.0, b15, b60, p, lo=split, hi=len(b15) - 1)
        if r["trades"]:
            show(f"  OOS rsi{p['rsi_max']} bb{p['bb']}", r)

    print("\n=== Fazit ===")
    if oos_full["ret"] > 0 and len(oos_full["trades"]) >= 3:
        print(f"  Out-of-Sample positiv: {oos_full['ret']:+.2f} %")
        print("  Das waere ein erstes Indiz fuer echten Edge. Trotzdem:")
        print("  ein einziger Zeitraum ist kein Beweis - laenger testen,")
        print("  Laufzeit beobachten, und vor allem live mit kleinen Betraegen.")
    else:
        print(f"  Out-of-Sample: {oos_full['ret']:+.2f} % bei "
              f"{len(oos_full['trades'])} Trades -> kein belastbarer Edge.")
        print("  Fazit: Mit dieser Indikator-Logik (RSI/EMA/ATR auf 15m+1h)")
        print("  laesst sich auf ETHUSDC kein verlaesslicher Vorteil heben.")
        print("  Vermutlich ist der Markt in diesem Zeitraum zu effizient fuer")
        print("  eine so einfache Regel - Gebuehren + Spread zehren alles auf.")


if __name__ == "__main__":
    main()