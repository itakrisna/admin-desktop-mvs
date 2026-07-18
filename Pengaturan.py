import sys
from database import DB, init_db
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QDialog,
    QSizePolicy, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QByteArray, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from toast_notification import show_toast, confirm_action
from theme import C


def _no_double_submit(fn):
    """Menonaktifkan tombol yang memicu handler ini selama proses berjalan,
    agar klik ganda/cepat tidak memicu aksi (mis. simpan/insert) dua kali.
    Tombol otomatis aktif lagi setelah handler selesai, baik berhasil maupun gagal."""
    def wrapper(self, *args, **kwargs):
        # NB: PyQt meneruskan argumen 'checked' (bool) dari sinyal clicked ke
        # sini. Argumen itu SENGAJA tidak diteruskan ke fn karena semua
        # handler yang dibungkus decorator ini hanya menerima (self).
        btn = self.sender()
        if btn is not None:
            btn.setEnabled(False)
        try:
            return fn(self)
        finally:
            if btn is not None:
                btn.setEnabled(True)
    return wrapper


#  SVG ICONS (stroke based, dipakai untuk header kartu & aksi tabel)
ICON_USER = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <path d='M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2'/>
  <circle cx='12' cy='7' r='4'/>
</svg>"""

ICON_CAP = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <path d='M22 10 12 5 2 10l10 5 10-5Z'/>
  <path d='M6 12v5c0 1.66 2.69 3 6 3s6-1.34 6-3v-5'/>
</svg>"""

ICON_CARD = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <rect x='2' y='5' width='20' height='14' rx='2'/>
  <line x1='2' y1='10' x2='22' y2='10'/>
</svg>"""

ICON_CLOCK = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <circle cx='12' cy='12' r='10'/>
  <polyline points='12 6 12 12 16 14'/>
</svg>"""

ICON_PENCIL = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <path d='M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z'/>
</svg>"""

ICON_TRASH = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <polyline points='3 6 5 6 21 6'/>
  <path d='M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2'/>
</svg>"""

ICON_PLUS = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'>
  <line x1='12' y1='5' x2='12' y2='19'/>
  <line x1='5' y1='12' x2='19' y2='12'/>
</svg>"""

EYE_OFF = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <path d='M17.94 17.94A10.07 10.07 0 0 1 12 20
    C7 20 2.73 16.39 1 12a10.1 10.1 0 0 1 2.06-3.94'/>
  <path d='M9.9 4.24A9.12 9.12 0 0 1 12 4c5 0 9.27 3.61 11 8
    a10.1 10.1 0 0 1-1.28 2.42'/>
  <line x1='1' y1='1' x2='23' y2='23'/>
</svg>"""

EYE_ON = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'
    fill='none' stroke='%s' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <path d='M1 12S5 4 12 4s11 8 11 8-4 8-11 8S1 12 1 12z'/>
  <circle cx='12' cy='12' r='3'/>
