from collections import defaultdict

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from quiz_gui import db

_PALETTE = {"correct": "#4caf50", "wrong": "#f44336", "skip": "#ff9800", "timeout": "#9c27b0", "cosmic": "#2196f3"}
_DARK_BG = "#1e1e1e"
_CARD_BG = "#252525"


def _stat_card(label: str, value: str, color: str = "#e0e0e0") -> QWidget:
    w = QWidget()
    w.setStyleSheet(f"background:{_CARD_BG}; border-radius:8px; padding:12px;")
    lay = QVBoxLayout(w)
    lay.setSpacing(4)
    val_lbl = QLabel(value)
    val_lbl.setFont(QFont("SF Mono", 22, QFont.Weight.Bold))
    val_lbl.setStyleSheet(f"color:{color}; background:transparent;")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl = QLabel(label)
    lbl.setFont(QFont("SF Pro Text", 10))
    lbl.setStyleSheet("color:#888; background:transparent;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(val_lbl)
    lay.addWidget(lbl)
    return w


class ResultsScreen(QWidget):
    def __init__(self, conn, session_id: int, on_home, on_retry_wrong, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._session_id = session_id
        self._on_home = on_home
        self._on_retry_wrong = on_retry_wrong
        self.setStyleSheet(f"background:{_DARK_BG};")
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setSpacing(24)
        root.setContentsMargins(40, 32, 40, 40)

        title = QLabel("Результаты сессии")
        title.setFont(QFont("SF Pro Display", 22, QFont.Weight.Bold))
        title.setStyleSheet("color:#e0e0e0;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        responses = db.get_session_responses(self._conn, self._session_id)
        if not responses:
            root.addWidget(QLabel("Нет ответов в этой сессии."))
            return

        counts = defaultdict(int)
        times = []
        by_diff: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})

        for r in responses:
            counts[r["rating"]] += 1
            times.append(r["time_taken_seconds"])
            diff = r["difficulty"] or "Unknown"
            by_diff[diff]["total"] += 1
            if r["rating"] == "correct":
                by_diff[diff]["correct"] += 1

        correct = counts["correct"]
        avg_time = sum(times) / len(times) if times else 0
        accuracy = round(correct / max(correct + counts["wrong"], 1) * 100)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.addWidget(_stat_card("Правильно", str(correct), "#4caf50"))
        cards.addWidget(_stat_card("Неправильно", str(counts["wrong"]), "#f44336"))
        cards.addWidget(_stat_card("Пропущено", str(counts["skip"]), "#ff9800"))
        cards.addWidget(_stat_card("Время вышло", str(counts["timeout"]), "#9c27b0"))
        cards.addWidget(_stat_card("Точность", f"{accuracy}%", "#1e90ff"))
        cards.addWidget(_stat_card("Ср. время", f"{avg_time:.1f}с", "#888"))
        root.addLayout(cards)

        root.addWidget(self._make_charts(counts, by_diff, times))

        btns = QHBoxLayout()
        btns.setSpacing(12)

        wrong_ids = db.get_wrong_question_ids(self._conn, self._session_id)
        if wrong_ids:
            retry_btn = QPushButton("🔁  Повторить неправильные")
            retry_btn.setFont(QFont("SF Pro Text", 12))
            retry_btn.setStyleSheet(
                "QPushButton { background:#b71c1c; color:white; border-radius:8px; padding:10px 20px; } "
                "QPushButton:hover { background:#d32f2f; }"
            )
            retry_btn.clicked.connect(lambda: self._on_retry_wrong(wrong_ids))
            btns.addWidget(retry_btn)

        home_btn = QPushButton("🏠  Главный экран")
        home_btn.setFont(QFont("SF Pro Text", 12))
        home_btn.setStyleSheet(
            "QPushButton { background:#2b2b2b; color:#ccc; border:1px solid #555; border-radius:8px; padding:10px 20px; } "
            "QPushButton:hover { background:#383838; }"
        )
        home_btn.clicked.connect(self._on_home)
        btns.addWidget(home_btn)

        root.addLayout(btns)

    def _make_charts(self, counts, by_diff, times) -> QWidget:
        fig = Figure(figsize=(12, 8), facecolor=_DARK_BG)
        fig.subplots_adjust(hspace=0.4, wspace=0.3)

        _txt = {"color": "#ccc", "fontsize": 10}

        ax1 = fig.add_subplot(2, 2, 1)
        ax1.set_facecolor(_CARD_BG)
        labels = [k for k, v in counts.items() if v > 0]
        values = [counts[k] for k in labels]
        colors = [_PALETTE.get(k, "#888") for k in labels]
        wedges, texts, autotexts = ax1.pie(
            values, labels=labels, colors=colors,
            autopct="%1.0f%%", startangle=90,
            textprops={"color": "#ccc", "fontsize": 9},
        )
        for at in autotexts:
            at.set_color("#fff")
        ax1.set_title("Распределение ответов", **_txt)

        ax2 = fig.add_subplot(2, 2, 2)
        ax2.set_facecolor(_CARD_BG)
        diffs = list(by_diff.keys())[:8]
        short_diffs = [d[:12] for d in diffs]
        acc_vals = [
            round(by_diff[d]["correct"] / max(by_diff[d]["total"], 1) * 100)
            for d in diffs
        ]
        bars = ax2.barh(short_diffs, acc_vals, color="#1e90ff", height=0.6)
        ax2.set_xlim(0, 100)
        ax2.set_xlabel("Точность, %", color="#aaa", fontsize=9)
        ax2.set_title("Точность по уровням", **_txt)
        ax2.tick_params(colors="#aaa", labelsize=8)
        ax2.spines[:].set_color("#444")
        for bar, val in zip(bars, acc_vals):
            ax2.text(val + 1, bar.get_y() + bar.get_height() / 2,
                     f"{val}%", va="center", color="#ccc", fontsize=8)

        ax3 = fig.add_subplot(2, 1, 2)
        ax3.set_facecolor(_CARD_BG)
        ax3.plot(range(1, len(times) + 1), times, color="#1e90ff", linewidth=1.5)
        ax3.axhline(sum(times) / len(times), color="#ff9800", linewidth=1, linestyle="--",
                    label=f"среднее: {sum(times)/len(times):.1f}с")
        ax3.axhline(TIMER_SECONDS := 60, color="#f44336", linewidth=1, linestyle=":",
                    label="лимит: 60с")
        ax3.set_xlabel("Вопрос №", color="#aaa", fontsize=9)
        ax3.set_ylabel("Время, с", color="#aaa", fontsize=9)
        ax3.set_title("Время на каждый вопрос", **_txt)
        ax3.tick_params(colors="#aaa", labelsize=8)
        ax3.spines[:].set_color("#444")
        ax3.legend(fontsize=8, labelcolor="#ccc", facecolor=_CARD_BG, edgecolor="#444")

        for ax in [ax1, ax2, ax3]:
            ax.set_facecolor(_CARD_BG)
            ax.tick_params(colors="#aaa")

        canvas = FigureCanvasQTAgg(fig)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas.setMinimumHeight(500)
        return canvas
