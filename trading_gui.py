#!/usr/bin/env python3
"""Trading-Oberflaeche fuer autonom-automatum. Durchgehend deutsch.

Bereiche:
  - Kursdiagramm (echte Bybit-Kerzendaten)
  - Live-Werte, Signal, Risiko
  - Paper-Trading-Bilanz
  - Assistent-Chat (OpenRouter)
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, time, threading, queue
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from core.trading_bot import CryptoTradingBot
from core.paper_trader import PaperTrader
from core.assistant import Assistant
from core import indicators, config

# Farben
BG = "#0d1117"
PANEL = "#161b22"
TEXT = "#e6edf3"
Gruen = "#00ff88"
Rot = "#ff5555"
Gelb = "#ffcc00"
Grau = "#8b949e"
Blau = "#58a6ff"
Violett = "#bc8cff"

PAARE = ["ETHUSDC", "ETHEUR", "ETHPLN", "BTCUSDC", "BTCEUR"]


class ChartCanvas(tk.Canvas):
    """Zeichnet echte Kerzendaten direkt auf ein Canvas - ohne matplotlib."""

    def __init__(self, master, **kw):
        super().__init__(master, bg=PANEL, highlightthickness=0, **kw)
        self.kerzen = []
        self.kaufen = []     # (index, preis)
        self.verkaufen = []
        self.titel = ""

    def zeichne(self, kerzen, kaufen=None, verkaufen=None, titel=""):
        self.kerzen = kerzen or []
        self.kaufen = kaufen or []
        self.verkaufen = verkaufen or []
        self.titel = titel
        self._render()

    def _render(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        pad_l, pad_r, pad_t, pad_b = 8, 60, 22, 20

        self.create_text(10, 8, text=self.titel, anchor="w", fill=Grau,
                         font=("Consolas", 8, "bold"))

        if not self.kerzen:
            self.create_text(w / 2, h / 2, text="Lade Kursdaten ...",
                             fill=Grau, font=("Consolas", 10))
            return

        k = self.kerzen
        highs = [c["high"] for c in k]
        lows = [c["low"] for c in k]
        hmax, lmin = max(highs), min(lows)
        span = (hmax - lmin) or 1
        n = len(k)
        bw = max((w - pad_l - pad_r) / n, 1)

        def y(v):
            return pad_t + (hmax - v) / span * (h - pad_t - pad_b)

        # Gitter + Preisskala
        for i in range(5):
            v = lmin + span * i / 4
            yy = y(v)
            self.create_line(pad_l, yy, w - pad_r, yy, fill="#21262d")
            self.create_text(w - pad_r + 5, yy, text=f"{v:,.0f}", anchor="w",
                             fill=Grau, font=("Consolas", 7))

        # Kerzen
        for i, c in enumerate(k):
            x = pad_l + i * bw + bw / 2
            auf = c["close"] >= c["open"]
            farbe = Gruen if auf else Rot
            self.create_line(x, y(c["high"]), x, y(c["low"]), fill=farbe)
            y1, y2 = y(max(c["open"], c["close"])), y(min(c["open"], c["close"]))
            self.create_rectangle(x - bw * 0.32, y1, x + bw * 0.32, max(y2, y1 + 1), fill=farbe)

        # Marker
        for idx, preis in self.kaufen:
            if 0 <= idx < n:
                x = pad_l + idx * bw + bw / 2
                self.create_text(x, y(preis) - 10, text="A", fill=Gruen,
                                 font=("Consolas", 9, "bold"))
        for idx, preis in self.verkaufen:
            if 0 <= idx < n:
                x = pad_l + idx * bw + bw / 2
                self.create_text(x, y(preis) + 14, text="V", fill=Rot,
                                 font=("Consolas", 9, "bold"))

        schluss = k[-1]["close"]
        self.create_line(pad_l, y(schluss), w - pad_r, y(schluss),
                         fill=Blau, dash=(3, 3))
        self.create_text(w - pad_r + 5, y(schluss), text=f"{schluss:,.1f}",
                         anchor="w", fill=Blau, font=("Consolas", 7, "bold"))


class TradingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("autonom-automatum — Trading-Oberfläche")
        self.root.geometry("1180x780")
        self.root.configure(bg=BG)

        self.bot = CryptoTradingBot()
        self.paper = PaperTrader()
        self.assistent = Assistant(self.bot, self.paper)
        self.laeuft = True
        self.letzte = None
        self.chat_laeuft = False
        self._chat_warteschlange = queue.Queue()

        self._baue()
        self._sag("Anwendung gestartet. Lade Marktdaten von Bybit EU ...")
        self.root.after(300, self._chat_entleeren)
        self._aktualisiere()

    # ---------- Aufbau ----------
    def _panel(self, eltern, titel):
        f = tk.Frame(eltern, bg=PANEL, bd=1, relief=tk.RIDGE)
        f.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        tk.Label(f, text=titel, bg=PANEL, fg=Grau,
                 font=("Consolas", 9, "bold")).grid(row=0, column=0, columnspan=3,
                                                   sticky="w", padx=8, pady=(6, 2))
        f.columnconfigure(1, weight=1)
        return f

    def _zeile(self, eltern, beschriftung, r, standard="-"):
        tk.Label(eltern, text=beschriftung, bg=PANEL, fg=TEXT,
                 font=("Consolas", 9)).grid(row=r + 1, column=0, sticky="w", padx=8)
        lbl = tk.Label(eltern, text=standard, bg=PANEL, fg=Gruen, font=("Consolas", 9, "bold"))
        lbl.grid(row=r + 1, column=1, sticky="e", padx=8)
        return lbl

    def _baue(self):
        kopf = tk.Frame(self.root, bg=BG)
        kopf.pack(fill=tk.X, padx=8, pady=(8, 0))
        tk.Label(kopf, text="autonom-automatum", bg=BG, fg=Gruen,
                 font=("Consolas", 16, "bold")).pack(side="left")
        self.l_status = tk.Label(kopf, text="verbinde ...", bg=BG, fg=Grau, font=("Consolas", 9))
        self.l_status.pack(side="right")

        mitte = tk.Frame(self.root, bg=BG)
        mitte.pack(fill=tk.BOTH, expand=True, padx=5, pady=4)

        links = tk.Frame(mitte, bg=BG)
        links.pack(side="left", fill=tk.BOTH, expand=True)
        rechts = tk.Frame(mitte, bg=BG)
        rechts.pack(side="left", fill=tk.BOTH, expand=True)

        # ---- Chart ----
        chart_rahmen = tk.Frame(links, bg=PANEL, bd=1, relief=tk.RIDGE)
        chart_rahmen.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        kopfzeile = tk.Frame(chart_rahmen, bg=PANEL)
        kopfzeile.pack(fill=tk.X, padx=8, pady=(6, 0))
        tk.Label(kopfzeile, text="KURSVERLAUF", bg=PANEL, fg=Grau,
                 font=("Consolas", 9, "bold")).pack(side="left")
        self.zeitraum = tk.StringVar(value="15")
        for iv, txt in (("15", "15 Min"), ("60", "1 Std"), ("240", "4 Std"), ("D", "1 Tag")):
            tk.Radiobutton(kopfzeile, text=txt, variable=self.zeitraum, value=iv,
                           bg=PANEL, fg=TEXT, selectcolor=PANEL, activebackground=PANEL,
                           activeforeground=Gruen, font=("Consolas", 8),
                           command=self._diagramm_neu).pack(side="right")
        self.chart = ChartCanvas(chart_rahmen, height=300)
        self.chart.pack(fill=tk.BOTH, expand=True, padx=2, pady=4)

        # ---- Markt + Signal ----
        markt = self._panel(links, "MARKT (Bybit EU)")
        self.l_preis = self._zeile(markt, "Kurs", 0)
        self.l_eur = self._zeile(markt, "Wert in EUR", 1)
        self.l_spread = self._zeile(markt, "Spread", 2)
        self.l_volumen = self._zeile(markt, "Volumen 24 Std", 3)

        signal = self._panel(links, "SIGNAL")
        self.l_signal = self._zeile(signal, "Empfehlung", 0, "HOLD")
        self.l_konf = self._zeile(signal, "Konfidenz", 1)
        self.l_tf = self._zeile(signal, "Zeitebenen 5m/15m/1h/4h", 2)
        self.l_grund = tk.Label(signal, text="-", bg=PANEL, fg=TEXT, font=("Consolas", 8),
                                wraplength=380, justify="left")
        self.l_grund.grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        # ---- Paper-Bilanz ----
        paper = self._panel(rechts, "PAPER-TRADING (Simulation, kein echtes Geld)")
        self.l_equity = self._zeile(paper, "Kapital", 0)
        self.l_rendite = self._zeile(paper, "Rendite", 1)
        self.l_trades = self._zeile(paper, "Trades (gewonnen/verloren)", 2)
        self.l_winrate = self._zeile(paper, "Trefferquote", 3)
        self.l_gebuehr = self._zeile(paper, "Gezahlte Gebühren", 4)
        self.l_dd = self._zeile(paper, "Drawdown", 5)

        self.btn_tick = tk.Button(paper, text="PAPER-TICK AUSFÜHREN", command=self._paper_tick,
                                  bg=Blau, fg="#000", font=("Consolas", 9, "bold"))
        self.btn_tick.grid(row=7, column=0, columnspan=2, pady=6)

        # ---- Risiko + Konto ----
        risiko = self._panel(rechts, "RISIKO-LIMITS")
        self.l_maxtrade = self._zeile(risiko, "Max. Trade", 0)
        self.l_reserve = self._zeile(risiko, "Reserve", 1)
        self.l_stunde = self._zeile(risiko, "Trades pro Stunde", 2)

        konto = self._panel(rechts, "BYBIT-KONTO")
        self.l_konto = self._zeile(konto, "Keys hinterlegt", 0)
        self.l_guthaben = self._zeile(konto, "ETH im Handelskonto", 1)
        self.l_mini = self._zeile(konto, "Mindestbestellung", 2)

        # ---- Assistent ----
        assistent = self._panel(rechts, "ASSISTENT (Sprachbedienung, OpenRouter)")
        self.chat_verlauf = tk.Text(assistent, height=9, bg=BG, fg=TEXT,
                                    font=("Consolas", 8), wrap="word",
                                    insertbackground=Gruen)
        self.chat_verlauf.grid(row=1, column=0, columnspan=3, sticky="nsew",
                               padx=8, pady=4)
        assistent.rowconfigure(1, weight=1)
        assistent.columnconfigure(2, weight=1)

        beispiele = tk.Frame(assistent, bg=PANEL)
        beispiele.grid(row=2, column=0, columnspan=3, sticky="w", padx=6)
        for q in Assistant.BEISPIELFRAGEN[:4]:
            tk.Button(beispiele, text=q.split("%")[0].strip()[:26], command=lambda x=q: self._frage(x),
                      bg="#21262d", fg=Blau, font=("Consolas", 7)).pack(side="left", padx=2, pady=2)

        eingabe = tk.Frame(assistent, bg=PANEL)
        eingabe.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=6)
        self.frage = tk.StringVar()
        self.eingabe = tk.Entry(eingabe, textvariable=self.frage, bg=BG, fg=TEXT,
                               insertbackground=Gruen, font=("Consolas", 9))
        self.eingabe.pack(side="left", fill=tk.X, expand=True)
        self.eingabe.bind("<Return>", lambda e: self._frage_stellen())
        tk.Button(eingabe, text="FRAGEN", command=self._frage_stellen, bg=Gruen,
                  fg="#000", font=("Consolas", 9, "bold")).pack(side="left", padx=4)

        # ---- Protokoll ----
        log_rahmen = tk.Frame(self.root, bg=PANEL, bd=1, relief=tk.RIDGE)
        log_rahmen.pack(fill=tk.X, padx=5, pady=3)
        tk.Label(log_rahmen, text="PROTOKOLL", bg=PANEL, fg=Grau,
                 font=("Consolas", 8, "bold")).pack(anchor="w", padx=8, pady=(4, 0))
        self.log = tk.Text(log_rahmen, height=5, bg=BG, fg=Gruen, font=("Consolas", 8))
        self.log.pack(fill=tk.X, padx=4, pady=4)
        self.log.insert(tk.END, "Befehle: %status% %analyse% %paper% %kosten% %reset%\n")

    # ---------- Hilfsfunktionen ----------
    def _sag(self, text):
        self.log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log.see(tk.END)

    def _chat(self, rolle, text):
        tag = "du" if rolle == "user" else "ia"
        self.chat_verlauf.insert(tk.END, f"{tag}: {text}\n\n")
        self.chat_verlauf.see(tk.END)

    def _frage(self, q):
        self.frage.set(q)
        self._frage_stellen()

    def _frage_stellen(self):
        if self.chat_laeuft:
            return
        q = self.frage.get().strip()
        if not q:
            return
        self.frage.set("")
        self._chat("user", q)
        self.chat_laeuft = True

        # Wichtig: root.after() darf NICHT aus einem Worker-Thread kommen.
        # Der Worker schreibt in eine Queue, der Hauptthread leert sie ab.
        def arbeite():
            try:
                antwort = self.assistent.ask(q)
            except Exception as exc:
                antwort = f"Fehler: {exc}"
            self._chat_warteschlange.put(("antwort", antwort))

        threading.Thread(target=arbeite, daemon=True).start()

    def _chat_entleeren(self):
        while True:
            try:
                art, inhalt = self._chat_warteschlange.get_nowait()
            except queue.Empty:
                break
            if art == "antwort":
                self.chat_laeuft = False
                self._chat("ia", inhalt)
            elif art == "protokoll":
                self._sag(inhalt)
        self.root.after(300, self._chat_entleeren)

    def _paper_tick(self):
        try:
            r = self.paper.tick()
            s = r["signal"]
            if r["result"]:
                self._sag(f"Paper-Fill: {r['result']['side']} {r['result']['qty']} @ {r['result']['fill']}")
            else:
                self._sag(f"Paper-Tick: {s['action']} (Konfidenz {s['confidence']:.0%})")
            self._aktualisiere_bilanz()
        except Exception as exc:
            self._sag(f"Paper-Tick fehlgeschlagen: {exc}")

    def _diagramm_neu(self):
        try:
            k = self.bot.exchange.klines(self.bot.symbol, self.zeitraum.get(), limit=80)
            if k:
                k.sort(key=lambda x: x["start"])
                titel = f"{self.bot.symbol} · {self.zeitraum.get()}Min · Bybit EU · {len(k)} Kerzen"
                self.chart.zeichne(k, titel=titel)
        except Exception as exc:
            self._sag(f"Diagramm: {exc}")

    # ---------- Aktualisierung ----------
    def _aktualisiere_bilanz(self):
        r = self.paper.report()
        self.l_equity.config(text=f"{r['equity']:.4f} USDC")
        self.l_rendite.config(text=f"{r['return_pct']:.2f} %",
                              fg=Gruen if r["return_pct"] >= 0 else Rot)
        self.l_trades.config(text=f"{r['trades']} ({r['wins']} / {r['losses']})")
        self.l_winrate.config(text=f"{r['winrate']} %" if r["winrate"] is not None else "-")
        self.l_gebuehr.config(text=f"{r['fees_paid']:.4f} USDC")
        self.l_dd.config(text=f"{r['max_drawdown_pct']:.2f} %",
                         fg=Rot if r["max_drawdown_pct"] < -1 else Gelb)

    def _aktualisiere(self):
        if not self.laeuft:
            return
        try:
            d = self.bot.analyze()
            self.letzte = d
            m, w = d["market"], d["wallet"]
            # Bybit schreibt Symbole ohne Bindestrich: "ETHUSDC"
            sym = self.bot.symbol
            q = sym[3:] if sym[:3] in ("ETH", "BTC") else sym

            self.l_preis.config(text=f"{m['last']:,.2f} {q}" if m.get("last") else "-")
            self.l_eur.config(text=f"{m['eth_eur']:,.2f} EUR" if m.get("eth_eur") else "-")
            self.l_spread.config(text=f"{m['spread_pct']:.4f} %" if m.get("spread_pct") else "-")
            self.l_volumen.config(text=f"{m['volume_24h']:,.0f} ETH" if m.get("volume_24h") else "-")

            act = d["action"]
            self.l_signal.config(text={"BUY": "KAUFEN", "SELL": "VERKAUFEN"}.get(act, "HALTEN"),
                                 fg=Gruen if act == "BUY" else (Rot if act == "SELL" else Gelb))
            self.l_konf.config(text=f"{d['confidence']:.0%}")
            mtf = d.get("mtf", {})
            self.l_tf.config(text=" / ".join(mtf.get(x, {}).get("action", "-")[:4]
                                             for x in ("5min", "15min", "1h", "4h")))
            self.l_grund.config(text=d.get("reason", "-")[:200])

            rs = self.bot.risk.stats()
            self.l_maxtrade.config(text=f"{rs['max_trade_quote']:.0f} USDC")
            self.l_reserve.config(text=f"{rs['min_reserve_quote']:.0f} USDC")
            self.l_stunde.config(text=f"{rs['trades_last_hour']} / {rs['max_per_hour']}")

            hat_keys = self.bot.exchange.has_keys
            self.l_konto.config(text="ja" if hat_keys else "nein",
                                fg=Gruen if hat_keys else Gelb)
            if hat_keys:
                b = self.bot.exchange.wallet_balance()
                for coin, v in (b.get("coins") or {}).items():
                    if coin == "ETH":
                        self.l_guthaben.config(text=f"{v['equity']:.8f} ETH")
                        break
                else:
                    self.l_guthaben.config(text="0 ETH")
            inst = self.bot.exchange.instrument(self.bot.symbol) or {}
            lot = inst.get("lotSizeFilter", {})
            self.l_mini.config(text=f"{lot.get('minOrderAmt','?')} USDC")

            self._aktualisiere_bilanz()
            self._diagramm_neu()
            self.l_status.config(text=f"{self.bot.exchange.host_name.upper()} · "
                                      f"Paper-Modus · Handlungen: {len(self.bot.trade_history)}",
                                 fg=Grau)
        except Exception as exc:
            self.l_status.config(text=f"Fehler: {exc}", fg=Rot)
        self.root.after(config.GUI_REFRESH_MS, self._aktualisiere)


if __name__ == "__main__":
    root = tk.Tk()
    TradingGUI(root)
    root.mainloop()
