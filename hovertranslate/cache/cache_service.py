# HOVERTRANSLATE skeleton file
from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from pathlib import Path

from hovertranslate.core.errors import CacheError


SCHEMA_VERSION = 1
POLICY_VERSION = 1
MAX_ENTRIES_DEFAULT = 10_000
MAX_BYTES_DEFAULT = 20 * 1024 * 1024


class CacheService:
    """SQLite-backed LRU translation cache."""

    def __init__(
        self,
        db_path: Path,
        ttl_seconds: int = 72 * 60 * 60,
        max_entries: int = MAX_ENTRIES_DEFAULT,
        max_bytes: int = MAX_BYTES_DEFAULT,
    ) -> None:
        self._db_path = db_path
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._lock = threading.RLock()

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._configure_connection()
        self._create_schema()

    def _configure_connection(self) -> None:
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")
        self._conn.execute("PRAGMA foreign_keys = ON;")

    def _create_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key_hash         TEXT PRIMARY KEY,
                    source_text_hash TEXT NOT NULL,
                    direction        TEXT NOT NULL,
                    provider         TEXT NOT NULL,
                    lang_pair        TEXT NOT NULL,
                    policy_version   INTEGER NOT NULL DEFAULT 1,
                    result           TEXT NOT NULL,
                    created_at       INTEGER NOT NULL,
                    expires_at       INTEGER NOT NULL,
                    last_used_at     INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_cache_lru
                    ON cache (last_used_at);

                CREATE INDEX IF NOT EXISTS idx_cache_exp
                    ON cache (expires_at);
                """
            )
            self._conn.commit()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _make_key(
        self,
        text: str,
        direction: str,
        provider: str,
        lang_pair: str,
    ) -> str:
        material = "|".join(
            [
                text,
                direction,
                provider,
                lang_pair,
                str(POLICY_VERSION),
            ]
        )
        return self._hash(material)

    def get(
        self,
        text: str,
        direction: str,
        provider: str,
        lang_pair: str,
    ) -> str | None:
        key_hash = self._make_key(text, direction, provider, lang_pair)
        now = int(time.time())

        with self._lock:
            row = self._conn.execute(
                """
                SELECT result, expires_at
                FROM cache
                WHERE key_hash = ?
                """,
                (key_hash,),
            ).fetchone()

            if row is None:
                return None

            result, expires_at = row
            if expires_at < now:
                self._conn.execute(
                    "DELETE FROM cache WHERE key_hash = ?",
                    (key_hash,),
                )
                self._conn.commit()
                return None

            self._conn.execute(
                """
                UPDATE cache
                SET last_used_at = ?
                WHERE key_hash = ?
                """,
                (now, key_hash),
            )
            self._conn.commit()
            return str(result)

    def put(
        self,
        text: str,
        direction: str,
        provider: str,
        lang_pair: str,
        result: str,
    ) -> None:
        key_hash = self._make_key(text, direction, provider, lang_pair)
        source_hash = self._hash(text)
        now = int(time.time())
        expires_at = now + self._ttl_seconds

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cache (
                    key_hash,
                    source_text_hash,
                    direction,
                    provider,
                    lang_pair,
                    policy_version,
                    result,
                    created_at,
                    expires_at,
                    last_used_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key_hash) DO UPDATE SET
                    result = excluded.result,
                    expires_at = excluded.expires_at,
                    last_used_at = excluded.last_used_at
                """,
                (
                    key_hash,
                    source_hash,
                    direction,
                    provider,
                    lang_pair,
                    POLICY_VERSION,
                    result,
                    now,
                    expires_at,
                    now,
                ),
            )
            self._conn.commit()
            self.evict_expired()
            self._enforce_limits()

    def evict_expired(self) -> None:
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (now,),
            )
            self._conn.commit()

    def _enforce_limits(self) -> None:
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) FROM cache"
            ).fetchone()[0]

            if count > self._max_entries:
                excess = int(count) - self._max_entries
                self._conn.execute(
                    """
                    DELETE FROM cache
                    WHERE key_hash IN (
                        SELECT key_hash
                        FROM cache
                        ORDER BY last_used_at ASC
                        LIMIT ?
                    )
                    """,
                    (excess,),
                )
                self._conn.commit()

            db_bytes = self._approximate_db_bytes()
            if db_bytes > self._max_bytes:
                self._conn.execute(
                    """
                    DELETE FROM cache
                    WHERE key_hash IN (
                        SELECT key_hash
                        FROM cache
                        ORDER BY last_used_at ASC
                        LIMIT (
                            SELECT COUNT(*) / 4
                            FROM cache
                        )
                    )
                    """
                )
                self._conn.commit()
                self._conn.execute("VACUUM")

    def _approximate_db_bytes(self) -> int:
        page_count = self._conn.execute(
            "PRAGMA page_count"
        ).fetchone()[0]
        page_size = self._conn.execute(
            "PRAGMA page_size"
        ).fetchone()[0]
        return int(page_count) * int(page_size)

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.commit()
            except sqlite3.Error:
                pass
            self._conn.close()

    def __enter__(self) -> "CacheService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()