from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget,
)

from quiz_gui import db


class HomeScreen(QWidget):
    def __init__(self, conn, on_start_quiz, on_show_leaderboard, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._on_start_quiz = on_start_quiz
        self._on_show_leaderboard = on_show_leaderboard
        self._user_id: int | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(24)
        root.setContentsMargins(48, 48, 48, 48)

        title = QLabel("C++ Flashcard Quiz")
        title.setFont(QFont("SF Pro Display", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        self._stats_label = QLabel()
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stats_label.setFont(QFont("SF Mono", 11))
        self._stats_label.setStyleSheet("color: #888; line-height: 1.6;")
        root.addWidget(self._stats_label)

        root.addItem(QSpacerItem(0, 16, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        user_row = QHBoxLayout()
        user_row.setSpacing(8)
        user_label = QLabel("Игрок:")
        user_label.setFont(QFont("SF Pro Text", 12))
        self._user_combo = QComboBox()
        self._user_combo.setFont(QFont("SF Pro Text", 12))
        self._user_combo.setMinimumWidth(200)
        self._user_combo.currentIndexChanged.connect(self._on_user_changed)
        add_user_btn = QPushButton("+ Новый")
        add_user_btn.setFont(QFont("SF Pro Text", 11))
        add_user_btn.clicked.connect(self._create_user)
        user_row.addStretch()
        user_row.addWidget(user_label)
        user_row.addWidget(self._user_combo)
        user_row.addWidget(add_user_btn)
        user_row.addStretch()
        root.addLayout(user_row)

        root.addItem(QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        self._warn_label = QLabel()
        self._warn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._warn_label.setStyleSheet("color: #e8a000; font-size: 12px;")
        self._warn_label.setWordWrap(True)
        root.addWidget(self._warn_label)

        btn_style = (
            "QPushButton { background:#1e90ff; color:white; border-radius:8px; "
            "padding:12px 32px; font-size:14px; font-weight:bold; } "
            "QPushButton:hover { background:#3aa0ff; } "
            "QPushButton:disabled { background:#444; color:#777; }"
        )
        secondary_style = (
            "QPushButton { background:#2b2b2b; color:#ccc; border:1px solid #555; "
            "border-radius:8px; padding:10px 24px; font-size:13px; } "
            "QPushButton:hover { background:#383838; color:#fff; }"
        )

        self._start_btn = QPushButton("▶  Начать квиз")
        self._start_btn.setFont(QFont("SF Pro Text", 14, QFont.Weight.Bold))
        self._start_btn.setStyleSheet(btn_style)
        self._start_btn.clicked.connect(self._start_quiz)
        root.addWidget(self._start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        row2 = QHBoxLayout()
        row2.setSpacing(12)
        lb_btn = QPushButton("🏆  Лидерборд")
        lb_btn.setFont(QFont("SF Pro Text", 12))
        lb_btn.setStyleSheet(secondary_style)
        lb_btn.clicked.connect(self._on_show_leaderboard)
        row2.addWidget(lb_btn)

        import_btn = QPushButton("📥  Импорт ответов")
        import_btn.setFont(QFont("SF Pro Text", 12))
        import_btn.setStyleSheet(secondary_style)
        import_btn.clicked.connect(self._import_answers)
        row2.addWidget(import_btn)

        update_btn = QPushButton("🔄  Обновить индекс")
        update_btn.setFont(QFont("SF Pro Text", 12))
        update_btn.setStyleSheet(secondary_style)
        update_btn.clicked.connect(self._update_index)
        row2.addWidget(update_btn)

        root.addLayout(row2)
        root.addStretch()

    def refresh(self) -> None:
        stats = db.get_stats(self._conn)
        has_answers = stats["with_answers"] > 0

        mode = "4-варианта" if has_answers else "Flashcard (знаю / не знаю)"
        self._stats_label.setText(
            f"Вопросов в базе: {stats['total_questions']}    "
            f"С ответами: {stats['with_answers']}    "
            f"Игроков: {stats['total_users']}    "
            f"Ответов сегодня: {stats['answered_today']}\n"
            f"Режим: {mode}"
        )

        if not has_answers:
            self._warn_label.setText(
                "⚠  Ответы не импортированы — квиз запустится в режиме flashcard.\n"
                "Используй «Импорт ответов» чтобы загрузить JSONL с вариантами."
            )
        else:
            self._warn_label.setText("")

        self._refresh_users()

    def _refresh_users(self) -> None:
        self._user_combo.blockSignals(True)
        self._user_combo.clear()
        users = db.get_all_users(self._conn)
        for u in users:
            self._user_combo.addItem(u["name"], userData=u["id"])
        self._user_combo.blockSignals(False)
        if users:
            self._user_id = users[0]["id"]

    def _on_user_changed(self, idx: int) -> None:
        if idx >= 0:
            self._user_id = self._user_combo.itemData(idx)

    def _create_user(self) -> None:
        dlg = _NewUserDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = dlg.name()
            try:
                db.create_user(self._conn, name)
                self.refresh()
                idx = self._user_combo.findText(name)
                if idx >= 0:
                    self._user_combo.setCurrentIndex(idx)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def _start_quiz(self) -> None:
        if self._user_id is None:
            QMessageBox.warning(self, "Выбери игрока", "Создай или выбери игрока перед началом.")
            return
        self._on_start_quiz(self._user_id)

    def _import_answers(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбери JSONL с ответами", "", "JSONL files (*.jsonl);;All files (*)"
        )
        if not path:
            return
        from pathlib import Path
        from quiz_gui.importer import import_answers
        try:
            import_answers(Path(path))
            QMessageBox.information(self, "Импорт", "Ответы успешно импортированы.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", str(e))

    def _update_index(self) -> None:
        from quiz_gui.importer import _load_questions
        try:
            _load_questions(self._conn)
            QMessageBox.information(self, "Индекс", "Индекс вопросов обновлён.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))


class _NewUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новый игрок")
        self.setFixedWidth(320)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Имя:"))
        self._edit = QLineEdit()
        self._edit.setMaxLength(30)
        self._edit.setPlaceholderText("Введи имя...")
        layout.addWidget(self._edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def name(self) -> str:
        return self._edit.text().strip()
