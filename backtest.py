#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backtest der Paper-Strategie auf echten historischen Bybit-Kerzendaten.

Warum das noetig ist: Der Paper-Runner sammelt nur Live-Ticks im 5-Min-Takt.
Das liefert zu wenige Trades fuer eine Aussage. Dieser Backtest replayt
historische Kerzen mit derselben Logik wie core/paper_trader.py:

  - Signal aus 1h (Trendfilter) + 15m (Einstieg)
  - Stop-Loss / Take-Profit / Trailing-Stop
  - Trendfilter: kein Long, wenn 1h im Abwaertstrend
  - RSI-Filter: kein Long bei RSI > 60, kein Sell bei RSI < 40

Realitaetsannahmen (bewusst pessimistisch, wie im Paper-Trader):
  - Signal entsteht aus Kerze N, Fill passiert zum Open von Kerze N+1
    (kein Look-Ahead auf die Schlusskurse der Signal-Kerze)
  - Fill zum Open mit Slippage: Kauf +0,05%, Verkauf -0,05%
  - Gebuehren 0,1% pro Seite
  - Innerhalb einer Kerze wird der Stop-Loss VOR dem Take-Profit geprueft
    (schlechtester Fall zuerst)

Aufruf:  python backtest.py [Tage]
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from core import indicators

API = "https://api.bybit.eu"
SYMBOL = "ETHUSDC"

TAKER_FEE = 0.001
SLIPPAGE = 0.0005
STOP_LOSS_PCT = 1.5
TAKE_PROFIT_PCT = 2.0
TRAIL_PCT = 1.0
MIN_CONFIDENCE = 0.22

INTERVAL_MS = {"15": 15 * 60 * 1000, "60": 60 * 60 * 1000}


def fetch_klines(interval, days):
    """Historische Kerzen per Paginierung (Bybit liefert max. 1000 pro Aufruf)."""
    step = INTERVAL_MS[interval]
    end = int(time.time() * 1000)
    start = end - days * 24 * 60 * 60 * 1000
    out = []
    cursor = end
    while cursor > start:
        params = {
            "category": "spot", "symbol": SYMBOL, "interval": interval,
            "limit": 1000, "end": cursor,
        }
        r = requests.get(f"{API}/v5/market/kline", params=params, timeout=30)
        r.raise_for_status()
        rows = r.json().get("result", {}).get("list", [])
        if not rows:
            break
        oldest = min(int(x[0]) for x in rows)
        out.extend(rows)
        if oldest <= start:
            break
        cursor = oldest - 1
        time.sleep(0.15)          # Rate-Limit schonen
    out.sort(key=lambda x: int(x[0]))
    seen, uniq = set(), []
    for x in out:
        if x[0] not in seen:
            seen.add(x[0])
            uniq.append(x)
    return [dict(start=int(x[0]), open=float(x[1]), high=float(x[2]),
                 low=float(x[3]), close=float(x[4])) for x in uniq]


def signal_for(k15_window, k1h_window, min_confidence):
    """Dieselbe Filterlogik wie PaperTrader._signal()."""
    s1h = indicators.analyze(k1h_window)
    s15 = indicators.analyze(k15_window)

    agree = s1h["action"] == s15["action"]
    strong_15 = s15["confidence"] >= min_confidence
    if not ((agree and s1h["action"] in ("BUY", "SELL")) or strong_15):
        return "HOLD", s1h, s15

    action = s1h["action"] if agree else s15["action"]
    rsi = s15.get("rsi")
    if action == "BUY":
        if s1h["action"] == "SELL":
            return "HOLD", s1h, s15
        if rsi is not None and rsi > 60:
            return "HOLD", s1h, s15
    if action == "SELL":
        if rsi is not None and rsi < 40:
            return "HOLD", s1h, s15
    return action, s1h, s15


def run(quote: float, bars15, bars60, min_confidence=MIN_CONFIDENCE, frac=1.0):
    """Replay ueber 15m-Kerzen; 1h-Fenster kommt aus dem 60m-Array.

    frac=1.0 -> jedes Signal setzt das gesamte freie Kapital ein.
    frac<1.0 -> nur einen Bruchteil, Rest bleibt als Liquiditaet liegen.
    """
    start_quote = quote          # Startkapital festhalten (quote veraendert sich)
    pos_eth = 0.0
    entry = 0.0
    peak = 0.0
    trades = []
    fees_total = 0.0
    peak_equity = quote
    max_dd = 0.0

    # Index-Map: 15m-Kerzenzeit -> Position im 60m-Array
    idx60 = {b["start"]: i for i, b in enumerate(bars60)}

    for i in range(30, len(bars15) - 1):
        cur = bars15[i]
        nxt = bars15[i + 1]

        # --- Offene Position verwalten (Fill zum Open der naechsten Kerze) ---
        if pos_eth > 0:
            entry_px = entry
            stop_px = entry * (1 - STOP_LOSS_PCT / 100)
            take_px = entry * (1 + TAKE_PROFIT_PCT / 100)
            trail_px = peak * (1 - TRAIL_PCT / 100)

            exit_px, exit_kind = None, None
            # Kerzen-Hoch/-Tief der Signal-Kerze fuer die Ausfuehrung nutzen
            if cur["low"] <= stop_px:
                exit_px, exit_kind = stop_px, "SL"
            elif cur["low"] <= trail_px:
                exit_px, exit_kind = trail_px, "TRAIL"
            elif cur["high"] >= take_px:
                exit_px, exit_kind = take_px, "TP"

            if exit_px is not None:
                fill = exit_px * (1 - SLIPPAGE)      # Verkauf zum Bid
                fee = pos_eth * fill * TAKER_FEE
                quote += pos_eth * fill - fee
                fees_total += fee
                pnl = (fill - entry_px) * pos_eth - fee
                trades.append({
                    "kind": exit_kind, "entry": round(entry_px, 2),
                    "exit": round(fill, 2),
                    "pnl": pnl, "pnl_pct": (fill / entry_px - 1) * 100,
                })
                pos_eth = 0.0
                entry = 0.0
                peak = 0.0
            else:
                peak = max(peak, cur["high"])

            eq = quote + pos_eth * cur["close"]
            peak_equity = max(peak_equity, eq)
            max_dd = min(max_dd, (eq - peak_equity) / peak_equity * 100)

        # --- Neues Signal (nur ohne offene Position bzw. nach Exit) ---
        if pos_eth == 0:
            j = idx60.get(cur["start"])
            if j is not None and j >= 30:
                action, _, _ = signal_for(bars15[i - 29:i + 1],
                                          bars60[j - 29:j + 1],
                                          min_confidence)
                if action == "BUY":
                    fill = nxt["open"] * (1 + SLIPPAGE)   # Kauf zum Ask
                    # Nur einen Bruchteil einsetzen? Dann bleibt Liquiditaet
                    # fuer spaetere, guenstigere Kaufsignale stehen.
                    budget = quote if frac >= 1.0 else quote * frac
                    fee = budget * TAKER_FEE
                    pos_eth = (budget - fee) / fill
                    entry = fill
                    peak = nxt["high"]
                    quote -= budget
                    fees_total += fee

    # Restposition zum letzten Kurs bewerten
    last = bars15[-1]["close"]
    equity = quote + pos_eth * last
    return {
        "start": start_quote, "equity": equity,
        "ret_pct": (equity / start_quote - 1) * 100,
        "trades": trades, "fees": fees_total,
        "max_dd": max_dd, "open_eth": pos_eth,
    }


