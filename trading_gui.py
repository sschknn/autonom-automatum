#!/usr/bin/env python3
"""GUI fuer den Krypto-Trading-Bot (autonom-automatum) mit Bybit-EU-Anbindung."""
import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from core.trading_bot import CryptoTradingBot
from core.strategies import STRATEGIES

BG, PANEL, FG = "#0d1117", "#161b22", "#e6edf3"
GREEN, RED, YELLOW, GREY, BLUE = "#00ff88", "#ff5555", "#ffcc00", "#8b949e", "#58a6ff"

SYMBOLS = ["ETHUSDC", "ETHEUR", "ETHPLN", "BTCUSDC", "BTCEUR"]


class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AUTONOM-AUTOMATUM - Trading Bot (Bybit EU)")
        self.root.geometry("880x660")
        self.root.configure(bg=BG)
        self.bot = CryptoTradingBot()
        self.running = True
        self.last = None
        self._build()
        self._say("Starte. Lade Bybit-EU-Marktdaten...")
        self._refresh()

    # ---------- UI-Bausteine (nur grid innerhalb von Panels) ----------
    def _panel(self, parent, title):
        f = tk.Frame(parent, bg=PANEL, bd=1, relief=tk.RIDGE)
        f.pack(fill=tk.BOTH, expand=True, padx=6, pady=3)
        tk.Label(f, text=title, bg=PANEL, fg=GREY,
                 font=("Consolas", 9, "bold")).grid(row=0, column=0, columnspan=2,
                                                    sticky="w", padx=8, pady=(6, 2))
        f.columnconfigure(0, weight=1)
        return f

    def _row(self, parent, label, r, default="-"):
        tk.Label(parent, text=label, bg=PANEL, fg=FG,
                 font=("Consolas", 9)).grid(row=r + 1, column=0, sticky="w", padx=8)
        lbl = tk.Label(parent, text=default, bg=PANEL, fg=GREEN, font=("Consolas", 9, "bold"))
        lbl.grid(row=r + 1, column=1, sticky="e", padx=8)
        return lbl

    def _build(self):
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill=tk.X, padx=8, pady=(8, 0))
        tk.Label(head, text="AUTONOM-AUTOMATUM", bg=BG, fg=GREEN,
                 font=("Consolas", 15, "bold")).pack(side="left")
        self.lbl_conn = tk.Label(head, text="connecting...", bg=BG, fg=GREY, font=("Consolas", 9))
        self.lbl_conn.pack(side="right")

        left = tk.Frame(self.root, bg=BG)
        left.pack(side="left", fill=tk.BOTH, expand=True)
        right = tk.Frame(self.root, bg=BG)
        right.pack(side="left", fill=tk.BOTH, expand=True)

        m = self._panel(left, "MARKT - Bybit EU (live)")
        self.l_price = self._row(m, "ETH (USDC)", 0)
        self.l_etheur = self._row(m, "ETH (EUR)", 1)
        self.l_spread = self._row(m, "Spread", 2)
        self.l_vol = self._row(m, "24h Volumen", 3)
        self.l_src = self._row(m, "Quelle", 4)

        w = self._panel(left, "WALLET")
        self.l_addr = self._row(w, "On-Chain", 0)
        self.l_bal = self._row(w, "Guthaben", 1)
        self.l_eur = self._row(w, "Wert EUR", 2)
        self.l_gas = self._row(w, "TX-Kosten", 3)
        self.l_keys = self._row(w, "Exchange-Keys", 4)

        d = self._panel(right, "DECISION (Multi-Timeframe)")
        self.l_action = self._row(d, "Aktion", 0, "HOLD")
        self.l_conf = self._row(d, "Konfidenz", 1)
        self.l_tf = self._row(d, "5m/15m/1h/4h", 2)
        self.l_reason = tk.Label(d, text="-", bg=PANEL, fg=FG, font=("Consolas", 8),
                                 wraplength=360, justify="left")
        self.l_reason.grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        r = self._panel(right, "RISIKO-LIMITS")
        self.l_maxtrade = self._row(r, "Max. Trade", 0)
        self.l_reserve = self._row(r, "Reserve", 1)
        self.l_perhour = self._row(r, "Trades/Stunde", 2)

        ctrl = tk.Frame(self.root, bg=BG)
        ctrl.pack(fill=tk.X, padx=6, pady=5)
        tk.Label(ctrl, text="Strategie:", bg=BG, fg=FG, font=("Consolas", 9)).pack(side="left")
        self.strategy = tk.StringVar(value="BUY_HOLD")
        ttk.Combobox(ctrl, textvariable=self.strategy, values=list(STRATEGIES.keys()),
                     state="readonly", width=14).pack(side="left", padx=3)
        self.symbol = tk.StringVar(value="ETHUSDC")
        ttk.Combobox(ctrl, textvariable=self.symbol, state="readonly",
                     width=9, values=SYMBOLS).pack(side="left", padx=3)
        tk.Button(ctrl, text="ANALYSE", command=self._analyze, bg=GREEN, fg="#000",
                  font=("Consolas", 9, "bold")).pack(side="left", padx=3)
        tk.Button(ctrl, text="DRY-RUN", command=self._dry_run, bg=YELLOW, fg="#000",
                  font=("Consolas", 9, "bold")).pack(side="left", padx=3)
        self.btn_send = tk.Button(ctrl, text="LIVE ORDER", command=self._live_send,
                                  bg=RED, fg="#fff", font=("Consolas", 9, "bold"),
                                  state=tk.DISABLED)
        self.btn_send.pack(side="left", padx=3)
        tk.Button(ctrl, text="STOP", command=self._stop, bg=GREY, fg="#000",
                  font=("Consolas", 9)).pack(side="left", padx=3)
        tk.Button(ctrl, text="API-KEYS", command=self._keys_dialog, bg=PANEL,
                  fg=BLUE, font=("Consolas", 9)).pack(side="right", padx=3)

        lg = tk.Frame(self.root, bg=PANEL, bd=1, relief=tk.RIDGE)
        lg.pack(fill=tk.BOTH, expand=True, padx=6, pady=3)
        self.log = tk.Text(lg, height=7, bg=BG, fg=GREEN, font=("Consolas", 8),
                           insertbackground=GREEN, wrap="word")
        self.log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _say(self, msg):
        import time
        self.log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log.see(tk.END)

    # ---------- Aktionen ----------
    def _apply_symbol(self):
        self.bot.symbol = self.symbol.get()
        self.bot.eur_symbol = "ETHEUR"

    def _analyze(self):
        self._apply_symbol()
        self.bot.strategy = self.strategy.get()
        self._say(f"Analysiere {self.symbol.get()} mit Strategie {self.strategy.get()}...")
        try:
            self._apply(self.bot.analyze())
        except Exception as exc:
            self._say(f"Analyse-Fehler: {exc}")

    def _dry_run(self):
        self._apply_symbol()
        self._say("Erstelle echte Bybit-Order (dry_run=True -> wird NICHT gesendet)...")
        r = self.bot.execute(dry_run=True, use_exchange=True)
        if r.get("status") == "DRY_RUN":
            self._say(f"DRY-RUN OK: {r['side']} {r['qty']} {r['symbol']} @ {r['est_price']} "
                      f"= {r['est_quote']} (Gebuehr ~{r['est_fee']})")
            if self.bot.exchange.has_keys:
                self.btn_send.config(state=tk.NORMAL)
            else:
                self._say("Fuer LIVE fehlen API-Keys -> Button 'API-KEYS'.")
        else:
            self._say(f"{r.get('status')}: {r.get('message') or r.get('retMsg','')}")

    def _live_send(self):
        amt = self.last.get("amount_usdc", 0) if self.last else 0
        if not messagebox.askyesno(
                "LIVE-ORDER bestaetigen",
                f"ACHTUNG: Echte, nicht umkehrbare Order auf Bybit EU.\n\n"
                f"Paar:   {self.symbol.get()}\n"
                f"Aktion: {self.last.get('action') if self.last else '?'}\n"
                f"Wert:   {amt:.2f} USDC\n\nFortfahren?"):
            self._say("Abgebrochen.")
            return
        self._say(">>> LIVE: sende echte Order an Bybit EU ...")
        price = self.last["market"]["last"]
        qty = round(amt / price, 6)
        r = self.bot.exchange.place_order(self.symbol.get(), self.last["action"],
                                          qty, order_type="Limit",
                                          price=round(price * (1.001 if self.last["action"] == "Buy" else 0.999), 2),
                                          dry_run=False)
        self._say(f"LIVE -> retCode={r.get('retCode')} {r.get('retMsg')} "
                  f"orderId={r.get('result',{}).get('orderId')}")

    def _keys_dialog(self):
        from core.bybit_exchange import BybitExchange
        dlg = tk.Toplevel(self.root)
        dlg.title("Bybit API-Keys")
        dlg.configure(bg=PANEL)
        tk.Label(dlg, text="Keys liegen in wallet/bybit_keys.json (in .gitignore).",
                 bg=PANEL, fg=FG, font=("Consolas", 9)).grid(row=0, column=0, columnspan=2, padx=10, pady=8)
        tk.Label(dlg, text="API Key:", bg=PANEL, fg=FG).grid(row=1, column=0, sticky="w", padx=10)
        e1 = tk.Entry(dlg, width=52, bg=BG, fg=FG, insertbackground=GREEN, font=("Consolas", 9))
        e1.grid(row=1, column=1, padx=10, pady=4)
        tk.Label(dlg, text="API Secret:", bg=PANEL, fg=FG).grid(row=2, column=0, sticky="w", padx=10)
        e2 = tk.Entry(dlg, width=52, bg=BG, fg=FG, insertbackground=GREEN, font=("Consolas", 9),
                      show="*")
        e2.grid(row=2, column=1, padx=10, pady=4)

        def save():
            if not e1.get().strip() or not e2.get().strip():
                messagebox.showwarning("Fehlt", "Key und Secret werden beide benoetigt.")
                return
            BybitExchange("eu").save_keys(e1.get().strip(), e2.get().strip())
            self.bot.exchange = BybitExchange("eu")
            self._say(f"Keys gespeichert. Teste Verbindung...")
            ci = self.bot.exchange.config_info()
            self._say(f"Key-Test: ok={ci.get('ok')} {ci.get('retMsg', ci.get('reason',''))}")
            dlg.destroy()

        tk.Button(dlg, text="SPEICHERN + TESTEN", command=save, bg=GREEN, fg="#000",
                  font=("Consolas", 9, "bold")).grid(row=3, column=0, columnspan=2, pady=10)

    def _stop(self):
        self.running = False
        self._say("Bot gestoppt.")

    # ---------- Anzeige ----------
    def _apply(self, d):
        m, wl = d.get("market", {}), d.get("wallet", {})
        quote = self.symbol.get().replace("ETH", "").replace("BTC", "") or "USDC"
        self.l_price.config(text=f"{m['last']:,.2f} {quote}" if m.get("last") else "-")
        self.l_etheur.config(text=f"{m['eth_eur']:,.2f} EUR" if m.get("eth_eur") else "-")
        self.l_spread.config(text=f"{m['spread_pct']:.4f}%" if m.get("spread_pct") is not None else "-",
                             fg=GREEN if (m.get("spread_pct") or 1) < 0.01 else YELLOW)
        self.l_vol.config(text=f"{m['volume_24h']:,.1f}" if m.get("volume_24h") else "-")
        self.l_src.config(text=m.get("source", "-"))

        self.l_addr.config(text=(wl.get("address") or "-")[:18] + "...")
        self.l_bal.config(text=f"{wl.get('balance_eth', 0):.8f} ETH")
        self.l_eur.config(text=f"{wl.get('balance_eur'):,.2f} EUR" if wl.get("balance_eur") else "-")
        self.l_gas.config(text=f"{(wl.get('tx_cost_eth') or 0):.8f} ETH")
        has_keys = self.bot.exchange.has_keys
        self.l_keys.config(text="hinterlegt" if has_keys else "FEHLT (nur Marktdaten)",
                           fg=GREEN if has_keys else YELLOW)

        act = d.get("action", "HOLD")
        self.l_action.config(text=act, fg=GREEN if act == "BUY" else (RED if act == "SELL" else YELLOW))
        self.l_conf.config(text=f"{d.get('confidence', 0):.0%}")
        mtf = d.get("mtf", {})
        self.l_tf.config(text=" / ".join(mtf.get(k, {}).get("action", "-")[:4]
                                         for k in ("5min", "15min", "1h", "4h")))
        self.l_reason.config(text=d.get("reason", "-")[:220])

        rs = self.bot.risk.stats()
        self.l_maxtrade.config(text=f"{rs['max_trade_quote']:.0f} USDC")
        self.l_reserve.config(text=f"{rs['min_reserve_quote']:.0f} USDC")
        self.l_perhour.config(text=f"{rs['trades_last_hour']}/{rs['max_per_hour']}")

        # Betrag in USDC fuer die Order-Groesse
        eur = m.get("eth_eur")
        if eur and wl.get("balance_eth"):
            d["amount_usdc"] = min(self.bot.risk.max_trade_quote,
                                   max(0.0, wl["balance_eth"] * m["last"] - self.bot.risk.min_reserve_quote))
        self.last = d

    def _refresh(self):
        if self.running:
            try:
                self._apply(self.bot.analyze())
                self.lbl_conn.config(
                    text=f"{self.bot.exchange.host_name.upper()} | trades {len(self.bot.trade_history)} "
                         f"| profitabel: {self.bot.status()['profitable_possible']}",
                    fg=GREY)
            except Exception as exc:
                self.lbl_conn.config(text=f"error: {exc}", fg=RED)
            self.root.after(8000, self._refresh)


if __name__ == "__main__":
    root = tk.Tk()
    TradingBotGUI(root)
    root.mainloop()
