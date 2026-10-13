"""Zentrale Konfiguration für autonom-automatum."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Datenbank- und Log-Pfade
DB_PATH = os.path.join(BASE_DIR, "data", "autonom_core.db")
LOG_FILE = os.path.join(BASE_DIR, "logs", "autonom.log")

# Arbeitsverzeichnisse (Input / Output)
INBOX_DIR = os.path.join(BASE_DIR, "inbox")
OUTBOX_DIR = os.path.join(BASE_DIR, "outbox")

# Daemon-Takt (Sekunden zwischen Ticks) – durch LLM-Agent optimiert
TICK_RATE = 0.5

# Budget-Parameter (virtuelles Energiemonto) – durch LLM-Agent kalibriert
INITIAL_BUDGET = 200.0
ENERGY_COST_PER_TASK = 3.0
ENERGY_REGEN_PER_TICK = 5.0
MAX_BUDGET = 1000.0

# LLM-Konfigurationsmodus (durch LLM-Agent aktiviert)
LLM_MODE_ENABLED = True
LLM_ANALYSIS_ENABLED = True
LLM_MAX_INPUT_SIZE = 10240  # Max. Zeichen für Analyse

# Wallet- und Genesis-Integration (durch LLM-Agent konfiguriert)
WALLET_ENABLED = True
GENESIS_PROMPT_FILE = os.path.join(BASE_DIR, "data", "genesis.prompt")
WALLET_POLICY_FILE = os.path.join(BASE_DIR, "wallet", "wallet_policy.json")

# OpenRouter KI-Integration (echte Free-Modelle)
OPENROUTER_ENABLED = True