def report(label, res):
    t = res["trades"]
    wins = [x for x in t if x["pnl"] > 0]
    losses = [x for x in t if x["pnl"] <= 0]
    gw = sum(x["pnl"] for x in wins)
    gl = abs(sum(x["pnl"] for x in losses))
    print(f"\n=== {label} ===")
    print(f"  Startkapital   : {res['start']:>12,.2f}")
    print(f"  Endkapital     : {res['equity']:>12,.2f}")
    print(f"  Rendite        : {res['ret_pct']:>12.2f} %")
    print(f"  Trades         : {len(t):>12d}   (Gewinn {len(wins)} / Verlust {len(losses)})")
    if t:
        wr = len(wins) / len(t) * 100
        pf = gw / gl if gl else None
        print(f"  Trefferquote   : {wr:>12.1f} %")
        print(f"  Profit-Faktor  : {pf:>12.2f}" if pf else "  Profit-Faktor  :          --")
        avg = sum(x["pnl"] for x in t) / len(t)
        print(f"  O Trade PnL    : {avg:>12.4f}")
    print(f"  Gebuehren      : {res['fees']:>12.2f}")
    print(f"  max. Drawdown  : {res['max_dd']:>12.2f} %")
    return res["ret_pct"]


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print(f"Lade {days} Tage {SYMBOL}-Historie von Bybit EU ...")
    bars15 = fetch_klines("15", days)
    bars60 = fetch_klines("60", days)
    print(f"  15m-Kerzen: {len(bars15)} | 60m-Kerzen: {len(bars60)}")
    if len(bars15) < 100:
        print("Zu wenig Daten - Abbruch.")
        return
    t0 = bars15[0]["start"]; t1 = bars15[-1]["start"]
    print(f"  Zeitraum: {time.strftime('%Y-%m-%d %H:%M', time.localtime(t0/1000))}"
          f"  bis  {time.strftime('%Y-%m-%d %H:%M', time.localtime(t1/1000))}")

    # A) Kapital 50.000, All-In je Signal
    r_big = run(50_000.0, bars15, bars60)
    # B) Massstab 50, All-In - muss prozentgleich sein
    r_small = run(50.0, bars15, bars60)
    a = report("50.000 Startkapital, All-In", r_big)
    b = report("50 Startkapital, All-In (Massstab)", r_small)

    print("\n=== Vergleich Kapitalgroesse ===")
    print(f"  Rendite 50.000 : {a:+.2f} %")
    print(f"  Rendite     50 : {b:+.2f} %")
    print(f"  Differenz      : {a-b:+.2f} Prozentpunkte")
    print("  -> Die Strategie setzt das gesamte Kapital pro Trade ein.")
    print("     Der Prozentwert ist daher kapitalunabhaengig: 50.000 ist")
    print("     derselbe Trade-Vektor wie 50, nur 1000x skaliert.")

    # C) Teilkapital-Varianten: wirkt weniger All-In besser?
    print("\n=== Teilkapital statt All-In (50.000 Startkapital) ===")
    results = {}
    for frac in (1.0, 0.75, 0.5, 0.25):
        res = run(50_000.0, bars15, bars60, frac=frac)
        results[frac] = res
        report(f"  Anteil je Signal: {int(frac*100)} %", res)

    print("\n=== Fazit ===")
    best = max(results.items(), key=lambda kv: kv[1]["ret_pct"])
    print(f"  Beste Variante : {int(best[0]*100)} % je Signal"
          f" -> {best[1]['ret_pct']:+.2f} %")
    print(f"  Worst Case     : {min(v['ret_pct'] for v in results.values()):+.2f} %")
    if all(v["ret_pct"] < 0 for v in results.values()):
        print("  -> Alle Varianten verlieren. Die Strategie hat in diesem")
        print("     Zeitraum keinen Edge; die Gebuehren (2x0,1% je Roundtrip)")
        print("     uebersteigen jeden Signal-Vorteil.")


if __name__ == "__main__":
    main()