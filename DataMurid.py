import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit, QDialog,
    QComboBox, QTextEdit, QDateEdit, QRadioButton,
    QButtonGroup, QSpinBox, QScrollArea,
    QCheckBox, QGridLayout
)
from PyQt5.QtCore import Qt, QDate, QRegExp, QObject, QEvent
from PyQt5.QtGui import QFont, QRegExpValidator, QPixmap
from toast_notification import show_toast, confirm_action
from theme import svg_icon, C, action_button_style, primary_button_style, resource_path


#  Font UI lintas-platform ("Segoe UI" tidak ada di macOS/Linux)
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


# Event filter: blokir scroll mouse pada widget tertentu (QDateEdit & QSpinBox)
class _BlockScroll(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)

# Instance tunggal — cukup satu untuk semua widget
_BLOCK_SCROLL = _BlockScroll()


# Stylesheet kalender popup — mencegah tanggal tampil hitam di atas background gelap
_CALENDAR_QSS = f"""
    QCalendarWidget QAbstractItemView {{
        background-color: white;
        color: {C.TEXT_DARKEST};
        selection-background-color: {C.ACCENT};
        selection-color: white;
    }}
    QCalendarWidget QAbstractItemView:disabled {{ color: {C.BORDER_LIGHT}; }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background-color: {C.SURFACE_ALT};
        border-bottom: 1px solid {C.BORDER};
    }}
    QCalendarWidget QToolButton {{
        color: {C.TEXT_SECONDARY}; background: transparent;
        border: none; font-size: 12px; font-weight: 600;
    }}
    QCalendarWidget QToolButton:hover {{ background: {C.BORDER}; border-radius: 4px; }}
    QCalendarWidget QSpinBox {{
        color: {C.TEXT_SECONDARY}; background: white;
        border: 1px solid {C.BORDER_LIGHT}; border-radius: 4px;
    }}
    QCalendarWidget QTableView {{ background-color: white; gridline-color: {C.SURFACE_HOVER}; }}
"""


