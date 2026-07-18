import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QFrame, QStackedWidget,
    QApplication, QSizePolicy,
    QDialog, QScrollArea,
    QShortcut, QButtonGroup, QMenu
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QKeySequence

# ── page imports ──────────────────────────────────────────────────────────────
from DataMurid import DataMuridWidget, TambahMuridDialog, TambahJadwalDialog
from DataGuru import DataGuruWidget
from Absensi import (
    AbsensiWidget, _load_jadwal_tanggal, render_absensi_card_list,
    FormAbsensiAdminDialog, render_reminder_besok_card_list
)
from LaporanKeuangan import LaporanKeuanganAdminWidget as LaporanKeuanganWidget
from Pembayaran import PembayaranMainWidget
from toast_notification import confirm_action, show_toast
from theme import C, sidebar_styles, sidebar_icon, svg_icon, svg_pixmap, PageHeader, TextScaleController, scale_stylesheet, install_text_scale_shortcuts, primary_button_style  # noqa: F401 (install_text_scale_shortcuts dipakai di blok __main__)

# ── Palet & style sidebar dari theme.py (satu sumber warna, sama dgn Dashboard Owner) ──
SIDEBAR_STYLE, MENU_ACTIVE, MENU_NORMAL, LOGOUT_STYLE = sidebar_styles()

# Nama section untuk breadcrumb topbar — harus sinkron urutan dgn menu_items
_MENU_SECTIONS = ["Dashboard", "Data Murid", "Data Guru", "Absensi",
                   "Pembayaran", "Laporan Keuangan"]


#  NOTE: Panel kanan-bawah ("Absensi Murid: Hari Ini") punya 2 tab —
#        "Absensi Hari Ini" (tandai Hadir/Tidak Hadir) & "Reminder Besok"
#        (kartu pengingat H-1, Salin Pengingat + Reschedule).

