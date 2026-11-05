"""Точка входа приложения «Склад / Учёт».

Содержит классы RetailInventoryApp (<<main>>) и ApplicationInitializer
(<<injector>>) из диаграммы классов лабораторной работы.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from common import apply_app_style  # noqa: E402
from database import Database  # noqa: E402
from main_window import InventoryUI, MainWindow  # noqa: E402
from service import InventoryService  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover
    from models import Employee


class ApplicationInitializer:
    """Класс ApplicationInitializer из диаграммы: создаёт сервисы и UI."""

    def __init__(self) -> None:
        self.is_initialized = False
        self.db: Database | None = None
        self.service: InventoryService | None = None
        self.ui: InventoryUI | None = None

    def initialize(self) -> None:
        self.db = Database()
        self.is_initialized = True

    def create_services(self) -> InventoryService:
        if self.db is None:
            self.initialize()
        self.service = InventoryService(self.db)
        return self.service

    def create_ui(self, employee: Employee | None = None) -> InventoryUI:
        if self.service is None:
            self.create_services()
        window = MainWindow(db=self.db, service=self.service)
        self.ui = InventoryUI(window)
        return self.ui


class RetailInventoryApp:
    """Класс RetailInventoryApp из диаграммы: запуск и остановка программы."""

    def __init__(self) -> None:
        self.is_running = False
        self._initializer: ApplicationInitializer | None = None
        self._ui: InventoryUI | None = None

    def main(self) -> int:
        app = QApplication(sys.argv)
        app.setApplicationName("Склад / Учёт")
        app.setOrganizationName("BGUIR")
        apply_app_style(app)
        return self.start()

    def start(self) -> int:
        self._initializer = ApplicationInitializer()
        self._initializer.initialize()
        self._initializer.create_services()
        self._ui = self._initializer.create_ui()
        if not self._ui.is_authenticated:
            self.stop()
            return 0
        self._ui.show()
        self.is_running = True
        return QApplication.instance().exec()

    def stop(self) -> None:
        self.is_running = False


def main() -> int:
    return RetailInventoryApp().main()


if __name__ == "__main__":
    raise SystemExit(main())
