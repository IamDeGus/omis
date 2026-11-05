"""Страница оформления возврата ранее проданного товара."""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QTableWidgetItem, QVBoxLayout, QWidget

from common import add_title, make_button, make_table, page_container, qty_text, show_error, show_info
from database import to_decimal
from service import InventoryService

REASONS = ["Брак или повреждение", "Товар не подошёл", "Ошибка при продаже", "Истёк срок годности", "Другое"]


class ReturnPage(QWidget):
    def __init__(self, service: InventoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._sale_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content, layout = page_container()
        root.addWidget(content)

        add_title(layout, "Возврат товара", "Оформите возврат ранее проданного товара.")

        # --- поиск продажи ---
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.document_no = QLineEdit("ЧК-0001")
        self.document_no.setPlaceholderText("Номер документа")
        self.document_no.setClearButtonEnabled(True)
        find_button = make_button("Найти продажу", "primary")
        find_button.clicked.connect(self.find_sale)
        self.document_no.returnPressed.connect(self.find_sale)
        search_row.addWidget(self._labelled("Номер продажи", self.document_no), 1)
        search_row.addWidget(self._btn_col(find_button))
        layout.addLayout(search_row)

        section = QLabel("Позиции продажи")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)

        self.table = make_table(["Артикул", "Название", "Продано", "Ед."])
        self.table.setMinimumHeight(110)
        self.table.itemSelectionChanged.connect(self._sync_position_combo)
        self.table.doubleClicked.connect(lambda *_: self.quantity.setFocus())
        layout.addWidget(self.table, 1)

        # --- товар для возврата и количество ---
        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        self.position = QComboBox()
        self.position.addItem("Выберите позицию", None)
        self.position.currentIndexChanged.connect(self._select_table_from_combo)
        self.quantity = QLineEdit()
        self.quantity.setPlaceholderText("Количество")
        self.quantity.setValidator(QDoubleValidator(0.001, 1_000_000.0, 3, self))
        bottom.addWidget(self._labelled("Товар для возврата", self.position), 3)
        bottom.addWidget(self._labelled("Количество", self.quantity), 1)
        layout.addLayout(bottom)

        # --- причина ---
        reason_row = QHBoxLayout()
        reason_row.setSpacing(12)
        self.reason = QComboBox()
        self.reason.addItem("Выберите причину", None)
        for reason in REASONS:
            self.reason.addItem(reason, reason)
        reason_row.addWidget(self._labelled("Причина", self.reason), 1)
        reason_row.addStretch(1)
        layout.addLayout(reason_row)

        # --- кнопки ---
        actions = QHBoxLayout()
        actions.setSpacing(10)
        return_button = make_button("Оформить возврат", "primary")
        cancel_button = make_button("Отмена", "secondary")
        return_button.clicked.connect(self.complete_return)
        cancel_button.clicked.connect(self.clear_form)
        actions.addWidget(return_button)
        actions.addWidget(cancel_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.find_sale(silent=True)

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

    def find_sale(self, silent: bool = False) -> None:
        document_no = self.document_no.text().strip()
        sale = self.service.find_sale(document_no)
        if sale is None:
            if not silent:
                show_error(self, "Продажа не найдена. Проверьте номер документа.")
            self._sale_id = None
            self.table.setRowCount(0)
            self.position.clear()
            self.position.addItem("Выберите позицию", None)
            return
        self._sale_id = sale["id"]
        self.refresh_data()
        if not silent:
            show_info(self, "Возврат", f"Найдена продажа {sale['document_no']} от {sale['date']} ({sale['employee_name']}).")

    def refresh_data(self) -> None:
        if self._sale_id is None:
            return
        items = self.service.sale_items(self._sale_id)
        self.table.setRowCount(0)
        self.position.blockSignals(True)
        self.position.clear()
        self.position.addItem("Выберите позицию", None)
        for row_index, item in enumerate(items):
            sold = to_decimal(item["quantity"])
            returned = to_decimal(item["returned_qty"])
            returnable = sold - returned
            self.table.insertRow(row_index)
            cells = [item["article"], item["name"], qty_text(sold), item["unit"]]
            for column, value in enumerate(cells):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item["product_id"])
                cell.setData(Qt.ItemDataRole.UserRole + 1, returnable)
                if column == 2:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, cell)
            if returnable > 0:
                self.position.addItem(f"{item['name']} ({item['article']}) — к возврату {qty_text(returnable)}", item["product_id"])
        self.position.blockSignals(False)
        if items:
            self.table.selectRow(0)

    def _selected_product_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return self.position.currentData()
        item = self.table.item(selected[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _sync_position_combo(self) -> None:
        product_id = self._selected_product_id()
        if product_id is None:
            return
        index = self.position.findData(product_id)
        if index >= 0 and index != self.position.currentIndex():
            self.position.blockSignals(True)
            self.position.setCurrentIndex(index)
            self.position.blockSignals(False)

    def _select_table_from_combo(self) -> None:
        product_id = self.position.currentData()
        if product_id is None:
            return
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == product_id:
                self.table.selectRow(row_index)
                break

    def _parse_quantity(self) -> Decimal | None:
        text = self.quantity.text().strip().replace(",", ".")
        if not text:
            return None
        try:
            qty = Decimal(text)
        except Exception:
            return None
        return qty if qty > 0 else None

    def complete_return(self) -> None:
        if self._sale_id is None:
            show_error(self, "Найдите продажу по номеру документа")
            return
        product_id = self.position.currentData() or self._selected_product_id()
        qty = self._parse_quantity()
        reason = self.reason.currentData()
        if product_id is None:
            show_error(self, "Выберите позицию для возврата")
            return
        if qty is None:
            show_error(self, "Введите количество больше нуля")
            return
        if not reason:
            show_error(self, "Выберите причину возврата")
            return
        try:
            return_id = self.service.record_return(
                document_no=self.document_no.text(),
                product_id=product_id,
                quantity=qty,
                reason=reason,
            )
        except ValueError as exc:
            show_error(self, str(exc))
            return
        show_info(self, "Возврат", f"Возврат оформлен (id {return_id}). Остаток возвращён в торговый зал.")
        self.quantity.clear()
        self.refresh_data()

    def clear_form(self) -> None:
        self.document_no.clear()
        self._sale_id = None
        self.table.setRowCount(0)
        self.position.clear()
        self.position.addItem("Выберите позицию", None)
        self.reason.setCurrentIndex(0)
        self.quantity.clear()