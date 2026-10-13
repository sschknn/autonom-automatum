"""Krypto-Trading-Bot für autonom-automatum.

EHRliche Beschreibung:
Dieser Bot bewertet Marktdaten und bereitet echte Mainnet-Transaktionen vor.
Er ist KEIN Profit-Generator. Mit 0.0004 ETH (~0.91 EUR) ist kein Trading
profitabel möglich - Gebühren fressen jeden Gewinn. Der Bot ist eine
Infrastruktur-Komponente, die auf Kapital und eine Exchange-API wartet.
"""
import os
from core import config, wallet, web3_integration, logger, indicators
from core.price_feed import PriceFeed
from core.risk_manager import RiskManager
from core.strategies import STRATEGIES
from core.bybit_exchange import BybitExchange

_log = logger.DualLogger()

# Mehrere Timeframes - ein Signal ist erst stark, wenn die Timeframes uebereinstimmen.
TIMEFRAMES = [("5", "5min"), ("15", "15min"), ("60", "1h"), ("240", "4h")]


class CryptoTradingBot:
    def __init__(self, strategy="BUY_HOLD", symbol="ETHUSDC", host="eu"):
        self.web3_engine = web3_integration.Web3Engine()
        self.wallet_engine = wallet.WalletEngine()
        self.price_feed = PriceFeed()
        self.exchange = BybitExchange(host)
        # Bybit EU fuehrt unter MiCA KEINE USDT-Paare. Handelbare
        # ETH-Paare: ETHUSDC (beste Liquiditaet) und ETHEUR (Fiat-Quote).
        self.symbol = symbol
        self.eur_symbol = "ETHEUR"
        self.risk = RiskManager()
        self.strategy = strategy
        self.mode = "LIVE_ONLY"
        self.last_decision = None
        self.trade_history = []
        os.makedirs(os.path.join(config.BASE_DIR, "data"), exist_ok=True)

    # ---------- Marktdaten ----------
    def get_eth_eur(self):
        """ETH-Kurs in EUR direkt von Bybit (ETHEUR) - kein Umrechnungsfehler."""
        t = self.exchange.ticker(self.eur_symbol) or {}
        if t.get("lastPrice"):
            return float(t["lastPrice"])
        return self.price_feed.get_eth_price_eur()

    def get_market(self):
        """Bybit ist Primaerquelle (echtes Orderbuch). CoinGecko nur Fallback.

        Achtung Einheiten: last = USDC pro ETH, eth_eur = EUR pro ETH.
        Das sind beides ETH-Kurse - sie werden NICHT multipliziert.
        """
        snap = self.exchange.market_snapshot(self.symbol)
        eur = self.get_eth_eur()
        snap["eth_eur"] = eur
        snap["price_eur"] = eur
        snap["source"] = f"Bybit {self.exchange.host_name.upper()} / {self.symbol}"
        if not snap.get("last"):
            snap["last"] = None
        return snap

    def multi_timeframe(self):
        """Haelt die Timeframes zusammen - vermeidet Ein-Zeitpunkt-Entscheidungen."""
        out = {}
        for iv, name in TIMEFRAMES:
            try:
                out[name] = indicators.analyze(self.exchange.klines(self.symbol, iv, limit=100))
            except Exception as exc:
                out[name] = {"action": "HOLD", "confidence": 0.0, "reason": f"keine Daten ({exc})"}
        return out

    # ---------- Wallet ----------
    def get_wallet_state(self):
        balance = self.web3_engine.get_balance_real()
        tx_cost = self.web3_engine.estimate_tx_cost_eth()
        balance = balance if isinstance(balance, float) else 0.0
        price = self.price_feed.get_eth_price_eur()
        return {
            "address": self.wallet_engine.get_public_address(),
            "balance_eth": balance,
            "balance_eur": round(balance * price, 4) if price else None,
            "tx_cost_eth": tx_cost,
            "target": self.wallet_engine.get_real_target_balance(),
        }

    # ---------- Strategie ----------
    def analyze(self):
        """Multi-Timeframe-Analyse + Risikoprüfung -> Entscheidung."""
        market = self.get_market()
        wallet_state = self.get_wallet_state()
        mtf = self.multi_timeframe()
        strat = STRATEGIES.get(self.strategy, STRATEGIES["BUY_HOLD"])

        if not market.get("last"):
            return {
                "action": "HOLD", "confidence": 0.0,
                "reason": "Kein Marktdaten von Bybit. Keine Entscheidung moeglich.",
                "market": market, "wallet": wallet_state, "strategy": self.strategy,
                "mtf": mtf,
            }

        # Timeframes gewichten: 4h/1h sind aussagekraeftiger als 5/15min
        weights = {"5min": 0.10, "15min": 0.20, "1h": 0.35, "4h": 0.35}
        score, votes, detail = 0.0, [], []
        for name, w in weights.items():
            s = mtf.get(name, {})
            act, conf = s.get("action", "HOLD"), s.get("confidence", 0.0)
            if act == "BUY":
                score += w * conf
            elif act == "SELL":
                score -= w * conf
            else:
                score += 0.0
            votes.append(act)
            detail.append(f"{name}:{act}({conf:.0%})")

        agree = len(set(votes)) == 1
        if agree and votes[0] != "HOLD":
            action = votes[0]
            confidence = min(0.95, 0.5 + abs(score))
        else:
            action, confidence = "HOLD", 0.4
            if not agree:
                confidence = 0.3   # widerspruechliche Timeframes = schwaches Signal

        balance = wallet_state["balance_eth"]
        tx_cost = wallet_state["tx_cost_eth"] or 0.0
        affordable = self.risk.max_affordable(balance, tx_cost)
        ok, why = self.risk.can_trade(
            min(strat["max_eth"], affordable) or 0.000001, balance, tx_cost)

        reasons = detail + [mtf.get("1h", {}).get("reason", "")[:80]]
        if market.get("spread_pct") is not None:
            reasons.append(f"Spread {market['spread_pct']:.4f}%")
        if not agree:
            reasons.append("Timeframes uneinheitlich -> kein Trade")

        if not ok:
            action, reasons = "HOLD", [f"Risiko-Block: {why}"] + reasons

        return {
            "action": action, "confidence": round(confidence, 2),
            "reason": " | ".join([r for r in reasons if r]),
            "amount_eth": round(affordable, 8), "risk_ok": ok, "risk_reason": why,
            "market": market, "wallet": wallet_state, "strategy": self.strategy,
            "mtf": mtf,
        }

    # ---------- Ausfuehrung ----------
    def execute(self, destination=None, amount_eth=None, dry_run=True, use_exchange=True):
        """Order ausfuehren.

        use_exchange=True  -> echte Bybit-Spot-Order (benoetigt API-Keys)
        use_exchange=False -> On-Chain-ETH-Transfer ueber Alchemy (braucht Gas)
        dry_run=True       -> nur berechnen, nicht senden (Default)
        """
        decision = self.analyze()
        if decision["action"] == "HOLD":
            return {"status": "HOLD", "message": decision["reason"], **decision}

        price = decision["market"].get("last")
        amt_eth = amount_eth if amount_eth is not None else decision["amount_eth"]

        if use_exchange:
            if not price:
                return {"status": "ERROR", "message": "Kein Preis fuer Umrechnung.", **decision}
            qty = round(amt_eth / price, 6)
            if qty <= 0:
                return {"status": "ERROR", "message": "Betrag zu klein fuer Bybit (min. Lot).", **decision}
            order_type = "Limit" if price else "Market"
            result = self.exchange.place_order(
                self.symbol, decision["action"], qty,
                order_type=order_type,
                price=(round(price * 1.001, 2) if decision["action"] == "Buy"
                       else round(price * 0.999, 2)) if order_type == "Limit" else None,
                dry_run=dry_run)
        else:
            if not destination:
                return {"status": "ERROR", "message": "Keine Zieladresse fuer On-Chain-Transfer.", **decision}
            result = self.web3_engine.send_transaction(destination, amt_eth, dry_run=dry_run)

        result["decision"] = decision["action"]
        result["venue"] = f"Bybit {self.exchange.host_name.upper()}" if use_exchange else "Alchemy Mainnet"
        result["dry_run"] = dry_run
        result["reason"] = decision["reason"]
        if result.get("retCode") == 0 and not dry_run:
            self.risk.record_trade(decision["action"], amt_eth)
            self.trade_history.append(result)
        self.last_decision = decision
        return result

    def status(self):
        market = self.get_market()
        wallet_state = self.get_wallet_state()
        keys_ok = self.exchange.config_info().get("ok", False)
        return {
            "mode": self.mode,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "venue": f"Bybit {self.exchange.host_name.upper()}",
            "exchange_keys": keys_ok,
            "strategies_available": list(STRATEGIES.keys()),
            "market": market,
            "wallet": wallet_state,
            "risk": self.risk.stats(),
            "trades_executed": len(self.trade_history),
            "web3_ready": self.web3_engine.is_ready(),
            # Realistisch: Grid/Scalping braucht mindestens ~0.01 ETH (~25 USD) Reserve
            "profitable_possible": bool(wallet_state["balance_eth"] >= 0.01),
        }
