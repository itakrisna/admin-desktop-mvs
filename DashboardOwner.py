import sys
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QFrame, QStackedWidget,
    QApplication, QShortcut
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QKeySequence

from database import DB
from DataAdmin import DataAdminWidget
from LaporanKeuangan import LaporanKeuanganWidget
from Pengaturan import PengaturanWidget
from theme import C, sidebar_styles, sidebar_icon, PageHeader, TextScaleController, scale_stylesheet, install_text_scale_shortcuts, svg_pixmap  # noqa: F401 (install_text_scale_shortcuts dipakai di blok __main__)
from toast_notification import confirm_action

SIDEBAR_W = 200

# Konsistensi semua warna diambil dari theme.py 
CLR_ACCENT   = C.ACCENT
CLR_DANGER   = C.DANGER
CLR_SUCCESS  = C.SUCCESS
CLR_WARNING  = C.WARNING

CLR_TEXT_PRIMARY   = C.TEXT_PRIMARY
CLR_TEXT_SECONDARY = C.TEXT_MUTED
CLR_TEXT_MUTED     = C.TEXT_FAINT
CLR_SURFACE        = C.SURFACE
CLR_SURFACE_ALT    = C.SURFACE_ALT
CLR_BORDER         = C.BORDER

SIDEBAR_STYLE, MENU_ACTIVE, MENU_NORMAL, LOGOUT_STYLE = sidebar_styles(
    accent=CLR_ACCENT, accent_bg=f"{C.ACCENT_BG}"
)

_MENU_SECTIONS = ["Dashboard", "Laporan Keuangan", "Data Admin", "Pengaturan"]


