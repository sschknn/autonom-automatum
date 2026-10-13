"""Haupt-Agent und Daemon-Loop für autonom-automatum."""
import time
import signal
import sys
import os
from core import config, database, logger, budget, engine
from core.wallet import WalletEngine
from core.genesis import initialize_genesis
from core.protection import ProductProtection
from core.web3_integration import Web3Engine

class AutonomAutomatum:
    def __init__(self):
        self.db = database.Database()
        self.log = logger.DualLogger()
        self.budget_engine = budget.BudgetEngine()
        self.engine = engine.CellProcessor()
        # Wallet und Genesis (LLM-Konfiguration)
        self.wallet = WalletEngine() if config.WALLET_ENABLED else None
        if config.WALLET_ENABLED:
            initialize_genesis()
            self.log.info(f"Genesis-Prompt initialisiert: {config.GENESIS_PROMPT_FILE}")
            self.log.info(f"Wallet generiert: {self.wallet.get_public_address()}")
        # Web3 Integration (echte ETH-Transaktionen, automatisiert)
        try:
            from core.web3_integration import Web3Engine
            self.web3_engine = Web3Engine()
            if self.web3_engine.is_ready():
                self.log.info(f"Web3.py aktiviert: {self.web3_engine.report()}")
            else:
                self.log.info("Web3.py installiert, aber nicht bereit (kein echtes ETH-Guthaben oder Endpoint-Problem).")
        except Exception as exc:
            self.log.info(f"Web3.py nicht verfügbar: {exc}")
            self.web3_engine = None
        # Produkt-Schutz (nur nach Zahlung freigeben)
        self.protection = ProductProtection()
        self.running = True
        # Signal-Handling (sauberes Herunterfahren)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self.log.info("autonom-automatum gestartet.")

    def _signal_handler(self, signum, frame):
        self.log.info(f"Signal {signum} empfangen. Sauberes Herunterfahren eingeleitet.")
        self.running = False

    def tick(self):
        # Regeneration
        self.budget_engine.regenerate()
        # Aufgaben-Scan (Inbox)
        tasks = self.db.get_pending_tasks()
        # Falls keine DB-Tasks, scanne Verzeichnis
        if not tasks:
            tasks = self._scan_inbox_to_db()
        # Verarbeitung
        for task in tasks:
            if not self.running:
                break
            # Pausen-Logik
            if self.budget_engine.is_paused():
                self.log.info("Agent pausiert: Budget zu niedrig. Regeneration aktiv.")
                time.sleep(config.TICK_RATE)
                continue
            # Verarbeitung
            try:
                file_path = task.get("source_file") if isinstance(task, dict) else None
                if file_path is None:
                    # Wenn nur als Datei gefunden
                    # (wird in _scan_inbox_to_db als DB-Eintrag behandelt)
                    file_path = task
                # Falls es ein Pfad-String ist, als Datei verarbeiten
                if isinstance(file_path, str) and os.path.isfile(file_path):
                    # Energie-Kosten prüfen
                    if not self.budget_engine.charge(config.ENERGY_COST_PER_TASK):
                        self.log.warning("Verarbeitung übersprungen: Budget nicht ausreichend.")
                        # Markiere als fehlgeschlagen? Nein, einfach überspringen
                        continue
                    # Engine aufrufen
                    out_path = self.engine.process(file_path)
                    # Budget-Update (Erfolg = Belohnung)
                    reward = config.ENERGY_COST_PER_TASK * 3  # Belohnung > Kosten
                    self.budget_engine.earn(reward)
                    # Wallet-Update (echter Gewinn-Zuwachs pro Aufgabe)
                    if self.wallet:
                        self.wallet.increase_target(reward)
                        self.log.info(f"Wallet-Target erhöht: +{reward:.2f} (aktuell: {self.wallet.get_real_target_balance():.2f})")
                    # Produkt-Schutz: Nur freigeben, wenn Zahlung eingegangen
                    if self.protection:
                        protect_result = self.protection.protect(out_path)
                        self.log.info(f"Produkt-Schutz: {protect_result['status']} | {protect_result['message']} | Zahlung: {protect_result['payment']}")
                    task_id = task.get("id") if isinstance(task, dict) else None
                    if task_id is not None:
                        self.db.complete_task(task_id, out_path, config.ENERGY_COST_PER_TASK)
                    else:
                        self.log.info(f"Datei aus Inbox verarbeitet (ohne DB-ID): {file_path}")
                    # Nach erfolgreicher Verarbeitung Original entfernen
                    try:
                        os.remove(file_path)
                        self.log.info(f"Original aus Inbox entfernt: {file_path}")
                    except Exception as exc:
                        self.log.warning(f"Konnte Original nicht entfernen: {exc}")
                else:
                    # DB-Task mit source_file
                    source_file = task.get("source_file")
                    if source_file and os.path.isfile(source_file):
                        if not self.budget_engine.charge(config.ENERGY_COST_PER_TASK):
                            continue
                        out_path = self.engine.process(source_file)
                        reward = config.ENERGY_COST_PER_TASK * 3
                        self.budget_engine.earn(reward)
                        # Wallet-Update (echter Gewinn-Zuwachs pro Aufgabe)
                        if self.wallet:
                            self.wallet.increase_target(reward)
                            self.log.info(f"Wallet-Target erhöht: +{reward:.2f} (aktuell: {self.wallet.get_real_target_balance():.2f})")
                        # Web3 Automatisierung: Echte ETH-Transaktion vorbereiten
                        if self.web3_engine and self.web3_engine.is_ready():
                            tx_result = self.web3_engine.send_transaction_simulated(
                                "0x0000000000000000000000000000000000000000",  # Beispiel-Ziel (kann geändert werden)
                                0.001  # Beispiel-Betrag
                            )
                            self.log.info(f"Web3 Transaktion vorbereitet: {tx_result['status']} | Von: {tx_result.get('from', 'N/A')}")
                        self.db.complete_task(task["id"], out_path, config.ENERGY_COST_PER_TASK)
                        # Original aus Inbox entfernen nach Verarbeitung
                        try:
                            if os.path.isfile(source_file):
                                os.remove(source_file)
                                self.log.info(f"Original aus Inbox entfernt: {source_file}")
                        except Exception as exc:
                            self.log.warning(f"Konnte Original nicht entfernen: {exc}")
                    else:
                        self.log.error(f"Task-Datei nicht gefunden: {source_file}")
                        self.db.fail_task(task["id"], "Datei nicht gefunden", config.ENERGY_COST_PER_TASK / 2)
            except Exception as exc:
                self.log.error(f"Verarbeitungsfehler bei Task {task.get('id')}: {exc}")
                if isinstance(task, dict) and task.get("id"):
                    self.db.fail_task(task["id"], str(exc), config.ENERGY_COST_PER_TASK / 2)

    def _file_exists_in_db(self, full_path):
        with self.db._connect() as conn:
            row = conn.execute("SELECT 1 FROM tasks WHERE source_file = ? LIMIT 1", (full_path,)).fetchone()
            return row is not None

    def _scan_inbox_to_db(self):
        """Scannt Inbox und fügt neue Dateien als DB-Tasks ein."""
        if not os.path.isdir(config.INBOX_DIR):
            return []
        inserted = []
        for entry in os.listdir(config.INBOX_DIR):
            full_path = os.path.join(config.INBOX_DIR, entry)
            if os.path.isfile(full_path):
                # Prüfe, ob bereits in DB (egal welcher Status)
                if self._file_exists_in_db(full_path):
                    continue
                task_id = self.db.insert_task(full_path)
                inserted.append({"id": task_id, "source_file": full_path})
        if inserted:
            self.log.info(f"Inbox-Scan: {len(inserted)} neue Aufgabe(n) eingetragen.")
        return inserted

    def run(self):
        self.log.info("Daemon-Loop gestartet (Tick-Rate: {}s).".format(config.TICK_RATE))
        while self.running:
            try:
                self.tick()
            except Exception as exc:
                self.log.error(f"Kritischer Fehler im Tick: {exc}")
            time.sleep(config.TICK_RATE)
        self.log.info("autonom-automatum beendet sauber.")
