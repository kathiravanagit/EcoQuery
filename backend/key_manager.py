import os
import sqlite3
import datetime
import logging
import uuid
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

logger = logging.getLogger("EcoQuery.key_manager")

DB_PATH = os.path.join(os.path.dirname(__file__), "keys.db")

# The store is built at import time, so the secret encrypting it must already
# be in the environment before the first `KeyManager` is constructed. main.py
# loads the same file, but `key_manager` can be imported first (tests,
# scripts) — and encrypting with the fallback string makes every row unreadable
# the moment the real KEY_ENCRYPTION_KEY/JWT_SECRET shows up, which is how a
# local keys.db ended up holding provider keys nothing could decrypt.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

class KeyManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        encryption_secret = os.getenv("KEY_ENCRYPTION_KEY") or os.getenv("JWT_SECRET") or "ecoquery-development-only-key"
        derived_key = base64.urlsafe_b64encode(hashlib.sha256(encryption_secret.encode()).digest())
        self._fernet = Fernet(derived_key)
        self._init_db()

    def _encrypt(self, value: str) -> str:
        return "enc:" + self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str | None:
        try:
            if not value.startswith("enc:"):
                return None
            return self._fernet.decrypt(value[4:].encode()).decode()
        except (InvalidToken, UnicodeDecodeError):
            return None

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
            self._migrate_plaintext_keys(cursor)
            conn.commit()
            self._seed_initial_keys()

    def _migrate_plaintext_keys(self, cursor):
        """Encrypt legacy rows in place; plaintext values are never returned."""
        cursor.execute("SELECT id, key_value FROM api_keys WHERE key_value NOT LIKE 'enc:%'")
        legacy_rows = cursor.fetchall()
        for key_id, key_value in legacy_rows:
            cursor.execute("UPDATE api_keys SET key_value = ? WHERE id = ?", (self._encrypt(key_value), key_id))
        if legacy_rows:
            logger.warning("Encrypted %d legacy provider key(s) at rest", len(legacy_rows))

    # Credentials the process is told about through the environment: every
    # provider EcoQuery can fail over to.
    ENV_KEYS = (
        ("OPENROUTER_API_KEY", "openrouter"),
        ("OPENROUTER_API_KEY_2", "openrouter"),
        ("GOOGLE_API_KEY", "google"),
        ("GROK_API_KEY", "grok"),
    )

    def _seed_initial_keys(self):
        """Ensure every credential in the environment is in the key store.

        Runs on every start rather than only when the table is empty. The store
        is a file that outlives a configuration change, so seeding once meant
        editing `GOOGLE_API_KEY` had no effect until `keys.db` was deleted by
        hand — and the OpenRouter failover would keep calling the previous,
        often quota-exhausted, credential. A credential already stored is left
        alone, so this never duplicates a row and never revives a key that was
        deliberately marked inactive.
        """
        wanted = []
        for env_name, provider in self.ENV_KEYS:
            value = os.getenv(env_name, "")
            if value:
                wanted.append((value, provider))
        if not wanted:
            return

        known = self._stored_key_values()
        added = 0
        for key_value, provider in wanted:
            if key_value in known:
                continue
            self.add_key(key_value, provider)
            known.add(key_value)
            added += 1
        if added:
            logger.info("Seeded %d provider key(s) from the environment", added)

    def _stored_key_values(self) -> set:
        """Every stored credential we can still decrypt, active or not.

        Rows that cannot be decrypted are deliberately left out: they are
        skipped at runtime, so an env credential has to be inserted beside
        them or it would never be used. Inactive rows do count — a key marked
        inactive after a provider rejection is still stored, and re-adding it
        would duplicate it on every boot instead of letting the operator
        repair it in place.
        """
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT key_value FROM api_keys")
            known = set()
            for row in cursor.fetchall():
                decrypted = self._decrypt(row["key_value"])
                if decrypted:
                    known.add(decrypted)
            return known

    def add_key(self, key_value: str, provider: str, role: str = 'user', daily_limit: int = 1000):
        key_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO api_keys (id, key_value, provider, role, daily_limit)
                VALUES (?, ?, ?, ?, ?)
            ''', (key_id, self._encrypt(key_value), provider, role, daily_limit))
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
            keys = []
            for row in cursor.fetchall():
                item = dict(row)
                decrypted = self._decrypt(item["key_value"])
                if decrypted is None:
                    logger.error("Skipping provider key %s because it cannot be decrypted", item["id"])
                    continue
                item["key_value"] = decrypted
                keys.append(item)
            return keys
            
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
