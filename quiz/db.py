import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from quiz.parser import Question

DB_PATH = Path(__file__).parent / "flashcards.db"

_USERNAME_RE = re.compile(r"^[\w\s\-]{1,30}$", re.UNICODE)


def validate_username(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Имя не может быть пустым")
    if len(name) > 30:
        raise ValueError("Имя не может быть длиннее 30 символов")
    if not _USERNAME_RE.match(name):
        raise ValueError("Имя содержит недопустимые символы (разрешены буквы, цифры, пробелы, -)")
    return name


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL UNIQUE,
            created_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT    NOT NULL,
            file_path   TEXT    NOT NULL,
            section     TEXT    NOT NULL,
            difficulty  TEXT    NOT NULL,
            file_number INTEGER NOT NULL,
            UNIQUE (file_path, file_number)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT    NOT NULL,
            ended_at   TEXT,
            scope      TEXT    NOT NULL,
            user_id    INTEGER REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS responses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES sessions(id),
            question_id INTEGER NOT NULL REFERENCES questions(id),
            rating      TEXT    NOT NULL CHECK(rating IN ('known', 'unknown', 'skip')),
            answered_at TEXT    NOT NULL
        );
    """)
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id)")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists


# ── Users ──────────────────────────────────────────────────────────────────

def create_user(conn: sqlite3.Connection, name: str) -> int:
    name = validate_username(name)
    cur = conn.execute(
        "INSERT INTO users (name, created_at) VALUES (?, ?)",
        (name, _now()),
    )
    conn.commit()
    return cur.lastrowid


def get_user_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()


def get_all_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM users ORDER BY name").fetchall()


# ── Questions ───────────────────────────────────────────────────────────────

def upsert_questions(conn: sqlite3.Connection, questions: list[Question]) -> int:
    rows = [(q.text, q.file_path, q.section, q.difficulty, q.file_number) for q in questions]
    before = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    conn.executemany(
        "INSERT OR IGNORE INTO questions (text, file_path, section, difficulty, file_number) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    return after - before


def get_questions(
    conn: sqlite3.Connection,
    file_paths: list[str] | None = None,
    section: str | None = None,
    difficulties: list[str] | None = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM questions WHERE 1=1"
    params: list = []

    if file_paths:
        placeholders = ",".join("?" * len(file_paths))
        query += f" AND file_path IN ({placeholders})"
        params.extend(file_paths)
    if section:
        query += " AND section = ?"
        params.append(section)
    if difficulties:
        conditions = " OR ".join("difficulty LIKE ?" for _ in difficulties)
        query += f" AND ({conditions})"
        params.extend(f"%{d}%" for d in difficulties)

    return conn.execute(query, params).fetchall()


# ── Sessions ────────────────────────────────────────────────────────────────

def create_session(conn: sqlite3.Connection, scope: str, user_id: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO sessions (started_at, scope, user_id) VALUES (?, ?, ?)",
        (_now(), scope, user_id),
    )
    conn.commit()
    return cur.lastrowid


def close_session(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (_now(), session_id))
    conn.commit()


def record_response(
    conn: sqlite3.Connection, session_id: int, question_id: int, rating: str
) -> None:
    if rating not in ("known", "unknown", "skip"):
        raise ValueError(f"Invalid rating: {rating!r}")
    conn.execute(
        "INSERT INTO responses (session_id, question_id, rating, answered_at) VALUES (?, ?, ?, ?)",
        (session_id, question_id, rating, _now()),
    )
    conn.commit()


def get_session_summary(conn: sqlite3.Connection, session_id: int) -> dict:
    rows = conn.execute(
        "SELECT rating, COUNT(*) as cnt FROM responses WHERE session_id = ? GROUP BY rating",
        (session_id,),
    ).fetchall()
    counts = {r["rating"]: r["cnt"] for r in rows}
    known = counts.get("known", 0)
    unknown = counts.get("unknown", 0)
    skip = counts.get("skip", 0)
    total = known + unknown + skip
    accuracy = round(known / (known + unknown) * 100) if (known + unknown) > 0 else 0
    return {"known": known, "unknown": unknown, "skip": skip, "total": total, "accuracy": accuracy}


def get_last_session_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def get_unknown_questions(conn: sqlite3.Connection, session_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT q.* FROM questions q "
        "JOIN responses r ON r.question_id = q.id "
        "WHERE r.session_id = ? AND r.rating = 'unknown'",
        (session_id,),
    ).fetchall()


# ── Leaderboard ─────────────────────────────────────────────────────────────

def get_leaderboard(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT
            u.name,
            COUNT(DISTINCT s.id)                                           AS sessions,
            COUNT(r.id)                                                    AS total,
            SUM(CASE WHEN r.rating = 'known'   THEN 1 ELSE 0 END)         AS known,
            SUM(CASE WHEN r.rating = 'unknown' THEN 1 ELSE 0 END)         AS unknown,
            ROUND(
                CAST(SUM(CASE WHEN r.rating = 'known' THEN 1 ELSE 0 END) AS REAL)
                / NULLIF(SUM(CASE WHEN r.rating IN ('known','unknown') THEN 1 ELSE 0 END), 0)
                * 100
            )                                                              AS accuracy
        FROM users u
        JOIN sessions s ON s.user_id = u.id
        JOIN responses r ON r.session_id = s.id
        GROUP BY u.id
        ORDER BY accuracy DESC, known DESC
    """).fetchall()
    return [dict(r) for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
