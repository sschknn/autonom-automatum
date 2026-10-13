"""Einstellungen fuer autonom-automatum.

Die Werte liegen in data/settings.json und werden beim Start geladen, damit
Regler im GUI nicht beim Beenden verloren gehen.

Zwei Regeln, die diese Datei durchsetzt:

1. **Bybit-Minimum.** Kein Spot-Order auf Bybit EU ist unter 5 USDC moeglich
   (lotSizeFilter.minOrderAmt). Ein Limit darunter wuerde nie gefuellt.

2. **Reserve kleiner als Kapital.** Liegt die Reserve ueber dem Kapital, ist
   technisch nie ein Trade moeglich. Das ist kein Fehler, wird aber gemeldet -
   sonst stellt man den Regler und wundert sich, dass nichts passiert.
"""
import json
import os

from core import config

# Wertebereich je Einstellung: (minimum, maximum, standard)
GRENZEN = {
    "initial_quote":      (5.0,   100000.0, 50.0),
    "max_trade_quote":    (5.0,   100000.0, 25.0),
    "min_reserve_quote":  (0.0,   100000.0, 10.0),
    "max_trades_per_hour": (1,    100,       5),
    "refresh_ms":         (2000,  300000,    15000),
    "min_confidence":     (0.1,    1.0,       0.22),
}

# Auf Bybit EU tatsaechlich befeuerte Paare (USDC und Fiat, kein USDT).
PAARE = ["ETHUSDC", "ETHEUR", "BTCUSDC", "BTCEUR"]

MIN_ORDER_AMT = 5.0   # Bybit EU lotSizeFilter.minOrderAmt


def standard():
    s = {"symbol": "ETHUSDC"}
    s.update({k: v[2] for k, v in GRENZEN.items()})
    return s


def _klemme(wert, bereich, name):
    lo, hi, _ = bereich
    try:
        wert = float(wert)
    except (TypeError, ValueError):
        return bereich[2], f"{name}: '{wert}' ist keine Zahl, auf {bereich[2]} gesetzt"
    if wert < lo:
        return lo, f"{name}: {wert} liegt unter dem Minimum {lo}, auf {lo} gesetzt"
    if wert > hi:
        return hi, f"{name}: {wert} liegt ueber dem Maximum {hi}, auf {hi} gesetzt"
    return wert, None


def normalisiere(roh, ausgabe=False):
    """Uebernimmt beliebige Eingaben und liefert (saubere_einstellungen, warnungen).

    Wird bei jedem Laden benutzt. Eine kaputte oder von Hand editierte Datei
    darf das Programm nicht zum Absturz bringen.

    ausgabe=True gibt die Warnungen auch auf der Konsole aus. Beim Laden aus
    der Datei ist das Quatsch - die Werte sind bereits in Ordnung, dafuer hat
    jemand sie selbst gesetzt. Nur im GUI zaehlt eine Warnung, die man nicht
    gelesen hat: dort fragt der Regler ab, man stellt ihn, und es passiert
    nichts.
    """
    roh = roh if isinstance(roh, dict) else {}
    raus, warnungen = standard(), []

    for name, bereich in GRENZEN.items():
        wert, w = _klemme(roh.get(name, bereich[2]), bereich, name)
        raus[name] = int(wert) if bereich[2] == int(bereich[2]) else wert
        if w:
            warnungen.append(w)

    symbol = str(roh.get("symbol", "ETHUSDC")).strip().upper()
    if symbol not in PAARE:
        warnungen.append(
            f"symbol: '{symbol}' ist kein handelbares Paar auf Bybit EU. "
            f"Ersatz: {PAARE[0]}")
        symbol = PAARE[0]
    raus["symbol"] = symbol

    # Logik zwischen den Werten pruefen
    if raus["min_reserve_quote"] >= raus["initial_quote"]:
        warnungen.append(
            f"Reserve ({_zahl(raus['min_reserve_quote'])} USDC) ist groesser oder "
            f"gleich dem Kapital ({_zahl(raus['initial_quote'])} USDC). "
            "Es kann technisch nie gehandelt werden.")
    if raus["max_trade_quote"] < MIN_ORDER_AMT:
        # _klemme faengt das bereits ab, hier nur zur Vollstaendigkeit
        pass
    if (raus["max_trade_quote"] + raus["min_reserve_quote"]
            > raus["initial_quote"]):
        warnungen.append(
            f"Max. Trade ({_zahl(raus['max_trade_quote'])}) plus Reserve "
            f"({_zahl(raus['min_reserve_quote'])}) uebersteigt das Kapital "
            f"({_zahl(raus['initial_quote'])}). Ein voller Trade wird "
            "dadurch nie moeglich.")
    return raus, warnungen