class DashboardWindow(QWidget):
    def __init__(self, switch_to_login=None):
        super().__init__()

        self.switch_to_login = switch_to_login
        self.username = "Admin Utama"
        self._menu_buttons = []
        self.init_ui()

    def init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── SIDEBAR ───────────────────────────────────────────────────────────
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setStyleSheet(SIDEBAR_STYLE)
        self.sidebar.setFixedWidth(200)  # Lebar sama dengan DashboardOwner (konsistensi)
        side_v = QVBoxLayout(self.sidebar)
        side_v.setContentsMargins(0, 0, 0, 0)
        side_v.setSpacing(0)

        logo_frame = QFrame()
        logo_frame.setStyleSheet(f"background-color: #FFFFFF; border-bottom: 1px solid {C.SURFACE_HOVER};")
        logo_frame.setFixedHeight(70)
        logo_lay = QVBoxLayout(logo_frame)
        logo_lay.setContentsMargins(20, 0, 20, 0)
        logo_lbl = QLabel("ADMIN MVS")
        logo_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {C.TEXT_PRIMARY}; letter-spacing: 1px;")
        logo_lay.addWidget(logo_lbl)
        side_v.addWidget(logo_frame)

        side_v.addSpacing(10)

        menu_items = ["Dashboard", "Data Murid", "Data Guru", "Absensi", "Pembayaran", "Laporan Keuangan"]
        menu_icon_names = ["dashboard", "murid", "guru", "absensi", "pembayaran", "laporan"]
        self._menu_icon_names = menu_icon_names
        for i, label in enumerate(menu_items):
            btn = QPushButton(f"  {label}")
            btn.setIcon(sidebar_icon(menu_icon_names[i], active=(i == 0)))
            btn.setIconSize(QSize(20, 20))
            btn.setFixedHeight(48)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(MENU_NORMAL)
            # Tooltip mencantumkan pintasan Alt+N sebagai alternatif mouse
            btn.setToolTip(f"Buka halaman {label}  (Alt+{i + 1})")
            btn.setAccessibleName(f"Menu {label}")            # aksesibilitas (screen reader)
            btn.setFocusPolicy(Qt.StrongFocus)                # bisa dinavigasi via Tab/keyboard
            side_v.addWidget(btn)
            self._menu_buttons.append(btn)

        side_v.addStretch()

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color: {C.BORDER};")
        side_v.addWidget(div)

        self.btn_logout = QPushButton("  Keluar Sistem")
        self.btn_logout.setIcon(sidebar_icon("logout", muted_color=C.DANGER, accent=C.DANGER))
        self.btn_logout.setIconSize(QSize(20, 20))
        self.btn_logout.setFixedHeight(48)
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.setStyleSheet(LOGOUT_STYLE)
        self.btn_logout.setToolTip("Keluar dari sistem dan kembali ke halaman login")
        self.btn_logout.setAccessibleName("Tombol Keluar Sistem")
        self.btn_logout.clicked.connect(self.logout)
        side_v.addWidget(self.btn_logout)

        root.addWidget(self.sidebar)

        # ── MAIN CONTENT ──────────────────────────────────────────────────────
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)

        topbar = QFrame()
        topbar.setFixedHeight(60)
        topbar.setStyleSheet(f"background-color: white; border-bottom: 1px solid {C.BORDER};")
        tb_lay = QHBoxLayout(topbar)
        tb_lay.setContentsMargins(30, 0, 30, 0)

        # Breadcrumb topbar, selalu sinkron dengan halaman aktif (diupdate di _switch_page)
        self.page_header = PageHeader("MELODY VIOLIN SCHOOL", "Dashboard")

        # Label status/error (sebelumnya hanya tercetak di konsol)
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(
            f"font-size: 11px; color: {C.DANGER_DARK}; background-color: {C.DANGER_BG};"
            "border-radius: 6px; padding: 4px 10px;"
        )
        self.status_lbl.setVisible(False)

        right_info = QVBoxLayout()
        right_info.setSpacing(0)
        self.admin_name_lbl = QLabel(self.username)
        self.admin_name_lbl.setAlignment(Qt.AlignRight)
        self.admin_name_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {C.TEXT_PRIMARY};")
        self.clock_lbl = QLabel()
        self.clock_lbl.setAlignment(Qt.AlignRight)
        self.clock_lbl.setStyleSheet(f"font-size: 11px; color: {C.TEXT_MUTED_STRONG};")  # warna sebelumnya #94A3B8, kontras 2.56:1 (gagal WCAG AA)
        right_info.addWidget(self.admin_name_lbl)
        right_info.addWidget(self.clock_lbl)

        tb_lay.addWidget(self.page_header)
        tb_lay.addStretch()
        tb_lay.addWidget(self.status_lbl)
        tb_lay.addSpacing(15)
        tb_lay.addLayout(right_info)
        right_col.addWidget(topbar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {C.SURFACE_ALT};")

        self.dashboard_page       = self._build_dashboard_page()
        self.murid_page           = DataMuridWidget()
        self.guru_page            = DataGuruWidget()
        self.absensi_page         = AbsensiWidget()
        self.LaporanKeuangan_page = LaporanKeuanganWidget()
        self.bayar_page           = PembayaranMainWidget()

        pages = [self.dashboard_page, self.murid_page, self.guru_page,
                 self.absensi_page, self.bayar_page, self.LaporanKeuangan_page]

        for p in pages:
            self.stack.addWidget(p)

        for i, (btn, page) in enumerate(zip(self._menu_buttons, pages)):
            btn.clicked.connect(lambda _, idx=i, pg=page: self._switch_page(idx, pg))

        # ── SHORTCUT ALT+1..6 ────────────────────────────────────────
        for i, page in enumerate(pages):
            sc = QShortcut(QKeySequence(f"Alt+{i + 1}"), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(lambda idx=i, pg=page: self._switch_page(idx, pg))

        # ── UKURAN TEKS: CTRL+=/-/0 ──────────────────────────────────
        self._text_scale = TextScaleController.instance()
        self._text_scale.scaleChanged.connect(self._apply_text_scale)

        right_col.addWidget(self.stack)
        root.addLayout(right_col)

        self._tick()
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)

        self._switch_page(0, self.dashboard_page)
        # Load data dashboard pertama kali setelah UI siap
        self._refresh_dashboard()

    def _build_dashboard_page(self):
        page = QWidget()
        page.setStyleSheet(f"background-color: {C.SURFACE_ALT};")
        v = QVBoxLayout(page)
        v.setContentsMargins(35, 30, 35, 30)
        v.setSpacing(25)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(20)

        card_murid,  self._stat_val_murid  = self._stat_card("MURID",           "-", "Total Aktif",    lambda: self._switch_page(1, self.murid_page))
        card_guru,   self._stat_val_guru   = self._stat_card("GURU",            "-", "Total Pengajar", lambda: self._switch_page(2, self.guru_page))
        card_jadwal, self._stat_val_jadwal = self._stat_card("ABSENSI HARI INI", "-", "Sesi Kelas",     lambda: self._switch_page(3, self.absensi_page))
        stats_row.addWidget(card_murid)
        stats_row.addWidget(card_guru)
        stats_row.addWidget(card_jadwal)

        # Quick-register card
        reg = QFrame()
        reg.setStyleSheet(f"QFrame {{ background-color: {C.TEXT_PRIMARY}; border: none; border-radius: 14px; }}")
        reg.setFixedWidth(230)
        rv = QVBoxLayout(reg)
        rv.setContentsMargins(22, 22, 22, 22)
        rv.setSpacing(14)
        t = QLabel("TAMBAH MURID & LES")
        t.setWordWrap(True)
        t.setStyleSheet("color: white; font-weight: bold; font-size: 15px; background: transparent;")
        ab = QPushButton("+ TAMBAH MURID")
        ab.setCursor(Qt.PointingHandCursor)
        ab.setFixedHeight(38)
        ab.setStyleSheet(primary_button_style())
        ab.clicked.connect(lambda: TambahMuridDialog(self).exec_())
        aj = QPushButton("+  Tambah Les Baru")
        aj.setCursor(Qt.PointingHandCursor)
        aj.setFixedHeight(38)
        aj.setStyleSheet(primary_button_style())
        aj.clicked.connect(self._open_tambah_jadwal)
        rv.addWidget(t); rv.addWidget(ab); rv.addWidget(aj)
        stats_row.addWidget(reg)
        v.addLayout(stats_row)

        # Bottom row
        bot = QHBoxLayout()
        bot.setSpacing(25)
        bot.setAlignment(Qt.AlignTop)

        # ── TODAY SCHEDULE ────────────────────────────────────────────────────
        today_box = QFrame()
        today_box.setStyleSheet("QFrame { background-color: white; border: none; }")
        today_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tv = QVBoxLayout(today_box)
        tv.setContentsMargins(22, 20, 8, 20)
        tv.setSpacing(12)
        tv.setAlignment(Qt.AlignTop)

        th = QHBoxLayout()
        th.setSpacing(10)

        # ── Tab pill "Absensi Hari Ini" / "Reminder Besok" ──────────────────
        tab_pill = QFrame()
        tab_pill.setStyleSheet(f"QFrame {{ background-color:{C.SURFACE_ALT}; border-radius:10px; }}")
        tab_pill_lay = QHBoxLayout(tab_pill)
        tab_pill_lay.setContentsMargins(3, 3, 3, 3)
        tab_pill_lay.setSpacing(2)

        def _make_tab_btn(text):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(30)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color:{C.TEXT_PRIMARY};
                    border:none; border-radius:8px; padding:0 14px;
                    font-size:11px; font-weight:bold;
                }}
                QPushButton:checked {{ background-color:{C.SURFACE}; color:{C.ACCENT_DARK}; }}
            """)
            return b

        self._tab_btn_absensi = _make_tab_btn("Absensi Hari Ini")
        self._tab_btn_reminder = _make_tab_btn("Reminder Besok")
        self._tab_btn_absensi.setChecked(True)

        tab_group = QButtonGroup(self)
        tab_group.setExclusive(True)
        tab_group.addButton(self._tab_btn_absensi)
        tab_group.addButton(self._tab_btn_reminder)
        self._today_tab_group = tab_group  # simpan referensi supaya tidak di-GC

        tab_pill_lay.addWidget(self._tab_btn_absensi)
        tab_pill_lay.addWidget(self._tab_btn_reminder)
        th.addWidget(tab_pill)
        th.addStretch()

        self._today_date_lbl = QLabel(datetime.now().strftime("%d %b %Y").upper())
        self._today_date_lbl.setStyleSheet(f"background-color:{C.SURFACE_ALT}; color:{C.TEXT_MUTED}; padding:4px 12px; border-radius:10px; font-size:11px; font-weight:600;")
        th.addWidget(self._today_date_lbl)
        # tanggal ditampilkan mengikuti tab aktif (hari ini / besok) — diisi oleh _refresh_dashboard
        self._date_label_hari_ini = ""
        self._date_label_besok = ""

        btn_menu = QPushButton()
        btn_menu.setIcon(svg_icon("more-vertical", C.TEXT_MUTED, 16))
        btn_menu.setCursor(Qt.PointingHandCursor)
        btn_menu.setFixedSize(28, 28)
        btn_menu.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background-color:{C.SURFACE_ALT}; }}
        """)
        menu = QMenu(btn_menu)
        menu.addAction("Muat Ulang", self._refresh_dashboard)
        btn_menu.setMenu(menu)
        th.addWidget(btn_menu)
        tv.addLayout(th)

        # ── Konten tab: 2 halaman (Absensi Hari Ini / Reminder Besok) ──────
        self._today_stack = QStackedWidget()

        # -- Halaman 1: Absensi Hari Ini (perilaku lama) --
        today_scroll = QScrollArea()
        today_scroll.setWidgetResizable(True)
        today_scroll.setStyleSheet(f"""
            QScrollArea{{border:none;background:transparent;}}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        self._today_content = QWidget()
        self._today_content.setStyleSheet("background:transparent;")
        self._today_lay = QVBoxLayout(self._today_content)
        self._today_lay.setContentsMargins(0, 0, 0, 0)
        self._today_lay.setSpacing(0)
        today_scroll.setWidget(self._today_content)
        self._today_stack.addWidget(today_scroll)

        # -- Halaman 2: Reminder Besok (kartu Salin Pengingat + Reschedule) --
        reminder_scroll = QScrollArea()
        reminder_scroll.setWidgetResizable(True)
        reminder_scroll.setStyleSheet(f"""
            QScrollArea{{border:none;background:transparent;}}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        self._reminder_content = QWidget()
        self._reminder_content.setStyleSheet("background:transparent;")
        self._reminder_lay = QVBoxLayout(self._reminder_content)
        self._reminder_lay.setContentsMargins(0, 0, 0, 0)
        self._reminder_lay.setSpacing(0)
        reminder_scroll.setWidget(self._reminder_content)
        self._today_stack.addWidget(reminder_scroll)

        tv.addWidget(self._today_stack)

        self._tab_btn_absensi.clicked.connect(lambda: (self._today_stack.setCurrentIndex(0), self._update_date_badge()))
        self._tab_btn_reminder.clicked.connect(lambda: (self._today_stack.setCurrentIndex(1), self._update_date_badge()))

        self._today_info = QLabel("")
        self._today_info.setStyleSheet(f"font-size:11px;color:{C.TEXT_MUTED_STRONG};")  # warna sebelumnya #94A3B8, kontras 2.56:1 (gagal WCAG AA)
        tv.addWidget(self._today_info)

        bot.addWidget(today_box, 2)

        # ── ABSENSI ADMIN (jam masuk / jam pulang staf admin hari ini) ─────────
        tom_box = QFrame()
        tom_box.setFixedWidth(320)
        tom_box.setStyleSheet("QFrame { background-color: white; border: none; }")
        tom_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        tmv = QVBoxLayout(tom_box)
        tmv.setContentsMargins(18, 20, 18, 20)
        tmv.setSpacing(10)
        tmv.setAlignment(Qt.AlignTop)

        tmh = QHBoxLayout()
        tml = QLabel("Absensi Admin")
        tml.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {C.TEXT_PRIMARY}; background: transparent;")
        tmtambah = QLabel("+ TAMBAH")
        tmtambah.setStyleSheet(f"color: {C.ACCENT_DARK}; font-size: 11px; font-weight: bold; background: transparent;")
        tmtambah.setCursor(Qt.PointingHandCursor)
        tmtambah.setToolTip("Tambah absensi admin manual")
        tmtambah.mousePressEvent = lambda e: self._tambah_absensi_dashboard()
        tmlink = QLabel("LIHAT SEMUA")
        tmlink.setStyleSheet(f"color: {C.ACCENT}; font-size: 11px; font-weight: bold; background: transparent;")
        tmlink.setCursor(Qt.PointingHandCursor)   # "cursor:" bukan properti valid di QSS → pakai setCursor
        tmlink.setToolTip("Buka halaman Absensi lengkap")
        tmlink.mousePressEvent = lambda e: self._switch_page(3, self.absensi_page)  # label berfungsi sebagai tautan
        tmh.addWidget(tml); tmh.addStretch()
        tmh.addWidget(tmtambah); tmh.addSpacing(10); tmh.addWidget(tmlink)
        tmv.addLayout(tmh)

        sub = QLabel("Jam masuk / jam pulang staf admin hari ini")
        sub.setStyleSheet(f"font-size:11px;color:{C.TEXT_MUTED_STRONG};background:transparent;")
        tmv.addWidget(sub)

        # ── Scroll area untuk absensi admin (card-style) ──
        besok_scroll = QScrollArea()
        besok_scroll.setWidgetResizable(True)
        besok_scroll.setStyleSheet(f"""
            QScrollArea{{border:none;background:transparent;}}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        self._besok_content = QWidget()
        self._besok_content.setStyleSheet("background:transparent;")
        self._besok_lay = QVBoxLayout(self._besok_content)
        self._besok_lay.setContentsMargins(0, 0, 0, 0)
        self._besok_lay.setSpacing(0)
        besok_scroll.setWidget(self._besok_content)
        tmv.addWidget(besok_scroll)

        bot.addWidget(tom_box, 1)
        v.addLayout(bot)
        return page

    def _open_tambah_jadwal(self):
        dlg = TambahJadwalDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_dashboard()

    def _refresh_dashboard(self):
        """Reload data absensi murid (hari ini) & absensi admin dari DB,
        render ulang ke panel dashboard."""
        from database import DB

        self.setCursor(Qt.WaitCursor)  # kursor sibuk selama proses memuat data
        try:
            tanggal_hari_ini = datetime.now().strftime("%d-%m-%Y")

            # ── Update stat cards dari DB ──────────────────────────────────────
            try:
                jumlah_murid = DB.fetch_one(
                    "SELECT COUNT(*) FROM murid WHERE status='Aktif'"
                )[0]
                jumlah_guru = DB.fetch_one(
                    "SELECT COUNT(*) FROM guru WHERE status='Aktif'"
                )[0]
                jumlah_jadwal = DB.fetch_one(
                    "SELECT COUNT(*) FROM jadwal_sesi WHERE tanggal=?",
                    (tanggal_hari_ini,)
                )[0]
                self._stat_val_murid.setText(str(jumlah_murid))
                self._stat_val_guru.setText(str(jumlah_guru))
                self._stat_val_jadwal.setText(str(jumlah_jadwal))
                self._show_status("")  # bersihkan pesan error sebelumnya jika berhasil
            except Exception as e:
                self._show_status("Gagal memuat data ringkasan. Coba muat ulang halaman.")
                print(f"[Dashboard] Gagal load stat cards: {e}")

            self._render_absensi(tanggal_hari_ini)
        finally:
            self.unsetCursor()

    def _update_date_badge(self):
        """Sinkronkan label tanggal di header panel dengan tab yang aktif —
        tanggal hari ini saat tab 'Absensi Hari Ini', tanggal besok saat
        tab 'Reminder Besok' aktif."""
        idx = self._today_stack.currentIndex()
        text = self._date_label_besok if idx == 1 else self._date_label_hari_ini
        self._today_date_lbl.setText(text or datetime.now().strftime("%d %b %Y").upper())

    def _show_status(self, message: str):
        """Tampilkan/sembunyikan pesan status di topbar agar user tahu kondisi sistem."""
        self.status_lbl.setText(message)
        self.status_lbl.setVisible(bool(message))

    def _render_absensi(self, tanggal_hari_ini):

        # ── Absensi Murid: Hari Ini ─────────────────────────────────────────────
        while self._today_lay.count():
            item = self._today_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sesi_hari_ini = _load_jadwal_tanggal(tanggal_hari_ini)

        if not sesi_hari_ini:
            lbl = QLabel("Tidak ada sesi kelas hari ini.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color:{C.TEXT_MUTED};font-size:12px;padding:24px;")  # kontras ditingkatkan (WCAG AA)
            self._today_lay.addWidget(lbl)
        else:
            render_absensi_card_list(
                sesi_hari_ini, self._today_lay,
                refresh_callback=self._refresh_dashboard,
                parent_widget=self
            )
        self._today_lay.addStretch()
        self._today_info.setText(f"Menampilkan {len(sesi_hari_ini)} sesi hari ini")

        # ── Reminder Besok: sesi H-1 dengan tombol Salin Pengingat/Reschedule ──
        while self._reminder_lay.count():
            item = self._reminder_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tanggal_dt = datetime.strptime(tanggal_hari_ini, "%d-%m-%Y")
        tanggal_besok = (tanggal_dt + timedelta(days=1)).strftime("%d-%m-%Y")
        sesi_besok = _load_jadwal_tanggal(tanggal_besok)

        # ── Sinkronkan badge tanggal di header dengan tab yang aktif ──────
        self._date_label_hari_ini = tanggal_dt.strftime("%d %b %Y").upper()
        besok_dt = tanggal_dt + timedelta(days=1)
        self._date_label_besok = besok_dt.strftime("%d %b %Y").upper()
        self._update_date_badge()

        if not sesi_besok:
            lbl = QLabel("Tidak ada sesi kelas besok.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color:{C.TEXT_MUTED};font-size:12px;padding:24px;")
            self._reminder_lay.addWidget(lbl)
        else:
            render_reminder_besok_card_list(
                sesi_besok, self._reminder_lay,
                refresh_callback=self._refresh_dashboard,
                parent_widget=self
            )
        self._reminder_lay.addStretch()

        # ── Absensi Admin: jam masuk/pulang staf hari ini ───────────────────────
        while self._besok_lay.count():
            item = self._besok_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            from database import DB
            kehadiran_hari_ini = [
                r for r in DB.get_kehadiran_admin("all") if r["tanggal"] == tanggal_hari_ini
            ]
        except Exception:
            kehadiran_hari_ini = []

        if not kehadiran_hari_ini:
            lbl = QLabel("Belum ada admin yang absen hari ini.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color:{C.TEXT_MUTED};font-size:12px;padding:24px;")  # kontras ditingkatkan (WCAG AA)
            self._besok_lay.addWidget(lbl)
        else:
            for row in kehadiran_hari_ini:
                self._besok_lay.addWidget(self._build_admin_attendance_card(row))
        self._besok_lay.addStretch()

    def _build_admin_attendance_card(self, row):
        """Card satu baris kehadiran admin (jam masuk/pulang) hari ini."""
        c = QFrame()
        c.setStyleSheet(
            "QFrame { background-color: white; border: none;"
            "border-radius: 10px; margin-bottom: 4px; }"
        )
        cv = QVBoxLayout(c)
        cv.setContentsMargins(14, 12, 14, 12)
        cv.setSpacing(3)

        top_row = QHBoxLayout()
        nl = QLabel(row["nama_admin"])
        nl.setStyleSheet(f"font-weight:bold;color:{C.TEXT_PRIMARY};font-size:13px;background:transparent;border:none;")
        sudah_pulang = bool(row["jam_pulang"])
        st_bg, st_fg, st_label = (f"{C.SUCCESS_BG_STRONG}", f"{C.SUCCESS_DARK}", "Sudah Pulang") if sudah_pulang \
            else (f"{C.ACCENT_BG}", f"{C.ACCENT_DARKER}", "Masih Bertugas")
        st_lbl = QLabel(st_label)
        st_lbl.setStyleSheet(
            f"background:{st_bg};color:{st_fg};border-radius:5px;"
            "font-size:9px;font-weight:bold;padding:2px 8px;border:none;")
        top_row.addWidget(nl)
        top_row.addStretch()
        top_row.addWidget(st_lbl)
        cv.addLayout(top_row)

        dl = QLabel(f"Masuk  {row['jam_masuk'] or '—'}    |    Pulang  {row['jam_pulang'] or '—'}")
        dl.setStyleSheet(f"color:{C.TEXT_MUTED_STRONG};font-size:10px;background:transparent;border:none;")  # warna sebelumnya #94A3B8 (kontras kurang)
        cv.addWidget(dl)

        # ── Aksi: Edit / Hapus — selaras dengan tabel Absensi Admin lengkap ──
        aksi_row = QHBoxLayout()
        aksi_row.setSpacing(10)
        aksi_row.addStretch()
        btn_edit = QLabel("Edit")
        btn_edit.setStyleSheet(f"color:{C.ACCENT_DARK};font-size:10px;font-weight:600;"
                                "text-decoration:underline;background:transparent;border:none;")
        btn_edit.setCursor(Qt.PointingHandCursor)
        row_id = row["id"]
        btn_edit.mousePressEvent = lambda e, rid=row_id: self._edit_absensi_dashboard(rid)
        btn_hapus = QLabel("Hapus")
        btn_hapus.setStyleSheet(f"color:{C.DANGER_DARK};font-size:10px;font-weight:600;"
                                 "text-decoration:underline;background:transparent;border:none;")
        btn_hapus.setCursor(Qt.PointingHandCursor)
        btn_hapus.mousePressEvent = lambda e, rid=row_id: self._hapus_absensi_dashboard(rid)
        aksi_row.addWidget(btn_edit)
        aksi_row.addWidget(btn_hapus)
        cv.addLayout(aksi_row)

        return c

    def _tambah_absensi_dashboard(self):
        from database import DB
        if not DB.get_admin_aktif():
            show_toast(self, "Perhatian", "Belum ada admin aktif. Tambahkan admin terlebih dahulu.", "warning")
            return
        dlg = FormAbsensiAdminDialog(self, existing=None, on_saved=self._refresh_dashboard)
        dlg.exec_()

    def _edit_absensi_dashboard(self, kehadiran_id):
        from database import DB
        r = DB.get_kehadiran_admin_by_id(kehadiran_id)
        if not r:
            return
        dlg = FormAbsensiAdminDialog(self, existing=r, on_saved=self._refresh_dashboard)
        dlg.exec_()

    def _hapus_absensi_dashboard(self, kehadiran_id):
        from database import DB
        jawab = confirm_action(
            self,
            "Hapus Absensi",
            "Hapus baris kehadiran admin ini? Tindakan ini tidak bisa dibatalkan.",
            yes_text="Ya, Hapus",
            no_text="Batal"
        )
        if jawab:
            DB.hapus_kehadiran_admin(kehadiran_id)
            self._refresh_dashboard()
            show_toast(self, "Berhasil", "Data kehadiran admin dihapus.", "success")

    def _stat_card(self, title, value, sub, on_click=None):
        f = QFrame()
        f.setFixedHeight(130)
        f.setObjectName("dashStatCard")
        f.setStyleSheet(f"""
            QFrame#dashStatCard {{
                background-color: white;
                border: 1px solid {C.BORDER};
                border-radius: 12px;
            }}
            QFrame#dashStatCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        if on_click:
            f.setCursor(Qt.PointingHandCursor)
            f.setToolTip(f"Klik untuk membuka halaman {title.title()}")
            f.setAccessibleName(f"Kartu statistik {title}")
            f.mousePressEvent  = lambda e, fn=on_click: fn()
            f.enterEvent       = lambda e: f.setStyleSheet(f"""
                QFrame#dashStatCard {{
                    background-color: {C.ACCENT_BG};
                    border: 2px solid {C.ACCENT_BORDER};
                    border-radius: 12px;
                }}
                QFrame#dashStatCard QLabel {{ border: none; background: transparent; }}
            """)
            f.leaveEvent       = lambda e: f.setStyleSheet(f"""
                QFrame#dashStatCard {{
                    background-color: white;
                    border: 1px solid {C.BORDER};
                    border-radius: 12px;
                }}
                QFrame#dashStatCard QLabel {{ border: none; background: transparent; }}
            """)
        v = QVBoxLayout(f)
        v.setContentsMargins(20, 15, 20, 15)
        t = QLabel(title)
        t.setStyleSheet(f"color: {C.TEXT_MUTED_STRONG}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")  # warna sebelumnya #94A3B8 (kontras kurang)
        vl = QLabel(value)
        vl.setStyleSheet(f"color: {C.TEXT_PRIMARY}; font-size: 34px; font-weight: bold;")
        sl = QLabel(sub)
        sl.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 12px;")

        if on_click:
            hint = QWidget()
            hint.setStyleSheet("background: transparent;")
            hint_lay = QHBoxLayout(hint)
            hint_lay.setContentsMargins(0, 0, 0, 0)
            hint_lay.setSpacing(3)
            hint_txt = QLabel("Klik untuk lihat")
            hint_txt.setStyleSheet(f"color: {C.ACCENT_DARK}; font-size: 10px; font-weight: 600;")  # warna sebelumnya #BFDBFE, kontras 1.42:1 (gagal total)
            hint_icon = QLabel()
            hint_icon.setPixmap(svg_pixmap("arrow-right", C.ACCENT_DARK, 10))
            hint_lay.addWidget(hint_txt)
            hint_lay.addWidget(hint_icon)
            hint_lay.addStretch()
            v.addWidget(t); v.addWidget(vl); v.addWidget(sl); v.addWidget(hint)
        else:
            v.addWidget(t); v.addWidget(vl); v.addWidget(sl)
        return f, vl

    def _apply_text_scale(self, factor: float):
        """Terapkan ulang ukuran font sidebar & tombol keluar saat skala teks berubah."""
        active_idx = self._menu_buttons.index(self._active_btn) if getattr(self, "_active_btn", None) in self._menu_buttons else 0
        for i, btn in enumerate(self._menu_buttons):
            base = MENU_ACTIVE if i == active_idx else MENU_NORMAL
            btn.setStyleSheet(scale_stylesheet(base, factor))
            btn.setIcon(sidebar_icon(self._menu_icon_names[i], active=(i == active_idx)))
        self.btn_logout.setStyleSheet(scale_stylesheet(LOGOUT_STYLE, factor))

    def _switch_page(self, idx, page):
        self.stack.setCurrentWidget(page)
        self._active_btn = self._menu_buttons[idx]
        for i, btn in enumerate(self._menu_buttons):
            btn.setStyleSheet(scale_stylesheet(
                MENU_ACTIVE if i == idx else MENU_NORMAL, self._text_scale.factor
            ))
            btn.setIcon(sidebar_icon(self._menu_icon_names[i], active=(i == idx)))
        #  breadcrumb topbar selalu ikut halaman aktif (wayfinding)
        section = _MENU_SECTIONS[idx] if idx < len(_MENU_SECTIONS) else ""
        self.page_header.set_page("MELODY VIOLIN SCHOOL", section)
        if idx == 0:
            self._refresh_dashboard()

    def reset_to_dashboard(self):
        self._switch_page(0, self.dashboard_page)

    def update_username(self, username):
        self.username = username
        self.admin_name_lbl.setText(username)


    def set_current_user(self, username: str):
        """Teruskan nama staff yang login ke PembayaranMainWidget."""
        self.bayar_page.set_current_user(username)

    def logout(self):
        #  error prevention — minta konfirmasi sebelum aksi yang
        #    tidak bisa "dibatalkan" (keluar sistem) ──
        jawab = confirm_action(
            self,
            "Konfirmasi Keluar",
            "Apakah Anda yakin ingin keluar dari sistem?",
            yes_text="Ya",
            no_text="Tidak"
        )
        if jawab and self.switch_to_login:
            self.switch_to_login()

    def _tick(self):
        now = datetime.now()
        days_id = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
        day = days_id[now.weekday()]
        self.clock_lbl.setText(f"{day}, {now.strftime('%d %B %Y')}  |  {now.strftime('%H:%M')} WIB")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    w = DashboardWindow()
    install_text_scale_shortcuts(w)  # hanya untuk mode standalone/testing
    w.setWindowTitle("Dashboard - Melody Violin School")
    w.resize(1280, 800)
    w.show()
    sys.exit(app.exec_())