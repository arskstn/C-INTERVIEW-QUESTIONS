from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QPushButton

_HINT_COLOR = QColor(160, 160, 160, 180)
_STATES = {
    "normal":      "background:#2b2b2b; color:#e0e0e0; border:2px solid #444; border-radius:8px;",
    "hover":       "background:#3a3a3a; color:#ffffff; border:2px solid #666; border-radius:8px;",
    "highlighted": "background:#1a3a5c; color:#7ec8ff; border:2px solid #7ec8ff; border-radius:8px;",
    "correct":     "background:#1a3d1a; color:#6dff6d; border:2px solid #4caf50; border-radius:8px;",
    "wrong":       "background:#3d1a1a; color:#ff6d6d; border:2px solid #f44336; border-radius:8px;",
}


class AnswerButton(QPushButton):
    def __init__(self, key_hint: str, parent=None):
        super().__init__(parent)
        self._key_hint = f"[{key_hint}]"
        self._state = "normal"
        self.setMinimumHeight(90)
        self.setFont(QFont("SF Pro Text", 13))
        self._apply_style()

    def set_state(self, state: str) -> None:
        self._state = state
        self._apply_style()
        self.update()

    def reset(self) -> None:
        self.set_state("normal")

    def _apply_style(self) -> None:
        self.setStyleSheet(f"QPushButton {{ {_STATES.get(self._state, _STATES['normal'])} }}")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("SF Mono", 9)
        painter.setFont(font)
        painter.setPen(_HINT_COLOR)
        painter.drawText(QRect(6, 4, 30, 14), Qt.AlignmentFlag.AlignLeft, self._key_hint)
        painter.end()
