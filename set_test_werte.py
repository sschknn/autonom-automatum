"""Einstellungen auf Test-Werte setzen und speichern.

Kapital 25 USDC, Reserve 10 USDC, Max.Trade 25 USDC. Diese Werte sind
nur fuer den Test gedacht, nicht fuer echtes Geld.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.settings import Settings

pfad = "data/settings.json"
if not os.path.exists(pfad):
    print("Fehler: data/settings.json nicht gefunden")
    sys.exit(1)

s = Settings(pfad=pfad)
s.set(
    initial_quote=50.0,      # Test-Kapital, nicht echtes Geld
    max_trade_quote=25.0,
    min_reserve_quote=10.0,
    max_trades_per_hour=5,
    refresh_ms=15000,
    symbol="ETHUSDC",
)
print("Gespeichert:", pfad)
print(s.als_text())
print()
print("Pruefe:", s.pruefe() or "keine Probleme - Kombination ist handelbar")