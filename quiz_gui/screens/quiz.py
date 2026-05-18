import random
import time
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from quiz_gui import db
from quiz_gui.widgets.answer_button import AnswerButton

ANSWER_KEYS = ["h", "j", "k", "l"]
TIMER_SECONDS = 60


class _CosmicThread(QThread):
    done = pyqtSignal(str, str)  # seed_hex, source

    def run(self):
        try:
            url = (
                "https://www.random.org/integers/"
                "?num=8&min=0&max=255&col=1&base=16&format=plain&rnd=new"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "flashcard-quiz/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                seed_hex = "".join(resp.read().decode().split())
            self.done.emit(seed_hex, "RANDOM.ORG (атмосферный шум)")
        except (urllib.error.URLError, OSError):
            seed_hex = format(random.getrandbits(64), "016x")
            self.done.emit(seed_hex, "локальный генератор")


class QuizScreen(QWidget):
    finished = pyqtSignal(int)  # session_id

    def __init__(self, conn, user_id: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user_id = user_id
        self._session_id: int | None = None
        self._questions: list = []
        self._index = 0
        self._q_start_time = 0.0
        self._answer_buttons: list[AnswerButton] = []
        self._current_options: list = []
        self._cosmic_highlighted: int | None = None
        self._answered = False
        self._fallback_mode = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setStyleSheet("background: #1a1a1a;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        self._progress_label = QLabel("0 / 0")
        self._progress_label.setFont(QFont("SF Mono", 11))
        self._progress_label.setStyleSheet("color: #888;")
        header_layout.addWidget(self._progress_label)

        self._file_label = QLabel()
        self._file_label.setFont(QFont("SF Mono", 10))
        self._file_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self._file_label)

        header_layout.addStretch()

        self._timer_label = QLabel("⏱  1:00")
        self._timer_label.setFont(QFont("SF Mono", 13, QFont.Weight.Bold))
        self._timer_label.setStyleSheet("color: #4caf50;")
        header_layout.addWidget(self._timer_label)

        root.addWidget(header)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            "QProgressBar { border:none; background:#222; } "
            "QProgressBar::chunk { background:#1e90ff; }"
        )
        root.addWidget(self._progress_bar)

        q_area = QWidget()
        q_area.setStyleSheet("background: #1e1e1e;")
        q_layout = QVBoxLayout(q_area)
        q_layout.setContentsMargins(48, 32, 48, 32)
        self._question_label = QLabel()
        self._question_label.setFont(QFont("SF Pro Text", 16))
        self._question_label.setStyleSheet("color: #e8e8e8;")
        self._question_label.setWordWrap(True)
        self._question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q_layout.addWidget(self._question_label)
        root.addWidget(q_area, stretch=2)

        answers_widget = QWidget()
        answers_widget.setStyleSheet("background: #252525;")
        answers_layout = QVBoxLayout(answers_widget)
        answers_layout.setContentsMargins(24, 16, 24, 16)
        answers_layout.setSpacing(12)

        self._cosmic_label = QLabel()
        self._cosmic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cosmic_label.setFont(QFont("SF Mono", 10))
        self._cosmic_label.setStyleSheet("color: #7ec8ff;")
        self._cosmic_label.hide()
        answers_layout.addWidget(self._cosmic_label)

        row1 = QHBoxLayout()
        row1.setSpacing(12)
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        for i, key in enumerate(ANSWER_KEYS):
            btn = AnswerButton(key)
            btn.setFont(QFont("SF Pro Text", 12))
            btn.clicked.connect(lambda checked, idx=i: self._select_answer(idx))
            self._answer_buttons.append(btn)
            (row1 if i < 2 else row2).addWidget(btn)

        answers_layout.addLayout(row1)
        answers_layout.addLayout(row2)
        root.addWidget(answers_widget, stretch=3)

        bottom = QFrame()
        bottom.setStyleSheet("background: #1a1a1a; border-top: 1px solid #333;")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(24, 10, 24, 10)
        bottom_layout.setSpacing(16)

        def _nav_btn(text, shortcut):
            b = QPushButton(text)
            b.setFont(QFont("SF Pro Text", 11))
            b.setStyleSheet(
                "QPushButton { background:transparent; color:#777; border:none; } "
                "QPushButton:hover { color:#ccc; }"
            )
            b.setToolTip(f"Клавиша: {shortcut}")
            return b

        cosmic_btn = _nav_btn("[w]  Космос", "w")
        cosmic_btn.clicked.connect(self._activate_cosmic)
        skip_btn = _nav_btn("[e]  Пропустить", "e")
        skip_btn.clicked.connect(self._skip)
        quit_btn = _nav_btn("[q]  Выйти", "q")
        quit_btn.clicked.connect(self._quit)

        bottom_layout.addWidget(cosmic_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(skip_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(quit_btn)
        root.addWidget(bottom)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._time_left = TIMER_SECONDS

    def start(self) -> None:
        has_answers = bool(db.get_questions_with_answers(self._conn))
        self._fallback_mode = not has_answers

        if self._fallback_mode:
            questions = db.get_all_questions(self._conn)
        else:
            questions = db.get_questions_with_answers(self._conn)

        questions = list(questions)
        random.shuffle(questions)
        self._questions = questions
        self._index = 0
        self._session_id = db.create_session(self._conn, self._user_id, "gui")

        if self._fallback_mode:
            for btn in self._answer_buttons[2:]:
                btn.hide()
            self._answer_buttons[0].setText("Не знаю")
            self._answer_buttons[1].setText("Знаю")

        self._show_question()

    def _show_question(self) -> None:
        if self._index >= len(self._questions):
            self._end_session()
            return

        q = self._questions[self._index]
        self._answered = False
        self._cosmic_highlighted = None
        self._cosmic_label.hide()

        total = len(self._questions)
        self._progress_label.setText(f"{self._index + 1} / {total}")
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(self._index)
        self._file_label.setText(Path(q["file_path"]).name + "  |  " + q["difficulty"])
        self._question_label.setText(q["text"])

        for btn in self._answer_buttons:
            btn.reset()
            btn.setEnabled(True)

        if not self._fallback_mode:
            opts = db.get_answer_options(self._conn, q["id"])
            shuffled = list(opts)
            random.shuffle(shuffled)
            self._current_options = shuffled
            for i, (btn, opt) in enumerate(zip(self._answer_buttons, shuffled)):
                btn.setText(opt["text"])
                btn.show()

        self._time_left = TIMER_SECONDS
        self._update_timer_label()
        self._timer.start()
        self._q_start_time = time.monotonic()

    def _tick(self) -> None:
        self._time_left -= 1
        self._update_timer_label()
        if self._time_left <= 10:
            self._timer_label.setStyleSheet("color: #f44336; font-weight: bold;")
        if self._time_left <= 0:
            self._timer.stop()
            self._record_and_advance(None, "timeout")

    def _update_timer_label(self) -> None:
        m, s = divmod(self._time_left, 60)
        self._timer_label.setText(f"⏱  {m}:{s:02d}")
        if self._time_left > 10:
            self._timer_label.setStyleSheet("color: #4caf50; font-weight: bold;")

    def _select_answer(self, idx: int) -> None:
        if self._answered:
            return
        self._answered = True
        self._timer.stop()

        if self._fallback_mode:
            rating = "wrong" if idx == 0 else "correct"
            self._record_and_advance(None, rating)
            return

        opt = self._current_options[idx]
        is_correct = bool(opt["is_correct"])
        rating = "cosmic" if self._cosmic_highlighted is not None else ("correct" if is_correct else "wrong")

        for i, (btn, o) in enumerate(zip(self._answer_buttons, self._current_options)):
            if o["is_correct"]:
                btn.set_state("correct")
            elif i == idx and not is_correct:
                btn.set_state("wrong")
            btn.setEnabled(False)

        self._record_and_advance(opt["id"], rating, delay=1500)

    def _record_and_advance(self, option_id, rating, delay=0) -> None:
        elapsed = time.monotonic() - self._q_start_time
        q = self._questions[self._index]
        is_correct = 1 if rating == "correct" else (0 if rating == "wrong" else None)

        db.record_response(
            self._conn,
            self._session_id,
            q["id"],
            option_id,
            is_correct,
            round(elapsed, 2),
            rating,
        )

        if delay:
            QTimer.singleShot(delay, self._next_question)
        else:
            self._next_question()

    def _next_question(self) -> None:
        self._index += 1
        self._show_question()

    def _skip(self) -> None:
        if not self._answered:
            self._answered = True
            self._timer.stop()
            self._record_and_advance(None, "skip")

    def _activate_cosmic(self) -> None:
        if self._answered or self._fallback_mode:
            return
        self._cosmic_label.setText("☄  Подключение к RANDOM.ORG...")
        self._cosmic_label.show()
        for btn in self._answer_buttons:
            btn.setEnabled(False)

        self._cosmic_thread = _CosmicThread()
        self._cosmic_thread.done.connect(self._on_cosmic_done)
        self._cosmic_thread.start()

    def _on_cosmic_done(self, seed_hex: str, source: str) -> None:
        seed_val = int(seed_hex, 16)
        idx = seed_val % len(self._current_options)
        self._cosmic_highlighted = idx
        self._cosmic_label.setText(
            f"☄  {source}  ·  сид: {seed_hex[:8].upper()}…  ·  "
            f"вселенная выбирает [{ANSWER_KEYS[idx]}]"
        )
        for btn in self._answer_buttons:
            btn.setEnabled(True)
        self._answer_buttons[idx].set_state("highlighted")

    def _quit(self) -> None:
        self._timer.stop()
        self._end_session()

    def _end_session(self) -> None:
        if self._session_id is not None:
            db.close_session(self._conn, self._session_id)
            self.finished.emit(self._session_id)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.text().lower()
        if key in ANSWER_KEYS:
            self._select_answer(ANSWER_KEYS.index(key))
        elif key == "w":
            self._activate_cosmic()
        elif key == "e":
            self._skip()
        elif key == "q":
            self._quit()
        else:
            super().keyPressEvent(event)
