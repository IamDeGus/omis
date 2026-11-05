"""Страница инвентаризации: сверка фактических остатков с учётными."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QComboBox, QTableWidgetItem, QVBoxLayout, QWidget

from common import add_title, make_button, make_table, page_container, qty_text, show_error, show_info
from database import to_decimal
from service import InventoryService

SCOPES = [("Все места", None), ("Основной склад", "warehouse"), ("Торговый зал", "shelf")]


class InventoryPage(QWidget):
    def __init__(self, service: InventoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._rows: list[tuple[int, Decimal, QLineEdit]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content, layout = page_container()
        root.addWidget(content)

        add_title(layout, "Инвентаризация", "Сверка фактического количества с учётными остатками.")

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.scope = QComboBox()
        for label, kind in SCOPES:
            self.scope.addItem(label, kind)
        self.scope.setCurrentIndex(0)
        self.inventory_date = QLineEdit(date.today().strftime("%d.%m.%Y"))
        self.inventory_date.setClearButtonEnabled(True)
        start_button = make_button("Начать сверку", "primary")
        start_button.clicked.connect(self.start_check)
        controls.addWidget(self._labelled("Склад", self.scope), 1)
        controls.addWidget(self._labelled("Дата", self.inventory_date), 1)
        controls.addWidget(self._btn_col(start_button))
        controls.addStretch(1)
        layout.addLayout(controls)

        section = QLabel("Проверка остатков")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)

        self.table = make_table(["Артикул", "Товар", "По учёту", "Фактически", "Разница"])
        self.table.setColumnWidth(3, 150)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        save_button = make_button("Сохранить результаты", "primary")
        cancel_button = make_button("Отменить", "secondary")
        save_button.clicked.connect(self.save_results)
        cancel_button.clicked.connect(self.clear_form)
        actions.addWidget(save_button)
        actions.addWidget(cancel_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.start_check(show_message=False)

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

    def _btn_col(self, button) -> QWidget:
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        column.addWidget(QLabel(""))
        column.addWidget(button)
        return box

    def refresh_data(self) -> None:
        self.start_check(show_message=False)

    def start_check(self, show_message: bool = True) -> None:
        rows = self.service.inventory_rows(location_kind=self.scope.currentData())
        self._rows.clear()
        self.table.setRowCount(0)
        for row_index, row in enumerate(rows):
            expected = to_decimal(row["scoped_qty"])
            self.table.insertRow(row_index)
            for column, value in enumerate([row["article"], row["name"]]):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column, item)
            expected_item = QTableWidgetItem(qty_text(expected))
            expected_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            expected_item.setFlags(expected_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, 2, expected_item)
            actual_edit = QLineEdit()
            actual_edit.setPlaceholderText("Введите")
            actual_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            actual_edit.setClearButtonEnabled(True)
            actual_edit.setProperty("product_id", row["id"])
            actual_edit.setStyleSheet(
                "QLineEdit {"
                "  border: 1px solid #CBD5E1;"
                "  border-radius: 3px;"
                "  padding: 0px 4px;"
                "  margin: 0px;"
                "  background: #FFFFFF;"
                "  font-size: 12px;"
                "}"
            )
            actual_edit.textChanged.connect(lambda _text, ri=row_index: self._update_difference(ri))

            # Оборачиваем в контейнер с вертикальным центрированием
            wrapper = QWidget()
            wrapper.setStyleSheet("background: transparent;")
            wl = QVBoxLayout(wrapper)
            wl.setContentsMargins(2, 0, 2, 0)
            wl.setSpacing(0)
            wl.addStretch(1)
            wl.addWidget(actual_edit)
            wl.addStretch(1)
            self.table.setCellWidget(row_index, 3, wrapper)
            self.table.setRowHeight(row_index, 34)
            diff_item = QTableWidgetItem("—")
            diff_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            diff_item.setFlags(diff_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, 4, diff_item)
            self._rows.append((row["id"], expected, actual_edit))
        if show_message:
            show_info(self, "Инвентаризация", "Список товаров обновлён. Введите фактические количества.")

    def _update_difference(self, row_index: int) -> None:
        if row_index >= len(self._rows):
            return
        _, expected, edit = self._rows[row_index]
        text = edit.text().strip().replace(",", ".")
        diff_item = self.table.item(row_index, 4)
        if not text:
            diff_item.setText("—")
            return
        try:
            actual = Decimal(text)
            if actual < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            diff_item.setText("!")
            return
        diff = actual - expected
        if diff == 0:
            diff_item.setText("0")
        else:
            diff_item.setText(f"{'+' if diff > 0 else ''}{qty_text(diff)}")

    def _parse_actuals(self) -> dict[int, Decimal] | None:
        actuals: dict[int, Decimal] = {}
        for product_id, _expected, edit in self._rows:
            text = edit.text().strip().replace(",", ".")
            if not text:
                show_error(self, "Введите фактическое количество по всем товарам")
                edit.setFocus()
                return None
            try:
                actual = Decimal(text)
                if actual < 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                show_error(self, "Фактическое количество должно быть неотрицательным числом")
                edit.setFocus()
                return None
            actuals[product_id] = actual
        return actuals

    def save_results(self) -> None:
        if not self._rows:
            show_error(self, "Сначала нажмите «Начать сверку»")
            return
        actuals = self._parse_actuals()
        if actuals is None:
            return
        try:
            check_id = self.service.save_inventory_results(
                date_text=self.inventory_date.text(),
                location_kind=self.scope.currentData(),
                actual_by_product=actuals,
            )
        except ValueError as exc:
            show_error(self, str(exc))
            return
        show_info(self, "Инвентаризация", f"Результаты сверки сохранены (id {check_id}).")
        self.start_check(show_message=False)

    def clear_form(self) -> None:
        self.table.setRowCount(0)
        self._rows.clear()
        self.inventory_date.setText(date.today().strftime("%d.%m.%Y"))
        self.scope.setCurrentIndex(1)