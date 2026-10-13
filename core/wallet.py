"""Echte lokale Krypto-Wallet-Integration für autonom-automatum.

WICHTIG: Dies erzeugt echte kryptografische Key-Paare lokal.
Für echte Blockchain-Transaktionen sind Netzwerk-APIs und Node-Provider
(z. B. Infura, Alchemy) erforderlich. Diese Datei bleibt lokal und wird
niemals automatisch übertragen.
"""
import os
import json
import hashlib
import secrets
from datetime import datetime
from core import config

WALLET_DIR = os.path.join(config.BASE_DIR, "wallet")
WALLET_FILE = os.path.join(WALLET_DIR, "local_wallet.json")

class WalletEngine:
    def __init__(self):
        os.makedirs(WALLET_DIR, exist_ok=True)
        self.wallet_path = WALLET_FILE
        self.data = self._load_or_create()

    def _derive_address(self, private_key_hex):
        """Leitet die ECHTE Ethereum-Adresse aus dem Private Key ab.

        Korrekte Kette: secp256k1-ECDSA -> Public Key (64 Byte, ohne 0x04)
        -> Keccak-256 -> letzte 20 Bytes -> Checksum-Adresse.
        Früher wurde hier fälschlich sha3_256(seed)[-20:] verwendet, was
        eine Adresse ergibt, zu der es keinen passenden Private Key gibt.
        """
        try:
            from eth_account import Account
            acct = Account.from_key("0x" + private_key_hex if not private_key_hex.startswith("0x") else private_key_hex)
            return acct.address, None
        except ImportError:
            return None, "eth-account fehlt (pip install web3)"
        except Exception as exc:
            return None, str(exc)

    def verify_key_pair(self):
        """Prüft ob Address und Private Key zusammenpassen.

        Gibt (ok, message) zurück. Ein Mismatch bedeutet: das Guthaben
        auf der Adresse gehört NICHT zu diesem Private Key.
        """
        pk = self.data.get("private_key_hex")
        stored = self.data.get("public_address")
        if not pk:
            return False, "Kein Private Key vorhanden."
        derived, err = self._derive_address(pk)
        if err:
            return False, f"Adresse nicht ableitbar: {err}"
        if derived.lower() != (stored or "").lower():
            return False, (
                f"MISMATCH! Datei: {stored} | Key gehört: {derived}. "
                "Das ETH auf der Datei-Adresse kann mit diesem Key NICHT ausgegeben werden."
            )
        return True, f"Key-Paar korrekt: {derived}"

    def _load_or_create(self):
        if os.path.isfile(self.wallet_path):
            with open(self.wallet_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Bestehende Wallet auf Konsistenz prüfen
            ok, msg = self.verify(data)
            if not ok and "MISMATCH" in msg:
                print(f"[WALLET-WARNUNG] {msg}")
            return data
        return self._create_new()

    def verify(self, data):
        pk = data.get("private_key_hex")
        stored = data.get("public_address")
        if not pk:
            return False, "Kein Private Key vorhanden."
        derived, err = self._derive_address(pk)
        if err:
            return False, f"Adresse nicht ableitbar: {err}"
        if derived.lower() != (stored or "").lower():
            return False, (
                f"MISMATCH! Datei: {stored} | Key gehört: {derived}. "
                "Das ETH auf der Datei-Adresse kann mit diesem Key NICHT ausgegeben werden."
            )
        return True, f"Key-Paar korrekt: {derived}"

    def _create_new(self):
        """Erzeugt ein neues Wallet mit echter ECDSA-Adressableitung."""
        try:
            from eth_account import Account
            acct = Account.create(secrets.token_bytes(32) if hasattr(secrets, "token_bytes") else None)
            private_key_hex = acct.key.hex()
            if private_key_hex.startswith("0x"):
                private_key_hex = private_key_hex[2:]
            public_address = acct.address
        except Exception as exc:
            raise RuntimeError(
                f"Wallet-Erstellung fehlgeschlagen: {exc}. Installiere: pip install web3"
            ) from exc

        wallet_data = {
            "type": "autonom_ki_wallet_ecdsa",
            "network_hint": "ethereum_mainnet",
            "public_address": public_address,
            "private_key_hex": private_key_hex,
            "balance_target": 0.0,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "genesis_block": "autonom-automatum-genesis-001",
            "derivation": "secp256k1-ECDSA -> Keccak-256 -> 20 Byte (echt)",
            "security_notice": "Private Key nur lokal. Niemals committen oder teilen.",
        }
        with open(self.wallet_path, "w", encoding="utf-8") as f:
            json.dump(wallet_data, f, indent=2)
        return wallet_data

    def get_public_address(self):
        return self.data.get("public_address")

    def get_private_key_hex(self):
        return self.data.get("private_key_hex")

    def get_real_target_balance(self):
        return self.data.get("balance_target", 0.0)

    def increase_target(self, amount):
        self.data["balance_target"] = self.data.get("balance_target", 0.0) + amount
        self._save()

    def decrease_target(self, amount):
        self.data["balance_target"] = max(0.0, self.data.get("balance_target", 0.0) - amount)
        self._save()

    def _save(self):
        with open(self.wallet_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def report(self):
        return (f"Wallet [{self.get_public_address()}] | "
                f"Real Target Balance: {self.get_real_target_balance():.2f} ETH-Äqv. | "
                f"Genesis: {self.data.get('genesis_block')}")
