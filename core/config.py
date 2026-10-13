"""Zentrale Konfiguration fuer autonom-automatum.

Nur Parameter, die der aktive Code tatsaechlich liest. Alles andere waere
Konfiguration ohne Wirkung.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Protokollierung ---
LOG_FILE = os.path.join(BASE_DIR, "logs", "autonom.log")
LOG_LEVEL = "INFO"          # DEBUG | INFO | WARNING | ERROR

# --- Daten ---
# Das Paper-Portfolio ist die einzige persistente Datei des Produkts.
PAPER_STATE_FILE = os.path.join(BASE_DIR, "data", "paper_portfolio.json")

# --- Assistent ---
ASSISTANT_ENABLED = True
ASSISTANT_MAX_TOKENS = 400

# --- Laufzeit ---
GUI_REFRESH_MS = 15000      # Aktualisierungsintervall der Oberflaeche
