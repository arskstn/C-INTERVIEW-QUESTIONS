import sqlite3

from quiz import db


class Session:
    def __init__(
        self,
        conn: sqlite3.Connection,
        questions: list[sqlite3.Row],
        scope: str,
        user_id: int | None = None,
    ):
        self.conn = conn
        self.questions = questions
        self.index = 0
        self.session_id = db.create_session(conn, scope, user_id=user_id)

    @property
    def current(self) -> sqlite3.Row | None:
        if self.index < len(self.questions):
            return self.questions[self.index]
        return None

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def position(self) -> int:
        return self.index + 1

    def record(self, rating: str) -> None:
        q = self.current
        if q:
            db.record_response(self.conn, self.session_id, q["id"], rating)
            self.index += 1

    def done(self) -> bool:
        return self.index >= len(self.questions)

    def close(self) -> dict:
        db.close_session(self.conn, self.session_id)
        return db.get_session_summary(self.conn, self.session_id)

    def unknown_questions(self) -> list[sqlite3.Row]:
        return db.get_unknown_questions(self.conn, self.session_id)
