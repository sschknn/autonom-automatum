"""Zugangskontrolle für Produkte: Nur nach echter Zahlung freigegeben."""
import os
import shutil
from core import config, wallet, web3_integration

PROTECTED_DIR = os.path.join(config.BASE_DIR, "outbox", "protected")
PUBLIC_DIR = os.path.join(config.BASE_DIR, "outbox", "public")

class ProductProtection:
    def __init__(self):
        os.makedirs(PROTECTED_DIR, exist_ok=True)
        os.makedirs(PUBLIC_DIR, exist_ok=True)
        self.web3_engine = web3_integration.Web3Engine()

    def has_payment(self):
        """Prüft, ob echte ETH auf Wallet eingegangen ist (Mainnet)."""
        if self.web3_engine.is_ready():
            balance = self.web3_engine.get_balance_real()
            if isinstance(balance, float) and balance > 0:
                return True, balance
        # Fallback: Lokales Wallet-Target (simuliert)
        w = wallet.WalletEngine()
        if w.get_real_target_balance() > 0:
            return True, w.get_real_target_balance()
        return False, 0.0

    def protect(self, out_path):
        """Produkt nur freigeben, wenn Zahlung eingegangen."""
        paid, amount = self.has_payment()
        basename = os.path.basename(out_path)
        if paid:
            # Zahlung eingegangen: Datei öffentlich freigeben
            public_path = os.path.join(PUBLIC_DIR, basename)
            shutil.copy2(out_path, public_path)
            return {"status": "RELEASED", "path": public_path, "payment": amount, "message": "Produkt freigegeben (Zahlung eingegangen)"}
        else:
            # Keine Zahlung: Datei geschützt halten
            protected_path = os.path.join(PROTECTED_DIR, basename)
            shutil.copy2(out_path, protected_path)
            return {"status": "PROTECTED", "path": protected_path, "payment": 0.0, "message": "Produkt geschützt (keine Zahlung eingegangen)"}
