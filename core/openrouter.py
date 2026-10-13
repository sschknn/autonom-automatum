"""OpenRouter API-Integration für echte KI-Modelle (Free Tier / Router)."""
import os
import json
from core import config

API_KEY_FILE = os.path.join(config.BASE_DIR, "wallet", "openrouter_key.json")

class OpenRouterEngine:
    def __init__(self):
        self.api_path = API_KEY_FILE
        self.config = self._load_config()

    def _load_config(self):
        if os.path.isfile(self.api_path):
            with open(self.api_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"status": "NO_KEY", "api_key": None}

    def is_active(self):
        key = self.config.get("api_key", "")
        return bool(key) and len(key) > 30 and "sk-or-" in key

    def get_key(self):
        return self.config.get("api_key")

    def get_models_available(self):
        """openrouter/free ist der Router: er waehlt automatisch ein freies,
        verfuegbares Modell. Einzelne Modell-IDs sind unzuverlaessig (404/402)."""
        return ["openrouter/free"]

    def chat(self, messages, max_tokens=None):
        """Echter Chat-Call an OpenRouter. Gibt immer Text zurueck.

        Wichtig: Auch bei Fehlern wird ein lesbarer Text geliefert, damit die
        GUI nie haengen bleibt. Der Aufrufer bekommt keine None.
        """
        from core import config
        if max_tokens is None:
            max_tokens = config.ASSISTANT_MAX_TOKENS
        if not config.ASSISTANT_ENABLED or not self.is_active():
            return ("[OpenRouter inaktiv] Kein gueltiger Key in "
                    "wallet/openrouter_key.json gefunden.")
        payload = {
            "model": "openrouter/free",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {self.get_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/sschknn/autonom-automatum",
            "X-Title": "autonom-automatum",
        }
        try:
            import requests
            r = requests.post(f"{self.config['base_url']}/chat/completions",
                              headers=headers, json=payload, timeout=60)
            if r.status_code != 200:
                return (f"[OpenRouter HTTP {r.status_code}] {r.text[:200]}\n\n"
                        "Der Free-Router ist oft ueberlastet - bitte erneut versuchen.")
            data = r.json()
            inhalt = data["choices"][0]["message"]["content"]
            return inhalt if inhalt and inhalt.strip() else "[Leere Antwort vom Modell]"
        except Exception as exc:
            return f"[Verbindungsfehler zu OpenRouter: {exc}]"

    def report(self):
        return (f"OpenRouter Status: {'AKTIV' if self.is_active() else 'INAKTIV'} | "
                f"Key-Präfix: {self.get_key()[:15]}... | "
                f"Free Models: {len(self.get_models_available())}")
