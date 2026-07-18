import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit, QDialog,
    QTextEdit,
)
from PyQt5.QtCore import Qt, QByteArray, QRectF
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from toast_notification import show_toast, confirm_action
from theme import svg_icon, C, action_button_style, primary_button_style


#  Font UI lintas-platform (lihat DataMurid.py / JadwalKursus.py)
def _ui_font(size=10, bold=False):
    family = "Segoe UI"
    if sys.platform == "darwin":
        family = ".AppleSystemUIFont"
    elif sys.platform.startswith("linux"):
        family = "Ubuntu"
    f = QFont(family, size)
    if bold:
        f.setWeight(QFont.Bold)
    return f


def _make_eye_icon(visible: bool, size=20) -> QIcon:
    """
    Render ikon mata (visible=True) atau mata-dicoret (visible=False)
    menggunakan SVG — warna abu-abu #64748B.
    """
    if visible:
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
                  fill='none' stroke='{C.TEXT_MUTED}' stroke-width='2'
                  stroke-linecap='round' stroke-linejoin='round'>
            <path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'/>
            <circle cx='12' cy='12' r='3'/>
        </svg>""".encode()
    else:
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
                  fill='none' stroke='{C.TEXT_MUTED}' stroke-width='2'
                  stroke-linecap='round' stroke-linejoin='round'>
            <path d='M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8
                     a18.45 18.45 0 0 1 5.06-5.94'/>
            <path d='M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8
                     a18.5 18.5 0 0 1-2.16 3.19'/>
            <line x1='1' y1='1' x2='23' y2='23'/>
        </svg>""".encode()
    renderer = QSvgRenderer(QByteArray(svg))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pix)


#  Gaya badge status — Aktif / Cuti / Nonaktif (samakan dengan Data Guru)
STATUS_STYLE = {
    "Aktif":    (f"{C.SUCCESS_BG_STRONG}", f"{C.SUCCESS_DARK}"),
    "Cuti":     (f"{C.WARNING_BG}", f"{C.WARNING_DARK}"),
    "Nonaktif": (f"{C.SURFACE_HOVER}", f"{C.TEXT_MUTED}"),
}


#  DIALOG: TAMBAH / EDIT ADMIN

