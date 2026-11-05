"""Страница оформления продажи товара."""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QTableWidgetItem, QVBoxLayout, QWidget

from common import add_title, make_button, make_table, page_container, qty_text, show_error, show_info
from service import InventoryService


class SalePage(QWidget):
    def __init__(self, service: InventoryService, parent: QWidget | None = None, employee_id: int | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.employee_id = employee_id
        self._visible_product_ids: list[int] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content, layout = page_container()
        root.addWidget(content)

        add_title(layout, "Продажа товара", "Выберите товар из доступного остатка и укажите количество.")

        # --- поиск ---
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Название или артикул")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.refresh_data)
        find_button = make_button("Найти", "primary")
        find_button.setFixedWidth(80)
        find_button.clicked.connect(self.refresh_data)
        search_row.addWidget(self._labelled("Поиск", self.search), 1)
        search_row.addWidget(self._btn_col(find_button))
        layout.addLayout(search_row)


        section = QLabel("Доступные товары")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)

        self.table = make_table(["Артикул", "Название", "Доступно", "Ед."])
        self.table.itemSelectionChanged.connect(self._fill_selected_product)
        self.table.doubleClicked.connect(lambda *_: self.quantity.setFocus())
        layout.addWidget(self.table, 1)

        # --- выбранный товар и количество ---
        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        self.selected_product = QLineEdit()
        self.selected_product.setReadOnly(True)
        self.selected_product.setPlaceholderText("Товар не выбран")
        self.quantity = QLineEdit()
        self.quantity.setPlaceholderText("Количество")
        self.quantity.setValidator(QDoubleValidator(0.001, 1_000_000.0, 3, self))
        bottom.addWidget(self._labelled("Выбранный товар", self.selected_product), 3)
        bottom.addWidget(self._labelled("Количество", self.quantity), 1)
        layout.addLayout(bottom)

        # --- кнопки ---
        actions = QHBoxLayout()
        actions.setSpacing(10)
        sell_button = make_button("Оформить продажу", "primary")
        clear_button = make_button("Очистить", "secondary")
        sell_button.clicked.connect(self.complete_sale)
        clear_button.clicked.connect(self.clear_form)
        actions.addWidget(sell_button)
        actions.addWidget(clear_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.refresh_data()

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

    def set_employee_id(self, employee_id: int) -> None:
        self.employee_id = employee_id

    def refresh_data(self) -> None:
        query = self.search.text().strip() if hasattr(self, "search") else ""
        rows = [row for row in self.service.list_stock(query) if row.total > 0]
        self.table.setRowCount(0)
        self._visible_product_ids = []
        for row in rows:
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)
            self._visible_product_ids.append(row.product_id)
            cells = [row.article, row.name, qty_text(row.total), row.unit]
            for column, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row.product_id)
                if column == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)
        if rows:
            self.table.selectRow(0)
        else:
            self.selected_product.clear()

    def _selected_product_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _fill_selected_product(self) -> None:
        product_id = self._selected_product_id()
        if product_id is None:
            self.selected_product.clear()
            return
        item = self.table.item(self.table.currentRow(), 0)
        name = self.table.item(self.table.currentRow(), 1).text()
        self.selected_product.setText(f"{name} ({item.text()})")

    def _parse_quantity(self) -> Decimal | None:
        text = self.quantity.text().strip().replace(",", ".")
        if not text:
            return None
        try:
            qty = Decimal(text)
        except Exception:
            return None
        return qty if qty > 0 else None

    def _employee_id(self) -> int:
        if self.employee_id is not None:
            return self.employee_id
        employees = self.service.list_employees()
        cashiers = [row for row in employees if row["role"] == "cashier"]
        return (cashiers[0] if cashiers else employees[0])["id"]

    def complete_sale(self) -> None:
        product_id = self._selected_product_id()
        qty = self._parse_quantity()
        if product_id is None:
            show_error(self, "Выберите товар в таблице")
            return
        if qty is None:
            show_error(self, "Введите количество больше нуля")
            return
        try:
            sale_id, document_no, notes = self.service.create_sale(employee_id=self._employee_id(), lines=[(product_id, qty)])
        except ValueError as exc:
            show_error(self, str(exc))
            return
        message = f"Продажа {document_no} оформлена (id {sale_id})."
        if notes:
            message += "\n\n" + "\n".join(notes)
        show_info(self, "Продажа", message)
        self.refresh_data()
        self.quantity.clear()

    def clear_form(self) -> None:
        self.search.clear()
        self.quantity.clear()
        self.selected_product.clear()
        self.refresh_data()