</svg>"""


class PengaturanWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C.SURFACE_ALT};")
        # Pastikan DB & tabel sudah ada sebelum query apapun
        init_db()
        self.init_ui()
        self._load_owner_from_db()
        self._load_gaji_from_db()
        self._load_durasi_from_db()

    def init_ui(self):
        # Bungkus dengan scroll agar tidak terpotong di layar kecil
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        # Horizontal scroll dimatikan — lebar konten harus menyesuaikan jendela,
        # bukan sebaliknya (jendela sudah dikunci minimum agar tidak kesempitan).
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Scrollbar vertikal disamakan gayanya dgn Data Guru/Data Murid/Absensi
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{C.SURFACE_ALT}; }}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)

        container = QWidget()
        container.setStyleSheet(f"background:{C.SURFACE_ALT};")
        v = QVBoxLayout(container)
        v.setContentsMargins(35, 30, 35, 30)
        v.setSpacing(20)

        # ── Heading ───────────────────────────────────────────────────
        tb = QVBoxLayout(); tb.setSpacing(2)
        tb.addWidget(self._lbl("Pengaturan Sistem",
                               f"font-size:20px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        tb.addWidget(self._lbl("Kelola konfigurasi akun, daftar kursus, durasi sesi, dan skema gaji.",
                               f"font-size:12px;color:{C.TEXT_FAINT};"))
        v.addLayout(tb)

        # ── Owner Card ────────────────────────────────────────────────
        owner_card = self._card()
        owner_lay = QVBoxLayout(owner_card)
        owner_lay.setContentsMargins(24, 22, 24, 24)
        owner_lay.setSpacing(14)

        owner_lay.addLayout(self._card_header(
            ICON_USER, "Informasi Akun Owner",
            "Kelola informasi akun owner MVS."))

        owner_lay.addWidget(self._field_lbl("Username"))
        self.owner_username = self._text_input("Masukkan username owner")
        self.owner_username.setText("owner")
        owner_lay.addWidget(self.owner_username)

        owner_lay.addWidget(self._field_lbl("Nama"))
        self.owner_nama = self._text_input("Masukkan nama owner")
        self.owner_nama.setText("Owner MVS")
        owner_lay.addWidget(self.owner_nama)

        owner_lay.addWidget(self._field_lbl("Password"))
        pw_wrap, self.owner_password = self._password_input_toggle()
        owner_lay.addWidget(pw_wrap)
        owner_lay.addWidget(self._lbl("Kosongkan jika tidak ingin mengubah password.",
                                      f"font-size:10px;color:{C.TEXT_FAINT};background:transparent;"))
        owner_lay.addStretch()

        simpan_owner_btn = self._primary_btn("Simpan Perubahan", icon_svg=None)
        simpan_owner_btn.clicked.connect(self._simpan_owner)
        owner_lay.addWidget(simpan_owner_btn)

        # ── Kursus Card ───────────────────────────────────────────────
        kursus_card = self._card()
        kursus_lay = QVBoxLayout(kursus_card)
        kursus_lay.setContentsMargins(24, 22, 24, 24)
        kursus_lay.setSpacing(16)
        kursus_lay.addLayout(self._build_kursus_section())

        # ── Owner + Kursus sejajar ────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        top_row.addWidget(owner_card, 1)
        top_row.addWidget(kursus_card, 1)
        v.addLayout(top_row)

        # ── Gaji Card ─────────────────────────────────────────────────
        gaji_card = self._card()
        gaji_lay = QVBoxLayout(gaji_card)
        gaji_lay.setContentsMargins(24, 22, 24, 24)
        gaji_lay.setSpacing(16)
        gaji_lay.addLayout(self._card_header(
            ICON_CARD, "Pengaturan Gaji Admin & Guru",
            "Atur besaran gaji untuk admin dan guru."))
        gaji_lay.addLayout(self._build_gaji_grid())
        gaji_lay.addStretch()

        save_gaji_btn = self._primary_btn("Simpan Pengaturan Gaji")
        save_gaji_btn.clicked.connect(self._save_gaji)
        gaji_lay.addWidget(save_gaji_btn)

        # ── Durasi Sesi Card ──────────────────────────────────────────
        durasi_card = self._card()
        durasi_lay = QVBoxLayout(durasi_card)
        durasi_lay.setContentsMargins(24, 22, 24, 24)
        durasi_lay.setSpacing(16)
        durasi_lay.addLayout(self._card_header(
            ICON_CLOCK, "Durasi Sesi",
            "Atur durasi sesi pembelajaran."))
        durasi_lay.addLayout(self._build_durasi_grid())
        durasi_lay.addStretch()

        save_durasi_btn = self._primary_btn("Simpan Pengaturan Durasi")
        save_durasi_btn.clicked.connect(self._save_durasi)
        durasi_lay.addWidget(save_durasi_btn)

        # ── Gaji + Durasi sejajar (sama seperti Owner + Kursus) ─────────
        gaji_row = QHBoxLayout()
        gaji_row.setSpacing(16)
        gaji_row.addWidget(gaji_card, 2)
        gaji_row.addWidget(durasi_card, 1)
        v.addLayout(gaji_row)

        v.addStretch()

        scroll.setWidget(container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    #  CARD / HEADER HELPERS
    #  PENTING: pakai ID selector "QFrame#nama{...}", bukan "QFrame{...}"
    #  (QLabel turunan QFrame, jadi style umum akan "bocor" ke label anak)
    _card_seq = 0

    def _card(self):
        PengaturanWidget._card_seq += 1
        name = f"card{PengaturanWidget._card_seq}"
        card = QFrame()
        card.setObjectName(name)
        card.setStyleSheet(f"""
            QFrame#{name}{{background:#FFFFFF;border-radius:14px;border:1px solid {C.BORDER};}}
        """)
        return card

    def _icon_box(self, svg_template, size=40, bg=f"{C.ACCENT_BG}", color=f"{C.ACCENT}"):
        box = QLabel()
        box.setFixedSize(size, size)
        box.setStyleSheet(
            f"background:{bg};border-radius:{size//3.3:.0f}px;border:none;")
        box.setAlignment(Qt.AlignCenter)
        icon_size = int(size * 0.55)
        box.setPixmap(self._svg_pixmap(svg_template, color, icon_size))
        return box

    def _svg_pixmap(self, svg_template, color, size=20):
        svg_bytes = svg_template % color.encode()
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        return pix

    def _svg_icon(self, svg_template, color, size=20):
        return QIcon(self._svg_pixmap(svg_template, color, size))

    def _card_header(self, svg_template, title, subtitle):
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._icon_box(svg_template))

        tb = QVBoxLayout(); tb.setSpacing(1)
        tb.addWidget(self._lbl(title,
                                f"font-size:14px;font-weight:bold;color:{C.TEXT_PRIMARY};"
                                "background:transparent;"))
        tb.addWidget(self._lbl(subtitle,
                                f"font-size:11px;color:{C.TEXT_FAINT};background:transparent;"))
        row.addLayout(tb, 1)
        return row

    def _primary_btn(self, text, icon_svg=None):
        btn = QPushButton(text)
        btn.setFixedHeight(42)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton{{background:{C.ACCENT};color:white;border-radius:8px;
                font-weight:bold;font-size:13px;border:none;padding-left:6px;padding-right:6px;}}
            QPushButton:hover{{background:{C.ACCENT_DARK};}}
        """)
        if icon_svg:
            btn.setIcon(self._svg_icon(icon_svg, "#FFFFFF", 16))
            btn.setIconSize(QSize(16, 16))
        return btn

    #  ACTIONS – OWNER
    def _load_owner_from_db(self):
        """Isi field Username/Nama/Password Owner dari database saat widget pertama dibuka."""
        try:
            info = DB.get_owner_info()
            if info.get("username"):
                self.owner_username.setText(info["username"])
            if info.get("nama"):
                self.owner_nama.setText(info["nama"])
        except Exception:
            pass  # DB mungkin belum di-init; biarkan nilai default
        try:
            pw_plain = DB.get_owner_password_plain()
            if pw_plain:
                self.owner_password.setText(pw_plain)
        except Exception:
            pass

    def _password_input_toggle(self):
        """Field password dengan tombol show/hide (ikon mata) di dalam kartu utama."""
        PengaturanWidget._card_seq += 1
        wname = f"wrap{PengaturanWidget._card_seq}"
        wrapper = QFrame()
        wrapper.setObjectName(wname)
        wrapper.setFixedHeight(40)
        wrapper.setStyleSheet(f"""
            QFrame#{wname}{{background:white;border:1.5px solid {C.BORDER};border-radius:8px;}}
        """)
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 6, 0)
        row.setSpacing(0)

        inp = QLineEdit()
        inp.setEchoMode(QLineEdit.Password)
        inp.setPlaceholderText("••••••••")
        inp.setStyleSheet(f"""
            QLineEdit{{border:none;border-radius:8px;padding-left:12px;
                font-size:12px;color:{C.TEXT_PRIMARY};background:transparent;}}
        """)
        row.addWidget(inp, 1)

        toggle_btn = QPushButton()
        toggle_btn.setFixedSize(30, 30)
        toggle_btn.setCursor(Qt.PointingHandCursor)
        toggle_btn.setCheckable(True)
        toggle_btn.setIcon(self._svg_icon(EYE_OFF, f"{C.TEXT_FAINT}", 18))
        toggle_btn.setIconSize(QSize(18, 18))
        toggle_btn.setToolTip("Tampilkan/sembunyikan kata sandi")
        toggle_btn.setAccessibleName("Tampilkan atau sembunyikan kata sandi")
        toggle_btn.setFocusPolicy(Qt.StrongFocus)
        toggle_btn.setStyleSheet("QPushButton{border:none;background:transparent;}")

        def _toggle(checked):
            if checked:
                inp.setEchoMode(QLineEdit.Normal)
                toggle_btn.setIcon(self._svg_icon(EYE_ON, f"{C.TEXT_FAINT}", 18))
            else:
                inp.setEchoMode(QLineEdit.Password)
                toggle_btn.setIcon(self._svg_icon(EYE_OFF, f"{C.TEXT_FAINT}", 18))
        toggle_btn.toggled.connect(_toggle)
        row.addWidget(toggle_btn)

        return wrapper, inp

    @_no_double_submit
    def _simpan_owner(self):
        """Simpan perubahan Username/Nama/Password Owner langsung dari kartu utama."""
        username = self.owner_username.text().strip()
        nama = self.owner_nama.text().strip()
        pw = self.owner_password.text().strip()

        if not username:
            show_toast(self, "Perhatian", "Username tidak boleh kosong!", "warning")
            return
        if not nama:
            show_toast(self, "Perhatian", "Nama tidak boleh kosong!", "warning")
            return

        try:
            ok = DB.update_owner(nama, username, pw if pw else None)
        except ValueError as e:
            show_toast(self, "Perhatian", str(e), "warning")
            return
        except Exception as e:
            show_toast(self, "Error", f"Gagal menyimpan ke database:\n{e}", "error")
            return

        if not ok:
            show_toast(self, "Error", "Data owner tidak ditemukan di database!", "error")
            return

        show_toast(
            self, "Berhasil",
            f"Data Owner berhasil disimpan!\nUsername: {username}\nNama: {nama}",
            "success"
        )

    #  KURSUS SECTION
    def _build_kursus_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)

        # ── Header + input tambah kursus sejajar ───────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_row.addLayout(self._card_header(
            ICON_CAP, "Daftar Kursus", "Kelola daftar kursus yang tersedia."))

        self.kursus_input = QLineEdit()
        self.kursus_input.setPlaceholderText("Masukkan nama kursus")
        self.kursus_input.setFixedHeight(38)
        self.kursus_input.setFixedWidth(190)
        self.kursus_input.setStyleSheet(f"""
            QLineEdit{{
                border:1.5px solid {C.BORDER};border-radius:8px;
                padding-left:12px;font-size:12px;color:{C.TEXT_PRIMARY};background:white;
            }}
            QLineEdit:focus{{border:1.5px solid {C.ACCENT};background:white;}}
        """)
        header_row.addWidget(self.kursus_input)

        tambah_btn = self._primary_btn("Tambah", icon_svg=ICON_PLUS)
        tambah_btn.setFixedWidth(110)
        tambah_btn.clicked.connect(self._tambah_kursus)
        header_row.addWidget(tambah_btn)

        layout.addLayout(header_row)

        # ── Tabel Kursus ──────────────────────────────────────────────
        self.kursus_table = QTableWidget()
        self.kursus_table.setColumnCount(2)
        self.kursus_table.setHorizontalHeaderLabels(["Nama Kursus", "Aksi"])
        self.kursus_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.kursus_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.kursus_table.setColumnWidth(1, 90)
        self.kursus_table.verticalHeader().setVisible(False)
        self.kursus_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.kursus_table.setSelectionMode(QTableWidget.NoSelection)
        self.kursus_table.setShowGrid(False)
        self.kursus_table.setAlternatingRowColors(True)
        # Tinggi minimum 240px, boleh melar mengisi sisa ruang kartu
        self.kursus_table.setMinimumHeight(240)
        self.kursus_table.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.kursus_table.setStyleSheet(f"""
            QTableWidget{{
                border:1px solid {C.BORDER};border-radius:8px;
                background:white;font-size:12px;color:{C.TEXT_PRIMARY};
                outline:none;
            }}
            QTableWidget::item{{padding:8px 12px;border:none;}}
            QTableWidget::item:alternate{{background:{C.SURFACE_ALT};}}
            QHeaderView::section{{
                background:{C.SURFACE_ALT};color:{C.TEXT_MUTED_STRONG};font-size:11px;
                font-weight:600;padding:8px 12px;
                border:none;border-bottom:1px solid {C.BORDER};
            }}
        """)
        layout.addWidget(self.kursus_table)

        self._load_kursus_table()
        return layout

    def _fetch_all_kursus(self):
        try:
            return DB.fetch_all("SELECT id, nama FROM kursus ORDER BY nama")
        except Exception:
            return []

    def _load_kursus_table(self):
        rows = self._fetch_all_kursus()

        self.kursus_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.kursus_table.setRowHeight(i, 42)
            nama_item = QTableWidgetItem(r["nama"])
            nama_item.setData(Qt.UserRole, r["id"])
            self.kursus_table.setItem(i, 0, nama_item)

            kursus_id = r["id"]
            kursus_nama = r["nama"]

            edit_btn = QPushButton()
            edit_btn.setFixedSize(28, 28)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setIcon(self._svg_icon(ICON_PENCIL, f"{C.TEXT_MUTED}", 15))
            edit_btn.setIconSize(QSize(15, 15))
            edit_btn.setStyleSheet(f"""
                QPushButton{{border:none;background:transparent;border-radius:6px;}}
                QPushButton:hover{{background:{C.SURFACE_HOVER};}}
            """)
            edit_btn.clicked.connect(
                lambda _, kid=kursus_id, kn=kursus_nama: self._edit_kursus(kid, kn)
            )

            hapus_btn = QPushButton()
            hapus_btn.setFixedSize(28, 28)
            hapus_btn.setCursor(Qt.PointingHandCursor)
            hapus_btn.setIcon(self._svg_icon(ICON_TRASH, f"{C.DANGER}", 15))
            hapus_btn.setIconSize(QSize(15, 15))
            hapus_btn.setStyleSheet(f"""
                QPushButton{{border:none;background:transparent;border-radius:6px;}}
                QPushButton:hover{{background:{C.DANGER_BG};}}
            """)
            hapus_btn.clicked.connect(
                lambda _, kid=kursus_id, kn=kursus_nama: self._hapus_kursus(kid, kn)
            )

            cell_widget = QWidget()
            cell_widget.setStyleSheet("background:transparent;")
            cell_lay = QHBoxLayout(cell_widget)
            cell_lay.setContentsMargins(8, 0, 8, 0)
            cell_lay.setSpacing(4)
            cell_lay.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            cell_lay.addWidget(edit_btn)
            cell_lay.addWidget(hapus_btn)
            self.kursus_table.setCellWidget(i, 1, cell_widget)

    @_no_double_submit
    def _tambah_kursus(self):
        nama = self.kursus_input.text().strip()
        if not nama:
            show_toast(self, "Perhatian", "Nama kursus tidak boleh kosong!", "warning")
            return
        try:
            existing = DB.fetch_one("SELECT id FROM kursus WHERE LOWER(nama)=LOWER(?)", (nama,))
            if existing:
                show_toast(self, "Perhatian", f"Kursus '{nama}' sudah ada!", "warning")
                return
            DB.execute("INSERT INTO kursus (nama) VALUES (?)", (nama,))
            self.kursus_input.clear()
            self._load_kursus_table()
            show_toast(self, "Berhasil", f"Kursus '{nama}' berhasil ditambahkan!", "success")
        except Exception as e:
            show_toast(self, "Error", f"Gagal menyimpan kursus:\n{e}", "error")

    def _edit_kursus(self, kursus_id, kursus_nama):
        """Popup kecil untuk mengubah nama kursus."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Kursus")
        dlg.setFixedWidth(360)
        dlg.setStyleSheet("background:white;border-radius:14px;")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(14)

        lay.addWidget(self._field_lbl("Nama Kursus"))
        input_nama = QLineEdit(kursus_nama)
        input_nama.setFixedHeight(40)
        input_nama.setStyleSheet(f"""
            QLineEdit{{border:1.5px solid {C.BORDER};border-radius:8px;
                padding-left:12px;font-size:13px;color:{C.TEXT_PRIMARY};background:white;}}
            QLineEdit:focus{{border:1.5px solid {C.ACCENT};}}
        """)
        lay.addWidget(input_nama)

        simpan_btn = self._primary_btn("Simpan")

        def _simpan():
            nama_baru = input_nama.text().strip()
            if not nama_baru:
                show_toast(dlg, "Perhatian", "Nama kursus tidak boleh kosong!", "warning")
                return
            try:
                dup = DB.fetch_one(
                    "SELECT id FROM kursus WHERE LOWER(nama)=LOWER(?) AND id!=?",
                    (nama_baru, kursus_id))
                if dup:
                    show_toast(dlg, "Perhatian", f"Kursus '{nama_baru}' sudah ada!", "warning")
                    return
                DB.execute("UPDATE kursus SET nama=? WHERE id=?", (nama_baru, kursus_id))
            except Exception as e:
                show_toast(dlg, "Error", f"Gagal menyimpan kursus:\n{e}", "error")
                return
            self._load_kursus_table()
            show_toast(dlg, "Berhasil", "Kursus berhasil diperbarui!", "success")
            dlg.accept()

        simpan_btn.clicked.connect(_simpan)
        lay.addWidget(simpan_btn)

        dlg.exec_()

    def _hapus_kursus(self, kursus_id, kursus_nama):
        # Cek apakah kursus masih dipakai di tabel lain
        try:
            pemakaian = []
            pk = DB.fetch_one(
                "SELECT COUNT(*) as cnt FROM pendaftaran_kursus WHERE kursus_id=?", (kursus_id,))
            if pk and pk["cnt"] > 0:
                pemakaian.append(f"- {pk['cnt']} data pendaftaran murid")
            psm = DB.fetch_one(
                "SELECT COUNT(*) as cnt FROM pembayaran_sesi_murid WHERE kursus_id=?", (kursus_id,))
            if psm and psm["cnt"] > 0:
                pemakaian.append(f"- {psm['cnt']} data pembayaran sesi")
        except Exception:
            pemakaian = []

        if pemakaian:
            detail = "\n".join(pemakaian)
            show_toast(
                self, "Tidak Dapat Dihapus",
                f"Kursus '{kursus_nama}' tidak dapat dihapus karena masih digunakan oleh:\n"
                f"{detail}. Hapus atau pindahkan data tersebut terlebih dahulu.",
                "warning"
            )
            return

        if confirm_action(
            self, "Konfirmasi Hapus",
            f"Apakah Anda yakin ingin menghapus kursus '{kursus_nama}'?"
        ):
            try:
                DB.execute("DELETE FROM kursus WHERE id=?", (kursus_id,))
                self._load_kursus_table()
                show_toast(self, "Berhasil", f"Kursus '{kursus_nama}' berhasil dihapus!", "success")
            except Exception as e:
                show_toast(self, "Error", f"Gagal menghapus kursus:\n{e}", "error")

    #  GAJI GRID
    def _build_gaji_grid(self):
        """Dua sub-bagian: Gaji Admin dan Gaji Teacher."""
        outer = QVBoxLayout()
        outer.setSpacing(10)

        # ── GAJI ADMIN ───────────────────────────────────────────────
        outer.addWidget(self._section_lbl("Gaji Admin"))

        row1 = QHBoxLayout(); row1.setSpacing(24)

        col1a = QVBoxLayout(); col1a.setSpacing(6)
        col1a.addWidget(self._field_lbl("Gaji Admin (per kehadiran)"))
        wrap1a, self.gaji_admin = self._currency_input_rp("0")
        col1a.addWidget(wrap1a)

        col1b = QVBoxLayout(); col1b.setSpacing(6)
        col1b.addWidget(self._field_lbl("Uang Makan Admin (per kehadiran)"))
        wrap1b, self.uang_makan_admin = self._currency_input_rp("0")
        col1b.addWidget(wrap1b)

        row1.addLayout(col1a, 1)
        row1.addLayout(col1b, 1)
        outer.addLayout(row1)

        # ── GAJI TEACHER ─────────────────────────────────────────────
        outer.addWidget(self._section_lbl("Gaji Teacher"))

        row2 = QHBoxLayout(); row2.setSpacing(24)

        col2a = QVBoxLayout(); col2a.setSpacing(6)
        col2a.addWidget(self._field_lbl("Gaji Guru - Offline (per sesi)"))
        wrap2a, self.gaji_guru = self._currency_input_rp("0")
        col2a.addWidget(wrap2a)
        col2a.addWidget(self._lbl("Di luar biaya transportasi",
                                  "font-size:10px;font-style:italic;color:transparent;"
                                  "background:transparent;"))

        col2b = QVBoxLayout(); col2b.setSpacing(6)
        col2b.addWidget(self._field_lbl("Gaji Guru - Online (per sesi)"))
        wrap2b, self.gaji_guru_online = self._currency_input_rp("0")
        col2b.addWidget(wrap2b)
        col2b.addWidget(self._lbl("Di luar biaya transportasi",
                                  "font-size:10px;font-style:italic;color:transparent;"
                                  "background:transparent;"))

        # Gaji Guru - Home Visit (transport dihitung otomatis dari
        # pembayaran_sesi_murid, tidak diinput manual di sini)
        col2c = QVBoxLayout(); col2c.setSpacing(6)
        col2c.addWidget(self._field_lbl("Gaji Guru - Home Visit (per sesi)"))
        wrap2c, self.gaji_guru_home_visit = self._currency_input_rp("0")
        col2c.addWidget(wrap2c)
        col2c.addWidget(self._lbl("Di luar biaya transportasi",
                                  f"font-size:10px;font-style:italic;color:{C.TEXT_FAINT};"
                                  "background:transparent;"))

        row2.addLayout(col2a, 1)
        row2.addLayout(col2b, 1)
        row2.addLayout(col2c, 1)
        outer.addLayout(row2)

        return outer

    def _load_gaji_from_db(self):
        """Isi field gaji dari database saat widget pertama dibuka."""
        try:
            cfg = DB.get_pengaturan_gaji()
            self.gaji_admin.setText(self._format_ribuan(cfg["gaji_admin"]))
            self.uang_makan_admin.setText(self._format_ribuan(cfg["uang_makan_admin"]))
            self.gaji_guru.setText(self._format_ribuan(cfg["gaji_guru"]))
            self.gaji_guru_online.setText(self._format_ribuan(cfg["gaji_guru_online"]))
            self.gaji_guru_home_visit.setText(self._format_ribuan(cfg["gaji_guru_home_visit"]))
        except Exception:
            pass  # DB mungkin belum di-init; biarkan field kosong

    @_no_double_submit
    def _save_gaji(self):
        gaji_admin_str   = self.gaji_admin.text().strip()
        uang_makan_str   = self.uang_makan_admin.text().strip()
        gaji_guru_str    = self.gaji_guru.text().strip()
        gaji_guru_on_str = self.gaji_guru_online.text().strip()
        gaji_guru_hv_str = self.gaji_guru_home_visit.text().strip()

        if not all([gaji_admin_str, uang_makan_str, gaji_guru_str,
                    gaji_guru_on_str, gaji_guru_hv_str]):
            show_toast(self, "Perhatian", "Semua field gaji harus diisi!", "warning")
            return

        try:
            gaji_admin_val   = int(gaji_admin_str.replace(".", "").replace(",", ""))
            uang_makan_val   = int(uang_makan_str.replace(".", "").replace(",", ""))
            gaji_guru_val    = int(gaji_guru_str.replace(".", "").replace(",", ""))
            gaji_guru_on_val = int(gaji_guru_on_str.replace(".", "").replace(",", ""))
            gaji_guru_hv_val = int(gaji_guru_hv_str.replace(".", "").replace(",", ""))
        except ValueError:
            show_toast(self, "Perhatian", "Nilai gaji harus berupa angka!", "warning")
            return

        try:
            cfg_sekarang = DB.get_pengaturan_gaji()
        except Exception:
            cfg_sekarang = {}

        try:
            DB.set_pengaturan_gaji(
                gaji_admin=gaji_admin_val,
                uang_makan_admin=uang_makan_val,
                gaji_guru=gaji_guru_val,
                gaji_guru_visit_online=gaji_guru_on_val,  # kolom lama, ikut tarif Online
                transport_guru=0,
                gaji_guru_online=gaji_guru_on_val,
                gaji_guru_home_visit=gaji_guru_hv_val,
                durasi_online=cfg_sekarang.get("durasi_online"),
                durasi_offline=cfg_sekarang.get("durasi_offline"),
                durasi_home_visit=cfg_sekarang.get("durasi_home_visit"),
            )
        except Exception as e:
            show_toast(self, "Error", f"Gagal menyimpan ke database:\n{e}", "error")
            return

        # Tampilkan ulang dengan format titik ribuan supaya tetap rapi & sejajar
        self.gaji_admin.setText(self._format_ribuan(gaji_admin_val))
        self.uang_makan_admin.setText(self._format_ribuan(uang_makan_val))
        self.gaji_guru.setText(self._format_ribuan(gaji_guru_val))
        self.gaji_guru_online.setText(self._format_ribuan(gaji_guru_on_val))
        self.gaji_guru_home_visit.setText(self._format_ribuan(gaji_guru_hv_val))

        msg = (
            f"Pengaturan gaji berhasil disimpan:\n"
            f"• Gaji Admin            : Rp {gaji_admin_val:,}\n"
            f"• Uang Makan            : Rp {uang_makan_val:,}\n"
            f"• Gaji Guru - Offline   : Rp {gaji_guru_val:,}\n"
            f"• Gaji Guru - Online    : Rp {gaji_guru_on_val:,}\n"
            f"• Gaji Guru - Home Visit: Rp {gaji_guru_hv_val:,} (+ transport dihitung otomatis)"
        )
        show_toast(self, "Berhasil", msg, "success")

    def _currency_input_rp(self, placeholder=""):
        """Kotak input dengan prefix 'Rp' di dalamnya.
        Mengembalikan (wrapper_frame, line_edit)."""
        PengaturanWidget._card_seq += 1
        wname = f"wrap{PengaturanWidget._card_seq}"
        wrapper = QFrame()
        wrapper.setObjectName(wname)
        wrapper.setFixedHeight(38)
        wrapper.setStyleSheet(f"""
            QFrame#{wname}{{background:white;border:1.5px solid {C.BORDER};border-radius:8px;}}
        """)
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(12, 0, 10, 0)
        row.setSpacing(4)

        prefix = QLabel("Rp")
        prefix.setFixedWidth(20)
        prefix.setStyleSheet(
            f"font-size:12px;color:{C.TEXT_FAINT};background:transparent;border:none;")
        row.addWidget(prefix)

        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setStyleSheet(
            "QLineEdit{border:none;background:transparent;"
            f"font-size:12px;color:{C.TEXT_PRIMARY};padding:0;}}")
        row.addWidget(inp, 1)

        def _format_on_blur():
            raw = inp.text().strip().replace(".", "").replace(",", "")
            if raw.isdigit():
                inp.setText(self._format_ribuan(int(raw)))
        inp.editingFinished.connect(_format_on_blur)

        return wrapper, inp

    def _duration_input_menit(self, placeholder=""):
        """Kotak input dengan suffix 'Menit' di dalamnya.
        Mengembalikan (wrapper_frame, line_edit)."""
        PengaturanWidget._card_seq += 1
        wname = f"wrap{PengaturanWidget._card_seq}"
        wrapper = QFrame()
        wrapper.setObjectName(wname)
        wrapper.setFixedHeight(38)
        wrapper.setStyleSheet(f"""
            QFrame#{wname}{{background:white;border:1.5px solid {C.BORDER};border-radius:8px;}}
        """)
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(12, 0, 10, 0)
        row.setSpacing(4)

        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setStyleSheet(
            "QLineEdit{border:none;background:transparent;"
            f"font-size:12px;color:{C.TEXT_PRIMARY};padding:0;}}")
        row.addWidget(inp, 1)

        suffix = QLabel("Menit")
        suffix.setStyleSheet(
            f"font-size:12px;color:{C.TEXT_FAINT};background:transparent;border:none;")
        row.addWidget(suffix)

        return wrapper, inp

    #  DURASI SESI GRID
    def _build_durasi_grid(self):
        """Setiap kelompok: label di atas, kotak input durasi (menit) di bawah."""
        outer = QVBoxLayout()
        outer.setSpacing(14)

        def _durasi_group(label_text):
            group = QVBoxLayout()
            group.setSpacing(6)
            group.addWidget(self._field_lbl(label_text))
            wrap, inp = self._duration_input_menit("0")
            group.addWidget(wrap)
            outer.addLayout(group)
            return inp

        self.durasi_online = _durasi_group("Online")
        self.durasi_offline = _durasi_group("Offline / Sanggar")
        self.durasi_home_visit = _durasi_group("Home Visit")

        return outer

    def _load_durasi_from_db(self):
        """Isi field durasi sesi dari database saat widget pertama dibuka."""
        try:
            cfg = DB.get_pengaturan_gaji()
            self.durasi_online.setText(str(cfg["durasi_online"]))
            self.durasi_offline.setText(str(cfg["durasi_offline"]))
            self.durasi_home_visit.setText(str(cfg["durasi_home_visit"]))
        except Exception:
            # DB mungkin belum di-init; pakai default standar
            self.durasi_online.setText("30")
            self.durasi_offline.setText("45")
            self.durasi_home_visit.setText("45")

    @_no_double_submit
    def _save_durasi(self):
        durasi_online_str  = self.durasi_online.text().strip()
        durasi_offline_str = self.durasi_offline.text().strip()
        durasi_hv_str       = self.durasi_home_visit.text().strip()

        if not all([durasi_online_str, durasi_offline_str, durasi_hv_str]):
            show_toast(self, "Perhatian", "Semua field durasi harus diisi!", "warning")
            return

        try:
            durasi_online_val  = int(durasi_online_str)
            durasi_offline_val = int(durasi_offline_str)
            durasi_hv_val       = int(durasi_hv_str)
        except ValueError:
            show_toast(self, "Perhatian", "Durasi harus berupa angka (menit)!", "warning")
            return

        if durasi_online_val <= 0 or durasi_offline_val <= 0 or durasi_hv_val <= 0:
            show_toast(self, "Perhatian", "Durasi harus lebih besar dari 0 menit!", "warning")
            return

        # Ambil tarif gaji yang sudah tersimpan supaya tidak ikut ter-overwrite
        try:
            cfg = DB.get_pengaturan_gaji()
        except Exception as e:
            show_toast(self, "Error", f"Gagal membaca pengaturan gaji:\n{e}", "error")
            return

        try:
            DB.set_pengaturan_gaji(
                gaji_admin=cfg["gaji_admin"],
                uang_makan_admin=cfg["uang_makan_admin"],
                gaji_guru=cfg["gaji_guru"],
                gaji_guru_visit_online=cfg["gaji_guru_visit_online"],
                transport_guru=cfg.get("transport_guru", 0),
                gaji_guru_online=cfg["gaji_guru_online"],
                gaji_guru_home_visit=cfg["gaji_guru_home_visit"],
                durasi_online=durasi_online_val,
                durasi_offline=durasi_offline_val,
                durasi_home_visit=durasi_hv_val,
            )
        except Exception as e:
            show_toast(self, "Error", f"Gagal menyimpan ke database:\n{e}", "error")
            return

        msg = (
            f"Pengaturan durasi sesi berhasil disimpan:\n"
            f"• Online       : {durasi_online_val} menit\n"
            f"• Offline      : {durasi_offline_val} menit\n"
            f"• Home Visit   : {durasi_hv_val} menit"
        )
        show_toast(self, "Berhasil", msg, "success")

    #  HELPERS
    def _lbl(self, text, style):
        l = QLabel(text)
        l.setStyleSheet(style + "border:none;")
        l.setWordWrap(True)
        return l

    def _field_lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            f"font-size:11px;font-weight:600;color:{C.TEXT_MUTED};"
            "background:transparent;border:none;")
        return l

    def _section_lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};"
            "background:transparent;border:none;")
        return l

    def _format_ribuan(self, value):
        """Format angka jadi string dengan titik ribuan, mis. 40000 -> '40.000'."""
        try:
            n = int(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{n:,}".replace(",", ".")

    def _text_input(self, placeholder=""):
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(40)
        inp.setStyleSheet(f"""
            QLineEdit{{
                border:1.5px solid {C.BORDER};border-radius:8px;
                padding-left:12px;font-size:12px;color:{C.TEXT_PRIMARY};
                background:white;
            }}
            QLineEdit:focus{{border:1.5px solid {C.ACCENT};background:white;}}
        """)
        return inp


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    w = PengaturanWidget()
    w.setWindowTitle("Pengaturan – Melody Violin School")
    w.resize(1150, 820)
    w.show()
    sys.exit(app.exec_())