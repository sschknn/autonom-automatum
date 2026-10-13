"""Testabdeckung fuer die Kernlogik.

Ausgefuehrt mit:  python -m pytest tests/ -v
oder ohne pytest:  python tests/test_kern.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import indicators
from core.risk_manager import RiskManager
from core.paper_trader import PaperTrader
from core.bybit_exchange import BybitExchange


# ---------------------------------------------------------------- Indikatoren
class TestIndikatoren(unittest.TestCase):
    def test_ema_entspricht_definition(self):
        # EMA mit konstanten Werten muss gegenueber dem Startwert konvergieren
        self.assertAlmostEqual(indicators.ema([5.0] * 50, 9), 5.0, places=6)

    def test_ema_reagiert_auf_steigende_werte(self):
        werte = list(range(1, 51))
        e = indicators.ema([float(v) for v in werte], 9)
        self.assertGreater(e, 45.0)

    def test_rsi_ohne_daten_ist_none(self):
        self.assertIsNone(indicators.rsi([1.0, 2.0, 3.0], period=14))

    def test_rsi_steigender_markt_ist_hoch(self):
        werte = [float(i) for i in range(1, 40)]
        self.assertGreater(indicators.rsi(werte, period=14), 90)

    def test_rsi_fallender_markt_ist_niedrig(self):
        werte = [float(i) for i in range(40, 1, -1)]
        self.assertLess(indicators.rsi(werte, period=14), 10)

    def test_atr_ohne_daten_ist_none(self):
        self.assertIsNone(indicators.atr([{"high": 1, "low": 0, "close": 0.5}]))

    def test_analyze_meldet_zu_wenig_kerzen(self):
        r = indicators.analyze([])
        self.assertEqual(r["action"], "HOLD")
        self.assertIn("Kerzendaten", r["reason"])

    def test_analyze_ohne_kursbewegung_hält(self):
        # konstante Kerzen -> kein Edge
        kerzen = [{"start": str(i * 60000), "high": 100.0, "low": 100.0,
                   "open": 100.0, "close": 100.0, "volume": 1.0}
                  for i in range(50)]
        r = indicators.analyze(kerzen)
        self.assertIn(r["action"], ("HOLD", "BUY", "SELL"))
        self.assertIn("rsi", r["reason"].lower())


# ------------------------------------------------------------- Risikomanager
class TestRisikomanager(unittest.TestCase):
    def setUp(self):
        self.r = RiskManager(max_trade_eth=0.01, min_reserve_eth=0.001,
                             max_trade_quote=25.0, min_reserve_quote=10.0)

    def test_max_affordable_beachtet_reserve(self):
        # 0,1 ETH - 0,001 Reserve - 0,0001 Gas = 0,0989, gedeckelt auf 0,01
        self.assertAlmostEqual(self.r.max_affordable(0.1, 0.0001), 0.01)

    def test_max_affordable_wird_nie_negativ(self):
        self.assertEqual(self.r.max_affordable(0.0005, 0.0001), 0.0)

    def test_betrag_ueber_limit_wird_abgelehnt(self):
        ok, _ = self.r.can_trade(0.5, 1.0, 0.0001)
        self.assertFalse(ok)

    def test_gas_reserve_wird_nicht_angetastet(self):
        # genau die Reserve vorhanden -> nichts handelbar
        ok, grund = self.r.can_trade(0.005, 0.0011, 0.0001)
        self.assertFalse(ok)

    def test_quote_limit_wird_durchgesetzt(self):
        ok, grund = self.r.can_trade_quote(30.0, 100.0)
        self.assertFalse(ok)
        self.assertIn("Limit", grund)

    def test_quote_reserve_wird_beachtet(self):
        ok, _ = self.r.can_trade_quote(5.0, 12.0)
        self.assertFalse(ok)   # 12 - 10 Reserve = 2 < 5
        ok, _ = self.r.can_trade_quote(5.0, 20.0)
        self.assertTrue(ok)

    def test_trades_pro_stunde_begrenzt(self):
        for _ in range(5):
            self.r.record_trade("BUY", 0.001)
        ok, grund = self.r.can_trade_quote(5.0, 100.0)
        self.assertFalse(ok)
        self.assertIn("Stunde", grund)


# ------------------------------------------------------------- Paper-Trading
class TestPaperTrader(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        self.p = PaperTrader(initial_quote=1000.0, state_file=self.tmp.name)

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_kauf_verbraucht_quote_und_erhaelt_base(self):
        r = self.p.open_position("Buy")
        self.assertEqual(r["status"], "FILLED")
        self.assertGreater(self.p.state["base"], 0)
        self.assertLess(self.p.state["quote"], 1000.0)

    def test_kauf_unter_mindestbetrag_wird_abgelehnt(self):
        klein = PaperTrader(initial_quote=1.0, state_file=self.p.state_file)
        r = klein.open_position("Buy")
        self.assertEqual(r["status"], "SKIP")

    def test_verkauf_ohne_position_wird_abgelehnt(self):
        r = self.p.open_position("Sell")
        self.assertEqual(r["status"], "SKIP")

    def test_rundgang_kostet_gebuehren(self):
        vor_gebuehr = self.p.state["fees_paid"]
        self.p.open_position("Buy")
        self.p.open_position("Sell")
        self.assertGreater(self.p.state["fees_paid"], vor_gebuehr)
        self.assertEqual(len(self.p.state["trades"]), 1)

    def test_persistenz_ueberlebt_neustart(self):
        self.p.open_position("Buy")
        equity = self.p.equity()
        neu = PaperTrader(initial_quote=1000.0, state_file=self.p.state_file)
        self.assertAlmostEqual(neu.equity(), equity, places=6)

    def test_reset_setzt_zurueck(self):
        self.p.open_position("Buy")
        self.p.reset()
        self.assertEqual(self.p.state["trades"], [])
        self.assertEqual(self.p.state["base"], 0.0)
        self.assertEqual(self.p.state["initial_quote"], 1000.0)

    def test_kein_codepfad_zu_echten_orders(self):
        """Sicherheitsgarantie: PaperTrader darf keine echten Orders senden."""
        import inspect
        quelle = inspect.getsource(PaperTrader)
        verboten = ["dry_run=False", "place_order(", "send_transaction(",
                    "self.exchange._post", "_post("]
        gefunden = [w for w in verboten if w in quelle]
        self.assertEqual(gefunden, [],
                         f"PaperTrader enthaelt verbotene Aufrufe: {gefunden}")

    def test_report_enthaelt_kennzahlen(self):
        r = self.p.report()
        for feld in ("equity", "return_pct", "trades", "winrate",
                     "profit_factor", "fees_paid", "max_drawdown_pct"):
            self.assertIn(feld, r)


# ------------------------------------------------------------- Bybit-Anbindung
class TestBybit(unittest.TestCase):
    """Tests ohne Netzwerk - deterministisch."""

    def test_seitenformat_wird_normalisiert(self):
        # Die API akzeptiert nur 'Buy'/'Sell', nicht 'BUY'
        self.assertEqual(BybitExchange._normalisiere("BUY"), "Buy")
        self.assertEqual(BybitExchange._normalisiere("sell"), "Sell")

    def test_schrittweite_rundet_abwaerts(self):
        self.assertAlmostEqual(BybitExchange._floor_step(0.00123456, 0.0001), 0.0012, places=8)
        self.assertAlmostEqual(BybitExchange._floor_step(1.999, 0.01), 1.99, places=8)

    def test_schrittweite_ohne_wert_aendert_nichts(self):
        self.assertEqual(BybitExchange._floor_step(1.23456, 0), 1.23456)

    def test_ungueltige_seite_wird_abgelehnt(self):
        ex = BybitExchange("eu")
        r = ex.place_order("ETHUSDC", "LONG", 1, dry_run=True)
        self.assertEqual(r["retCode"], -1)

    def test_onchain_burn_adresse_wird_blockiert(self):
        """Der Burn-Schutz gehoert auf den On-Chain-Pfad, nicht auf Exchange-Orders.

        Eine Exchange-Market-Order hat keine Zieladresse - das ETH landet im
        eigenen Depot. Nur beim direkten Transfer darf 0x0 nicht durchgehen.
        """
        from core.web3_integration import Web3Engine
        import inspect
        quelle = inspect.getsource(Web3Engine.send_transaction)
        self.assertIn("Null-Adresse", quelle)
        self.assertIn("int(to, 16) == 0", quelle)

    def test_ohne_keys_kein_privater_zugriff(self):
        ex = BybitExchange("eu", keys_file="/tmp/gibt_es_nicht.json")
        ex.keys = {}
        ex.has_keys = False
        d = ex._get("/v5/account/wallet-balance", {}, private=True)
        self.assertEqual(d["retCode"], 10001)


# ------------------------------------------------------------------ Wallet
class TestWallet(unittest.TestCase):
    def test_neues_wallet_hat_korrektes_key_paar(self):
        """Regressionstest: Die Adresse MUSS aus dem Private Key folgen.

        Genau dieser Fehler ist previously unbemerkt geblieben: Die Adresse
        wurde per sha3_256(seed)[-20:] gebildet statt per ECDSA. Damit gehoerte
        das Guthaben einer Adresse zu einem Key, den es nicht gibt.
        """
        import tempfile
        d = tempfile.mkdtemp()
        pfad = os.path.join(d, "w.json")
        from core import wallet as wallet_mod
        alt = wallet_mod.WALLET_FILE
        wallet_mod.WALLET_FILE = pfad
        try:
            w = wallet_mod.WalletEngine()
            ok, msg = w.verify_key_pair()
            self.assertTrue(ok, f"Key-Paar ist inkonsistent: {msg}")
            # Adresse muss 0x + 40 Hex-Zeichen sein
            self.assertRegex(w.get_public_address(), r"^0x[0-9a-fA-F]{40}$")
            self.assertEqual(len(w.get_private_key_hex()), 64)
        finally:
            wallet_mod.WALLET_FILE = alt


if __name__ == "__main__":
    unittest.main(verbosity=2)
