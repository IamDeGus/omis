"""Слой доступа к SQLite: схема, начальные данные и операции репозитория."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from models import Employee, Product, Stock

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "inventory.db"

Q3 = Decimal("0.001")


def hash_password(password: str) -> str:
    """Возвращает хэш пароля: salt + ':' + pbkdf2_hmac hex."""
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Проверяет пароль по сохранённому хэшу."""
    try:
        salt, dk_hex = stored_hash.split(":", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex() == dk_hex


def to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Q3)


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    contact TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('manager', 'storekeeper', 'cashier')),
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    article TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    unit TEXT NOT NULL,
    threshold NUMERIC NOT NULL DEFAULT 0 CHECK (threshold >= 0),
    price NUMERIC NOT NULL DEFAULT 0 CHECK (price >= 0)
);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('warehouse', 'shelf'))
);

CREATE TABLE IF NOT EXISTS stock (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    quantity NUMERIC NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    PRIMARY KEY (product_id, location_id)
);

CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    document_no TEXT NOT NULL UNIQUE,
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipt_items (
    receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (receipt_id, product_id)
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    document_no TEXT NOT NULL UNIQUE,
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sale_items (
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    price NUMERIC NOT NULL DEFAULT 0 CHECK (price >= 0),
    PRIMARY KEY (sale_id, product_id)
);

CREATE TABLE IF NOT EXISTS returns (
    id INTEGER PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    reason TEXT NOT NULL,
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shelf_tasks (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'done'))
);

