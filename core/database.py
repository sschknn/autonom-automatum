"""SQLite-Datenbank-Setup und Persistenz für autonom-automatum."""
import sqlite3
import os
from core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    result_path TEXT,
    energy_cost REAL DEFAULT 0.0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS budget (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance REAL DEFAULT 100.0,
    last_regen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_earned REAL DEFAULT 0.0,
    total_spent REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level TEXT,
    message TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_budget_id ON budget(id);
"""

class Database:
    def __init__(self, path=config.DB_PATH):
        self.path = path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        os.makedirs(os.path.dirname(self.path) if os.path.dirname(self.path) else ".", exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            # Budget-Initialisierung
            conn.execute("INSERT OR IGNORE INTO budget (id, balance, total_earned, total_spent) VALUES (1, ?, 0.0, 0.0)", (config.INITIAL_BUDGET,))
            conn.commit()

    # --- Budget ---
    def get_budget(self):
        with self._connect() as conn:
            row = conn.execute("SELECT balance, total_earned, total_spent FROM budget WHERE id = 1").fetchone()
            return dict(row) if row else {"balance": 0.0, "total_earned": 0.0, "total_spent": 0.0}

    def update_budget(self, delta, earn=0.0, spend=0.0):
        with self._connect() as conn:
            conn.execute(
                "UPDATE budget SET balance = balance + ?, total_earned = total_earned + ?, total_spent = total_spent + ? WHERE id = 1",
                (delta, earn, spend)
            )
            conn.commit()

    def reset_regen_time(self):
        with self._connect() as conn:
            conn.execute("UPDATE budget SET last_regen = CURRENT_TIMESTAMP WHERE id = 1")
            conn.commit()

    # --- Tasks ---
    def insert_task(self, source_file):
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (source_file, status, energy_cost) VALUES (?, 'pending', 0.0)",
                (source_file,)
            )
            conn.commit()
            return cur.lastrowid

    def get_pending_tasks(self, limit=10):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def complete_task(self, task_id, result_path, energy_cost):
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'completed', processed_at = CURRENT_TIMESTAMP, result_path = ?, energy_cost = ? WHERE id = ?",
                (result_path, energy_cost, task_id)
            )
            conn.commit()

    def fail_task(self, task_id, error_message, energy_cost=0.0):
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'failed', error_message = ?, energy_cost = ? WHERE id = ?",
                (error_message, energy_cost, task_id)
            )
            conn.commit()

    # --- Logging ---
    def log(self, level, message):
        with self._connect() as conn:
            conn.execute("INSERT INTO logs (level, message) VALUES (?, ?)", (level, message))
            conn.commit()
