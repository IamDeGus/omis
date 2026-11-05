"""Главная страница с карточками основных операций."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from common import add_title, make_button, page_container


class HomePage(QWidget):
    pageRequested = pyqtSignal(str)

    CARDS = [
        ("goods", "☰", "Товары и остатки", "Каталог и текущее наличие"),
        ("receipt", "↓", "Приёмка товара", "Поступление от поставщика"),
        ("sale", "→", "Продажа", "Зафиксировать выдачу товара"),
        ("return", "↩", "Возврат", "Оформить возврат товара"),
        ("inventory", "📋", "Инвентаризация", "Сверить фактические остатки"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        content, content_layout = page_container()
        layout.addWidget(content)
        add_title(content_layout, "Главная", "Выберите операцию для работы с товарами.")

        cards = QGridLayout()
        cards.setSpacing(14)
        for index, (page_name, icon, title, subtitle) in enumerate(self.CARDS):
            cards.addWidget(self._make_card(page_name, icon, title, subtitle), index // 2, index % 2)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        content_layout.addLayout(cards)

        note = QLabel("Без графиков и аналитики — только основные рабочие операции.")
        note.setObjectName("footerNote")
        content_layout.addWidget(note)
        content_layout.addStretch(1)

    def _make_card(self, page_name: str, icon: str, title: str, subtitle: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 16, 20, 14)
        row.setSpacing(14)

        icon_box = QLabel(icon)
        icon_box.setObjectName("iconBox")
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setFixedSize(48, 48)
        icon_box.setStyleSheet("font-size: 22px; color: #1F2937;")
        row.addWidget(icon_box, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("cardText")
        subtitle_label.setWordWrap(True)
        open_button = make_button("Открыть  →", "linkButton")
        open_button.clicked.connect(lambda checked=False, page=page_name: self.pageRequested.emit(page))
        text_col.addWidget(title_label)
        text_col.addWidget(subtitle_label)
        text_col.addSpacing(2)
        text_col.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignLeft)
        row.addLayout(text_col, 1)
        return card
