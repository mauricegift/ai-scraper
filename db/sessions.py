"""
Session storage backend.

Automatically selects the storage engine at startup:
  - PostgreSQL  — when DATABASE_URL environment variable is set
  - JSON file   — fallback when DATABASE_URL is absent

Public interface (module-level singleton `store`):
  store.get(session_id)                     → list[dict]
  store.save(session_id, messages, turns)   → None
  store.delete(session_id)                  → None
  store.delete_all()                        → None
  store.list_all()                          → dict[str, dict]
  store.backend                             → "postgres" | "json"
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

DATABASE_URL: str | None = os.environ.get("DATABASE_URL")
_JSON_FILE = Path(__file__).parent.parent / "sessions_store.json"

# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL backend
# ─────────────────────────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ai_sessions (
    session_id  VARCHAR(255)  PRIMARY KEY,
    messages    JSONB         NOT NULL DEFAULT '[]',
    turns       INTEGER       NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_sessions_updated
    ON ai_sessions (updated_at DESC);
"""


class _PostgresStore:
    """PostgreSQL-backed session storage using psycopg2."""

    def __init__(self, dsn: str):
        import psycopg2
        import psycopg2.extras
        self._psycopg2 = psycopg2
        self._extras = psycopg2.extras
        self._dsn = dsn
        self._conn = None
        self._connect()
        self._ensure_table()
        log.info("SessionStore: connected to PostgreSQL")

    # ── Internal connection helpers ───────────────────────────────────────────

    def _connect(self):
        self._conn = self._psycopg2.connect(self._dsn)
        self._conn.autocommit = True

    def _cursor(self):
        """Return a DictCursor, reconnecting if the connection dropped."""
        try:
            self._conn.isolation_level  # cheap liveness check
        except Exception:
            log.warning("PostgreSQL connection lost — reconnecting…")
            self._connect()
        return self._conn.cursor(cursor_factory=self._extras.RealDictCursor)

    def _ensure_table(self):
        with self._cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def backend(self) -> str:
        return "postgres"

    def get(self, session_id: str) -> list:
        """Return the message list for a session, creating it if necessary."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT messages FROM ai_sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if row:
                return row["messages"] if isinstance(row["messages"], list) else json.loads(row["messages"])
            # Auto-create an empty session row
            cur.execute(
                "INSERT INTO ai_sessions (session_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (session_id,),
            )
            return []

    def save(self, session_id: str, messages: list, turns: int = 0) -> None:
        """Upsert the session messages and turn count."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_sessions (session_id, messages, turns, updated_at)
                VALUES (%s, %s::jsonb, %s, NOW())
                ON CONFLICT (session_id) DO UPDATE
                    SET messages   = EXCLUDED.messages,
                        turns      = EXCLUDED.turns,
                        updated_at = NOW()
                """,
                (session_id, json.dumps(messages), turns),
            )

    def delete(self, session_id: str) -> None:
        """Delete a single session."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM ai_sessions WHERE session_id = %s", (session_id,))

    def delete_all(self) -> None:
        """Delete every session row."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM ai_sessions")

    def list_all(self) -> dict:
        """Return a dict of {session_id: {turns, created_at, updated_at, message_count}}."""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT session_id,
                       turns,
                       created_at,
                       updated_at,
                       jsonb_array_length(messages) AS message_count
                FROM ai_sessions
                ORDER BY updated_at DESC
                """
            )
            rows = cur.fetchall()
        return {
            r["session_id"]: {
                "turns": r["turns"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                "message_count": r["message_count"] or 0,
            }
            for r in rows
        }


# ─────────────────────────────────────────────────────────────────────────────
# JSON file backend (fallback)
# ─────────────────────────────────────────────────────────────────────────────

class _JsonStore:
    """JSON file-backed session storage. Survives server restarts."""

    def __init__(self, path: Path):
        self._path = path
        self._sessions: dict[str, list] = {}
        self._meta: dict[str, dict] = {}
        self._load()
        log.info(f"SessionStore: using JSON file at {self._path} ({len(self._sessions)} sessions loaded)")

    @property
    def backend(self) -> str:
        return "json"

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._sessions = data.get("sessions", {})
            self._meta = data.get("meta", {})
        except Exception as exc:
            log.warning(f"Could not load sessions from {self._path}: {exc}")

    def _flush(self) -> None:
        try:
            self._path.write_text(
                json.dumps({"sessions": self._sessions, "meta": self._meta})
            )
        except Exception as exc:
            log.warning(f"Could not save sessions to {self._path}: {exc}")

    def get(self, session_id: str) -> list:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
            self._meta[session_id] = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "turns": 0,
            }
        return self._sessions[session_id]

    def save(self, session_id: str, messages: list, turns: int = 0) -> None:
        self._sessions[session_id] = messages
        meta = self._meta.setdefault(session_id, {
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        meta["turns"] = turns
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._flush()

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._meta.pop(session_id, None)
        self._flush()

    def delete_all(self) -> None:
        self._sessions.clear()
        self._meta.clear()
        self._flush()

    def list_all(self) -> dict:
        result = {}
        for sid, msgs in self._sessions.items():
            m = self._meta.get(sid, {})
            result[sid] = {
                "turns": m.get("turns", 0),
                "created_at": m.get("created_at"),
                "updated_at": m.get("updated_at"),
                "message_count": len(msgs),
            }
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton — import this everywhere
# ─────────────────────────────────────────────────────────────────────────────

def _init_store():
    if DATABASE_URL:
        try:
            return _PostgresStore(DATABASE_URL)
        except Exception as exc:
            log.error(
                f"Failed to connect to PostgreSQL ({exc}). "
                "Falling back to JSON file storage."
            )
    return _JsonStore(_JSON_FILE)


store = _init_store()
