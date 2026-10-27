"""Modul persistensi SQLite (state.db): migrasi skema dan repository LedgerStore."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from .models import EntryRecord, EvidenceItem, NoteRecord, RunRecord, Status

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id       TEXT PRIMARY KEY,
            work_date    TEXT NOT NULL,
            stage        TEXT NOT NULL,
            status       TEXT NOT NULL,
            started_at   TEXT NOT NULL,
            finished_at  TEXT,
            tokens_in    INTEGER NOT NULL DEFAULT 0,
            tokens_out   INTEGER NOT NULL DEFAULT 0,
            duration_ms  INTEGER NOT NULL DEFAULT 0,
            error_code   TEXT
        );

        CREATE TABLE IF NOT EXISTS entries (
            work_date      TEXT PRIMARY KEY,
            draft_json     TEXT NOT NULL,
            approved_json  TEXT,
            prompt_version TEXT,
            model          TEXT,
            edit_ratio     REAL,
            content_hash   TEXT,
            portal_status  TEXT,
            approved_at    TEXT,
            submitted_at   TEXT,
            verified_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS evidence (
            id         TEXT NOT NULL,
            work_date  TEXT NOT NULL,
            source     TEXT NOT NULL,
            kind       TEXT NOT NULL,
            ts         TEXT NOT NULL,
            title      TEXT NOT NULL,
            detail     TEXT NOT NULL DEFAULT '',
            strength   TEXT NOT NULL,
            PRIMARY KEY (work_date, id)
        );

        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            work_date  TEXT NOT NULL,
            kind       TEXT NOT NULL CHECK (kind IN ('aktivitas','pembelajaran','kendala')),
            text       TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_runs_date ON runs(work_date);
        CREATE INDEX IF NOT EXISTS idx_evidence_date ON evidence(work_date);
        CREATE INDEX IF NOT EXISTS idx_notes_date ON notes(work_date);
        """,
    ),
]


