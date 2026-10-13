"""Bybit-EU-Exchange-Connector (V5 API, Spot only).

Wichtig zur Rechtslage:
- Binance ist seit 01.07.2026 ohne MiCA-Lizenz fuer EU-Buerger gesperrt.
- Bybit EU GmbH (FMA Oesterreich) ist MiCA-lizenziert -> nur api.bybit.eu nutzen.
- Futures/Derivate sind fuer Bybit EU nicht lizenziert. Dieser Connector
  handelt daher ausschliesslich SPOT.

Sicherheit:
- Ohne Keys sind nur oeffentliche Marktdaten moeglich (read-only).
- Jede Order-Methode hat dry_run=True als Default.
"""
import os
import json
import time
import hmac
import hashlib
import requests
from core import config, logger

_log = logger.DualLogger()

KEYS_FILE = os.path.join(config.BASE_DIR, "wallet", "bybit_keys.json")

# Bybit EU = MiCA-lizenzierte Entity. Die globale Domain ist fuer EU nicht zulaessig.
HOSTS = {
    "eu": "https://api.bybit.eu",
    "global": "https://api.bybit.com",
    "testnet": "https://api-testnet.bybit.eu",
}
DEFAULT_HOST = "eu"


class BybitExchange:
    """Bybit V5 REST Client. Signierung nach Bybit-Spec."""

    def __init__(self, host=DEFAULT_HOST, keys_file=KEYS_FILE, recv_window=5000):
        self.base = HOSTS.get(host, HOSTS[DEFAULT_HOST])
        self.host_name = host
        self.recv_window = recv_window
        self.session = requests.Session()
        self.keys = self._load_keys(keys_file)
        self.has_keys = bool(self.keys.get("api_key") and self.keys.get("api_secret"))

    # ---------- Keys ----------
    @staticmethod
    def _load_keys(path):
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_keys(self, api_key, api_secret, host=DEFAULT_HOST):
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump({"api_key": api_key, "api_secret": api_secret, "host": host}, f, indent=2)
        self.keys = {"api_key": api_key, "api_secret": api_secret, "host": host}
        self.has_keys = True

    # ---------- HTTP ----------
    def _sign(self, params):
        """Bybit V5: signiert timestamp + apiKey + recvWindow + querystring."""
        ts = str(int(time.time() * 1000))
        recv = str(self.recv_window)
        # Bybit verlangt die Parameter alphabetisch sortiert
        query = "&".join(f"{k}={params[k]}" for k in sorted(params))
        payload = ts + self.keys["api_key"] + recv + query
        sig = hmac.new(self.keys["api_secret"].encode("utf-8"),
                       payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "X-BAPI-API-KEY": self.keys["api_key"],
            "X-BAPI-SIGN": sig,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv,
            "Content-Type": "application/json",
        }

    def _get(self, path, params=None, private=False):
        # Key-Pruefung VOR der Signierung, sonst fliegt ein KeyError
        if private and not self.has_keys:
            return {"retCode": 10001, "retMsg": "Keine API-Keys hinterlegt.",
                    "result": {}, "private_required": True}
        params = params or {}
        headers = self._sign(params) if private else {}
        try:
            r = self.session.get(self.base + path, params=params, headers=headers, timeout=15)
            data = r.json()
            if data.get("retCode") != 0:
                _log.error(f"Bybit {path}: retCode={data.get('retCode')} {data.get('retMsg')}")
            return data
        except Exception as exc:
            _log.error(f"Bybit {path} fehlgeschlagen: {exc}")
            return {"retCode": -1, "retMsg": str(exc)}

    def _post(self, path, params, private=True):
        if not self.has_keys:
            return {"retCode": 10001, "retMsg": "Keine API-Keys hinterlegt.",
                    "result": {}, "private_required": True}
        headers = self._sign(params)
        try:
            r = self.session.post(self.base + path, headers=headers, timeout=15)
            data = r.json()
            if data.get("retCode") != 0:
                _log.error(f"Bybit {path}: retCode={data.get('retCode')} {data.get('retMsg')}")
            return data
        except Exception as exc:
            _log.error(f"Bybit {path} fehlgeschlagen: {exc}")
            return {"retCode": -1, "retMsg": str(exc)}

    # ---------- Oeffentliche Marktdaten (keine Keys noetig) ----------
    def server_time(self):
        return self._get("/v5/market/time")

    def ticker(self, symbol="ETHUSDT", category="spot"):
        d = self._get("/v5/market/tickers", {"category": category, "symbol": symbol})
        lst = d.get("result", {}).get("list", [])
        return lst[0] if lst else None

    def orderbook(self, symbol="ETHUSDT", limit=50, category="spot"):
        d = self._get("/v5/market/orderbook",
                      {"category": category, "symbol": symbol, "limit": limit})
        return d.get("result", {})

    def klines(self, symbol="ETHUSDT", interval="15", limit=200, category="spot"):
        """Kerzendaten fuer technische Indikatoren.

        Achtung: Die EU-Entity serviert nur /v5/market/kline (singular).
        /v5/market/klines liefert dort HTTP 404 mit leerem Body.
        """
        d = self._get("/v5/market/kline",
                      {"category": category, "symbol": symbol, "interval": interval, "limit": limit})
        rows = d.get("result", {}).get("list", [])
        # Bybit liefert umgekehrt (neueste zuerst): [start, open, high, low, close, volume, turnover]
        return [dict(start=r[0], open=float(r[1]), high=float(r[2]), low=float(r[3]),
                     close=float(r[4]), volume=float(r[5]), turnover=float(r[6]))
                for r in rows]

    def market_snapshot(self, symbol="ETHUSDT"):
        """Alles was die GUI/Strategie pro Takt braucht."""
        t = self.ticker(symbol) or {}
        ob = self.orderbook(symbol)
        bids = [(float(p), float(q)) for p, q in ob.get("b", [])]
        asks = [(float(p), float(q)) for p, q in ob.get("a", [])]
        out = {
            "symbol": symbol,
            "host": self.host_name,
            "last": float(t["lastPrice"]) if t.get("lastPrice") else None,
            "bid": bids[0][0] if bids else None,
            "ask": asks[0][0] if asks else None,
            "volume_24h": float(t["volume24h"]) if t.get("volume24h") else None,
            "turnover_24h": float(t["turnover24h"]) if t.get("turnover24h") else None,
            "spread_pct": None,
        }
        if out["bid"] and out["ask"]:
            mid = (out["bid"] + out["ask"]) / 2
            out["spread_pct"] = (out["ask"] - out["bid"]) / mid * 100
            out["mid"] = mid
        return out

    # ---------- Private Endpunkte ----------
    def wallet_balance(self, account_type="UNIFIED"):
        d = self._get("/v5/account/wallet-balance",
                      {"accountType": account_type, "coin": "USDT"}, private=True)
        if d.get("retCode") != 0:
            return d
        coins = d.get("result", {}).get("list", [{}])[0].get("total", [])
        return {"retCode": 0, "coins": {c["coin"]: float(c["total"]) for c in coins}}

    _instr_cache = {}

    def instrument(self, symbol="ETHUSDT", category="spot"):
        """Handelsregeln: Lot-Groesse, Schrittweiten, Min-Order.

        Die EU-Entity ignoriert den symbol-Parameter und liefert alle
        Instrumente (128 Stueck) -> deshalb clientseitig filtern + cachen.
        """
        key = (category,)
        if key not in self._instr_cache:
            d = self._get("/v5/market/instruments-info", {"category": category})
            self._instr_cache[key] = {i["symbol"]: i for i in d.get("result", {}).get("list", [])}
        return self._instr_cache[key].get(symbol)

    @staticmethod
    def _floor_step(value, step):
        """Rundet kaufmaennisch auf die Bybit-Schrittweite ab (float-sicher)."""
        import math
        try:
            step = float(step)
            if step <= 0:
                return value
            decimals = max(0, int(math.ceil(-math.log10(step))))
            return float(math.floor(value / step) * step)
        except Exception:
            return value

    def place_order(self, symbol, side, qty, order_type="Market", price=None,
                    time_in_force="GTC", dry_run=True):
        """Setzt eine echte Spot-Order. dry_run=True simuliert nur.

        Bybit V5 verlangt side als 'Buy'/'Sell' in CamelCase, nicht 'BUY'.
        """
        side = {"BUY": "Buy", "SELL": "Sell", "buy": "Buy", "sell": "Sell"}.get(
            str(side).strip(), str(side).strip())
        if side not in ("Buy", "Sell"):
            return {"retCode": -1, "retMsg": f"Ungueltige side '{side}'. Erlaubt: Buy, Sell."}

        qty = float(qty)
        # Lot-Size pruefen, BEVOR irgendetwas gesendet wird
        info = self.instrument(symbol) or {}
        lot = info.get("lotSizeFilter", {}) or {}
        min_qty = float(lot.get("minOrderQty") or 0)
        step = lot.get("qtyStep") or "0"
        if step and float(step) > 0:
            qty = self._floor_step(qty, step)
        if min_qty and qty < min_qty:
            return {"retCode": -1, "min_qty": min_qty, "qty_step": step,
                    "retMsg": f"Qty {qty} < Bybit-Minimum {min_qty} {symbol}. Order verworfen."}
        if qty <= 0:
            return {"retCode": -1, "qty_step": step,
                    "retMsg": f"Qty nach Rundung auf Schritt {step} = 0. Order verworfen."}

        params = {
            "category": "spot",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": str(qty),
            "timeInForce": time_in_force,
        }
        if price is not None and order_type == "Limit":
            tick = (info.get("priceFilter", {}) or {}).get("tickSize")
            if tick and float(tick) > 0:
                price = self._floor_step(price, tick)
            params["price"] = str(price)

        snap = self.market_snapshot(symbol)
        if not snap.get("last"):
            return {"retCode": -1, "retMsg": "Kein Marktdaten - Order verworfen."}

        if dry_run:
            est_price = price if price else (snap["ask"] if side == "Buy" else snap["bid"])
            notional = round(qty * est_price, 4)
            return {
                "retCode": 0, "dry_run": True,
                "symbol": symbol, "side": side, "type": order_type,
                "qty": qty, "est_price": est_price, "est_quote": notional,
                "min_qty": min_qty, "qty_step": step,
                "fee_estimate_pct": 0.1,
                "est_fee": round(notional * 0.001, 6),
                "message": "DRY-RUN: Order NICHT gesendet. dry_run=False sendet sie live.",
            }

        d = self._post("/v5/order/create", params)
        if d.get("retCode") == 0:
            _log.info(f"ORDER LIVE: {side} {qty} {symbol} ({order_type}) -> {d['result'].get('orderId')}")
        return d

    def open_orders(self, symbol=None, category="spot"):
        p = {"category": category, "openOnly": 0}
        if symbol:
            p["symbol"] = symbol
        return self._get("/v5/order/realtime", p, private=True)

    def cancel_order(self, symbol, order_id):
        return self._post("/v5/order/cancel",
                          {"category": "spot", "symbol": symbol, "orderId": order_id})

    def config_info(self):
        """Prueft ob die Keys gueltig sind und welche Permissions gelten."""
        if not self.has_keys:
            return {"ok": False, "reason": "Keine Keys hinterlegt (nur oeffentliche Daten)."}
        d = self._get("/v5/account/constraints", {"accountType": "UNIFIED"}, private=True)
        return {"ok": d.get("retCode") == 0,
                "retMsg": d.get("retMsg"),
                "details": d.get("result", {})}
