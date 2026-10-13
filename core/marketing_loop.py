"""Marketing-Loop: Bewirbt Produkte aktiv und zieht Kunden an."""
from core import config
from core.openrouter import OpenRouterEngine
from core.web3_integration import Web3Engine
from core.wallet import WalletEngine
from core.protection import ProductProtection
import os

class MarketingLoop:
    def __init__(self):
        self.wallet = WalletEngine()
        self.protection = ProductProtection()
        self.or_engine = OpenRouterEngine()
        self.web3_engine = Web3Engine()

    def promote_products(self):
        outbox_dir = os.path.join(config.BASE_DIR, "outbox")
        products = [f for f in os.listdir(outbox_dir) if f.endswith(".processed")]
        promotion_text = f"""=== AUTONOM-AUTOMATUM PRODUKTE ===
Autonome KI-Firma. Echte Blockchain-Zahlungen. Echte KI-Produkte.

Produkte bereit: {len(products)}
Wallet: {self.wallet.get_public_address()}
Echtes ETH: {self.web3_engine.get_balance_real() if self.web3_engine.is_ready() else 0.0} ETH
OpenRouter: {self.or_engine.get_models_available()[:2]}...
Genesis: KI-Produktivität, Prompt-Engineering, Monetarisierung.

Zahlung: ETH an 0xa4416ca6c022c9fc142af1ea50e76e8e568af183 (Mainnet)
QR-Code: wallet/wallet_qr.png
Katalog: produkte.md
Repo: github.com/sschknn/autonom-automatum
"""
        return promotion_text

    def run_promotion_cycle(self):
        text = self.promote_products()
        # In einem echten Szenario würde hier ein Social-Media-Post oder Newsletter-Versand erfolgen
        return {"status": "PROMOTION_READY", "channel": "GitHub + Social + Newsletter", "message": text[:200] + "..."}
