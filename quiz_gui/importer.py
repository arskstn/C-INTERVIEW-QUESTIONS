"""
Import AI-generated answers from JSONL into the GUI database.

JSONL format (one JSON object per line):
    {"qid": 1, "correct": "...", "wrong": ["...", "...", "..."]}

qid matches the global number in questions_export.txt.

Usage:
    python -m quiz_gui.importer answers.jsonl
    python -m quiz_gui.importer answers.jsonl --reset
"""

import json
import sys
from pathlib import Path

from quiz_gui import db

REPO_ROOT = Path(__file__).parent.parent


def _load_questions(conn) -> None:
    from quiz.parser import DIFFICULTY_RE, QUESTION_RE

    files = sorted((REPO_ROOT / "content").rglob("*.md"))
    content_root = (REPO_ROOT / "content").resolve()
    global_n = 0
    rows = []

    for md in files:
        if not md.resolve().is_relative_to(content_root):
            continue
        rel = md.relative_to(REPO_ROOT)
        section = rel.parts[1]
        current_difficulty = "Unknown"

        for line in md.read_text(encoding="utf-8").splitlines():
            m = DIFFICULTY_RE.match(line)
            if m:
                current_difficulty = m.group(1).strip()
                continue
            m = QUESTION_RE.match(line)
            if m:
                global_n += 1
                rows.append({
                    "global_id": global_n,
                    "text": m.group(1).strip(),
                    "file_path": str(rel),
                    "section": section,
                    "difficulty": current_difficulty,
                })

    added = db.upsert_questions(conn, rows)
    print(f"Вопросы: {global_n} всего, {added} новых загружено в БД.")


def import_answers(jsonl_path: Path, reset: bool = False) -> None:
    conn = db.connect()
    db.init_db(conn)

    _load_questions(conn)

    if reset:
        conn.execute("DELETE FROM answer_options")
        conn.commit()
        print("Старые ответы удалены.")

    total = skipped = inserted = 0

    with jsonl_path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            total += 1
            try:
                obj = json.loads(raw)
                qid = int(obj["qid"])
                correct = str(obj["correct"]).strip()
                wrong = [str(w).strip() for w in obj["wrong"]]
                if len(wrong) != 3:
                    raise ValueError("нужно ровно 3 неверных ответа")
                if not correct or any(not w for w in wrong):
                    raise ValueError("пустой текст ответа")
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                print(f"  Строка {lineno}: пропущена — {e}")
                skipped += 1
                continue

            row = conn.execute(
                "SELECT id FROM questions WHERE global_id = ?", (qid,)
            ).fetchone()
            if not row:
                skipped += 1
                continue

            question_id = row["id"]
            existing = conn.execute(
                "SELECT COUNT(*) FROM answer_options WHERE question_id = ?", (question_id,)
            ).fetchone()[0]
            if existing and not reset:
                skipped += 1
                continue

            conn.execute(
                "INSERT INTO answer_options (question_id, text, is_correct) VALUES (?, ?, 1)",
                (question_id, correct),
            )
            for w in wrong:
                conn.execute(
                    "INSERT INTO answer_options (question_id, text, is_correct) VALUES (?, ?, 0)",
                    (question_id, w),
                )
            inserted += 1

    conn.commit()
    conn.close()
    print(f"Импорт завершён: {inserted} вопросов с ответами, {skipped} пропущено из {total}.")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Импорт ответов из JSONL в БД")
    ap.add_argument("file", type=Path, help="Путь к JSONL-файлу с ответами")
    ap.add_argument("--reset", action="store_true", help="Удалить старые ответы перед импортом")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"Файл не найден: {args.file}")
        sys.exit(1)

    import_answers(args.file, reset=args.reset)


if __name__ == "__main__":
    main()
