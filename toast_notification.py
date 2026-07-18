"""
toast_notification.py
=====================
Komponen notifikasi toast reusable untuk Melody Violin School.

Cara pakai:
    from toast_notification import show_toast

    # Muncul dekat button yang dipencet
    show_toast(self, "Berhasil", "Data Berhasil Disimpan", "success", anchor=btn)

    # Tanpa anchor → pojok kanan bawah window
    show_toast(self, "Gagal", f"Gagal: {str(e)}", "error")
    show_toast(self, "Perhatian", "Field kosong!", "warning")

Semua jenis hilang otomatis setelah 5 detik.
Bisa juga ditutup dengan klik ✕.
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QApplication, QDialog, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PyQt5.QtGui import QFont, QColor

from theme import svg_pixmap, svg_icon

# ── Tema warna ─────────────────────────────────────────────────────────────────

_THEME = {
    "success": {
        "bg":          "#E6FAF5",
        "border":      "#2DC08E",
        "icon_bg":     "#2DC08E",
        "icon_text":   None,
        "icon_name":   "check",
        "title_color": "#1E293B",
        "body_color":  "#475569",
        "close_color": "#5B6B82",   # warna sebelumnya #94A3B8, kontras 2.36:1 (gagal) → sekarang 5.0:1 (PASS AA)
        "close_hover": "#1E293B",
    },
    "error": {
        "bg":          "#FEF2F2",
        "border":      "#EF4444",
        "icon_bg":     "#EF4444",
        "icon_text":   "!",
        "icon_name":   None,
        "title_color": "#EF4444",
        "body_color":  "#475569",
        "close_color": "#EF4444",
        "close_hover": "#B91C1C",
    },
    "warning": {
        "bg":          "#FFF7ED",
        "border":      "#F97316",
        "icon_bg":     "#F97316",
        "icon_text":   "!",
        "icon_name":   None,
        "title_color": "#EA580C",
        "body_color":  "#475569",
        "close_color": "#F97316",
        "close_hover": "#C2410C",
    },
}

_AUTO_CLOSE_MS = 5000   # semua jenis hilang setelah 5 detik
_MARGIN        = 10     # jarak toast dari anchor/tepi layar (px)

# ── Registry toast aktif ─────────────────────────────────────────────────────
# Mencegah toast "dobel"/bertumpuk: toast baru dgn anchor/parent yang sama
# akan menutup toast lama di posisi itu dulu (bukan menumpuk di belakangnya).
_ACTIVE_TOASTS = {}


def _toast_key(parent_widget, anchor):
    target = anchor if anchor is not None else parent_widget
    return id(target) if target is not None else None


# ── Widget Toast ───────────────────────────────────────────────────────────────

class ToastNotification(QWidget):

    def __init__(self, parent_widget, title: str, message: str,
                 kind: str = "success", anchor: QWidget = None, persistent: bool = False):
        # Toast dijadikan "anak" dari parent_widget (mis. dialog yang
        # memanggilnya) — bukan window lepas tanpa induk (parent=None).
        # Kalau tetap parent=None, toast ini terkunci/tidak bisa diklik
        # ketika muncul di atas QDialog modal (mis. konfirmasi "Jadwal
        # Bentrok" di atas dialog Tambah Les Baru): dialog modal memblokir
        # input ke semua window lain yang BUKAN keturunannya. Qt.Tool
        # dipakai (bukan cuma FramelessWindowHint) supaya toast tetap
        # jadi window mengambang terpisah (posisi global, tidak terkurung
        # dalam area parent) meski sekarang punya parent.
        super().__init__(parent_widget, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet("background: transparent;")

        self._kind          = kind
        self._theme         = _THEME.get(kind, _THEME["error"])
        self._parent_widget = parent_widget
        self._anchor        = anchor
        self._persistent    = persistent

        # Tutup toast lama di posisi (anchor/parent) yang sama, kalau masih terbuka,
        # supaya tidak numpuk tak terlihat di belakang toast yang baru.
        self._key = _toast_key(parent_widget, anchor)
        if self._key is not None:
            old = _ACTIVE_TOASTS.get(self._key)
            if old is not None and old is not self:
                try:
                    old.close()
                except RuntimeError:
                    pass
            _ACTIVE_TOASTS[self._key] = self

        self._build_ui(title, message)
        self._position()
        if not self._persistent:
            QTimer.singleShot(_AUTO_CLOSE_MS, self._fade_out)

    def closeEvent(self, event):
        if self._key is not None and _ACTIVE_TOASTS.get(self._key) is self:
            del _ACTIVE_TOASTS[self._key]
        super().closeEvent(event)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, title: str, message: str):
        t = self._theme

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("ToastCard")
        card.setFixedWidth(320)
        card.setStyleSheet(f"""
            QFrame#ToastCard {{
                background-color: {t['bg']};
                border: 1.5px solid {t['border']};
                border-radius: 12px;
            }}
        """)

        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        # Ikon
        icon = QLabel()
        icon.setObjectName("ToastIcon")
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignCenter)
        if t.get("icon_name"):
            icon.setPixmap(svg_pixmap(t["icon_name"], "white", 16))
        else:
            icon.setText(t["icon_text"])
            icon.setFont(QFont("Segoe UI", 13, QFont.Bold))
        icon.setStyleSheet(f"""
            QLabel#ToastIcon {{
                background-color: {t['icon_bg']};
                color: white;
                border-radius: 16px;
                border: none;
            }}
        """)
        lay.addWidget(icon, 0, Qt.AlignTop)

        # Teks
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("ToastTitle")
        lbl_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        lbl_title.setStyleSheet(f"""
            QLabel#ToastTitle {{ color:{t['title_color']}; background:transparent; border:none; }}
        """)

        lbl_msg = QLabel(message)
        lbl_msg.setObjectName("ToastMsg")
        lbl_msg.setWordWrap(True)
        lbl_msg.setFont(QFont("Segoe UI", 9))
        lbl_msg.setStyleSheet(f"""
            QLabel#ToastMsg {{ color:{t['body_color']}; background:transparent; border:none; }}
        """)

        col.addWidget(lbl_title)
        col.addWidget(lbl_msg)
        lay.addLayout(col, 1)

        # Tombol tutup
        btn_close = QPushButton()
        btn_close.setObjectName("ToastClose")
        btn_close.setIcon(svg_icon("x", t['close_color'], 11))
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton#ToastClose {{ border:none; background:transparent; }}
            QPushButton#ToastClose:focus {{ outline: none; border: 1.5px solid #2563EB; border-radius: 4px; }}
        """)
        btn_close.setAccessibleName("Tutup notifikasi")
        btn_close.setFocusPolicy(Qt.StrongFocus)
        btn_close.clicked.connect(self.close)
        lay.addWidget(btn_close, 0, Qt.AlignTop)

        root.addWidget(card)
        self.adjustSize()

    # ── Posisi ────────────────────────────────────────────────────────────────

    def _position(self):
        self.adjustSize()
        w, h = self.width(), self.height()

        if self._anchor and self._anchor.isVisible():
            # Muncul tepat di atas button yang dipencet
            g   = self._anchor.mapToGlobal(QPoint(0, 0))
            ax, ay, aw = g.x(), g.y(), self._anchor.width()

            # Tengah-kan horizontal terhadap anchor, dorong kiri jika keluar layar
            x = ax + (aw - w) // 2
            y = ay - h - _MARGIN

            screen = QApplication.primaryScreen().geometry()
            x = max(_MARGIN, min(x, screen.width()  - w - _MARGIN))
            y = max(_MARGIN, min(y, screen.height() - h - _MARGIN))

            # Jika tidak muat di atas, tampil di bawah anchor
            if y < _MARGIN:
                y = ay + self._anchor.height() + _MARGIN
        else:
            # Fallback: pojok kanan bawah parent window
            pw = self._parent_widget
            if pw:
                g = pw.mapToGlobal(QPoint(0, 0))
                x = g.x() + pw.width()  - w - 24
                y = g.y() + pw.height() - h - 24
            else:
                screen = QApplication.primaryScreen().geometry()
                x = screen.width()  - w - 24
                y = screen.height() - h - 24

        # Slide-in dari bawah
        self.setGeometry(x, y + 30, w, h)
        self.show()

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setStartValue(QRect(x, y + 30, w, h))
        self._anim.setEndValue(QRect(x, y,        w, h))
        self._anim.start()

    # ── Fade out ──────────────────────────────────────────────────────────────

    # Esc menutup toast tanpa mouse
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _fade_out(self):
        if not self.isVisible():
            return
        geo = self.geometry()
        self._out = QPropertyAnimation(self, b"geometry")
        self._out.setDuration(200)
        self._out.setEasingCurve(QEasingCurve.InCubic)
        self._out.setStartValue(geo)
        self._out.setEndValue(QRect(geo.x(), geo.y() + 30, geo.width(), geo.height()))
        self._out.finished.connect(self.close)
        self._out.start()


