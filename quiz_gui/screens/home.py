from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QRadioButton, QScrollArea,
    QSizePolicy, QSlider, QSpinBox, QSpacerItem, QVBoxLayout, QWidget,
)

from quiz_gui import db

_URL_ORIGINAL = "https://github.com/Jollu8"
_URL_QUIZ     = "https://github.com/arskstn"


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
        root.setSpacing(20)
        root.setContentsMargins(48, 40, 48, 20)

        title = QLabel("C++ Flashcard Quiz")
        title.setFont(QFont("SF Pro Display", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        self._stats_label = QLabel()
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stats_label.setFont(QFont("SF Mono", 11))
        self._stats_label.setStyleSheet("color: #888;")
        root.addWidget(self._stats_label)

        root.addItem(QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

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

        footer = QHBoxLayout()
        footer.setSpacing(12)

        link_style = (
            "QPushButton { background:transparent; color:#555; border:none; "
            "font-size:11px; padding:4px 8px; } "
            "QPushButton:hover { color:#888; }"
        )

        orig_btn = QPushButton("GitHub оригинального репо")
        orig_btn.setStyleSheet(link_style)
        orig_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        orig_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(_URL_ORIGINAL)))
        footer.addWidget(orig_btn)

        footer.addStretch()

        quiz_btn = QPushButton("GitHub автора квиза")
        quiz_btn.setStyleSheet(link_style)
        quiz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quiz_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(_URL_QUIZ)))
        footer.addWidget(quiz_btn)

        footer.addStretch()

        quit_btn = QPushButton("Выйти")
        quit_btn.setFont(QFont("SF Pro Text", 11))
        quit_btn.setStyleSheet(
            "QPushButton { background:#2b2b2b; color:#f44336; border:1px solid #444; "
            "border-radius:6px; padding:6px 18px; } "
            "QPushButton:hover { background:#3d1a1a; border-color:#f44336; }"
        )
        quit_btn.clicked.connect(QApplication.instance().quit)
        footer.addWidget(quit_btn)

        root.addLayout(footer)

    def refresh(self) -> None:
        stats = db.get_stats(self._conn)
        self._stats_label.setText(
            f"Вопросов в базе: {stats['total_questions']}    "
            f"С ответами: {stats['with_answers']}    "
            f"Игроков: {stats['total_users']}    "
            f"Ответов сегодня: {stats['answered_today']}"
        )
        if stats["with_answers"] == 0:
            self._warn_label.setText(
                "⚠  Ответы не импортированы — в настройках квиза будет доступен только режим Flashcard.\n"
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
        stats = db.get_stats(self._conn)
        dlg = _QuizSettingsDialog(
            conn=self._conn,
            has_answers=stats["with_answers"] > 0,
            total_questions=max(stats["total_questions"], 1),
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._on_start_quiz(self._user_id, dlg.settings())

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


class _QuizSettingsDialog(QDialog):
    def __init__(self, conn, has_answers: bool, total_questions: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки квиза")
        self.setFixedWidth(460)
        self._has_answers = has_answers
        self._total = max(total_questions, 1)
        self._conn = conn
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # Mode
        mode_group = QGroupBox("Режим")
        ml = QVBoxLayout(mode_group)
        radio_row = QHBoxLayout()
        self._flashcard_radio = QRadioButton("Flashcard (знаю / не знаю)")
        self._quiz_radio = QRadioButton("4 варианта")
        self._quiz_radio.setEnabled(self._has_answers)
        self._quiz_radio.setChecked(self._has_answers)
        self._flashcard_radio.setChecked(not self._has_answers)
        bg = QButtonGroup(self)
        bg.addButton(self._flashcard_radio)
        bg.addButton(self._quiz_radio)
        radio_row.addWidget(self._flashcard_radio)
        radio_row.addWidget(self._quiz_radio)
        ml.addLayout(radio_row)
        if not self._has_answers:
            note = QLabel("ℹ  Импортируй JSONL чтобы разблокировать режим «4 варианта»")
            note.setStyleSheet("color: #888; font-size: 11px;")
            note.setWordWrap(True)
            ml.addWidget(note)
        layout.addWidget(mode_group)

        # Sections
        sections_group = QGroupBox("Разделы вопросов")
        sg = QVBoxLayout(sections_group)

        ctrl_row = QHBoxLayout()
        ctrl_row.addStretch()
        sel_all = QPushButton("Все")
        sel_all.setFixedWidth(52)
        sel_all.setStyleSheet(
            "QPushButton { background:#2b2b2b; color:#ccc; border:1px solid #555; "
            "border-radius:4px; padding:2px 6px; font-size:11px; } "
            "QPushButton:hover { background:#383838; }"
        )
        desel_all = QPushButton("Сбросить")
        desel_all.setFixedWidth(72)
        desel_all.setStyleSheet(sel_all.styleSheet())
        ctrl_row.addWidget(sel_all)
        ctrl_row.addWidget(desel_all)
        sg.addLayout(ctrl_row)

        scroll = QScrollArea()
        scroll.setMaximumHeight(140)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #333; border-radius:4px; background:#1e1e1e; } "
        )
        sc_w = QWidget()
        sc_w.setStyleSheet("background:#1e1e1e;")
        sc_vbox = QVBoxLayout(sc_w)
        sc_vbox.setSpacing(4)
        sc_vbox.setContentsMargins(8, 6, 8, 6)
        scroll.setWidget(sc_w)

        self._section_checks: dict[str, QCheckBox] = {}
        sections = db.get_sections(self._conn)
        cb_style = "QCheckBox { color: #ccc; } QCheckBox::indicator { width:14px; height:14px; }"
        for sec in sections:
            cb = QCheckBox(sec)
            cb.setChecked(True)
            cb.setStyleSheet(cb_style)
            self._section_checks[sec] = cb
            sc_vbox.addWidget(cb)
        sc_vbox.addStretch()
        sg.addWidget(scroll)

        sel_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self._section_checks.values()])
        desel_all.clicked.connect(lambda: [cb.setChecked(False) for cb in self._section_checks.values()])

        layout.addWidget(sections_group)

        # Count
        count_group = QGroupBox("Количество вопросов")
        cl = QHBoxLayout(count_group)
        max_count = min(self._total, 500)
        default_count = min(20, max_count)
        self._count_slider = QSlider(Qt.Orientation.Horizontal)
        self._count_slider.setRange(1, max_count)
        self._count_slider.setValue(default_count)
        self._count_spin = QSpinBox()
        self._count_spin.setRange(1, max_count)
        self._count_spin.setValue(default_count)
        self._count_spin.setFixedWidth(72)
        self._count_slider.valueChanged.connect(self._count_spin.setValue)
        self._count_spin.valueChanged.connect(self._count_slider.setValue)
        cl.addWidget(self._count_slider)
        cl.addWidget(self._count_spin)
        layout.addWidget(count_group)

        # Timer
        timer_group = QGroupBox("Время на вопрос")
        tl = QHBoxLayout(timer_group)
        self._timer_slider = QSlider(Qt.Orientation.Horizontal)
        self._timer_slider.setRange(10, 300)
        self._timer_slider.setValue(60)
        self._timer_val = QLabel("60 с")
        self._timer_val.setFixedWidth(48)
        self._timer_slider.valueChanged.connect(lambda v: self._timer_val.setText(f"{v} с"))
        tl.addWidget(self._timer_slider)
        tl.addWidget(self._timer_val)
        layout.addWidget(timer_group)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Старт ▶")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def settings(self) -> dict:
        checked = [sec for sec, cb in self._section_checks.items() if cb.isChecked()]
        # None = no filter (all selected or all deselected)
        sections = None if (len(checked) == len(self._section_checks) or not checked) else checked
        return {
            "mode": "quiz" if self._quiz_radio.isChecked() else "flashcard",
            "count": self._count_spin.value(),
            "timer": self._timer_slider.value(),
            "sections": sections,
        }


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
