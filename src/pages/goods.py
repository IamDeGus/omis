"""Страница «Товары и остатки»: поиск, добавление и редактирование товаров."""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from common import add_title, make_button, make_table, page_container, qty_text, show_error, show_info
from service import InventoryService


class ProductDialog(QDialog):
    def __init__(self, service: InventoryService, product_id: int | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Товар")
        self.setMinimumWidth(460)
        self._service = service
        self._product_id = product_id

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(8)

        self.article = QLineEdit()
        self.article.setPlaceholderText("Например, P-009")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Название товара")
        self.category = QComboBox()
        for category in service.list_categories():
            self.category.addItem(category.name, category.id)
        self.unit = QLineEdit("шт.")
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0, 1_000_000)
        self.threshold.setDecimals(3)
        self.threshold.setValue(10)
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 1_000_000)
        self.price.setDecimals(2)
        self.price.setPrefix("")
        self.price.setSuffix(" / ед.")

        for widget in (self.article, self.name, self.unit):
            widget.setClearButtonEnabled(True)

        if product_id is not None:
            product = service.get_product(product_id)
            self.article.setText(product.article)
            self.name.setText(product.name)
            index = self.category.findData(product.category_id)
            self.category.setCurrentIndex(max(index, 0))
            self.unit.setText(product.unit)
            self.threshold.setValue(float(product.threshold))
            self.price.setValue(float(product.price))

        layout.addRow("Артикул", self.article)
        layout.addRow("Название", self.name)
        layout.addRow("Категория", self.category)
        layout.addRow("Ед.", self.unit)
        layout.addRow("Порог полки", self.threshold)
        layout.addRow("Цена", self.price)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict:
        return {
            "product_id": self._product_id,
            "article": self.article.text(),
            "name": self.name.text(),
            "category_id": self.category.currentData(),
            "unit": self.unit.text(),
            "threshold": Decimal(str(self.threshold.value())).quantize(Decimal("0.001")),
            "price": Decimal(str(self.price.value())).quantize(Decimal("0.01")),
        }


class GoodsPage(QWidget):
    def __init__(self, service: InventoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._current_query = ""
        self._current_category_id: int | None = None
        content, layout = page_container()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(content)

        add_title(layout, "Товары и остатки", "Поиск, добавление и редактирование товаров.")

        # --- filters row ---
        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Название или артикул")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(220)
        self.category = QComboBox()
        self.category.addItem("Все категории", None)
        for category in service.list_categories():
            self.category.addItem(category.name, category.id)
        find_button = make_button("Найти", "primary")
        find_button.setFixedWidth(80)
        add_button = make_button("Добавить", "primary")
        add_button.setFixedWidth(100)
        filters.addWidget(self._labelled("Поиск", self.search), 3)
        filters.addWidget(self._labelled("Категория", self.category), 2)
        filters.addSpacing(6)
        filters.addWidget(self._btn_col(find_button))
        filters.addSpacing(14)
        filters.addWidget(self._btn_col(add_button))
        layout.addLayout(filters)

        section = QLabel("Список товаров")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)

        self.table = make_table(["Артикул", "Название", "Категория", "На складе", "Ед."])
        self.table.doubleClicked.connect(lambda *_: self.edit_selected())
        layout.addWidget(self.table, 1)

        edit_button = make_button("Изменить", "secondary")
        edit_button.clicked.connect(self.edit_selected)
        edit_button.setFixedWidth(120)
        layout.addWidget(edit_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self.search.returnPressed.connect(self.apply_filters)
        self.category.currentIndexChanged.connect(self.apply_filters)
        find_button.clicked.connect(self.apply_filters)
        add_button.clicked.connect(self.add_product)
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

    def _btn_col(self, button: QPushButton) -> QWidget:
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        column.addWidget(QLabel(""))
        column.addWidget(button)
        return box

    def apply_filters(self) -> None:
        self._current_query = self.search.text()
        self._current_category_id = self.category.currentData()
        self.refresh_data()

    def refresh_data(self) -> None:
        rows = self.service.list_stock(self._current_query, self._current_category_id)
        self.table.setRowCount(0)
        for row_index, stock in enumerate(rows):
            self.table.insertRow(row_index)
            values = [
                stock.article,
                stock.name,
                stock.category_name,
                qty_text(stock.total),
                stock.unit,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, stock.product_id)
                if column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)
        if rows:
            self.table.selectRow(0)

    def _selected_product_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def add_product(self) -> None:
        dialog = ProductDialog(self.service, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.service.save_product(**dialog.values())
        except ValueError as exc:
            show_error(self, str(exc))
            return
        self.apply_filters()
        show_info(self, "Товар", "Товар добавлен.")

    def edit_selected(self) -> None:
        product_id = self._selected_product_id()
        if product_id is None:
            show_error(self, "Выберите товар в таблице")
            return
        dialog = ProductDialog(self.service, product_id=product_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.service.save_product(**dialog.values())
        except ValueError as exc:
            show_error(self, str(exc))
            return
        self.apply_filters()
        show_info(self, "Товар", "Изменения сохранены.")