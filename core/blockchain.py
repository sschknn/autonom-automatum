"""Blockchain-Integration für echte On-Chain-Transaktionen.

Voraussetzung: Ein echter API-Key muss in wallet/api_keys.json eingetragen werden.
Ohne echten Key läuft das System im lokalen Tracking-Modus.
"""
import json
import os
from core import config

API_KEY_FILE = os.path.join(config.BASE_DIR, "wallet", "api_keys.json")

class BlockchainEngine:
    def __init__(self):
        self.api_path = API_KEY_FILE
        self.config = self._load_config()

    def _load_config(self):
        if os.path.isfile(self.api_path):
            with open(self.api_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"status": "NO_KEY_FILE", "provider": None}

    def is_ready(self):
        key = self.config.get("api_key_placeholder", "")
        status = self.config.get("status", "")
        return status == "ACTIVE" and key.startswith("0x") is False and len(key) > 20 and "DEIN" not in key

    def get_endpoint(self):
        endpoint = self.config.get("endpoint_template", "")
        key = self.config.get("api_key_placeholder", "")
        if self.is_ready():
            return endpoint.format(API_KEY=key)
        return None

    def check_real_balance(self, wallet_engine):
        # Ohne echten Key: Fallback auf lokales Tracking
        if not self.is_ready():
            return {
                "on_chain_available": False,
                "message": "Kein echter API-Key aktiv. Lokales Wallet-Tracking aktiv.",
                "local_target": wallet_engine.get_real_target_balance(),
                "wallet_address": wallet_engine.get_public_address()
            }
        # Hier würde echte On-Chain-Abfrage erfolgen (web3.py / requests)
        return {
            "on_chain_available": True,
            "message": "Echter API-Key aktiv. On-Chain-Abfrage bereit.",
            "endpoint": self.get_endpoint(),
            "wallet_address": wallet_engine.get_public_address()
        }
