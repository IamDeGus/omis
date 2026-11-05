"""Страница приёмки товара от поставщика."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from common import add_title, make_button, make_table, page_container, qty_text, show_error, show_info
from service import InventoryService


class ReceiptPage(QWidget):
    def __init__(self, service: InventoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._lines: list[tuple[int, Decimal]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content, layout = page_container()
        root.addWidget(content)

        add_title(layout, "Приёмка товара", "Регистрация поступления от поставщика.")

        # --- верхняя строка: поставщик, номер, дата ---
        top = QHBoxLayout()
        top.setSpacing(12)
        self.supplier = QComboBox()
        self.supplier.addItem("Выберите поставщика", None)
        for row in service.list_suppliers():
            self.supplier.addItem(row["name"], row["id"])
        self.document_no = QLineEdit()
        self.document_no.setPlaceholderText("Номер документа")
        self.document_no.setClearButtonEnabled(True)
        self.received_date = QLineEdit(date.today().strftime("%d.%m.%Y"))
        self.received_date.setClearButtonEnabled(True)
        top.addWidget(self._labelled("Поставщик", self.supplier), 3)
        top.addWidget(self._labelled("Номер документа", self.document_no), 2)
        top.addWidget(self._labelled("Дата", self.received_date), 2)
        layout.addLayout(top)

        # --- таблица позиций ---
        section = QLabel("Товары в поступлении")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)

        self.table = make_table(["Артикул", "Наименование", "Кол-во", "Ед."])
        self.table.setMinimumHeight(120)
        layout.addWidget(self.table, 1)

        # --- Добавление строки ---
        add_row_layout = QHBoxLayout()
        add_row_layout.setSpacing(10)
        self.product = QComboBox()
        self.product.addItem("Выберите товар", None)
        for row in service.list_products():
            self.product.addItem(f"{row['name']} ({row['article']})", row["id"])
        self.quantity = QLineEdit()
        self.quantity.setPlaceholderText("Количество")
        self.quantity.setValidator(QDoubleValidator(0.001, 1_000_000.0, 3, self))
        add_btn = make_button("Добавить строку", "secondary")
        add_btn.clicked.connect(self.add_line_from_inputs)
        add_row_layout.addWidget(self._labelled("Товар", self.product), 3)
        add_row_layout.addWidget(self._labelled("Количество", self.quantity), 1)
        add_row_layout.addWidget(self._btn_col(add_btn))
        layout.addLayout(add_row_layout)

        # --- кнопки сохранения ---
        actions = QHBoxLayout()
        actions.setSpacing(10)
        save_button = make_button("Сохранить приёмку", "primary")
        cancel_button = make_button("Отмена", "secondary")
        save_button.clicked.connect(self.save)
        cancel_button.clicked.connect(self.clear_form)
        actions.addWidget(save_button)
        actions.addWidget(cancel_button)
        actions.addStretch(1)
        layout.addLayout(actions)

    def _labelled(self, label_text: str, field: QWidget) -> QWidget:
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        column.addWidget(label)
        column.addWidget(field)
        return box

    def _btn_col(self, button: QPushButton) -> QWidget:
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        column.addWidget(QLabel(""))
        column.addWidget(button)
        return box

    def _parse_quantity(self) -> Decimal | None:
        text = self.quantity.text().strip().replace(",", ".")
        if not text:
            return None
        try:
            qty = Decimal(text)
        except Exception:
            return None
        return qty if qty > 0 else None

    def add_line_from_inputs(self) -> None:
        product_id = self.product.currentData()
        qty = self._parse_quantity()
        if product_id is None:
            show_error(self, "Выберите товар")
            return
        if qty is None:
            show_error(self, "Введите количество больше нуля")
            return
        product = next((row for row in self.service.list_products() if row["id"] == product_id), None)
        if product is None:
            show_error(self, "Товар не найден")
            return

        replaced = False
        for row_index, (existing_id, existing_qty) in enumerate(self._lines):
            if existing_id == product_id:
                self._lines[row_index] = (product_id, existing_qty + qty)
                replaced = True
                break
        if not replaced:
            self._lines.append((product_id, qty))
        self.quantity.clear()
        self._render_lines()

    def _render_lines(self) -> None:
        products = {row["id"]: row for row in self.service.list_products()}
        self.table.setRowCount(0)
        for row_index, (product_id, qty) in enumerate(self._lines):
            product = products[product_id]
            self.table.insertRow(row_index)
            cells = [product["article"], product["name"], qty_text(qty), product["unit"]]
            for column, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)

    def clear_form(self) -> None:
        self.supplier.setCurrentIndex(0)
        self.document_no.clear()
        self.received_date.setText(date.today().strftime("%d.%m.%Y"))
        self.product.setCurrentIndex(0)
        self.quantity.clear()
        self._lines.clear()
        self._render_lines()

    def refresh_data(self) -> None:
        current_id = self.product.currentData()
        self.product.blockSignals(True)
        self.product.clear()
        self.product.addItem("Выберите товар", None)
        for row in self.service.list_products():
            self.product.addItem(f"{row['name']} ({row['article']})", row["id"])
        index = self.product.findData(current_id)
        self.product.setCurrentIndex(max(index, 0))
        self.product.blockSignals(False)

    def save(self) -> None:
        supplier_id = self.supplier.currentData()
        if supplier_id is None:
            show_error(self, "Выберите поставщика")
            return
        if not self._lines:
            show_error(self, "Добавьте хотя бы одну строку в поступление")
            return
        try:
            receipt_id = self.service.record_receipt(
                supplier_id=supplier_id,
                document_no=self.document_no.text(),
                date_text=self.received_date.text(),
                lines=self._lines,
            )
        except ValueError as exc:
            show_error(self, str(exc))
            return
        show_info(self, "Приёмка", f"Приёмка сохранена (документ № {self.document_no.text().strip()}, id {receipt_id}).")
        self.clear_form()