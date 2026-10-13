"""Echter Preis-Feed via CoinGecko (kostenlos, kein API-Key)."""
import requests
from core import logger

COINGECKO = "https://api.coingecko.com/api/v3"
_log = logger.DualLogger()

# CoinGecko drosselt hart (429). Cache ist Pflicht, Backoff ebenso.
_CACHE = {}
_TTL_SECONDS = 300
_BACKOFF_UNTIL = 0.0


class PriceFeed:
    """Holt echte Preise. Ohne Preis kein Trade - das ist die Grundregel."""

    def __init__(self, ttl=_TTL_SECONDS):
        self.ttl = ttl

    def _get(self, path, params):
        """HTTP mit 429-Backoff. Gibt dict oder None zurück."""
        global _BACKOFF_UNTIL
        import time
        if time.time() < _BACKOFF_UNTIL:
            return None
        try:
            r = requests.get(f"{COINGECKO}{path}", params=params, timeout=10)
            if r.status_code == 429:
                _BACKOFF_UNTIL = time.time() + 120
                _log.warning("Preis-Feed: 429 Rate-Limit. 120s Backoff aktiv.")
                return None
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            _log.error(f"Preis-Feed Fehler ({path}): {exc}")
            return None

    def get_price_eur(self, coin_id="ethereum"):
        import time
        cached = _CACHE.get(coin_id)
        if cached and (time.time() - cached["ts"]) < self.ttl:
            return cached["price"]
        data = self._get("/simple/price", {"ids": coin_id, "vs_currencies": "eur"})
        if not data or coin_id not in data:
            return cached["price"] if cached else None
        price = float(data[coin_id]["eur"])
        _CACHE[coin_id] = {"price": price, "ts": time.time()}
        return price

    def get_eth_price_eur(self):
        return self.get_price_eur("ethereum")

    def get_market_snapshot(self):
        """Preis + 24h-Änderung. Fällt auf Cache zurück statt zu crashen."""
        data = self._get("/coins/markets",
                         {"vs_currency": "eur", "ids": "ethereum",
                          "price_change_percentage": "24h"})
        if not data:
            cached = _CACHE.get("ethereum")
            return {"price_eur": cached["price"] if cached else None,
                    "change_24h": None, "high_24h": None, "low_24h": None,
                    "stale": True}
        d = data[0]
        import time
        _CACHE["ethereum"] = {"price": float(d["current_price"]), "ts": time.time()}
        return {
            "price_eur": float(d["current_price"]),
            "change_24h": float(d.get("price_change_percentage_24h") or 0.0),
            "high_24h": float(d["high_24h"]),
            "low_24h": float(d["low_24h"]),
            "stale": False,
        }
