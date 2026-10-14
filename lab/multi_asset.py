#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-Asset-Search: Findet ein handelbares Setup ueber mehrere Coins.

Offene Frage aus dem 120-Tage-ETH-Test: Ist ETHUSDC das Problem, oder
ist die Logik generell zu schwach? Diese Datei testet dieselbe Strategie
auf mehreren Paaren - inklusive BTC (typischerweise niedrigere Volatilitaet
=> weniger Roundtrips => niedrigere Gebuehrenbelastung) und SOL/XRP (hochvolatil
=> groessere Bewegungen pro Trade).

Methodik (gegen Ueberanpassung):
  - Jedes Paar wird einzeln bewertet, kein pooling.
  - Split je Paar: 60% In-Sample (Tuning), 40% Out-of-Sample.
  - Nur Paare, die auf BEIDEN Teilen positiv sind, werden gemeldet.
  - Gebuehren sind realistisch (0,1%/Seite + Slippage) - genau das, was
    auf Bybit EU Spot anfaellt.

Aufruf:  python lab/multi_asset.py [Tage]
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

API = "https://api.bybit.eu"
PAIRS = ["ETHUSDC", "BTCUSDC", "SOLUSDC", "XRPUSDC", "DOGEUSDC", "ADAUSDC"]

TAKER_FEE = 0.001
SLIPPAGE = 0.0005
STEP = {"15": 15 * 60 * 1000, "60": 60 * 60 * 1000}


def fetch(symbol, interval, days):
    end = int(time.time() * 1000)
    start = end - days * 86400000
    out, cursor = [], end
    while cursor > start:
        r = requests.get(f"{API}/v5/market/kline", timeout=30, params={
            "category": "spot", "symbol": symbol, "interval": interval,
            "limit": 1000, "end": cursor})
        if r.status_code != 200:
            return []
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
    seen, u = set(), []
    for x in out:
        if x[0] not in seen:
            seen.add(x[0])
            u.append(x)
    return [dict(start=int(x[0]), open=float(x[1]), high=float(x[2]),
                 low=float(x[3]), close=float(x[4])) for x in u]


def ema(v, p):
    if not v:
        return None
    k = 2 / (p + 1)
    e = v[0]
    for x in v[1:]:
        e = x * k + e * (1 - k)
    return e


def rsi(c, period=14):
    if len(c) < period + 1:
        return None
    g = [max(c[i] - c[i-1], 0) for i in range(1, len(c))]
    l = [max(c[i-1] - c[i], 0) for i in range(1, len(c))]
    ag, al = sum(g[:period]) / period, sum(l[:period]) / period
    for i in range(period, len(g)):
        ag = (ag * (period - 1) + g[i]) / period
        al = (al * (period - 1) + l[i]) / period
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return 100 - 100 / (1 + ag / al)


def atr(b, period=14):
    if len(b) < period + 1:
        return None
    tr = [max(b[i]["high"] - b[i]["low"],
              abs(b[i]["high"] - b[i-1]["close"]),
              abs(b[i]["low"] - b[i-1]["close"])) for i in range(1, len(b))]
    a = sum(tr[:period]) / period
    for t in tr[period:]:
        a = (a * (period - 1) + t) / period
    return a


def feats(bars, i):
    w = bars[i-29:i+1] if i >= 29 else bars[:i+1]
    c = [x["close"] for x in w]
    if len(c) < 30:
        return None
    return {"rsi": rsi(c), "e9": ema(c, 9), "e21": ema(c, 21),
            "atr": atr(w), "close": c[-1],
            "highs": [x["high"] for x in w]}


def h60(bars60, j):
    w = bars60[j-29:j+1] if j >= 29 else bars60[:j+1]
    c = [x["close"] for x in w]
    if len(c) < 30:
        return None
    return {"rsi": rsi(c), "e9": ema(c, 9), "e21": ema(c, 21)}


def sig(f15, f60, p):
    if not f60 or not f15:
        return False
    trend_up = f60["e9"] > f60["e21"] and f15["e9"] > f15["e21"]
    if not trend_up:
        return False
    if p["mode"] == "pullback":
        return f15["close"] < f15["e9"] and f15["rsi"] <= p["rsi"]
    if p["mode"] == "breakout":
        lb = p["bb"]
        return f15["close"] > max(f15["highs"][-lb-1:-1])
    if p["mode"] == "hybrid":
        lb = p["bb"]
        pb = f15["close"] < f15["e9"] and f15["rsi"] <= p["rsi"]
        bo = f15["close"] > max(f15["highs"][-lb-1:-1])
        return pb or bo
    if p["mode"] == "dip":
        return f15["rsi"] <= p["rsi"] and f15["e9"] > f15["e21"]
    return False