class AdminDialog(QDialog):
    """
    Dialog untuk tambah atau edit data admin.
    Field: Nama Admin, Password (toggle show), No HP, Status (radio), Alamat.
    Username di-generate otomatis dari nama admin.
    Tombol: HAPUS (merah), BATAL (abu-abu), SIMPAN (biru solid).
    """

    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self._is_edit = data is not None
        self._current_status = "Aktif"  # default; overridden by prefill if editing
        self._result_action = None   # 'simpan' | 'ubah' | 'hapus'

        self.setWindowTitle("Data Admin")
        self.setFixedWidth(440)
        self.setStyleSheet(f"QDialog {{ background-color: {C.SURFACE_ALT}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{ background-color: {C.ACCENT_BG}; border-bottom: 1px solid {C.ACCENT_BG_STRONG}; }}
        """)
        header.setFixedHeight(64)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        t1 = QLabel("Data Admin")
        t1.setStyleSheet(f"font-size:14px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;")
        t2 = QLabel("Kelola Akses Admin Sistem MVS")
        t2.setStyleSheet(f"font-size:11px;color:{C.TEXT_MUTED};background:transparent;")
        title_col.addWidget(t1)
        title_col.addWidget(t2)

        close_btn = QPushButton()
        close_btn.setIcon(svg_icon("x", C.TEXT_MUTED, 12))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ border:none; color:{C.TEXT_MUTED_STRONG}; font-size:14px; background:transparent; }}
            QPushButton:hover {{ color:{C.TEXT_PRIMARY}; }}
        """)
        close_btn.clicked.connect(self.reject)

        hl.addLayout(title_col, 1)
        hl.addWidget(close_btn)
        root.addWidget(header)

        # ── Form body ─────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background-color: white;")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(24, 20, 24, 20)
        bv.setSpacing(14)

        # Nama Admin
        bv.addWidget(self._field_lbl("Nama Admin"))
        self.nama_input = self._line_edit("Andini Larasati")
        bv.addWidget(self.nama_input)

        # Username (visible, bisa diisi manual)
        bv.addWidget(self._field_lbl("Username Login"))
        self.user_input = self._line_edit("contoh: andini123")
        bv.addWidget(self.user_input)

        # Email (input manual)
        bv.addWidget(self._field_lbl("Email"))
        self.email_input = self._line_edit("contoh: andini@gmail.com")
        bv.addWidget(self.email_input)

        # Password (full width)
        _has_login = bool(data and data.get("user_id")) if data else True
        _pw_lbl_text = "Password" if _has_login else "Password (kosong = tidak ada akun login)"
        bv.addWidget(self._field_lbl(_pw_lbl_text))
        pw_frame = QFrame()
        pw_frame.setStyleSheet(f"""
            QFrame {{
                border: 1.5px solid {C.BORDER};
                border-radius: 8px;
                background: {C.SURFACE_ALT};
            }}
        """)
        pw_lay = QHBoxLayout(pw_frame)
        pw_lay.setContentsMargins(12, 0, 6, 0)
        pw_lay.setSpacing(4)
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("••••••••••")
        self.pw_input.setStyleSheet(f"""
            QLineEdit {{
                border: none; background: transparent;
                font-size: 13px; color: {C.TEXT_PRIMARY};
            }}
        """)
        self.pw_input.setFixedHeight(38)
        self._pw_visible = False
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedSize(32, 32)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setIcon(_make_eye_icon(False, 20))
        self._toggle_btn.setIconSize(self._toggle_btn.size())
        self._toggle_btn.setToolTip("Tampilkan/sembunyikan kata sandi")
        self._toggle_btn.setAccessibleName("Tampilkan atau sembunyikan kata sandi")
        self._toggle_btn.setFocusPolicy(Qt.StrongFocus)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{ border:none; background:transparent; }}
            QPushButton:hover {{ background: {C.SURFACE_HOVER}; border-radius: 6px; }}
        """)
        self._toggle_btn.clicked.connect(self._toggle_pw)
        pw_lay.addWidget(self.pw_input, 1)
        pw_lay.addWidget(self._toggle_btn)
        pw_frame.setFixedHeight(42)
        bv.addWidget(pw_frame)

        # No HP (full width)
        bv.addWidget(self._field_lbl("No HP"))
        self.hp_input = self._line_edit("0812-xxxx-xxxx")
        bv.addWidget(self.hp_input)

        # Status dikelola via toggle di tabel — tidak ditampilkan di form

        # Alamat
        bv.addWidget(self._field_lbl("Alamat"))
        self.alamat_input = QTextEdit()
        self.alamat_input.setPlaceholderText("Alamat lengkap admin...")
        self.alamat_input.setFixedHeight(80)
        self.alamat_input.setStyleSheet(f"""
            QTextEdit {{
                border: 1.5px solid {C.BORDER}; border-radius: 8px;
                padding: 10px 12px; background: {C.SURFACE_ALT};
                font-size: 12px; color: {C.TEXT_PRIMARY};
            }}
            QTextEdit:focus {{ border: 1.5px solid {C.ACCENT}; background: white; }}
        """)
        bv.addWidget(self.alamat_input)

        root.addWidget(body)

        # Prefill if editing
        if data:
            self.nama_input.setText(data.get("nama", ""))
            self.user_input.setText(data.get("username", ""))
            self.email_input.setText(data.get("email", ""))
            self.hp_input.setText(data.get("hp", ""))
            self.alamat_input.setPlainText(data.get("alamat", ""))
            self._current_status = data.get("status", "Aktif")
            # Load password plain dari DB jika admin punya akun login
            from database import DB as _DB
            user_id = data.get("user_id")
            pw_plain = ""
            if user_id:
                pw_plain = _DB.get_password_plain(user_id)
            if not pw_plain:
                # Fallback: cari lewat username
                uname = data.get("username", "").strip()
                if uname:
                    row = _DB.fetch_one(
                        "SELECT password_plain FROM users WHERE username=?", (uname,)
                    )
                    if row:
                        pw_plain = row["password_plain"] or ""
            if pw_plain:
                self.pw_input.setText(pw_plain)

        # ── Footer / buttons ──────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet(f"""
            QFrame {{ background: white; border-top: 1px solid {C.BORDER}; }}
        """)
        footer.setFixedHeight(60)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)
        fl.setSpacing(10)

        kembali_btn = QPushButton(" Kembali")
        kembali_btn.setIcon(svg_icon("arrow-left", C.TEXT_BODY, 13))
        kembali_btn.setFixedHeight(40)
        kembali_btn.setCursor(Qt.PointingHandCursor)
        kembali_btn.setStyleSheet(f"""
            QPushButton {{
                background: white; color: {C.TEXT_BODY};
                border: 1.5px solid {C.BORDER_STRONG}; border-radius: 8px;
                font-weight: bold; font-size: 12px; padding: 0 16px;
            }}
            QPushButton:hover {{ background: {C.SURFACE_ALT}; border-color: {C.TEXT_FAINT}; }}
        """)
        kembali_btn.clicked.connect(self.reject)

        hapus_btn = QPushButton("Hapus")
        hapus_btn.setFixedHeight(40)
        hapus_btn.setCursor(Qt.PointingHandCursor)
        hapus_btn.setStyleSheet(f"""
            QPushButton {{
                background: white; color: {C.DANGER_DARKER};
                border: 1.5px solid {C.DANGER}; border-radius: 8px;
                font-weight: bold; font-size: 12px; padding: 0 16px;
            }}
            QPushButton:hover {{ background: {C.DANGER_BG}; }}
        """)
        hapus_btn.clicked.connect(self._on_hapus)

        simpan_btn = QPushButton("Simpan")
        simpan_btn.setFixedHeight(40)
        simpan_btn.setCursor(Qt.PointingHandCursor)
        simpan_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.ACCENT}; color: white;
                border: none; border-radius: 8px;
                font-weight: bold; font-size: 12px; padding: 0 20px;
            }}
            QPushButton:hover {{ background: {C.ACCENT_DARK}; }}
        """)
        simpan_btn.clicked.connect(self._on_simpan)
        self._btn_simpan = simpan_btn
        fl.addStretch()
        fl.addWidget(hapus_btn)
        fl.addWidget(simpan_btn)
        root.addWidget(footer)

    def _field_lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:12px;font-weight:600;color:{C.TEXT_BODY};")
        return l

    def _line_edit(self, placeholder=""):
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(42)
        inp.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {C.BORDER}; border-radius: 8px;
                padding-left: 12px; background: {C.SURFACE_ALT};
                font-size: 13px; color: {C.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{ border: 1.5px solid {C.ACCENT}; background: white; }}
        """)
        return inp

    def _radio_style(self):
        return f"""
            QRadioButton {{
                font-size: 13px; color: {C.TEXT_PRIMARY};
                spacing: 6px;
            }}
            QRadioButton::indicator {{
                width: 16px; height: 16px;
                border-radius: 8px;
                border: 2px solid {C.BORDER_STRONG};
                background: white;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {C.ACCENT};
                background: {C.ACCENT};
            }}
        """

    def _toggle_pw(self):
        self._pw_visible = not self._pw_visible
        self.pw_input.setEchoMode(
            QLineEdit.Normal if self._pw_visible else QLineEdit.Password
        )
        self._toggle_btn.setIcon(_make_eye_icon(self._pw_visible, 20))

    def _on_hapus(self):
        # Dialog konfirmasi custom (senada dengan toast/dialog lain), default fokus di "Tidak"
        if confirm_action(
            self, "Konfirmasi Hapus",
            f"Hapus admin '{self.nama_input.text().strip()}'?"
        ):
            self._result_action = "hapus"
            self.accept()

    def _on_simpan(self):
        if not self._validate():
            return
        self._btn_simpan.setEnabled(False)
        self._result_action = "simpan"
        self.accept()

    def _validate(self):
        if not self.nama_input.text().strip():
            show_toast(self, "Perhatian", "Nama Admin tidak boleh kosong!", "warning", anchor=self._btn_simpan)
            self.nama_input.setFocus()
            return False
        if not self.user_input.text().strip():
            show_toast(self, "Perhatian", "Username Login tidak boleh kosong!", "warning", anchor=self._btn_simpan)
            self.user_input.setFocus()
            return False
        if not self.email_input.text().strip():
            show_toast(self, "Perhatian", "Email tidak boleh kosong!", "warning", anchor=self._btn_simpan)
            self.email_input.setFocus()
            return False
        # Password wajib diisi saat tambah baru
        if not self._is_edit and not self.pw_input.text().strip():
            show_toast(self, "Perhatian", "Password tidak boleh kosong!", "warning", anchor=self._btn_simpan)
            self.pw_input.setFocus()
            return False
        return True

    def get_data(self):
        status = self._current_status
        return {
            "nama":     self.nama_input.text().strip(),
            "username": self.user_input.text().strip(),
            "email":    self.email_input.text().strip(),
            "password": self.pw_input.text().strip(),
            "hp":       self.hp_input.text().strip(),
            "alamat":   self.alamat_input.toPlainText().strip(),
            "status":   status,
            "action":   self._result_action,
        }


#  WIDGET: DATA ADMIN

class DataAdminWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C.SURFACE_ALT};")
        self._data = []
        # Pastikan DB & tabel sudah ada sebelum query apapun
        from database import init_db
        init_db()
        self._load_from_db()
        self.init_ui()

    def _load_from_db(self):
        from database import DB
        rows = DB.fetch_all("""
            SELECT a.id, a.user_id, a.nama, a.email, a.no_hp, a.status, a.alamat,
                   u.username
            FROM admin a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.id
        """)
        self._data = []
        for i, r in enumerate(rows, 1):
            self._data.append({
                "id":       r["id"],
                "user_id":  r["user_id"],
                "no":       str(i),
                "nama":     r["nama"] or "",
                "email":    r["email"] or "",
                "hp":       r["no_hp"] or "",
                "username": r["username"] or "",
                "status":   r["status"] or "Aktif",   # "Aktif" | "Cuti" | "Nonaktif"
                "alamat":   r["alamat"] or "",
            })

    def init_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(35, 30, 35, 30)
        v.setSpacing(24)

        # ── Heading ───────────────────────────────────────────────────────────
        h = QHBoxLayout()
        title_col = QVBoxLayout(); title_col.setSpacing(2)
        title_col.addWidget(self._lbl("Data Admin",
                                      f"font-size:20px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        title_col.addWidget(self._lbl("Kelola akun admin Melody Violin School",
                                      f"font-size:12px;color:{C.TEXT_MUTED_STRONG};"))
        h.addLayout(title_col)
        h.addStretch()

        btn_add = QPushButton("+ Tambah Admin")
        btn_add.setFixedHeight(38)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(primary_button_style())
        btn_add.clicked.connect(self._tambah)
        h.addWidget(btn_add)
        v.addLayout(h)

        # ── Stat cards ────────────────────────────────────────────────────────
        self._active_filter = "AKTIF"   # "SEMUA" | "AKTIF" | "NON-AKTIF"
        sr = QHBoxLayout(); sr.setSpacing(16)
        self.stat_total    = self._stat_card("Total Admin",     "SEMUA",     f"{C.ACCENT}")
        self.stat_active   = self._stat_card("Admin Aktif",     "AKTIF",     "#10B981")
        self.stat_inactive = self._stat_card("Admin Non-Aktif", "NON-AKTIF", f"{C.DANGER}")
        sr.addWidget(self.stat_total)
        sr.addWidget(self.stat_active)
        sr.addWidget(self.stat_inactive)
        sr.addStretch()
        v.addLayout(sr)

        # ── Table card ────────────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet("QFrame{background-color:white;border-radius:14px;border:none;}")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(22, 20, 22, 20)
        cv.setSpacing(16)

        # Toolbar
        tb = QHBoxLayout()
        tb.addWidget(self._lbl("Daftar Admin",
                               f"font-size:16px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;"))
        tb.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari Nama, Username, atau Email...")
        self.search.addAction(svg_icon("search", C.TEXT_FAINT, 15), QLineEdit.LeadingPosition)
        self.search.setFixedSize(240, 36)
        self.search.setStyleSheet(f"""
            QLineEdit {{
                border:1.5px solid {C.BORDER}; border-radius:8px;
                background:{C.SURFACE_ALT}; padding-left:12px;
                font-size:12px; color:{C.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{ border:1.5px solid {C.ACCENT}; background:white; }}
        """)
        self.search.textChanged.connect(self._filter)
        tb.addWidget(self.search)
        cv.addLayout(tb)

        # Table
        cols = ["No", "Nama", "Username", "Email", "No HP", "Alamat", "Status", "Aksi"]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(65)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(f"""
            QTableWidget {{ border:none; background-color:white; }}
            QHeaderView::section {{
                background-color:{C.SURFACE_ALT}; padding:12px 10px;
                border:none; border-bottom:2px solid {C.SURFACE_HOVER};
                color:{C.TEXT_MUTED_STRONG}; font-weight:bold; font-size:11px;
            }}
            QTableWidget::item {{
                padding:14px 10px; border-bottom:1px solid {C.SURFACE_HOVER};
                color:{C.TEXT_BODY}; font-size:12px;
            }}
            QTableWidget::item:selected {{ background:{C.ACCENT_BG}; color:{C.TEXT_PRIMARY}; }}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Fixed width kolom Status & Aksi agar tidak tertimpa scrollbar vertikal
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 180)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 110)
        cv.addWidget(self.table)

        # Pagination
        pg = QHBoxLayout()
        self.info_lbl = QLabel()
        self.info_lbl.setStyleSheet(f"color:{C.TEXT_MUTED_STRONG};font-size:12px;background:transparent;")
        pg.addWidget(self.info_lbl)
        pg.addStretch()

        self._page_btns_layout = QHBoxLayout()
        self._page_btns_layout.setSpacing(6)
        for txt in ["‹ Prev", "1", "Next ›"]:
            b = QPushButton(txt)
            b.setFixedHeight(32)
            b.setFixedWidth(50 if txt.isdigit() else 70)
            b.setCursor(Qt.PointingHandCursor)
            active = (txt == "1")
            b.setStyleSheet(f"""
                QPushButton {{
                    border-radius:6px; font-size:12px;
                    background-color:{f'{C.ACCENT}' if active else 'white'};
                    color:{'white' if active else f'{C.TEXT_MUTED}'};
                    border:{'none' if active else f'1px solid {C.BORDER}'};
                }}
                QPushButton:hover {{ background-color:{f'{C.ACCENT_DARK}' if active else f'{C.SURFACE_ALT}'}; }}
            """)
            self._page_btns_layout.addWidget(b)
        pg.addLayout(self._page_btns_layout)
        cv.addLayout(pg)

        v.addWidget(card)
        self._set_filter("AKTIF")

    def _refresh_table(self, keyword=""):
        af = self._active_filter
        filtered = [
            d for d in self._data
            if (keyword.lower() in d["nama"].lower()
                or keyword.lower() in d["username"].lower()
                or keyword.lower() in d["email"].lower())
            and (af == "SEMUA"
                 or (af == "AKTIF"     and d["status"] == "Aktif")
                 or (af == "NON-AKTIF" and d["status"] != "Aktif"))
        ]
        self._filtered_data = filtered
        self.table.setRowCount(0)
        for row_data in filtered:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.verticalHeader().setDefaultSectionSize(65)

            # No – bold
            no_item = QTableWidgetItem(row_data["no"])
            self.table.setItem(r, 0, no_item)

            # Nama – bold
            nama_item = QTableWidgetItem(row_data["nama"])
            nama_item.setFont(_ui_font(10, bold=True))
            nama_item.setForeground(QColor(f"{C.TEXT_PRIMARY}"))
            self.table.setItem(r, 1, nama_item)

            # Username
            uname_item = QTableWidgetItem(row_data["username"] or "-")
            uname_item.setForeground(QColor(f"{C.TEXT_MUTED}"))
            self.table.setItem(r, 2, uname_item)

            # Email
            self.table.setItem(r, 3, QTableWidgetItem(row_data["email"]))

            # No HP
            self.table.setItem(r, 4, QTableWidgetItem(row_data["hp"]))

            # Alamat
            alamat_text = row_data["alamat"] or "-"
            alamat_item = QTableWidgetItem(alamat_text)
            alamat_item.setForeground(QColor(f"{C.TEXT_MUTED}"))
            alamat_item.setToolTip(alamat_text)
            self.table.setItem(r, 5, alamat_item)

            # Status — Toggle Switch interaktif (Aktif / Nonaktif)
            status = row_data["status"]
            is_active = (status == "Aktif")

            toggle_w = QWidget()
            tl = QHBoxLayout(toggle_w)
            tl.setContentsMargins(12, 0, 8, 0)
            tl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            toggle_btn = QPushButton()
            toggle_btn.setFixedSize(52, 26)
            toggle_btn.setCursor(Qt.PointingHandCursor)
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(is_active)

            lbl_toggle = QLabel("Aktif" if is_active else "Non-Aktif")

            def _apply_style(btn, lbl, active):
                if active:
                    btn.setText("ON")
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {C.SUCCESS};
                            border-radius: 13px;
                            border: none;
                            color: white;
                            font-size: 8px;
                            font-weight: bold;
                            padding-left: 5px;
                            text-align: left;
                        }}
                    """)
                    lbl.setText("Aktif")
                    lbl.setStyleSheet(f"font-size:11px;font-weight:600;color:{C.SUCCESS_DARK};background:transparent;border:none;")
                else:
                    btn.setText("OFF")
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {C.BORDER_STRONG};
                            border-radius: 13px;
                            border: none;
                            color: white;
                            font-size: 8px;
                            font-weight: bold;
                            padding-right: 5px;
                            text-align: right;
                        }}
                    """)
                    lbl.setText("Non-Aktif")
                    lbl.setStyleSheet(f"font-size:11px;font-weight:600;color:{C.TEXT_MUTED_STRONG};background:transparent;border:none;")

            _apply_style(toggle_btn, lbl_toggle, is_active)

            def _on_toggle(checked, d=row_data, btn=toggle_btn, lbl=lbl_toggle):
                from database import DB
                new_status = "Aktif" if checked else "Nonaktif"
                DB.execute("UPDATE admin SET status=? WHERE id=?", (new_status, d["id"]))
                d["status"] = new_status
                _apply_style(btn, lbl, checked)
                n_active   = sum(1 for x in self._data if x["status"] == "Aktif")
                n_inactive = len(self._data) - n_active
                self._update_stat_labels(len(self._data), n_active, n_inactive)

            toggle_btn.toggled.connect(_on_toggle)
            tl.addWidget(toggle_btn)
            tl.addSpacing(8)
            tl.addWidget(lbl_toggle)
            self.table.setCellWidget(r, 6, toggle_w)

            # Aksi – Edit button
            aksi_w = QWidget()
            al = QHBoxLayout(aksi_w)
            al.setContentsMargins(2, 2, 2, 2)
            al.setAlignment(Qt.AlignCenter)
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedHeight(32)
            edit_btn.setMinimumWidth(64)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(action_button_style())
            edit_btn.clicked.connect(lambda _, d=row_data: self._edit(d))
            al.addWidget(edit_btn)
            self.table.setCellWidget(r, 7, aksi_w)

        total = len(self._data)
        shown = len(filtered)
        # Update stat card values dynamically
        n_active   = sum(1 for d in self._data if d["status"] == "Aktif")
        n_inactive = len(self._data) - n_active
        self._update_stat_labels(len(self._data), n_active, n_inactive)
        self.info_lbl.setText(f"Menampilkan 1-{shown} dari {total} admin")

    def _filter(self, text):
        self._refresh_table(text)

    def _on_row_click(self, row, col):
        # Kolom 6 = toggle status, jangan buka dialog
        if col == 6:
            return
        # Ambil data dari _filtered_data
        if hasattr(self, '_filtered_data') and row < len(self._filtered_data):
            self._edit(self._filtered_data[row])


    def _tambah(self):
        from database import DB
        import hashlib
        dlg = AdminDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            d = dlg.get_data()
            if d["action"] in ("simpan", "ubah"):
                username = d["username"]
                pw_raw   = d.get("password", "").strip()
                email    = d["email"]
                status   = d["status"]

                # Cek username sudah ada
                existing = DB.fetch_one("SELECT id FROM users WHERE username=?", (username,))
                if existing:
                    show_toast(self, "Gagal", f"Username '{username}' sudah dipakai.", "error")
                    return

                # Selalu buat entry users (password sudah divalidasi wajib isi)
                pw_hash = hashlib.sha256(pw_raw.encode()).hexdigest()
                user_id = DB.execute(
                    "INSERT INTO users(username,password,password_plain,display_name,role) "
                    "VALUES(?,?,?,?,'admin')",
                    (username, pw_hash, pw_raw, d["nama"])
                )

                DB.execute(
                    "INSERT INTO admin(user_id,nama,email,no_hp,alamat,status) VALUES(?,?,?,?,?,?)",
                    (user_id, d["nama"], email, d["hp"], d["alamat"], status)
                )
                self._load_from_db()
                self._refresh_table()
                show_toast(self, "Berhasil", "Data Berhasil Disimpan", "success")

    def _edit(self, data):
        from database import DB
        import hashlib
        dlg = AdminDialog(self, data)
        if dlg.exec_() == QDialog.Accepted:
            d = dlg.get_data()
            admin_id = data.get("id")
            if d["action"] == "hapus":
                if admin_id:
                    DB.execute("DELETE FROM admin WHERE id=?", (admin_id,))
                    show_toast(self, "Berhasil", "Data Admin Berhasil Dihapus", "success")
            else:
                status = d["status"]
                pw_raw = d.get("password", "").strip()
                email  = d.get("email", "").strip()
                if admin_id:
                    DB.execute(
                        "UPDATE admin SET nama=?,email=?,no_hp=?,alamat=?,status=? WHERE id=?",
                        (d["nama"], email, d["hp"], d["alamat"], status, admin_id)
                    )
                    if pw_raw:
                        # Coba update password via user_id
                        ok = DB.update_admin_password(admin_id, pw_raw)
                        if not ok:
                            # Admin belum punya akun login — buatkan baru
                            username = d["username"] or (
                                "mvs_" + "_".join(d["nama"].lower().split())
                            )
                            existing = DB.fetch_one(
                                "SELECT id FROM users WHERE username=?", (username,)
                            )
                            if existing:
                                username = username + f"_{admin_id}"
                            pw_hash = hashlib.sha256(pw_raw.encode()).hexdigest()
                            user_id = DB.execute(
                                "INSERT INTO users(username,password,password_plain,"
                                "display_name,role) VALUES(?,?,?,?,'admin')",
                                (username, pw_hash, pw_raw, d["nama"])
                            )
                            DB.execute(
                                "UPDATE admin SET user_id=? WHERE id=?",
                                (user_id, admin_id)
                            )
                show_toast(self, "Berhasil", "Data Berhasil Disimpan", "success")
            self._load_from_db()
            self._refresh_table()

    def _lbl(self, text, style):
        l = QLabel(text)
        l.setStyleSheet(style)
        return l

    def _stat_card(self, title, filter_key, accent):
        """Clickable stat card. filter_key: 'all' | 'active' | 'inactive'"""
        f = QFrame()
        f.setFixedSize(200, 90)
        f.setCursor(Qt.PointingHandCursor)
        f._filter_key = filter_key
        f._accent     = accent
        f._title      = title
        f.setStyleSheet(self._stat_style(False, accent))

        fl = QVBoxLayout(f)
        fl.setContentsMargins(16, 14, 16, 14)
        fl.setSpacing(6)

        t = QLabel(title)
        t.setObjectName("stat_title")
        t.setStyleSheet(f"font-size:12px;color:{C.TEXT_MUTED};background:transparent;border:none;")
        n = QLabel("0")
        n.setObjectName("stat_value")
        n.setStyleSheet(f"font-size:28px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;border:none;")
        fl.addWidget(t)
        fl.addWidget(n)

        # Click handler via mousePressEvent
        def on_click(event, key=filter_key):
            self._set_filter(key)
        f.mousePressEvent = on_click
        return f

    def _stat_style(self, active, accent):
        if active:
            return f"""
                QFrame {{
                    background-color: #F0F7FF;
                    border: 2px solid {C.ACCENT};
                    border-radius: 12px;
                }}
            """
        return f"""
            QFrame {{
                background-color: white;
                border: 1.5px solid {C.BORDER};
                border-radius: 12px;
            }}
        """

    def _set_filter(self, key):
        self._active_filter = key
        cards = [self.stat_total, self.stat_active, self.stat_inactive]
        for card in cards:
            is_active = card._filter_key == key
            card.setStyleSheet(self._stat_style(is_active, card._accent))
            # Update title label color
            t_lbl = card.findChild(QLabel, "stat_title")
            if t_lbl:
                color = card._accent if is_active else f"{C.TEXT_MUTED}"
                t_lbl.setStyleSheet(
                    f"font-size:12px;color:{color};font-weight:{'bold' if is_active else 'normal'};"
                    "background:transparent;border:none;"
                )
        self._refresh_table(self.search.text())

    def _update_stat_labels(self, total, active, inactive):
        vals = {"SEMUA": total, "AKTIF": active, "NON-AKTIF": inactive}
        for card in [self.stat_total, self.stat_active, self.stat_inactive]:
            v_lbl = card.findChild(QLabel, "stat_value")
            if v_lbl:
                v_lbl.setText(str(vals.get(card._filter_key, 0)))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    app.setFont(_ui_font(10))
    w = DataAdminWidget()
    w.setWindowTitle("Data Admin – Melody Violin School")
    w.resize(1150, 750)
    w.show()
    sys.exit(app.exec_())