#  Dialog: Pratinjau Kuitansi
class KuitansiPreviewDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Pratinjau Kuitansi")
        self.setMinimumSize(700, 560)
        self.resize(760, 620)
        self.setStyleSheet(f"background-color: {C.SURFACE_HOVER};")
        self.data = data or {}
        self._build()

    def _build(self):
        import os
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Header bar ──────────────────────────────────────
        hdr_row = QHBoxLayout()
        title = QLabel("Pratinjau Kuitansi")
        title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C.TEXT_PRIMARY};")
        hdr_row.addWidget(title)
        hdr_row.addStretch()
        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ border:none; background:{C.BORDER}; border-radius:6px;
                          color:{C.TEXT_MUTED}; font-size:12px; }}
            QPushButton:hover {{ background:{C.BORDER_STRONG}; }}
        """)
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)
        root.addLayout(hdr_row)

        # ── Scroll area ──────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)

        # ── Kuitansi card (white paper) ──────────────────────
        card = QFrame()
        card.setObjectName("kuitansiCard")
        card.setStyleSheet(f"""
            QFrame#kuitansiCard {{
                background-color: white;
                border-radius: 4px;
                border: 1px solid {C.BORDER_STRONG};
            }}
            QFrame#kuitansiCard QFrame {{ border: none; background: transparent; }}
            QFrame#kuitansiCard QLabel {{ border: none; background: transparent; }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(0)

        # HEADER: Logo | Info Sekolah | KWITANSI
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        # -- Logo -- sejajar (top-aligned) dengan baris nama sekolah di sampingnya
        _LOGO_SIZE = 132
        logo_img_lbl = QLabel()
        logo_img_lbl.setFixedSize(_LOGO_SIZE, _LOGO_SIZE)
        logo_img_lbl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        logo_img_lbl.setStyleSheet("border:none;background:transparent;")
        _logo_path = resource_path("mvs.png")
        if os.path.exists(_logo_path):
            _px = QPixmap(_logo_path).scaled(
                _LOGO_SIZE, _LOGO_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_img_lbl.setPixmap(_px)

        # -- Nama & Info Sekolah --
        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        info_col.setAlignment(Qt.AlignTop)
        lbl_nama = QLabel("MELODY VIOLIN SCHOOL")
        lbl_nama.setStyleSheet(f"font-size:18px;font-weight:900;color:{C.TEXT_DARKEST};letter-spacing:0.5px;")
        lbl_kota = QLabel("YOGYAKARTA")
        lbl_kota.setStyleSheet(f"font-size:12px;font-weight:800;color:{C.DANGER};letter-spacing:0.5px;")
        lbl_alamat = QLabel(
            "Desa Dukuh RT.002, Guwosari, Pajangan, Bantul\n"
            "Daerah Istimewa Yogyakarta"
        )
        lbl_alamat.setStyleSheet(f"font-size:9px;color:{C.TEXT_SECONDARY};")

        # Kontak 2 baris (Hotline+IG / Email+FB), lebar kolom kiri disamakan
        kontak_col = QVBoxLayout()
        kontak_col.setSpacing(4)
        kontak_col.setContentsMargins(0, 6, 0, 0)

        def _kontak_cell(label_text, value_text):
            """Satu sel kontak: label kecil (uppercase) di atas + nilai di bawah, tanpa icon."""
            cell_w = QWidget()
            cell_w.setStyleSheet("background:transparent;")
            text_col = QVBoxLayout(cell_w)
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(1)

            lbl_l = QLabel(label_text.upper())
            lbl_l.setStyleSheet(
                "font-size:7.5px;color:#9CA3AF;font-weight:700;letter-spacing:0.6px;"
            )
            lbl_v = QLabel(value_text)
            lbl_v.setStyleSheet(f"font-size:9px;color:{C.TEXT_SECONDARY};font-weight:500;")
            text_col.addWidget(lbl_l)
            text_col.addWidget(lbl_v)
            return cell_w

        cell_hotline = _kontak_cell("Hotline", "089636833384")
        cell_ig      = _kontak_cell("Instagram", "@melody.violin")
        cell_email   = _kontak_cell("Email", "melodyklasik@gmail.com")
        cell_fb      = _kontak_cell("Facebook", "melody violin school")

        _kontak_col1_w = max(cell_hotline.sizeHint().width(), cell_email.sizeHint().width())
        cell_hotline.setFixedWidth(_kontak_col1_w)
        cell_email.setFixedWidth(_kontak_col1_w)

        row_hotline_ig = QHBoxLayout()
        row_hotline_ig.setSpacing(14)
        row_hotline_ig.addWidget(cell_hotline)
        row_hotline_ig.addWidget(cell_ig)
        row_hotline_ig.addStretch(1)

        row_email_fb = QHBoxLayout()
        row_email_fb.setSpacing(14)
        row_email_fb.addWidget(cell_email)
        row_email_fb.addWidget(cell_fb)
        row_email_fb.addStretch(1)

        kontak_col.addLayout(row_hotline_ig)
        kontak_col.addLayout(row_email_fb)

        info_col.addWidget(lbl_nama)
        info_col.addWidget(lbl_kota)
        info_col.addSpacing(2)
        info_col.addWidget(lbl_alamat)
        info_col.addLayout(kontak_col)

        # -- KWITANSI / RECEIPT di kanan — italic serif dengan garis bawah --
        kwit_col = QVBoxLayout()
        kwit_col.setAlignment(Qt.AlignRight | Qt.AlignTop)
        kwit_col.setSpacing(0)

        # Frame pembungkus untuk garis bawah di bawah RECEIPT
        kwit_frame = QFrame()
        kwit_frame.setStyleSheet(
            f"QFrame {{ border:none; border-bottom:1.5px solid {C.TEXT_DARKEST}; background:transparent; }}"
            "QFrame QLabel { border:none; background:transparent; }"
        )
        kwit_fl = QVBoxLayout(kwit_frame)
        kwit_fl.setContentsMargins(0, 0, 0, 2)
        kwit_fl.setSpacing(0)

        lbl_kwit = QLabel("KWITANSI")
        lbl_kwit.setAlignment(Qt.AlignRight)
        lbl_kwit.setStyleSheet(
            f"font-size:20px;font-weight:400;color:{C.TEXT_DARKEST};letter-spacing:2px;"
            "font-family:'Georgia',serif;font-style:italic;"
        )
        lbl_rcpt = QLabel("RECEIPT")
        lbl_rcpt.setAlignment(Qt.AlignRight)
        lbl_rcpt.setStyleSheet(
            f"font-size:13px;font-weight:400;color:{C.TEXT_SECONDARY};font-style:italic;"
            "font-family:'Georgia',serif;"
        )
        kwit_fl.addWidget(lbl_kwit)
        kwit_fl.addWidget(lbl_rcpt)

        # No. Number
        no_row = QHBoxLayout()
        no_row.setSpacing(0)
        lbl_no_title = QLabel("No.")
        lbl_no_title.setStyleSheet(f"font-size:9px;color:{C.TEXT_SECONDARY};font-style:italic;font-family:'Georgia',serif;")
        lbl_no_val   = QLabel(self.data.get('nomor', ''))
        lbl_no_val.setStyleSheet(f"font-size:9px;color:{C.TEXT_SECONDARY};min-width:100px;border-bottom:1px solid {C.TEXT_SECONDARY};")
        no_row.addStretch()
        no_row.addWidget(lbl_no_title)
        no_row.addSpacing(4)
        no_row.addWidget(lbl_no_val)

        kwit_col.addWidget(kwit_frame)
        kwit_col.addSpacing(6)
        kwit_col.addLayout(no_row)

        header_row.addWidget(logo_img_lbl, 0, Qt.AlignTop)
        header_row.addLayout(info_col, 1)
        header_row.addSpacing(10)
        header_row.addLayout(kwit_col)
        cl.addLayout(header_row)

        # BODY TABLE (border kotak)
        cl.addSpacing(8)

        body_frame = QFrame()
        body_frame.setObjectName("bodyFrame")
        body_frame.setStyleSheet(f"""
            QFrame#bodyFrame {{
                border: 1.5px solid {C.TEXT_SECONDARY};
                border-radius: 0px;
                background: white;
            }}
            QFrame#bodyFrame QLabel {{ border:none; background:transparent; }}
            QFrame#bodyFrame QFrame {{ background:transparent; }}
        """)
        body_vl = QVBoxLayout(body_frame)
        body_vl.setContentsMargins(0, 0, 0, 0)
        body_vl.setSpacing(0)

        def table_row(lbl_id, lbl_en, value, is_last=False):
            """Satu baris tabel kuitansi dengan garis putus-putus di bawah value."""
            outer = QFrame()
            outer.setStyleSheet("border:none;background:transparent;")
            hl = QHBoxLayout(outer)
            hl.setContentsMargins(10, 8, 10, 8)
            hl.setSpacing(6)

            # Kolom label (lebar tetap)
            label_widget = QWidget()
            label_widget.setFixedWidth(130)
            label_widget.setStyleSheet("background:transparent;")
            lv = QVBoxLayout(label_widget)
            lv.setContentsMargins(0, 0, 0, 0)
            lv.setSpacing(1)
            l1 = QLabel(lbl_id)
            l1.setStyleSheet(f"font-size:10px;font-weight:700;color:{C.TEXT_DARKEST};")
            l2 = QLabel(lbl_en)
            l2.setStyleSheet("font-size:9px;color:#6B7280;font-style:italic;")
            lv.addWidget(l1)
            lv.addWidget(l2)

            # Titik dua
            colon = QLabel(" :")
            colon.setStyleSheet(f"font-size:10px;color:{C.TEXT_DARKEST};")
            colon.setFixedWidth(14)

            # Kolom nilai dengan garis bawah putus-putus
            val_container = QWidget()
            val_container.setStyleSheet("background:transparent;")
            vc = QVBoxLayout(val_container)
            vc.setContentsMargins(0, 0, 0, 0)
            vc.setSpacing(0)
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet(f"font-size:13px;color:{C.TEXT_DARKEST};")
            val_lbl.setWordWrap(True)

            # garis putus-putus di bawah nilai
            dotted = QFrame()
            dotted.setFrameShape(QFrame.HLine)
            dotted.setStyleSheet(f"border:none;border-top:1px dashed {C.TEXT_SECONDARY};margin-top:2px;")
            dotted.setFixedHeight(4)

            vc.addWidget(val_lbl)
            vc.addWidget(dotted)

            hl.addWidget(label_widget)
            hl.addWidget(colon)
            hl.addWidget(val_container, 1)

            if not is_last:
                # Garis horizontal pemisah antar baris
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setStyleSheet(f"border:none;border-top:1px solid {C.TEXT_SECONDARY};background:transparent;")
                separator.setFixedHeight(1)
                row_wrapper = QVBoxLayout()
                row_wrapper.setContentsMargins(0,0,0,0)
                row_wrapper.setSpacing(0)
                row_wrapper.addWidget(outer)
                row_wrapper.addWidget(separator)
                w2 = QWidget()
                w2.setStyleSheet("background:transparent;")
                w2.setLayout(row_wrapper)
                return w2
            return outer

        body_vl.addWidget(table_row(
            "Sudah Terima Dari", "Received From",
            self.data.get('nama', ''), is_last=False
        ))
        body_vl.addWidget(table_row(
            "Banyaknya Uang", "Amount Received",
            self.data.get('jumlah', ''), is_last=False
        ))
        body_vl.addWidget(table_row(
            "Untuk Pembayaran", "In Payment Of",
            self.data.get('keterangan', ''), is_last=True
        ))

        cl.addWidget(body_frame)

        # FOOTER: Nominal + Tanggal + TTD
        cl.addSpacing(14)

        foot_row = QHBoxLayout()
        foot_row.setSpacing(0)

        # Nominal kiri
        nom_col = QVBoxLayout()
        nom_col.setSpacing(4)
        nom_col.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Box nominal dengan garis-garis abu samar di belakang angka
        from PyQt5.QtGui import QPainter, QColor, QPen

        # Label nominal — dibuat dulu agar StripedBox bisa baca posisi Rp.
        _lbl_rp  = QLabel("Rp.")
        _lbl_rp.setStyleSheet(
            f"font-size:16px;font-style:italic;color:{C.TEXT_DARKEST};font-weight:600;background:transparent;"
        )
        _lbl_amt = QLabel(self.data.get('nominal_angka', '0'))
        _lbl_amt.setStyleSheet(
            f"font-size:32px;font-weight:900;color:{C.TEXT_DARKEST};letter-spacing:2px;background:transparent;"
        )

        class StripedBox(QFrame):
            """Box Rp. dengan garis horizontal rapat hanya di area angka.
               Persis seperti referensi: garis sejajar, padat, warna abu terang.
            """
            def __init__(self, rp_lbl, parent=None):
                super().__init__(parent)
                self._rp_lbl = rp_lbl
                self.setObjectName("nomBox")
                # border solid di atas-bawah box (kiri kanan tidak pakai border CSS
                # karena akan digambar manual agar bisa dibatasi ke area angka)
                self.setStyleSheet(f"""
                    QFrame#nomBox {{
                        border: 1.5px solid {C.TEXT_SECONDARY};
                        border-radius: 0px;
                        background: white;
                    }}
                    QFrame#nomBox QLabel {{ border:none; background:transparent; }}
                """)

            def paintEvent(self, event):
                super().paintEvent(event)
                painter = QPainter(self)
                painter.setRenderHint(QPainter.Antialiasing, False)

                r = self.rect()

                # Batas kiri garis = tepat setelah label "Rp." + sedikit gap
                rp_right = self._rp_lbl.x() + self._rp_lbl.width() + 4
                x_start  = rp_right
                x_end    = r.right() - 2

                # Garis horizontal rapat (step 5px) warna abu terang
                pen_line = QPen(QColor(170, 170, 170, 150))
                pen_line.setWidth(1)
                painter.setPen(pen_line)
                step = 5
                y = r.top() + step
                while y < r.bottom() - 1:
                    painter.drawLine(x_start, y, x_end, y)
                    y += step

                painter.end()

        nom_box = StripedBox(_lbl_rp)
        nom_bx_l = QHBoxLayout(nom_box)
        nom_bx_l.setContentsMargins(14, 8, 14, 8)
        lbl_rp  = _lbl_rp
        lbl_amt = _lbl_amt
        nom_bx_l.addWidget(lbl_rp)
        nom_bx_l.addSpacing(10)
        nom_bx_l.addWidget(lbl_amt)
        nom_bx_l.addStretch()
        nom_col.addWidget(nom_box)

        # Catatan (opsional, di bawah nominal) — format rapi per baris
        catatan_raw = self.data.get('catatan', '')
        if catatan_raw:
            # Bersihkan header "Catatan" jika sudah ada di data
            lines_raw = catatan_raw.strip().splitlines()
            lines_clean = [l for l in lines_raw if not l.strip().lower().startswith("catatan")]

            nom_col.addSpacing(8)
            lbl_cat_hdr = QLabel("Catatan :")
            lbl_cat_hdr.setStyleSheet(
                f"font-size:9px;color:{C.TEXT_SECONDARY};font-weight:700;"
            )
            nom_col.addWidget(lbl_cat_hdr)

            # Setiap baris ditampilkan sebagai QLabel terpisah agar rapi
            for line in lines_clean:
                txt = line.strip()
                if not txt:
                    nom_col.addSpacing(2)
                    continue
                # Baris yang dimulai '*' atau berisi nomor rekening diberi indentasi
                if txt.startswith("*"):
                    lbl_line = QLabel(txt)
                    lbl_line.setStyleSheet(f"font-size:8.5px;color:{C.TEXT_SECONDARY};")
                elif txt.upper().startswith(("BCA", "BNI", "BRI", "A.N", "AN ")):
                    lbl_line = QLabel("   " + txt)   # indent 3 spasi
                    lbl_line.setStyleSheet(f"font-size:8.5px;color:{C.TEXT_SECONDARY};")
                else:
                    lbl_line = QLabel("   " + txt)
                    lbl_line.setStyleSheet(f"font-size:8.5px;color:{C.TEXT_SECONDARY};")
                lbl_line.setWordWrap(False)
                nom_col.addWidget(lbl_line)

        foot_row.addLayout(nom_col)
        foot_row.addStretch()

        # Tanggal + TTD kanan
        ttd_col = QVBoxLayout()
        ttd_col.setAlignment(Qt.AlignRight | Qt.AlignTop)
        ttd_col.setSpacing(2)

        tanggal = self.data.get('tanggal', '')
        lbl_tgl = QLabel(f"Bantul, {tanggal}")
        lbl_tgl.setAlignment(Qt.AlignRight)
        lbl_tgl.setStyleSheet(f"font-size:10px;color:{C.TEXT_DARKEST};")

        # Tanda tangan (gambar tanda tangan asli). Fallback ke teks kursif
        # jika file ttd_gm.png belum diletakkan di folder yang sama.
        _TTD_H = 60
        lbl_sig = QLabel()
        lbl_sig.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        lbl_sig.setStyleSheet("border:none;background:transparent;")
        _ttd_path = resource_path("ttd_gm.png")
        if os.path.exists(_ttd_path):
            _ttd_px = QPixmap(_ttd_path).scaledToHeight(_TTD_H, Qt.SmoothTransformation)
            lbl_sig.setPixmap(_ttd_px)
            # fixedSize disamakan PERSIS dengan ukuran pixmap (bukan cuma tinggi)
            # supaya tidak ada margin/box yang bentrok dan memotong gambar
            lbl_sig.setFixedSize(_ttd_px.size())
        else:
            lbl_sig.setText(self.data.get('ttd_nama', 'Aris Suryahadi'))
            lbl_sig.setStyleSheet(
                f"font-size:22px;font-style:italic;font-weight:700;color:{C.TEXT_DARKEST};"
                "font-family:'Georgia',serif;"
            )

        lbl_sig_name = QLabel("Aris Suryahadi Yunanto")
        lbl_sig_name.setAlignment(Qt.AlignRight)
        lbl_sig_name.setStyleSheet(f"font-size:10px;color:{C.TEXT_DARKEST};font-weight:600;")
        lbl_sig_jabatan = QLabel("General Manager")
        lbl_sig_jabatan.setAlignment(Qt.AlignRight)
        lbl_sig_jabatan.setStyleSheet(f"font-size:10px;color:{C.TEXT_DARKEST};")
        lbl_sig_sekolah = QLabel("Melody Violin School Yogyakarta")
        lbl_sig_sekolah.setAlignment(Qt.AlignRight)
        lbl_sig_sekolah.setStyleSheet(f"font-size:8.5px;color:{C.TEXT_DARKEST};")

        ttd_col.addWidget(lbl_tgl)
        ttd_col.addSpacing(10)
        ttd_col.addWidget(lbl_sig)
        ttd_col.addSpacing(2)
        ttd_col.addWidget(lbl_sig_name)
        ttd_col.addWidget(lbl_sig_jabatan)
        ttd_col.addWidget(lbl_sig_sekolah)

        foot_row.addLayout(ttd_col)
        cl.addLayout(foot_row)

        scroll.setWidget(card)
        root.addWidget(scroll, 1)
        self._card = card

        # ── Footer buttons ────────────────────────────────────
        footer = QHBoxLayout()
        btn_kembali = QPushButton("\u2190 Kembali")
        btn_kembali.setFixedHeight(36); btn_kembali.setFixedWidth(110)
        btn_kembali.setCursor(Qt.PointingHandCursor)
        btn_kembali.setStyleSheet(f"""
            QPushButton {{ border:1px solid {C.BORDER_LIGHT}; border-radius:7px;
                          background:white; color:{C.TEXT_SECONDARY}; font-size:13px; }}
            QPushButton:hover {{ background:{C.SURFACE_SUBTLE}; }}
        """)
        btn_kembali.clicked.connect(self.reject)

        btn_save = QPushButton("\u2b07  Download PDF")
        btn_save.setFixedHeight(36); btn_save.setFixedWidth(150)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{ border:none; border-radius:7px; background:{C.ACCENT};
                          color:white; font-size:13px; font-weight:700; }}
            QPushButton:hover {{ background:{C.ACCENT_DARK}; }}
        """)
        btn_save.clicked.connect(self._save_pdf)

        footer.addWidget(btn_kembali)
        footer.addStretch()
        footer.addWidget(btn_save)
        root.addLayout(footer)

    def _save_pdf(self):
        from PyQt5.QtWidgets import QFileDialog
        from PyQt5.QtPrintSupport import QPrinter
        from PyQt5.QtGui import QPainter

        nomor = self.data.get('nomor', 'kuitansi').replace('/', '-')
        default_name = f"Kuitansi_{nomor}.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Kuitansi PDF", default_name,
            "PDF Files (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith('.pdf'):
            path += '.pdf'

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPrinter.A5)
        printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)

        painter = QPainter()
        if not painter.begin(printer):
            show_toast(self, "Gagal", "Tidak bisa membuat file PDF.", "error")
            return

        # render card widget ke printer
        page_rect = printer.pageRect()
        card = self._card
        card_size = card.size()

        scale_x = page_rect.width()  / card_size.width()
        scale_y = page_rect.height() / card_size.height()
        scale   = min(scale_x, scale_y)

        painter.scale(scale, scale)
        card.render(painter)
        painter.end()

        show_toast(self, "Berhasil", f"Kuitansi berhasil disimpan: {path}", "success")


#  Dialog: Tambah Murid Baru
class TambahMuridDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tambah Murid Baru")
        self.setFixedSize(480, 560)
        self.setStyleSheet("background-color: white;")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────
        hdr = QVBoxLayout()
        hdr.setSpacing(2)
        t = QLabel("Tambah Murid Baru")
        t.setStyleSheet(f"font-size:17px;font-weight:700;color:{C.TEXT_PRIMARY};")
        s = QLabel("ADMIN MVS PORTAL")
        s.setStyleSheet(f"font-size:10px;font-weight:600;color:{C.TEXT_MUTED_STRONG};letter-spacing:1px;")
        hdr.addWidget(t)
        hdr.addWidget(s)

        close_btn = QPushButton()
        close_btn.setIcon(svg_icon("x", C.TEXT_MUTED, 12))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ border:none; background:{C.SURFACE_HOVER}; border-radius:6px;
                          color:{C.TEXT_MUTED}; font-size:12px; }}
            QPushButton:hover {{ background:{C.BORDER}; }}
        """)
        close_btn.clicked.connect(self.reject)

        top = QHBoxLayout()
        top.addLayout(hdr)
        top.addStretch()
        top.addWidget(close_btn)
        root.addLayout(top)
        root.addSpacing(20)

        # ── Form fields ─────────────────────────────────────
        def line_edit(placeholder):
            e = QLineEdit()
            e.setPlaceholderText(placeholder)
            e.setFixedHeight(36)
            e.setStyleSheet(f"""
                QLineEdit {{ border:1px solid {C.BORDER_LIGHT}; border-radius:6px;
                            padding-left:10px; font-size:12px; color:{C.TEXT_PRIMARY}; background:white; }}
                QLineEdit:focus {{ border:1px solid {C.ACCENT}; }}
            """)
            return e

        def combo(placeholder, items):
            c = QComboBox()
            c.addItem(placeholder)
            c.addItems(items)
            c.setFixedHeight(36)
            c.setStyleSheet(f"""
                QComboBox {{ border:1px solid {C.BORDER_LIGHT}; border-radius:6px;
                            padding-left:10px; font-size:12px; color:{C.TEXT_MUTED}; background:white; }}
                QComboBox:focus {{ border:1px solid {C.ACCENT}; }}
                QComboBox::drop-down {{ border:none; width:24px; }}
            """)
            # Style langsung ke popup view agar hover item konsisten (lihat theme.style_combo())
            c.view().setStyleSheet(f"""
                QListView {{ border:1px solid {C.BORDER}; border-radius:0px; background:white;
                            padding:4px; outline:none; font-size:12px; color:{C.TEXT_PRIMARY}; }}
                QListView::item {{ min-height:28px; padding-left:10px; border-radius:4px; }}
                QListView::item:hover {{ background-color:{C.ACCENT}; color:white; }}
                QListView::item:selected {{ background-color:{C.ACCENT}; color:white; }}
            """)
            c.view().setMouseTracking(True)
            c.view().viewport().setMouseTracking(True)
            return c

        def date_edit():
            d = QDateEdit()
            d.setDisplayFormat("dd/MM/yyyy")
            d.setDate(QDate.currentDate())
            d.setFixedHeight(36)
            d.setCalendarPopup(True)
            d.setFocusPolicy(Qt.StrongFocus)
            d.installEventFilter(_BLOCK_SCROLL)
            d.setStyleSheet(f"""
                QDateEdit {{ border:1px solid {C.BORDER_LIGHT}; border-radius:6px;
                            padding-left:10px; font-size:12px; color:{C.TEXT_MUTED}; background:white; }}
                QDateEdit:focus {{ border:1px solid {C.ACCENT}; }}
                QDateEdit::drop-down {{ border:none; width:24px; }}
            """ + _CALENDAR_QSS)
            return d

        def field_label(txt):
            l = QLabel(txt)
            l.setStyleSheet(f"font-size:12px;font-weight:600;color:{C.TEXT_SECONDARY};")
            return l

        form = QVBoxLayout()
        form.setSpacing(12)

        # Row 1: Nama Siswa / Jenis Kelamin
        r1 = QHBoxLayout(); r1.setSpacing(16)
        c1 = QVBoxLayout(); c1.setSpacing(4)
        c1.addWidget(field_label("Nama Siswa"))
        nama_edit = line_edit("Masukkan nama lengkap")
        self._nama_edit = nama_edit
        c1.addWidget(nama_edit)
        c2 = QVBoxLayout(); c2.setSpacing(4)
        c2.addWidget(field_label("Jenis Kelamin"))
        self._jk_combo = combo("Pilih jenis kelamin", ["Laki-laki", "Perempuan"])
        c2.addWidget(self._jk_combo)
        r1.addLayout(c1); r1.addLayout(c2)
        form.addLayout(r1)

        # Row 2: Tanggal Lahir / Tanggal Daftar
        r2 = QHBoxLayout(); r2.setSpacing(16)
        c3 = QVBoxLayout(); c3.setSpacing(4)
        c3.addWidget(field_label("Tanggal Lahir"))
        self._tgl_lahir = date_edit()
        c3.addWidget(self._tgl_lahir)
        c4 = QVBoxLayout(); c4.setSpacing(4)
        c4.addWidget(field_label("Tanggal Daftar"))
        self._tgl_daftar = date_edit()
        c4.addWidget(self._tgl_daftar)
        r2.addLayout(c3); r2.addLayout(c4)
        form.addLayout(r2)

        # Row 3: Alamat
        c5 = QVBoxLayout(); c5.setSpacing(4)
        c5.addWidget(field_label("Alamat"))
        self._addr_edit = QTextEdit()
        self._addr_edit.setPlaceholderText("Alamat lengkap domisili")
        self._addr_edit.setFixedHeight(72)
        self._addr_edit.setStyleSheet(f"""
            QTextEdit {{ border:1px solid {C.BORDER_LIGHT}; border-radius:6px;
                        padding:8px 10px; font-size:12px; color:{C.TEXT_PRIMARY}; background:white; }}
            QTextEdit:focus {{ border:1px solid {C.ACCENT}; }}
        """)
        c5.addWidget(self._addr_edit)
        form.addLayout(c5)

        # Row 4: Wali / No HP
        r4 = QHBoxLayout(); r4.setSpacing(16)
        c6 = QVBoxLayout(); c6.setSpacing(4)
        c6.addWidget(field_label("Wali"))
        self._ortu_edit = line_edit("Ayah/Ibu/Wali")
        c6.addWidget(self._ortu_edit)
        c7 = QVBoxLayout(); c7.setSpacing(4)
        c7.addWidget(field_label("No HP Orang Tua"))
        self._hp_edit = line_edit("Contoh: 08123456789")
        c7.addWidget(self._hp_edit)
        r4.addLayout(c6); r4.addLayout(c7)
        form.addLayout(r4)

        # Row 5: Biaya Daftar
        r5 = QHBoxLayout(); r5.setSpacing(16)
        c8 = QVBoxLayout(); c8.setSpacing(4)
        c8.addWidget(field_label("Biaya Daftar"))
        biaya = QLineEdit("Rp200.000")
        biaya.setFixedHeight(36)
        biaya.setStyleSheet(f"""
            QLineEdit {{ border:1.5px solid {C.ACCENT}; border-radius:6px;
                        padding-left:10px; font-size:13px; font-weight:700;
                        color:{C.ACCENT_DARKER}; background:white; }}
        """)
        self._biaya_edit = biaya
        c8.addWidget(biaya)

        r5.addLayout(c8)
        form.addLayout(r5)

        root.addLayout(form)
        root.addStretch()

        # ── Footer buttons ───────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{C.BORDER};")
        root.addWidget(sep)
        root.addSpacing(12)

        footer = QHBoxLayout()
        btn_batal = QPushButton(" Kembali")
        btn_batal.setIcon(svg_icon("arrow-left", C.TEXT_SECONDARY, 13))
        btn_batal.setFixedHeight(36); btn_batal.setFixedWidth(110)
        btn_batal.setCursor(Qt.PointingHandCursor)
        btn_batal.setStyleSheet(f"""
            QPushButton {{ border:1px solid {C.BORDER_LIGHT}; border-radius:7px;
                          background:white; color:{C.TEXT_SECONDARY}; font-size:13px; }}
            QPushButton:hover {{ background:{C.SURFACE_SUBTLE}; }}
        """)
        btn_batal.clicked.connect(self.reject)

        btn_kuitansi = QPushButton("Lihat Kuitansi")
        btn_kuitansi.setFixedHeight(36)
        btn_kuitansi.setCursor(Qt.PointingHandCursor)
        btn_kuitansi.setStyleSheet(f"""
            QPushButton {{ border:1px solid {C.BORDER_LIGHT}; border-radius:7px;
                          background:white; color:{C.TEXT_SECONDARY}; font-size:13px; padding:0 14px; }}
            QPushButton:hover {{ background:{C.SURFACE_SUBTLE}; }}
        """)
        btn_kuitansi.clicked.connect(self._show_kuitansi_murid)

        btn_simpan = QPushButton("Simpan")
        btn_simpan.setFixedHeight(36); btn_simpan.setFixedWidth(90)
        btn_simpan.setCursor(Qt.PointingHandCursor)
        btn_simpan.setStyleSheet(f"""
            QPushButton {{ border:none; border-radius:7px; background:{C.ACCENT};
                          color:white; font-size:13px; font-weight:700; }}
            QPushButton:hover {{ background:{C.ACCENT_DARK}; }}
        """)
        btn_simpan.clicked.connect(self._simpan_murid)
        self._btn_simpan = btn_simpan

        footer.addWidget(btn_batal)
        footer.addStretch()
        footer.addWidget(btn_kuitansi); footer.addSpacing(8)
        footer.addWidget(btn_simpan)
        root.addLayout(footer)

    def _simpan_murid(self):
        from database import DB
        import datetime

        nama   = self._nama_edit.text().strip()
        jk_text = self._jk_combo.currentText()
        alamat = self._addr_edit.toPlainText().strip()
        hp     = self._hp_edit.text().strip()
        ortu   = self._ortu_edit.text().strip() if hasattr(self, '_ortu_edit') else ""

        # Validasi semua field wajib
        errors = []
        if not nama:
            errors.append("• Nama Siswa")
        if jk_text == "Pilih jenis kelamin":
            errors.append("• Jenis Kelamin")
        if not alamat:
            errors.append("• Alamat")
        if not hp:
            errors.append("• No HP Orang Tua")
        if not ortu:
            errors.append("• Wali")
        if errors:
            show_toast(self, "Perhatian", "Field berikut wajib diisi: " + ", ".join(errors), "warning", anchor=getattr(self, "_btn_simpan", None))
            return

        # Cegah klik ganda memicu INSERT dobel
        if hasattr(self, "_btn_simpan"):
            self._btn_simpan.setEnabled(False)

        jk = "L" if jk_text == "Laki-laki" else "P"

        # Usia dihitung otomatis dari tanggal lahir
        tgl_lahir = self._tgl_lahir.date()
        today = datetime.date.today()
        usia = today.year - tgl_lahir.year() - (
            (today.month, today.day) < (tgl_lahir.month(), tgl_lahir.day())
        )

        # Tanggal daftar
        tgl_daftar = self._tgl_daftar.date()
        tgl_masuk = f"{tgl_daftar.year()}-{tgl_daftar.month():02d}-{tgl_daftar.day():02d}"

        status = "Aktif"  # murid baru selalu Aktif

        # Generate no_pendaft otomatis: MV-YYYY-XXX
        tahun = tgl_daftar.year()
        existing = DB.fetch_all(
            "SELECT no_pendaft FROM murid WHERE no_pendaft LIKE ? ORDER BY no_pendaft DESC LIMIT 1",
            (f"MV-{tahun}-%",)
        )
        if existing:
            last_no = int(existing[0]["no_pendaft"].split("-")[-1])
            no_pendaft = f"MV-{tahun}-{last_no + 1:03d}"
        else:
            no_pendaft = f"MV-{tahun}-001"

        try:
            DB.execute("""
                INSERT INTO murid (no_pendaft, nama, jenis_kel, usia, no_hp, alamat, wali, tgl_masuk, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (no_pendaft, nama, jk, usia, hp, alamat, ortu, tgl_masuk, status))

            try:
                biaya_raw = self._biaya_edit.text() if hasattr(self, '_biaya_edit') else ""
                biaya_daftar = int(''.join(c for c in biaya_raw if c.isdigit())) if biaya_raw else 200000
            except Exception:
                biaya_daftar = 200000

            # Sinkron ke transaksi_keuangan sebagai Debit [PENDAFTARAN]
            try:
                tgl_disp = datetime.date.today().strftime("%d/%m/%Y")
                ket_daftar = f"[PENDAFTARAN] {no_pendaft} – {nama} | Biaya Pendaftaran | ID:new"
                existing = DB.fetch_one(
                    "SELECT id FROM transaksi_keuangan WHERE keterangan=?", (ket_daftar,)
                )
                if not existing and biaya_daftar > 0:
                    DB.execute(
                        "INSERT INTO transaksi_keuangan (tanggal, jenis, keterangan, nominal) "
                        "VALUES (?, 'Debit', ?, ?)",
                        (tgl_disp, ket_daftar, biaya_daftar)
                    )
            except Exception:
                pass

            show_toast(self, "Berhasil", f"Murid '{nama}' berhasil disimpan. ID: {no_pendaft}", "success", anchor=getattr(self, "_btn_simpan", None))
            self.accept()
        except Exception as e:
            if hasattr(self, "_btn_simpan"):
                self._btn_simpan.setEnabled(True)
            show_toast(self, "Gagal", f"Gagal menyimpan data murid: {str(e)}", "error", anchor=getattr(self, "_btn_simpan", None))

    def _show_kuitansi_murid(self):
        import datetime
        biaya_text = self._biaya_edit.text() if hasattr(self, '_biaya_edit') else "Rp200.000"
        nama_siswa = self._nama_edit.text().strip() if hasattr(self, '_nama_edit') and self._nama_edit.text().strip() else "—"
        data = {
            "nomor":         "MVS-2024-001",
            "nama":          nama_siswa,
            "jumlah":        f"{biaya_text} (Dua Ratus Ribu Rupiah)",
            "keterangan":    "Biaya Pendaftaran Murid Baru",
            "nominal_angka": biaya_text.replace('Rp', '').strip(),
            "tanggal":       datetime.date.today().strftime("%d / %m / %Y"),
            "ttd_nama":      "Aris Suryahadi",
            "ttd_jabatan":   "Aris Suryahadi Yunanto\nGENERAL MANAGER\nMelody Violin School Yogyakarta",
            "catatan":     (
                "Catatan :\n"
                "* Mohon pembayaran ditransfer ke rekening bank berikut ini :\n"
                "  BCA 4451561892  |  BNI 0536029816  |  BRI 0029.01.114973.50.9\n"
                "  a.n : Mahudiah Safitri\n"
            ),
        }
        dlg = KuitansiPreviewDialog(self, data)
        dlg.exec_()


#  Durasi sesi per metode: Offline/Home Visit 45 menit, Online 30 menit
DURASI_PER_METODE = {
    "Offline":    45,
    "Home Visit": 45,
    "Online":     30,
}

# Warna banner info durasi, menyesuaikan metode belajar:
# (background, accent kiri, warna teks)
BANNER_STYLES = {
    "Offline":    (f"{C.WARNING_BG}", "#FB923C", "#C2410C"),
    "Online":     (f"{C.ACCENT_BG}", f"{C.ACCENT}", f"{C.ACCENT_DARKER}"),
    "Home Visit": (f"{C.SUCCESS_BG}", f"{C.SUCCESS}", f"{C.SUCCESS_DARK}"),
}


#  Dialog: Tambah Jadwal Les
class TambahJadwalDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tambah Les Baru")
        self.setFixedSize(580, 700)
        self.setStyleSheet("background-color: white;")
        self._build()

    def eventFilter(self, obj, event):
        # Guru Pengajar diklik tapi Kursus belum dipilih → kasih tahu user
        # kenapa daftar gurunya kosong, alih-alih diam saja.
        if (obj is getattr(self, "_guru_combo", None)
                and event.type() == QEvent.MouseButtonPress
                and self._kursus_combo.currentText() == "Pilih Kursus"):
            show_toast(self, "Pilih Kursus Dulu",
                       "Daftar guru pengajar baru muncul setelah Kursus dipilih.",
                       "warning", anchor=self._guru_combo)
            return True
        return super().eventFilter(obj, event)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────
        hdr_row = QHBoxLayout()
        ico = QLabel(""); ico.setStyleSheet("font-size:16px;")
        t = QLabel("Tambah Les Baru")
        t.setStyleSheet(f"font-size:17px;font-weight:700;color:{C.TEXT_PRIMARY};")
        hdr_row.addWidget(ico); hdr_row.addSpacing(6); hdr_row.addWidget(t)
        hdr_row.addStretch()
        close_btn = QPushButton()
        close_btn.setIcon(svg_icon("x", C.TEXT_MUTED, 12))
        close_btn.setFixedSize(28, 28); close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ border:none; background:{C.SURFACE_HOVER}; border-radius:6px;
                          color:{C.TEXT_MUTED}; font-size:12px; }}
            QPushButton:hover {{ background:{C.BORDER}; }}
        """)
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)
        root.addLayout(hdr_row)
        root.addSpacing(20)

        def field_label(txt):
            l = QLabel(txt); l.setStyleSheet(f"font-size:12px;font-weight:600;color:{C.TEXT_SECONDARY};")
            return l

        def combo(placeholder, items):
            c = QComboBox(); c.addItem(placeholder); c.addItems(items)
            c.setFixedHeight(36)
            c.setStyleSheet(f"""
                QComboBox {{ border:1px solid {C.BORDER_LIGHT}; border-radius:6px;
                            padding-left:10px; font-size:12px; color:{C.TEXT_MUTED}; background:white; }}
                QComboBox:focus {{ border:1px solid {C.ACCENT}; }}
                QComboBox::drop-down {{ border:none; width:24px; }}
            """)
            # Style langsung ke popup view supaya item yang dilewati kursor
            # selalu ke-highlight — lihat catatan di theme.style_combo().
            c.view().setStyleSheet(f"""
                QListView {{ border:1px solid {C.BORDER}; border-radius:0px; background:white;
                            padding:4px; outline:none; font-size:12px; color:{C.TEXT_PRIMARY}; }}
                QListView::item {{ min-height:28px; padding-left:10px; border-radius:4px; }}
                QListView::item:hover {{ background-color:{C.ACCENT}; color:white; }}
                QListView::item:selected {{ background-color:{C.ACCENT}; color:white; }}
            """)
            c.view().setMouseTracking(True)
            c.view().viewport().setMouseTracking(True)
            return c

        def date_edit():
            d = QDateEdit(); d.setDisplayFormat("dd/MM/yyyy"); d.setDate(QDate.currentDate())
            d.setFixedHeight(36); d.setCalendarPopup(True); d.setFocusPolicy(Qt.StrongFocus)
            d.installEventFilter(_BLOCK_SCROLL)
            d.setStyleSheet(f"""
                QDateEdit {{ border:1px solid {C.BORDER_LIGHT}; border-radius:6px;
                            padding-left:10px; font-size:12px; color:{C.TEXT_MUTED}; background:white; }}
                QDateEdit:focus {{ border:1px solid {C.ACCENT}; }}
                QDateEdit::drop-down {{ border:none; width:24px; }}
            """ + _CALENDAR_QSS)
            return d

        def rp_field(is_total=False):
            e = QLineEdit("0"); e.setFixedHeight(34)
            color = f"{C.ACCENT_DARKER}" if is_total else f"{C.TEXT_PRIMARY}"
            border_color = f"{C.ACCENT}" if is_total else f"{C.BORDER_LIGHT}"
            bg = f"{C.ACCENT_BG_STRONG}" if is_total else "white"
            e.setStyleSheet(f"""
                QLineEdit {{ border:1px solid {border_color}; border-radius:6px;
                            padding-left:10px; font-size:12px; font-weight:700;
                            color:{color}; background:{bg}; }}
            """)
            return e

        form = QVBoxLayout(); form.setSpacing(10)

        # Load data dari database
        from database import DB
        murid_list  = [r["nama"] for r in DB.fetch_all("SELECT nama FROM murid WHERE status='Aktif' ORDER BY nama")]
        kursus_list = [r["nama"] for r in DB.fetch_all("SELECT nama FROM kursus ORDER BY nama")]
        # Mapping kursus -> guru yang mengajar kursus tsb (dari kolom keahlian di tabel guru)
        self._guru_per_kursus = {}
        for k in kursus_list:
            guru_k = DB.fetch_all(
                "SELECT nama FROM guru WHERE status='Aktif' AND keahlian LIKE ? ORDER BY nama",
                (f"%{k}%",)
            )
            self._guru_per_kursus[k] = [r["nama"] for r in guru_k]

        # Row 1: Nama Siswa / Kursus
        r1 = QHBoxLayout(); r1.setSpacing(16)
        c1 = QVBoxLayout(); c1.setSpacing(4)
        c1.addWidget(field_label("Nama Siswa"))
        self._siswa_combo = combo("Pilih Siswa", murid_list)
        c1.addWidget(self._siswa_combo)
        c2 = QVBoxLayout(); c2.setSpacing(4)
        c2.addWidget(field_label("Kursus"))
        self._kursus_combo = combo("Pilih Kursus", kursus_list)
        c2.addWidget(self._kursus_combo)
        r1.addLayout(c1, 1); r1.addLayout(c2, 1)
        form.addLayout(r1)

        # Row 2: Guru / Metode
        r2 = QHBoxLayout(); r2.setSpacing(16)
        c3 = QVBoxLayout(); c3.setSpacing(4)
        c3.addWidget(field_label("Guru Pengajar"))
        self._guru_combo = combo("Pilih Kursus dulu", [])
        self._guru_combo.installEventFilter(self)
        c3.addWidget(self._guru_combo)

        # Auto-filter guru saat kursus berubah
        def _on_kursus_changed(text):
            self._guru_combo.clear()
            if text == "Pilih Kursus":
                self._guru_combo.addItem("Pilih Kursus dulu")
                return
            daftar_guru = self._guru_per_kursus.get(text, [])
            if not daftar_guru:
                self._guru_combo.addItem(f"Belum ada guru untuk {text}")
                return
            self._guru_combo.addItem("Pilih Guru")
            for nama in daftar_guru:
                self._guru_combo.addItem(nama)
        self._kursus_combo.currentTextChanged.connect(_on_kursus_changed)
        c4 = QVBoxLayout(); c4.setSpacing(4)
        c4.addWidget(field_label("Metode Belajar"))
        rb_row = QHBoxLayout(); rb_row.setSpacing(12)
        self._rb_offline = QRadioButton("Offline")
        self._rb_online  = QRadioButton("Online")
        self._rb_home    = QRadioButton("Home Visit")
        self._rb_offline.setChecked(True)
        # Gaya sama persis dengan checkbox Hari Les: kotak indikator, biru saat
        # dicentang, latar biru muda saat hover — biar konsisten satu form.
        _metode_rb_style = (
            f"QRadioButton{{font-size:11px;color:{C.TEXT_SECONDARY};spacing:5px;"
            f"border:1px solid {C.BORDER};border-radius:6px;"
            "padding:3px 8px;background:white;}"
            "QRadioButton::indicator{width:12px;height:12px;border-radius:3px;"
            f"border:1.5px solid {C.BORDER_STRONG};background:white;}}"
            f"QRadioButton::indicator:checked{{background:{C.ACCENT};border:1.5px solid {C.ACCENT};}}"
            f"QRadioButton:hover{{border:1px solid {C.ACCENT_BORDER};background:{C.ACCENT_BG};}}"
            f"QRadioButton:checked{{color:{C.ACCENT_DARKER};font-weight:600;"
            f"border:1px solid {C.ACCENT_BORDER};background:{C.ACCENT_BG};}}"
        )
        for rb in [self._rb_offline, self._rb_online, self._rb_home]:
            rb.setCursor(Qt.PointingHandCursor)
            rb.setFixedHeight(24)
            rb.setStyleSheet(_metode_rb_style); rb_row.addWidget(rb)
        rb_row.addStretch()
        rb_wrap = QWidget(); rb_wrap.setLayout(rb_row); rb_wrap.setFixedHeight(36)
        c4.addWidget(rb_wrap)
        r2.addLayout(c3, 1); r2.addLayout(c4, 1)
        form.addLayout(r2)

        # Banner durasi — full width, warna menyesuaikan metode belajar
        self._durasi_lbl = QLabel("")
        self._durasi_lbl.setWordWrap(True)
        form.addWidget(self._durasi_lbl)

        # Row 3: Hari Les & Jam Sesi — per hari ada opsi "Sesi 2" (back-to-back)
        c5a = QVBoxLayout(); c5a.setSpacing(8)
        section_title = QLabel("Hari Les, Jam & Sesi per Hari")
        section_title.setStyleSheet("font-size:13px;font-weight:700;color:#1F2937;")
        c5a.addWidget(section_title)

        JAM_LIST = [
            "07:00","07:30","08:00","08:30","09:00","09:30",
            "10:00","10:30","11:00","11:30","12:00","12:30",
            "13:00","13:30","14:00","14:30","15:00","15:30",
            "16:00","16:30","17:00","17:30","18:00","18:30","19:00",
        ]
        CB_STYLE = (
            f"QCheckBox{{font-size:11px;color:{C.TEXT_SECONDARY};spacing:5px;"
            f"border:1px solid {C.BORDER};border-radius:6px;"
            "padding:3px 8px;background:white;}"
            "QCheckBox::indicator{width:12px;height:12px;border-radius:3px;"
            f"border:1.5px solid {C.BORDER_STRONG};background:white;}}"
            f"QCheckBox::indicator:checked{{background:{C.ACCENT};border:1.5px solid {C.ACCENT};}}"
        )
        CB_SESI2_STYLE = (
            f"QCheckBox{{font-size:10px;color:{C.TEXT_MUTED_STRONG};spacing:5px;"
            f"border:1px solid {C.BORDER};border-radius:6px;"
            "padding:3px 8px;background:white;}"
            "QCheckBox::indicator{width:12px;height:12px;border-radius:3px;"
            f"border:1.5px solid {C.BORDER_STRONG};background:white;}}"
            f"QCheckBox::indicator:disabled{{background:{C.SURFACE_SUBTLE};border:1.5px solid {C.SURFACE_HOVER};}}"
            f"QCheckBox::indicator:checked{{background:{C.ACCENT};border:1.5px solid {C.ACCENT};}}"
            f"QCheckBox:checked{{color:{C.ACCENT_DARKER};font-weight:600;border:1px solid {C.ACCENT_BORDER};background:{C.ACCENT_BG};}}"
            f"QCheckBox:disabled{{color:{C.BORDER_LIGHT};border:1px solid {C.SURFACE_HOVER};background:{C.SURFACE_SUBTLE};}}"
        )
        COMBO_STYLE = (
            f"QComboBox{{border:1px solid {C.BORDER};border-radius:6px;padding-left:6px;"
            f"font-size:11px;color:{C.TEXT_SECONDARY};background:white;}}"
            f"QComboBox:disabled{{color:{C.BORDER_LIGHT};background:{C.SURFACE_SUBTLE};border:1px solid {C.SURFACE_HOVER};}}"
            f"QComboBox:focus{{border:1px solid {C.ACCENT};}}"
            "QComboBox::drop-down{border:none;width:16px;}"
            "QComboBox QAbstractItemView{font-size:11px;}"
        )
        # Style popup jam_cb (top-level window terpisah dari COMBO_STYLE)
        JAM_COMBO_POPUP_QSS = (
            f"QListView{{border:1px solid {C.BORDER};border-radius:0px;background:white;"
            "padding:4px;outline:none;font-size:11px;color:" + C.TEXT_PRIMARY + ";}"
            "QListView::item{min-height:26px;padding-left:8px;border-radius:4px;}"
            f"QListView::item:hover{{background-color:{C.ACCENT};color:white;}}"
            f"QListView::item:selected{{background-color:{C.ACCENT};color:white;}}"
        )
        HDR_LBL_STYLE = (f"font-size:10px;font-weight:700;color:{C.TEXT_MUTED_STRONG};"
                         "background:transparent;border:none;letter-spacing:0.5px;")

        self._hari_checks = {}
        self._hari_jams   = {}
        self._hari_sesi2  = {}

        hari_container = QWidget()
        hari_container.setStyleSheet(
            f"QWidget{{background:white;border:1px solid {C.BORDER};border-radius:10px;}}"
            "QLabel{border:none;background:transparent;}")
        grid = QGridLayout(hari_container)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(2, 1)

        # Header
        h_hari = QLabel("HARI")
        h_jam  = QLabel("JAM MULAI")
        h_s2   = QLabel("SESI 2 (LANJUTAN)")
        for h in (h_hari, h_jam, h_s2):
            h.setStyleSheet(HDR_LBL_STYLE)
        grid.addWidget(h_hari, 0, 0)
        grid.addWidget(h_jam,  0, 1)
        grid.addWidget(h_s2,   0, 2)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C.SURFACE_HOVER};border:none;")
        grid.addWidget(sep, 1, 0, 1, 3)

        HARI_DEFS = [
            ("Sen","Senin",0),("Sel","Selasa",1),("Rab","Rabu",2),("Kam","Kamis",3),
            ("Jum","Jumat",4),("Sab","Sabtu",5),("Min","Minggu",6),
        ]

        # Validator format jam: HH:MM (00:00 - 23:59)
        jam_validator = QRegExpValidator(QRegExp(r"^([01]\d|2[0-3]):[0-5]\d$"))

        for row_offset, (short, full, idx) in enumerate(HARI_DEFS):
            row = row_offset + 2

            cb = QCheckBox(full)
            cb.setStyleSheet(CB_STYLE)
            cb.setFixedHeight(24)
            cb.setMinimumWidth(74)

            # Jam Mulai — bisa diketik manual (HH:MM) ATAU pilih dari dropdown
            jam_cb = QComboBox()
            jam_cb.addItems(JAM_LIST)
            jam_cb.setEditable(True)
            jam_cb.setInsertPolicy(QComboBox.NoInsert)
            jam_cb.lineEdit().setValidator(jam_validator)
            jam_cb.setCurrentText("09:00")
            jam_cb.setFixedHeight(24)
            jam_cb.setMinimumWidth(82)
            jam_cb.setEnabled(False)
            jam_cb.setStyleSheet(COMBO_STYLE)
            jam_cb.view().setStyleSheet(JAM_COMBO_POPUP_QSS)
            jam_cb.view().setMouseTracking(True)
            jam_cb.view().viewport().setMouseTracking(True)

            cb_sesi2 = QCheckBox("Sesi 2")
            cb_sesi2.setStyleSheet(CB_SESI2_STYLE)
            cb_sesi2.setFixedHeight(24)
            cb_sesi2.setEnabled(False)

            self._hari_checks[short] = cb
            self._hari_jams[short]   = jam_cb
            self._hari_sesi2[short]  = cb_sesi2

            def _on_day_toggle(checked, jc=jam_cb, c2=cb_sesi2, sh=short):
                jc.setEnabled(checked)
                c2.setEnabled(checked)
                if not checked:
                    c2.setChecked(False)
                self._update_sesi2_label(sh)
                self._update_preview_jadwal()

            def _on_jam_changed(*_args, sh=short):
                self._update_sesi2_label(sh)
                self._update_preview_jadwal()

            def _on_sesi2_toggle(_checked, sh=short):
                self._update_sesi2_label(sh)
                self._update_preview_jadwal()

            cb.toggled.connect(_on_day_toggle)
            jam_cb.currentIndexChanged.connect(_on_jam_changed)
            jam_cb.editTextChanged.connect(_on_jam_changed)
            cb_sesi2.toggled.connect(_on_sesi2_toggle)

            grid.addWidget(cb,       row, 0)
            grid.addWidget(jam_cb,   row, 1)
            grid.addWidget(cb_sesi2, row, 2)

        c5a.addWidget(hari_container)
        form.addLayout(c5a)

        # Row 4: Jumlah Sesi / Tanggal Mulai
        r4 = QHBoxLayout(); r4.setSpacing(16)
        c5 = QVBoxLayout(); c5.setSpacing(4)
        c5.addWidget(field_label("Jumlah Sesi"))
        self._sesi_spin = QSpinBox()
        self._sesi_spin.setRange(1, 52); self._sesi_spin.setValue(4)
        self._sesi_spin.setSuffix("x Sesi"); self._sesi_spin.setFixedHeight(36)
        self._sesi_spin.setFocusPolicy(Qt.StrongFocus)
        self._sesi_spin.installEventFilter(_BLOCK_SCROLL)
        self._sesi_spin.setStyleSheet(f"""
            QSpinBox {{ border:1px solid {C.BORDER_LIGHT}; border-radius:6px;
                       padding-left:10px; font-size:12px; color:{C.TEXT_MUTED}; background:white; }}
            QSpinBox:focus {{ border:1px solid {C.ACCENT}; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width:20px; }}
        """)
        c5.addWidget(self._sesi_spin)
        c6 = QVBoxLayout(); c6.setSpacing(4)
        c6.addWidget(field_label("Tanggal Mulai"))
        self._tgl_edit = date_edit()
        c6.addWidget(self._tgl_edit)
        r4.addLayout(c5); r4.addLayout(c6)
        form.addLayout(r4)

        # Preview jadwal otomatis
        self._preview_label = QLabel("Pilih hari dan jam untuk melihat preview jadwal")
        self._preview_label.setStyleSheet(
            f"font-size:10px;color:{C.TEXT_MUTED};font-style:italic;"
            f"background:{C.SURFACE_ALT};border:1px solid {C.BORDER};border-radius:6px;padding:6px 10px;"
        )
        self._preview_label.setWordWrap(True)
        form.addWidget(self._preview_label)

        # Row 5: Biaya panel
        biaya_panel = QFrame()
        biaya_panel.setStyleSheet("QFrame { background-color:#F0F9FF; border-radius:8px; border:none; }")
        bp = QHBoxLayout(biaya_panel); bp.setContentsMargins(14,12,14,12); bp.setSpacing(16)
        col_les = QVBoxLayout(); col_les.setSpacing(4)
        col_les.addWidget(field_label("Biaya Les"))
        self._biaya_les = rp_field(); col_les.addWidget(self._biaya_les)
        self._transport_container = QWidget()
        col_tr = QVBoxLayout(self._transport_container)
        col_tr.setSpacing(4); col_tr.setContentsMargins(0,0,0,0)
        col_tr.addWidget(field_label("Biaya Transport"))
        self._biaya_transport = rp_field(); col_tr.addWidget(self._biaya_transport)
        self._transport_container.setVisible(False)
        col_total = QVBoxLayout(); col_total.setSpacing(4)
        lbl_total = QLabel("Total Bayar")
        lbl_total.setStyleSheet(f"font-size:11px;font-weight:700;color:{C.ACCENT_DARKER};")
        col_total.addWidget(lbl_total)
        self._total_edit = rp_field(is_total=True); self._total_edit.setReadOnly(True)
        col_total.addWidget(self._total_edit)
        bp.addLayout(col_les); bp.addWidget(self._transport_container); bp.addLayout(col_total)
        form.addWidget(biaya_panel)

        form_widget = QWidget()
        form_widget.setLayout(form)
        form_widget.setStyleSheet("background:transparent;")

        scroll = QScrollArea()
        scroll.setWidget(form_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        # Scrollbar disamakan dgn gaya yang dipakai di Data Guru/Data Murid/Absensi
        # (thin, abu-abu, rounded) — sebelumnya polos/pakai scrollbar bawaan OS.
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        root.addWidget(scroll)

        # ── Koneksi signal ──────────────────────────────────
        self._biaya_les.textChanged.connect(self._hitung_total)
        self._biaya_transport.textChanged.connect(self._hitung_total)
        self._rb_home.toggled.connect(self._on_metode_changed)
        self._rb_offline.toggled.connect(self._on_metode_changed)
        self._rb_online.toggled.connect(self._on_metode_changed)
        self._sesi_spin.valueChanged.connect(self._on_params_changed)
        self._tgl_edit.dateChanged.connect(self._on_params_changed)

        # Tampilkan info durasi awal (default: Offline, 45 menit/sesi)
        self._update_durasi_label()

        # ── Footer ───────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet(f"color:{C.BORDER};")
        root.addWidget(sep); root.addSpacing(12)
        footer = QHBoxLayout()
        btn_batal = QPushButton(" Kembali")
        btn_batal.setIcon(svg_icon("arrow-left", C.TEXT_SECONDARY, 13))
        btn_batal.setFixedHeight(36); btn_batal.setFixedWidth(90); btn_batal.setCursor(Qt.PointingHandCursor)
        btn_batal.setStyleSheet(f"""
            QPushButton {{ border:1px solid {C.BORDER_LIGHT}; border-radius:7px;
                          background:white; color:{C.TEXT_SECONDARY}; font-size:12px; }}
            QPushButton:hover {{ background:{C.SURFACE_SUBTLE}; }}
        """)
        btn_batal.clicked.connect(self.reject)
        btn_kuitansi = QPushButton("Lihat Kuitansi")
        btn_kuitansi.setFixedHeight(36); btn_kuitansi.setCursor(Qt.PointingHandCursor)
        btn_kuitansi.setStyleSheet(f"""
            QPushButton {{ border:1px solid {C.BORDER_LIGHT}; border-radius:7px;
                          background:white; color:{C.TEXT_SECONDARY}; font-size:12px; padding:0 14px; }}
            QPushButton:hover {{ background:{C.SURFACE_SUBTLE}; }}
        """)
        btn_kuitansi.clicked.connect(self._show_kuitansi_jadwal)
        btn_simpan = QPushButton("Simpan")
        btn_simpan.setFixedHeight(36); btn_simpan.setFixedWidth(100); btn_simpan.setCursor(Qt.PointingHandCursor)
        btn_simpan.setStyleSheet(f"""
            QPushButton {{ border:none; border-radius:7px; background:{C.ACCENT};
                          color:white; font-size:12px; font-weight:700; }}
            QPushButton:hover {{ background:{C.ACCENT_DARK}; }}
        """)
        btn_simpan.clicked.connect(self._simpan_jadwal)
        self._btn_simpan = btn_simpan
        footer.addWidget(btn_batal)
        footer.addStretch()
        footer.addWidget(btn_kuitansi); footer.addSpacing(8)
        footer.addWidget(btn_simpan)
        root.addLayout(footer)

    def _parse_rp(self, text):
        import re
        digits = re.sub(r'[^\d]', '', text)
        return int(digits) if digits else 0

    def _fmt_rp_display(self, val):
        return f"Rp {val:,.0f}".replace(",", ".")

    def _terbilang(self, n):
        satuan = ["","satu","dua","tiga","empat","lima","enam","tujuh","delapan","sembilan"]
        belasan = ["sepuluh","sebelas","dua belas","tiga belas","empat belas","lima belas",
                   "enam belas","tujuh belas","delapan belas","sembilan belas"]
        def _ratusan(x):
            if x == 0: return ""
            h, r = divmod(x, 100); res = ""
            if h == 1: res += "seratus "
            elif h > 1: res += satuan[h] + " ratus "
            if 10 <= r < 20: res += belasan[r-10] + " "
            else:
                p, q = divmod(r, 10)
                if p == 1: res += "sepuluh "
                elif p > 1: res += satuan[p] + " puluh "
                if q: res += satuan[q] + " "
            return res
        if n == 0: return "Nol Rupiah"
        juta, r = divmod(n, 1_000_000); ribu, sisa = divmod(r, 1_000); out = ""
        if juta: out += _ratusan(juta).strip() + " juta "
        if ribu:
            if ribu == 1: out += "seribu "
            else: out += _ratusan(ribu).strip() + " ribu "
        if sisa: out += _ratusan(sisa).strip()
        return out.strip().capitalize() + " Rupiah"

    def _get_metode(self):
        if self._rb_home.isChecked(): return "Home Visit"
        if self._rb_online.isChecked(): return "Online"
        return "Offline"

    def _on_metode_changed(self):
        is_home = self._rb_home.isChecked()
        self._transport_container.setVisible(is_home)
        if not is_home: self._biaya_transport.setText("0")
        self._hitung_total()
        self._on_params_changed()

    def _get_durasi_satuan(self):
        """Durasi 1 sesi (menit) berdasarkan metode belajar yang dipilih."""
        return DURASI_PER_METODE.get(self._get_metode(), 45)

    def _update_durasi_label(self):
        durasi = self._get_durasi_satuan()
        metode = self._get_metode()
        bg, accent, fg = BANNER_STYLES.get(metode, BANNER_STYLES["Offline"])
        self._durasi_lbl.setStyleSheet(
            f"font-size:11px;color:{fg};font-weight:600;background:{bg};"
            f"border:none;border-radius:6px;padding:8px 12px;"
        )
        self._durasi_lbl.setText(f"Durasi: {durasi} menit / sesi  ({metode})")

    def _update_sesi2_label(self, hari_key):
        """Perbarui teks checkbox 'Sesi 2' agar menampilkan jam lanjutan saat dicentang."""
        cb_sesi2  = self._hari_sesi2[hari_key]
        jam_combo = self._hari_jams[hari_key]
        if cb_sesi2.isChecked():
            durasi = self._get_durasi_satuan()
            ranges = self._hitung_jam_ranges(jam_combo.currentText(), durasi, 2)
            jm2, js2 = ranges[1]
            cb_sesi2.setText(f"Sesi 2  ({jm2}–{js2})")
        else:
            cb_sesi2.setText("Sesi 2")

    def _on_params_changed(self):
        """Dipanggil saat metode, jumlah sesi, tanggal, atau opsi sesi berubah."""
        for hari_key in self._hari_sesi2:
            self._update_sesi2_label(hari_key)
        self._update_durasi_label()
        self._update_preview_jadwal()

    def _hitung_total(self):
        les = self._parse_rp(self._biaya_les.text())
        tr  = self._parse_rp(self._biaya_transport.text()) if self._rb_home.isChecked() else 0
        self._total_edit.setText(self._fmt_rp_display(les + tr))

    def _get_hari_dipilih(self):
        """Return list (nama_panjang, weekday_idx, jam_str, sesi2_bool) untuk hari yang dicentang."""
        MAP = {"Sen":("Senin",0),"Sel":("Selasa",1),"Rab":("Rabu",2),
               "Kam":("Kamis",3),"Jum":("Jumat",4),"Sab":("Sabtu",5),"Min":("Minggu",6)}
        result = []
        for key in ["Sen","Sel","Rab","Kam","Jum","Sab","Min"]:
            if self._hari_checks[key].isChecked():
                nama, idx = MAP[key]
                jam   = self._hari_jams[key].currentText()
                sesi2 = self._hari_sesi2[key].isChecked()
                result.append((nama, idx, jam, sesi2))
        return result

    def _generate_tanggal_sesi(self):
        from datetime import date, timedelta
        hari_list = self._get_hari_dipilih()  # [(nama, weekday_idx, jam_str, sesi2_bool), ...]
        if not hari_list: return []
        qd = self._tgl_edit.date()
        start = date(qd.year(), qd.month(), qd.day())
        n_sesi = self._sesi_spin.value()

        # Kandidat pertemuan mingguan untuk setiap hari yang dipilih.
        # Worst-case (tanpa "+sesi 2") butuh maksimal n_sesi minggu.
        candidates = []
        for nama_hari, weekday_idx, jam_str, sesi2 in hari_list:
            diff = (weekday_idx - start.weekday()) % 7
            first = start + timedelta(days=diff)
            for w in range(n_sesi + 1):
                candidates.append((first + timedelta(weeks=w), nama_hari, jam_str, sesi2))
        candidates.sort(key=lambda x: x[0])

        # Ambil pertemuan berurutan sampai jumlah sesi terkumpul >= n_sesi.
        # Pertemuan dengan "+sesi 2" menyumbang 2 sesi back-to-back sekaligus.
        result = []
        total = 0
        for cand in candidates:
            if total >= n_sesi:
                break
            result.append(cand)
            total += 2 if cand[3] else 1
        return result  # [(date, nama_hari, jam_str, sesi2_bool), ...]

    def _hitung_jam_ranges(self, jam_str, durasi_menit, n_kali):
        """
        Kembalikan list (jam_mulai, jam_selesai) sebanyak `n_kali`,
        masing-masing berdurasi `durasi_menit`, disusun back-to-back
        mulai dari `jam_str` (format 'HH:MM').
        """
        from datetime import datetime as _dt, timedelta as _td
        try:
            cursor = _dt.strptime(jam_str, "%H:%M")
        except Exception:
            return [(jam_str, jam_str)] * n_kali
        ranges = []
        for _ in range(n_kali):
            akhir = cursor + _td(minutes=durasi_menit)
            ranges.append((cursor.strftime("%H:%M"), akhir.strftime("%H:%M")))
            cursor = akhir
        return ranges

    def _update_preview_jadwal(self):
        dates = self._generate_tanggal_sesi()
        if not dates:
            self._preview_label.setText("Pilih hari dan jam untuk melihat preview jadwal")
            return

        durasi = self._get_durasi_satuan()
        n_sesi = self._sesi_spin.value()

        lines = []
        sesi_no = 1
        for d, hari, jam, sesi2 in dates:
            kali = 2 if sesi2 else 1
            for jm, js in self._hitung_jam_ranges(jam, durasi, kali):
                if sesi_no > n_sesi:
                    break
                lines.append(f"Sesi {sesi_no}: {d.strftime('%d-%m-%Y')} ({hari})  {jm} - {js}")
                sesi_no += 1
        self._preview_label.setText("\n".join(lines))

    def _get_sesi_data(self):
        dates  = self._generate_tanggal_sesi()
        kursus = self._kursus_combo.currentText()
        metode = self._get_metode()
        durasi = self._get_durasi_satuan()
        n_sesi = self._sesi_spin.value()

        result = []
        sesi_no = 1
        for d, _hari, jam, sesi2 in dates:
            kali = 2 if sesi2 else 1
            for jm, js in self._hitung_jam_ranges(jam, durasi, kali):
                if sesi_no > n_sesi:
                    break
                result.append({
                    "les": kursus, "no": sesi_no, "tanggal": d.strftime('%d-%m-%Y'),
                    "guru": "–", "jam": f"{jm} - {js}", "metode": metode, "status": "Pending"
                })
                sesi_no += 1
        return result

    def _cek_bentrok_jadwal(self, sesi_list, guru_id, murid_id):
        """
        Cek apakah sesi-sesi baru pada sesi_list bentrok (jam tumpang tindih)
        dengan jadwal yang sudah tersimpan di database — baik untuk guru
        yang sama maupun untuk murid yang sama, pada tanggal yang sama.
        Sesi dengan status 'Batal' diabaikan (dianggap sudah tidak terpakai).
        Mengembalikan list pesan bentrok (list kosong = aman, tidak ada bentrok).
        """
        from database import DB
        konflik = []

        for s in sesi_list:
            tanggal = s["tanggal"]
            jam_parts = s["jam"].split(" - ")
            if len(jam_parts) != 2:
                continue
            jm_baru, js_baru = jam_parts[0].strip(), jam_parts[1].strip()

            rows = DB.fetch_all("""
                SELECT js.jam_mulai, js.jam_selesai, js.guru_id, pk.murid_id,
                       g.nama AS nama_guru, m.nama AS nama_murid
                FROM jadwal_sesi js
                JOIN pendaftaran_kursus pk ON js.pendaftaran_id = pk.id
                LEFT JOIN guru g ON js.guru_id = g.id
                LEFT JOIN murid m ON pk.murid_id = m.id
                WHERE js.tanggal = ? AND js.status NOT IN ('Batal', 'Reschedule')
                  AND (js.guru_id = ? OR pk.murid_id = ?)
            """, (tanggal, guru_id, murid_id))

            for r in rows:
                jm_ada  = (r["jam_mulai"] or "").strip()
                js_ada  = (r["jam_selesai"] or "").strip()
                if not jm_ada or not js_ada:
                    continue
                # Dua rentang waktu tumpang tindih jika: mulai_baru < selesai_ada DAN mulai_ada < selesai_baru
                tumpang_tindih = (jm_baru < js_ada) and (jm_ada < js_baru)
                if not tumpang_tindih:
                    continue

                if guru_id is not None and r["guru_id"] == guru_id:
                    konflik.append(
                        f"Guru {r['nama_guru'] or '-'} sudah mengajar pada {tanggal} "
                        f"jam {jm_ada}-{js_ada} (bentrok dengan sesi baru {jm_baru}-{js_baru})"
                    )
                if murid_id is not None and r["murid_id"] == murid_id:
                    konflik.append(
                        f"Murid {r['nama_murid'] or '-'} sudah memiliki jadwal pada {tanggal} "
                        f"jam {jm_ada}-{js_ada} (bentrok dengan sesi baru {jm_baru}-{js_baru})"
                    )

        return konflik

    def _simpan_jadwal(self):
        from database import DB

        nama       = self._siswa_combo.currentText()
        kursus     = self._kursus_combo.currentText()
        nama_guru  = self._guru_combo.currentText() if hasattr(self, '_guru_combo') else "Pilih Guru"
        biaya_les  = self._parse_rp(self._biaya_les.text()) if hasattr(self, '_biaya_les') else 0
        sesi_list  = self._get_sesi_data()
        hari_dipilih = any(cb.isChecked() for cb in self._hari_checks.values()) if hasattr(self, '_hari_checks') else False

        # Validasi semua field wajib
        errors = []
        if nama == "Pilih Siswa":
            errors.append("• Siswa")
        if kursus == "Pilih Kursus":
            errors.append("• Kursus")
        if nama_guru in ("Pilih Guru", "Pilih Kursus dulu") or nama_guru.startswith("Belum ada guru untuk"):
            errors.append("• Guru")
        if not hari_dipilih:
            errors.append("• Hari Jadwal (pilih minimal satu)")
        if biaya_les <= 0:
            errors.append("• Biaya Les (harus lebih dari 0)")
        if errors:
            show_toast(self, "Perhatian", "Field berikut wajib diisi: " + ", ".join(errors), "warning", anchor=getattr(self, "_btn_simpan", None))
            return

        if not sesi_list:
            show_toast(self, "Perhatian", "Tidak ada sesi yang bisa dibuat dari jadwal yang dipilih.", "warning", anchor=getattr(self, "_btn_simpan", None))
            return

        # Cegah klik ganda memicu insert sesi jadwal dua kali
        if hasattr(self, "_btn_simpan"):
            self._btn_simpan.setEnabled(False)

        # Cari murid_id dan guru_id dari nama
        murid = DB.fetch_one("SELECT id FROM murid WHERE nama=?", (nama,))
        kursus_row = DB.fetch_one("SELECT id FROM kursus WHERE nama=?", (kursus,))
        if not murid or not kursus_row:
            if hasattr(self, "_btn_simpan"):
                self._btn_simpan.setEnabled(True)
            show_toast(self, "Gagal", "Data murid atau kursus tidak ditemukan.", "error", anchor=getattr(self, "_btn_simpan", None))
            return

        murid_id = murid["id"]
        kursus_id = kursus_row["id"]

        # Ambil guru_id dari combo
        guru_row = DB.fetch_one("SELECT id FROM guru WHERE nama=?", (nama_guru,))
        guru_id_selected = guru_row["id"] if guru_row else None

        # ── Cek bentrok jadwal (guru & murid) SEBELUM data disimpan ──────
        konflik = self._cek_bentrok_jadwal(sesi_list, guru_id_selected, murid_id)
        if konflik:
            if hasattr(self, "_btn_simpan"):
                self._btn_simpan.setEnabled(True)
            pesan = "Tidak bisa disimpan, jadwal bentrok:\n" + "\n".join(f"• {k}" for k in konflik[:5])
            if len(konflik) > 5:
                pesan += f"\n... dan {len(konflik) - 5} bentrok lainnya."
            show_toast(self, "Jadwal Bentrok", pesan, "error",
                       anchor=getattr(self, "_btn_simpan", None), persistent=True)
            return

        # Ambil / buat pendaftaran_kursus
        pk = DB.fetch_one(
            "SELECT id, guru_id FROM pendaftaran_kursus WHERE murid_id=? AND kursus_id=? AND status='Aktif'",
            (murid_id, kursus_id)
        )
        jumlah_sesi_paket = self._sesi_spin.value()

        if not pk:
            tgl_mulai = sesi_list[0]["tanggal"] if sesi_list else ""
            # Coba tambah kolom jumlah_sesi_paket kalau belum ada
            try:
                DB.execute("ALTER TABLE pendaftaran_kursus ADD COLUMN jumlah_sesi_paket INTEGER DEFAULT 0")
            except Exception:
                pass
            pk_id = DB.execute(
                "INSERT INTO pendaftaran_kursus(murid_id,kursus_id,guru_id,tgl_mulai,status,jumlah_sesi_paket) VALUES(?,?,?,?,'Aktif',?)",
                (murid_id, kursus_id, guru_id_selected, tgl_mulai, jumlah_sesi_paket)
            )
            guru_id = guru_id_selected
        else:
            pk_id = pk["id"]
            guru_id = guru_id_selected or pk["guru_id"]
            # Update jumlah_sesi_paket setiap kali ada penambahan sesi baru
            try:
                DB.execute("ALTER TABLE pendaftaran_kursus ADD COLUMN jumlah_sesi_paket INTEGER DEFAULT 0")
            except Exception:
                pass
            DB.execute(
                "UPDATE pendaftaran_kursus SET jumlah_sesi_paket = jumlah_sesi_paket + ? WHERE id=?",
                (jumlah_sesi_paket, pk_id)
            )

        # Simpan setiap sesi
        metode = self._get_metode()
        try:
            for s in sesi_list:
                jam_parts = s["jam"].split(" - ")
                jam_mulai = jam_parts[0] if len(jam_parts) > 0 else ""
                jam_selesai = jam_parts[1] if len(jam_parts) > 1 else ""
                DB.execute("""
                    INSERT INTO jadwal_sesi
                        (pendaftaran_id, guru_id, no_sesi, tanggal, jam_mulai, jam_selesai, metode, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
                """, (pk_id, guru_id, s["no"], s["tanggal"], jam_mulai, jam_selesai, metode))

            # Sinkron ke transaksi_keuangan sebagai Debit [LES]
            try:
                import datetime as _dt
                tgl_disp = _dt.date.today().strftime("%d/%m/%Y")
                # Ambil biaya les & transport dari field dialog (jika ada)
                try:
                    les_val = self._parse_rp(self._biaya_les.text()) if hasattr(self, '_biaya_les') else 0
                    tr_val  = self._parse_rp(self._biaya_transport.text()) if (
                        hasattr(self, '_biaya_transport') and hasattr(self, '_rb_home') and self._rb_home.isChecked()
                    ) else 0
                    total_les = les_val + tr_val
                except Exception:
                    total_les = 0

                if total_les > 0:
                    # Ambil no_pendaft murid
                    murid_row = DB.fetch_one("SELECT no_pendaft FROM murid WHERE id=?", (murid_id,))
                    no_pend   = murid_row["no_pendaft"] if murid_row else "-"
                    ket_les = (
                        f"[LES] {no_pend} – {nama} | {kursus} | "
                        f"{len(sesi_list)}x sesi | ID:{pk_id}"
                    )
                    existing = DB.fetch_one(
                        "SELECT id FROM transaksi_keuangan WHERE keterangan=?", (ket_les,)
                    )
                    if not existing:
                        DB.execute(
                            "INSERT INTO transaksi_keuangan (tanggal, jenis, keterangan, nominal) "
                            "VALUES (?, 'Debit', ?, ?)",
                            (tgl_disp, ket_les, total_les)
                        )

            except Exception:
                pass

            # ── Simpan ke pembayaran_sesi_murid ───────────────────────
            try:
                import datetime as _dt2
                tgl_bayar  = _dt2.date.today().strftime("%Y-%m-%d")
                les_val2   = self._parse_rp(self._biaya_les.text()) if hasattr(self, '_biaya_les') else 0
                tr_val2    = self._parse_rp(self._biaya_transport.text()) if (
                    hasattr(self, '_biaya_transport') and hasattr(self, '_rb_home')
                    and self._rb_home.isChecked()
                ) else 0
                total_val2 = les_val2 + tr_val2
                if total_val2 > 0:
                    # Buat baris pembayaran_murid sebagai parent (required FK)
                    pm_id = DB.execute("""
                        INSERT INTO pembayaran_murid
                            (murid_id, pendaftaran_id, tanggal, keterangan, nominal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (murid_id, pk_id, tgl_bayar,
                          f"Les {kursus} {jumlah_sesi_paket}x sesi", total_val2))
                    DB.execute("""
                        INSERT INTO pembayaran_sesi_murid
                            (pembayaran_id, murid_id, guru_id, kursus_id, tanggal_bayar,
                             jumlah_sesi, metode, biaya_les, biaya_transport,
                             total_bayar, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Lunas')
                    """, (pm_id, murid_id, guru_id, kursus_id, tgl_bayar,
                          jumlah_sesi_paket, metode,
                          les_val2, tr_val2, total_val2))
            except Exception:
                pass

            show_toast(self, "Berhasil", f"{len(sesi_list)} sesi jadwal berhasil disimpan untuk {nama}.", "success", anchor=getattr(self, "_btn_simpan", None))
            self.accept()
        except Exception as e:
            if hasattr(self, "_btn_simpan"):
                self._btn_simpan.setEnabled(True)
            show_toast(self, "Gagal", f"Gagal menyimpan jadwal: {str(e)}", "error", anchor=getattr(self, "_btn_simpan", None))

    def _show_kuitansi_jadwal(self):
        import datetime
        nama_siswa = self._siswa_combo.currentText()
        if nama_siswa == "Pilih Siswa": nama_siswa = "—"
        kursus    = self._kursus_combo.currentText()
        n_sesi    = self._sesi_spin.value()
        sesi_str  = f"{n_sesi}x Pertemuan"
        les   = self._parse_rp(self._biaya_les.text())
        tr    = self._parse_rp(self._biaya_transport.text()) if self._rb_home.isChecked() else 0
        total = les + tr
        keterangan = f"Les {kursus} {nama_siswa} {sesi_str}".strip()
        jumlah_str = f"{self._fmt_rp_display(total)} ({self._terbilang(total)})"
        data = {
            "nomor":         "MVS-2024-001",
            "nama":          nama_siswa,
            "jumlah":        jumlah_str,
            "keterangan":    keterangan,
            "nominal_angka": self._fmt_rp_display(total).replace('Rp', '').replace('.','').strip(),
            "tanggal":       datetime.date.today().strftime("%d / %m / %Y"),
            "ttd_nama":      "Aris Suryahadi",
            "ttd_jabatan":   "Aris Suryahadi Yunanto\nGENERAL MANAGER\nMelody Violin School Yogyakarta",
            "catatan": (
                "Catatan :\n"
                "* Mohon pembayaran ditransfer ke rekening bank berikut ini :\n"
                "  BCA 4451561892  |  BNI 0536029816  |  BRI 0029.01.114973.50.9\n"
                "  a.n : Mahudiah Safitri\n"

            ),
        }
        dlg = KuitansiPreviewDialog(self, data)
        dlg.exec_()


#  Main Widget: Data Murid
#  DIALOG: EDIT DATA MURID  (gaya & fungsi disamakan dengan Data Admin / Data Guru)

class EditMuridDialog(QDialog):
    """
    Dialog untuk mengubah data murid: Nama, Jenis Kelamin, Usia, No HP, Alamat.
    Status dikelola via toggle di tabel — tidak ditampilkan di form (identik Data Admin & Data Guru).
    Tombol: HAPUS (merah), KEMBALI (abu-abu), SIMPAN (biru solid).
    """

    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self._data = data or {}
        self._result_action = None   # 'simpan' | 'hapus'

        self.setWindowTitle("Data Murid")
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
        t1 = QLabel("Data Murid")
        t1.setStyleSheet(f"font-size:14px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;")
        t2 = QLabel("Kelola Data Murid Melody Violin School")
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

        # Nama Murid
        bv.addWidget(self._field_lbl("Nama Murid"))
        self.nama_input = self._line_edit("Nama lengkap murid")
        bv.addWidget(self.nama_input)

        # Jenis Kelamin
        bv.addWidget(self._field_lbl("Jenis Kelamin"))
        jk_row = QHBoxLayout()
        jk_row.setSpacing(20)
        self.rb_laki = QRadioButton("Laki-laki")
        self.rb_perempuan = QRadioButton("Perempuan")
        for rb in (self.rb_laki, self.rb_perempuan):
            rb.setStyleSheet(self._radio_style())
        jk_grp = QButtonGroup(self)
        jk_grp.addButton(self.rb_laki)
        jk_grp.addButton(self.rb_perempuan)
        jk_row.addWidget(self.rb_laki)
        jk_row.addWidget(self.rb_perempuan)
        jk_row.addStretch()
        bv.addLayout(jk_row)

        # Usia
        bv.addWidget(self._field_lbl("Usia"))
        self.usia_input = QSpinBox()
        self.usia_input.setRange(1, 100)
        self.usia_input.setSuffix(" Thn")
        self.usia_input.setFixedHeight(42)
        self.usia_input.setStyleSheet(f"""
            QSpinBox {{
                border: 1.5px solid {C.BORDER}; border-radius: 8px;
                padding-left: 12px; background: {C.SURFACE_ALT};
                font-size: 13px; color: {C.TEXT_PRIMARY};
            }}
            QSpinBox:focus {{ border: 1.5px solid {C.ACCENT}; background: white; }}
        """)
        self.usia_input.installEventFilter(_BLOCK_SCROLL)
        bv.addWidget(self.usia_input)

        # No HP
        bv.addWidget(self._field_lbl("No HP"))
        self.hp_input = self._line_edit("0812-xxxx-xxxx")
        bv.addWidget(self.hp_input)

        # Alamat
        bv.addWidget(self._field_lbl("Alamat"))
        self.alamat_input = QTextEdit()
        self.alamat_input.setPlaceholderText("Alamat lengkap domisili murid...")
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

        # Wali
        bv.addWidget(self._field_lbl("Wali"))
        self.ortu_input = self._line_edit("Ayah/Ibu/Wali")
        bv.addWidget(self.ortu_input)

        root.addWidget(body)

        # Prefill jika edit
        if data:
            self.nama_input.setText(data.get("nama", ""))
            self.hp_input.setText(data.get("hp", ""))
            self.alamat_input.setPlainText(data.get("alamat", ""))
            self.ortu_input.setText(data.get("ortu", ""))
            try:
                self.usia_input.setValue(int(data.get("usia") or 1))
            except (TypeError, ValueError):
                pass
            jk = (data.get("jk") or "").upper()
            if jk == "L":
                self.rb_laki.setChecked(True)
            elif jk == "P":
                self.rb_perempuan.setChecked(True)

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

    def _on_hapus(self):
        # Dialog konfirmasi custom, senada dengan toast & dialog lain di aplikasi
        if confirm_action(
            self, "Konfirmasi Hapus",
            f"Hapus murid '{self.nama_input.text().strip()}'?\n"
            "Seluruh data pendaftaran & riwayat terkait juga akan terhapus."
        ):
            self._result_action = "hapus"
            self.accept()

    def _on_simpan(self):
        if not self._validate():
            return
        self._result_action = "simpan"
        self.accept()

    def _validate(self):
        if not self.nama_input.text().strip():
            show_toast(self, "Perhatian", "Nama Murid tidak boleh kosong!", "warning", anchor=self._btn_simpan)
            self.nama_input.setFocus()
            return False
        if not self.rb_laki.isChecked() and not self.rb_perempuan.isChecked():
            show_toast(self, "Perhatian", "Jenis Kelamin harus dipilih!", "warning", anchor=self._btn_simpan)
            return False
        if not self.hp_input.text().strip():
            show_toast(self, "Perhatian", "No HP tidak boleh kosong!", "warning", anchor=self._btn_simpan)
            self.hp_input.setFocus()
            return False
        if not self.alamat_input.toPlainText().strip():
            show_toast(self, "Perhatian", "Alamat tidak boleh kosong!", "warning", anchor=self._btn_simpan)
            return False
        return True

    def get_data(self):
        return {
            "nama":   self.nama_input.text().strip(),
            "jk":     "L" if self.rb_laki.isChecked() else "P",
            "usia":   self.usia_input.value(),
            "hp":     self.hp_input.text().strip(),
            "alamat": self.alamat_input.toPlainText().strip(),
            "ortu":   self.ortu_input.text().strip(),
            "action": self._result_action,
        }


#  WIDGET: DATA MURID

class DataMuridWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C.SURFACE_ALT};")
        self.init_ui()

    def init_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(35, 30, 35, 30)
        v.setSpacing(25)

        # ── Page heading ──────────────────────────────────────
        h = QHBoxLayout()
        title = QLabel("Data Murid")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {C.TEXT_PRIMARY};")
        sub = QLabel("Manajemen data seluruh murid sekolah")
        sub.setStyleSheet(f"font-size: 12px; color: {C.TEXT_MUTED_STRONG}; margin-top: 2px;")
        t_box = QVBoxLayout(); t_box.setSpacing(2)
        t_box.addWidget(title); t_box.addWidget(sub)
        h.addLayout(t_box)
        v.addLayout(h)

        # ── Stat cards + action buttons row ───────────────────
        stat_row = QHBoxLayout()
        stat_row.setSpacing(16)

        self.active_filter = "aktif"  # semua / aktif / nonaktif
        self.stat_cards = {}          # key -> (card QFrame, title QLabel, value QLabel)

        def make_stat_card(key, title, value):
            card = QFrame()
            card.setFixedSize(200, 90)
            card.setObjectName("statCard")
            card.setCursor(Qt.PointingHandCursor)

            layout = QVBoxLayout(card)
            layout.setContentsMargins(18, 14, 18, 14)
            layout.setSpacing(6)

            t_lbl = QLabel(title)
            v_lbl = QLabel(value)
            v_lbl.setStyleSheet(f"font-size:28px;font-weight:bold;color:{C.TEXT_PRIMARY};border:none;background:transparent;")
            layout.addWidget(t_lbl)
            layout.addWidget(v_lbl)

            self.stat_cards[key] = (card, t_lbl, v_lbl)
            self._apply_card_style(key, active=(key == self.active_filter))

            # click handler
            def on_click(_, k=key):
                self.active_filter = k
                for ck in self.stat_cards:
                    self._apply_card_style(ck, active=(ck == self.active_filter))
                self._filter_table()

            card.mousePressEvent = on_click
            return card

        stat_row.addWidget(make_stat_card("semua",    "Total Murid",     "0"))
        stat_row.addWidget(make_stat_card("aktif",    "Murid Aktif",     "0"))
        stat_row.addWidget(make_stat_card("nonaktif", "Murid Non-Aktif", "0"))
        stat_row.addStretch()

        # Action buttons on the right
        btn_tambah_murid = QPushButton("+ TAMBAH MURID")
        btn_tambah_murid.setFixedSize(180, 42)
        btn_tambah_murid.setCursor(Qt.PointingHandCursor)
        btn_tambah_murid.setStyleSheet(primary_button_style())
        btn_tambah_murid.clicked.connect(self.open_tambah_murid)

        stat_row.addWidget(btn_tambah_murid)
        v.addLayout(stat_row)

        # ── Table card ────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: white; border-radius: 14px; border: none; }")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(22, 20, 22, 20)
        cv.setSpacing(16)

        # Toolbar
        tb = QHBoxLayout()
        lbl = QLabel("Daftar Murid")
        lbl.setStyleSheet(f"font-size:16px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;")
        search = QLineEdit()
        search.setPlaceholderText("Cari nama atau ID murid…")
        search.addAction(svg_icon("search", C.TEXT_FAINT, 15), QLineEdit.LeadingPosition)
        search.setFixedSize(240, 36)
        search.setStyleSheet(f"""
            QLineEdit {{ border:1.5px solid {C.BORDER}; border-radius:8px;
                        background:{C.SURFACE_ALT}; padding-left:12px; font-size:12px; color:{C.TEXT_PRIMARY}; }}
            QLineEdit:focus {{ border:1.5px solid {C.ACCENT}; background:white; }}
        """)
        tb.addWidget(lbl); tb.addStretch(); tb.addWidget(search)
        self._search_edit = search
        cv.addLayout(tb)

        # Table
        cols = ["NO", "ID MURID", "NAMA MURID", "L/P", "UMUR", "NO HP", "ALAMAT", "WALI", "STATUS", "AKSI"]
        self.table = QTableWidget(5, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(f"""
            QTableWidget {{ border:none; background-color:white; }}
            QHeaderView::section {{
                background-color:{C.SURFACE_ALT}; padding:12px 8px;
                border:none; border-bottom:2px solid {C.SURFACE_HOVER};
                color:{C.TEXT_MUTED_STRONG}; font-weight:bold; font-size:11px;
            }}
            QTableWidget::item {{
                padding:14px 8px; border-bottom:1px solid {C.SURFACE_HOVER};
                color:{C.TEXT_BODY}; font-size:12px;
            }}
            QTableWidget::item:selected {{ background-color:{C.ACCENT_BG}; color:{C.TEXT_PRIMARY}; }}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        # Kolom sempit — fixed
        hh.setSectionResizeMode(0, QHeaderView.Fixed); self.table.setColumnWidth(0, 42)   # NO
        hh.setSectionResizeMode(3, QHeaderView.Fixed); self.table.setColumnWidth(3, 56)   # L/P
        hh.setSectionResizeMode(4, QHeaderView.Fixed); self.table.setColumnWidth(4, 70)   # UMUR
        hh.setSectionResizeMode(8, QHeaderView.Fixed); self.table.setColumnWidth(8, 180)  # STATUS
        hh.setSectionResizeMode(9, QHeaderView.Fixed); self.table.setColumnWidth(9, 100)  # AKSI
        self.table.verticalHeader().setDefaultSectionSize(58)
        self._fill_table()
        cv.addWidget(self.table)

        # Pagination
        pg = QHBoxLayout()
        info = QLabel("Menampilkan 1-5 dari 5 murid")
        info.setStyleSheet(f"color:{C.TEXT_MUTED_STRONG};font-size:12px;background:transparent;")
        self._info_label = info
        self._search_edit.textChanged.connect(self._filter_table)
        pb = QHBoxLayout(); pb.setSpacing(6)
        for txt in ["‹ Prev", "1", "Next ›"]:
            b = QPushButton(txt)
            b.setFixedHeight(32)
            b.setFixedWidth(50 if txt.isdigit() else 70)
            b.setCursor(Qt.PointingHandCursor)
            is_active = txt == "1"
            b.setStyleSheet(f"""
                QPushButton {{
                    border-radius:6px; font-size:12px;
                    background-color:{f'{C.ACCENT}' if is_active else 'white'};
                    color:{'white' if is_active else f'{C.TEXT_MUTED}'};
                    border:{'none' if is_active else f'1px solid {C.BORDER}'};
                }}
                QPushButton:hover {{ background-color:{f'{C.ACCENT_DARK}' if is_active else f'{C.SURFACE_ALT}'}; }}
            """)
            pb.addWidget(b)
        pg.addWidget(info); pg.addStretch(); pg.addLayout(pb)
        cv.addLayout(pg)

        v.addWidget(card)

    def _apply_card_style(self, key, active=False):
        card, t_lbl, v_lbl = self.stat_cards[key]
        accent_map = {"semua": f"{C.ACCENT}", "aktif": "#10B981", "nonaktif": f"{C.DANGER}"}
        accent = accent_map.get(key, f"{C.ACCENT}")
        bg     = "#F0F6FF" if active else "white"
        border = f"2px solid {C.ACCENT}" if active else f"1px solid {C.BORDER}"
        lbl_color = accent if active else f"{C.TEXT_MUTED_STRONG}"
        card.setStyleSheet(f"""
            QFrame#statCard {{
                background-color: {bg};
                border-radius: 14px;
                border: {border};
            }}
            QFrame#statCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        t_lbl.setStyleSheet(
            f"font-size:12px;font-weight:{'bold' if active else 'normal'};color:{lbl_color};"
            "border:none;background:transparent;"
        )

    def _filter_table(self):
        f = self.active_filter
        query = self._search_edit.text().strip().lower() if hasattr(self, '_search_edit') else ""
        filtered = [
            row for row in self.all_data
            if (f == "semua"
                or (f == "aktif"    and row[8] == "Aktif")
                or (f == "nonaktif" and row[8] == "Nonaktif"))
            and (not query or query in row[2].lower() or query in row[1].lower())
        ]
        self.table.setRowCount(len(filtered))
        for r in range(len(filtered)):
            self.table.setRowHeight(r, 65)
        # Update info label
        if hasattr(self, '_info_label'):
            total_shown = len(filtered)
            total_all   = len(self.all_data)
            if total_shown > 0:
                self._info_label.setText(f"Menampilkan 1-{total_shown} dari {total_all} murid")
            else:
                self._info_label.setText(f"Tidak ada data ditemukan")
        for r, row in enumerate(filtered):
            murid_id = row[9]
            status   = row[8]
            alamat   = row[6]
            ortu     = row[7]
            jk_raw   = row[10] if len(row) > 10 else "L"
            usia_raw = row[11] if len(row) > 11 else 0

            for c, val in enumerate(row[:8]):
                if c == 2:
                    item = QTableWidgetItem(val)
                    item.setFont(_ui_font(10, bold=True))
                    self.table.setItem(r, c, item)
                else:
                    self.table.setItem(r, c, QTableWidgetItem(val))

            murid_dict = {
                "id": murid_id, "nama": row[2], "hp": row[5],
                "alamat": alamat, "ortu": ortu, "jk": jk_raw, "usia": usia_raw,
                "status": status,
            }

            # Status — Toggle Switch interaktif (identik gaya Data Admin / Data Guru)
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

            def _on_toggle(checked, d=murid_dict, btn=toggle_btn, lbl=lbl_toggle):
                from database import DB
                new_status = "Aktif" if checked else "Nonaktif"
                DB.execute("UPDATE murid SET status=? WHERE id=?", (new_status, d["id"]))
                d["status"] = new_status
                for row_ref in self.all_data:
                    if row_ref[9] == d["id"]:
                        row_ref[8] = new_status
                        break
                _apply_style(btn, lbl, checked)
                self._update_stat_counts()

            toggle_btn.toggled.connect(_on_toggle)
            tl.addWidget(toggle_btn)
            tl.addSpacing(8)
            tl.addWidget(lbl_toggle)
            self.table.setCellWidget(r, 8, toggle_w)

            # Aksi — tombol Edit membuka dialog lengkap (identik Data Admin / Data Guru)
            aksi_w = QWidget()
            al = QHBoxLayout(aksi_w)
            al.setContentsMargins(2, 2, 2, 2)
            al.setAlignment(Qt.AlignCenter)
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedHeight(32)
            edit_btn.setMinimumWidth(64)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(action_button_style())
            edit_btn.clicked.connect(lambda _, d=murid_dict: self._open_edit_murid(d))
            al.addWidget(edit_btn)
            self.table.setCellWidget(r, 9, aksi_w)

    def _open_edit_murid(self, data):
        dlg = EditMuridDialog(self, data)
        if dlg.exec_() == QDialog.Accepted:
            from database import DB
            d = dlg.get_data()
            murid_id = data.get("id")
            if d["action"] == "hapus":
                if murid_id:
                    DB.execute("DELETE FROM murid WHERE id=?", (murid_id,))
                    show_toast(self, "Berhasil", "Data Murid Berhasil Dihapus", "success")
            else:
                if murid_id:
                    DB.execute(
                        "UPDATE murid SET nama=?,jenis_kel=?,usia=?,no_hp=?,alamat=?,wali=? WHERE id=?",
                        (d["nama"], d["jk"], d["usia"], d["hp"], d["alamat"], d["ortu"], murid_id)
                    )
                    show_toast(self, "Berhasil", "Data Berhasil Disimpan", "success")
            self._fill_table()

    def open_tambah_murid(self):
        dlg = TambahMuridDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._fill_table()

    def open_tambah_jadwal(self):
        dlg = TambahJadwalDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._fill_table()

    def _fill_table(self):
        from database import DB
        DB.sinkronkan_paket_selesai()
        rows = DB.fetch_all("""
            SELECT m.id AS murid_id, m.no_pendaft, m.nama, m.jenis_kel, m.usia, m.no_hp,
                   m.alamat, m.wali, m.status
            FROM murid m
            ORDER BY m.nama
        """)
        self.all_data = []
        for i, r in enumerate(rows, 1):
            # Format L/P singkat — sama seperti kolom "L/P" di Data Guru
            # (bukan lagi teks penuh "Laki-laki"/"Perempuan").
            jk = "L" if r["jenis_kel"] == "L" else "P"
            usia = f"{r['usia']} Thn" if r["usia"] else "-"

            self.all_data.append([
                str(i).zfill(2),
                r["no_pendaft"] or "-",
                r["nama"],
                jk,
                usia,
                r["no_hp"] or "-",
                r["alamat"] or "-",
                r["wali"] or "-",
                r["status"],
                r["murid_id"],
                r["jenis_kel"] or "L",      # index 10 = jenis kelamin raw (L/P)
                r["usia"] or 0,             # index 11 = usia raw (int)
            ])
        self._update_stat_counts()
        self._filter_table()

    def _update_stat_counts(self):
        total    = len(self.all_data)
        aktif    = sum(1 for r in self.all_data if r[8] == "Aktif")
        nonaktif = total - aktif
        if hasattr(self, "stat_cards"):
            self.stat_cards["semua"][2].setText(str(total))
            self.stat_cards["aktif"][2].setText(str(aktif))
            self.stat_cards["nonaktif"][2].setText(str(nonaktif))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    app.setFont(_ui_font(10))
    w = DataMuridWidget()
    w.setWindowTitle("Data Murid – Melody Violin School")
    w.resize(1150, 750)
    w.show()
    sys.exit(app.exec_())