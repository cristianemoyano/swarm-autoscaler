import os
import sqlite3
import logging
from time import time
from typing import Dict, List, Optional


class EventsStore:
    """SQLite-backed store (multi-process safe within a node)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("EVENTS_DB_PATH", "/app/events.db")
        self.logger = logging.getLogger("EventsStore")
        # Maximum rows to keep; oldest rows are evicted when limit is exceeded
        try:
            self.max_events = int(os.getenv("EVENTS_MAX_ROWS", "10000"))
        except ValueError:
            self.max_events = 10000
        # Services cache (per-process) – invalidated on writes
        self._services_cache: Optional[list[str]] = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            isolation_level=None,  # autocommit
            check_same_thread=False,
        )
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            self.logger.warning("Failed to set SQLite pragmas", exc_info=True)
        return conn

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    serviceId TEXT NOT NULL,
                    service TEXT NOT NULL,
                    old INTEGER NOT NULL,
                    new INTEGER NOT NULL,
                    delta INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    reason TEXT,
                    metric TEXT,
                    dryRun INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_service ON events(service);")

    def add_scale_event(
        self,
        *,
        service_id: str,
        service_name: str,
        old_replicas: int,
        new_replicas: int,
        reason: str = "",
        metric: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        ts = time()
        delta = int(new_replicas) - int(old_replicas)
        direction = "up" if delta > 0 else ("down" if delta < 0 else "same")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (ts, serviceId, service, old, new, delta, direction, reason, metric, dryRun)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    service_id,
                    service_name,
                    int(old_replicas),
                    int(new_replicas),
                    delta,
                    direction,
                    reason,
                    metric,
                    1 if dry_run else 0,
                ),
            )
            self._enforce_retention(conn)
        # Invalidate services cache
        self._services_cache = None

    def list_events(
        self,
        limit: int = 100,
        service: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        offset: int = 0,
    ) -> List[Dict]:
        q = "SELECT ts, serviceId, service, old, new, delta, direction, reason, metric, dryRun FROM events"
        where = []
        args: List = []
        if service:
            where.append("service = ?")
            args.append(service)
        if since is not None:
            where.append("ts >= ?")
            args.append(float(since))
        if until is not None:
            where.append("ts <= ?")
            args.append(float(until))
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY ts DESC LIMIT ? OFFSET ?"
        args.append(int(limit))
        args.append(int(max(0, offset)))
        with self._connect() as conn:
            rows = conn.execute(q, args).fetchall()
        def to_obj(r):
            return {
                "ts": r[0],
                "serviceId": r[1],
                "service": r[2],
                "old": r[3],
                "new": r[4],
                "delta": r[5],
                "direction": r[6],
                "reason": r[7],
                "metric": r[8],
                "dryRun": bool(r[9]),
            }
        return [to_obj(r) for r in rows]

    def count_events(
        self,
        service: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> int:
        q = "SELECT COUNT(*) FROM events"
        where = []
        args: List = []
        if service:
            where.append("service = ?")
            args.append(service)
        if since is not None:
            where.append("ts >= ?")
            args.append(float(since))
        if until is not None:
            where.append("ts <= ?")
            args.append(float(until))
        if where:
            q += " WHERE " + " AND ".join(where)
        with self._connect() as conn:
            row = conn.execute(q, args).fetchone()
        return int(row[0] if row else 0)

    def clear(self, service: Optional[str] = None) -> int:
        q = "DELETE FROM events"
        args: List = []
        if service:
            q += " WHERE service = ?"
            args.append(service)
        with self._connect() as conn:
            cur = conn.execute(q, args)
            return cur.rowcount if cur.rowcount is not None else 0
        # Invalidate services cache
        self._services_cache = None

    def _enforce_retention(self, conn: sqlite3.Connection) -> None:
        """Delete oldest rows so only the most recent max_events remain."""
        try:
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            overflow = int(total) - int(self.max_events)
            if overflow > 0:
                conn.execute(
                    "DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY ts ASC LIMIT ?)",
                    (overflow,),
                )
        except Exception:
            self.logger.warning("Failed to enforce events retention", exc_info=True)

    def list_services(self) -> List[str]:
        if self._services_cache is not None:
            return list(self._services_cache)
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT service FROM events ORDER BY service ASC").fetchall()
        services = [r[0] for r in rows]
        self._services_cache = services
        return services


Events = EventsStore()
