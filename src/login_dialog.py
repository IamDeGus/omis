"""Диалог входа в систему."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import Database


class LoginDialog(QDialog):
    STYLE = """
    QDialog {
        background-color: #F1F5F9;
    }
    #loginTitle {
        color: #1F2937;
        font-size: 19px;
        font-weight: 800;
        background-color: transparent;
    }
    QLineEdit {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 8px 10px;
        min-height: 32px;
        font-size: 13px;
    }
    QLineEdit:focus { border: 1px solid #2563EB; }
    #loginBtn {
        background-color: #2563EB;
        color: #FFFFFF;
        border: none;
        border-radius: 7px;
        padding: 9px 20px;
        font-weight: 700;
        font-size: 13px;
        min-height: 36px;
    }
    #loginBtn:hover { background-color: #1D4ED8; }
    #errorLabel {
        color: #DC2626;
        font-size: 12px;
        background-color: transparent;
    }
    """

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._employee_data: dict | None = None

        self.setWindowTitle("Вход — Склад / Учёт")
        self.setFixedSize(380, 260)
        self.setStyleSheet(self.STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 26, 34, 24)
        layout.setSpacing(14)

        title = QLabel("Вход в систему")
        title.setObjectName("loginTitle")
        layout.addWidget(title)

        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("Логин")
        layout.addWidget(self.login_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Пароль")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        login_btn = QPushButton("Войти")
        login_btn.setObjectName("loginBtn")
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self._try_login)
        self.login_edit.returnPressed.connect(self._try_login)
        self.password_edit.returnPressed.connect(self._try_login)
        btn_row.addWidget(login_btn)
        layout.addLayout(btn_row)
        layout.addStretch(1)

    @property
    def employee_data(self) -> dict | None:
        return self._employee_data

    def _try_login(self) -> None:
        login = self.login_edit.text().strip()
        password = self.password_edit.text()
        if not login:
            self.error_label.setText("Введите логин")
            return
        if not password:
            self.error_label.setText("Введите пароль")
            return
        employee = self.db.authenticate(login, password)
        if employee is None:
            self.error_label.setText("Неверный логин или пароль")
            self.password_edit.clear()
            self.password_edit.setFocus()
            return
        self._employee_data = {
            "id": employee.id,
            "full_name": employee.full_name,
            "role": employee.role,
            "login": employee.login,
        }
        self.accept()