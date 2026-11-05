"""Сервисный слой системы управления инвентарём.

Реализует классы, соответствующие диаграмме классов из лабораторной работы:
InventoryService, а также роли сотрудников Manager, WarehouseKeeper и Cashier
(в диаграмме они связаны отношением uses с InventoryUI и делегируют свою
работу InventoryService). Доступ к данным — через класс Database из
src/database.py; класс InventoryService также пробрасывает на него все
остальные (справочные) запросы, чтобы страницы UI могли работать через сервис.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from models import (
    Employee,
    GoodsReceipt,
    InventoryReport,
    ReturnDocument,
    RestockRequest,
    Sale,
    Stock,
)

_TODAY = lambda: date.today().isoformat()  # noqa: E731


class InventoryService:
    """Реализует операции InventoryService из диаграммы классов.

    Собственные методы соответствуют операциям UML:
    receive_goods, process_sale, process_return, check_stock,
    create_replenishment_task, create_restock_request,
    perform_stocktaking, record_discrepancy.
    Все прочие (справочные) запросы делегируются слою данных.
    """

    def __init__(self, db: Any, low_stock_threshold: int = 10) -> None:
        self._db = db
        self.low_stock_threshold = low_stock_threshold

    def __getattr__(self, name: str) -> Any:
        # Делегирование: страницы UI получают через сервис и списки,
        # и справочники. К приватным атрибутам сервис не пробрасывает.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._db, name)

    # --- приёмка ------------------------------------------------------------
    def receive_goods(self, receipt: GoodsReceipt) -> int:
        """Фиксирует поступление товара от поставщика и увеличивает склад."""
        receipt_id = self._db.record_receipt(
            supplier_id=receipt.supplier_id,
            document_no=receipt.document_no,
            date_text=receipt.date,
            lines=[(line.product_id, line.quantity) for line in receipt.lines],
        )
        receipt.id = receipt_id
        return receipt_id

    # --- продажи и возвраты --------------------------------------------------
    def process_sale(self, sale: Sale):
        """Оформляет продажу: списывает с полки, затем со склада."""
        result = self._db.create_sale(
            employee_id=sale.employee_id,
            lines=[(line.product_id, line.quantity) for line in sale.lines],
        )
        sale.id = result[0]
        return result

    def process_return(self, return_doc: ReturnDocument) -> int:
        """Оформляет возврат ранее проданного товара."""
        return_id = self._db.record_return(
            sale_id=return_doc.sale_id,
            product_id=return_doc.product_id,
            quantity=return_doc.quantity,
            reason=return_doc.reason,
            date_text=return_doc.date,
        )
        return_doc.id = return_id
        return return_id

    # --- остатки -------------------------------------------------------------
    def check_stock(self, product_id: int) -> int:
        """Возвращает суммарный остаток товара (как на диаграмме: int)."""
        return int(self._db.total_stock(product_id))

    def create_replenishment_task(self, product_id: int) -> int | None:
        """Создаёт кладовщику задачу на пополнение полки со склада."""
        totals = self._db.stock_totals(product_id)
        replenish = max(totals.threshold * 2 - totals.shelf_qty, Decimal("1"))
        return self._db.create_shelf_task(product_id, min(totals.warehouse_qty, replenish))

    def create_restock_request(
        self, product_id: int, quantity: Decimal | None = None
    ) -> RestockRequest:
        """Формирует заявку на дозаказ поставщику и возвращает её модель."""
        if quantity is None:
            totals = self._db.stock_totals(product_id)
            quantity = max(totals.threshold * 2 - totals.shelf_qty, Decimal("1"))
        request_id = self._db.create_restock_request(product_id, quantity)
        return RestockRequest(
            product_id=product_id,
            quantity=quantity,
            date=_TODAY(),
            id=request_id,
        )

    # --- инвентаризация и отчёты ---------------------------------------------
    def perform_stocktaking(
        self,
        *,
        date_text: str,
        location_kind: str | None = None,
        category_id: int | None = None,
        actual_by_product: dict[int, Decimal],
    ) -> InventoryReport:
        """Сохраняет результаты сверки и формирует InventoryReport."""
        check_id = self._db.save_inventory_results(
            date_text=date_text,
            category_id=category_id,
            location_kind=location_kind,
            actual_by_product=actual_by_product,
        )
        return InventoryReport(
            report_id=check_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            total_products=len(actual_by_product),
        )

    def view_inventory_report(
        self, category_id: int | None = None
    ) -> InventoryReport:
        """Отчёт по текущим остаткам (для управляющего)."""
        rows = self._db.list_stock("", category_id) if category_id else self._db.list_stock()
        return InventoryReport(
            created_at=datetime.now().isoformat(timespec="seconds"),
            total_products=len(rows),
            items=rows,
        )

    def record_discrepancy(self, product_id: int) -> int:
        """Оформляет акт списания по последней незакрытой недостаче товара."""
        diff = self._db.last_inventory_difference(product_id)
        if diff is None or diff >= 0:
            raise ValueError("Нет незарегистрированной недостачи по этому товару")
        return self._db.create_writeoff_act(
            product_id,
            -diff,
            "Недостача по инвентаризации",
            _TODAY(),
        )

    # --- сводка по одному товару ---------------------------------------------
    @property
    def stock_statement_class(self) -> type[Stock]:  # pragma: no cover
        """Доступ к классу сводки (для читаемости зависимостей)."""
        return Stock


# --- роли сотрудников (классы Manager, WarehouseKeeper, Cashier из UML) -------


class Manager(Employee):
    """Управляющий магазином: утверждает заказы и смотрит отчёты."""

    def __init__(self, *, id: int, full_name: str, service: "InventoryService") -> None:
        super().__init__(id=id, full_name=full_name, role="manager")
        self.service = service

    def create_supplier_order(
        self, product_id: int, quantity: Decimal | None = None
    ) -> RestockRequest:
        """Формирует и утверждает заявку на дозаказ поставщику."""
        request = self.service.create_restock_request(product_id, quantity)
        request.submit_for_approval()
        request.approve()
        self.service.set_restock_request_status(request.request_id, request.status)
        return request

    def view_inventory_report(self, category_id: int | None = None) -> InventoryReport:
        """Возвращает отчёт по остаткам."""
        return self.service.view_inventory_report(category_id)


class WarehouseKeeper(Employee):
    """Кладовщик: приёмка товара и инвентаризация."""

    def __init__(self, *, id: int, full_name: str, service: "InventoryService") -> None:
        super().__init__(id=id, full_name=full_name, role="storekeeper")
        self.service = service

    def register_goods_receipt(self, receipt: GoodsReceipt) -> int:
        """Регистрирует поступление товара от поставщика."""
        return self.service.receive_goods(receipt)

    def perform_stocktaking(self, **kwargs) -> InventoryReport:
        """Проводит инвентаризацию и возвращает отчёт."""
        return self.service.perform_stocktaking(**kwargs)


class Cashier(Employee):
    """Продавец-кассир: продажа товара и оформление возвратов."""

    def __init__(self, *, id: int, full_name: str, service: "InventoryService") -> None:
        super().__init__(id=id, full_name=full_name, role="cashier")
        self.service = service

    def process_sale(self, sale: Sale):
        """Оформляет продажу товара покупателю."""
        return self.service.process_sale(sale)

    def register_return(self, return_doc: ReturnDocument) -> int:
        """Оформляет возврат товара по продаже."""
        return self.service.process_return(return_doc)


def make_role(employee: Employee, service: InventoryService):
    """Строит ролевой класс (Manager/WarehouseKeeper/Cashier) из Employee."""
    kwargs = {"id": employee.id, "full_name": employee.full_name, "service": service}
    rules = {
        "manager": Manager,
        "storekeeper": WarehouseKeeper,
        "cashier": Cashier,
    }
    role_class = rules.get(employee.role)
    if role_class is None:
        raise ValueError(f"Неизвестная роль сотрудника: {employee.role}")
    return role_class(**kwargs)
