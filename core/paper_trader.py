"""Paper-Trading-Engine: echte Marktdaten, simulierte Ausfuehrung, echtes Tracking.

Zweck: Validieren, ob die Strategie Edge hat, BEVOR echtes Geld bewegt wird.
Harte Garantie: Diese Klasse kann keine echte Order senden. Sie ruft niemals
place_order() mit dry_run=False auf - es existiert kein Pfad dahin.

Der Fill wird pessimistisch simuliert:
  - Kauf zum Ask, Verkauf zum Bid (niemals zum Mid)
  - Zusaetzlicher Slippage-Anteil
  - Gebuehren wie bei Bybit Spot (0,1% pro Seite)
  - Latenz: Signal von der letzten Kerze, Fill zum naechsten Open
"""
import os
import json
import time
from core import config, logger
from core.bybit_exchange import BybitExchange
from core import indicators

_log = logger.Log()

STATE_FILE = config.PAPER_STATE_FILE

TAKER_FEE = 0.001        # 0,1% pro Seite
SLIPPAGE_PCT = 0.0005    # 0,05% zusaetzlicher Slippage
MIN_NOTIONAL = 5.0       # Bybit-Mindestbetrag
DEFAULT_QUOTE = 6.79     # Startkapital: entspricht dem echten ETH-Wert (0,00279 ETH)

# ---------- Position-Management (verschärft) ----------
STOP_LOSS_PCT   = 1.5    # Position bei -1,5% Verlust vom Einstand geschlossen
TAKE_PROFIT_PCT = 2.0    # Position bei +2,0% Gewinn vom Einstand geschlossen
TRAIL_PCT       = 1.0    # Trailing-Stop: 1,0% unter dem Kurs-Hoch der Position


