#!/usr/bin/env python3
"""Kommandozeile fuer autonom-automatum.

Beispiele:
  python cli.py status            Aktueller Zustand
  python cli.py analyse           Technische Analyse
  python cli.py kosten            Kosten eines Roundtrips
  python cli.py paper             Paper-Report
  python cli.py tick              Einen Paper-Schritt ausfuehren
  python cli.py daemon            Dauerlauf mit Report am Ende
  python cli.py ask "Frage"       Assistent fragen

Sicherheit: Es gibt keinen Befehl fuer echte Orders. Der einzige Pfad zu
einer Börse ist dry_run.
"""
import argparse
import os
import sys
import time
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from core.trading_bot import CryptoTradingBot
from core.paper_trader import PaperTrader
from core.assistant import Assistant

_running = True


def _stop(signum, frame):
    global _running
    _running = False


def _kopf():
    print("=" * 64)
    print("  autonom-automatum")
    print("=" * 64)


def cmd_status(bot, paper):
    _kopf()
    d = bot.analyze()
    m, w = d["market"], d["wallet"]
    sym = bot.symbol
    quote = sym[3:] if sym[:3] in ("ETH", "BTC") else sym
    print(f"  Kurs          {m.get('last')} {quote}  ({m.get('eth_eur')} EUR)")
    print(f"  Spread        {m.get('spread_pct')}%")
    print(f"  Volumen 24h   {m.get('volume_24h')} ETH")
    print(f"  Signal        {d['action']}  (Konfidenz {d['confidence']:.0%})")
    mtf = d.get("mtf", {})
    print("  Zeitebenen    " + "  ".join(
        f"{k}:{v['action'][:4]}" for k, v in mtf.items()))
    print(f"  On-Chain      {w.get('balance_eth')} ETH")
    print("  Begruendung   " + d["reason"][:150])
    r = paper.report()
    print(f"  Paper         {r['equity']} USDC  ({r['return_pct']}%)  "
          f"Trades {r['trades']}")


def cmd_analyse(bot):
    _kopf()
    d = bot.analyze()
    for name, v in d.get("mtf", {}).items():
        print(f"  {name:<7} {v['action']:<5} RSI {str(v['rsi']):<6} "
              f"EMA9 {str(v['ema9']):<9} ATR {v['atr']}")
        print(f"          {v['reason'][:110]}")


def cmd_kosten(bot, paper):
    _kopf()
    a = Assistant(bot, paper)
    k = a._cmd_kosten()
    print(f"  Kapital              {k['kapital_usdc']} USDC")
    print(f"  Gebuehr je Seite     {k['gebuhr_pro_seite_prozent']} %")
    print(f"  Spread               {k['spread_prozent']} %")
    print(f"  Kosten je Roundtrip  {k['rundgangskosten_usdc']} USDC "
          f"= {k['rundgangskosten_prozent']} %")
    print(f"  Fuer 5 % Gewinn      {k['kursbewegung_fuer_5_prozent']} % Kursbewegung noetig")


def cmd_paper(paper):
    _kopf()
    r = paper.report()
    for k, v in r.items():
        print(f"  {k:<20} {v}")


def cmd_tick(bot, paper):
    _kopf()
    res = paper.tick()
    s = res["signal"]
    print(f"  Signal {s['action']}  Konfidenz {s['confidence']:.0%}")
    if s["reason"]:
        print(f"  {s['reason'][:120]}")
    if res["result"]:
        f = res["result"]
        print(f"  FILL {f['side']} {f['qty']} @ {f['fill']}  Gebuehr {f['fee']}")
    print(f"  Equity {res['equity']} USDC  Drawdown {res['drawdown_pct']}%")


def cmd_daemon(bot, paper, intervall):
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    _kopf()
    print(f"  Daemon laeuft, Intervall {intervall}s. Beenden mit Strg+C.\n")
    print(f"  {'Zeit':<9} {'Equity':>10} {'Return':>8} {'Signal':<6} {'Trades':>7}")
    print("  " + "-" * 56)
    while _running:
        try:
            res = paper.tick()
            s = res["signal"]
            marke = "FILL" if res["result"] else "-"
            print(f"  {time.strftime('%H:%M:%S'):<9} {res['equity']:>10.4f} "
                  f"{paper.report()['return_pct']:>7.2f}% {marke:<6} "
                  f"{len(paper.state['trades']):>7}")
            sys.stdout.flush()
        except Exception as exc:
            print(f"  Fehler: {exc}")
        for _ in range(intervall):
            if not _running:
                break
            time.sleep(1)
    print("\n  Beendet.")
    cmd_paper(paper)


def cmd_ask(bot, paper, frage):
    a = Assistant(bot, paper)
    print(a.ask(frage))


def main():
    p = argparse.ArgumentParser(
        description="autonom-automatum - Trading-Werkzeug fuer Bybit EU")
    p.add_argument("--symbol", default="ETHUSDC", help="Handelspaar (Standard ETHUSDC)")
    p.add_argument("--kapital", type=float, default=6.79, help="Startkapital Paper (USDC)")
    sub = p.add_subparsers(dest="befehl", required=True)
    for name, hilfe in (("status", "Aktueller Zustand"),
                        ("analyse", "Technische Analyse"),
                        ("kosten", "Roundtrip-Kosten"),
                        ("paper", "Paper-Report"),
                        ("tick", "Ein Paper-Schritt")):
        sub.add_parser(name, help=hilfe)
    d = sub.add_parser("daemon")
    d.add_argument("--intervall", type=int, default=300, help="Sekunden zwischen Ticks")
    a = sub.add_parser("ask")
    a.add_argument("frage", help="Frage an den Assistenten")

    args = p.parse_args()
    bot = CryptoTradingBot(symbol=args.symbol)
    paper = PaperTrader(symbol=args.symbol, initial_quote=args.kapital)

    if args.befehl == "status":
        cmd_status(bot, paper)
    elif args.befehl == "analyse":
        cmd_analyse(bot)
    elif args.befehl == "kosten":
        cmd_kosten(bot, paper)
    elif args.befehl == "paper":
        cmd_paper(paper)
    elif args.befehl == "tick":
        cmd_tick(bot, paper)
    elif args.befehl == "daemon":
        cmd_daemon(bot, paper, args.intervall)
    elif args.befehl == "ask":
        cmd_ask(bot, paper, args.frage)


if __name__ == "__main__":
    main()
