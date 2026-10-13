"""Eindeutschsprachiger Bedien-Assistent fuer die Trading-GUI.

Der Assistent kennt den Live-Zustand des Bots (Preise, Signale, Bilanz,
Risiko) und kann eine Whitelist harmloser Befehle ausfuehren.

SICHERHEIT:
  - Keine echten Orders. Befehle koennen ausschliesslich lesen, analysieren
    oder die Paper-Simulation starten.
  - Es gibt keinen Befehl fuer "live kaufen/verkaufen".
"""
import json
import time
from core.openrouter import OpenRouterEngine

SYSTEM_PROMPT = """Du bist der Bedien-Assistent der Trading-Anwendung "autonom-automatum".
Du antwortest AUSSCHLIESSLICH auf Deutsch, sachlich, kurz und praezise.

Fachlicher Hintergrund:
- Der Bot handelt ETH/USDC auf Bybit EU (Spot). Kein Derivat, kein USDT-Paar.
- Signale entstehen aus echten Kerzendaten: RSI, EMA9/EMA21, ATR.
- Ein Trade nur, wenn 15-Minuten- UND 1-Stunden-Trend dieselbe Richtung zeigen.
- Gebuehren: 0,1% pro Seite. Spread aktuell sehr klein.
- Die Anwendung laeuft standardmaessig im PAPER-MODUS: echte Marktdaten,
  simulierte Orders, echtes Tracking. Es werden keine echten Geldtransfers ausgefuehrt.
- Risikolimits: max. Trade 25 USDC, Reserve 10 USDC, max. 5 Trades pro Stunde.

Formeln:
  %befehl% fuehrt einen Befehl aus. Verfuegbare Befehle:
  - %status%   : aktueller Zustand (Preis, Bilanz, Signale)
  - %analyse%  : technische Analyse ausfuehren und erklaeren
  - %paper%    : Paper-Trading-Report
  - %kosten%   : Gebuehren und Kosten eines Roundtrips berechnen
  - %settings% : aktive Einstellungen und Risiko-Limits
  - %reset%    : Paper-Portfolio zuruecksetzen
  Wenn mehrere passen, fuehre alle aus und beziehe dich in deiner Antwort darauf.

Regeln:
- Nutze Zahlen aus dem Live-Kontext, rate nicht.
- Steht unter "hinweise" eine Warnung, nenne sie ausdruecklich: sie bedeutet,
  dass mit den aktuellen Einstellungen gar nicht gehandelt werden kann.
- Erklaerst du Gebuehren und Risiken, sei ehrlich: bei kleinem Kapital sind
  Gebuehren der groesste Kostenposten.
- Wenn ein Befehl fehlschlaegt, sage das klar.
- Hoechstens 6 Saetze Antwort."""


