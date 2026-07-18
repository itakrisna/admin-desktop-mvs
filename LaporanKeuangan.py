import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QDialog,
    QLineEdit, QDateEdit, QSpinBox, QFileDialog,
    QScrollArea, QSizePolicy,
    QStyledItemDelegate
)
from PyQt5.QtCore import Qt, QDate
from toast_notification import show_toast, confirm_action
from theme import svg_icon, svg_pixmap, C, action_button_style, primary_button_style, style_combo
from PyQt5.QtGui import QFont, QColor, QPen


#  KONSTANTA

_BULAN_NAMES = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

# Tag sumber transaksi yang disimpan di kolom keterangan (awalan)
_TAG_LES          = "[LES]"
_TAG_PENDAFTARAN  = "[PENDAFTARAN]"
_TAG_GAJI_GURU    = "[GAJI-GURU]"
_TAG_GAJI_ADMIN   = "[GAJI-ADMIN]"


#  HELPERS

def _lbl(text, style=""):
    l = QLabel(text)
    if style:
        l.setStyleSheet(style)
    return l


def _fmt_rp(value: int) -> str:
    return "Rp {:,.0f}".format(value).replace(",", ".")


# ── Konversi format tanggal ───────────────────────────────────────────────────

def _to_display(tanggal: str) -> str:
    """Normalisasi format tanggal → 'DD/MM/YYYY'."""
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(tanggal, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return tanggal  # kembalikan apa adanya jika tidak cocok


def _parse_dt(tanggal: str) -> datetime:
    """Parse tanggal display 'DD/MM/YYYY' → datetime."""
    return datetime.strptime(tanggal, "%d/%m/%Y")


#  DELEGATE: Warna teks kolom angka

class _ColorDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text  = index.data(Qt.DisplayRole) or ""
        color = index.data(Qt.ForegroundRole)
        bold  = index.data(Qt.FontRole)

        painter.save()
        if option.state & 0x0002:
            painter.fillRect(option.rect, QColor(f"{C.ACCENT_BG}"))
        else:
            painter.fillRect(option.rect, QColor("white"))

        painter.setPen(QPen(QColor(f"{C.SURFACE_HOVER}"), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        font = QFont("Segoe UI", 10)
        if bold:
            font.setBold(True)
        painter.setFont(font)
        fg = QColor(color) if color else QColor(f"{C.TEXT_BODY}")
        if option.state & 0x0002:
            fg = QColor(f"{C.TEXT_PRIMARY}")
        painter.setPen(fg)
        painter.drawText(
            option.rect.adjusted(10, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            text
        )
        painter.restore()


class _RightDelegate(_ColorDelegate):
    def paint(self, painter, option, index):
        text  = index.data(Qt.DisplayRole) or ""
        color = index.data(Qt.ForegroundRole)

        painter.save()
        if option.state & 0x0002:
            painter.fillRect(option.rect, QColor(f"{C.ACCENT_BG}"))
        else:
            painter.fillRect(option.rect, QColor("white"))

        painter.setPen(QPen(QColor(f"{C.SURFACE_HOVER}"), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        fg = QColor(color) if color else QColor(f"{C.TEXT_BODY}")
        if option.state & 0x0002:
            fg = QColor(f"{C.TEXT_PRIMARY}")
        painter.setPen(fg)
        painter.drawText(
            option.rect.adjusted(10, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignRight,
            text
        )
        painter.restore()


def _make_table(cols, fixed_last=None):
    tbl = QTableWidget(0, len(cols))
    tbl.setHorizontalHeaderLabels(cols)
    tbl.verticalHeader().setVisible(False)
    tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
    tbl.setShowGrid(False)
    tbl.setFocusPolicy(Qt.NoFocus)
    tbl.setStyleSheet(f"""
        QTableWidget {{ border:none; background:white; outline:none; }}
        QHeaderView::section {{
            background: {C.SURFACE_ALT};
            padding: 10px 6px;
            border: none;
            border-bottom: 1px solid {C.BORDER};
            color: {C.TEXT_MUTED_STRONG};
            font-weight: bold;
            font-size: 10px;
            letter-spacing: 0.2px;
        }}
        QScrollBar:vertical {{ width: 6px; background: transparent; }}
        QScrollBar::handle:vertical {{ background: {C.BORDER}; border-radius: 3px; }}
    """)
    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    if fixed_last:
        for col_idx, w in fixed_last:
            tbl.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.Fixed)
            tbl.setColumnWidth(col_idx, w)
    return tbl


#  SINKRONISASI DATABASE → transaksi_keuangan

def _sinkron_db():
    """
    Tarik data baru dari tiga sumber dan simpan ke transaksi_keuangan.
    Gunakan keterangan bertag unik sebagai kunci deduplikasi.
    Kembalikan tuple (jumlah_ditambah, pesan_detail).
    """
    from database import get_conn

    ditambah = 0
    detail   = []

    conn = get_conn()
    cur  = conn.cursor()

    def _sudah_ada(ket: str) -> bool:
        """
        Cek duplikat berdasarkan prefix (semua bagian sebelum "| ID:").

        Format gaji:   "[GAJI-ADMIN] Fenny | Februari 2026 | ... | ID:?"
        Format les:    "[LES] MV-2026-020 – nani | ... | ID:5"
        Format daftar: "[PENDAFTARAN] MV-2026-001 – nindy | ... | ID:new"

        Nomor ID di akhir bisa berbeda antara yang diinsert langsung oleh
        DataMurid.py/Pembayaran.py (pakai pendaftaran_id) vs yang ditarik
        oleh _sinkron_db (pakai id baris pembayaran) — jadi dicek pakai
        LIKE prefix (bukan exact-match) supaya keduanya saling mengenali
        dan tidak pernah tercatat dobel.
        """
        if "| ID:" in ket:
            prefix = ket.split("| ID:")[0] + "| ID:"
        else:
            prefix = ket
        r = cur.execute(
            "SELECT id FROM transaksi_keuangan WHERE keterangan LIKE ?",
            (prefix + "%",)
        ).fetchone()
        return r is not None

    def _insert(tanggal: str, jenis: str, keterangan: str, nominal: int):
        nonlocal ditambah
        if _sudah_ada(keterangan):
            return
        cur.execute(
            "INSERT INTO transaksi_keuangan(tanggal,jenis,keterangan,nominal) VALUES(?,?,?,?)",
            (tanggal, jenis, keterangan, nominal)
        )
        ditambah += 1

    rows_les = cur.execute("""
        SELECT
            psm.id,
            psm.tanggal_bayar,
            psm.total_bayar,
            psm.jumlah_sesi,
            m.nama      AS nama_murid,
            m.no_pendaft,
            g.nama      AS nama_guru,
            k.nama      AS nama_kursus
        FROM pembayaran_sesi_murid psm
        JOIN murid  m ON m.id = psm.murid_id
        LEFT JOIN guru   g ON g.id  = psm.guru_id
        LEFT JOIN kursus k ON k.id  = psm.kursus_id
        WHERE psm.status = 'Lunas'
        ORDER BY psm.tanggal_bayar DESC
    """).fetchall()

    for r in rows_les:
        tgl = _to_display(r["tanggal_bayar"])
        ket = (f"{_TAG_LES} {r['no_pendaft']} – {r['nama_murid']} "
               f"| {r['nama_kursus']} | {r['jumlah_sesi']}x sesi "
               f"| ID:{r['id']}")
        _insert(tgl, "Debit", ket, r["total_bayar"])

    if ditambah:
        detail.append(f"- {ditambah} transaksi les baru")
    les_count = ditambah; ditambah = 0

    rows_daftar = cur.execute("""
        SELECT
            pm.id, pm.tanggal, pm.nominal,
            m.nama AS nama_murid, m.no_pendaft
        FROM pembayaran_murid pm
        JOIN murid m ON m.id = pm.murid_id
        WHERE LOWER(pm.keterangan) LIKE '%pendaft%'
          AND pm.status = 'Lunas'
        ORDER BY pm.tanggal DESC
    """).fetchall()

    for r in rows_daftar:
        tgl = _to_display(r["tanggal"])
        ket = (f"{_TAG_PENDAFTARAN} {r['no_pendaft']} – {r['nama_murid']} "
               f"| Biaya Pendaftaran | ID:{r['id']}")
        _insert(tgl, "Debit", ket, r["nominal"])

    if ditambah:
        detail.append(f"- {ditambah} pendaftaran baru")
    daftar_count = ditambah; ditambah = 0

    rows_gg = cur.execute("""
        SELECT
            gg.id, gg.tanggal_bayar, gg.nominal_total,
            gg.periode, gg.jumlah_sesi,
            g.nama AS nama_guru
        FROM gaji_guru gg
        JOIN guru g ON g.id = gg.guru_id
        WHERE gg.status = 'Sudah Dibayar'
          AND gg.tanggal_bayar IS NOT NULL
        ORDER BY gg.tanggal_bayar DESC
    """).fetchall()

    for r in rows_gg:
        tgl = _to_display(r["tanggal_bayar"])
        ket = (f"{_TAG_GAJI_GURU} {r['nama_guru']} "
               f"| {r['periode']} | {r['jumlah_sesi']} sesi "
               f"| ID:{r['id']}")
        _insert(tgl, "Kredit", ket, r["nominal_total"])

    if ditambah:
        detail.append(f"- {ditambah} slip gaji guru baru")
    gg_count = ditambah; ditambah = 0

    rows_ga = cur.execute("""
        SELECT
            ga.id, ga.tanggal_bayar, ga.nominal_total,
            ga.periode, ga.hari_kerja,
            a.nama AS nama_admin
        FROM gaji_admin ga
        JOIN admin a ON a.id = ga.admin_id
        WHERE ga.status = 'Sudah Dibayar'
          AND ga.tanggal_bayar IS NOT NULL
        ORDER BY ga.tanggal_bayar DESC
    """).fetchall()

    for r in rows_ga:
        tgl = _to_display(r["tanggal_bayar"])
        ket = (f"{_TAG_GAJI_ADMIN} {r['nama_admin']} "
               f"| {r['periode']} | {r['hari_kerja']} hari "
               f"| ID:{r['id']}")
        _insert(tgl, "Kredit", ket, r["nominal_total"])

    if ditambah:
        detail.append(f"- {ditambah} slip gaji admin baru")

    conn.commit()
    conn.close()

    total = les_count + daftar_count + gg_count + ditambah
    if not detail:
        detail.append("Tidak ada data baru.")
    return total, "\n".join(detail)


#  DIALOG: TAMBAH / EDIT TRANSAKSI MANUAL

class TambahTransaksiDialog(QDialog):
    def __init__(self, parent=None, data=None, is_auto=False):
        super().__init__(parent)
        self.setWindowTitle("Transaksi")
        self.setFixedWidth(440)
        self.setStyleSheet("""
            QDialog { background: white; }
            QWidget { background: white; }
            QLabel  { background: transparent; }
        """)
        self._jenis = "debit"
        self._bukti_path = None
        self._is_auto = is_auto
        self._edit_data = data
        self._build(data)

    def _build(self, data):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        title_txt = "Edit Transaksi" if data else "Tambah Transaksi"
        title = QLabel(title_txt)
        title.setStyleSheet(f"font-size:17px;font-weight:700;color:{C.TEXT_PRIMARY_DARK};background:transparent;")
        close = QPushButton()
        close.setIcon(svg_icon("x", C.TEXT_MUTED, 12))
        close.setFixedSize(28, 28)
        close.setCursor(Qt.PointingHandCursor)
        close.setStyleSheet(f"""
            QPushButton {{ border:none; background:{C.SURFACE_HOVER}; border-radius:6px;
                          color:{C.TEXT_MUTED}; font-size:13px; }}
            QPushButton:hover {{ background:{C.BORDER}; color:{C.TEXT_PRIMARY_DARK}; }}
        """)
        close.clicked.connect(self.reject)
        hdr.addWidget(title); hdr.addStretch(); hdr.addWidget(close)
        root.addLayout(hdr)
        root.addSpacing(20)

        # Tanggal
        root.addWidget(self._field_label("Tanggal"))
        root.addSpacing(6)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd / MM / yyyy")
        self.date_edit.setFixedHeight(40)
        self.date_edit.setStyleSheet(self._input_style())
        root.addWidget(self.date_edit)
        root.addSpacing(14)

        # Jenis transaksi
        root.addWidget(self._field_label("Jenis Transaksi"))
        root.addSpacing(6)
        jenis_row = QHBoxLayout(); jenis_row.setSpacing(8)
        self.btn_debit  = QPushButton(" Pemasukan")
        self.btn_debit.setIcon(svg_icon("arrow-down", C.ACCENT, 13))
        self.btn_kredit = QPushButton(" Pengeluaran")
        self.btn_kredit.setIcon(svg_icon("arrow-up", C.DANGER, 13))
        for btn, j in [(self.btn_debit, "debit"), (self.btn_kredit, "kredit")]:
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, jj=j: self._set_jenis(jj))
            jenis_row.addWidget(btn)
        self._update_jenis_style()
        root.addLayout(jenis_row)
        root.addSpacing(14)

        # Keterangan
        root.addWidget(self._field_label("Keterangan"))
        root.addSpacing(6)
        self.ket_input = QLineEdit()
        self.ket_input.setPlaceholderText("Misal: Pembayaran Gaji Guru")
        self.ket_input.setFixedHeight(40)
        self.ket_input.setStyleSheet(self._input_style())
        root.addWidget(self.ket_input)
        root.addSpacing(14)

        # Nominal
        root.addWidget(self._field_label("Nominal (Rp)"))
        root.addSpacing(6)
        nom_frame = QFrame()
        nom_frame.setFixedHeight(40)
        nom_frame.setStyleSheet(f"""
            QFrame {{ border:1.5px solid {C.BORDER}; border-radius:8px; background:{C.SURFACE_ALT}; }}
        """)
        nfl = QHBoxLayout(nom_frame)
        nfl.setContentsMargins(12, 0, 4, 0)
        nfl.setSpacing(4)
        rp = QLabel("Rp")
        rp.setStyleSheet(f"font-size:13px;color:{C.TEXT_MUTED_STRONG};background:transparent;border:none;")
        self.nominal_spin = QSpinBox()
        self.nominal_spin.setRange(0, 999_999_999)
        self.nominal_spin.setSingleStep(50_000)
        self.nominal_spin.setValue(0)
        self.nominal_spin.setFixedHeight(36)
        self.nominal_spin.setStyleSheet(f"""
            QSpinBox {{ border:none; background:transparent; font-size:13px; color:{C.TEXT_PRIMARY_DARK}; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width:22px; }}
        """)
        nfl.addWidget(rp); nfl.addWidget(self.nominal_spin, 1)
        root.addWidget(nom_frame)
        root.addSpacing(14)

        # Bukti transaksi
        root.addWidget(self._field_label("Bukti Transaksi (opsional)"))
        root.addSpacing(6)
        self.bukti_btn = QPushButton("  Pilih File Bukti Transaksi")
        self.bukti_btn.setIcon(svg_icon("upload", C.TEXT_MUTED, 14))
        self.bukti_btn.setFixedHeight(44)
        self.bukti_btn.setCursor(Qt.PointingHandCursor)
        self.bukti_btn.setStyleSheet(f"""
            QPushButton {{
                border: 1.5px solid {C.BORDER}; border-radius: 8px;
                background: {C.SURFACE_ALT}; color: {C.TEXT_MUTED};
                font-size: 13px; font-weight: 600; text-align: center;
            }}
            QPushButton:hover {{ background: {C.SURFACE_HOVER}; color: {C.TEXT_BODY}; border-color: {C.BORDER_STRONG}; }}
        """)
        self.bukti_btn.clicked.connect(self._pick_bukti)
        root.addWidget(self.bukti_btn)
        hint = _lbl("JPG, PNG, atau PDF · Maks 5MB",
                    f"font-size:10px;color:{C.TEXT_MUTED_STRONG};background:transparent;")
        hint.setAlignment(Qt.AlignCenter)
        root.addSpacing(4)
        root.addWidget(hint)
        root.addSpacing(20)

        # Divider
        div = QFrame(); div.setFixedHeight(1)
        div.setStyleSheet(f"background:{C.SURFACE_HOVER};")
        root.addWidget(div)
        root.addSpacing(16)

        # Tombol footer
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        if data:
            # Mode Edit
            kembali = QPushButton(" Kembali")
            kembali.setIcon(svg_icon("arrow-left", C.TEXT_MUTED, 13))
            kembali.setFixedHeight(38); kembali.setCursor(Qt.PointingHandCursor)
            kembali.setStyleSheet(f"""
                QPushButton {{ background:white; color:{C.TEXT_MUTED}; border:1.5px solid {C.BORDER};
                              border-radius:8px; font-size:13px; padding:0 16px; }}
                QPushButton:hover {{ background:{C.SURFACE_ALT}; }}
            """)
            kembali.clicked.connect(self.reject)

            simpan = QPushButton("Simpan")
            simpan.setFixedHeight(38); simpan.setCursor(Qt.PointingHandCursor)
            simpan.setStyleSheet(f"""
                QPushButton {{ background:{C.ACCENT}; color:white; border:none;
                              border-radius:8px; font-size:13px; font-weight:700;
                              padding:0 20px; }}
                QPushButton:hover {{ background:{C.ACCENT_DARK}; }}
            """)
            simpan.clicked.connect(self._validate_and_accept)
            self._btn_simpan = simpan
            btn_row.addStretch()

            if self._is_auto:
                # Data otomatis (les/pendaftaran/gaji): TIDAK BISA DIHAPUS, hanya bisa diedit.
                info = QWidget()
                info_lay = QHBoxLayout(info)
                info_lay.setContentsMargins(0, 0, 0, 0)
                info_lay.setSpacing(4)
                lock_icon = QLabel()
                lock_icon.setPixmap(svg_pixmap("lock", C.TEXT_MUTED_STRONG, 11))
                info_lay.addWidget(lock_icon)
                info_lay.addWidget(_lbl(
                    "Tidak bisa dihapus",
                    f"font-size:10px;color:{C.TEXT_MUTED_STRONG};background:transparent;"
                ))
                btn_row.addWidget(info)
                btn_row.addSpacing(8)
            else:
                # Mode Edit transaksi manual: ← Kembali | Hapus (merah) | Simpan (biru)
                hapus = QPushButton("Hapus")
                hapus.setFixedHeight(38); hapus.setCursor(Qt.PointingHandCursor)
                hapus.setStyleSheet(f"""
                    QPushButton {{ background:white; color:{C.DANGER_DARKER}; border:1.5px solid {C.DANGER};
                                  border-radius:8px; font-size:13px; font-weight:700;
                                  padding:0 16px; }}
                    QPushButton:hover {{ background:{C.DANGER_BG}; }}
                """)
                hapus.clicked.connect(self._konfirmasi_hapus)
                btn_row.addWidget(hapus)

            btn_row.addWidget(simpan)
        else:
            # Mode Tambah: ← Kembali | Simpan Transaksi
            batal = QPushButton(" Kembali")
            batal.setIcon(svg_icon("arrow-left", C.TEXT_MUTED, 13))
            batal.setFixedHeight(38); batal.setCursor(Qt.PointingHandCursor)
            batal.setStyleSheet(f"""
                QPushButton {{ background:white; color:{C.TEXT_MUTED}; border:1.5px solid {C.BORDER};
                              border-radius:8px; font-size:13px; padding:0 16px; }}
                QPushButton:hover {{ background:{C.SURFACE_ALT}; }}
            """)
            batal.clicked.connect(self.reject)

            simpan = QPushButton("Simpan Transaksi")
            simpan.setFixedHeight(38); simpan.setCursor(Qt.PointingHandCursor)
            simpan.setStyleSheet(f"""
                QPushButton {{ background:{C.ACCENT}; color:white; border:none;
                              border-radius:8px; font-size:13px; font-weight:700;
                              padding:0 20px; }}
                QPushButton:hover {{ background:{C.ACCENT_DARK}; }}
            """)
            simpan.clicked.connect(self._validate_and_accept)
            self._btn_simpan = simpan
            btn_row.addWidget(batal); btn_row.addStretch(); btn_row.addWidget(simpan)

        root.addLayout(btn_row)

        # Pre-fill jika mode edit
        if data:
            d = QDate.fromString(data.get("tanggal", ""), "dd/MM/yyyy")
            if d.isValid():
                self.date_edit.setDate(d)
            self._set_jenis("debit" if data.get("jenis") == "Debit" else "kredit")
            self.ket_input.setText(data.get("keterangan", ""))
            try:
                self.nominal_spin.setValue(int(data.get("nominal", 0)))
            except (ValueError, TypeError):
                pass

    def _konfirmasi_hapus(self):
        # Hanya untuk transaksi manual; dialog konfirmasi custom (bukan QMessageBox OS)
        if confirm_action(
            self, "Hapus Transaksi", "Yakin ingin menghapus transaksi ini?"
        ):
            self.done(2)   # kode 2 = sinyal hapus ke pemanggil

    def _field_label(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:11px;font-weight:700;color:{C.TEXT_MUTED};letter-spacing:0.3px;")
        return l

    def _input_style(self):
        return f"""
            QDateEdit, QLineEdit {{
                border:1.5px solid {C.BORDER}; border-radius:8px;
                padding-left:12px; background:{C.SURFACE_ALT};
                font-size:13px; color:{C.TEXT_PRIMARY_DARK};
            }}
            QDateEdit:focus, QLineEdit:focus {{
                border:1.5px solid {C.BORDER_STRONG}; background:white;
            }}
            QDateEdit::drop-down {{ border:none; }}
        """

    def _set_jenis(self, jenis):
        self._jenis = jenis
        self._update_jenis_style()

    def _update_jenis_style(self):
        da = self._jenis == "debit"
        self.btn_debit.setStyleSheet(f"""
            QPushButton {{
                border-radius:8px; font-size:12px; font-weight:bold; padding:0 14px;
                background:{f'{C.ACCENT_BG}' if da else f'{C.SURFACE_ALT}'};
                color:{f'{C.ACCENT_DARK}' if da else f'{C.TEXT_MUTED_STRONG}'};
                border:{'1.5px solid #93C5FD' if da else f'1.5px solid {C.BORDER}'};
            }}
        """)
        self.btn_kredit.setStyleSheet(f"""
            QPushButton {{
                border-radius:8px; font-size:12px; font-weight:bold; padding:0 14px;
                background:{f'{C.SURFACE_ALT}' if da else f'{C.DANGER_BG}'};
                color:{f'{C.TEXT_MUTED_STRONG}' if da else f'{C.DANGER_DARK}'};
                border:{f'1.5px solid {C.BORDER}' if da else f'1.5px solid {C.DANGER_BORDER}'};
            }}
        """)

    def _pick_bukti(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Bukti", "", "Images / PDF (*.jpg *.jpeg *.png *.pdf)"
        )
        if path:
            self._bukti_path = path
            self.bukti_btn.setText(f"  {os.path.basename(path)}")
            self.bukti_btn.setIcon(svg_icon("check", C.SUCCESS_HOVER, 14))
            self.bukti_btn.setStyleSheet(f"""
                QPushButton {{
                    border: 1.5px solid #BBF7D0; border-radius: 8px;
                    background: {C.SUCCESS_BG}; color: {C.SUCCESS_HOVER};
                    font-size: 13px; font-weight: 600; text-align: center;
                }}
                QPushButton:hover {{ background: {C.SUCCESS_BG_STRONG}; }}
            """)

    def _validate_and_accept(self):
        if not self.ket_input.text().strip():
            show_toast(self, "Perhatian", "Keterangan tidak boleh kosong!", "warning", anchor=getattr(self, "_btn_simpan", None))
            return
        if self.nominal_spin.value() <= 0:
            show_toast(self, "Perhatian", "Nominal harus lebih dari 0!", "warning", anchor=getattr(self, "_btn_simpan", None))
            return
        self.accept()

    def get_data(self):
        return {
            "tanggal":    self.date_edit.date().toString("dd/MM/yyyy"),
            "jenis":      "Debit" if self._jenis == "debit" else "Kredit",
            "keterangan": self.ket_input.text().strip(),
            "nominal":    self.nominal_spin.value(),
            "bukti":      self._bukti_path or "",
        }


#  PDF EXPORT  (reportlab)

def _save_pdf(path: str, bulan_label: str, rows: list, saldo_awal: int):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    PAGE_W, PAGE_H = A4
    MARGIN = 20 * mm

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=16 * mm, bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()

    def sty(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    s_title = sty("Title2",   fontSize=18, fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.TEXT_PRIMARY_DARK}"), alignment=TA_CENTER, spaceAfter=4)
    s_sub   = sty("Sub",      fontSize=11, textColor=colors.HexColor(f"{C.TEXT_MUTED}"),
                  alignment=TA_CENTER, spaceAfter=16)
    s_label = sty("CardLbl",  fontSize=8,  fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.TEXT_FAINT}"))
    s_val_b = sty("CardValB", fontSize=16, fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.ACCENT_DARK}"))
    s_val_r = sty("CardValR", fontSize=16, fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.DANGER_DARK}"))
    s_val_d = sty("CardValD", fontSize=16, fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.TEXT_PRIMARY_DARK}"))
    s_th    = sty("TH",       fontSize=8,  fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.TEXT_FAINT}"))
    s_cell  = sty("Cell",     fontSize=9,  textColor=colors.HexColor(f"{C.TEXT_BODY}"))
    s_green = sty("Green",    fontSize=9,  fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.SUCCESS_HOVER}"), alignment=TA_RIGHT)
    s_red   = sty("Red",      fontSize=9,  fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.DANGER_DARK}"), alignment=TA_RIGHT)
    s_saldo = sty("Saldo",    fontSize=9,  fontName="Helvetica-Bold",
                  textColor=colors.HexColor(f"{C.TEXT_PRIMARY_DARK}"), alignment=TA_RIGHT)
    s_dash  = sty("Dash",     fontSize=9,  textColor=colors.HexColor(f"{C.BORDER_STRONG}"),
                  alignment=TA_RIGHT)
    s_ket   = sty("Ket",      fontSize=8,  textColor=colors.HexColor(f"{C.TEXT_MUTED}"))

    story = []

    story.append(Paragraph("MELODY VIOLIN SCHOOL", sty("MVS",
        fontSize=10, fontName="Helvetica-Bold",
        textColor=colors.HexColor(f"{C.DANGER}"), alignment=TA_CENTER)))
    story.append(Paragraph("Laporan Keuangan Bulanan", s_title))
    story.append(Paragraph(f"Periode: {bulan_label}", s_sub))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor(f"{C.BORDER}"), spaceAfter=16))

    tot_d = sum(r["nominal"] for r in rows if r["jenis"] == "Debit")
    tot_k = sum(r["nominal"] for r in rows if r["jenis"] == "Kredit")
    laba  = tot_d - tot_k

    card_data = [[
        [Paragraph("TOTAL PEMASUKAN",   s_label), Paragraph(_fmt_rp(tot_d), s_val_b)],
        [Paragraph("TOTAL PENGELUARAN", s_label), Paragraph(_fmt_rp(tot_k), s_val_r)],
        [Paragraph("LABA BERSIH",       s_label), Paragraph(_fmt_rp(laba),  s_val_d)],
    ]]
    avail = PAGE_W - 2 * MARGIN
    col_w = avail / 3
    card_table = Table(card_data, colWidths=[col_w, col_w, col_w])
    card_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(f"{C.SURFACE_ALT}")),
        ("BOX",         (0, 0), (-1, -1), 0.5, colors.HexColor(f"{C.BORDER}")),
        ("LINEAFTER",   (0, 0), (1, 0),   0.5, colors.HexColor(f"{C.BORDER}")),
        ("TOPPADDING",  (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING",(0,0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",(0, 0), (-1, -1), 16),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 20))

    DATE_W = 22 * mm
    KET_W  = avail - DATE_W - 24 * mm - 30 * mm - 30 * mm - 28 * mm
    SRC_W  = 24 * mm
    NUM_W  = 30 * mm
    SAL_W  = 28 * mm

    header = [
        Paragraph("TANGGAL",     s_th),
        Paragraph("KETERANGAN",  s_th),
        Paragraph("SUMBER",      s_th),
        Paragraph("DEBIT",       ParagraphStyle("THR", parent=s_th, alignment=TA_RIGHT)),
        Paragraph("KREDIT",      ParagraphStyle("THR", parent=s_th, alignment=TA_RIGHT)),
        Paragraph("SALDO",       ParagraphStyle("THR", parent=s_th, alignment=TA_RIGHT)),
    ]
    tbl_data = [header]

    saldo = saldo_awal
    row_colors = []

    for i, row in enumerate(rows):
        debit  = row["nominal"] if row["jenis"] == "Debit"  else 0
        kredit = row["nominal"] if row["jenis"] == "Kredit" else 0
        saldo  = saldo + debit - kredit

        ket_raw = row["keterangan"]
        sumber  = _tag_label(ket_raw)
        ket_bersih = _strip_tag(ket_raw)

        d_para = Paragraph(_fmt_rp(debit),  s_green) if debit  else Paragraph("–", s_dash)
        k_para = Paragraph(_fmt_rp(kredit), s_red)   if kredit else Paragraph("–", s_dash)

        tbl_data.append([
            Paragraph(row["tanggal"],  s_cell),
            Paragraph(ket_bersih,      s_ket),
            Paragraph(sumber,          s_cell),
            d_para,
            k_para,
            Paragraph(_fmt_rp(saldo), s_saldo),
        ])
        bg = colors.white if i % 2 == 0 else colors.HexColor("#FAFAFA")
        row_colors.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))

    trans_table = Table(
        tbl_data,
        colWidths=[DATE_W, KET_W, SRC_W, NUM_W, NUM_W, SAL_W],
        repeatRows=1,
    )
    trans_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.white),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, colors.HexColor(f"{C.BORDER}")),
        ("LINEBELOW",     (0, 1), (-1, -1), 0.3, colors.HexColor(f"{C.SURFACE_HOVER}")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ] + row_colors))
    story.append(trans_table)

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor(f"{C.BORDER}"), spaceAfter=8))
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(
        f"Dicetak pada {ts}",
        sty("Footer", fontSize=8, textColor=colors.HexColor(f"{C.TEXT_FAINT}"),
            alignment=TA_RIGHT)
    ))

    doc.build(story)


