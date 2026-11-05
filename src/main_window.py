"""Главное окно: боковая панель, верхняя панель и страницы операций."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from database import Database
from login_dialog import LoginDialog
from service import InventoryService
from pages.goods import GoodsPage
from pages.home import HomePage
from pages.inventory import InventoryPage
from pages.receipt import ReceiptPage
from pages.returns import ReturnPage
from pages.sale import SalePage

PAGE_META = {
    "home": ("Главная", "Учёт товаров"),
    "goods": ("Товары и остатки", "Товары и остатки"),
    "receipt": ("Приёмка товара", "Приёмка товара"),
    "sale": ("Продажа товара", "Продажа товара"),
    "return": ("Возврат товара", "Возврат товара"),
    "inventory": ("Инвентаризация", "Инвентаризация"),
}

NAV_ITEMS = [
    ("home", "Главная"),
    ("goods", "Товары и остатки"),
    ("receipt", "Приёмка"),
    ("sale", "Продажа"),
    ("return", "Возврат"),
    ("inventory", "Инвентаризация"),
]

ROLE_LABELS = {
    "manager": "Управляющий",
    "storekeeper": "Кладовщик",
    "cashier": "Продавец-кассир",
}

# Какие страницы доступны каждой роли
ROLE_PAGES: dict[str, set[str]] = {
    "manager": {"home", "goods", "receipt", "sale", "return", "inventory"},
    "storekeeper": {"home", "goods", "receipt", "inventory"},
    "cashier": {"home", "sale", "return"},
}


class TopBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 18, 0)
        layout.setSpacing(12)

        self.breadcrumb = QLabel()
        self.breadcrumb.setObjectName("breadcrumb")
        layout.addWidget(self.breadcrumb)
        layout.addStretch(1)

        self.user_label = QLabel()
        self.user_label.setObjectName("employeeButton")
        layout.addWidget(self.user_label)

    def set_page(self, title: str) -> None:
        self.breadcrumb.setText(
            "<span style='color:#64748B'>Учёт товаров</span>"
            "<span style='color:#94A3B8'>&nbsp;&nbsp;/&nbsp;&nbsp;</span>"
            f"<span style='color:#334155;font-weight:700'>{title}</span>"
        )

    def set_user(self, full_name: str, role: str) -> None:
        role_text = ROLE_LABELS.get(role, role)
        self.user_label.setText(f"{full_name}  ({role_text})")


class Sidebar(QWidget):
    pageRequested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(215)
        self.buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 22, 14, 20)
        layout.setSpacing(4)

        brand_title = QLabel("СКЛАД / УЧЁТ")
        brand_title.setObjectName("brandTitle")
        brand_subtitle = QLabel("Управление товарами")
        brand_subtitle.setObjectName("brandSubtitle")
        layout.addWidget(brand_title)
        layout.addWidget(brand_subtitle)
        layout.addSpacing(20)

        for page_name, label in NAV_ITEMS:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, name=page_name: self.pageRequested.emit(name)
            )
            self.buttons[page_name] = button
            layout.addWidget(button)
        layout.addStretch(1)

    def mark_current(self, page_name: str) -> None:
        for name, button in self.buttons.items():
            button.setChecked(name == page_name)

    def set_allowed_pages(self, allowed: set[str]) -> None:
        """Скрывает кнопки страниц, недоступных роли."""
        for name, button in self.buttons.items():
            button.setVisible(name in allowed)


class MainWindow(QMainWindow):
    def __init__(
        self,
        db: Database | None = None,
        service: InventoryService | None = None,
    ) -> None:
        super().__init__()
        self.db = db or Database()
        # Класс InventoryService из диаграммы: страницы UI работают через него.
        self.service = service or InventoryService(self.db)

        # --- авторизация ---
        login_dlg = LoginDialog(self.db)
        if login_dlg.exec() != LoginDialog.DialogCode.Accepted:
            self._logged_in = False
            return
        self._logged_in = True
        self._employee = login_dlg.employee_data

        self.setWindowTitle("Склад / Учёт")
        self.setMinimumSize(980, 660)
        self.resize(1240, 800)

        root = QWidget()
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        self.sidebar = Sidebar()
        self.top_bar = TopBar()
        self.stack = QStackedWidget()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.top_bar)
        right_layout.addWidget(self.stack, 1)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(right, 1)

        allowed = ROLE_PAGES.get(self._employee["role"], {"home"})

        self.pages: dict[str, QWidget] = {
            "home": HomePage(),
            "goods": GoodsPage(self.service),
            "receipt": ReceiptPage(self.service),
            "sale": SalePage(self.service),
            "return": ReturnPage(self.service),
            "inventory": InventoryPage(self.service),
        }
        for page_name, page in self.pages.items():
            self.stack.addWidget(page)
        self.pages["home"].pageRequested.connect(self.show_page)  # type: ignore[attr-defined]
        self.sidebar.pageRequested.connect(self.show_page)
        self.sidebar.set_allowed_pages(allowed)

        # Передаём сотрудника на страницу продажи
        if isinstance(self.pages["sale"], SalePage):
            self.pages["sale"].set_employee_id(self._employee["id"])

        self.top_bar.set_user(self._employee["full_name"], self._employee["role"])

        # Запускаем главную; если она недоступна — первую доступную
        first_page = "home" if "home" in allowed else next(iter(allowed))
        self.show_page(first_page)

    @property
    def is_authenticated(self) -> bool:
        return self._logged_in

    @property
    def current_user_id(self) -> int | None:
        """Идентификатор вошедшего сотрудника (InventoryUI.current_user_id)."""
        return self._employee["id"] if self._logged_in else None

    def show_page(self, page_name: str) -> None:
        allowed = ROLE_PAGES.get(self._employee["role"], set())
        if page_name not in allowed:
            page_name = "home" if "home" in allowed else next(iter(allowed))
        page = self.pages.get(page_name)
        if page is None:
            return
        refresh = getattr(page, "refresh_data", None)
        if callable(refresh):
            refresh()
        self.stack.setCurrentWidget(page)
        self.sidebar.mark_current(page_name)
        self.top_bar.set_page(PAGE_META[page_name][0])


class InventoryUI:
    """Оболочка InventoryUI из диаграммы классов.

    Оборачивает главное окно и exposing операции UML: show_main_menu,
    handle_goods_receipt, handle_sale, handle_return, handle_inventory,
    handle_reports. Приложение оперирует этим классом, не зная о Qt.
    """

    def __init__(self, window: MainWindow) -> None:
        self._window = window

    # --- состояние -----------------------------------------------------------
    @property
    def window(self) -> MainWindow:
        return self._window

    @property
    def is_authenticated(self) -> bool:
        return self._window.is_authenticated

    @property
    def current_user_id(self) -> int | None:
        return self._window.current_user_id

    def show(self) -> None:
        self._window.show()

    # --- операции из диаграммы ------------------------------------------------
    def show_main_menu(self) -> None:
        self._window.show_page("home")

    def handle_goods_receipt(self) -> None:
        self._window.show_page("receipt")

    def handle_sale(self) -> None:
        self._window.show_page("sale")

    def handle_return(self) -> None:
        self._window.show_page("return")

    def handle_inventory(self) -> None:
        self._window.show_page("inventory")

    def handle_reports(self) -> None:
        # Отчёты по остаткам показывает страница «Товары и остатки».
        self._window.show_page("goods")