def _format_datetime(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _parse_datetime(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _format_date(d: date) -> str:
    return d.isoformat()


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


class LedgerStore:
    """Repository SQLite untuk audit run, entri logbook, bukti, dan catatan."""

    def __init__(self, db_path: Path | str = "data/state.db", auto_migrate: bool = True) -> None:
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else db_path
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._active_conn: sqlite3.Connection | None = None
        if auto_migrate:
            self.migrate()

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if str(self.db_path) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _commit_if_auto(self, conn: sqlite3.Connection) -> None:
        """Melakukan commit hanya bila operasi tidak berada di dalam blok transaction() aktif."""
        if self._active_conn is None:
            conn.commit()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Menyediakan koneksi aktif. Jika sedang dalam transaksi, gunakan koneksi transaksi."""
        if self._active_conn is not None:
            yield self._active_conn
        else:
            conn = self._open_connection()
            try:
                yield conn
            finally:
                conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Mengelola transaksi atomik dengan commit otomatis atau rollback jika terjadi exception."""
        if self._active_conn is not None:
            yield self._active_conn
            return

        conn = self._open_connection()
        self._active_conn = conn
        try:
            conn.execute("BEGIN;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._active_conn = None
            conn.close()

    def migrate(self) -> None:
        """Menjalankan migrasi skema database yang belum diterapkan."""
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            applied = {
                row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
            }

            for version, sql_ddl in MIGRATIONS:
                if version not in applied:
                    conn.executescript(sql_ddl)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                        (version, datetime.now().isoformat()),
                    )
            self._commit_if_auto(conn)

    # --- Operasi Runs ---

    def record_run(self, run: RunRecord) -> None:
        """Menyimpan atau memperbarui rekam jejak eksekusi pipeline."""
        sql = """
        INSERT INTO runs (
            run_id, work_date, stage, status, started_at, finished_at,
            tokens_in, tokens_out, duration_ms, error_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            stage = excluded.stage,
            status = excluded.status,
            finished_at = excluded.finished_at,
            tokens_in = excluded.tokens_in,
            tokens_out = excluded.tokens_out,
            duration_ms = excluded.duration_ms,
            error_code = excluded.error_code;
        """
        with self.connection() as conn:
            conn.execute(
                sql,
                (
                    run.run_id,
                    _format_date(run.work_date),
                    run.stage,
                    str(run.status),
                    _format_datetime(run.started_at),
                    _format_datetime(run.finished_at),
                    run.tokens_in,
                    run.tokens_out,
                    run.duration_ms,
                    run.error_code,
                ),
            )
            self._commit_if_auto(conn)

    def get_run(self, run_id: str) -> RunRecord | None:
        """Mengambil RunRecord berdasarkan run_id."""
        sql = "SELECT * FROM runs WHERE run_id = ?;"
        with self.connection() as conn:
            row = conn.execute(sql, (run_id,)).fetchone()
            if row is None:
                return None
            return RunRecord(
                run_id=row["run_id"],
                work_date=_parse_date(row["work_date"]),
                stage=row["stage"],
                status=Status(row["status"])
                if row["status"] in Status.__members__
                else row["status"],
                started_at=_parse_datetime(row["started_at"]) or datetime.now(),
                finished_at=_parse_datetime(row["finished_at"]),
                tokens_in=row["tokens_in"],
                tokens_out=row["tokens_out"],
                duration_ms=row["duration_ms"],
                error_code=row["error_code"],
            )

    def get_runs_for_date(self, work_date: date) -> list[RunRecord]:
        """Mengambil seluruh rekam jejak run untuk tanggal tertentu."""
        sql = "SELECT * FROM runs WHERE work_date = ? ORDER BY started_at ASC;"
        with self.connection() as conn:
            rows = conn.execute(sql, (_format_date(work_date),)).fetchall()
            return [
                RunRecord(
                    run_id=r["run_id"],
                    work_date=_parse_date(r["work_date"]),
                    stage=r["stage"],
                    status=Status(r["status"])
                    if r["status"] in Status.__members__
                    else r["status"],
                    started_at=_parse_datetime(r["started_at"]) or datetime.now(),
                    finished_at=_parse_datetime(r["finished_at"]),
                    tokens_in=r["tokens_in"],
                    tokens_out=r["tokens_out"],
                    duration_ms=r["duration_ms"],
                    error_code=r["error_code"],
                )
                for r in rows
            ]

    # --- Operasi Entries ---

    def save_entry(self, entry: EntryRecord) -> None:
        """Menyimpan atau memperbarui entri logbook dengan strategi upsert."""
        sql = """
        INSERT INTO entries (
            work_date, draft_json, approved_json, prompt_version, model,
            edit_ratio, content_hash, portal_status, approved_at, submitted_at, verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(work_date) DO UPDATE SET
            draft_json = excluded.draft_json,
            approved_json = COALESCE(excluded.approved_json, entries.approved_json),
            prompt_version = COALESCE(excluded.prompt_version, entries.prompt_version),
            model = COALESCE(excluded.model, entries.model),
            edit_ratio = COALESCE(excluded.edit_ratio, entries.edit_ratio),
            content_hash = COALESCE(excluded.content_hash, entries.content_hash),
            portal_status = COALESCE(excluded.portal_status, entries.portal_status),
            approved_at = COALESCE(excluded.approved_at, entries.approved_at),
            submitted_at = COALESCE(excluded.submitted_at, entries.submitted_at),
            verified_at = COALESCE(excluded.verified_at, entries.verified_at);
        """
        with self.connection() as conn:
            conn.execute(
                sql,
                (
                    _format_date(entry.work_date),
                    entry.draft_json,
                    entry.approved_json,
                    entry.prompt_version,
                    entry.model,
                    entry.edit_ratio,
                    entry.content_hash,
                    entry.portal_status,
                    _format_datetime(entry.approved_at),
                    _format_datetime(entry.submitted_at),
                    _format_datetime(entry.verified_at),
                ),
            )
            self._commit_if_auto(conn)

    def insert_entry_strict(self, entry: EntryRecord) -> None:
        """Menyisipkan entri baru tanpa upsert; gagal bila work_date sudah ada."""
        sql = """
        INSERT INTO entries (
            work_date, draft_json, approved_json, prompt_version, model,
            edit_ratio, content_hash, portal_status, approved_at, submitted_at, verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.connection() as conn:
            conn.execute(
                sql,
                (
                    _format_date(entry.work_date),
                    entry.draft_json,
                    entry.approved_json,
                    entry.prompt_version,
                    entry.model,
                    entry.edit_ratio,
                    entry.content_hash,
                    entry.portal_status,
                    _format_datetime(entry.approved_at),
                    _format_datetime(entry.submitted_at),
                    _format_datetime(entry.verified_at),
                ),
            )
            self._commit_if_auto(conn)

    def get_entry(self, work_date: date) -> EntryRecord | None:
        """Mengambil entri logbook untuk tanggal tertentu."""
        sql = "SELECT * FROM entries WHERE work_date = ?;"
        with self.connection() as conn:
            row = conn.execute(sql, (_format_date(work_date),)).fetchone()
            if row is None:
                return None
            return EntryRecord(
                work_date=_parse_date(row["work_date"]),
                draft_json=row["draft_json"],
                approved_json=row["approved_json"],
                prompt_version=row["prompt_version"],
                model=row["model"],
                edit_ratio=row["edit_ratio"],
                content_hash=row["content_hash"],
                portal_status=row["portal_status"],
                approved_at=_parse_datetime(row["approved_at"]),
                submitted_at=_parse_datetime(row["submitted_at"]),
                verified_at=_parse_datetime(row["verified_at"]),
            )

    def get_approved_entries(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[EntryRecord]:
        """Mengambil seluruh entri yang sudah disetujui (approved_json IS NOT NULL)

        secara kronologis berdasarkan work_date, dengan filter opsional rentang tanggal.
        """
        clauses = ["approved_json IS NOT NULL"]
        params: list[str] = []

        if from_date is not None:
            clauses.append("work_date >= ?")
            params.append(_format_date(from_date))

        if to_date is not None:
            clauses.append("work_date <= ?")
            params.append(_format_date(to_date))

        where_sql = " AND ".join(clauses)
        sql = f"SELECT * FROM entries WHERE {where_sql} ORDER BY work_date ASC;"

        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [
                EntryRecord(
                    work_date=_parse_date(row["work_date"]),
                    draft_json=row["draft_json"],
                    approved_json=row["approved_json"],
                    prompt_version=row["prompt_version"],
                    model=row["model"],
                    edit_ratio=row["edit_ratio"],
                    content_hash=row["content_hash"],
                    portal_status=row["portal_status"],
                    approved_at=_parse_datetime(row["approved_at"]),
                    submitted_at=_parse_datetime(row["submitted_at"]),
                    verified_at=_parse_datetime(row["verified_at"]),
                )
                for row in rows
            ]

    def update_entry_approval(
        self,
        work_date: date,
        approved_json: str,
        approved_at: datetime,
        edit_ratio: float | None = None,
    ) -> None:
        """Memperbarui teks disetujui, timestamp persetujuan, dan rasio edit."""
        sql = """
        UPDATE entries
        SET approved_json = ?, approved_at = ?, edit_ratio = ?
        WHERE work_date = ?;
        """
        with self.connection() as conn:
            conn.execute(
                sql,
                (
                    approved_json,
                    _format_datetime(approved_at),
                    edit_ratio,
                    _format_date(work_date),
                ),
            )
            self._commit_if_auto(conn)

    def update_entry_submission(
        self,
        work_date: date,
        portal_status: str,
        submitted_at: datetime | None = None,
        verified_at: datetime | None = None,
    ) -> None:
        """Memperbarui status submit portal dan timestamp verifikasi."""
        sql = """
        UPDATE entries
        SET portal_status = ?,
            submitted_at = COALESCE(?, submitted_at),
            verified_at = COALESCE(?, verified_at)
        WHERE work_date = ?;
        """
        with self.connection() as conn:
            conn.execute(
                sql,
                (
                    portal_status,
                    _format_datetime(submitted_at),
                    _format_datetime(verified_at),
                    _format_date(work_date),
                ),
            )
            self._commit_if_auto(conn)

    # --- Operasi Evidence ---

    def save_evidence(self, items: list[EvidenceItem]) -> None:
        """Menyimpan butir bukti aktivitas secara batch."""
        sql = """
        INSERT INTO evidence (id, work_date, source, kind, ts, title, detail, strength)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(work_date, id) DO UPDATE SET
            source = excluded.source,
            kind = excluded.kind,
            ts = excluded.ts,
            title = excluded.title,
            detail = excluded.detail,
            strength = excluded.strength;
        """
        with self.connection() as conn:
            conn.executemany(
                sql,
                [
                    (
                        item.id,
                        _format_date(item.work_date),
                        item.source,
                        item.kind,
                        item.ts if isinstance(item.ts, str) else item.ts.isoformat(),
                        item.title,
                        item.detail,
                        item.strength,
                    )
                    for item in items
                ],
            )
            self._commit_if_auto(conn)

    def get_evidence_for_date(self, work_date: date) -> list[EvidenceItem]:
        """Mengambil seluruh bukti yang tercatat untuk tanggal tertentu."""
        sql = "SELECT * FROM evidence WHERE work_date = ? ORDER BY ts ASC;"
        with self.connection() as conn:
            rows = conn.execute(sql, (_format_date(work_date),)).fetchall()
            return [
                EvidenceItem(
                    id=r["id"],
                    work_date=_parse_date(r["work_date"]),
                    source=r["source"],
                    kind=r["kind"],
                    ts=r["ts"],
                    title=r["title"],
                    detail=r["detail"],
                    strength=r["strength"],
                )
                for r in rows
            ]

    # --- Operasi Notes ---

    def add_note(self, note: NoteRecord) -> int:
        """Menyisipkan catatan harian baru dan mengembalikan id yang dihasilkan."""
        sql = """
        INSERT INTO notes (work_date, kind, text, created_at)
        VALUES (?, ?, ?, ?);
        """
        with self.connection() as conn:
            cur = conn.execute(
                sql,
                (
                    _format_date(note.work_date),
                    note.kind,
                    note.text,
                    _format_datetime(note.created_at),
                ),
            )
            self._commit_if_auto(conn)
            return int(cur.lastrowid or 0)

    def get_notes_for_date(self, work_date: date) -> list[NoteRecord]:
        """Mengambil seluruh catatan untuk tanggal tertentu."""
        sql = "SELECT * FROM notes WHERE work_date = ? ORDER BY created_at ASC;"
        with self.connection() as conn:
            rows = conn.execute(sql, (_format_date(work_date),)).fetchall()
            return [
                NoteRecord(
                    id=r["id"],
                    work_date=_parse_date(r["work_date"]),
                    kind=r["kind"],
                    text=r["text"],
                    created_at=_parse_datetime(r["created_at"]) or datetime.now(),
                )
                for r in rows
            ]

    # Convenience aliases
    get_evidence = get_evidence_for_date
    get_notes = get_notes_for_date

    def list_runs(self, target_date: date | None = None) -> list[RunRecord]:
        """Alias untuk get_runs_for_date atau seluruh runs."""
        if target_date is not None:
            return self.get_runs_for_date(target_date)
        sql = "SELECT * FROM runs ORDER BY started_at ASC;"
        with self.connection() as conn:
            rows = conn.execute(sql).fetchall()
            return [
                RunRecord(
                    run_id=r["run_id"],
                    work_date=_parse_date(r["work_date"]),
                    stage=r["stage"],
                    status=Status(r["status"])
                    if r["status"] in Status.__members__
                    else r["status"],
                    started_at=_parse_datetime(r["started_at"]) or datetime.now(),
                    finished_at=_parse_datetime(r["finished_at"]),
                    tokens_in=r["tokens_in"],
                    tokens_out=r["tokens_out"],
                    duration_ms=r["duration_ms"],
                    error_code=r["error_code"],
                )
                for r in rows
            ]

    def set_approved(
        self,
        work_date: date,
        approved_json: str,
        approved_at: datetime,
        edit_ratio: float | None = None,
    ) -> None:
        """Memperbarui draf yang disetujui beserta rasio edit."""
        self.update_entry_approval(
            work_date=work_date,
            approved_json=approved_json,
            approved_at=approved_at,
            edit_ratio=edit_ratio,
        )

    def mark_submitted(
        self,
        work_date: date,
        portal_status: str = "BERHASIL",
        submitted_at: datetime | None = None,
    ) -> None:
        """Memperbarui status pengiriman entri."""
        self.update_entry_submission(
            work_date=work_date,
            portal_status=portal_status,
            submitted_at=submitted_at or datetime.now(),
        )

    def mark_verified(
        self,
        work_date: date,
        portal_status: str = "SUDAH_TERKIRIM",
        verified_at: datetime | None = None,
    ) -> None:
        """Memperbarui status verifikasi entri."""
        self.update_entry_submission(
            work_date=work_date,
            portal_status=portal_status,
            verified_at=verified_at or datetime.now(),
        )