# ─── Helper keterangan tag ────────────────────────────────────────────────────

def _tag_label(ket: str) -> str:
    if ket.startswith(_TAG_LES):
        return "Les"
    if ket.startswith(_TAG_PENDAFTARAN):
        return "Pendaftaran"
    if ket.startswith(_TAG_GAJI_GURU):
        return "Gaji Guru"
    if ket.startswith(_TAG_GAJI_ADMIN):
        return "Gaji Admin"
    return "Manual"


def _strip_tag(ket: str) -> str:
    """Sederhanakan keterangan agar mudah dibaca di tabel."""
    # Hapus tag awalan
    for tag in (_TAG_LES, _TAG_PENDAFTARAN, _TAG_GAJI_GURU, _TAG_GAJI_ADMIN):
        if ket.startswith(tag):
            ket = ket[len(tag):].strip()
            break

    # Hapus suffix "| ID:xx"
    if "| ID:" in ket:
        ket = ket[:ket.rfind("| ID:")].strip()

    parts = [p.strip() for p in ket.split("|")]

    # Les: "MV-2026-010 – Andini Putri | Biola | 4x sesi"
    #   → "Andini Putri – Biola (4x sesi)"
    if len(parts) >= 3 and "sesi" in parts[2].lower():
        nama_no  = parts[0]   # "MV-2026-010 – Andini Putri"
        kursus   = parts[1]   # "Biola"
        sesi     = parts[2]   # "4x sesi"
        # Ambil nama saja (setelah "–")
        if "–" in nama_no:
            nama = nama_no.split("–", 1)[1].strip()
        elif "-" in nama_no:
            nama = nama_no.split("-", 1)[-1].strip()
        else:
            nama = nama_no
        return f"{nama} – {kursus} ({sesi})"

    # Pendaftaran: "MV-2026-010 – Andini Putri | Biaya Pendaftaran"
    #   → "Andini Putri – Pendaftaran"
    if len(parts) >= 2 and "pendaftaran" in parts[1].lower():
        nama_no = parts[0]
        if "–" in nama_no:
            nama = nama_no.split("–", 1)[1].strip()
        elif "-" in nama_no:
            nama = nama_no.split("-", 1)[-1].strip()
        else:
            nama = nama_no
        return f"{nama} – Pendaftaran"

    # Gaji Guru/Admin: "Budi | Februari 2026 | 8 sesi"
    #   → "Budi – Februari 2026"
    if len(parts) >= 2:
        nama    = parts[0]
        periode = parts[1]
        return f"{nama} – {periode}"

    return ket


