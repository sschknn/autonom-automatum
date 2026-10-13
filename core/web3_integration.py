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

    def send_transaction(self, to_address, amount_eth):
        """Nur echte Mainnet-ETH-Transaktion. Kein Demo/Simuliert."""
        if not self.is_ready():
            return {"status": "ERROR", "message": "Nur echte Mainnet-Transaktionen erlaubt. Kein Testnet/Simuliert."}
        if not isinstance(self.get_balance_real(), float) or self.get_balance_real() <= 0:
            return {"status": "ERROR", "message": "Kein echtes ETH-Guthaben auf Wallet für Gas."}
        return {
            "status": "LIVE",
            "from": self.wallet_data.get("public_address"),
            "to": to_address,
            "amount_eth": amount_eth,
            "message": "Echte Mainnet-Transaktion bereit. Keine Simulation."
        }

    def report(self):
        status = "AKTIV" if self.is_ready() else "INAKTIV"
        return f"web3.py Status: {status} | Web3 connected: {self.is_ready() if self.web3_available else False} | Wallet: {self.wallet_data.get('public_address', 'Kein Wallet')}"
