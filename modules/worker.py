"""Worker-Logik für zusätzliche Aufgabenverarbeitung (z. B. Log-Analyse)."""
from core import logger

class LogAnalyzerWorker:
    def __init__(self):
        self.log = logger.DualLogger()

    def analyze(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
            error_count = sum(1 for line in lines if "ERROR" in line)
            warning_count = sum(1 for line in lines if "WARNING" in line)
            summary = f"Log-Analyse: {len(lines)} Zeilen | Fehler: {error_count} | Warnungen: {warning_count}"
            self.log.info(summary)
            return summary
        except Exception as exc:
            self.log.error(f"LogAnalyzer-Fehler: {exc}")
            raise