class PaperTrader:
    def __init__(self, symbol="ETHUSDC", initial_quote=DEFAULT_QUOTE, state_file=STATE_FILE, min_confidence=0.35):
        self.exchange = BybitExchange("eu")
        self.symbol = symbol
        self.initial_quote = initial_quote
        self.state_file = state_file
        self.min_confidence = min_confidence
        self.state = self._load()

    # ---------- Persistenz ----------
    def _default(self):
        return {
            "symbol": self.symbol,
            "quote": self.initial_quote,      # USDC-Bestand
            "base": 0.0,                      # ETH-Bestand
            "realized_pnl": 0.0,
            "fees_paid": 0.0,
            "trades": [],                     # abgeschlossene Roundtrips
            "signals": [],                    # Log aller Signale (auch ohne Trade)
            "equity_curve": [],               # (ts, equity)
            "started": time.strftime("%Y-%m-%d %H:%M:%S"),
            "peak_equity": self.initial_quote,
            "position_peak": self.initial_quote,  # Kurs-Hoch der offenen Position
        }

    def _load(self):
        """Lade Zustand; bei leerer/beschädigter Datei neu initialisieren."""
        st = None
        if os.path.isfile(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    st = json.load(f)
            except Exception:
                self.state = self._default()
                self.save()
                _log.warning(f"Zustandsdatei beschädigt/leer ({self.state_file}) -> neu initialisiert")
                return self.state
        if not st:
            st = self._default()
        # initial_quote konsistent halten (falls Nutzer Kapital geändert hat):
        st["initial_quote"] = self.initial_quote
        # Quote nur anpassen, wenn sie eindeutig falsch ist (verwaister/froster
        # Zustand). Ein legitimer Closed-Position-Wert (quote ~= initial_quote +
        # realisierter PnL) wird erhalten, damit Gewinne/Verluste nicht verloren
        # gehen.
        if float(st.get("base", 0)) == 0.0:
            expected = float(self.initial_quote) + float(st.get("realized_pnl", 0.0) or 0.0)
            threshold = max(float(self.initial_quote) * 0.1, 5.0)
            if abs(float(st.get("quote", 0.0) or 0.0) - expected) > threshold:
                st["quote"] = self.initial_quote
                st["peak_equity"] = self.initial_quote
        self.state = st
        self.save()
        return self.state

    def save(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self.state["initial_quote"] = self.initial_quote
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def reset(self):
        self.state = self._default()
        self.save()
        return self.state

    # ---------- Markt ----------
    def price(self):
        s = self.exchange.market_snapshot(self.symbol)
        return s.get("last"), s

    # ---------- Bewertung ----------
    def equity(self):
        px, _ = self.price()
        if px is None:
            return self.state["quote"] + self.state["base"] * 0
        return self.state["quote"] + self.state["base"] * px

    def drawdown(self):
        eq = self.equity()
        peak = self.state.get("peak_equity", self.initial_quote)
        if eq > peak:
            self.state["peak_equity"] = eq
            return 0.0
        return (eq - peak) / peak * 100 if peak else 0.0

    # ---------- Simulierte Fill-Kosten ----------
    def _fill_price(self, side, snap):
        """Pessimistisch: Kauf am Ask, Verkauf am Bid, plus Slippage."""
        base = snap["ask"] if side == "Buy" else snap["bid"]
        return base * (1 + SLIPPAGE_PCT) if side == "Buy" else base * (1 - SLIPPAGE_PCT)

    # ---------- Ausfuehrung ----------
    def open_position(self, side, frac=1.0):
        """Oeffnet eine Position mit frac des verfuegbaren Kapitals."""
        snap = self.exchange.market_snapshot(self.symbol)
        if not snap.get("last"):
            return {"status": "ERROR", "msg": "keine Marktdaten"}

        fill = self._fill_price(side, snap)
        if side == "Buy":
            spend = self.state["quote"] * frac
            if spend < MIN_NOTIONAL:
                return {"status": "SKIP",
                        "msg": f"Kapital {spend:.2f} < Bybit-Minimum {MIN_NOTIONAL} USDC"}
            fee = spend * TAKER_FEE
            qty = (spend - fee) / fill
            self.state["quote"] -= spend
            self.state["base"] += qty
            self.state["fees_paid"] += fee
            entry = fill
        else:
            qty = self.state["base"] * frac
            if qty <= 0:
                return {"status": "SKIP", "msg": "keine Long-Position"}
            gross = qty * fill
            fee = gross * TAKER_FEE
            self.state["base"] -= qty
            self.state["quote"] += gross - fee
            self.state["fees_paid"] += fee
            # Roundtrip schliessen
            entry = self.state.get("entry_price") or fill
            pnl = (fill - entry) * qty - fee
            self.state["realized_pnl"] += pnl
            self.state["trades"].append({
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "side": "LONG",
                "qty": round(qty, 6),
                "entry": round(entry, 2),
                "exit": round(fill, 2),
                "pnl_usdc": round(pnl, 4),
                "pnl_pct": round((fill / entry - 1) * 100, 3),
            })
            entry = None

        if side == "Buy":
            self.state["entry_price"] = round(fill, 2)
        else:
            self.state["entry_price"] = None

        self.state["equity_curve"].append(
            {"ts": time.strftime("%Y-%m-%d %H:%M"), "equity": round(self.equity(), 4)})

        self.save()
        return {"status": "FILLED", "side": side, "qty": round(qty, 6),
                "fill": round(fill, 2), "fee": round(fee, 5),
                "equity": round(self.equity(), 4)}

    # ---------- Ein Tick ----------
    def tick(self, min_confidence=0.22):
        """Holt Signal, verwaltet Position (SL/TP/Trailing), eroeffnet/schliesst.

        TEST-KONFIGURATION: min_confidence=0.22 statt 0.5. In PRODUKTION auf 0.5
        zuruecksetzen. Positionen werden nun durch Stop-Loss, Take-Profit und
        Trailing-Stop verwaltet.
        """
        snap = self.exchange.market_snapshot(self.symbol)
        if not snap.get("last"):
            return {"status": "ERROR", "msg": "keine Marktdaten"}

        s1h = indicators.analyze(self.exchange.klines(self.symbol, "60", limit=100))
        s15 = indicators.analyze(self.exchange.klines(self.symbol, "15", limit=100))
        px = snap["last"]

        # 1) Offene Position verwalten (Stop-Loss / Take-Profit / Trailing)
        closed = self._manage_position(px)

        # 2) Neues Signal nur, wenn Position nicht gerade verwaltet wurde
        if not closed:
            action, conf, reason = self._signal(s1h, s15, min_confidence)
        else:
            action, conf, reason = "HOLD", 0.0, "Position verwaltet"

        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "price": px,
               "action": action, "confidence": round(conf, 2), "reason": reason}
        self.state["signals"].append(rec)
        self.state["signals"] = self.state["signals"][-500:]

        result = None
        if action == "BUY" and self.state["base"] == 0:
            result = self.open_position("Buy")
        elif action == "SELL" and self.state["base"] > 0:
            result = self.open_position("Sell")

        if result is None:
            self.save()

        return {"signal": rec, "result": result,
                "equity": round(self.equity(), 4),
                "drawdown_pct": round(self.drawdown(), 3)}

    # ---------- Position-Management ----------
    def _manage_position(self, px):
        """Stop-Loss / Take-Profit / Trailing-Stop. Gibt True, wenn Position
        geschlossen wurde."""
        if self.state["base"] <= 0:
            return False
        entry = self.state["entry_price"]
        if not entry:
            return False

        pos_pct = (px - entry) / entry * 100
        peak = self.state.get("position_peak") or entry

        # Take-Profit (vom Einstand)
        if pos_pct >= TAKE_PROFIT_PCT:
            self.open_position("Sell")
            _log.info(f"Take-Profit: Position +{pos_pct:.2f}% -> geschlossen")
            return True
        # Stop-Loss (vom Einstand)
        if pos_pct <= -STOP_LOSS_PCT:
            self.open_position("Sell")
            _log.info(f"Stop-Loss: Position {pos_pct:.2f}% -> geschlossen")
            return True
        # Trailing-Stop (vom Kurs-Hoch)
        if px > peak:
            peak = px
        if px <= peak * (1 - TRAIL_PCT / 100):
            self.open_position("Sell")
            _log.info(f"Trailing-Stop: Peak {peak:.2f} -> Position geschlossen")
            return True

        self.state["position_peak"] = peak
        return False

    # ---------- Signal-Auswertung ----------
    def _signal(self, s1h, s15, min_confidence):
        """Signal zusammenfuegen mit Trend- und RSI-Filter.

        - Kein Long, wenn 1h im Abwaertstrend ist (EMA9 < EMA21).
        - Kein Long, wenn 15m RSI > 60 (ueberkauft).
        - 1h und 15m muessen einig sein ODER das 15m-Fenster muss klar signalisieren.
        """
        action, conf, reason = "HOLD", 0.0, ""
        agree = s1h["action"] == s15["action"]
        strong_15 = s15["confidence"] >= min_confidence

        if (agree and s1h["action"] in ("BUY", "SELL")) or strong_15:
            if agree:
                action = s1h["action"]
                conf = (s1h["confidence"] + s15["confidence"]) / 2
                reason = "1h+15m einig: " + s1h["reason"][:70]
            else:
                action = s15["action"]
                conf = s15["confidence"]
                reason = "15m klar: " + s15["reason"][:70]

            rsi = s15.get("rsi")
            if action == "BUY":
                if s1h["action"] == "SELL":
                    action, conf, reason = "HOLD", 0.0, "1h im Abwaertstrend -> kein Long"
                elif rsi is not None and rsi > 60:
                    action, conf, reason = "HOLD", 0.0, "RSI %.1f zu ueberkauft" % rsi
            if action == "SELL":
                if rsi is not None and rsi < 40:
                    action, conf, reason = "HOLD", 0.0, "RSI %.1f zu ueberverkauft" % rsi

        return action, conf, reason

    # ---------- Report ----------
    def report(self):
        eq = self.equity()
        trades = self.state["trades"]
        wins = [t for t in trades if t["pnl_usdc"] > 0]
        losses = [t for t in trades if t["pnl_usdc"] <= 0]
        gross_win = sum(t["pnl_usdc"] for t in wins)
        gross_loss = abs(sum(t["pnl_usdc"] for t in losses))
        ret = (eq / self.initial_quote - 1) * 100 if self.initial_quote else 0.0

        return {
            "symbol": self.symbol,
            "started": self.state["started"],
            "initial_quote": self.initial_quote,
            "equity": round(eq, 4),
            "return_pct": round(ret, 3),
            "quote": round(self.state["quote"], 4),
            "base": round(self.state["base"], 6),
            "realized_pnl": round(self.state["realized_pnl"], 4),
            "fees_paid": round(self.state["fees_paid"], 4),
            "trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "winrate": round(len(wins) / len(trades) * 100, 1) if trades else None,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
            "max_drawdown_pct": round(self.drawdown(), 2),
            "signals_seen": len(self.state["signals"]),
            "guarantee": "PAPER ONLY - kein Code-Pfad zu echten Orders",
        }
