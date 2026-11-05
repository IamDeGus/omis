"""Доменные модели системы управления инвентарём для розничных магазинов.

Имена классов соответствуют диаграмме классов из лабораторной работы:
Product, Supplier, GoodsReceipt, Sale, ReturnDocument, RestockRequest,
InventoryBalance, InventoryReport, Stocktaking, WriteOffAct, Employee.
Данные хранятся в SQLite; модели не знают о SQL и виджетах.

Часть полей из UML оформлена как свойства (product_id, receipt_id,
sale_date и т.п.), чтобы модель оставалась совместимой со схемой БД.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")


@dataclass
class Category:
    id: int
    name: str


@dataclass
class Product:
    id: int
    article: str
    name: str
    category_id: int
    unit: str
    threshold: Decimal = ZERO
    price: Decimal = ZERO
    category_name: str = ""
    quantity: Decimal = ZERO  # моментальный остаток (как quantity на UML)

    @property
    def product_id(self) -> int:
        return self.id


@dataclass
class Supplier:
    id: int
    name: str
    contact: str = ""

    @property
    def supplier_id(self) -> int:
        return self.id

    @property
    def phone(self) -> str:
        return self.contact


@dataclass
class Employee:
    id: int
    full_name: str
    role: str  # manager | storekeeper | cashier
    login: str = ""


@dataclass
class Location:
    id: int
    name: str
    kind: str  # warehouse | shelf


@dataclass
class InventoryBalance:
    """Остаток товара в конкретном месте хранения (класс InventoryBalance)."""

    product_id: int
    location_id: int
    quantity: Decimal
    location_type: str = ""  # warehouse | shelf


@dataclass
class Stock:
    """Сводная информация об остатке по товару."""

    product_id: int
    article: str
    name: str
    category_name: str
    unit: str
    warehouse_qty: Decimal
    shelf_qty: Decimal
    threshold: Decimal

    @property
    def total(self) -> Decimal:
        return self.warehouse_qty + self.shelf_qty


@dataclass
class GoodsReceiptLine:
    """Строка поступления (состав GoodsReceipt ↔ Product 1..*)."""

    product_id: int
    quantity: Decimal


@dataclass
class GoodsReceipt:
    """Поступление товара от поставщика (приёмка)."""

    supplier_id: int
    document_no: str
    date: str
    lines: list[GoodsReceiptLine] = field(default_factory=list)
    id: int | None = None

    @property
    def receipt_id(self) -> int | None:
        return self.id

    @property
    def receipt_date(self) -> str:
        return self.date


@dataclass
class SaleLine:
    product_id: int
    quantity: Decimal
    price: Decimal = ZERO


@dataclass
class Sale:
    employee_id: int
    document_no: str
    date: str
    lines: list[SaleLine] = field(default_factory=list)
    id: int | None = None

    @property
    def sale_id(self) -> int | None:
        return self.id

    @property
    def sale_date(self) -> str:
        return self.date

    @property
    def total_amount(self) -> Decimal:
        return sum((line.quantity * line.price for line in self.lines), Decimal("0"))


@dataclass
class ReturnDocument:
    """Возврат товара по ранее оформленной продаже."""

    sale_id: int
    product_id: int
    quantity: Decimal
    reason: str
    date: str
    id: int | None = None

    @property
    def return_id(self) -> int | None:
        return self.id

    @property
    def return_date(self) -> str:
        return self.date


@dataclass
class RestockRequest:
    """Заявка на дозаказ поставщику, формируется при падении остатка ниже порога."""

    product_id: int
    quantity: Decimal
    date: str
    status: str = "new"  # new | approved | ordered | cancelled
    id: int | None = None

    @property
    def request_id(self) -> int | None:
        return self.id

    @property
    def created_at(self) -> str:
        return self.date

    @property
    def requested_quantity(self) -> Decimal:
        return self.quantity

    def calculate_quantity(self) -> int:
        """Размер дозаказа (целое количество единиц)."""
        return int(self.quantity)

    def submit_for_approval(self) -> None:
        """Отправляет заявку управляющему на утверждение."""
        self.status = "approved"

    def approve(self) -> None:
        """Утверждает заявку — заказ уходит поставщику."""
        self.status = "ordered"


@dataclass
class InventoryReport:
    """Отчёт по остаткам/инвентаризации (создаётся InventoryService)."""

    report_id: int | None = None
    created_at: str = ""
    total_products: int = 0
    items: list = field(default_factory=list)  # список Stock


@dataclass
class Stocktaking:
    """Инвентаризация: сверка фактических остатков с учётными."""

    stocktaking_id: int | None = None
    stocktaking_date: str = ""
    status: str = "new"  # new | in_progress | completed
    differences: dict[int, Decimal] = field(default_factory=dict)

    def compare_quantities(
        self, expected: dict[int, Decimal], actual: dict[int, Decimal]
    ) -> dict[int, Decimal]:
        """Сверяет учётное и фактическое количество по каждому товару."""
        self.differences = {
            product_id: actual.get(product_id, Decimal("0")) - qty
            for product_id, qty in expected.items()
        }
        self.status = "in_progress"
        return self.differences

    def record_discrepancies(self) -> list[tuple[int, Decimal]]:
        """Возвращает обнаруженные расхождения (недостачи и излишки)."""
        self.status = "completed"
        return [(pid, diff) for pid, diff in sorted(self.differences.items()) if diff != 0]


@dataclass
class ShelfTask:
    """Задача кладовщику на пополнение полки со склада."""

    product_id: int
    quantity: Decimal
    date: str
    status: str = "new"  # new | done
    id: int | None = None


@dataclass
class WriteOffAct:
    """Акт на списание товара."""

    product_id: int
    quantity: Decimal
    reason: str
    date: str
    id: int | None = None
