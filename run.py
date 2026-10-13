#!/usr/bin/env python3
"""Einstiegspunkt für autonom-automatum."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent import AutonomAutomatum
from core import config

def main():
    # Sicherstellen, dass Inbox und Outbox existieren
    os.makedirs(config.INBOX_DIR, exist_ok=True)
    os.makedirs(config.OUTBOX_DIR, exist_ok=True)
    agent = AutonomAutomatum()
    agent.run()

if __name__ == "__main__":
    main()
