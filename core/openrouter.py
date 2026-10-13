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
        # Free-Modelle über OpenRouter (Router verteilt auf verschiedene Anbieter)
        return [
            "mistralai/mistral-7b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
            "qwen/qwen-2.5-7b-instruct",
            "google/gemma-2-9b-it"
        ]

    def report(self):
        return (f"OpenRouter Status: {'AKTIV' if self.is_active() else 'INAKTIV'} | "
                f"Key-Präfix: {self.get_key()[:15]}... | "
                f"Free Models: {len(self.get_models_available())}")
