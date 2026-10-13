#!/usr/bin/env python3
"""Kurztest: Ein Tick und sauberes Beenden."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.agent import AutonomAutomatum
agent = AutonomAutomatum()
agent.tick()
agent.running = False
agent.log.info("Kurztest abgeschlossen.")