class Assistant:
    def __init__(self, bot, paper):
        self.bot = bot
        self.paper = paper
        self.llm = OpenRouterEngine()
        self.history = []

    # ---------- Befehle ----------
    def _cmd_status(self):
        d = self.bot.analyze()
        m, w = d["market"], d["wallet"]
        mtf = d.get("mtf", {})
        return {
            "preis_usdc": m.get("last"),
            "preis_eur": m.get("eth_eur"),
            "spread_prozent": m.get("spread_pct"),
            "volumen_24h_eth": m.get("volume_24h"),
            "signal": d["action"],
            "konfidenz": d["confidence"],
            "begruendung": d["reason"][:200],
            "timeframes": {k: v["action"] for k, v in mtf.items()},
            "rsi_1h": mtf.get("1h", {}).get("rsi"),
            "onchain_eth": w.get("balance_eth"),
            "risiko": self.bot.risk.stats(),
        }

    def _cmd_analyse(self):
        s = self._cmd_status()
        ind = {}
        for iv, name in (("15", "15min"), ("60", "1h"), ("240", "4h")):
            from core import indicators
            ind[name] = indicators.analyze(self.bot.exchange.klines(self.bot.symbol, iv, limit=100))
        s["indikatoren"] = {k: {"aktion": v["action"], "rsi": v["rsi"], "atr": v["atr"],
                                "grund": v["reason"][:120]} for k, v in ind.items()}
        return s

    def _cmd_paper(self):
        return self.paper.report()

    def _cmd_kosten(self):
        snap = self.bot.exchange.market_snapshot(self.bot.symbol)
        px = snap["last"]
        fee = 0.001
        spread_cost = abs(snap["ask"] - snap["bid"])
        beispiel = self.paper.initial_quote
        qty = beispiel / px
        roundtrip = 2 * (beispiel * fee) + spread_cost * qty
        return {
            "kapital_usdc": beispiel,
            "spread_prozent": round(snap["spread_pct"], 4),
            "gebuhr_pro_seite_prozent": 0.1,
            "rundgangskosten_usdc": round(roundtrip, 4),
            "rundgangskosten_prozent": round(roundtrip / beispiel * 100, 3),
            "kursbewegung_fuer_5_prozent": round(5 + roundtrip / beispiel * 100, 2),
        }

    def _cmd_reset(self):
        self.paper.reset()
        return self.paper.report()

    def _cmd_settings(self):
        from core.settings import Settings
        s = Settings()
        w = s.werte
        return {
            "symbol": w["symbol"],
            "startkapital_usdc": w["initial_quote"],
            "max_trade_usdc": w["max_trade_quote"],
            "reserve_usdc": w["min_reserve_quote"],
            "max_trades_pro_stunde": w["max_trades_per_hour"],
            "aktualisierung_sekunden": w["refresh_ms"] // 1000,
            "aktive_risiko_limits": self.bot.risk.stats(),
            "hinweise": s.pruefe(),
            "datei": "data/settings.json",
        }

    # Zuordnung als METHODENNAME, nicht als Funktionsobjekt - sonst geht
    # das self beim Aufruf verloren ("_cmd_status() missing 1 required
    # positional argument: 'self'").
    COMMANDS = {
        "status": "_cmd_status",
        "analyse": "_cmd_analyse",
        "paper": "_cmd_paper",
        "kosten": "_cmd_kosten",
        "reset": "_cmd_reset",
        "settings": "_cmd_settings",
    }

    # Ueber dem Chat: Fragen zu den Einstellungen.
    EINSTELLUNGSFRAGEN = [
        "Welche Einstellungen sind gerade aktiv? %settings%",
        "Passen meine Risiko-Limits zu meinem Kapital? %settings% %kosten%",
        "Warum wurde kein Trade ausgefuehrt? %analyse% %settings%",
        "Was kostet ein Roundtrip bei meinem Kapital? %kosten% %paper%",
    ]

    BEISPIELFRAGEN = [
        "Wie teuer ist ein Roundtrip? %kosten%",
        "Was ist gerade das Signal? %status%",
        "Analysiere den Markt. %analyse%",
        "Zeig mir den Paper-Report. %paper%",
        "Lohnt sich Trading mit meinem Kapital? %kosten% %paper%",
    ]

    # ---------- Frage beantworten ----------
    def ask(self, frage):
        frage = (frage or "").strip()
        if not frage:
            return "Bitte eine Frage eingeben."

        results = {}
        for name, methode in self.COMMANDS.items():
            if f"%{name}%" in frage:
                try:
                    results[name] = getattr(self, methode)()
                except Exception as exc:
                    results[name] = {"fehler": str(exc)}

        ctx = json.dumps(results, ensure_ascii=False, default=str) if results else \
            "Kein Befehl in der Frage. Verfuegbar: %status% %analyse% %paper% %kosten% %reset%"

        self.history.append({"role": "user", "content": frage})
        self.history = self.history[-8:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += self.history
        messages.append({"role": "user",
                         "content": f"{frage}\n\nLIVE-KONTEXT:\n{ctx}"})

        antwort = self.llm.chat(messages)
        if not antwort or not str(antwort).strip():
            antwort = ("Es kam keine Antwort. Der Free-Router von OpenRouter ist "
                       "in der Regel ueberlastet - bitte gleich nochmal fragen.")
        antwort = str(antwort).strip()

        # WICHTIG: Das Sprachmodell rechnet unzuverlaessig - es hat oben
        # 0,20 statt 0,0136 USDC genannt. Die belastbaren Zahlen werden
        # darunter fest aus den berechneten Werten gesetzt, nicht erfunden.
        fakten = self._fakten(results)
        if fakten:
            antwort = antwort + "\n\n--- Aus den Live-Daten berechnet ---\n" + fakten

        self.history.append({"role": "assistant", "content": antwort})
        return antwort

    def _fakten(self, results):
        """Erzeugt die Zahlen direkt aus den berechneten Werten."""
        z = []
        if "kosten" in results and "fehler" not in results["kosten"]:
            k = results["kosten"]
            z.append(f"Kapital:          {k['kapital_usdc']} USDC")
            z.append(f"Gebuehr je Seite: {k['gebuhr_pro_seite_prozent']} %")
            z.append(f"Spread:           {k['spread_prozent']} %")
            z.append(f"Kosten je Roundtrip: {k['rundgangskosten_usdc']} USDC "
                     f"= {k['rundgangskosten_prozent']} %")
            z.append(f"Fuer 5 % Gewinn noetig: {k['kursbewegung_fuer_5_prozent']} % Kursbewegung")
        if "paper" in results and "fehler" not in results["paper"]:
            p = results["paper"]
            z.append("")
            z.append(f"Paper-Kapital:    {p['equity']} USDC")
            z.append(f"Rendite:         {p['return_pct']} %")
            z.append(f"Trades:          {p['trades']} (gewonnen {p['wins']} / verloren {p['losses']})")
            z.append(f"Quotenverhaeltnis (Profit-Faktor): {p['profit_factor']}")
            z.append(f"Gezahlte Gebuehren: {p['fees_paid']} USDC")
        if "status" in results and "fehler" not in results["status"]:
            s = results["status"]
            z.append("")
            z.append(f"Kurs:            {s['preis_usdc']} USDC = {s['preis_eur']} EUR")
            z.append(f"Signal:          {s['signal']} (Konfidenz {s['konfidenz']})")
            z.append(f"Zeitebenen:      {s['timeframes']}")
        if "analyse" in results and "fehler" not in results["analyse"]:
            a = results["analyse"]
            z.append("")
            for name, v in a.get("indikatoren", {}).items():
                z.append(f"{name}: {v['aktion']}  RSI {v['rsi']}  ATR {v['atr']}")
        return "\n".join(z)
