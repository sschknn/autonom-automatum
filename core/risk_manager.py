"""Risiko-Manager: Limits, die den Bot daran hindern, alles zu verlieren."""
import time
from core import logger, config

_log = logger.DualLogger()


class RiskManager:
    def __init__(self, max_trade_eth=0.0002, daily_loss_limit_eth=0.001,
                 min_reserve_eth=0.00005, max_trades_per_hour=5,
                 max_trade_quote=25.0, min_reserve_quote=10.0):
        # On-Chain-Limits (Alchemy/ETH)
        self.max_trade_eth = max_trade_eth
        self.daily_loss_limit_eth = daily_loss_limit_eth
        self.min_reserve_eth = min_reserve_eth      # Gas-Reserve, nie anfassen
        # Exchange-Limits (Bybit, in Quote-Waehrung = USDC)
        self.max_trade_quote = max_trade_quote
        self.min_reserve_quote = min_reserve_quote
        self.max_trades_per_hour = max_trades_per_hour
        self.trades = []   # [{"ts": float, "amount": float, "action": str}]

    def can_trade(self, amount_eth, balance_eth, tx_cost_eth):
        """Gibt (bool, reason) zurück. Jede Ablehnung wird protokolliert."""
        if amount_eth <= 0:
            return False, "Betrag <= 0"
        if amount_eth > self.max_trade_eth:
            return False, f"Betrag {amount_eth:.6f} > Limit {self.max_trade_eth:.6f} ETH"
        spendable = balance_eth - self.min_reserve_eth - tx_cost_eth
        if spendable < amount_eth:
            # Anzeigewert nie negativ: wer unter der Reserve liegt, hat 0 verfügbar,
            # nicht "-0,000051 ETH verfügbar".
            return False, (f"Nicht genug ETH: verfügbar {max(0.0, spendable):.6f} "
                           f"(Balance {balance_eth:.6f} - Reserve {self.min_reserve_eth:.6f} - Gas {tx_cost_eth:.6f})")
        hour_ago = time.time() - 3600
        self.trades = [t for t in self.trades if t["ts"] > hour_ago]
        if len(self.trades) >= self.max_trades_per_hour:
            return False, f"Max Trades/Stunde erreicht ({self.max_trades_per_hour})"
        return True, "OK"

    def max_affordable(self, balance_eth, tx_cost_eth):
        return max(0.0, min(self.max_trade_eth,
                            balance_eth - self.min_reserve_eth - tx_cost_eth))

    def can_trade_quote(self, notional_quote, balance_quote):
        """Exchange-Check in Quote-Waehrung (USDC)."""
        if notional_quote <= 0:
            return False, "Notional <= 0"
        if notional_quote > self.max_trade_quote:
            return False, f"Notional {notional_quote:.2f} > Limit {self.max_trade_quote:.2f} USDC"
        available = balance_quote - self.min_reserve_quote
        if available < notional_quote:
            return False, (f"Nicht genug USDC: verfuegbar {available:.2f} "
                           f"(Balance {balance_quote:.2f} - Reserve {self.min_reserve_quote:.2f})")
        hour_ago = time.time() - 3600
        self.trades = [t for t in self.trades if t["ts"] > hour_ago]
        if len(self.trades) >= self.max_trades_per_hour:
            return False, f"Max Trades/Stunde erreicht ({self.max_trades_per_hour})"
        return True, "OK"

    def record_trade(self, action, amount_eth):
        self.trades.append({"ts": time.time(), "action": action, "amount": amount_eth})

    def stats(self):
        hour_ago = time.time() - 3600
        recent = [t for t in self.trades if t["ts"] > hour_ago]
        return {
            "trades_last_hour": len(recent),
            "max_per_hour": self.max_trades_per_hour,
            "max_trade_eth": self.max_trade_eth,
            "min_reserve_eth": self.min_reserve_eth,
            "max_trade_quote": self.max_trade_quote,
            "min_reserve_quote": self.min_reserve_quote,
        }