#  DIALOG: PRINT PREVIEW + FILTER BULAN

class PrintPreviewDialog(QDialog):
    def __init__(self, parent=None, bulan="", rows=None, saldo_awal=0):
        super().__init__(parent)
        self.setWindowTitle("Laporan Keuangan Bulanan")
        self.setMinimumSize(760, 640)
        self.setStyleSheet("QDialog { background:white; }")

        self._all_rows   = rows or []
        self._saldo_awal = saldo_awal

        parts = (bulan or "").split()
        self._sel_month  = QDate.currentDate().month()
        self._sel_year   = QDate.currentDate().year()
        if len(parts) == 2:
            try:
                self._sel_month = _BULAN_NAMES.index(parts[0]) + 1
            except ValueError:
                pass
            try:
                self._sel_year = int(parts[1])
            except ValueError:
                pass

        self._build()
        self._refresh_preview()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top filter bar
        top = QFrame()
        top.setFixedHeight(54)
        top.setStyleSheet(f"QFrame{{background:white;border-bottom:1px solid {C.SURFACE_HOVER};}}"
                          "QLabel{background:transparent;}")
        tl = QHBoxLayout(top); tl.setContentsMargins(24, 0, 24, 0); tl.setSpacing(10)
        tl.addWidget(_lbl("Periode:", f"font-size:12px;font-weight:600;color:{C.TEXT_MUTED};"))

        cb_style = f"""
            QComboBox {{ border:1.5px solid {C.BORDER}; border-radius:7px;
                background:{C.SURFACE_ALT}; padding:0 10px; font-size:12px; color:{C.TEXT_PRIMARY_DARK};
                height:32px; min-width:110px; }}
            QComboBox:focus {{ border-color:{C.BORDER_STRONG}; background:white; }}
            QComboBox::drop-down {{ border:none; width:20px; }}
            QComboBox QAbstractItemView {{ selection-background-color:{C.ACCENT_BG}; color:{C.TEXT_PRIMARY_DARK}; }}
        """
        def _popup_hover_qss():
            return f"""
                QListView {{ border:1px solid {C.BORDER}; border-radius:0px; background:white;
                            padding:4px; outline:none; }}
                QListView::item {{ min-height:26px; padding-left:6px; border-radius:4px; }}
                QListView::item:hover {{ background-color:{C.ACCENT}; color:white; }}
                QListView::item:selected {{ background-color:{C.ACCENT}; color:white; }}
            """

        self.cb_bulan = QComboBox()
        self.cb_bulan.addItems(_BULAN_NAMES)
        self.cb_bulan.setCurrentIndex(self._sel_month - 1)
        self.cb_bulan.setStyleSheet(cb_style)
        # Style langsung ke popup view agar item yang dilewati kursor ke-highlight
        self.cb_bulan.view().setStyleSheet(_popup_hover_qss())
        # setMouseTracking wajib diaktifkan agar highlight item:hover ikut bergerak
        self.cb_bulan.view().setMouseTracking(True)
        self.cb_bulan.view().viewport().setMouseTracking(True)
        self.cb_bulan.currentIndexChanged.connect(self._on_filter_changed)
        tl.addWidget(self.cb_bulan)

        self.sp_tahun = QSpinBox()
        self.sp_tahun.setRange(2000, 2100)
        self.sp_tahun.setValue(self._sel_year)
        self.sp_tahun.setFixedHeight(32); self.sp_tahun.setFixedWidth(80)
        self.sp_tahun.setStyleSheet(f"""
            QSpinBox {{ border:1.5px solid {C.BORDER}; border-radius:7px;
                background:{C.SURFACE_ALT}; padding:0 8px; font-size:12px; color:{C.TEXT_PRIMARY_DARK}; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width:18px; }}
        """)
        self.sp_tahun.valueChanged.connect(self._on_filter_changed)
        tl.addWidget(self.sp_tahun)
        tl.addStretch()
        root.addWidget(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border:none; }")
        root.addWidget(self.scroll, 1)

        # Bottom bar
        bar = QFrame(); bar.setFixedHeight(60)
        bar.setStyleSheet(f"QFrame{{background:white;border-top:1px solid {C.SURFACE_HOVER};}}")
        bl = QHBoxLayout(bar); bl.setContentsMargins(24, 0, 24, 0); bl.setSpacing(10)

        kembali = QPushButton(" Kembali")
        kembali.setIcon(svg_icon("arrow-left", C.TEXT_MUTED, 13))
        kembali.setFixedHeight(36); kembali.setCursor(Qt.PointingHandCursor)
        kembali.setStyleSheet(f"""
            QPushButton{{background:white;color:{C.TEXT_MUTED};border:1.5px solid {C.BORDER};
                border-radius:8px;font-size:12px;padding:0 18px;}}
            QPushButton:hover{{background:{C.SURFACE_ALT};}}
        """)
        kembali.clicked.connect(self.reject)

        self.cetak_btn = QPushButton("Simpan PDF")
        self.cetak_btn.setFixedHeight(36); self.cetak_btn.setCursor(Qt.PointingHandCursor)
        self.cetak_btn.setStyleSheet(f"""
            QPushButton{{background:{C.ACCENT};color:white;border:none;
                border-radius:8px;font-size:12px;font-weight:700;padding:0 20px;}}
            QPushButton:hover{{background:{C.ACCENT_DARK};}}
        """)
        self.cetak_btn.clicked.connect(self._do_save_pdf)
        bl.addStretch(); bl.addWidget(kembali); bl.addWidget(self.cetak_btn)
        root.addWidget(bar)

    def _on_filter_changed(self):
        self._sel_month = self.cb_bulan.currentIndex() + 1
        self._sel_year  = self.sp_tahun.value()
        self._refresh_preview()

    def _filtered_rows(self):
        result = []
        for row in self._all_rows:
            try:
                d = _parse_dt(row["tanggal"])
                if d.month == self._sel_month and d.year == self._sel_year:
                    result.append(row)
            except ValueError:
                pass
        return sorted(result, key=lambda r: _parse_dt(r["tanggal"]))

    def _bulan_label(self):
        return f"{_BULAN_NAMES[self._sel_month - 1]} {self._sel_year}"

    def _refresh_preview(self):
        rows = self._filtered_rows()
        self.scroll.setWidget(self._build_preview_body(rows))

    def _build_preview_body(self, rows):
        body = QWidget(); body.setStyleSheet("background:white;")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(48, 40, 48, 40); bv.setSpacing(0)

        h = _lbl("Laporan Keuangan Bulanan",
                 f"font-size:20px;font-weight:bold;color:{C.TEXT_PRIMARY_DARK};")
        h.setAlignment(Qt.AlignCenter)
        bv.addWidget(h); bv.addSpacing(4)
        p = _lbl(f"Periode: {self._bulan_label()}", f"font-size:12px;color:{C.TEXT_MUTED};")
        p.setAlignment(Qt.AlignCenter)
        bv.addWidget(p); bv.addSpacing(24)

        tot_d = sum(r["nominal"] for r in rows if r["jenis"] == "Debit")
        tot_k = sum(r["nominal"] for r in rows if r["jenis"] == "Kredit")
        laba  = tot_d - tot_k

        summ = QFrame()
        summ.setStyleSheet(f"QFrame{{background:{C.SURFACE_ALT};border-radius:10px;border:none;}}"
                           "QLabel{border:none;background:transparent;}")
        sl = QHBoxLayout(summ); sl.setContentsMargins(0, 0, 0, 0)
        for i, (title, val, color) in enumerate([
            ("TOTAL PEMASUKAN",   _fmt_rp(tot_d), f"{C.ACCENT_DARK}"),
            ("TOTAL PENGELUARAN", _fmt_rp(tot_k), f"{C.DANGER_DARK}"),
            ("LABA BERSIH",       _fmt_rp(laba),  f"{C.TEXT_PRIMARY_DARK}"),
        ]):
            cell = QFrame()
            cl = QVBoxLayout(cell); cl.setContentsMargins(22, 16, 22, 16); cl.setSpacing(4)
            cl.addWidget(_lbl(title,
                f"font-size:10px;font-weight:700;color:{C.TEXT_MUTED_STRONG};letter-spacing:0.5px;"))
            cl.addWidget(_lbl(val, f"font-size:17px;font-weight:700;color:{color};"))
            sl.addWidget(cell, 1)
            if i < 2:
                sep = QFrame(); sep.setFixedWidth(1)
                sep.setStyleSheet(f"background:{C.BORDER};")
                sl.addWidget(sep)
        bv.addWidget(summ); bv.addSpacing(24)

        if rows:
            cols = ["TANGGAL", "KETERANGAN", "SUMBER", "DEBIT", "KREDIT", "SALDO"]
            tbl = _make_table(cols)
            base_dlg  = _ColorDelegate(tbl)
            right_dlg = _RightDelegate(tbl)
            for c in range(6):
                tbl.setItemDelegateForColumn(c, right_dlg if c in (3, 4, 5) else base_dlg)

            saldo = self._saldo_awal
            tbl.setRowCount(len(rows))
            for r, row in enumerate(rows):
                tbl.setRowHeight(r, 44)
                debit  = row["nominal"] if row["jenis"] == "Debit"  else 0
                kredit = row["nominal"] if row["jenis"] == "Kredit" else 0
                saldo  = saldo + debit - kredit

                tbl.setItem(r, 0, QTableWidgetItem(row["tanggal"]))
                tbl.setItem(r, 1, QTableWidgetItem(_strip_tag(row["keterangan"])))
                tbl.setItem(r, 2, QTableWidgetItem(_tag_label(row["keterangan"])))

                d_item = QTableWidgetItem(_fmt_rp(debit) if debit else "–")
                if debit: d_item.setData(Qt.ForegroundRole, f"{C.SUCCESS_HOVER}")
                tbl.setItem(r, 3, d_item)

                k_item = QTableWidgetItem(_fmt_rp(kredit) if kredit else "–")
                if kredit: k_item.setData(Qt.ForegroundRole, f"{C.DANGER_DARK}")
                tbl.setItem(r, 4, k_item)

                s_item = QTableWidgetItem(_fmt_rp(saldo))
                s_item.setData(Qt.FontRole, True)
                tbl.setItem(r, 5, s_item)

            tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tbl.setFixedHeight(36 + len(rows) * 44)
            bv.addWidget(tbl)
        else:
            empty = _lbl("Tidak ada transaksi pada periode ini.",
                         f"font-size:13px;color:{C.TEXT_MUTED_STRONG};")
            empty.setAlignment(Qt.AlignCenter)
            bv.addSpacing(32); bv.addWidget(empty)

        bv.addStretch()
        return body

    def _do_save_pdf(self):
        default_name = f"Laporan_{_BULAN_NAMES[self._sel_month-1]}_{self._sel_year}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan PDF", default_name, "PDF Files (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        rows = self._filtered_rows()
        try:
            _save_pdf(path, self._bulan_label(), rows, self._saldo_awal)
            show_toast(self, "Berhasil", f"PDF berhasil disimpan: {path}", "success", anchor=self.cetak_btn)
        except Exception as e:
            show_toast(self, "Gagal", f"Gagal menyimpan PDF: {e}", "error", anchor=self.cetak_btn)


