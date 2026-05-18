import argparse
import random
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path

from quiz import db, parser
from quiz.session import Session

SEP = "=" * 56
LINE = "-" * 56

KEYS = {
    "l": "known",
    "h": "unknown",
    "j": "skip",
}
HINT = "  l = знаю   h = не знаю   j = пропустить   ? = космос   q = выйти"


def cosmic_help(options: list[str] | None = None) -> None:
    print()
    print("  [COSMIC] Инициализация квантового канала...")
    time.sleep(0.6)
    print("  [COSMIC] Подключение к RANDOM.ORG (атмосферный шум)...")
    time.sleep(0.8)

    seed_hex = ""
    source = "RANDOM.ORG"
    try:
        url = (
            "https://www.random.org/integers/"
            "?num=8&min=0&max=255&col=1&base=16&format=plain&rnd=new"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "flashcard-quiz/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            seed_hex = "".join(resp.read().decode().split())
    except (urllib.error.URLError, OSError):
        seed_hex = format(random.getrandbits(64), "016x")
        source = "локальный генератор (космос временно недоступен)"

    seed_val = int(seed_hex, 16)

    time.sleep(0.4)
    print(f"  [COSMIC] Источник:          {source}")
    print(f"  [COSMIC] Сырые данные:      {seed_hex.upper()}")
    print(f"  [COSMIC] seed = 0x{seed_hex.upper()} = {seed_val}")
    print(f"  [COSMIC] Декодирование...")
    time.sleep(0.5)

    if options:
        chosen = options[seed_val % len(options)]
        print(f"  [COSMIC] Вселенная выбирает вариант [{seed_val % len(options) + 1}]: {chosen}")
    else:
        chosen = ["знаю", "не знаю"][seed_val % 2]
        print(f"  [COSMIC] Вселенная говорит: {chosen.upper()}")
        print(f"  [COSMIC] — когда появятся 4 варианта ответа, выбор будет среди них")
    print()


def select_user(conn: db.sqlite3.Connection) -> int:
    users = db.get_all_users(conn)

    print(f"\n{SEP}")
    print("  Добро пожаловать в C++ Flashcard Quiz!")
    print(SEP)

    if users:
        print("  Существующие игроки:")
        lb = {row["name"]: row for row in db.get_leaderboard(conn)}
        for i, u in enumerate(users, 1):
            stats = lb.get(u["name"])
            acc = f"  точность: {int(stats['accuracy'])}%" if stats else ""
            print(f"    {i}. {u['name']}{acc}")
        print(f"    0. Новый игрок")
        print()

        while True:
            try:
                raw = input("  Выбери номер > ").strip()
            except (EOFError, KeyboardInterrupt):
                raise SystemExit(0)

            if raw == "0":
                break
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(users):
                    return users[idx]["id"]
            print("  Введи номер из списка или 0 для нового игрока.")
    else:
        print("  Игроков пока нет. Создадим первого!")
        print()

    while True:
        try:
            raw = input("  Имя нового игрока > ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(0)
        try:
            name = db.validate_username(raw)
        except ValueError as e:
            print(f"  Ошибка: {e}")
            continue

        existing = db.get_user_by_name(conn, name)
        if existing:
            print(f"  Игрок '{name}' уже существует. Выбери его из списка.")
            continue

        user_id = db.create_user(conn, name)
        print(f"  Создан игрок: {name}")
        return user_id


def run_quiz(
    conn,
    questions: list,
    scope: str,
    shuffle: bool,
    user_id: int | None,
) -> Session:
    if shuffle:
        random.shuffle(questions)

    session = Session(conn, questions, scope, user_id=user_id)
    print(f"\n  Начинаем! {session.total} вопросов. Удачи.")
    print(f"  Управление: l = знаю  h = не знаю  j = пропустить  ? = космос  q = выйти\n")

    while not session.done():
        q = session.current
        filename = Path(q["file_path"]).name

        print(f"\n{SEP}")
        print(f"  [{session.position} / {session.total}]  {filename}  |  {q['difficulty']}")
        print(SEP)
        print()
        for line in textwrap.wrap(q["text"], width=54):
            print(f"  {line}")
        print()
        print(LINE)
        print(HINT)

        while True:
            try:
                answer = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Выход...")
                return session

            if answer in KEYS:
                session.record(KEYS[answer])
                break
            elif answer == "?":
                cosmic_help()
            elif answer == "q":
                print("\n  Выход из сессии...")
                return session
            else:
                print(f"  Неизвестная клавиша. {HINT}")

    return session


def cmd_populate(args) -> None:
    questions = parser.parse_scope()
    conn = db.connect()
    db.init_db(conn)
    count = db.upsert_questions(conn, questions)
    total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    conn.close()
    print(f"Загружено новых вопросов: {count}. Всего в базе: {total}.")


def cmd_leaderboard(args) -> None:
    conn = db.connect()
    db.init_db(conn)
    rows = db.get_leaderboard(conn)
    conn.close()

    print(f"\n{SEP}")
    print("  ТАБЛИЦА ЛИДЕРОВ")
    print(SEP)
    if not rows:
        print("  Пока никто не проходил тест.")
    else:
        print(f"  {'#':<4} {'Игрок':<20} {'Сессий':>6} {'Ответов':>8} {'Знаю':>6} {'Точность':>9}")
        print(f"  {LINE}")
        for i, r in enumerate(rows, 1):
            print(
                f"  {i:<4} {r['name']:<20} {r['sessions']:>6} "
                f"{r['total']:>8} {r['known']:>6} {int(r['accuracy'] or 0):>8}%"
            )
    print(SEP)


def cmd_summary(args) -> None:
    conn = db.connect()
    db.init_db(conn)
    session_id = db.get_last_session_id(conn)
    if session_id is None:
        print("Нет завершённых сессий.")
    else:
        _print_summary(db.get_session_summary(conn, session_id))
    conn.close()


def cmd_quiz(args) -> None:
    conn = db.connect()
    db.init_db(conn)

    user_id = select_user(conn)

    difficulties = args.difficulty or None
    rows = db.get_questions(conn, difficulties=difficulties)
    if not rows:
        msg = f" с уровнем {args.difficulty}" if difficulties else ""
        print(f"Вопросов{msg} не найдено. Сначала запусти: python -m quiz.cli --populate")
        conn.close()
        return

    questions = list(rows)
    if args.count and args.count < len(questions):
        random.shuffle(questions)
        questions = questions[: args.count]
        shuffle = False  # already shuffled above
    else:
        shuffle = not args.no_shuffle

    scope = ", ".join(difficulties) if difficulties else "01_cpp"
    session = run_quiz(conn, questions, scope, shuffle=shuffle, user_id=user_id)
    summary = session.close()
    _print_summary(summary)

    unknown = session.unknown_questions()
    if unknown and summary["unknown"] > 0:
        try:
            again = input("\n  Повторить только 'не знаю'? [y/n] > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            again = "n"
        if again == "y":
            session2 = run_quiz(
                conn, list(unknown), scope + " (повтор)",
                shuffle=not args.no_shuffle, user_id=user_id,
            )
            _print_summary(session2.close())

    conn.close()


def _print_summary(summary: dict) -> None:
    print(f"\n{SEP}")
    print("  Результаты сессии")
    print(SEP)
    print(f"  Знаю      : {summary['known']}")
    print(f"  Не знаю   : {summary['unknown']}")
    print(f"  Пропустил : {summary['skip']}")
    print(f"  Итого     : {summary['total']} вопросов")
    print(f"  Точность  : {summary['accuracy']}%  (знаю / (знаю + не знаю))")
    print(SEP)


def main() -> None:
    ap = argparse.ArgumentParser(description="Flashcard quiz по вопросам C++ интервью")
    ap.add_argument("--populate", action="store_true", help="Загрузить вопросы в БД и выйти")
    ap.add_argument("--leaderboard", action="store_true", help="Показать таблицу лидеров")
    ap.add_argument("--summary", action="store_true", help="Показать статистику последней сессии")
    ap.add_argument(
        "--difficulty", metavar="LEVEL", nargs="+",
        help="Фильтр по уровням сложности (можно несколько)",
    )
    ap.add_argument("--count", type=int, metavar="N", help="Количество вопросов в сессии")
    ap.add_argument("--no-shuffle", action="store_true", help="Не перемешивать вопросы")

    args = ap.parse_args()

    if args.count is not None and args.count < 1:
        ap.error("--count должен быть >= 1")

    if args.populate:
        cmd_populate(args)
    elif args.leaderboard:
        cmd_leaderboard(args)
    elif args.summary:
        cmd_summary(args)
    else:
        cmd_quiz(args)


if __name__ == "__main__":
    main()