CREATE TABLE IF NOT EXISTS reorder_requests (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'approved', 'ordered', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS inventory_checks (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'all',
    category_id INTEGER REFERENCES categories(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_items (
    check_id INTEGER NOT NULL REFERENCES inventory_checks(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    expected NUMERIC NOT NULL,
    actual NUMERIC NOT NULL,
    difference NUMERIC NOT NULL,
    PRIMARY KEY (check_id, product_id)
);

CREATE TABLE IF NOT EXISTS writeoff_acts (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity NUMERIC NOT NULL CHECK (quantity > 0),
    reason TEXT NOT NULL,
    date TEXT NOT NULL
);
"""


def _today() -> str:
    return date.today().isoformat()


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._with_connection(self._create_schema)
        self._with_connection(self._seed_if_empty)

    # --- low-level helpers -------------------------------------------------
    def _with_connection(self, fn):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return fn(conn)

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(SCHEMA)
        conn.commit()

    def _location_id(self, conn: sqlite3.Connection, kind: str) -> int:
        return conn.execute("SELECT id FROM locations WHERE kind = ?", (kind,)).fetchone()["id"]

    # --- seed data ---------------------------------------------------------
    def _seed_if_empty(self, conn: sqlite3.Connection) -> None:
        if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
            return

        conn.executemany(
            "INSERT INTO categories(name) VALUES (?)",
            [("Молочные продукты",), ("Выпечка",), ("Фрукты и овощи",), ("Бакалея",), ("Бытовая химия",)],
        )
        conn.executemany(
            "INSERT INTO suppliers(name, contact) VALUES (?, ?)",
            [
                ("ООО «Молочный комбинат»", "+375 17 200-00-01"),
                ("ИП «Хлебный дом»", "+375 17 200-00-02"),
                ("СОАО «Агрофрукт»", "+375 17 200-00-03"),
                ("ООО «Бакалея-Опт»", "+375 17 200-00-04"),
            ],
        )
        default_hash = hash_password("123")
        conn.executemany(
            "INSERT INTO employees(full_name, role, login, password_hash) VALUES (?, ?, ?, ?)",
            [
                ("Поплавский Кирилл Дмитриевич", "manager", "manager", default_hash),
                ("Сидорова Мария Викторовна", "storekeeper", "storekeeper", default_hash),
                ("Иванова Анна Сергеевна", "cashier", "cashier", default_hash),
            ],
        )
        conn.executemany(
            "INSERT INTO locations(name, kind) VALUES (?, ?)",
            [("Основной склад", "warehouse"), ("Торговый зал", "shelf")],
        )

        category_id = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM categories")}
        products = [
            ("P-001", "Молоко 1 л", "Молочные продукты", "шт.", 10, 2.35, 18, 30),
            ("P-002", "Хлеб белый", "Выпечка", "шт.", 10, 1.80, 6, 20),
            ("P-003", "Яблоки", "Фрукты и овощи", "кг", 15, 3.20, 25, 47),
            ("P-004", "Чай чёрный", "Бакалея", "упак.", 8, 9.50, 10, 5),
            ("P-005", "Сыр твёрдый", "Молочные продукты", "кг", 6, 18.90, 7, 12),
            ("P-006", "Гречка 1 кг", "Бакалея", "шт.", 12, 2.10, 30, 40),
            ("P-007", "Кефир 1 л", "Молочные продукты", "шт.", 10, 2.55, 12, 16),
            ("P-008", "Бананы", "Фрукты и овощи", "кг", 12, 4.10, 0, 28),
        ]
        for article, name, category, unit, threshold, price, warehouse, shelf in products:
            cur = conn.execute(
                "INSERT INTO products(article, name, category_id, unit, threshold, price) VALUES (?, ?, ?, ?, ?, ?)",
                (article, name, category_id[category], unit, threshold, price),
            )
            product_id = cur.lastrowid
            warehouse_id = self._location_id(conn, "warehouse")
            shelf_id = self._location_id(conn, "shelf")
            conn.execute("INSERT INTO stock(product_id, location_id, quantity) VALUES (?, ?, ?)", (product_id, warehouse_id, warehouse))
            conn.execute("INSERT INTO stock(product_id, location_id, quantity) VALUES (?, ?, ?)", (product_id, shelf_id, shelf))

        # Начальная продажа нужна для демонстрации окна возврата.
        cashier_id = conn.execute("SELECT id FROM employees WHERE login = 'cashier'").fetchone()["id"]
        cur = conn.execute(
            "INSERT INTO sales(employee_id, document_no, date) VALUES (?, ?, ?)",
            (cashier_id, "ЧК-0001", _today()),
        )
        sale_id = cur.lastrowid
        product_id = {row["article"]: row["id"] for row in conn.execute("SELECT id, article FROM products")}
        conn.executemany(
            "INSERT INTO sale_items(sale_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
            [
                (sale_id, product_id["P-001"], 2, 2.35),
                (sale_id, product_id["P-004"], 1, 9.50),
            ],
        )
        conn.commit()

    # --- queries for UI ----------------------------------------------------
    def list_categories(self) -> list[CategoryRow]:  # type: ignore[name-defined]
        with closing(self._connect()) as conn:
            return [CategoryRow(row["id"], row["name"]) for row in conn.execute("SELECT id, name FROM categories ORDER BY name")]

    def list_suppliers(self) -> list[sqlite3.Row]:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()

    def list_employees(self) -> list[sqlite3.Row]:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT id, full_name, role FROM employees ORDER BY id").fetchall()

    def authenticate(self, login: str, password: str) -> Employee | None:
        """Проверяет логин/пароль и возвращает Employee при успехе."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id, full_name, role, login, password_hash FROM employees WHERE login = ?",
                (login.strip(),),
            ).fetchone()
            if row is None:
                return None
            if not verify_password(password, row["password_hash"]):
                return None
            return Employee(id=row["id"], full_name=row["full_name"], role=row["role"], login=row["login"])

    def change_password(self, employee_id: int, new_password: str) -> None:
        """Меняет пароль сотрудника."""
        new_hash = hash_password(new_password)
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "UPDATE employees SET password_hash = ? WHERE id = ?",
                    (new_hash, employee_id),
                )

    def list_products(self) -> list[sqlite3.Row]:
        with closing(self._connect()) as conn:
            return conn.execute(
                "SELECT id, article, name, unit FROM products ORDER BY article"
            ).fetchall()

    def list_stock(self, query: str = "", category_id: int | None = None) -> list[Stock]:
        sql = [
            "SELECT p.id AS product_id, p.article, p.name, c.name AS category_name, p.unit, p.threshold,",
            "  COALESCE(SUM(CASE WHEN l.kind='warehouse' THEN s.quantity ELSE 0 END), 0) AS warehouse_qty,",
            "  COALESCE(SUM(CASE WHEN l.kind='shelf' THEN s.quantity ELSE 0 END), 0) AS shelf_qty",
            "FROM products p",
            "JOIN categories c ON c.id = p.category_id",
            "LEFT JOIN stock s ON s.product_id = p.id",
            "LEFT JOIN locations l ON l.id = s.location_id",
            "WHERE 1=1",
        ]
        params: list[Any] = []
        query = query.strip()
        if query:
            like = f"%{query.lower()}%"
            sql.append("AND (lower(p.article) LIKE ? OR lower(p.name) LIKE ?)")
            params += [like, like]
        if category_id:
            sql.append("AND p.category_id = ?")
            params.append(category_id)
        sql.append("GROUP BY p.id ORDER BY p.article")
        with closing(self._connect()) as conn:
            return [
                Stock(
                    product_id=row["product_id"],
                    article=row["article"],
                    name=row["name"],
                    category_name=row["category_name"],
                    unit=row["unit"],
                    warehouse_qty=to_decimal(row["warehouse_qty"]),
                    shelf_qty=to_decimal(row["shelf_qty"]),
                    threshold=to_decimal(row["threshold"]),
                )
                for row in conn.execute("\n".join(sql), params)
            ]

    def inventory_rows(self, category_id: int | None = None, location_kind: str | None = None) -> list[sqlite3.Row]:
        scoped_expr = (
            "COALESCE(SUM(s.quantity), 0)"
            if location_kind is None
            else "COALESCE(SUM(CASE WHEN l.kind = ? THEN s.quantity ELSE 0 END), 0)"
        )
        sql = [
            "SELECT p.id, p.article, p.name,",
            "  COALESCE(SUM(CASE WHEN l.kind='warehouse' THEN s.quantity ELSE 0 END), 0) AS warehouse_qty,",
            "  COALESCE(SUM(CASE WHEN l.kind='shelf' THEN s.quantity ELSE 0 END), 0) AS shelf_qty,",
            f"  {scoped_expr} AS scoped_qty",
            "FROM products p",
            "LEFT JOIN stock s ON s.product_id = p.id",
            "LEFT JOIN locations l ON l.id = s.location_id",
            "WHERE 1=1",
        ]
        params: list[Any] = [] if location_kind is None else [location_kind]
        if category_id:
            sql.append("AND p.category_id = ?")
            params.append(category_id)
        sql.append("GROUP BY p.id ORDER BY p.article")
        with closing(self._connect()) as conn:
            return conn.execute("\n".join(sql), params).fetchall()

    def find_sale(self, document_no: str) -> sqlite3.Row | None:
        with closing(self._connect()) as conn:
            return conn.execute(
                "SELECT s.id, s.document_no, s.date, e.full_name AS employee_name FROM sales s JOIN employees e ON e.id = s.employee_id WHERE s.document_no = ?",
                (document_no.strip(),),
            ).fetchone()

    def sale_items(self, sale_id: int) -> list[sqlite3.Row]:
        with closing(self._connect()) as conn:
            return conn.execute(
                "SELECT si.product_id, p.article, p.name, p.unit, si.quantity, si.price,"
                "  COALESCE((SELECT SUM(r.quantity) FROM returns r WHERE r.sale_id = si.sale_id AND r.product_id = si.product_id), 0) AS returned_qty"
                " FROM sale_items si JOIN products p ON p.id = si.product_id WHERE si.sale_id = ? ORDER BY p.article",
                (sale_id,),
            ).fetchall()

    def get_product(self, product_id: int) -> Product:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT p.id, p.article, p.name, p.category_id, p.unit, p.threshold, p.price, c.name AS category_name"
                " FROM products p JOIN categories c ON c.id = p.category_id WHERE p.id = ?",
                (product_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Товар не найден")
            return Product(row["id"], row["article"], row["name"], row["category_id"], row["unit"], to_decimal(row["threshold"]), to_decimal(row["price"]), row["category_name"])

    # --- mutations ---------------------------------------------------------
    def save_product(self, *, product_id: int | None, article: str, name: str, category_id: int, unit: str, threshold: Decimal, price: Decimal) -> int:
        article = article.strip()
        name = name.strip()
        unit = unit.strip() or "шт."
        if not article or not name:
            raise ValueError("Артикул и название обязательны")
        if threshold < 0 or price < 0:
            raise ValueError("Порог и цена не могут быть отрицательными")
        with closing(self._connect()) as conn:
            duplicate = conn.execute(
                "SELECT id FROM products WHERE lower(article) = lower(?) AND (? IS NULL OR id <> ?)",
                (article, product_id, product_id),
            ).fetchone()
            if duplicate:
                raise ValueError(f"Артикул {article} уже используется")
            with conn:
                if product_id is None:
                    cur = conn.execute(
                        "INSERT INTO products(article, name, category_id, unit, threshold, price) VALUES (?, ?, ?, ?, ?, ?)",
                        (article, name, category_id, unit, float(threshold), float(price)),
                    )
                    new_id = cur.lastrowid
                    for kind in ("warehouse", "shelf"):
                        conn.execute("INSERT INTO stock(product_id, location_id, quantity) VALUES (?, ?, 0)", (new_id, self._location_id(conn, kind)))
                    return new_id
                conn.execute(
                    "UPDATE products SET article=?, name=?, category_id=?, unit=?, threshold=?, price=? WHERE id=?",
                    (article, name, category_id, unit, float(threshold), float(price), product_id),
                )
                return product_id

    def record_receipt(self, *, supplier_id: int, document_no: str, date_text: str, lines: Iterable[tuple[int, Decimal]]) -> int:
        document_no = document_no.strip()
        if not document_no:
            raise ValueError("Номер документа обязателен")
        parsed_date = self._parse_date(date_text)
        rows = self._normalized_lines(lines)
        with closing(self._connect()) as conn:
            with conn:
                if conn.execute("SELECT 1 FROM receipts WHERE document_no = ?", (document_no,)).fetchone():
                    raise ValueError(f"Документ {document_no} уже сохранён")
                cur = conn.execute(
                    "INSERT INTO receipts(supplier_id, document_no, date) VALUES (?, ?, ?)",
                    (supplier_id, document_no, parsed_date),
                )
                receipt_id = cur.lastrowid
                warehouse_id = self._location_id(conn, "warehouse")
                for product_id, qty in rows:
                    conn.execute("INSERT INTO receipt_items(receipt_id, product_id, quantity) VALUES (?, ?, ?)", (receipt_id, product_id, float(qty)))
                    self._add_stock(conn, product_id, warehouse_id, qty)
                return receipt_id

    def create_sale(self, *, employee_id: int, lines: Iterable[tuple[int, Decimal]], date_text: str | None = None) -> tuple[int, str, list[str]]:
        parsed_date = self._parse_date(date_text or _today())
        rows = self._normalized_lines(lines)
        notes: list[str] = []
        with closing(self._connect()) as conn:
            with conn:
                document_no = self._next_document_no(conn, "sales", "ЧК")
                cur = conn.execute(
                    "INSERT INTO sales(employee_id, document_no, date) VALUES (?, ?, ?)",
                    (employee_id, document_no, parsed_date),
                )
                sale_id = cur.lastrowid
                shelf_id = self._location_id(conn, "shelf")
                for product_id, qty in rows:
                    product = conn.execute("SELECT article, name, threshold, price FROM products WHERE id=?", (product_id,)).fetchone()
                    if product is None:
                        raise ValueError("Товар не найден")
                    self._check_available(conn, product_id, qty)
                    price = to_decimal(product["price"])
                    conn.execute("INSERT INTO sale_items(sale_id, product_id, quantity, price) VALUES (?, ?, ?, ?)", (sale_id, product_id, float(qty), float(price)))
                    # Сначала списываем с полки, остаток — со склада. _check_available уже гарантировал достаточность суммарного остатка.
                    undeducted = self._deduct_stock(conn, product_id, shelf_id, qty)
                    if undeducted > 0:
                        raise ValueError("Недостаточно товара в остатках")
                    self._after_sale_product(conn, product_id, parsed_date, notes)
                return sale_id, document_no, notes

    def record_return(
        self,
        *,
        product_id: int,
        quantity: Decimal,
        reason: str,
        document_no: str | None = None,
        sale_id: int | None = None,
        date_text: str | None = None,
    ) -> int:
        parsed_date = self._parse_date(date_text or _today())
        if sale_id is not None:
            with closing(self._connect()) as conn:
                sale = conn.execute(
                    "SELECT s.id, s.document_no, s.date, e.full_name AS employee_name"
                    " FROM sales s JOIN employees e ON e.id = s.employee_id WHERE s.id = ?",
                    (sale_id,),
                ).fetchone()
        else:
            sale = self.find_sale(document_no or "")
        if sale is None:
            raise ValueError(f"Продажа {document_no or '(не указан номер)'} не найдена")
        qty = self._positive_qty(quantity)
        reason = reason.strip()
        if not reason:
            raise ValueError("Укажите причину возврата")
        with closing(self._connect()) as conn:
            with conn:
                sold = conn.execute(
                    "SELECT quantity FROM sale_items WHERE sale_id=? AND product_id=?",
                    (sale["id"], product_id),
                ).fetchone()
                if sold is None:
                    raise ValueError("Эта позиция не входит в указанную продажу")
                already = conn.execute(
                    "SELECT COALESCE(SUM(quantity), 0) FROM returns WHERE sale_id=? AND product_id=?",
                    (sale["id"], product_id),
                ).fetchone()[0]
                if qty > to_decimal(sold["quantity"]) - to_decimal(already):
                    raise ValueError("Возвращаемое количество больше, чем остаток к возврату по этой позиции")
                shelf_id = self._location_id(conn, "shelf")
                cur = conn.execute(
                    "INSERT INTO returns(sale_id, product_id, quantity, reason, date) VALUES (?, ?, ?, ?, ?)",
                    (sale["id"], product_id, float(qty), reason, parsed_date),
                )
                self._add_stock(conn, product_id, shelf_id, qty)
                return cur.lastrowid

    def save_inventory_results(self, *, date_text: str, category_id: int | None = None, location_kind: str | None = None, actual_by_product: dict[int, Decimal]) -> int:
        parsed_date = self._parse_date(date_text)
        rows = self.inventory_rows(category_id, location_kind)
        if not rows:
            raise ValueError("Нет товаров для сверки")
        for product_id, actual in actual_by_product.items():
            if actual < 0:
                raise ValueError("Фактическое количество не может быть отрицательным")
        scope = location_kind or "all"
        with closing(self._connect()) as conn:
            with conn:
                cur = conn.execute(
                    "INSERT INTO inventory_checks(date, scope, category_id, created_at) VALUES (?, ?, ?, ?)",
                    (parsed_date, scope, category_id, datetime.now().isoformat(timespec="seconds")),
                )
                check_id = cur.lastrowid
                warehouse_id = self._location_id(conn, "warehouse")
                shelf_id = self._location_id(conn, "shelf")
                for row in rows:
                    warehouse_qty = to_decimal(row["warehouse_qty"])
                    shelf_qty = to_decimal(row["shelf_qty"])
                    expected = warehouse_qty + shelf_qty if location_kind is None else to_decimal(row["scoped_qty"])
                    actual = to_decimal(actual_by_product.get(row["id"], expected))
                    diff = actual - expected
                    conn.execute(
                        "INSERT INTO inventory_items(check_id, product_id, expected, actual, difference) VALUES (?, ?, ?, ?, ?)",
                        (check_id, row["id"], float(expected), float(actual), float(diff)),
                    )
                    if location_kind is None:
                        self._reconcile_stock(conn, row["id"], warehouse_id, shelf_id, expected, actual, parsed_date)
                    else:
                        location_id = self._location_id(conn, location_kind)
                        self._reconcile_single_location(conn, row["id"], location_id, expected, actual, parsed_date)
                return check_id

    # --- additive service-level operations ------------------------------------
    def total_stock(self, product_id: int) -> Decimal:
        """Суммарный остаток товара по всем местам хранения."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM stock WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            return to_decimal(row[0])

    def stock_totals(self, product_id: int) -> Stock:
        """Сводка по остаткам одного товара (склад, полка, порог)."""
        sql = [
            "SELECT p.id AS product_id, p.article, p.name, c.name AS category_name, p.unit, p.threshold,",
            "  COALESCE(SUM(CASE WHEN l.kind='warehouse' THEN s.quantity ELSE 0 END), 0) AS warehouse_qty,",
            "  COALESCE(SUM(CASE WHEN l.kind='shelf' THEN s.quantity ELSE 0 END), 0) AS shelf_qty",
            "FROM products p",
            "JOIN categories c ON c.id = p.category_id",
            "LEFT JOIN stock s ON s.product_id = p.id",
            "LEFT JOIN locations l ON l.id = s.location_id",
            "WHERE p.id = ?",
            "GROUP BY p.id",
        ]
        with closing(self._connect()) as conn:
            row = conn.execute("\n".join(sql), (product_id,)).fetchone()
        if row is None:
            raise ValueError("Товар не найден")
        return Stock(
            product_id=row["product_id"],
            article=row["article"],
            name=row["name"],
            category_name=row["category_name"],
            unit=row["unit"],
            warehouse_qty=to_decimal(row["warehouse_qty"]),
            shelf_qty=to_decimal(row["shelf_qty"]),
            threshold=to_decimal(row["threshold"]),
        )

    def create_shelf_task(self, product_id: int, quantity: Decimal) -> int | None:
        """Создаёт открытую задачу кладовщику; возвращает id или None, если задача уже есть."""
        qty = self._positive_qty(quantity)
        with closing(self._connect()) as conn:
            with conn:
                exists = conn.execute(
                    "SELECT id FROM shelf_tasks WHERE product_id=? AND status='new'",
                    (product_id,),
                ).fetchone()
                if exists:
                    return None
                cur = conn.execute(
                    "INSERT INTO shelf_tasks(product_id, quantity, date, status) VALUES (?, ?, ?, 'new')",
                    (product_id, float(qty), _today()),
                )
                return cur.lastrowid

    def create_restock_request(self, product_id: int, quantity: Decimal) -> int:
        """Создаёт заявку на дозаказ; при открытой заявке возвращает её id."""
        qty = self._positive_qty(quantity)
        with closing(self._connect()) as conn:
            with conn:
                exists = conn.execute(
                    "SELECT id FROM reorder_requests WHERE product_id=? AND status='new'",
                    (product_id,),
                ).fetchone()
                if exists:
                    return exists["id"]
                cur = conn.execute(
                    "INSERT INTO reorder_requests(product_id, quantity, date, status) VALUES (?, ?, ?, 'new')",
                    (product_id, float(qty), _today()),
                )
                return cur.lastrowid

    def set_restock_request_status(self, request_id: int, status: str) -> None:
        """Обновляет статус заявки на дозаказ."""
        if status not in ("new", "approved", "ordered", "cancelled"):
            raise ValueError("Недопустимый статус заявки")
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "UPDATE reorder_requests SET status = ? WHERE id = ?",
                    (status, request_id),
                )

    def create_writeoff_act(
        self, product_id: int, quantity: Decimal, reason: str, date_text: str | None = None
    ) -> int:
        """Оформляет акт списания товара."""
        qty = self._positive_qty(quantity)
        if not reason.strip():
            raise ValueError("Укажите причину списания")
        with closing(self._connect()) as conn:
            with conn:
                cur = conn.execute(
                    "INSERT INTO writeoff_acts(product_id, quantity, reason, date) VALUES (?, ?, ?, ?)",
                    (product_id, float(qty), reason.strip(), self._parse_date(date_text or _today())),
                )
                return cur.lastrowid

    def last_inventory_difference(self, product_id: int) -> Decimal | None:
        """Разница из последней инвентаризации по товару (None — сверок не было)."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT ii.difference FROM inventory_items ii"
                " JOIN inventory_checks ic ON ic.id = ii.check_id"
                " WHERE ii.product_id = ?"
                " ORDER BY ic.created_at DESC, ic.id DESC LIMIT 1",
                (product_id,),
            ).fetchone()
            return to_decimal(row["difference"]) if row else None

    # --- internal stock helpers --------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _parse_date(value: str) -> str:
        text = (value or "").strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
        raise ValueError("Дата должна быть в формате ДД.ММ.ГГГГ")

    @staticmethod
    def _positive_qty(value: Decimal) -> Decimal:
        qty = to_decimal(value)
        if qty <= 0:
            raise ValueError("Количество должно быть больше нуля")
        return qty

    def _normalized_lines(self, lines: Iterable[tuple[int, Decimal]]) -> list[tuple[int, Decimal]]:
        totals: dict[int, Decimal] = {}
        for product_id, qty in lines:
            value = self._positive_qty(qty)
            totals[product_id] = totals.get(product_id, Decimal("0")) + value
        if not totals:
            raise ValueError("Добавьте хотя бы одну строку")
        return sorted(totals.items())

    def _stock_qty(self, conn: sqlite3.Connection, product_id: int, location_id: int) -> Decimal:
        row = conn.execute("SELECT quantity FROM stock WHERE product_id=? AND location_id=?", (product_id, location_id)).fetchone()
        return to_decimal(row["quantity"] if row else 0)

    def _add_stock(self, conn: sqlite3.Connection, product_id: int, location_id: int, qty: Decimal) -> None:
        conn.execute(
            "INSERT INTO stock(product_id, location_id, quantity) VALUES (?, ?, ?)"
            " ON CONFLICT(product_id, location_id) DO UPDATE SET quantity = quantity + excluded.quantity",
            (product_id, location_id, float(qty)),
        )

    def _set_stock(self, conn: sqlite3.Connection, product_id: int, location_id: int, qty: Decimal) -> None:
        conn.execute(
            "INSERT INTO stock(product_id, location_id, quantity) VALUES (?, ?, ?)"
            " ON CONFLICT(product_id, location_id) DO UPDATE SET quantity = excluded.quantity",
            (product_id, location_id, float(max(qty, Decimal("0")))),
        )

    def _check_available(self, conn: sqlite3.Connection, product_id: int, qty: Decimal) -> None:
        available = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM stock WHERE product_id = ?", (product_id,)
        ).fetchone()[0]
        if to_decimal(available) < qty:
            raise ValueError("Недостаточно товара в остатках")

    def _deduct_stock(self, conn: sqlite3.Connection, product_id: int, preferred_location_id: int, qty: Decimal) -> Decimal:
        warehouse_id = self._location_id(conn, "warehouse")
        shelf_id = self._location_id(conn, "shelf")
        order = [preferred_location_id] + [loc for loc in (shelf_id, warehouse_id) if loc != preferred_location_id]
        remaining = qty
        for location_id in order:
            current = self._stock_qty(conn, product_id, location_id)
            take = min(current, remaining)
            if take > 0:
                self._set_stock(conn, product_id, location_id, current - take)
                remaining -= take
            if remaining == 0:
                break
        return remaining

    def _after_sale_product(self, conn: sqlite3.Connection, product_id: int, date_text: str, notes: list[str]) -> None:
        product = conn.execute("SELECT article, name, threshold FROM products WHERE id = ?", (product_id,)).fetchone()
        threshold = to_decimal(product["threshold"])
        warehouse_id = self._location_id(conn, "warehouse")
        shelf_id = self._location_id(conn, "shelf")
        shelf_qty = self._stock_qty(conn, product_id, shelf_id)
        warehouse_qty = self._stock_qty(conn, product_id, warehouse_id)
        if shelf_qty > threshold:
            return
        replenish = max(threshold * 2 - shelf_qty, Decimal("1"))
        open_task = conn.execute("SELECT 1 FROM shelf_tasks WHERE product_id=? AND status='new'", (product_id,)).fetchone()
        if warehouse_qty > 0:
            if not open_task:
                qty = min(warehouse_qty, replenish)
                conn.execute("INSERT INTO shelf_tasks(product_id, quantity, date, status) VALUES (?, ?, ?, 'new')", (product_id, float(qty), date_text))
                notes.append(f"{product['article']}: создана задача кладовщику на пополнение полки ({format_qty(qty)} ед.)")
        else:
            open_request = conn.execute("SELECT 1 FROM reorder_requests WHERE product_id=? AND status='new'", (product_id,)).fetchone()
            if not open_request:
                conn.execute("INSERT INTO reorder_requests(product_id, quantity, date, status) VALUES (?, ?, ?, 'new')", (product_id, float(replenish), date_text))
                notes.append(f"{product['article']}: сформирована заявка на дозаказ поставщику ({format_qty(replenish)} ед.)")

    def _reconcile_stock(self, conn: sqlite3.Connection, product_id: int, warehouse_id: int, shelf_id: int, expected: Decimal, actual: Decimal, date_text: str) -> None:
        diff = actual - expected
        if diff == 0:
            return
        if diff > 0:
            self._add_stock(conn, product_id, shelf_id, diff)
            return
        missing = -diff
        shelf_qty = self._stock_qty(conn, product_id, shelf_id)
        take_shelf = min(shelf_qty, missing)
        if take_shelf > 0:
            self._set_stock(conn, product_id, shelf_id, shelf_qty - take_shelf)
            missing -= take_shelf
        if missing > 0:
            warehouse_qty = self._stock_qty(conn, product_id, warehouse_id)
            take_warehouse = min(warehouse_qty, missing)
            self._set_stock(conn, product_id, warehouse_id, warehouse_qty - take_warehouse)
            missing -= take_warehouse
        written_off = -diff - missing
        if written_off > 0:
            conn.execute(
                "INSERT INTO writeoff_acts(product_id, quantity, reason, date) VALUES (?, ?, ?, ?)",
                (product_id, float(written_off), "Недостача по инвентаризации", date_text),
            )

    def _reconcile_single_location(self, conn: sqlite3.Connection, product_id: int, location_id: int, expected: Decimal, actual: Decimal, date_text: str) -> None:
        diff = actual - expected
        if diff == 0:
            return
        if diff > 0:
            self._add_stock(conn, product_id, location_id, diff)
            return
        self._set_stock(conn, product_id, location_id, actual)
        conn.execute(
            "INSERT INTO writeoff_acts(product_id, quantity, reason, date) VALUES (?, ?, ?, ?)",
            (product_id, float(-diff), "Недостача по инвентаризации", date_text),
        )

    def _next_document_no(self, conn: sqlite3.Connection, table: str, prefix: str) -> str:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        candidate = f"{prefix}-{count + 1:04d}"
        suffix = count + 1
        while conn.execute(f"SELECT 1 FROM {table} WHERE document_no = ?", (candidate,)).fetchone():
            suffix += 1
            candidate = f"{prefix}-{suffix:04d}"
        return candidate


class CategoryRow(tuple):
    """Немного удобства для строк категорий: id, name."""

    __slots__ = ()

    def __new__(cls, id: int, name: str):  # noqa: A002 - имя поля совпадает с колонкой БД
        return super().__new__(cls, (id, name))

    @property
    def id(self) -> int:  # type: ignore[override]
        return self[0]

    @property
    def name(self) -> str:  # type: ignore[override]
        return self[1]


def format_qty(value: Decimal) -> str:
    quantized = to_decimal(value)
    text = format(quantized.normalize(), "f") if quantized != quantized.to_integral_value() else str(int(quantized))
    return text
