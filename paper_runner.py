#!/usr/bin/env python3
"""Paper-Trading-Daemon: laeuft im Hintergrund, sammelt Track-Record.

Nutzt ECHTE Marktdaten von Bybit EU, simuliert aber jede Ausfuehrung.
Es wird niemals eine echte Order gesendet - siehe core/paper_trader.py.

Start:  python paper_runner.py
Stopp:   Strg+C
Report:  python paper_runner.py --report
Reset:   python paper_runner.py --reset
"""
import sys, os, time, signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from core.paper_trader import PaperTrader
from core import config, logger

INTERVAL = 300  # 5 Minuten zwischen Ticks

_log = logger.DualLogger()
_running = True


def _stop(signum, frame):
    global _running
    _running = False


def show(pt, extra=""):
    r = pt.report()
    print(f"[{time.strftime('%H:%M:%S')}] Equity {r['equity']:>10.4f} USDC "
          f"| Return {r['return_pct']:>7.2f}% | Trades {r['trades']} "
          f"| Winrate {r['winrate'] if r['winrate'] is not None else '-'}"
          f"| DD {r['max_drawdown_pct']:.2f}% {extra}")
    sys.stdout.flush()


def main():
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if "--reset" in sys.argv:
        PaperTrader().reset()
        print("Portfolio zurueckgesetzt.")
        return

    pt = PaperTrader(initial_quote=6.79)

    if "--report" in sys.argv:
        r = pt.report()
        print("=" * 62)
        print("  PAPER-TRADING REPORT (echte Daten, simulierte Orders)")
        print("=" * 62)
        for k, v in r.items():
            print(f"  {k:<20}: {v}")
        print("=" * 62)
        return

    _log.info(f"Paper-Trading-Daemon gestartet (Intervall {INTERVAL}s, Symbol {pt.symbol})")
    print("Paper-Trading-Daemon laeuft. Beenden mit Strg+C.\n")
    show(pt, "| Start")
    tick = 0
    while _running:
        tick += 1
        try:
            res = pt.tick()
            s = res["signal"]
            extra = ""
            if res["result"]:
                r0 = res["result"]
                extra = f"| FILL {r0['side']} {r0['qty']} @ {r0['fill']}"
            show(pt, f"| {s['action']:<4} {extra}")
        except Exception as exc:
            _log.error(f"Paper-Tick {tick} fehlgeschlagen: {exc}")
            print(f"  Fehler: {exc}")
        for _ in range(INTERVAL):
            if not _running:
                break
            time.sleep(1)

    r = pt.report()
    _log.info(f"Paper-Daemon beendet. Equity {r['equity']} USDC, Return {r['return_pct']}%")
    print(f"\nBeendet. Equity {r['equity']:.4f} USDC | Return {r['return_pct']:.2f}% "
          f"| Trades {r['trades']} | Gebuehren {r['fees_paid']:.4f}")


if __name__ == "__main__":
    main()
