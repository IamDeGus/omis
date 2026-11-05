"""Проверки бизнес-логики склада на временной SQLite-базе."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

import unittest

from database import Database


class DatabaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "inventory.db"
        self.db = Database(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _stock_by_article(self, article: str):
        return next(row for row in self.db.list_stock() if row.article == article)

    def _product_id(self, article: str) -> int:
        return next(row["id"] for row in self.db.list_products() if row["article"] == article)

    def test_sale_drops_shelf_creates_replenishment_task(self) -> None:
        product_id = self._product_id("P-002")
        sale_id, doc_no, notes = self.db.create_sale(employee_id=3, lines=[(product_id, Decimal("15"))])
        self.assertTrue(doc_no.startswith("ЧК-"))
        stock = self._stock_by_article("P-002")
        self.assertEqual(stock.shelf_qty, Decimal("5.000"))
        self.assertEqual(stock.warehouse_qty, Decimal("6.000"))
        self.assertTrue(any("пополнение полки" in note for note in notes))

    def test_sale_without_warehouse_creates_reorder_request(self) -> None:
        product_id = self._product_id("P-008")
        # P-008: shelves 28, warehouse 0; sale 25 leaves 3 (< threshold 12).
        _, _, notes = self.db.create_sale(employee_id=3, lines=[(product_id, Decimal("25"))])
        self.assertTrue(any("дозаказ" in note for note in notes))

    def test_sale_rejects_more_than_available(self) -> None:
        product_id = self._product_id("P-008")
        with self.assertRaises(ValueError):
            self.db.create_sale(employee_id=3, lines=[(product_id, Decimal("9999"))])

    def test_return_cannot_exceed_remaining_quantity(self) -> None:
        with self.assertRaises(ValueError):
            self.db.record_return(
                document_no="ЧК-0001",
                product_id=self._product_id("P-001"),
                quantity=Decimal("3"),
                reason="Брак или повреждение",
            )
        self.db.record_return(
            document_no="ЧК-0001",
            product_id=self._product_id("P-001"),
            quantity=Decimal("2"),
            reason="Брак или повреждение",
        )
        with self.assertRaises(ValueError):
            self.db.record_return(
                document_no="ЧК-0001",
                product_id=self._product_id("P-001"),
                quantity=Decimal("1"),
                reason="Брак или повреждение",
            )

    def test_inventory_shortage_creates_writeoff_act(self) -> None:
        rows = self.db.inventory_rows(location_kind=None)
        actual = {row["id"]: Decimal(str(row["scoped_qty"])) for row in rows}
        milk_id = self._product_id("P-001")
        actual[milk_id] = actual[milk_id] - Decimal("3")
        self.db.save_inventory_results(date_text="04.11.2026", location_kind=None, actual_by_product=actual)
        # 3 единицы списаны, суммарный остаток уменьшен.
        self.assertEqual(self._stock_by_article("P-001").total, Decimal("45.000"))


if __name__ == "__main__":
    unittest.main()
