# C++ Flashcard Quiz — CLI

Терминальный тренажёр по вопросам из репозитория. Работает локально, без внешних зависимостей (кроме stdlib).

## Быстрый старт

```bash
pip install -r requirements.txt

# Загрузить вопросы в локальную БД (один раз)
python -m quiz.cli --populate

# Запустить квиз
python -m quiz.cli
```

## Команды

| Команда | Что делает |
|---|---|
| `python -m quiz.cli` | Запустить квиз (выбор игрока, все вопросы) |
| `python -m quiz.cli --populate` | Загрузить/обновить вопросы из `content/` в SQLite |
| `python -m quiz.cli --leaderboard` | Таблица лидеров |
| `python -m quiz.cli --summary` | Статистика последней сессии |
| `python -m quiz.cli --difficulty "Лёгкий" "Средний"` | Фильтр по уровню (можно несколько) |
| `python -m quiz.cli --count 20` | Ограничить количество вопросов |
| `python -m quiz.cli --no-shuffle` | Вопросы по порядку, без перемешивания |

## Управление в квизе

| Клавиша | Действие |
|---|---|
| `l` | Знаю |
| `h` | Не знаю |
| `j` | Пропустить |
| `?` | Помощь из космоса |
| `q` | Выйти |

**Помощь из космоса** — подключается к [RANDOM.ORG](https://www.random.org) (атмосферный шум как источник энтропии), получает 8 случайных байт, выводит сид и делает предсказание. Заготовка под будущий режим с 4 вариантами ответов.

## Файловая структура

```
quiz/
├── parser.py    # парсинг markdown → вопросы (state machine по ## заголовкам)
├── db.py        # SQLite: users, questions, sessions, responses
├── session.py   # состояние текущей сессии
└── cli.py       # точка входа
quiz/flashcards.db   # локальная БД (в .gitignore)
```

## БД

SQLite, `quiz/flashcards.db`. Таблицы:

- `users` — игроки
- `questions` — вопросы (загружаются из `content/01_cpp/01–04.md` по умолчанию)
- `sessions` — каждый запуск квиза
- `responses` — ответы с рейтингом `known / unknown / skip`

По умолчанию загружаются первые 4 файла из `content/01_cpp/`. Чтобы расширить — добавь пути в `quiz/parser.py` → `DEFAULT_FILES`.

## Экспорт вопросов

```bash
python scripts/export_questions.py
# → questions_export.txt, 18 000+ вопросов с глобальным номером и тегом
```

Формат:
```
[1] [01_cpp | Лёгкий уровень]
Что такое язык программирования C++?
```
