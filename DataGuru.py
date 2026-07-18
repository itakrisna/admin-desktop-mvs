import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit, QDialog,
    QComboBox, QCheckBox, QRadioButton, QButtonGroup,
    QTextEdit, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from toast_notification import show_toast, confirm_action
from theme import svg_icon, C, style_combo, action_button_style, primary_button_style


#  Avatar circle widget
class AvatarLabel(QLabel):
    COLORS = [f"{C.ACCENT}", "#10B981", f"{C.WARNING}", "#8B5CF6", f"{C.DANGER}", "#06B6D4"]
    def __init__(self, initials, idx=0):
        super().__init__(initials)
        self.setFixedSize(32, 32)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"background:{self.COLORS[idx % len(self.COLORS)]};color:white;"
            f"border-radius:16px;font-weight:bold;font-size:11px;"
        )


#  Clickable Stat Card  (gaya DashboardAdmin)
def _card_style(active=False, hover=False):
    if active:
        bg     = "#F0F6FF"
        border = f"2px solid {C.ACCENT}"
    elif hover:
        bg     = f"{C.SURFACE_ALT}"
        border = f"1.5px solid {C.BORDER_STRONG}"
    else:
        bg     = "white"
        border = f"1px solid {C.BORDER}"
    return (
        f"QFrame#statCard{{"
        f"background-color:{bg};border:{border};border-radius:14px;}}"
        f"QFrame#statCard QLabel{{border:none;background:transparent;}}"
    )


class StatCard(QFrame):
    def __init__(self, title, value, side_text, accent, filter_key, on_click):
        super().__init__()
        self.filter_key = filter_key
        self.on_click   = on_click
        self._active    = False
        self._accent    = accent

        self.setObjectName("statCard")
        self.setFixedSize(200, 90)
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(_card_style())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(6)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(
            f"color:{C.TEXT_MUTED};font-size:12px;font-weight:normal;"
        )

        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(
            f"color:{C.TEXT_PRIMARY};font-size:28px;font-weight:bold;"
        )

        lay.addWidget(self.title_lbl)
        lay.addWidget(self.val_lbl)

    def enterEvent(self, event):
        if not self._active:
            self.setStyleSheet(_card_style(hover=True))
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._active:
            self.setStyleSheet(_card_style())
        super().leaveEvent(event)

    def set_active(self, active):
        self._active = active
        self.setStyleSheet(_card_style(active=active))
        if active:
            self.title_lbl.setStyleSheet(
                f"color:{self._accent};font-size:12px;font-weight:bold;"
            )
        else:
            self.title_lbl.setStyleSheet(
                f"color:{C.TEXT_MUTED};font-size:12px;font-weight:normal;"
            )

    def mousePressEvent(self, event):
        self.on_click(self.filter_key)
        super().mousePressEvent(event)


