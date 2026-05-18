import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QStackedWidget, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from quiz_gui import db
from quiz_gui.screens.home import HomeScreen
from quiz_gui.screens.quiz import QuizScreen
from quiz_gui.screens.results import ResultsScreen

_DARK = "#121212"
_SURFACE = "#1e1e1e"


def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(_DARK))
    p.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    p.setColor(QPalette.ColorRole.Base, QColor(_SURFACE))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#2a2a2a"))
    p.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    p.setColor(QPalette.ColorRole.Button, QColor("#2b2b2b"))
    p.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
    p.setColor(QPalette.ColorRole.Highlight, QColor("#1e90ff"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    return p


class LeaderboardDialog(QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Таблица лидеров")
        self.resize(720, 460)
        self.setStyleSheet(f"background:{_SURFACE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #444; } "
            "QTabBar::tab { background:#2b2b2b; color:#aaa; padding:8px 20px; } "
            "QTabBar::tab:selected { background:#1e90ff; color:white; }"
        )
        tabs.addTab(self._make_table(db.get_leaderboard(conn, "quiz")), "Тест (4 варианта)")
        tabs.addTab(self._make_table(db.get_leaderboard(conn, "flashcard")), "Flashcard")
        layout.addWidget(tabs)

        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.reject)
        layout.addWidget(close_btn)

    def _make_table(self, rows: list[dict]) -> QWidget:
        headers = ["#", "Игрок", "Сессий", "Ответов", "Правильно", "Точность", "Ср. время"]
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setStyleSheet(
            "QTableWidget { background:#1e1e1e; color:#e0e0e0; border:none; gridline-color:#333; } "
            "QHeaderView::section { background:#2b2b2b; color:#aaa; border:none; padding:6px; }"
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for i, r in enumerate(rows):
            acc = int(r["accuracy"] or 0)
            avg = f"{r['avg_time']:.1f}с" if r["avg_time"] else "—"
            for j, val in enumerate([i + 1, r["name"], r["sessions"], r["total"], r["correct"], f"{acc}%", avg]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(i, j, item)

        return table


class MainWindow(QMainWindow):
    def __init__(self, conn):
        super().__init__()
        self._conn = conn
        self.setWindowTitle("C++ Flashcard Quiz")
        self.resize(900, 640)
        self.setMinimumSize(760, 520)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._home = HomeScreen(
            conn,
            on_start_quiz=self._start_quiz,
            on_show_leaderboard=self._show_leaderboard,
        )
        self._stack.addWidget(self._home)
        self._show_home()

    def _show_home(self) -> None:
        self._home.refresh()
        self._stack.setCurrentWidget(self._home)

    def _start_quiz(self, user_id: int, settings: dict) -> None:
        self._last_user_id = user_id
        self._last_timer = settings.get("timer", 60)
        self._last_mode = settings.get("mode", "quiz")
        quiz = QuizScreen(self._conn, user_id, settings, parent=self)
        quiz.finished.connect(self._show_results)
        quiz.cancelled.connect(self._on_quiz_cancelled)
        self._stack.addWidget(quiz)
        self._stack.setCurrentWidget(quiz)
        quiz.start()
        quiz.setFocus()

    def _show_results(self, session_id: int, timer_seconds: int) -> None:
        results = ResultsScreen(
            self._conn,
            session_id,
            timer_seconds,
            on_home=self._show_home,
            on_retry_wrong=self._retry_wrong,
        )
        self._stack.addWidget(results)
        self._stack.setCurrentWidget(results)

    def _retry_wrong(self, question_ids: list[int]) -> None:
        if not question_ids or not hasattr(self, "_last_user_id"):
            return
        settings = {
            "mode": getattr(self, "_last_mode", "quiz"),
            "timer": getattr(self, "_last_timer", 60),
            "question_ids": question_ids,
        }
        self._start_quiz(self._last_user_id, settings)

    def _on_quiz_cancelled(self) -> None:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Нет вопросов", "По выбранным фильтрам вопросов не найдено.")
        self._show_home()

    def _show_leaderboard(self) -> None:
        dlg = LeaderboardDialog(self._conn, self)
        dlg.exec()

    def closeEvent(self, event):
        self._conn.close()
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("C++ Flashcard Quiz")
    app.setPalette(_dark_palette())
    app.setFont(QFont("SF Pro Text", 12))

    conn = db.connect()
    db.init_db(conn)

    window = MainWindow(conn)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
