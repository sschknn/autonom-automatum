"""Robustes Logging für autonom-automatum (Datei + DB)."""
import logging
import os
from core import config, database

class DualLogger:
    def __init__(self, name="autonom"):
        self.db = database.Database()
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        # Datei-Handler
        os.makedirs(os.path.dirname(config.LOG_FILE) if os.path.dirname(config.LOG_FILE) else ".", exist_ok=True)
        fh = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        # Formatter
        fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
        fh.setFormatter(fmt)
        # Konsolen-Handler (optional, aber nützlich)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        # Vermeide doppelte Handler bei Wieder-Initialisierung
        if not self.logger.handlers:
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)

    def info(self, msg):
        self.logger.info(msg)
        self.db.log("INFO", msg)

    def error(self, msg):
        self.logger.error(msg)
        self.db.log("ERROR", msg)

    def warning(self, msg):
        self.logger.warning(msg)
        self.db.log("WARNING", msg)

    def debug(self, msg):
        self.logger.debug(msg)
        self.db.log("DEBUG", msg)