#  Modal Dialog – Tambah / Edit Guru
class DataGuruDialog(QDialog):
    def __init__(self, parent=None, guru_data=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(460)
        self._guru_data = guru_data  # dict row untuk mode edit, None untuk tambah
        self._current_status = "Aktif"  # default; dioverride saat prefill edit
        self._build()
        if guru_data:
            self._prefill(guru_data)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setFrameShape(QFrame.NoFrame)
        card.setStyleSheet("QFrame{background:white;border-radius:16px;}")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(28, 24, 28, 24)
        cv.setSpacing(16)

        # header
        hdr = QHBoxLayout()
        htxt = QVBoxLayout(); htxt.setSpacing(2)
        htxt.addWidget(self._lbl("Data Guru", f"font-size:16px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        htxt.addWidget(self._lbl("Lengkapi detail instruktur di bawah ini", f"font-size:11px;color:{C.TEXT_MUTED_STRONG};"))
        hdr.addLayout(htxt); hdr.addStretch()
        close = QPushButton()
        close.setIcon(svg_icon("x", C.TEXT_MUTED, 12))
        close.setFixedSize(28, 28)
        close.setStyleSheet(f"QPushButton{{border:none;background:transparent;color:{C.TEXT_MUTED_STRONG};font-size:14px;}}"
                            f"QPushButton:hover{{color:{C.TEXT_PRIMARY};}}")
        close.clicked.connect(self.reject)
        hdr.addWidget(close)
        cv.addLayout(hdr)

        # Row 1: Nama + No HP
        row1 = QHBoxLayout(); row1.setSpacing(16)
        nama_col, self._nama_le = self._field("Nama Guru", "Masukkan nama lengkap")
        hp_col,   self._hp_le   = self._field("No HP", "0812xxxxxx")
        row1.addLayout(nama_col); row1.addLayout(hp_col)
        cv.addLayout(row1)

        # Email
        email_col, self._email_le = self._field("Email", "contoh: guru@gmail.com")
        cv.addLayout(email_col)

        # Jenis Kelamin
        cv.addWidget(self._lbl("Jenis Kelamin", f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        jk_row = QHBoxLayout(); jk_row.setSpacing(20)
        self._rb_laki = QRadioButton("Laki-laki")
        self._rb_perempuan = QRadioButton("Perempuan")
        for rb in [self._rb_laki, self._rb_perempuan]:
            rb.setStyleSheet(f"font-size:12px;color:{C.TEXT_SECONDARY};")
        jk_grp = QButtonGroup(self)
        jk_grp.addButton(self._rb_laki); jk_grp.addButton(self._rb_perempuan)
        jk_row.addWidget(self._rb_laki); jk_row.addWidget(self._rb_perempuan); jk_row.addStretch()
        cv.addLayout(jk_row)

        # Alamat
        alamat_col, self._alamat_te = self._field_area("Alamat", "Alamat lengkap tempat tinggal")
        cv.addLayout(alamat_col)

        # Status dikelola via toggle di tabel — tidak ditampilkan di form

        # Metode + Kursus
        checks = QHBoxLayout(); checks.setSpacing(32)
        metode = QVBoxLayout(); metode.setSpacing(8)
        metode.addWidget(self._lbl("Metode Mengajar", f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        self._cb_offline = QCheckBox("Offline"); self._cb_offline.setStyleSheet(f"font-size:12px;color:{C.TEXT_SECONDARY};")
        self._cb_online  = QCheckBox("Online");  self._cb_online.setStyleSheet(f"font-size:12px;color:{C.TEXT_SECONDARY};")
        self._cb_home_visit = QCheckBox("Home Visit"); self._cb_home_visit.setStyleSheet(f"font-size:12px;color:{C.TEXT_SECONDARY};")
        metode.addWidget(self._cb_offline); metode.addWidget(self._cb_online); metode.addWidget(self._cb_home_visit)

        kursus = QVBoxLayout(); kursus.setSpacing(8)
        kursus.addWidget(self._lbl("Kursus yang Diajarkan", f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        kg = QHBoxLayout(); kg.setSpacing(24)
        lk = QVBoxLayout(); lk.setSpacing(8)
        rk = QVBoxLayout(); rk.setSpacing(8)
        self._kursus_checks = {}
        for i, opt in enumerate(["Biola", "Vocal", "Gitar", "Piano", "Drum"]):
            cb = QCheckBox(opt); cb.setStyleSheet(f"font-size:12px;color:{C.TEXT_SECONDARY};")
            self._kursus_checks[opt] = cb
            (lk if i < 3 else rk).addWidget(cb)
        kg.addLayout(lk); kg.addLayout(rk)
        kursus.addLayout(kg)

        checks.addLayout(metode); checks.addLayout(kursus); checks.addStretch()
        cv.addLayout(checks)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C.SURFACE_HOVER};max-height:1px;")
        cv.addWidget(sep)

        foot = QHBoxLayout(); foot.setSpacing(10)

        kembali = QPushButton(" Kembali")
        kembali.setIcon(svg_icon("arrow-left", C.TEXT_SECONDARY, 13))
        kembali.setFixedHeight(38)
        kembali.setStyleSheet(f"QPushButton{{background:white;color:{C.TEXT_SECONDARY};border:1px solid {C.BORDER};"
                              "border-radius:10px;font-size:12px;padding:0 20px;}"
                              f"QPushButton:hover{{background:{C.SURFACE_ALT};border-color:{C.BORDER_STRONG};}}")
        kembali.clicked.connect(self.reject)

        hapus = QPushButton("Hapus")
        hapus.setFixedHeight(38)
        hapus.setStyleSheet(f"QPushButton{{background:white;color:{C.DANGER_DARKER};border:1.5px solid {C.DANGER};"
                            "border-radius:10px;font-size:12px;font-weight:bold;padding:0 20px;}"
                            f"QPushButton:hover{{background:{C.DANGER_BG};}}")
        hapus.clicked.connect(self._on_hapus)

        simpan = QPushButton("Simpan")
        simpan.setFixedHeight(38)
        simpan.setStyleSheet(f"QPushButton{{background:{C.ACCENT};color:white;border:none;"
                             "border-radius:10px;font-size:12px;font-weight:bold;padding:0 24px;}"
                             f"QPushButton:hover{{background:{C.ACCENT_DARK};}}")
        simpan.clicked.connect(self._on_simpan)
        self._btn_simpan = simpan

        foot.addWidget(kembali)
        foot.addStretch()
        foot.addWidget(hapus)
        foot.addWidget(simpan)
        cv.addLayout(foot)
        outer.addWidget(card)

    def _prefill(self, d):
        self._nama_le.setText(d.get("nama", ""))
        self._email_le.setText(d.get("email", ""))
        self._hp_le.setText(d.get("hp", ""))
        self._alamat_te.setPlainText(d.get("alamat", ""))

        # gunakan key "lp" (L/P) yang dikirim dari guru_dict di _render_table
        jk = d.get("lp", "").upper()
        if jk == "L":
            self._rb_laki.setChecked(True)
        elif jk == "P":
            self._rb_perempuan.setChecked(True)

        self._current_status = d.get("status", "AKTIF")

        metode_list = [m.strip() for m in d.get("metode", "").split(",")]
        self._cb_offline.setChecked("Offline" in metode_list)
        self._cb_online.setChecked("Online" in metode_list)
        self._cb_home_visit.setChecked("Home Visit" in metode_list)

        # prefill kursus yang diajarkan
        keahlian_list = [k.strip() for k in d.get("keahlian", "").split(",")]
        for opt, cb in self._kursus_checks.items():
            cb.setChecked(opt in keahlian_list)

    def _on_hapus(self):
        # Dialog konfirmasi custom, senada dengan gaya visual toast di seluruh app
        if not self._guru_data:
            return
        if confirm_action(
            self, "Konfirmasi Hapus",
            f"Hapus guru '{self._nama_le.text().strip()}'?"
        ):
            self._result_action = "hapus"
            self.accept()

    def _on_simpan(self):
        from database import DB

        nama   = self._nama_le.text().strip()
        email  = self._email_le.text().strip()
        hp     = self._hp_le.text().strip()
        alamat = self._alamat_te.toPlainText().strip()

        # Validasi semua field wajib diisi
        if not nama:
            show_toast(self, "Perhatian", "Nama guru tidak boleh kosong.", "warning", anchor=self._btn_simpan)
            return
        if not email:
            show_toast(self, "Perhatian", "Email tidak boleh kosong.", "warning", anchor=self._btn_simpan)
            return
        if not hp:
            show_toast(self, "Perhatian", "No HP tidak boleh kosong.", "warning", anchor=self._btn_simpan)
            return
        if not self._rb_laki.isChecked() and not self._rb_perempuan.isChecked():
            show_toast(self, "Perhatian", "Jenis kelamin harus dipilih.", "warning", anchor=self._btn_simpan)
            return
        if not alamat:
            show_toast(self, "Perhatian", "Alamat tidak boleh kosong.", "warning", anchor=self._btn_simpan)
            return
        if not (self._cb_offline.isChecked() or self._cb_online.isChecked() or self._cb_home_visit.isChecked()):
            show_toast(self, "Perhatian", "Pilih minimal satu metode mengajar.", "warning", anchor=self._btn_simpan)
            return
        kursus_dipilih = [opt for opt, cb in self._kursus_checks.items() if cb.isChecked()]
        if not kursus_dipilih:
            show_toast(self, "Perhatian", "Pilih minimal satu kursus yang diajarkan.", "warning", anchor=self._btn_simpan)
            return

        # Cegah klik ganda memicu INSERT/UPDATE dua kali sebelum dialog tertutup
        self._btn_simpan.setEnabled(False)

        jenis_kel = "L" if self._rb_laki.isChecked() else "P"

        # Status dikelola via toggle di tabel
        status = getattr(self, "_current_status", "Aktif")
        if status.upper() == "AKTIF":
            status = "Aktif"
        elif status.upper() == "CUTI":
            status = "Cuti"
        else:
            status = "Nonaktif"

        metode_parts = []
        if self._cb_offline.isChecked():    metode_parts.append("Offline")
        if self._cb_online.isChecked():     metode_parts.append("Online")
        if self._cb_home_visit.isChecked(): metode_parts.append("Home Visit")
        metode = ", ".join(metode_parts)
        keahlian = ", ".join(kursus_dipilih)

        try:
            # Pastikan kolom email ada (migration-safe untuk database lama)
            try:
                DB.execute("ALTER TABLE guru ADD COLUMN email TEXT")
            except Exception:
                pass

            if self._guru_data and self._guru_data.get("db_id"):
                # UPDATE
                DB.execute(
                    "UPDATE guru SET nama=?,email=?,no_hp=?,jenis_kel=?,alamat=?,status=?,metode=?,keahlian=? WHERE id=?",
                    (nama, email, hp, jenis_kel, alamat, status, metode, keahlian, self._guru_data["db_id"])
                )
            else:
                # INSERT — generate kode otomatis
                last = DB.fetch_one("SELECT kode FROM guru ORDER BY id DESC LIMIT 1")
                if last and last["kode"]:
                    try:
                        num = int(last["kode"].split("-")[1]) + 1
                    except Exception:
                        num = 1
                else:
                    num = 1
                kode = f"TCH-{num:03d}"
                DB.execute(
                    "INSERT INTO guru(kode,nama,email,no_hp,jenis_kel,alamat,status,metode,keahlian,gaji_per_sesi) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (kode, nama, email, hp, jenis_kel, alamat, status, metode, keahlian, 150000)
                )
            self.accept()
        except Exception as e:
            self._btn_simpan.setEnabled(True)
            show_toast(self, "Gagal", f"Gagal menyimpan data guru: {str(e)}", "error", anchor=self._btn_simpan)

    def _lbl(self, text, style):
        l = QLabel(text); l.setStyleSheet(style); return l

    def _field(self, label, placeholder):
        col = QVBoxLayout(); col.setSpacing(5)
        col.addWidget(self._lbl(label, f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        le = QLineEdit(); le.setPlaceholderText(placeholder)
        le.setFixedHeight(36)
        le.setStyleSheet(f"QLineEdit{{border:1px solid {C.BORDER};border-radius:8px;padding-left:12px;"
                         f"font-size:12px;color:{C.TEXT_PRIMARY};background:white;}}"
                         f"QLineEdit:focus{{border:1px solid {C.ACCENT};}}")
        col.addWidget(le)
        return col, le

    def _field_area(self, label, placeholder):
        col = QVBoxLayout(); col.setSpacing(5)
        col.addWidget(self._lbl(label, f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        te = QTextEdit(); te.setPlaceholderText(placeholder)
        te.setFixedHeight(70)
        te.setStyleSheet(f"QTextEdit{{border:1px solid {C.BORDER};border-radius:8px;padding:8px 12px;"
                         f"font-size:12px;color:{C.TEXT_PRIMARY};background:white;}}"
                         f"QTextEdit:focus{{border:1px solid {C.ACCENT};}}")
        col.addWidget(te)
        return col, te


#  Load guru data dari database
def _load_guru_data():
    from database import DB
    # Pastikan kolom email ada (migration-safe untuk database lama)
    try:
        DB.execute("ALTER TABLE guru ADD COLUMN email TEXT")
    except Exception:
        pass
    rows = DB.fetch_all("""
        SELECT id, kode, nama, jenis_kel, keahlian, no_hp, status, metode, alamat, email
        FROM guru ORDER BY id
    """)
    result = []
    for i, r in enumerate(rows, 1):
        nama = r["nama"] or ""
        inits = "".join(w[0].upper() for w in nama.split()[:2]) if nama else "??"
        lp = r["jenis_kel"] or ""
        status_raw = (r["status"] or "Aktif").upper()
        status_display = "AKTIF" if status_raw == "AKTIF" else "CUTI" if status_raw == "CUTI" else "NONAKTIF"
        result.append((
            str(i),
            r["kode"] or "",
            inits,
            nama,
            lp,
            r["keahlian"] or "",
            r["no_hp"] or "",
            status_display,
            r["id"],       # index 8 = db_id
            r["metode"] or "",
            r["alamat"] or "",
            r["email"] or "",   # index 11 = email
        ))
    return result


#  Main Data Guru Widget
class DataGuruWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{C.SURFACE_ALT};")
        self._active_filter = "AKTIF"
        self._stat_cards = {}
        self._guru_data = _load_guru_data()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(20)

        # ── Top bar ───────────────────────────────────────────────────
        top = QHBoxLayout()
        tb = QVBoxLayout(); tb.setSpacing(2)
        tb.addWidget(self._lbl("Data Guru", f"font-size:22px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        tb.addWidget(self._lbl("Kelola informasi instruktur Melody Violin School", f"font-size:12px;color:{C.TEXT_MUTED_STRONG};"))
        top.addLayout(tb); top.addStretch()
        add_btn = QPushButton("+ Tambah Guru")
        add_btn.setFixedHeight(38)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(primary_button_style())
        add_btn.clicked.connect(self._open_add_dialog)
        top.addWidget(add_btn)
        root.addLayout(top)

        # ── Stat cards (clickable) ────────────────────────────────────
        sc = QHBoxLayout(); sc.setSpacing(20)
        total    = len(self._guru_data)
        aktif    = sum(1 for r in self._guru_data if r[7] == "AKTIF")
        nonaktif = total - aktif
        cards_def = [
            ("Total Guru",     str(total),    "Orang",      f"{C.ACCENT}", "SEMUA"),
            ("Guru Aktif",     str(aktif),    "Tersedia",   "#10B981", "AKTIF"),
            ("Guru Non-Aktif", str(nonaktif), "Cuti/Libur", f"{C.DANGER}", "NON-AKTIF"),
        ]
        for title, val, side, accent, key in cards_def:
            card = StatCard(title, val, side, accent, key, self._on_stat_click)
            self._stat_cards[key] = card
            sc.addWidget(card)
        sc.addStretch()
        self._stat_cards["AKTIF"].set_active(True)
        root.addLayout(sc)

        # ── Table card ───────────────────────────────────────────────
        tcard = QFrame()
        tcard.setFrameShape(QFrame.NoFrame)
        tcard.setStyleSheet("QFrame{background:white;border-radius:14px;border:none;}")
        cv = QVBoxLayout(tcard); cv.setContentsMargins(22, 20, 22, 20); cv.setSpacing(14)

        sf = QHBoxLayout(); sf.setSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari Nama Guru atau ID...")
        self.search.addAction(svg_icon("search", C.TEXT_FAINT, 15), QLineEdit.LeadingPosition)
        self.search.setFixedHeight(36)
        self.search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search.setStyleSheet(f"""
            QLineEdit {{
                border:1.5px solid {C.BORDER}; border-radius:8px;
                background:{C.SURFACE_ALT}; padding-left:12px;
                font-size:12px; color:{C.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{ border:1.5px solid {C.ACCENT}; background:white; }}
        """)
        self.search.textChanged.connect(self._apply_filters)

        self.filter_keahlian = QComboBox()
        # Label harus sama persis dengan opsi "Kursus yang Diajarkan" di form Tambah/Edit Guru
        # (lihat _kursus_checks), supaya cocok dengan nilai keahlian yang tersimpan di database.
        self.filter_keahlian.addItems(["Semua Keahlian", "Biola", "Vocal", "Gitar", "Piano", "Drum"])
        self.filter_keahlian.setFixedHeight(36); self.filter_keahlian.setFixedWidth(160)
        style_combo(self.filter_keahlian, radius=8, height=36, font_size=12)
        self.filter_keahlian.currentIndexChanged.connect(self._apply_filters)
        sf.addWidget(self.search); sf.addWidget(self.filter_keahlian)
        cv.addLayout(sf)

        # active filter label
        self.filter_label = QLabel("")
        self.filter_label.setStyleSheet(f"font-size:11px;color:{C.TEXT_MUTED};")
        cv.addWidget(self.filter_label)

        cols = ["NO", "NAMA GURU", "L/P", "KEAHLIAN", "NO HP", "EMAIL", "METODE", "STATUS", "AKSI"]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(f"""
            QTableWidget {{ border:none; background:white; }}
            QHeaderView::section {{
                background:{C.SURFACE_ALT}; padding:10px 8px;
                border:none; border-bottom:2px solid {C.SURFACE_HOVER};
                color:{C.TEXT_MUTED_STRONG}; font-weight:bold; font-size:11px;
            }}
            QTableWidget::item {{
                padding:10px 8px; border-bottom:1px solid {C.SURFACE_HOVER};
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
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed); self.table.setColumnWidth(0, 48)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed); self.table.setColumnWidth(2, 40)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed); self.table.setColumnWidth(7, 160)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed); self.table.setColumnWidth(8, 90)
        self.table.verticalHeader().setDefaultSectionSize(58)
        cv.addWidget(self.table)
        self._apply_filters()

        # pagination
        pg = QHBoxLayout()
        self.pg_info = QLabel("")
        self.pg_info.setStyleSheet(f"color:{C.TEXT_MUTED_STRONG};font-size:11px;")
        pg.addWidget(self.pg_info); pg.addStretch()
        for txt in ["‹ Prev", "1", "Next ›"]:
            b = QPushButton(txt)
            b.setFixedHeight(32)
            b.setFixedWidth(50 if txt.isdigit() else 70)
            b.setCursor(Qt.PointingHandCursor)
            active = txt == "1"
            b.setStyleSheet(
                "QPushButton{border-radius:6px;font-size:12px;"
                f"background:{f'{C.ACCENT}' if active else 'white'};"
                f"color:{'white' if active else f'{C.TEXT_MUTED}'};"
                f"border:{'none' if active else f'1px solid {C.BORDER}'};}}"
                f"QPushButton:hover{{background:{f'{C.ACCENT_DARK}' if active else f'{C.SURFACE_ALT}'};}}"
            )
            pg.addWidget(b)
        cv.addLayout(pg)
        root.addWidget(tcard)

    def _on_stat_click(self, key):
        # toggle: click active card → reset to SEMUA
        if self._active_filter == key and key != "SEMUA":
            key = "SEMUA"
        self._active_filter = key
        for k, card in self._stat_cards.items():
            card.set_active(k == key)
        self._apply_filters()

    def _apply_filters(self):
        query = self.search.text().lower() if hasattr(self, "search") else ""
        f_keahlian = self.filter_keahlian.currentText() if hasattr(self, "filter_keahlian") else "Semua Keahlian"
        filtered = []
        for row in self._guru_data:
            no, id_guru, inits, nama, lp, keahlian, hp, status = row[:8]
            if self._active_filter == "AKTIF" and status != "AKTIF":
                continue
            if self._active_filter == "NON-AKTIF" and status == "AKTIF":
                continue
            if query and query not in nama.lower() and query not in id_guru.lower():
                continue
            if f_keahlian != "Semua Keahlian":
                keahlian_list = [k.strip() for k in keahlian.split(",")]
                if f_keahlian not in keahlian_list:
                    continue
            filtered.append(row)
        self._render_table(filtered)
        label_map = {"SEMUA": "Semua Guru", "AKTIF": "Guru Aktif", "NON-AKTIF": "Guru Non-Aktif"}
        label = label_map.get(self._active_filter, "")
        if f_keahlian != "Semua Keahlian":
            label = f"{label} • Keahlian: {f_keahlian}"
        self.filter_label.setText(f"Filter aktif: {label}  •  {len(filtered)} guru ditampilkan")
        if hasattr(self, "pg_info"):
            self.pg_info.setText(f"Menampilkan 1-{len(filtered)} dari {len(self._guru_data)} Guru")

    def _render_table(self, data):
        self.table.setRowCount(len(data))
        for r, row in enumerate(data):
            no, id_guru, inits, nama, lp, keahlian, hp, status = row[:8]
            db_id = row[8] if len(row) > 8 else None
            metode = row[9] if len(row) > 9 else ""
            alamat = row[10] if len(row) > 10 else ""
            email = row[11] if len(row) > 11 else ""

            self.table.setItem(r, 0, QTableWidgetItem(no))

            nama_w = QWidget()
            nl = QHBoxLayout(nama_w); nl.setContentsMargins(6, 4, 6, 4); nl.setSpacing(10)
            name_lbl = QLabel(nama)
            name_lbl.setStyleSheet(f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};")
            nl.addWidget(name_lbl); nl.addStretch()
            self.table.setCellWidget(r, 1, nama_w)

            self.table.setItem(r, 2, QTableWidgetItem(lp))
            self.table.setItem(r, 3, QTableWidgetItem(keahlian))
            self.table.setItem(r, 4, QTableWidgetItem(hp))
            self.table.setItem(r, 5, QTableWidgetItem(email))

            # Kolom METODE (col 6) — teks biasa, koma-separated
            metode_lbl = QLabel(metode)
            metode_lbl.setStyleSheet(f"font-size:12px;color:{C.TEXT_BODY};padding-left:8px;")
            metode_lbl.setWordWrap(True)
            self.table.setCellWidget(r, 6, metode_lbl)

            is_active = (status == "AKTIF")

            guru_dict = {
                "db_id": db_id, "nama": nama, "hp": hp, "email": email,
                "keahlian": keahlian, "alamat": alamat,
                "status": status, "metode": metode,
                "lp": lp,
            }

            # Status — Toggle Switch interaktif
            toggle_w = QWidget()
            tl = QHBoxLayout(toggle_w)
            tl.setContentsMargins(8, 0, 8, 0)
            tl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            toggle_btn = QPushButton()
            toggle_btn.setFixedSize(52, 26)
            toggle_btn.setCursor(Qt.PointingHandCursor)
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(is_active)

            lbl_toggle = QLabel()

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

            def _on_toggle(checked, d=guru_dict, btn=toggle_btn, lbl=lbl_toggle):
                from database import DB
                new_status = "Aktif" if checked else "Nonaktif"
                DB.execute("UPDATE guru SET status=? WHERE id=?", (new_status, d["db_id"]))
                new_status_display = "AKTIF" if checked else "NONAKTIF"
                d["status"] = new_status_display
                # self._guru_data berisi tuple (immutable) — cari & bangun ulang
                # barisnya berdasarkan db_id supaya stat card ikut ter-update.
                for idx, row_ref in enumerate(self._guru_data):
                    if row_ref[8] == d["db_id"]:
                        row_list = list(row_ref)
                        row_list[7] = new_status_display
                        self._guru_data[idx] = tuple(row_list)
                        break
                _apply_style(btn, lbl, checked)
                self._update_stat_counts()

            toggle_btn.toggled.connect(_on_toggle)
            tl.addWidget(toggle_btn)
            tl.addSpacing(8)
            tl.addWidget(lbl_toggle)
            self.table.setCellWidget(r, 7, toggle_w)

            # Aksi – Edit button
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedHeight(32)
            edit_btn.setMinimumWidth(64)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(action_button_style())
            edit_btn.clicked.connect(lambda _, d=guru_dict: self._open_edit_dialog(d))
            aw = QWidget(); al = QHBoxLayout(aw); al.setContentsMargins(6, 4, 6, 4); al.addWidget(edit_btn)
            self.table.setCellWidget(r, 8, aw)

    def _open_add_dialog(self):
        dlg = DataGuruDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._guru_data = _load_guru_data()
            self._update_stat_counts()
            self._apply_filters()
            show_toast(self, "Berhasil", "Data Berhasil Disimpan", "success")

    def _open_edit_dialog(self, guru_dict):
        dlg = DataGuruDialog(self, guru_dict)
        if dlg.exec_() == QDialog.Accepted:
            if getattr(dlg, "_result_action", None) == "hapus" and guru_dict.get("db_id"):
                from database import DB
                DB.execute("DELETE FROM guru WHERE id=?", (guru_dict["db_id"],))
                show_toast(self, "Berhasil", "Data Guru Berhasil Dihapus", "success")
            else:
                show_toast(self, "Berhasil", "Data Berhasil Disimpan", "success")
            self._guru_data = _load_guru_data()
            self._update_stat_counts()
            self._apply_filters()

    def _update_stat_counts(self):
        total    = len(self._guru_data)
        aktif    = sum(1 for r in self._guru_data if r[7] == "AKTIF")
        nonaktif = total - aktif
        counts = {"SEMUA": total, "AKTIF": aktif, "NON-AKTIF": nonaktif}
        for key, card in self._stat_cards.items():
            card.val_lbl.setText(str(counts.get(key, 0)))


    def _lbl(self, text, style):
        l = QLabel(text); l.setStyleSheet(style); return l


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    w = DataGuruWidget()
    w.setWindowTitle("Data Guru – Melody Violin School")
    w.resize(1150, 750)
    w.show()
    sys.exit(app.exec_())