#  WIDGET UTAMA: LAPORAN KEUANGAN

class LaporanKeuanganAdminWidget(QWidget):
    """
    Widget laporan keuangan dengan dua sumber data:
      1. Otomatis dari DB (les, pendaftaran, gaji guru/admin) — disinkronkan
         secara otomatis setiap kali data diperbarui/tabel dimuat ulang,
         tanpa perlu tombol manual.
      2. Input manual via tombol "+ Tambah Transaksi"
    Semua data tersimpan di tabel transaksi_keuangan.
    """

    _SALDO_AWAL = 0   # Saldo awal buku kas (bisa diubah dari pengaturan)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{C.SURFACE_ALT};")
        self.init_ui()
        self._refresh_table()

    def showEvent(self, event):
        """Muat ulang & sinkron data setiap kali halaman Laporan Keuangan dibuka."""
        super().showEvent(event)
        self._refresh_table()

    def init_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(32, 28, 32, 28)
        v.setSpacing(18)

        # ── Header row ────────────────────────────────────────────────
        h = QHBoxLayout()
        col = QVBoxLayout(); col.setSpacing(2)
        col.addWidget(_lbl("Laporan Keuangan",
                           f"font-size:20px;font-weight:700;color:{C.TEXT_PRIMARY_DARK};background:transparent;"))
        col.addWidget(_lbl("Catat dan pantau seluruh arus kas",
                           f"font-size:12px;color:{C.TEXT_MUTED_STRONG};background:transparent;"))
        h.addLayout(col); h.addStretch()

        # Tombol Laporan PDF
        lap_btn = QPushButton(" Laporan PDF")
        lap_btn.setIcon(svg_icon("file-text", C.ACCENT, 14))
        lap_btn.setFixedHeight(36)
        lap_btn.setCursor(Qt.PointingHandCursor)
        lap_btn.setStyleSheet(f"""
            QPushButton{{background:white;color:{C.ACCENT};border:1.5px solid {C.ACCENT_BORDER};
                border-radius:8px;font-size:12px;font-weight:600;padding:0 16px;}}
            QPushButton:hover{{background:{C.ACCENT_BG};}}
        """)
        lap_btn.clicked.connect(self._show_print_preview)

        # Tombol Tambah Manual
        tambah_btn = QPushButton("+ Tambah Transaksi")
        tambah_btn.setFixedHeight(36)
        tambah_btn.setCursor(Qt.PointingHandCursor)
        tambah_btn.setStyleSheet(primary_button_style())
        tambah_btn.clicked.connect(self._tambah)

        h.addWidget(lap_btn)
        h.addSpacing(6)
        h.addWidget(tambah_btn)
        v.addLayout(h)

        # ── Summary cards ─────────────────────────────────────────────
        saldo_row = QHBoxLayout(); saldo_row.setSpacing(14)
        card_specs = [
            ("saldo",    "Saldo Saat Ini",    "Rp 0", f"{C.TEXT_PRIMARY_DARK}"),
            ("masuk",    "Total Pemasukan",   "Rp 0", f"{C.SUCCESS_HOVER}"),
            ("keluar",   "Total Pengeluaran", "Rp 0", f"{C.DANGER_DARK}"),
        ]
        self._sum_cards = {}
        for key, title, val, accent in card_specs:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame{{background:white;border-radius:16px;border:1px solid {C.BORDER_LIGHT};}}
                QLabel{{border:none;background:transparent;}}
            """)
            cl = QVBoxLayout(card); cl.setContentsMargins(20, 16, 20, 16); cl.setSpacing(6)
            t_lbl = _lbl(title.upper(),
                f"font-size:10px;font-weight:700;color:{C.TEXT_MUTED_STRONG};letter-spacing:0.5px;")
            v_lbl = _lbl(val, f"font-size:18px;font-weight:700;color:{accent};")
            cl.addWidget(t_lbl); cl.addWidget(v_lbl)
            self._sum_cards[key] = (v_lbl, accent)
            saldo_row.addWidget(card, 1)
        v.addLayout(saldo_row)

        # ── Filter + tabel — pakai style_combo() standar dari theme.py agar konsisten ──
        filter_row = QHBoxLayout(); filter_row.setSpacing(10)
        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet(f"font-size:13px;color:{C.TEXT_BODY};background:transparent;")
        filter_row.addWidget(filter_lbl)

        self._filter_jenis = QComboBox()
        self._filter_jenis.addItems(["Semua", "Debit (Masuk)", "Kredit (Keluar)"])
        self._filter_jenis.setFixedHeight(38)
        self._filter_jenis.setMinimumWidth(140)
        self._filter_jenis.setCursor(Qt.PointingHandCursor)
        style_combo(self._filter_jenis)
        self._filter_jenis.currentIndexChanged.connect(self._refresh_table)

        self._filter_sumber = QComboBox()
        self._filter_sumber.addItems(
            ["Semua Sumber", "Les", "Pendaftaran", "Gaji Guru", "Gaji Admin", "Manual"]
        )
        self._filter_sumber.setFixedHeight(38)
        self._filter_sumber.setMinimumWidth(140)
        self._filter_sumber.setCursor(Qt.PointingHandCursor)
        style_combo(self._filter_sumber)
        self._filter_sumber.currentIndexChanged.connect(self._refresh_table)

        self._filter_bulan = QComboBox()
        self._filter_bulan.addItem("Semua Bulan")
        self._filter_bulan.addItems(_BULAN_NAMES)
        self._filter_bulan.setCurrentIndex(QDate.currentDate().month())
        self._filter_bulan.setFixedHeight(38)
        self._filter_bulan.setMinimumWidth(140)
        self._filter_bulan.setCursor(Qt.PointingHandCursor)
        style_combo(self._filter_bulan)
        self._filter_bulan.currentIndexChanged.connect(self._refresh_table)

        self._filter_tahun = QSpinBox()
        self._filter_tahun.setRange(2020, 2100)
        self._filter_tahun.setValue(QDate.currentDate().year())
        self._filter_tahun.setFixedHeight(38); self._filter_tahun.setFixedWidth(90)
        self._filter_tahun.setCursor(Qt.PointingHandCursor)
        self._filter_tahun.setStyleSheet(f"""
            QSpinBox{{border:1.5px solid {C.ACCENT_BORDER};border-radius:10px;
                background:white;padding:0 10px;font-size:13px;color:{C.TEXT_PRIMARY};}}
            QSpinBox:focus{{border:2px solid {C.ACCENT};}}
        """)
        self._filter_tahun.valueChanged.connect(self._refresh_table)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Cari keterangan…")
        self._search.addAction(svg_icon("search", C.TEXT_FAINT, 15), QLineEdit.LeadingPosition)
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                border:1.5px solid {C.BORDER}; border-radius:8px;
                background:{C.SURFACE_ALT}; padding-left:12px;
                font-size:12px; color:{C.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{ border:1.5px solid {C.ACCENT}; background:white; }}
        """)
        self._search.textChanged.connect(self._refresh_table)

        filter_row.addWidget(self._filter_jenis)
        filter_row.addWidget(self._filter_sumber)
        filter_row.addWidget(self._filter_bulan)
        filter_row.addWidget(self._filter_tahun)
        filter_row.addStretch()
        filter_row.addWidget(self._search)
        v.addLayout(filter_row)

        # ── Tabel card ────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet("QFrame{background:white;border-radius:14px;border:none;}")
        cv = QVBoxLayout(card); cv.setContentsMargins(0, 0, 0, 0); cv.setSpacing(0)

        cols = ["NO", "TANGGAL", "KETERANGAN", "SUMBER",
                "DEBIT (+)", "KREDIT (-)", "SALDO", "BUKTI", "AKSI"]
        self.table = _make_table(cols, fixed_last=[(0, 44), (7, 56), (8, 80)])

        base_dlg  = _ColorDelegate(self.table)
        right_dlg = _RightDelegate(self.table)
        for c in range(9):
            self.table.setItemDelegateForColumn(
                c, right_dlg if c in (4, 5, 6) else base_dlg
            )
        cv.addWidget(self.table)

        # Pagination info
        pg_bar = QHBoxLayout(); pg_bar.setContentsMargins(20, 12, 20, 16)
        self._pg_info = _lbl("", f"font-size:11px;color:{C.TEXT_MUTED_STRONG};")
        pg_bar.addWidget(self._pg_info); pg_bar.addStretch()
        cv.addLayout(pg_bar)

        v.addWidget(card)

    # DATA

    def _load_all(self) -> list:
        """Ambil semua transaksi dari DB, kembalikan sebagai list dict."""
        from database import DB
        rows = DB.fetch_all(
            "SELECT * FROM transaksi_keuangan ORDER BY tanggal DESC, id DESC"
        )
        result = []
        for r in rows:
            result.append({
                "id":         r["id"],
                "tanggal":    _to_display(r["tanggal"]),
                "jenis":      r["jenis"],
                "keterangan": r["keterangan"],
                "nominal":    r["nominal"],
                "bukti":      r["bukti_path"] or "",
            })
        return result

    def _refresh_table(self):
        self._auto_sinkron()
        all_data = self._load_all()

        # ── Filter ───────────────────────────────────────────────────
        jenis_f  = self._filter_jenis.currentText()
        sumber_f = self._filter_sumber.currentText()
        bulan_i  = self._filter_bulan.currentIndex()   # 0 = Semua
        tahun_f  = self._filter_tahun.value()
        kw       = self._search.text().lower().strip()

        filtered = []
        for row in all_data:
            # Jenis
            if jenis_f == "Debit (Masuk)"   and row["jenis"] != "Debit":  continue
            if jenis_f == "Kredit (Keluar)"  and row["jenis"] != "Kredit": continue

            # Sumber
            sumber = _tag_label(row["keterangan"])
            if sumber_f != "Semua Sumber" and sumber != sumber_f: continue

            # Bulan / tahun
            if bulan_i > 0:
                try:
                    dt = _parse_dt(row["tanggal"])
                    if dt.month != bulan_i or dt.year != tahun_f:
                        continue
                except ValueError:
                    pass

            # Kata kunci
            if kw and kw not in row["keterangan"].lower():
                continue

            filtered.append(row)

        # ── Isi tabel ────────────────────────────────────────────────
        self.table.setRowCount(0)

        # Hitung saldo per baris dari seluruh data (bukan hanya filtered)
        # supaya saldo kumulatif benar
        all_sorted = sorted(all_data, key=lambda r: (r["tanggal"][:10], r["id"]))
        saldo_map = {}
        s = self._SALDO_AWAL
        for row in all_sorted:
            if row["jenis"] == "Debit":
                s += row["nominal"]
            else:
                s -= row["nominal"]
            saldo_map[row["id"]] = s

        # Tampilkan descending (terbaru di atas)
        for row in filtered:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 50)

            debit  = row["nominal"] if row["jenis"] == "Debit"  else 0
            kredit = row["nominal"] if row["jenis"] == "Kredit" else 0
            saldo_row = saldo_map.get(row["id"], 0)

            # Kolom 0: Nomor urut
            no_item = QTableWidgetItem(str(r + 1))
            no_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.table.setItem(r, 0, no_item)

            self.table.setItem(r, 1, QTableWidgetItem(row["tanggal"]))
            self.table.setItem(r, 2, QTableWidgetItem(_strip_tag(row["keterangan"])))

            # Badge sumber
            sumber_lbl = _tag_label(row["keterangan"])
            src_item = QTableWidgetItem(sumber_lbl)
            src_color = {
                "Les":          f"{C.ACCENT_DARKER}",
                "Pendaftaran":  "#6D28D9",
                "Gaji Guru":    f"{C.DANGER_DARK}",
                "Gaji Admin":   "#92400E",
                "Manual":       f"{C.TEXT_BODY}",
            }.get(sumber_lbl, f"{C.TEXT_BODY}")
            src_item.setForeground(QColor(src_color))
            self.table.setItem(r, 3, src_item)

            d_item = QTableWidgetItem(_fmt_rp(debit) if debit else "–")
            if debit:
                d_item.setData(Qt.ForegroundRole, f"{C.SUCCESS_HOVER}")
                d_item.setData(Qt.FontRole, True)
            self.table.setItem(r, 4, d_item)

            k_item = QTableWidgetItem(_fmt_rp(kredit) if kredit else "–")
            if kredit:
                k_item.setData(Qt.ForegroundRole, f"{C.DANGER_DARK}")
                k_item.setData(Qt.FontRole, True)
            self.table.setItem(r, 5, k_item)

            s_item = QTableWidgetItem(_fmt_rp(saldo_row))
            s_item.setData(Qt.FontRole, True)
            self.table.setItem(r, 6, s_item)

            # Bukti — auto-generate marker preview untuk semua jenis transaksi auto
            bukti_path = row["bukti"] or ""
            sumber_lbl_bukti = _tag_label(row["keterangan"])

            if not bukti_path:
                ket_raw = row["keterangan"]
                if sumber_lbl_bukti == "Gaji Admin":
                    # "[GAJI-ADMIN] Admin Nia | Februari 2026 | ..."
                    parts_ket = [p.strip() for p in ket_raw.replace(_TAG_GAJI_ADMIN, "").split("|")]
                    nama_adm    = parts_ket[0] if len(parts_ket) > 0 else ""
                    periode_adm = parts_ket[1] if len(parts_ket) > 1 else ""
                    bukti_path = f"SLIP-ADMIN:{nama_adm}:{periode_adm}"

                elif sumber_lbl_bukti == "Gaji Guru":
                    # "[GAJI-GURU] Ms. Happy | Februari 2026 | 4 sesi | ID:..."
                    parts_ket = [p.strip() for p in ket_raw.replace(_TAG_GAJI_GURU, "").split("|")]
                    nama_gr     = parts_ket[0] if len(parts_ket) > 0 else ""
                    periode_gr  = parts_ket[1] if len(parts_ket) > 1 else ""
                    bukti_path = f"SLIP-GURU:{nama_gr}:{periode_gr}"

                elif sumber_lbl_bukti == "Les":
                    bukti_path = f"KUITANSI-LES:{ket_raw}"

                elif sumber_lbl_bukti == "Pendaftaran":
                    bukti_path = f"KUITANSI-PENDAFTARAN:{ket_raw}"

            tooltip_map = {
                "SLIP-ADMIN":         "Lihat Slip Gaji Admin",
                "SLIP-GURU":          "Lihat Slip Gaji Guru",
                "KUITANSI-LES":       "Lihat Kuitansi Les",
                "KUITANSI-PENDAFTARAN": "Lihat Kuitansi Pendaftaran",
            }
            tip = ""
            for prefix, label in tooltip_map.items():
                if bukti_path.startswith(prefix):
                    tip = label; break

            bukti_w = QWidget(); bl2 = QHBoxLayout(bukti_w)
            bl2.setContentsMargins(4, 4, 4, 4); bl2.setAlignment(Qt.AlignCenter)
            ic = QPushButton("")
            if bukti_path:
                ic.setIcon(svg_icon("paperclip", C.TEXT_MUTED_STRONG, 14))
            ic.setFixedSize(26, 26); ic.setCursor(Qt.PointingHandCursor)
            ic.setStyleSheet("QPushButton{border:none;background:transparent;}"
                             f"QPushButton:hover{{background:{C.SURFACE_HOVER};border-radius:5px;}}")
            if bukti_path:
                ic.setToolTip(tip or bukti_path)
                ic.clicked.connect(lambda _, p=bukti_path: self._open_bukti(p))
            bl2.addWidget(ic)
            self.table.setCellWidget(r, 7, bukti_w)

            # Aksi — satu tombol Edit untuk semua transaksi
            aksi_w = QWidget(); al = QHBoxLayout(aksi_w)
            al.setContentsMargins(4, 4, 4, 4); al.setAlignment(Qt.AlignCenter)

            is_auto = _tag_label(row["keterangan"]) != "Manual"
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedHeight(32); edit_btn.setMinimumWidth(64)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(action_button_style())
            edit_btn.clicked.connect(lambda _, d=row, auto=is_auto: self._edit(d, auto))
            al.addWidget(edit_btn)

            self.table.setCellWidget(r, 8, aksi_w)

        n = len(filtered)
        self._pg_info.setText(f"Menampilkan {n} transaksi")

        # Update summary cards
        tot_d = sum(r["nominal"] for r in filtered if r["jenis"] == "Debit")
        tot_k = sum(r["nominal"] for r in filtered if r["jenis"] == "Kredit")
        saldo_akhir = self._SALDO_AWAL + tot_d - tot_k

        self._sum_cards["saldo"][0].setText(_fmt_rp(saldo_akhir))
        self._sum_cards["masuk"][0].setText(_fmt_rp(tot_d))
        self._sum_cards["keluar"][0].setText(_fmt_rp(tot_k))

        saldo_color = f"{C.SUCCESS_HOVER}" if saldo_akhir >= 0 else f"{C.DANGER_DARK}"
        self._sum_cards["saldo"][0].setStyleSheet(
            f"font-size:18px;font-weight:700;color:{saldo_color};"
        )

    # AKSI

    def _auto_sinkron(self):
        """
        Sinkronisasi otomatis & senyap (tanpa tombol) dari sumber DB
        (les, pendaftaran, gaji guru/admin) ke transaksi_keuangan.
        Dipanggil setiap kali tabel dimuat/diperbarui sehingga data
        selalu ter-update tanpa perlu aksi manual dari pengguna.
        """
        try:
            _sinkron_db()
        except Exception:
            # Gagal sinkron tidak boleh mengganggu tampilan laporan
            pass

    def _tambah(self):
        dlg = TambahTransaksiDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            d = dlg.get_data()
            self._simpan_manual(d)
            show_toast(self, "Berhasil", "Data Berhasil Disimpan", "success")

    def _edit(self, data, is_auto: bool = False):
        dlg = TambahTransaksiDialog(self, data, is_auto=is_auto)
        result = dlg.exec_()
        if result == QDialog.Accepted:
            d = dlg.get_data()
            self._update_manual(data["id"], d)
            show_toast(self, "Berhasil", "Data Berhasil Disimpan", "success")
        elif result == 2:   # kode hapus dari dialog
            self._hapus(data["id"], is_auto)

    def _hapus(self, transaksi_id: int, is_auto: bool = False):
        if is_auto:
            show_toast(
                self, "Gagal",
                "Transaksi otomatis tidak dapat dihapus dari sini. Hapus dari modul sumber.",
                "error"
            )
            return

        if confirm_action(
            self, "Hapus Transaksi", "Yakin ingin menghapus transaksi ini?"
        ):
            from database import DB
            DB.execute("DELETE FROM transaksi_keuangan WHERE id=?", (transaksi_id,))
            self._refresh_table()
            show_toast(self, "Berhasil", "Transaksi Berhasil Dihapus", "success")

    def _simpan_manual(self, d: dict):
        from database import DB
        DB.execute(
            "INSERT INTO transaksi_keuangan(tanggal,jenis,keterangan,nominal,bukti_path)"
            " VALUES(?,?,?,?,?)",
            (d["tanggal"], d["jenis"], d["keterangan"], d["nominal"], d["bukti"])
        )
        self._refresh_table()

    def _update_manual(self, transaksi_id: int, d: dict):
        from database import DB
        DB.execute(
            "UPDATE transaksi_keuangan"
            " SET tanggal=?, jenis=?, keterangan=?, nominal=?, bukti_path=?"
            " WHERE id=?",
            (d["tanggal"], d["jenis"], d["keterangan"], d["nominal"], d["bukti"],
             transaksi_id)
        )
        self._refresh_table()

    def _open_bukti(self, path: str):
        # Marker slip gaji admin: "SLIP-ADMIN:Admin Nia:Februari 2026"
        if path.startswith("SLIP-ADMIN:"):
            try:
                from Pembayaran import SlipGajiDialog
                parts = path.split(":", 2)
                admin_name = parts[1] if len(parts) > 1 else ""
                dlg = SlipGajiDialog(self, admin_name, preview_only=True)
                dlg.setMinimumSize(600, 700)
                dlg.exec_()
            except Exception as e:
                show_toast(self, "Tidak dapat membuka slip", str(e), "error")
            return

        # Marker slip gaji guru: "SLIP-GURU:Ms. Happy:Februari 2026"
        if path.startswith("SLIP-GURU:"):
            try:
                from Pembayaran import SlipGajiGuruDialog
                parts = path.split(":", 2)
                guru_name = parts[1] if len(parts) > 1 else ""
                dlg = SlipGajiGuruDialog(self, guru_name, preview_only=True)
                dlg.setMinimumSize(600, 700)
                dlg.exec_()
            except Exception as e:
                show_toast(self, "Tidak dapat membuka slip", str(e), "error")
            return

        # Kuitansi Les / Pendaftaran — buka KuitansiPreviewDialog dari DataMurid
        if path.startswith("KUITANSI-LES:") or path.startswith("KUITANSI-PENDAFTARAN:"):
            try:
                from DataMurid import KuitansiPreviewDialog
                import datetime as _dt
                if path.startswith("KUITANSI-LES:"):
                    ket_raw = path[len("KUITANSI-LES:"):]
                    # parse: "[LES] MV-2026-020 – nani | Gitar | 4x sesi | ID:5"
                    ket_clean = ket_raw.replace("[LES]", "").strip()
                    parts = [p.strip() for p in ket_clean.split("|")]
                    nama_no   = parts[0] if len(parts) > 0 else "—"
                    kursus    = parts[1] if len(parts) > 1 else "—"
                    sesi_str  = parts[2] if len(parts) > 2 else "—"
                    # ambil nominal dari DB
                    from database import DB
                    row_t = DB.fetch_one("SELECT nominal FROM transaksi_keuangan WHERE keterangan=?", (ket_raw,))
                    nominal = row_t["nominal"] if row_t else 0
                    def _fmt(n): return f"Rp {int(n):,}".replace(",", ".")
                    data = {
                        "nomor":         "Auto",
                        "nama":          nama_no,
                        "jumlah":        f"{_fmt(nominal)}",
                        "keterangan":    f"Les {kursus} – {sesi_str}",
                        "nominal":       _fmt(nominal),
                        "nominal_angka": f"{int(nominal):,}".replace(",", "."),
                        "tanggal":       _dt.date.today().strftime("Bantul, %d / %m / %Y"),
                        "ttd_nama":      "Aris Suryahadi",
                        "ttd_jabatan":   "Aris Suryahadi Yunanto\nGENERAL MANAGER\nMelody Violin School Yogyakarta",
                        "catatan": (
                            "Catatan :\n"
                            "* Mohon pembayaran ditransfer ke rekening bank berikut ini :\n"
                            "  BCA 4451561892  |  BNI 0536029816  |  BRI 0029.01.114973.50.9\n"
                            "  a.n : Mahudiah Safitri\n"
                        ),
                    }
                else:
                    ket_raw = path[len("KUITANSI-PENDAFTARAN:"):]
                    ket_clean = ket_raw.replace("[PENDAFTARAN]", "").strip()
                    parts = [p.strip() for p in ket_clean.split("|")]
                    nama_no = parts[0] if len(parts) > 0 else "—"
                    from database import DB
                    row_t = DB.fetch_one("SELECT nominal FROM transaksi_keuangan WHERE keterangan=?", (ket_raw,))
                    nominal = row_t["nominal"] if row_t else 200000
                    def _fmt(n): return f"Rp {int(n):,}".replace(",", ".")
                    data = {
                        "nomor":         "Auto",
                        "nama":          nama_no,
                        "jumlah":        f"{_fmt(nominal)}",
                        "keterangan":    "Biaya Pendaftaran Murid Baru",
                        "nominal":       _fmt(nominal),
                        "nominal_angka": f"{int(nominal):,}".replace(",", "."),
                        "tanggal":       _dt.date.today().strftime("Bantul, %d / %m / %Y"),
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
            except Exception as e:
                show_toast(self, "Tidak dapat membuka kuitansi", str(e), "error")
            return

        # File biasa — buka dengan aplikasi OS
        import subprocess, platform
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
        except Exception as e:
            show_toast(self, "Tidak dapat membuka file", str(e), "error")

    def _show_print_preview(self):
        all_data = self._load_all()
        bulan_now = f"{_BULAN_NAMES[QDate.currentDate().month()-1]} {QDate.currentDate().year()}"
        dlg = PrintPreviewDialog(self, bulan_now, all_data, self._SALDO_AWAL)
        dlg.exec_()


# Alias agar kompatibel dengan import lama
LaporanKeuanganWidget = LaporanKeuanganAdminWidget


#  ENTRY POINT

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    # Font native per platform
    import sys as _sys
    if _sys.platform == "darwin":
        app.setFont(QFont(".AppleSystemUIFont", 10))
    elif _sys.platform.startswith("linux"):
        app.setFont(QFont("Ubuntu", 10))
    else:
        app.setFont(QFont("Segoe UI", 10))

    # Inisialisasi DB
    try:
        from database import init_db
        init_db()
    except Exception as e:
        print(f"[WARN] init_db: {e}")

    w = LaporanKeuanganAdminWidget()
    w.setWindowTitle("Laporan Keuangan – Melody Violin School")
    w.resize(1280, 820)
    w.show()
    sys.exit(app.exec_())