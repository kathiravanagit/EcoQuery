import os
import sqlite3
import datetime
import logging
import uuid

logger = logging.getLogger("EcoQuery.key_manager")

DB_PATH = os.path.join(os.path.dirname(__file__), "keys.db")

class KeyManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # API Keys table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    key_value TEXT NOT NULL,
                    provider TEXT NOT NULL, 
                    role TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT 1,
                    daily_limit INTEGER DEFAULT 1000,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP
                )
            ''')
            
            # Usage Log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT NOT NULL,
                    provider TEXT,
                    model TEXT,
                    tokens INTEGER,
                    status TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(key_id) REFERENCES api_keys(id)
                )
            ''')
            conn.commit()
            
            self._sync_environment_keys()

    def _sync_environment_keys(self):
        """Add environment keys that are not already in the persistent key pool."""
        environment_keys = (
            (os.getenv("OPENROUTER_API_KEY", ""), "openrouter"),
            (os.getenv("OPENROUTER_API_KEY_2", ""), "openrouter"),
            (os.getenv("GROK_API_KEY", ""), "grok"),
            (os.getenv("GOOGLE_API_KEY", ""), "google"),
        )

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for key_value, provider in environment_keys:
                if not key_value:
                    continue
                cursor.execute(
                    "SELECT 1 FROM api_keys WHERE key_value = ? AND provider = ?",
                    (key_value, provider),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        INSERT INTO api_keys (id, key_value, provider, role, daily_limit)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (str(uuid.uuid4()), key_value, provider, "user", 1000),
                    )
                    logger.info("Added %s API key from environment", provider)
            conn.commit()

    def add_key(self, key_value: str, provider: str, role: str = 'user', daily_limit: int = 1000):
        key_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO api_keys (id, key_value, provider, role, daily_limit)
                VALUES (?, ?, ?, ?, ?)
            ''', (key_id, key_value, provider, role, daily_limit))
            conn.commit()
        return key_id

    def get_active_keys(self, provider: str = None) -> list:
        """Get all active keys, optionally filtered by provider."""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if provider:
                cursor.execute("SELECT * FROM api_keys WHERE is_active = 1 AND provider = ?", (provider,))
            else:
                cursor.execute("SELECT * FROM api_keys WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]
            
    def check_rate_limit(self, key_id: str) -> bool:
        """Check if the key has exceeded its daily limit."""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT daily_limit FROM api_keys WHERE id = ?
            ''', (key_id,))
            row = cursor.fetchone()
            if not row:
                return False
            daily_limit = row[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM usage_logs 
                WHERE key_id = ? AND date(timestamp) = ? AND status = 'success'
            ''', (key_id, today))
            current_usage = cursor.fetchone()[0]
            
            return current_usage < daily_limit

    def log_usage(self, key_id: str, provider: str, model: str, tokens: int, status: str):
        """Log API key usage for auditing and throttling."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO usage_logs (key_id, provider, model, tokens, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (key_id, provider, model, tokens, status))
            
            if status == 'success':
                cursor.execute('''
                    UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?
                ''', (key_id,))
            conn.commit()

    def mark_key_inactive(self, key_id: str):
        """Mark a key as inactive (e.g., if it's expired or rate limited)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE api_keys SET is_active = 0 WHERE id = ?
            ''', (key_id,))
            conn.commit()
            
    def get_all_providers_keys(self) -> dict:
        """Get a grouped dictionary of all active keys by provider."""
        active_keys = self.get_active_keys()
        grouped = {}
        for key in active_keys:
            if not self.check_rate_limit(key["id"]):
                continue
            prov = key["provider"]
            if prov not in grouped:
                grouped[prov] = []
            grouped[prov].append(key)
        return grouped

key_manager = KeyManager()