def run(cap, b15, b60, p, lo=0, hi=None):
    n = len(b15)
    hi = hi if hi is not None else n - 1
    idx60 = {x["start"]: i for i, x in enumerate(b60)}
    q = cap
    start = cap
    pos = entry = peak = 0.0
    tr, fees = [], 0.0
    for i in range(max(30, lo), min(hi, n - 1)):
        cur, nxt = b15[i], b15[i + 1]
        if pos > 0:
            stop = entry * (1 - p["sl"]/100)
            take = entry * (1 + p["tp"]/100)
            trail = peak * (1 - p["trail"]/100) if p["trail"] else 0
            ex = kind = None
            if cur["low"] <= stop:
                ex, kind = stop, "SL"
            elif trail and cur["low"] <= trail:
                ex, kind = trail, "TR"
            elif cur["high"] >= take:
                ex, kind = take, "TP"
            if ex is not None:
                f = ex * (1 - SLIPPAGE)
                fee = pos * f * TAKER_FEE
                q += pos * f - fee
                fees += fee
                tr.append({"kind": kind, "pnl": (f - entry) * pos - fee,
                           "pct": (f/entry - 1) * 100})
                pos = entry = peak = 0.0
            else:
                peak = max(peak, cur["high"])
        if pos == 0:
            f15 = feats(b15, i)
            j = idx60.get(cur["start"])
            if f15 and j is not None and j >= 29:
                f60 = h60(b60, j)
                if f60 and sig(f15, f60, p):
                    f = nxt["open"] * (1 + SLIPPAGE)
                    budget = q * p["frac"]
                    fee = budget * TAKER_FEE
                    pos = (budget - fee) / f
                    entry = f
                    peak = nxt["high"]
                    q -= budget
                    fees += fee
    eq = q + pos * b15[min(hi, n-1)]["close"]
    return {"start": start, "equity": eq, "ret": (eq/start-1)*100,
            "trades": tr, "fees": fees}


def stats(r):
    t = r["trades"]
    if not t:
        return (0, 0.0, 0.0, 0.0)
    w = [x for x in t if x["pnl"] > 0]
    gw = sum(x["pnl"] for x in w)
    gl = abs(sum(x["pnl"] for x in t if x["pnl"] <= 0))
    return (len(t), len(w)/len(t)*100, (gw/gl if gl else (999.0 if gw > 0 else 0.0)),
            sum(x["pct"] for x in t)/len(t))


def line(tag, r):
    n, wr, pf, avg = stats(r)
    return (f"  {tag:<12} Ret {r['ret']:+7.2f}%  n={n:>4d}  WR {wr:5.1f}%"
            f"  PF {pf:5.2f}  Ø% {avg:+6.2f}  Gebühren {r['fees']:>9,.0f}")


# Bewusst kleines Grid: je mehr Parameter, desto eher findet man Zufall.
# Wir wollen robuste Sets, nicht den Bestwert von hunderten Varianten.
GRID = []
for mode in ("pullback", "breakout", "dip"):
    for rsi_v in (40, 50):
        for bb in (20,):
            for sl, tp in ((1.2, 2.4), (1.5, 2.0)):
                for trail in (0.0,):
                    for frac in (1.0,):
                        GRID.append(dict(mode=mode, rsi=rsi_v, bb=bb, sl=sl,
                                         tp=tp, trail=trail, frac=frac))


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "multi_asset_report.txt"), "w", encoding="utf-8")

    def p(*a):
        s = " ".join(str(x) for x in a)
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    p(f"Multi-Asset-Search, {days} Tage, {len(GRID)} Kombinationen je Paar")
    p("=" * 100)
    winners = []
    for sym in PAIRS:
        b15 = fetch(sym, "15", days)
        b60 = fetch(sym, "60", days)
        if len(b15) < 400 or len(b60) < 200:
            p(f"{sym}: zu wenig Daten ({len(b15)}/{len(b60)}) - uebersprungen")
            continue
        split = int(len(b15) * 0.6)
        p(f"\n### {sym}  ({len(b15)} Kerzen, "
          f"{time.strftime('%Y-%m-%d', time.localtime(b15[0]['start']/1000))}"
          f" bis {time.strftime('%Y-%m-%d', time.localtime(b15[-1]['start']/1000))})")

        scored = []
        for pr in GRID:
            r = run(50_000, b15, b60, pr, lo=30, hi=split)
            if not r["trades"]:
                continue
            n, wr, pf, avg = stats(r)
            sc = r["ret"] - max(0, n - 40) * 0.05
            scored.append((sc, pr, r))
        if not scored:
            p("  keine Trades in In-Sample")
            continue
        scored.sort(key=lambda x: x[0], reverse=True)

        p("  In-Sample:")
        for s, pr, r in scored[:3]:
            p(line(f"  {pr['mode']} r{pr['rsi']} {pr['sl']}/{pr['tp']}", r))
        best_in = scored[0]

        pr = best_in[1]
        o = run(50_000, b15, b60, pr, lo=split, hi=len(b15) - 1)
        p("  Out-of-Sample-Validierung mit dem In-Sample-Gewinner:")
        p(line("  OOS", o))
        if o["ret"] > 0 and best_in[2]["ret"] > 0 and len(o["trades"]) >= 2:
            winners.append((sym, pr, best_in[2], o))
            p(f"  >> ROBUST: {sym} positiv auf beiden Haelften")
        else:
            p(f"  >> {sym}: kein Setup ueberzeugt auf beiden Haelften")

    p("\n" + "=" * 100)
    p("ERGEBNIS")
    p("=" * 100)
    if not winners:
        p("  Kein einziges Setup war auf In- UND Out-of-Sample positiv.")
        p("  Interpretation: Die getesteten Regeln (RSI/EMA, 15m+1h, Long-only)")
        p("  haben auf diesen Maerkten keinen stabilen Edge. Das ist ein")
        p("  realistisches Ergebnis - nicht jeder Markt laesst sich mit so")
        p("  einfachen Mitteln profitabel handeln.")
    else:
        for sym, pr, ins, oos in winners:
            p(f"\n  {sym}: {pr}")
            p(line("  In-Sample", ins))
            p(line("  Out-of-Sample", oos))
    log.close()


if __name__ == "__main__":
    main()