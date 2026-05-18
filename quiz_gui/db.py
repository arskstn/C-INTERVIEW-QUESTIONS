import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "app.db"

_USERNAME_RE = re.compile(r"^[\w\s\-]{1,30}$", re.UNICODE)


def validate_username(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Имя не может быть пустым")
    if len(name) > 30:
        raise ValueError("Имя не может быть длиннее 30 символов")
    if not _USERNAME_RE.match(name):
        raise ValueError("Имя содержит недопустимые символы")
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
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            global_id INTEGER UNIQUE NOT NULL,
            text      TEXT    NOT NULL,
            file_path TEXT    NOT NULL,
            section   TEXT    NOT NULL,
            difficulty TEXT   NOT NULL
        );

        CREATE TABLE IF NOT EXISTS answer_options (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            text        TEXT    NOT NULL,
            is_correct  INTEGER NOT NULL CHECK(is_correct IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER REFERENCES users(id),
            started_at TEXT    NOT NULL,
            ended_at   TEXT,
            scope      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS responses (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id         INTEGER NOT NULL REFERENCES sessions(id),
            question_id        INTEGER NOT NULL REFERENCES questions(id),
            selected_option_id INTEGER REFERENCES answer_options(id),
            is_correct         INTEGER,
            time_taken_seconds REAL    NOT NULL,
            rating             TEXT    NOT NULL
                CHECK(rating IN ('correct','wrong','skip','timeout','cosmic')),
            answered_at        TEXT    NOT NULL
        );
    """)
    conn.commit()


# ── Users ───────────────────────────────────────────────────────────────────

def create_user(conn: sqlite3.Connection, name: str) -> int:
    name = validate_username(name)
    cur = conn.execute(
        "INSERT INTO users (name, created_at) VALUES (?, ?)", (name, _now())
    )
    conn.commit()
    return cur.lastrowid


def get_all_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM users ORDER BY name").fetchall()


def get_user_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()


# ── Questions ────────────────────────────────────────────────────────────────

def upsert_questions(conn: sqlite3.Connection, questions: list[dict]) -> int:
    before = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    conn.executemany(
        "INSERT OR IGNORE INTO questions (global_id, text, file_path, section, difficulty) "
        "VALUES (:global_id, :text, :file_path, :section, :difficulty)",
        questions,
    )
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] - before


def get_questions_with_answers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT DISTINCT q.* FROM questions q "
        "JOIN answer_options a ON a.question_id = q.id"
    ).fetchall()


def get_all_questions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM questions").fetchall()


def get_answer_options(conn: sqlite3.Connection, question_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM answer_options WHERE question_id = ?", (question_id,)
    ).fetchall()


# ── Stats ────────────────────────────────────────────────────────────────────

def get_stats(conn: sqlite3.Connection) -> dict:
    total_q = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    with_answers = conn.execute(
        "SELECT COUNT(DISTINCT question_id) FROM answer_options WHERE is_correct = 1"
    ).fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    today = _now()[:10]
    answered_today = conn.execute(
        "SELECT COUNT(*) FROM responses WHERE answered_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]
    return {
        "total_questions": total_q,
        "with_answers": with_answers,
        "total_users": total_users,
        "answered_today": answered_today,
    }


# ── Sessions ─────────────────────────────────────────────────────────────────

def create_session(conn: sqlite3.Connection, user_id: int | None, scope: str) -> int:
    cur = conn.execute(
        "INSERT INTO sessions (user_id, started_at, scope) VALUES (?, ?, ?)",
        (user_id, _now(), scope),
    )
    conn.commit()
    return cur.lastrowid


def close_session(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (_now(), session_id))
    conn.commit()


def record_response(
    conn: sqlite3.Connection,
    session_id: int,
    question_id: int,
    selected_option_id: int | None,
    is_correct: int | None,
    time_taken_seconds: float,
    rating: str,
) -> None:
    if rating not in ("correct", "wrong", "skip", "timeout", "cosmic"):
        raise ValueError(f"Invalid rating: {rating!r}")
    conn.execute(
        "INSERT INTO responses "
        "(session_id, question_id, selected_option_id, is_correct, time_taken_seconds, rating, answered_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, question_id, selected_option_id, is_correct, time_taken_seconds, rating, _now()),
    )
    conn.commit()


def get_session_responses(conn: sqlite3.Connection, session_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT r.*, q.difficulty, q.text as question_text "
        "FROM responses r JOIN questions q ON q.id = r.question_id "
        "WHERE r.session_id = ?",
        (session_id,),
    ).fetchall()


def get_wrong_question_ids(conn: sqlite3.Connection, session_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT question_id FROM responses WHERE session_id = ? AND rating = 'wrong'",
        (session_id,),
    ).fetchall()
    return [r["question_id"] for r in rows]


# ── Leaderboard ──────────────────────────────────────────────────────────────

def get_leaderboard(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT
            u.name,
            COUNT(DISTINCT s.id)                                                AS sessions,
            COUNT(r.id)                                                         AS total,
            SUM(CASE WHEN r.rating = 'correct' THEN 1 ELSE 0 END)              AS correct,
            ROUND(
                CAST(SUM(CASE WHEN r.rating = 'correct' THEN 1 ELSE 0 END) AS REAL)
                / NULLIF(SUM(CASE WHEN r.rating IN ('correct','wrong') THEN 1 ELSE 0 END), 0)
                * 100
            )                                                                   AS accuracy,
            ROUND(AVG(r.time_taken_seconds), 1)                                AS avg_time
        FROM users u
        JOIN sessions s ON s.user_id = u.id
        JOIN responses r ON r.session_id = s.id
        GROUP BY u.id
        ORDER BY accuracy DESC, correct DESC
    """).fetchall()
    return [dict(r) for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