class OwnerDashboard(QWidget):
    def __init__(self, logout_callback=None):
        super().__init__()
        self.logout_callback = logout_callback
        self.username = "Owner MVS"
        self._menu_buttons = []
        self.init_ui()

    def init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── SIDEBAR ───────────────────────────────────────────────────
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setStyleSheet(SIDEBAR_STYLE)
        self.sidebar.setFixedWidth(SIDEBAR_W)
        side_v = QVBoxLayout(self.sidebar)
        side_v.setContentsMargins(0, 0, 0, 0)
        side_v.setSpacing(0)

        logo_frame = QFrame()
        logo_frame.setStyleSheet(f"background-color: #FFFFFF; border-bottom: 1px solid {C.SURFACE_HOVER};")
        logo_frame.setFixedHeight(70)
        logo_lay = QVBoxLayout(logo_frame)
        logo_lay.setContentsMargins(20, 0, 20, 0)
        logo_lbl = QLabel("OWNER MVS")
        logo_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {C.TEXT_PRIMARY}; letter-spacing: 1px;")
        logo_lay.addWidget(logo_lbl)
        side_v.addWidget(logo_frame)

        side_v.addSpacing(10)

        owner_menu_labels = ["Dashboard", "Laporan Keuangan", "Data Admin", "Pengaturan"]
        owner_menu_icon_names = ["dashboard", "laporan", "admin", "pengaturan"]
        self._menu_icon_names = owner_menu_icon_names
        for i, label in enumerate(owner_menu_labels):
            btn = QPushButton(f"  {label}")
            btn.setIcon(sidebar_icon(owner_menu_icon_names[i], active=(i == 0)))
            btn.setIconSize(QSize(20, 20))
            btn.setFixedHeight(48)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(MENU_NORMAL)
            # Tooltip & aksesibilitas keyboard, konsisten dengan DashboardAdmin.py
            btn.setToolTip(f"Buka halaman {label}  (Alt+{i + 1})")
            btn.setAccessibleName(f"Menu {label}")
            btn.setFocusPolicy(Qt.StrongFocus)
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
        self.btn_logout.setFocusPolicy(Qt.StrongFocus)
        self.btn_logout.clicked.connect(self.do_logout)
        side_v.addWidget(self.btn_logout)

        root.addWidget(self.sidebar)

        # ── MAIN RIGHT COLUMN ─────────────────────────────────────────
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)

        topbar = QFrame()
        topbar.setFixedHeight(52)
        topbar.setStyleSheet(f"background-color: white; border-bottom: 1px solid {CLR_BORDER};")
        tb_lay = QHBoxLayout(topbar)
        tb_lay.setContentsMargins(24, 0, 24, 0)

        # Breadcrumb dinamis, konsisten dengan pola di DashboardAdmin.py
        self.page_header = PageHeader("MELODY VIOLIN SCHOOL", "Dashboard")

        right_info = QVBoxLayout()
        right_info.setSpacing(1)
        self.owner_name_lbl = QLabel(self.username)
        self.owner_name_lbl.setAlignment(Qt.AlignRight)
        self.owner_name_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {CLR_TEXT_PRIMARY};")
        self.clock_lbl = QLabel()
        self.clock_lbl.setAlignment(Qt.AlignRight)
        self.clock_lbl.setStyleSheet(f"font-size: 11px; color: {CLR_TEXT_MUTED};")
        right_info.addWidget(self.owner_name_lbl)
        right_info.addWidget(self.clock_lbl)

        tb_lay.addWidget(self.page_header)
        tb_lay.addStretch()
        tb_lay.addLayout(right_info)
        right_col.addWidget(topbar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {C.SURFACE_ALT};")

        self.dashboard_page  = self._build_dashboard_page()
        self.admin_page      = DataAdminWidget()
        self.laporan_page    = LaporanKeuanganWidget()
        self.pengaturan_page = PengaturanWidget()

        pages = [self.dashboard_page, self.laporan_page,
                 self.admin_page, self.pengaturan_page]
        for p in pages:
            self.stack.addWidget(p)
        for i, (btn, page) in enumerate(zip(self._menu_buttons, pages)):
            btn.clicked.connect(lambda _, idx=i, pg=page: self._switch_page(idx, pg))

        # ── SHORTCUT ALT+1..4 (ambil halaman terkini, bukan referensi lama) ──
        self._page_getters = [
            lambda: self.dashboard_page, lambda: self.laporan_page,
            lambda: self.admin_page, lambda: self.pengaturan_page,
        ]
        for i in range(len(pages)):
            sc = QShortcut(QKeySequence(f"Alt+{i + 1}"), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(lambda idx=i: self._switch_page(idx, self._page_getters[idx]()))

        # ── UKURAN TEKS: shortcut didaftarkan sekali di MainApp, di sini ambil singleton saja ──
        self._text_scale = TextScaleController.instance()
        self._text_scale.scaleChanged.connect(self._apply_text_scale)

        right_col.addWidget(self.stack)
        root.addLayout(right_col)

        self._tick()
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)

        self._switch_page(0, self.dashboard_page)

    def _load_dashboard_data(self):
        now = datetime.now()
        bulan = now.month
        tahun = now.year

        # ── Stat cards ──
        total_admin = DB.fetch_one(
            "SELECT COUNT(*) AS n FROM admin WHERE status='Aktif'"
        )["n"]
        total_guru = DB.fetch_one(
            "SELECT COUNT(*) AS n FROM guru WHERE status='Aktif'"
        )["n"]
        total_murid = DB.fetch_one(
            "SELECT COUNT(*) AS n FROM murid WHERE status='Aktif'"
        )["n"]

        # ── Keuangan bulan ini ──
        transaksi = DB.get_transaksi_bulan(bulan, tahun)
        pemasukan = sum(r["nominal"] for r in transaksi if r["jenis"] == "Debit")
        pengeluaran = sum(r["nominal"] for r in transaksi if r["jenis"] == "Kredit")
        laba = pemasukan - pengeluaran

        # ── Log aktivitas: 5 transaksi terbaru ──
        log_rows = DB.fetch_all("""
            SELECT keterangan, tanggal, jenis, nominal
            FROM transaksi_keuangan
            ORDER BY created_at DESC, id DESC
            LIMIT 5
        """)

        return {
            "total_admin": total_admin,
            "total_guru": total_guru,
            "total_murid": total_murid,
            "pemasukan": pemasukan,
            "pengeluaran": pengeluaran,
            "laba": laba,
            "log": log_rows,
            "bulan_label": now.strftime("%B %Y"),
        }

    def _build_dashboard_page(self):
        page = QWidget()
        page.setStyleSheet(f"background-color: {CLR_SURFACE_ALT};")
        v = QVBoxLayout(page)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(14)

        data = self._load_dashboard_data()

        def fmt_rp(n):
            return f"Rp {n:,.0f}".replace(",", ".")

        # ── Section label helper ──────────────────────────────────────
        def section_label(text):
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(
                f"font-size: 10px; font-weight: bold; color: {CLR_TEXT_MUTED}; "
                f"letter-spacing: 0.8px;"
            )
            return lbl

        # ── RINGKASAN STAF ────────────────────────────────────────────
        v.addWidget(section_label("Ringkasan Staf"))

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(self._stat_card(
            "Admin aktif", str(data["total_admin"]), "Staf operasional",
            value_color=CLR_ACCENT))
        row1.addWidget(self._stat_card(
            "Guru aktif", str(data["total_guru"]), "Instruktur terdaftar",
            value_color=CLR_TEXT_PRIMARY))
        row1.addWidget(self._stat_card(
            "Murid aktif", str(data["total_murid"]), f"Per {data['bulan_label']}",
            value_color=CLR_SUCCESS))
        v.addLayout(row1)

        # ── KEUANGAN BULAN INI ────────────────────────────────────────
        v.addWidget(section_label(f"Keuangan Bulan Ini — {data['bulan_label']}"))

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(self._keu_card(
            "Pemasukan", fmt_rp(data["pemasukan"]),
            "Pembayaran les & pendaftaran",
            CLR_ACCENT, icon="arrow-down"))
        row2.addWidget(self._keu_card(
            "Pengeluaran", fmt_rp(data["pengeluaran"]),
            "Gaji & operasional",
            CLR_DANGER, icon="arrow-up"))
        row2.addWidget(self._keu_card(
            "Laba bersih", fmt_rp(data["laba"]),
            "Net profit bulan ini",
            CLR_SUCCESS, icon="equals"))
        v.addLayout(row2)

        # ── LOG AKTIVITAS ─────────────────────────────────────────────
        log_box = QFrame()
        log_box.setStyleSheet(f"""
            QFrame {{ background-color: white; border-radius: 10px;
                      border: 1px solid {CLR_BORDER}; }}
        """)
        lv = QVBoxLayout(log_box)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        log_header = QFrame()
        log_header.setStyleSheet(
            f"background: transparent; border-bottom: 1px solid {CLR_BORDER}; "
            f"border-radius: 0px;"
        )
        lh_lay = QHBoxLayout(log_header)
        lh_lay.setContentsMargins(14, 10, 14, 10)
        ll = QLabel("Log transaksi terbaru")
        ll.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {CLR_TEXT_PRIMARY}; border: none;")
        lh_lay.addWidget(ll)
        lh_lay.addStretch()
        lv.addWidget(log_header)

        if data["log"]:
            for r in data["log"]:
                ket   = r["keterangan"].replace("[LES]", "[PEMBAYARAN LES]")
                tgl   = r["tanggal"]
                jenis = r["jenis"]
                is_debit = (jenis == "Debit")

                row_h = QWidget()
                row_h.setStyleSheet(
                    "QWidget { background: transparent; border: none; }"
                    f"QWidget:hover {{ background-color: {C.SURFACE_ALT}; }}"
                )
                rh_lay = QHBoxLayout(row_h)
                rh_lay.setContentsMargins(14, 8, 14, 8)
                rh_lay.setSpacing(10)

                # Titik warna semantik
                dot = QLabel("●")
                dot_color = CLR_SUCCESS if is_debit else CLR_DANGER
                dot.setStyleSheet(f"color: {dot_color}; font-size: 10px; border: none;")
                dot.setFixedWidth(12)

                # Info kiri
                info_col = QVBoxLayout()
                info_col.setSpacing(1)
                desc = QLabel(ket)
                desc.setStyleSheet(f"color: {CLR_TEXT_PRIMARY}; font-size: 12px; border: none;")
                t = QLabel(tgl)
                t.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 10px; border: none;")
                info_col.addWidget(desc)
                info_col.addWidget(t)

                # Nominal kanan
                amount_color = CLR_SUCCESS if is_debit else CLR_DANGER
                amount_prefix = "+" if is_debit else "−"
                nominal = r["nominal"]
                amount_lbl = QLabel(f"{amount_prefix} {fmt_rp(nominal)}")
                amount_lbl.setStyleSheet(f"color: {amount_color}; font-size: 12px; font-weight: bold; border: none;")
                amount_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

                rh_lay.addWidget(dot)
                rh_lay.addLayout(info_col, 1)
                rh_lay.addWidget(amount_lbl)
                lv.addWidget(row_h)
        else:
            empty = QLabel("Belum ada transaksi bulan ini.")
            empty.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 11px; padding: 12px 14px;")
            lv.addWidget(empty)

        lv.addStretch()
        v.addWidget(log_box)
        return page

    def _stat_card(self, title, value, sub, value_color=None, highlight=False):
        if value_color is None:
            value_color = CLR_TEXT_PRIMARY
        f = QFrame()
        f.setFixedHeight(88)
        f.setStyleSheet(f"""
            QFrame {{ background-color: white; border-radius: 10px;
                      border: 1px solid {CLR_BORDER}; }}
            QLabel {{ border: none; background: transparent; }}
        """)
        fl = QVBoxLayout(f)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(3)
        t  = QLabel(title)
        t.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 11px; font-weight: bold;")
        vl = QLabel(value)
        vl.setStyleSheet(f"color: {value_color}; font-size: 26px; font-weight: bold;")
        sl = QLabel(sub)
        sl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 10px;")
        fl.addWidget(t)
        fl.addWidget(vl)
        fl.addWidget(sl)
        return f

    def _keu_card(self, title, value, sub, color, icon="", show_bar=False):
        f = QFrame()
        f.setFixedHeight(82)
        f.setStyleSheet(f"""
            QFrame {{ background-color: white; border-radius: 10px;
                      border: 1px solid {CLR_BORDER}; }}
            QLabel {{ border: none; background: transparent; }}
        """)
        fl = QVBoxLayout(f)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(3)
        # Label dengan ikon tren kecil di depan (SVG, bukan karakter unicode)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)
        if icon:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(svg_pixmap(icon, color, 11))
            top_row.addWidget(icon_lbl)
        t  = QLabel(title)
        t.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 10px; font-weight: bold;")
        top_row.addWidget(t)
        top_row.addStretch()
        vl = QLabel(value)
        vl.setStyleSheet(f"color: {color}; font-size: 17px; font-weight: bold;")
        sl = QLabel(sub)
        sl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 10px;")
        fl.addLayout(top_row)
        fl.addWidget(vl)
        fl.addWidget(sl)
        return f

    def _switch_page(self, idx, page):
        self.stack.setCurrentWidget(page)
        self._active_idx = idx
        factor = self._text_scale.factor if hasattr(self, "_text_scale") else 1.0
        for i, btn in enumerate(self._menu_buttons):
            btn.setStyleSheet(scale_stylesheet(
                MENU_ACTIVE if i == idx else MENU_NORMAL, factor
            ))
            btn.setIcon(sidebar_icon(self._menu_icon_names[i], active=(i == idx)))
        section = _MENU_SECTIONS[idx] if idx < len(_MENU_SECTIONS) else ""
        self.page_header.set_page("MELODY VIOLIN SCHOOL", section)

    def _apply_text_scale(self, factor: float):
        """Terapkan ulang ukuran font sidebar & tombol keluar saat skala teks berubah."""
        idx = getattr(self, "_active_idx", 0)
        for i, btn in enumerate(self._menu_buttons):
            btn.setStyleSheet(scale_stylesheet(
                MENU_ACTIVE if i == idx else MENU_NORMAL, factor
            ))
            btn.setIcon(sidebar_icon(self._menu_icon_names[i], active=(i == idx)))
        self.btn_logout.setStyleSheet(scale_stylesheet(LOGOUT_STYLE, factor))

    def reset_to_dashboard(self):
        self._switch_page(0, self.dashboard_page)

    def update_username(self, username):
        self.username = username
        self.owner_name_lbl.setText(username)

    def refresh_dashboard(self):
        """Rebuild halaman dashboard dengan data terbaru dari database."""
        old_page = self.dashboard_page
        self.dashboard_page = self._build_dashboard_page()
        self.stack.insertWidget(0, self.dashboard_page)
        self.stack.removeWidget(old_page)
        old_page.deleteLater()
        # Reconnect tombol Dashboard
        self._menu_buttons[0].clicked.disconnect()
        self._menu_buttons[0].clicked.connect(
            lambda: self._switch_page(0, self.dashboard_page)
        )
        self._switch_page(0, self.dashboard_page)

    def do_logout(self):
        # error prevention — minta konfirmasi sebelum aksi yang
        #    tidak bisa "dibatalkan" (keluar sistem), sama seperti Dashboard Admin ──
        jawab = confirm_action(
            self,
            "Konfirmasi Keluar",
            "Apakah Anda yakin ingin keluar dari sistem?",
            yes_text="Ya",
            no_text="Tidak"
        )
        if jawab and self.logout_callback:
            self.logout_callback()

    def _tick(self):
        now = datetime.now()
        days_id = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
        self.clock_lbl.setText(
            f"{days_id[now.weekday()]}, {now.strftime('%d %B %Y')}  |  {now.strftime('%H:%M')} WIB"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    w = OwnerDashboard()
    install_text_scale_shortcuts(w)  # hanya untuk mode standalone/testing
    w.setWindowTitle("Dashboard Owner - Melody Violin School")
    w.resize(1280, 800)
    w.show()
    sys.exit(app.exec_())