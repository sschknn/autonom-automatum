"""Verschiedene Trading-Strategien für den KI-Bot."""

STRATEGIES = {
    "BUY_HOLD": {"description": "Kaufen und halten bei echtem ETH-Guthaben", "min_eth": 0.0001, "max_eth": 0.01},
    "SCALPING": {"description": "Schnelle kleine Trades bei hoher Volatilität", "min_eth": 0.001, "max_eth": 0.005},
    "GRID_TRADING": {"description": "Grid-Strategie in Range-Märkten", "min_eth": 0.002, "max_eth": 0.02},
    "DCA": {"description": "Dollar-Cost-Averaging bei fallenden Kursen", "min_eth": 0.001, "max_eth": 0.01},
    "ARBITRAGE": {"description": "Arbitrage zwischen Mainnet und L2", "min_eth": 0.005, "max_eth": 0.05},
}
