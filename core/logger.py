"""Logging fuer autonom-automatum.

Bewusst nur Datei + Konsole. Die frueher zusaetzlich vorhandene SQLite-Kopie
war reine Redundanz: gleiche Eintraege an zwei Orten, zwei Fehlerquellen,
ein zusaetzlicher Zustand, der nichts zur Berechnung beitrug.
"""
import logging
import os
from core import config


class Log:
    def __init__(self, name="autonom"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
        # Mehrfach-Initialisierung des Loggers darf keine Handler duplizieren
        if self.logger.handlers:
            return
        os.makedirs(os.path.dirname(config.LOG_FILE) or ".", exist_ok=True)
        fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
        fh = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def debug(self, msg):
        self.logger.debug(msg)


# Abwaertskompatibel: frueherer Klassenname
DualLogger = Log
