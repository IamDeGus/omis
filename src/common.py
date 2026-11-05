"""Общие виджеты и стиль приложения."""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from database import format_qty

APP_STYLE = """
QWidget {
    background-color: #F1F5F9;
    color: #1F2937;
    font-family: 'Adwaita Sans', 'Segoe UI', 'Ubuntu', 'DejaVu Sans', sans-serif;
    font-size: 12px;
}
#sidebar {
    background-color: #0F172A;
    border: none;
}
#brandTitle {
    color: #FFFFFF;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 2px;
    background-color: transparent;
}
#brandSubtitle {
    color: #94A3B8;
    font-size: 10px;
    background-color: transparent;
}
#navButton {
    background-color: transparent;
    color: #CBD5E1;
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 9px 14px;
    font-size: 13px;
}
#navButton:hover { background-color: #1E293B; color: #FFFFFF; }
#navButton:checked {
    background-color: #263A5B;
    color: #FFFFFF;
    font-weight: 700;
}
#topBar {
    background-color: #F8FAFC;
    border-bottom: 1px solid #E2E8F0;
}
#employeeButton {
    background-color: transparent;
    border: none;
    color: #0F172A;
    font-weight: 600;
    font-size: 12px;
    padding: 6px 10px;
}
#employeeButton:hover { background-color: #E2E8F0; border-radius: 6px; }
#pageTitle { color: #1F2937; font-size: 20px; font-weight: 800; background-color: transparent; }
#pageSubtitle { color: #64748B; font-size: 12px; background-color: transparent; }
#sectionTitle { color: #1F2937; font-size: 14px; font-weight: 800; background-color: transparent; }
#fieldLabel { color: #64748B; font-size: 11px; background-color: transparent; }
#breadcrumb { background-color: transparent; }
QLineEdit, QComboBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 5px;
    padding: 6px 8px;
    min-height: 28px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border: 1px solid #2563EB; }
QComboBox::drop-down { border: none; width: 24px; }
#primary {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 700;
    min-height: 32px;
    font-size: 12px;
}
#primary:hover { background-color: #1D4ED8; }
#primary:pressed { background-color: #1E40AF; }
#secondary {
    background-color: #FFFFFF;
    color: #1F2937;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    min-height: 32px;
    font-size: 12px;
}
#secondary:hover { background-color: #F8FAFC; border-color: #94A3B8; }
#linkButton {
    background-color: transparent;
    color: #2563EB;
    border: none;
    padding: 2px 0;
    font-weight: 700;
    font-size: 12px;
    text-align: left;
}
#linkButton:hover { color: #1D4ED8; }
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 7px;
    selection-background-color: #DBEAFE;
    selection-color: #111827;
    gridline-color: transparent;
}
QTableWidget::item { padding: 5px 8px; border-bottom: 1px solid #E2E8F0; }
QHeaderView::section {
    background-color: #E8EEFC;
    color: #1F2937;
    border: none;
    border-bottom: 1px solid #DDE6F8;
    padding: 8px 8px;
    font-weight: 800;
    font-size: 12px;
}
#card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
}
#card:hover { border-color: #BFDBFE; }
#cardTitle { color: #1F2937; font-size: 14px; font-weight: 800; background-color: transparent; }
#cardText { color: #64748B; font-size: 12px; background-color: transparent; }
#iconBox { background-color: #E7EEF9; border-radius: 8px; }
#footerNote { color: #64748B; font-size: 11px; background-color: transparent; }
QMessageBox { background-color: #FFFFFF; }
"""


def apply_app_style(app) -> None:
    app.setStyleSheet(APP_STYLE)
    font = QFont("Adwaita Sans", 10)
    app.setFont(font)


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def make_button(text: str, kind: str = "secondary") -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(kind)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def make_table(columns: list[str], editable_columns: set[int] | None = None) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(32)
    table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setStretchLastSection(False)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(len(columns) - 1, QHeaderView.ResizeMode.ResizeToContents)
    for index in range(1, len(columns) - 1):
        table.horizontalHeader().setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
    table.setAlternatingRowColors(False)
    _ = editable_columns or set()
    return table


def page_container() -> tuple[QWidget, QVBoxLayout]:
    widget = QWidget()
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(20, 16, 20, 18)
    layout.setSpacing(10)
    return widget, layout


def add_title(layout: QVBoxLayout, title: str, subtitle: str) -> QLabel:
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("pageSubtitle")
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    return title_label


def qty_text(value: Decimal) -> str:
    return format_qty(value)


def show_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(parent, "Нужно исправить", message)


def show_info(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)