# ── Fungsi publik ──────────────────────────────────────────────────────────────

def show_toast(parent, title: str, message: str,
               kind: str = "success", anchor: QWidget = None,
               persistent: bool = False) -> ToastNotification:
    """
    Tampilkan toast notification.

    Parameters
    ----------
    parent : QWidget | None   — window induk
    title  : str              — judul tebal
    message: str              — isi pesan
    kind   : str              — "success" | "error" | "warning"
    anchor : QWidget | None   — button yang dipencet; toast muncul di atasnya
    persistent : bool         — True = tidak hilang otomatis, harus ditutup manual (klik ✕ / Esc).
                                 Dipakai untuk notifikasi penting seperti "Jadwal Bentrok"
                                 yang isinya perlu benar-benar dibaca user.
    """
    return ToastNotification(parent, title, message, kind, anchor, persistent)


# ── Dialog Konfirmasi (pengganti QMessageBox.question, tampilan oren senada toast warning) ──

_CONFIRM_THEME = _THEME["warning"]


class ConfirmDialog(QDialog):

    def __init__(self, parent, title: str, message: str,
                 yes_text: str = "Ya", no_text: str = "Tidak"):
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self._result = False

        t = _CONFIRM_THEME

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        card = QFrame()
        card.setObjectName("ConfirmCard")
        card.setFixedWidth(360)
        card.setStyleSheet(f"""
            QFrame#ConfirmCard {{
                background-color: white;
                border: 1.5px solid {t['border']};
                border-radius: 14px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 60))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        body = QVBoxLayout(card)
        body.setContentsMargins(22, 20, 22, 18)
        body.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(12)

        icon = QLabel("?")
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFont(QFont("Segoe UI", 15, QFont.Bold))
        icon.setStyleSheet(f"""
            background-color: {t['icon_bg']};
            color: white;
            border-radius: 19px;
            border: none;
        """)
        top.addWidget(icon, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_title.setStyleSheet(f"color:{t['title_color']}; background:transparent; border:none;")
        lbl_title.setWordWrap(True)

        lbl_msg = QLabel(message)
        lbl_msg.setFont(QFont("Segoe UI", 10))
        lbl_msg.setStyleSheet(f"color:{t['body_color']}; background:transparent; border:none;")
        lbl_msg.setWordWrap(True)

        col.addWidget(lbl_title)
        col.addWidget(lbl_msg)
        top.addLayout(col, 1)

        body.addLayout(top)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        btn_no = QPushButton(no_text)
        btn_no.setCursor(Qt.PointingHandCursor)
        btn_no.setFixedHeight(34)
        btn_no.setMinimumWidth(84)
        btn_no.setFont(QFont("Segoe UI", 9, QFont.Bold))
        btn_no.setAccessibleName(f"Tombol {no_text}")
        btn_no.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {t['title_color']};
                border: 1.5px solid {t['border']};
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{ background-color: {t['bg']}; }}
            QPushButton:focus {{ outline: none; border: 2px solid #2563EB; }}
        """)
        btn_no.clicked.connect(self._on_no)

        btn_yes = QPushButton(yes_text)
        btn_yes.setCursor(Qt.PointingHandCursor)
        btn_yes.setFixedHeight(34)
        btn_yes.setMinimumWidth(84)
        btn_yes.setFont(QFont("Segoe UI", 9, QFont.Bold))
        btn_yes.setAccessibleName(f"Tombol {yes_text}")
        btn_yes.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['icon_bg']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{ background-color: {t['close_hover']}; }}
            QPushButton:focus {{ outline: none; border: 2px solid #1E3A8A; }}
        """)
        btn_yes.clicked.connect(self._on_yes)

        # Default & fokus awal di "Tidak" (opsi aman) agar Enter tidak sengaja konfirmasi
        btn_yes.setAutoDefault(False)
        btn_no.setAutoDefault(True)
        btn_no.setDefault(True)

        btn_row.addWidget(btn_no)
        btn_row.addWidget(btn_yes)
        body.addLayout(btn_row)

        btn_no.setFocus()  # fokus awal di opsi aman ("Tidak")

    def _on_yes(self):
        self._result = True
        self.accept()

    def _on_no(self):
        self._result = False
        self.reject()


def confirm_action(parent, title: str, message: str,
                    yes_text: str = "Ya", no_text: str = "Tidak") -> bool:
    """
    Tampilkan dialog konfirmasi bertema oren (pengganti QMessageBox.question).

    Contoh:
        if confirm_action(self, "Konfirmasi", "Tandai sesi ini sebagai Terlaksana?"):
            ...lakukan aksi...

    Return True jika user klik "Ya", False jika "Tidak"/ditutup.
    """
    dlg = ConfirmDialog(parent, title, message, yes_text, no_text)
    dlg.exec_()
    return dlg._result