def _zahl(w):
    """Deutsche Darstellung: 1234.5 -> '1.234,50'"""
    s = f"{float(w):,.2f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# Ohne Unterstrich: die GUI greift darauf zu.
settings_zahl = _zahl


class Settings:
    """Liest und schreibt data/settings.json."""

    def __init__(self, pfad=None):
        self.pfad = pfad or config.SETTINGS_FILE
        self.warnungen = []
        self.werte = self._laden()

    def _laden(self):
        try:
            with open(self.pfad, "r", encoding="utf-8") as f:
                roh = json.load(f)
        except FileNotFoundError:
            roh = {}
        except Exception as exc:
            roh = {}
            self.warnungen.append(f"Einstellungsdatei unlesbar ({exc}), Standard benutzt")
        # Keine Konsolenausgabe: wer die Datei selbst geschrieben hat, kennt
        # seine Werte. Die Warnung bleibt fuer das GUI sichtbar.
        werte, warn = normalisiere(roh, ausgabe=False)
        self.warnungen.extend(warn)
        return werte

    def get(self, name, standard_ersatz=None):
        if name in self.werte:
            return self.werte[name]
        if standard_ersatz is not None:
            return standard_ersatz
        return GRENZEN[name][2]

    def __getitem__(self, name):
        return self.get(name)

    def set(self, **kwargs):
        """Setzt Werte, klemmt sie und schreibt sofort."""
        kandidat = dict(self.werte)
        kandidat.update(kwargs)
        werte, warn = normalisiere(kandidat)
        self.werte = werte
        self.warnungen = warn
        self._speichern()
        return werte

    def _speichern(self):
        os.makedirs(os.path.dirname(self.pfad), exist_ok=True)
        with open(self.pfad, "w", encoding="utf-8") as f:
            json.dump(self.werte, f, indent=2, ensure_ascii=False)

    def als_text(self):
        """Fuer das Log und die Anzeige im Assistenten."""
        w = self.werte
        zeilen = [
            f"Symbol:              {w['symbol']}",
            f"Startkapital:        {_zahl(w['initial_quote'])} USDC",
            f"Max. Trade:          {_zahl(w['max_trade_quote'])} USDC",
            f"Reserve:             {_zahl(w['min_reserve_quote'])} USDC",
            f"Max. Trades/Stunde:  {w['max_trades_per_hour']}",
            f"Aktualisierung:      {w['refresh_ms'] // 1000} Sekunden",
        ]
        if self.warnungen:
            zeilen.append("")
            zeilen.append("Warnungen:")
            zeilen.extend(f"- {x}" for x in self.warnungen)
        return "\n".join(zeilen)

    def pruefe(self):
        """Meldet Kombinationen, die zwar gueltig sind, aber nichts bewirken."""
        w = self.werte
        probleme = []
        if w["min_reserve_quote"] >= w["initial_quote"]:
            probleme.append("Reserve >= Kapital: es kann nie gehandelt werden.")
        if w["max_trade_quote"] > w["initial_quote"]:
            probleme.append(
                "Max. Trade ist groesser als das Kapital: effektiv begrenzt das Kapital.")
        if w["max_trade_quote"] + w["min_reserve_quote"] > w["initial_quote"]:
            probleme.append(
                "Max. Trade + Reserve uebersteigt das Kapital: "
                "es bleibt weniger als ein voller Trade uebrig.")
        return probleme