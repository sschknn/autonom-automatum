"""web3.py Integration für echte ETH-Transaktionen.

Voraussetzungen:
- Python-Paket 'web3' installiert (pip install web3)
- Echte Alchemy-API-Key in wallet/api_keys.json (AKTIV)
- Wallet (Private Key) in wallet/local_wallet.json

Sicherheit:
- Der Private Key bleibt lokal und wird nur zur Signatur verwendet.
- Keine Übertragung des Keys über das Netzwerk.
"""
import os
import json
from core import config

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

WALLET_FILE = os.path.join(config.BASE_DIR, "wallet", "local_wallet.json")
API_KEY_FILE = os.path.join(config.BASE_DIR, "wallet", "api_keys.json")

class Web3Engine:
    def __init__(self):
        self.web3_available = WEB3_AVAILABLE
        self.wallet_path = WALLET_FILE
        self.api_path = API_KEY_FILE
        self.wallet_data = self._load_wallet()
        self.api_data = self._load_api()
        self.w3 = None
        if self.web3_available and self.api_data.get("status") == "ACTIVE":
            endpoint = self.api_data.get("endpoint_template", "").format(API_KEY=self.api_data.get("api_key_placeholder", ""))
            if endpoint and "DEIN" not in endpoint:
                self.w3 = Web3(Web3.HTTPProvider(endpoint))
        # Logger (wird von Fehlerpfaden gebraucht)
        try:
            from core import logger as _logger
            self.log = _logger.DualLogger()
        except Exception:
            class _NullLog:
                def error(self, *a, **k): pass
                def info(self, *a, **k): pass
                def warning(self, *a, **k): pass
            self.log = _NullLog()

    def _load_wallet(self):
        if os.path.isfile(self.wallet_path):
            with open(self.wallet_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_api(self):
        if os.path.isfile(self.api_path):
            with open(self.api_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def is_ready(self):
        return self.web3_available and self.w3 is not None and self.w3.is_connected() if self.w3 else False

    def get_balance_real(self):
        if not self.is_ready():
            return None
        address = self.wallet_data.get("public_address")
        if not address:
            return None
        try:
            balance_wei = self.w3.eth.get_balance(Web3.to_checksum_address(address))
            return float(Web3.from_wei(balance_wei, 'ether'))
        except Exception as exc:
            return {"error": str(exc)}

    def estimate_tx_cost_eth(self):
        """Kostenschätzung für eine einfache ETH-Überweisung."""
        if not self.is_ready():
            return None
        try:
            gas_price = self.w3.eth.gas_price
            return float(self.w3.from_wei(gas_price * 21000, "ether"))
        except Exception as exc:
            self.log.error(f"Gas-Schätzung fehlgeschlagen: {exc}")
            return None

    def send_transaction(self, to_address, amount_eth, dry_run=False):
        """Signiert und sendet eine ECHTE Mainnet-Transaktion.

        dry_run=True: erstellt und signiert die Transaktion, sendet sie aber NICHT.
        Damit kann der Bot echte Kosten kalkulieren ohne Geld zu bewegen.
        """
        if not self.is_ready():
            return {"status": "ERROR", "message": "Web3 nicht verbunden. Kein Mainnet-Zugriff."}
        if not self.wallet_data.get("private_key_hex"):
            return {"status": "ERROR", "message": "Kein Private Key in wallet/local_wallet.json."}

        try:
            from eth_account import Account
        except ImportError:
            return {"status": "ERROR", "message": "eth-account fehlt. Installiere: pip install web3"}

        balance = self.get_balance_real()
        if not isinstance(balance, float):
            return {"status": "ERROR", "message": f"Guthaben nicht abrufbar: {balance}"}

        # WICHTIG: Die Absenderadresse muss aus dem Private Key ABGELEITET werden.
        # Der Wert in der JSON-Datei kann veraltet/falsch sein (siehe wallet.py).
        try:
            account = Account.from_key(
                "0x" + self.wallet_data["private_key_hex"]
                if not self.wallet_data["private_key_hex"].startswith("0x")
                else self.wallet_data["private_key_hex"]
            )
            frm = account.address          # <- Quelle der Wahrheit
            to = Web3.to_checksum_address(to_address)
        except Exception as exc:
            return {"status": "ERROR", "message": f"Ungültige Adresse/Key: {exc}"}

        stored = self.wallet_data.get("public_address")
        if stored and stored.lower() != frm.lower():
            self.log.warning(
                f"Wallet-Datei inkonsistent: gespeichert {stored}, Key gehoert {frm}. "
                "ETH auf der gespeicherten Adresse ist mit diesem Key nicht auszahlbar."
            )

        # Burn-Address ist verboten
        if int(to, 16) == 0:
            return {"status": "ERROR", "message": "Zieladresse ist die Null-Adresse (ETH-Verlust). Blockiert."}

        try:
            nonce = self.w3.eth.get_transaction_count(frm, "pending")
            chain_id = self.w3.eth.chain_id
            gas_price = self.w3.eth.gas_price
            value_wei = self.w3.to_wei(amount_eth, "ether")

            tx = {
                "from": frm,
                "to": to,
                "value": value_wei,
                "gas": 21000,
                "gasPrice": gas_price,
                "nonce": nonce,
                "chainId": chain_id,
            }

            # Gas prüfen bevor wir irgendetwas anderes tun
            max_cost = float(self.w3.from_wei(gas_price * 21000, "ether"))
            if balance < amount_eth + max_cost:
                return {
                    "status": "ERROR",
                    "message": (f"Zu wenig ETH: Balance {balance:.8f}, benötigt "
                                f"{amount_eth:.8f} + Gas {max_cost:.8f} = {amount_eth + max_cost:.8f}"),
                    "balance": balance,
                    "required": amount_eth + max_cost,
                }

            account = Account.from_key(self.wallet_data["private_key_hex"])
            signed = account.sign_transaction(tx)
            raw = signed.raw_transaction if hasattr(signed, "raw_transaction") else signed.rawTransaction
            tx_hash = "0x" + signed.hash.hex() if not isinstance(signed.hash, str) else signed.hash

            if dry_run:
                return {
                    "status": "DRY_RUN",
                    "from": frm,
                    "to": to,
                    "amount_eth": amount_eth,
                    "max_cost_eth": max_cost,
                    "nonce": nonce,
                    "chain_id": chain_id,
                    "tx_hash": tx_hash,
                    "message": "Transaktion signiert, aber NICHT gesendet (dry_run=True).",
                }

            # ECHTE Übertragung auf Mainnet
            receipt_hash = self.w3.eth.send_raw_transaction(raw)
            receipt = self.w3.eth.wait_for_transaction_receipt(receipt_hash, timeout=120)
            self.log.info(f"Mainnet-TX gesendet: {receipt_hash.hex()} | Status: {receipt.status} | Block: {receipt.blockNumber}")
            return {
                "status": "SENT",
                "from": frm,
                "to": to,
                "amount_eth": amount_eth,
                "gas_cost_eth": float(self.w3.from_wei(receipt.gasUsed * receipt.effectiveGasPrice, "ether")),
                "tx_hash": receipt_hash.hex(),
                "block": receipt.blockNumber,
                "success": receipt.status == 1,
                "message": "Echte Mainnet-Transaktion bestätigt.",
            }
        except Exception as exc:
            self.log.error(f"Transaktion fehlgeschlagen: {exc}")
            return {"status": "ERROR", "message": str(exc)}

    def report(self):
        status = "AKTIV" if self.is_ready() else "INAKTIV"
        return f"web3.py Status: {status} | Web3 connected: {self.is_ready() if self.web3_available else False} | Wallet: {self.wallet_data.get('public_address', 'Kein Wallet')}"
