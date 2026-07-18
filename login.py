import sys
import hashlib

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QByteArray, QSize
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

from database import DB, init_db
from toast_notification import show_toast
from theme import TextScaleController, scale_stylesheet, install_text_scale_shortcuts


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


_INPUT_STYLE = """
    QLineEdit {
        border: 1.5px solid #E2E8F0; border-radius: 8px;
        padding-left: 14px; background: #F8FAFC;
        font-size: 13px; color: #1E293B;
    }
    QLineEdit:focus { border: 2px solid #2563EB; background: white; }
"""


class LoginWindow(QWidget):
    def __init__(self, on_login_success=None):
        super().__init__()
        self.on_login_success = on_login_success
        self.setStyleSheet("background-color: #F0F4F8;")
        init_db()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedSize(400, 360)
        card.setStyleSheet("QFrame { background: white; border-radius: 16px; }")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(45, 40, 45, 35)
        lay.setSpacing(14)

        title = QLabel("Login")
        title.setAlignment(Qt.AlignCenter)
        _title_qss = "font-size: 22px; font-weight: bold; color: #1E293B; margin-bottom: 6px;"
        title.setStyleSheet(_title_qss)
        lay.addWidget(title)

        _label_qss = "font-size: 12px; font-weight: bold; color: #475569;"

        self._scalable_labels = [(title, _title_qss)]

        def field_label(text):
            l = QLabel(text)
            l.setStyleSheet(_label_qss)
            self._scalable_labels.append((l, _label_qss))
            return l

        lay.addWidget(field_label("Username"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setFixedHeight(42)
        self.username_input.setStyleSheet(_INPUT_STYLE)
        lay.addWidget(self.username_input)

        lay.addWidget(field_label("Password"))

        # Wrapper password + toggle
        pw_wrap = QFrame()
        pw_wrap.setFixedHeight(42)
        pw_wrap.setStyleSheet("""
            QFrame {
                border: 1.5px solid #E2E8F0; border-radius: 8px;
                background: #F8FAFC;
            }
            QFrame:focus-within { border: 1.5px solid #1E293B; background: white; }
        """)
        pw_lay = QHBoxLayout(pw_wrap)
        pw_lay.setContentsMargins(14, 0, 8, 0)
        pw_lay.setSpacing(0)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("••••••••")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                border: none; background: transparent;
                font-size: 13px; color: #1E293B;
            }
        """)
        pw_lay.addWidget(self.password_input)

        # Toggle button dengan SVG eye icon
        self._pw_visible = False
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setFocusPolicy(Qt.StrongFocus)
        self._toggle_btn.setToolTip("Tampilkan/sembunyikan kata sandi")
        self._toggle_btn.setAccessibleName("Tampilkan atau sembunyikan kata sandi")
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid transparent; background: transparent;
                font-size: 16px; color: #475569;
                padding: 0; border-radius: 4px;
            }
            QPushButton:hover { color: #1E293B; }
            QPushButton:focus { outline: none; border: 2px solid #2563EB; }
        """)
        self._toggle_btn.clicked.connect(self._toggle_password)
        self._update_eye_icon()
        pw_lay.addWidget(self._toggle_btn)

        lay.addWidget(pw_wrap)

        btn = QPushButton("&Login")   # mnemonic Alt+L
        btn.setFixedHeight(44)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setDefault(True)          # Enter di field mana pun memicu tombol ini
        btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: white;
                border-radius: 8px; font-size: 14px;
                font-weight: bold; margin-top: 4px; border: 2px solid transparent;
            }
            QPushButton:hover { background-color: #334155; }
            QPushButton:pressed { background-color: #0F172A; }
            QPushButton:focus { outline: none; border: 2px solid #93C5FD; }
        """)
        lay.addWidget(btn)

        self.username_input.setFocusPolicy(Qt.StrongFocus)
        self.password_input.setFocusPolicy(Qt.StrongFocus)
        # Urutan Tab eksplisit & logis
        self.setTabOrder(self.username_input, self.password_input)
        self.setTabOrder(self.password_input, self._toggle_btn)
        self.setTabOrder(self._toggle_btn, btn)

        self.username_input.returnPressed.connect(self.do_login)
        self.password_input.returnPressed.connect(self.do_login)
        btn.clicked.connect(self.do_login)
        self._btn_login = btn

        root.addWidget(card)
        self._login_card = card

        # ── UKURAN TEKS: shortcut didaftarkan sekali di MainApp, di sini ambil singleton saja ──
        self._text_scale = TextScaleController.instance()
        self._text_scale.scaleChanged.connect(self._apply_text_scale)

    def _apply_text_scale(self, factor: float):
        for lbl, base_qss in self._scalable_labels:
            lbl.setStyleSheet(scale_stylesheet(base_qss, factor))
        # Kartu login berukuran tetap (fixed) — sedikit diperbesar tingginya
        # agar teks yang lebih besar tidak terpotong.
        self._login_card.setFixedSize(400, int(360 * min(factor, 1.3)))

    _SVG_EYE_SHOW = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
        stroke="#475569" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
    </svg>"""

    _SVG_EYE_HIDE = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
        stroke="#475569" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
        <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>"""

    def _svg_to_icon(self, svg_bytes: bytes) -> QIcon:
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        pixmap   = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)
        painter  = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def _update_eye_icon(self):
        svg = self._SVG_EYE_HIDE if self._pw_visible else self._SVG_EYE_SHOW
        self._toggle_btn.setIcon(self._svg_to_icon(svg))
        self._toggle_btn.setIconSize(QSize(18, 18))
        self._toggle_btn.setText("")

    def _toggle_password(self):
        self._pw_visible = not self._pw_visible
        self.password_input.setEchoMode(
            QLineEdit.Normal if self._pw_visible else QLineEdit.Password
        )
        self._update_eye_icon()

    def do_login(self):
        user = self.username_input.text().strip()
        pwd  = self.password_input.text().strip()

        if not user or not pwd:
            show_toast(self, "Perhatian", "Username dan Password wajib diisi.", "warning", anchor=self._btn_login)
            return

        result = DB.fetch_one(
            "SELECT id, password, display_name, role FROM users WHERE username = ?", (user,)
        )

        if result and result["password"] == hash_password(pwd):
            display_name = result["display_name"] or user
            role         = result["role"] or "admin"

            # Absensi Admin diketik manual lewat tab Absensi Admin
            if self.on_login_success:
                self.on_login_success(display_name, role, user)
        else:
            show_toast(self, "Gagal", "Username atau Password salah.", "error", anchor=self._btn_login)
            self.password_input.clear()
            self.password_input.setFocus()

    def reset_fields(self):
        self.username_input.clear()
        self.password_input.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    w = LoginWindow()
    install_text_scale_shortcuts(w)  # hanya untuk mode standalone/testing
    w.setWindowTitle("Login - Melody Violin School")
    w.resize(900, 600)
    w.show()
    sys.exit(app.exec_())
