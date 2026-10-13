"""Verarbeitungs-Engine nach Bangway/Zellen-Prinzip für autonom-automatum."""
import os
import hashlib
from core import config, logger

class CellProcessor:
    """Verarbeitet Aufgaben als zelluläre Automate (Nachbar-Daten / Regelwerk)."""
    def __init__(self):
        self.log = logger.DualLogger()

    def process(self, file_path):
        """Liest Rohdaten, wendet Regelwerk an und erzeugt Ergebnisdatei."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()

        # Zellen-Prinzip: Wir betrachten Zeichen als Zellen und berechnen einen Zustand
        # basierend auf Nachbarn (vorheriges/nächstes Zeichen) und einer Regel.
        lines = raw.splitlines()
        result_lines = []
        for line in lines:
            # Regel: Jede Zeile wird als Zell-String behandelt; wir berechnen einen Hash als "Zustand"
            # und erzeugen eine zusammengefasste Ausgabe.
            state_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()[:12]
            # "Nachbar-Daten": Länge der Zeile als Nachbar-Wert
            neighbor_metric = len(line)
            # Zustandsänderung: Kombination aus Hash und Nachbar-Metrik
            transformed = f"ZUSTAND:{state_hash}|NACHBAR_METRIK:{neighbor_metric}|ORIGINAL_LEN:{len(line)}"
            result_lines.append(transformed)

        result_text = "\n".join(result_lines)
        result_filename = os.path.basename(file_path) + ".processed"
        out_path = os.path.join(config.OUTBOX_DIR, result_filename)
        os.makedirs(config.OUTBOX_DIR, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result_text)
        self.log.info(f"Engine verarbeitet: {file_path} -> {out_path}")
        return out_path
