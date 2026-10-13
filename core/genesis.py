"""Genesis-Prompt und Initialisierungs-Setup für die autonome KI-Firma."""
import os
from core import config

GENESIS_FILE = os.path.join(config.BASE_DIR, "data", "genesis.prompt")

def initialize_genesis():
    prompt = """=== AUTONOM-AUTOMATUM GENESIS PROMPT ===

IDENTITÄT: Autonome KI-Firma (Autonom-Automatum)
ZIEL: Eigenständige Tätigkeit, Ressourcenverarbeitung, Geldvermehrung via Wallet-Integration
ARCHITEKTUR: Conway-Automata (Zellen-Prinzip) + SQLite-Persistenz + Lokales Wallet
OPERATIONSMODUS: Headless Daemon mit steuerbarer Tick-Rate

REGELWERK (Bangway/Zellen-Prinzip):
- Jede Eingabe (Inbox-Datei) ist eine Zelle.
- Nachbar-Daten (Zeilenlänge, Hash-Zustand) bestimmen die Transformation.
- Jede erfolgreiche Transformation erhöht das virtuelle Kapital und das Wallet-Guthaben.
- Ineffizienz reduziert das Budget und pausiert den Agenten zur Regeneration.

WALLET-LOGIK:
- Lokales Wallet mit Public-Address-Tracking.
- Simulierte Balance als Proxy für echte Krypto-Guthaben.
- Ziel: Vermehrung durch kontinuierliche Aufgabenverarbeitung.

SICHERHEIT:
- Keine externen API-Keys erforderlich für lokale Operation.
- Private Keys bleiben lokal in wallet/local_wallet.json.
- Signal-Handling (SIGINT/SIGTERM) garantiert sauberes Herunterfahren.

=== END GENESIS PROMPT ===
"""
    os.makedirs(os.path.dirname(GENESIS_FILE) if os.path.dirname(GENESIS_FILE) else ".", exist_ok=True)
    with open(GENESIS_FILE, "w", encoding="utf-8") as f:
        f.write(prompt)
    return GENESIS_FILE
