import sys
import re
from datetime import datetime
from database import DB
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit, QDialog,
    QScrollArea, QStackedWidget, QComboBox,
    QStyledItemDelegate, QStyleOptionViewItem, QSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPainter
from toast_notification import show_toast
from theme import svg_icon, svg_pixmap, C, style_combo, resource_path


def _no_double_submit(fn):
    """Menonaktifkan tombol pemicu selama handler berjalan, agar klik ganda/cepat
    tidak memicu simpan/insert dua kali."""
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


#  Delegate: warna status tidak bisa ditimpa stylesheet
_STATUS_COLORS = {
    "Terlaksana": f"{C.SUCCESS_HOVER}",
    "Selesai":    f"{C.SUCCESS_HOVER}",
    "Pending":    f"{C.WARNING}",
    "Batal":      f"{C.DANGER_DARK}",
}

class StatusDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        text = index.data(Qt.DisplayRole) or ""
        color = _STATUS_COLORS.get(text, f"{C.TEXT_MUTED}")

        painter.save()
        if option.state & 0x0002:  # QStyle.State_Selected
            painter.fillRect(option.rect, QColor(f"{C.ACCENT_BG}"))
        else:
            painter.fillRect(option.rect, QColor("white"))

        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.setPen(QColor(color))
        painter.drawText(option.rect, Qt.AlignCenter, text)
        painter.restore()


def _paint_icon_text(painter, rect, icon_name, icon_color, text, text_color, font, icon_size=13):
    """Gambar ikon SVG kecil + teks, sejajar dan di-tengah-kan bersama
    (menggantikan karakter emoji/simbol unicode yang dulu ditempel di teks)."""
    painter.setFont(font)
    fm = painter.fontMetrics()
    text_w = fm.horizontalAdvance(text) if hasattr(fm, "horizontalAdvance") else fm.width(text)
    gap = 6
    total_w = icon_size + gap + text_w
    x = rect.x() + (rect.width() - total_w) // 2
    y = rect.y() + (rect.height() - icon_size) // 2

    pix = svg_pixmap(icon_name, icon_color, icon_size)
    painter.drawPixmap(x, y, pix)

    painter.setPen(QColor(text_color))
    text_rect = rect.adjusted(0, 0, 0, 0)
    text_rect.setX(x + icon_size + gap)
    painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)


class TerlaksanaDelegate(QStyledItemDelegate):
    """Teks 'Terlaksana' + ikon centang hijau, tanpa bentuk badge/button."""
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()

        # Background baris
        if option.state & 0x0002:
            painter.fillRect(option.rect, QColor(f"{C.ACCENT_BG}"))
        else:
            painter.fillRect(option.rect, QColor("white"))

        painter.setRenderHint(QPainter.Antialiasing)
        _paint_icon_text(
            painter, option.rect, "check", C.SUCCESS_HOVER,
            "Terlaksana", C.SUCCESS_HOVER, QFont("Segoe UI", 10, QFont.Bold)
        )
        painter.restore()


class StatusGajiDelegate(QStyledItemDelegate):
    """Teks STATUS GAJI polos (tanpa badge/button): 'Dibayar' + ikon centang biru,
    'Pending' + ikon jam abu."""
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()

        # Background baris
        if option.state & 0x0002:
            painter.fillRect(option.rect, QColor(f"{C.ACCENT_BG}"))
        else:
            painter.fillRect(option.rect, QColor("white"))

        text = index.data(Qt.DisplayRole) or ""
        if text == "Dibayar":
            text_color = f"{C.ACCENT_DARKER}"
            label, icon_name = "Dibayar", "check"
        else:  # Pending
            text_color = f"{C.TEXT_MUTED}"
            label, icon_name = "Pending", "clock"

        painter.setRenderHint(QPainter.Antialiasing)
        _paint_icon_text(
            painter, option.rect, icon_name, text_color,
            label, text_color, QFont("Segoe UI", 10, QFont.Bold)
        )
        painter.restore()


# ── No Ref generator ─────────────────────────────────────────────────────────
_slip_counter = 0

def _gen_no_ref() -> str:
    """Generate no ref otomatis: tahun + nomor urut 3 digit. Contoh: 2026001"""
    global _slip_counter
    _slip_counter += 1
    tahun = datetime.today().year
    return f"{tahun}{_slip_counter:03d}"


def _fmt_rp(val: int) -> str:
    return "Rp{:,.0f},-".format(val).replace(",", ".")


def _load_admin_list_db():
    """Ambil daftar nama admin aktif dari database."""
    try:
        from database import DB
        rows = DB.fetch_all("SELECT nama FROM admin WHERE status='Aktif' ORDER BY nama")
        return [r["nama"] for r in rows]
    except Exception:
        return []


def _get_admin_info_db(admin_name):
    """
    Ambil data admin asli dari tabel 'admin' di database (alamat, no_hp),
    untuk dipakai mengisi slip gaji. nama_staff & nama selalu mengikuti
    admin yang bersangkutan (bukan field statis terpisah).
    Ambil info admin dari DB untuk slip gaji.
    """
    base = {}
    try:
        from database import DB
        row = DB.fetch_one("SELECT nama, alamat, no_hp FROM admin WHERE nama=?", (admin_name,))
        if row:
            nama_pendek = row["nama"]
            base["nama"]        = nama_pendek
            base["nama_staff"]  = nama_pendek
            base["jabatan"]     = "Admin"
            base["alamat"]      = row["alamat"] or base.get("alamat", "-")
            base["telp"]        = row["no_hp"] or base.get("telp", "-")
            base["periode"]     = datetime.today().strftime("%B %Y")
            base["gaji_harian"] = 25000
            base["makan_harian"]= 12000
            base["ttd_name"]    = "Aris Suryahadi"
            base["ttd_jabatan"] = "Chief Operating Officer"
            return base
    except Exception:
        pass
    # Gunakan teks default jika nama admin tidak tersedia
    base.setdefault("nama", admin_name)
    base.setdefault("nama_staff", admin_name)
    base.setdefault("jabatan", "Admin")
    base.setdefault("alamat", "-")
    base.setdefault("telp", "-")
    base.setdefault("periode", datetime.today().strftime("%B %Y"))
    base.setdefault("gaji_harian", 25000)
    base.setdefault("makan_harian", 12000)
    base.setdefault("ttd_name", "Aris Suryahadi")
    base.setdefault("ttd_jabatan", "Chief Operating Officer")
    return base


_duplikat_gaji_sudah_dibersihkan = False  # guard agar hanya jalan sekali per sesi app

def _bersihkan_duplikat_transaksi_gaji():
    """
    Bersihkan transaksi [GAJI-ADMIN]/[GAJI-GURU] duplikat di transaksi_keuangan.
    Duplikat dikenali dari kombinasi (nama, periode) pada keterangan — bukan
    seluruh string, karena jumlah hari/sesi di akhir teks bisa berbeda antar
    percobaan simpan yang sebenarnya merujuk transaksi yang sama.
    Baris dengan id terkecil (paling lama) dipertahankan, sisanya dihapus.
    Dijalankan otomatis & silent setiap halaman Pembayaran dibuka, sekali per sesi.
    """
    global _duplikat_gaji_sudah_dibersihkan
    if _duplikat_gaji_sudah_dibersihkan:
        return
    _duplikat_gaji_sudah_dibersihkan = True
    try:
        rows = DB.fetch_all(
            "SELECT id, keterangan FROM transaksi_keuangan "
            "WHERE keterangan LIKE '[GAJI-ADMIN]%' OR keterangan LIKE '[GAJI-GURU]%' "
            "ORDER BY id ASC"
        )
        grup = {}
        for r in rows:
            m = re.match(r"^\[(GAJI-ADMIN|GAJI-GURU)\]\s*([^|]+)\|\s*([^|]+)\|", r["keterangan"])
            if not m:
                continue
            key = (m.group(1).strip(), m.group(2).strip(), m.group(3).strip())
            grup.setdefault(key, []).append(r["id"])

        ids_to_delete = []
        for key, ids in grup.items():
            if len(ids) > 1:
                ids_to_delete.extend(ids[1:])  # simpan id pertama, hapus sisanya

        if ids_to_delete:
            placeholders = ",".join("?" * len(ids_to_delete))
            DB.execute(
                f"DELETE FROM transaksi_keuangan WHERE id IN ({placeholders})",
                tuple(ids_to_delete)
            )
    except Exception:
        pass


def _load_kehadiran_admin_db(admin_filter="all"):
    """
    Ambil riwayat kehadiran admin dari tabel kehadiran_admin di database.
    Format dict:
        {"id", "tanggal", "nama", "masuk", "pulang", "makan", "status_gaji"}
    Fallback ke list kosong jika koneksi DB gagal.
    """
    try:
        from database import DB
        rows = DB.get_kehadiran_admin(admin_filter)
        result = []
        for r in rows:
            result.append({
                "id":          r["id"],
                "tanggal":     r["tanggal"] or "-",
                "nama":        r["nama_admin"],
                "masuk":       r["jam_masuk"] or "-",
                "pulang":      r["jam_pulang"] or "-",
                # Setiap kali masuk kerja (jam_masuk terisi) = otomatis 1x makan siang
                "makan":       "1" if r["jam_masuk"] else "0",
                "status_gaji": r["status_gaji"] or "Pending",
            })
        return result
    except Exception:
        if admin_filter == "all":
            return []


def _terbilang(n: int) -> str:
    """Simple terbilang untuk nominal gaji (ratusan ribu)."""
    n = int(n or 0)  # pastikan integer, bukan float
    satuan = ["", "satu", "dua", "tiga", "empat", "lima",
              "enam", "tujuh", "delapan", "sembilan"]
    belasan = ["sepuluh", "sebelas", "dua belas", "tiga belas", "empat belas",
               "lima belas", "enam belas", "tujuh belas", "delapan belas", "sembilan belas"]

    def _ratusan(x):
        x = int(x)
        if x == 0: return ""
        h, r = divmod(x, 100)
        res = ""
        if h == 1: res += "seratus "
        elif h > 1: res += satuan[h] + " ratus "
        if 10 <= r < 20: res += belasan[r-10] + " "
        else:
            p, q = divmod(r, 10)
            if p == 1: res += "sepuluh "
            elif p > 1: res += satuan[p] + " puluh "
            if q: res += satuan[q] + " "
        return res

    if n == 0: return "nol rupiah"
    juta, r = divmod(n, 1_000_000)
    ribu, sisa = divmod(r, 1_000)
    out = ""
    if juta:
        out += _ratusan(juta).strip() + " juta "
    if ribu:
        if ribu == 1: out += "seribu "
        else: out += _ratusan(ribu).strip() + " ribu "
    if sisa:
        out += _ratusan(sisa).strip() + " "
    return out.strip().capitalize() + " rupiah"


#  DIALOG: SLIP GAJI

class SlipGajiDialog(QDialog):
    def __init__(self, parent=None, admin_name="Admin Nia", on_saved=None, preview_only=False, current_user=None):
        super().__init__(parent)
        self.setWindowTitle("Slip Gaji")
        self.setMinimumWidth(580)
        self.setStyleSheet("QDialog{background:#F0F4F8;}")
        self._admin_name  = admin_name
        self._on_saved    = on_saved   # callback(admin_name, total) setelah simpan
        self._preview_only = preview_only

        sd = _get_admin_info_db(admin_name)

        # ── Tarif dari database (Pengaturan) ──────────────────────────
        try:
            cfg = DB.get_pengaturan_gaji()
            gaji_harian  = cfg["gaji_admin"]
            makan_harian = cfg["uang_makan_admin"]
        except Exception:
            # Gunakan nilai default jika data belum tersedia
            gaji_harian  = sd.get("gaji_harian",  25000)
            makan_harian = sd.get("makan_harian", 12000)

        # Override sd agar kalkulasi di bawah konsisten
        sd = dict(sd)
        sd["gaji_harian"]  = gaji_harian
        sd["makan_harian"] = makan_harian

        # Generate otomatis
        tanggal_slip     = datetime.today().strftime("%d-%m-%Y")
        self._no_ref     = _gen_no_ref()
        no_ref           = self._no_ref
        # Nama staff: utamakan current_user (staff yang sedang login)
        nama_staff       = current_user if current_user else sd.get("nama_staff", "-")
        self._periode    = sd.get("periode", datetime.today().strftime("%B %Y"))

        # Mode bayar: kehadiran belum dibayar saja. Mode preview: tampilkan semua.
        kehadiran_all = _load_kehadiran_admin_db(admin_name)
        if preview_only:
            kehadiran_admin = kehadiran_all
        else:
            kehadiran_admin = [d for d in kehadiran_all if d.get("status_gaji", "Pending") == "Pending"]
        self._kehadiran_ids = [d["id"] for d in kehadiran_admin if "id" in d]

        n_hari      = len(kehadiran_admin)
        n_makan     = sum(1 for d in kehadiran_admin if d["makan"] == "1")
        total_gaji  = n_hari * sd["gaji_harian"]
        total_makan = n_makan * sd["makan_harian"]
        total       = total_gaji + total_makan
        self._total_gaji = total

        # Label tanggal kehadiran (ambil angka hari dari string "DD-MM-YYYY")
        hari_list   = sorted(set(int(d["tanggal"].split("-")[0]) for d in kehadiran_admin
                                   if d["tanggal"] and d["tanggal"] != "-"))
        hari_str    = ", ".join(f"{d:02d}" for d in hari_list)
        hari_label  = f"{hari_str} ({n_hari}x)"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")

        body = QWidget()
        body.setStyleSheet("background:white;")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(40, 32, 40, 32)
        bv.setSpacing(0)

        # ── Kop ────────────────────────────────────────────────────
        kop = QHBoxLayout()

        # Logo lingkaran + teks
        import os
        from PyQt5.QtGui import QPixmap
        logo_frame = QLabel()
        logo_frame.setFixedSize(80, 80)
        _logo_path = resource_path("mvs.png")
        _logo_pix = QPixmap(_logo_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_frame.setPixmap(_logo_pix)
        logo_frame.setAlignment(Qt.AlignCenter)
        logo_frame.setStyleSheet("background:transparent;border:none;")

        school_col = QVBoxLayout(); school_col.setSpacing(2)
        school_col.addWidget(self._lbl("MELODY VIOLIN SCHOOL",
            f"font-size:16px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        school_col.addWidget(self._lbl("Jl. S. Parman 14a, Kota Bantul, Daerah",
            f"font-size:10px;color:{C.TEXT_MUTED};"))
        school_col.addWidget(self._lbl("Istimewa Yogyakarta",
            f"font-size:10px;color:{C.TEXT_MUTED};"))
        school_col.addWidget(self._lbl("Hotline: 089636833384",
            f"font-size:10px;color:{C.TEXT_MUTED};"))

        kop_left = QHBoxLayout(); kop_left.setSpacing(14)
        kop_left.addWidget(logo_frame)
        kop_left.addLayout(school_col)

        kop_right = QVBoxLayout(); kop_right.setSpacing(4); kop_right.setAlignment(Qt.AlignTop)
        slip_title = QLabel("SLIP GAJI")
        slip_title.setStyleSheet(f"font-size:22px;font-weight:bold;color:{C.TEXT_PRIMARY};")
        slip_title.setAlignment(Qt.AlignRight)

        for label, val in [("Tanggal", f": {tanggal_slip}"),
                            ("No Ref",  f": {no_ref}")]:
            row = QHBoxLayout()
            row.addWidget(self._lbl(label, f"font-size:11px;color:{C.TEXT_MUTED};"), 1)
            row.addWidget(self._lbl(val,   f"font-size:11px;color:{C.TEXT_PRIMARY};"))

        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame{border:none;}")
        info_lay = QVBoxLayout(info_frame); info_lay.setSpacing(2); info_lay.setContentsMargins(0,0,0,0)
        for label, val in [("Tanggal",    tanggal_slip),
                            ("No Ref",    no_ref),
                            ("Nama Staff", nama_staff)]:
            r = QHBoxLayout()
            r.addWidget(self._lbl(label, f"font-size:11px;color:{C.TEXT_MUTED};"))
            r.addWidget(self._lbl(f":  {val}", f"font-size:11px;color:{C.TEXT_PRIMARY};"))
            r.addStretch()
            info_lay.addLayout(r)

        kop_right.addWidget(slip_title)
        kop_right.addWidget(info_frame)

        kop.addLayout(kop_left, 1)
        kop.addLayout(kop_right)
        bv.addLayout(kop)
        bv.addSpacing(18)

        # Divider
        bv.addWidget(self._hdiv())
        bv.addSpacing(14)

        # ── Info pegawai ───────────────────────────────────────────
        info_grid = QHBoxLayout()
        left_col = QVBoxLayout(); left_col.setSpacing(6)
        right_col = QVBoxLayout(); right_col.setSpacing(6)
        for label, val in [("Nama", sd['nama']), ("Jabatan", sd['jabatan'])]:
            r = QHBoxLayout()
            r.addWidget(self._lbl(label, f"font-size:12px;color:{C.TEXT_MUTED};font-weight:600;"))
            r.addWidget(self._lbl(f":  {val}", f"font-size:12px;color:{C.TEXT_PRIMARY};"))
            r.addStretch()
            left_col.addLayout(r)
        for label, val in [("Alamat", sd['alamat']), ("No. Tlpon", sd['telp'])]:
            r = QHBoxLayout()
            r.addWidget(self._lbl(label, f"font-size:12px;color:{C.TEXT_MUTED};font-weight:600;"))
            r.addWidget(self._lbl(f":  {val}", f"font-size:12px;color:{C.TEXT_PRIMARY};"))
            r.addStretch()
            right_col.addLayout(r)
        info_grid.addLayout(left_col, 1)
        info_grid.addLayout(right_col, 1)
        bv.addLayout(info_grid)
        bv.addSpacing(18)

        # ── Tabel rincian ──────────────────────────────────────────
        tbl = QTableWidget(2, 3)
        tbl.setHorizontalHeaderLabels(["NO", "KETERANGAN", "JUMLAH"])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setShowGrid(True)
        tbl.setFocusPolicy(Qt.NoFocus)
        tbl.setStyleSheet(f"""
            QTableWidget{{border:1px solid {C.BORDER};background:white;}}
            QHeaderView::section{{
                background:{C.SURFACE_ALT};padding:10px 12px;border:none;
                border-bottom:1px solid {C.BORDER};border-right:1px solid {C.BORDER};
                color:{C.TEXT_MUTED_STRONG};font-weight:bold;font-size:11px;
            }}
            QTableWidget::item{{
                padding:10px 12px;color:{C.TEXT_PRIMARY};font-size:12px;
            }}
        """)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        tbl.setColumnWidth(0, 50)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        tbl.setColumnWidth(2, 120)

        # Row 1 — gaji
        tbl.setItem(0, 0, QTableWidgetItem("1"))
        ket1 = QTableWidgetItem(
            f"Bulan {sd['periode']}:\n{hari_label}"
        )
        ket1.setFont(QFont("Segoe UI", 10))
        tbl.setItem(0, 1, ket1)
        g_item = QTableWidgetItem(_fmt_rp(total_gaji))
        g_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        g_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
        tbl.setItem(0, 2, g_item)
        tbl.setRowHeight(0, 56)

        # Row 2 — makan
        tbl.setItem(1, 0, QTableWidgetItem("2"))
        makan_tgl   = sorted(set(int(d["tanggal"].split("-")[0]) for d in kehadiran_admin if d["makan"] == "1"))
        makan_str   = ", ".join(f"{d:02d}" for d in makan_tgl)
        makan_label = f"{makan_str} ({n_makan}x)" if makan_str else "0x"
        ket2 = QTableWidgetItem(
            f"Makan bulan {sd['periode']}:\n{makan_label}"
        )
        tbl.setItem(1, 1, ket2)
        m_item = QTableWidgetItem(_fmt_rp(total_makan))
        m_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        m_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
        tbl.setItem(1, 2, m_item)
        tbl.setRowHeight(1, 56)

        tbl.setFixedHeight(36 + 56*2 + 4)
        bv.addWidget(tbl)
        bv.addSpacing(14)

        # ── Total ──────────────────────────────────────────────────
        total_row = QHBoxLayout()
        terbilang_lbl = QLabel(_terbilang(total).capitalize())
        terbilang_lbl.setStyleSheet(
            f"font-size:11px;color:{C.TEXT_BODY};font-style:italic;"
            f"background:{C.SURFACE_ALT};border:1px solid {C.BORDER};"
            "border-radius:6px;padding:6px 12px;")
        total_row.addWidget(terbilang_lbl, 1)
        total_row.addStretch()

        total_box = QFrame()
        total_box.setStyleSheet("QFrame{border:none;}")
        tbl_v = QHBoxLayout(total_box); tbl_v.setSpacing(16)
        tbl_v.addWidget(self._lbl("TOTAL DITERIMA :",
            f"font-size:12px;font-weight:bold;color:{C.TEXT_BODY};background:transparent;"))
        tbl_v.addWidget(self._lbl(_fmt_rp(total).replace(",-",""),
            f"font-size:16px;font-weight:bold;color:{C.ACCENT};background:transparent;"))

        total_row.addWidget(total_box)
        bv.addLayout(total_row)
        bv.addSpacing(28)

        # ── TTD ────────────────────────────────────────────────────
        bv.addWidget(self._hdiv())
        bv.addSpacing(20)

        ttd_row = QHBoxLayout()
        ttd_row.addStretch()

        ttd_col = QVBoxLayout(); ttd_col.setSpacing(4); ttd_col.setAlignment(Qt.AlignHCenter)
        ttd_col.addWidget(self._lbl(tanggal_slip,
            f"font-size:11px;color:{C.TEXT_MUTED};background:transparent;"))
        ttd_col.addSpacing(6)

        # Tanda tangan (gambar tanda tangan asli). Fallback ke teks kursif
        # jika file ttd_gm.png belum diletakkan di folder yang sama.
        _TTD_H = 46
        ttd_sign = QLabel()
        ttd_sign.setAlignment(Qt.AlignCenter)
        ttd_sign.setStyleSheet("background:transparent;border:none;")
        _ttd_path = resource_path("ttd_gm.png")
        if os.path.exists(_ttd_path):
            _ttd_px = QPixmap(_ttd_path).scaledToHeight(_TTD_H, Qt.SmoothTransformation)
            ttd_sign.setPixmap(_ttd_px)
            ttd_sign.setFixedSize(_ttd_px.size())
        else:
            ttd_sign.setText(sd['ttd_name'])
            ttd_sign.setStyleSheet(
                f"font-size:18px;font-family:cursive;color:{C.ACCENT_DARKER};"
                "background:transparent;")
        ttd_col.addWidget(ttd_sign, 0, Qt.AlignHCenter)

        # Garis TTD
        garis = QFrame(); garis.setFrameShape(QFrame.HLine)
        garis.setStyleSheet(f"color:{C.TEXT_PRIMARY};max-height:1px;")
        ttd_col.addWidget(garis)

        ttd_col.addWidget(self._lbl(sd['ttd_name'],
            f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;"))
        ttd_col.addWidget(self._lbl(sd['ttd_jabatan'],
            f"font-size:10px;color:{C.TEXT_MUTED};background:transparent;"))
        ttd_col.addWidget(self._lbl("MELODY VIOLIN SCHOOL",
            f"font-size:10px;color:{C.TEXT_MUTED};background:transparent;"))

        # Nama penerima (kiri bawah)
        penerima_col = QVBoxLayout(); penerima_col.setAlignment(Qt.AlignBottom)
        penerima_col.addWidget(self._lbl("Penerima",
            f"font-size:11px;color:{C.TEXT_MUTED};background:transparent;"))
        penerima_col.addSpacing(40)
        penerima_col.addWidget(self._lbl(sd['nama'],
            f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;"))

        ttd_row.addLayout(penerima_col)
        ttd_row.addStretch()
        ttd_row.addLayout(ttd_col)
        bv.addLayout(ttd_row)

        scroll.setWidget(body)
        root.addWidget(scroll)

        # ── Bottom bar ─────────────────────────────────────────────
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"QFrame{{background:white;border-top:1px solid {C.BORDER};}}")
        bl = QHBoxLayout(bar); bl.setContentsMargins(20,0,20,0); bl.setSpacing(12)

        kembali_btn = QPushButton(" Kembali")
        kembali_btn.setIcon(svg_icon("arrow-left", C.TEXT_PRIMARY, 13))
        kembali_btn.setFixedHeight(36)
        kembali_btn.setCursor(Qt.PointingHandCursor)
        kembali_btn.setStyleSheet(f"""
            QPushButton{{background:white;color:{C.TEXT_PRIMARY};border:1.5px solid {C.BORDER};
                border-radius:8px;font-size:12px;font-weight:bold;padding:0 16px;}}
            QPushButton:hover{{background:{C.SURFACE_ALT};}}
        """)
        kembali_btn.clicked.connect(self.reject)

        # Sudah dibayar jika tidak ada kehadiran Pending untuk admin ini
        _sudah_dibayar = len(self._kehadiran_ids) == 0

        simpan_btn = QPushButton("Simpan Pembayaran")
        simpan_btn.setFixedHeight(36)
        simpan_btn.setCursor(Qt.PointingHandCursor)
        simpan_btn.setEnabled(not _sudah_dibayar)
        simpan_btn.setStyleSheet(f"""
            QPushButton{{background:{C.ACCENT};color:white;border:none;
                border-radius:8px;font-size:12px;font-weight:bold;padding:0 18px;}}
            QPushButton:hover{{background:{C.ACCENT_DARK};}}
            QPushButton:disabled{{background:{C.ACCENT_BORDER};color:{C.ACCENT_BG};}}
        """)
        if _sudah_dibayar:
            simpan_btn.setText(" Tersimpan")
            simpan_btn.setIcon(svg_icon("check", "white", 13))
        simpan_btn.clicked.connect(self._simpan_pembayaran)
        self._simpan_btn = simpan_btn
        simpan_btn.setVisible(not preview_only)

        dl_btn = QPushButton(" Download PDF")
        dl_btn.setIcon(svg_icon("download", C.ACCENT, 14))
        dl_btn.setFixedHeight(36)
        dl_btn.setCursor(Qt.PointingHandCursor)
        dl_btn.setStyleSheet(f"""
            QPushButton{{background:white;color:{C.ACCENT};border:1.5px solid {C.ACCENT};
                border-radius:8px;font-size:12px;font-weight:bold;padding:0 18px;}}
            QPushButton:hover{{background:{C.ACCENT_BG};}}
        """)
        self._slip_body   = body
        self._slip_no_ref = no_ref
        dl_btn.clicked.connect(self._download_pdf)

        bl.addWidget(kembali_btn)
        bl.addStretch()
        bl.addWidget(simpan_btn)
        bl.addWidget(dl_btn)
        root.addWidget(bar)

    def _download_pdf(self):
        from PyQt5.QtWidgets import QFileDialog
        from PyQt5.QtPrintSupport import QPrinter
        from PyQt5.QtGui import QPainter

        default_name = f"SlipGaji_{self._admin_name.replace(' ', '_')}_{self._slip_no_ref}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan PDF", default_name, "PDF Files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPrinter.A4)
        printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)

        body = self._slip_body
        painter = QPainter(printer)
        scale = printer.width() / max(body.width(), 1)
        painter.scale(scale, scale)
        body.render(painter)
        painter.end()

        show_toast(self, "Berhasil", f"PDF berhasil disimpan:\n{path}", "success")

    @_no_double_submit
    def _simpan_pembayaran(self):
        nama   = self._admin_name
        total  = self._total_gaji
        periode = self._periode
        tgl    = datetime.today().strftime("%Y-%m-%d")

        # 1. Cari admin_id dari tabel admin
        admin_id = None
        try:
            row = DB.fetch_one("SELECT id FROM admin WHERE nama=?", (nama,))
            if row:
                admin_id = row["id"]
        except Exception:
            pass

        kehadiran_ids = self._kehadiran_ids
        if not kehadiran_ids:
            show_toast(self, "Info", f"Tidak ada kehadiran yang perlu dibayar untuk {nama}.", "warning")
            return

        # 2. Hitung hari_kerja & uang_makan dari kehadiran yang sedang dibayar
        kehadiran_admin = _load_kehadiran_admin_db(nama)
        kehadiran_admin = [d for d in kehadiran_admin if d["id"] in kehadiran_ids]
        n_hari  = len(kehadiran_admin)
        n_makan = sum(1 for d in kehadiran_admin if d["makan"] == "1")
        try:
            cfg = DB.get_pengaturan_gaji()
            gaji_h  = cfg["gaji_admin"]
            makan_h = cfg["uang_makan_admin"]
        except Exception:
            gaji_h, makan_h = 25000, 12000
        uang_makan = n_makan * makan_h

        # 3. Update status_gaji di kehadiran_admin untuk semua kehadiran yang dibayar
        try:
            try:
                DB.execute("ALTER TABLE kehadiran_admin ADD COLUMN status_gaji TEXT DEFAULT 'Pending'")
            except Exception:
                pass
            placeholders = ",".join("?" * len(kehadiran_ids))
            DB.execute(
                f"UPDATE kehadiran_admin SET status_gaji='Dibayar' WHERE id IN ({placeholders})",
                tuple(kehadiran_ids)
            )
        except Exception:
            pass

        # 4. Simpan ke tabel gaji_admin — cek duplikat (admin + periode) dulu
        #    agar klik ganda atau buka-tutup dialog tidak membuat baris ganda.
        gaji_admin_id = None
        if admin_id:
            try:
                existing_ga = DB.fetch_one(
                    "SELECT id FROM gaji_admin WHERE admin_id=? AND periode=?",
                    (admin_id, periode)
                )
                if existing_ga:
                    # Sudah ada — perbarui nominal saja (bukan insert ulang)
                    gaji_admin_id = existing_ga["id"]
                    DB.execute(
                        "UPDATE gaji_admin SET hari_kerja=?, gaji_harian=?, uang_makan=?,"
                        " nominal_total=?, tanggal_bayar=?, status='Sudah Dibayar'"
                        " WHERE id=?",
                        (n_hari, gaji_h, uang_makan, total, tgl, gaji_admin_id)
                    )
                else:
                    gaji_admin_id = DB.execute(
                        "INSERT INTO gaji_admin "
                        "(admin_id, periode, hari_kerja, gaji_harian, uang_makan,"
                        " nominal_total, tanggal_bayar, no_referensi, status) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Sudah Dibayar')",
                        (admin_id, periode, n_hari, gaji_h, uang_makan,
                         total, tgl, self._no_ref)
                    )
            except Exception:
                pass

        # 5. Simpan ke transaksi_keuangan [GAJI-ADMIN] — format harus sama dgn _sinkron_db() di LaporanKeuangan.py
        try:
            id_str   = str(gaji_admin_id) if gaji_admin_id else "auto"
            ket      = f"[GAJI-ADMIN] {nama} | {periode} | {n_hari} hari | ID:{id_str}"
            prefix   = f"[GAJI-ADMIN] {nama} | {periode} |"
            tgl_disp = datetime.today().strftime("%d/%m/%Y")
            bukti_marker = f"SLIP-ADMIN:{nama}:{periode}"
            existing_trx = DB.fetch_one(
                "SELECT id FROM transaksi_keuangan WHERE keterangan LIKE ?",
                (prefix + "%",)
            )
            if existing_trx:
                # Perbarui keterangan & nominal (misal hari berubah)
                DB.execute(
                    "UPDATE transaksi_keuangan SET keterangan=?, nominal=?, bukti_path=?"
                    " WHERE id=?",
                    (ket, total, bukti_marker, existing_trx["id"])
                )
            else:
                DB.execute(
                    "INSERT INTO transaksi_keuangan"
                    " (tanggal, jenis, keterangan, nominal, bukti_path)"
                    " VALUES (?, 'Kredit', ?, ?, ?)",
                    (tgl_disp, ket, total, bukti_marker)
                )
        except Exception:
            pass

        # 6. Disable tombol, beri feedback
        self._simpan_btn.setEnabled(False)
        self._simpan_btn.setText(" Tersimpan")
        self._simpan_btn.setIcon(svg_icon("check", "white", 13))
        self._kehadiran_ids = []

        # 7. Panggil callback agar tabel kehadiran di-refresh
        if self._on_saved:
            self._on_saved(nama, total)

        show_toast(self, "Berhasil", f"Pembayaran gaji {nama} ({periode}) sebesar Rp{total:,.0f} telah disimpan.", "success")

    def _lbl(self, text, style):
        l = QLabel(text); l.setStyleSheet(style); return l

    def _hdiv(self):
        f = QFrame(); f.setFrameShape(QFrame.HLine)
        f.setStyleSheet(f"color:{C.BORDER};"); return f


#  WIDGET: PEMBAYARAN / KEHADIRAN ADMIN

class PembayaranWidget(QWidget):
    def __init__(self, current_user=None):
        super().__init__()
        _bersihkan_duplikat_transaksi_gaji()
        self.setStyleSheet(f"background-color: {C.SURFACE_ALT};")
        self._current_user = current_user
        self._selected_admin = "all"   # "all" | nama admin
        self.init_ui()

    def init_ui(self):
        v = QVBoxLayout(self)
        # Margin kiri-kanan 0 — sudah diberi 35px oleh PembayaranMainWidget di level atas
        v.setContentsMargins(0, 20, 0, 30)
        v.setSpacing(20)

        # ── Filter Admin dropdown ─────────────────────────────────────
        filter_row = QHBoxLayout(); filter_row.setSpacing(10)
        filter_lbl = QLabel("Filter Admin:")
        filter_lbl.setStyleSheet(f"font-size:13px;color:{C.TEXT_BODY};background:transparent;")

        self._admin_combo = QComboBox()
        self._admin_combo.addItem("Seluruh Admin", "all")
        for a in _load_admin_list_db():
            self._admin_combo.addItem(a, a)
        self._admin_combo.setFixedHeight(38)
        self._admin_combo.setMinimumWidth(200)
        self._admin_combo.setCursor(Qt.PointingHandCursor)
        style_combo(self._admin_combo)
        self._admin_combo.currentIndexChanged.connect(self._on_admin_combo_changed)

        self._bulan_combo = QComboBox()
        self._bulan_combo.addItem("Semua Bulan", 0)

        bulan_list = [
            "Januari", "Februari", "Maret", "April",
            "Mei", "Juni", "Juli", "Agustus",
            "September", "Oktober", "November", "Desember"
        ]

        for i, nama in enumerate(bulan_list, start=1):
            self._bulan_combo.addItem(nama, i)

        self._bulan_combo.setCurrentIndex(datetime.now().month)
        self._bulan_combo.setFixedHeight(38)
        self._bulan_combo.setCursor(Qt.PointingHandCursor)
        style_combo(self._bulan_combo)
        self._bulan_combo.currentIndexChanged.connect(self._refresh_table)

        self._tahun_spin = QSpinBox()
        self._tahun_spin.setRange(2000, 2100)
        self._tahun_spin.setValue(datetime.now().year)
        self._tahun_spin.setFixedHeight(38)
        self._tahun_spin.setFixedWidth(90)
        self._tahun_spin.setCursor(Qt.PointingHandCursor)
        self._tahun_spin.setStyleSheet(f"""
            QSpinBox{{border:1.5px solid {C.ACCENT_BORDER};border-radius:10px;
                background:white;padding:0 10px;font-size:13px;color:{C.TEXT_PRIMARY};}}
            QSpinBox:focus{{border:2px solid {C.ACCENT};}}
        """)
        self._tahun_spin.valueChanged.connect(self._refresh_table)

        filter_row.addWidget(filter_lbl)
        filter_row.addWidget(self._admin_combo)
        filter_row.addWidget(self._bulan_combo)
        filter_row.addWidget(self._tahun_spin)
        filter_row.addStretch()
        v.addLayout(filter_row)

        # ── Detail card (hanya muncul saat admin tertentu dipilih) ────
        self.detail_card = self._build_detail_card()
        v.addWidget(self.detail_card)
        self.detail_card.setVisible(False)

        # ── Table section ─────────────────────────────────────────────
        table_frame = QFrame()
        table_frame.setStyleSheet("QFrame{background:white;border-radius:14px;border:none;}")
        tv = QVBoxLayout(table_frame)
        tv.setContentsMargins(22, 20, 22, 16)
        tv.setSpacing(14)

        # Toolbar
        tb = QHBoxLayout()
        self.section_title = QLabel("Kehadiran Harian")
        self.section_title.setStyleSheet(
            f"font-size:18px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;")
        # Dummy search agar _refresh_table tidak error saat akses self._search
        self._search = QLineEdit()
        self._search.setVisible(False)
        tb.addWidget(self.section_title)
        tb.addStretch()
        tv.addLayout(tb)

        # Table
        cols = ["NO", "TANGGAL", "NAMA ADMIN", "JAM MASUK", "JAM PULANG", "MAKAN SIANG", "STATUS GAJI"]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(f"""
            QTableWidget{{border:none;background:white;}}
            QHeaderView::section{{
                background:{C.SURFACE_ALT};padding:12px 10px;border:none;
                border-bottom:2px solid {C.SURFACE_HOVER};
                color:{C.TEXT_MUTED_STRONG};font-weight:bold;font-size:11px;
            }}
            QTableWidget::item{{
                padding:14px 10px;border-bottom:1px solid {C.SURFACE_HOVER};
                color:{C.TEXT_BODY};font-size:12px;
            }}
            QTableWidget::item:selected{{background:{C.ACCENT_BG};color:{C.TEXT_PRIMARY};}}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 60)
        # Delegate badge STATUS GAJI (kolom 6)
        self._status_gaji_delegate = StatusGajiDelegate(self.table)
        self.table.setItemDelegateForColumn(6, self._status_gaji_delegate)
        tv.addWidget(self.table)

        # Footer info
        self._info_lbl = QLabel("Menampilkan 0 kehadiran")
        self._info_lbl.setStyleSheet(
            f"font-size:11px;color:{C.TEXT_FAINT};padding:10px 18px;background:transparent;")
        tv.addWidget(self._info_lbl)
        v.addWidget(table_frame)

        self._refresh_table()

    def _build_detail_card(self):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame{{background:white;border-radius:14px;border:1.5px solid {C.ACCENT_BG_STRONG};}}
        """)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(30)

        # Total kehadiran
        left = QVBoxLayout(); left.setSpacing(4)
        self.detail_kehadiran_lbl = QLabel("TOTAL KEHADIRAN FEBRUARI 2026")
        self.detail_kehadiran_lbl.setStyleSheet(
            f"font-size:11px;font-weight:bold;color:{C.ACCENT};background:transparent;border:none;")
        self.detail_hari_lbl = QLabel("22 Hari")
        self.detail_hari_lbl.setStyleSheet(
            f"font-size:26px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;")
        left.addWidget(self.detail_kehadiran_lbl)
        left.addWidget(self.detail_hari_lbl)


        # Tombol slip gaji
        self.slip_btn = QPushButton("Lihat Slip Gaji")
        self.slip_btn.setFixedHeight(38)
        self.slip_btn.setCursor(Qt.PointingHandCursor)
        self.slip_btn.setStyleSheet(f"""
            QPushButton{{background:{C.ACCENT};color:white;border:none;
                border-radius:8px;font-weight:bold;font-size:13px;padding:0 20px;}}
            QPushButton:hover{{background:{C.ACCENT_DARK};}}
        """)
        self.slip_btn.clicked.connect(self._show_slip)

        lay.addLayout(left)
        lay.addStretch()
        lay.addWidget(self.slip_btn)
        return card

    def _refresh_table(self):
        kw = self._search.text().lower() if hasattr(self, '_search') else ""
        af = self._selected_admin
        bulan_filter = self._bulan_combo.currentData()
        tahun_filter = self._tahun_spin.value()

        all_rows = _load_kehadiran_admin_db(af)
        filtered = []

        for d in all_rows:
            cocok_search = (
                kw in d["nama"].lower()
                or kw in d["tanggal"].lower()
            )

            if not cocok_search:
                continue

            try:
                parts = d["tanggal"].split("-")
                bulan_data = int(parts[1])
                tahun_data = int(parts[2])
            except Exception:
                continue

            if bulan_filter and bulan_data != bulan_filter:
                continue
            if tahun_data != tahun_filter:
                continue

            filtered.append(d)

        self.table.setRowCount(0)
        for i, row in enumerate(filtered):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 52)

            self.table.setItem(r, 0, QTableWidgetItem(f"{i+1:02d}"))

            # Tanggal – bold
            tgl = QTableWidgetItem(row["tanggal"])
            tgl.setFont(QFont("Segoe UI", 10, QFont.Bold))
            tgl.setForeground(QColor(f"{C.TEXT_PRIMARY}"))
            self.table.setItem(r, 1, tgl)

            # Nama admin – biru link style jika all
            nama_item = QTableWidgetItem(row["nama"])
            if af == "all":
                nama_item.setForeground(QColor(f"{C.ACCENT}"))
                nama_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table.setItem(r, 2, nama_item)

            self.table.setItem(r, 3, QTableWidgetItem(row["masuk"]))
            self.table.setItem(r, 4, QTableWidgetItem(row["pulang"]))
            self.table.setItem(r, 5, QTableWidgetItem(row["makan"]))
            # Kolom STATUS GAJI — nilai dirender oleh StatusGajiDelegate
            status_item = QTableWidgetItem(row.get("status_gaji", "Pending"))
            status_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.table.setItem(r, 6, status_item)

        if hasattr(self, '_info_lbl'):
            self._info_lbl.setText(f"Menampilkan {len(filtered)} kehadiran")

    def _on_admin_combo_changed(self, index):
        key = self._admin_combo.itemData(index)
        self._set_admin(key)

    def _set_admin(self, key):
        self._selected_admin = key
        self.detail_card.setVisible(key != "all")
        if key != "all":
            n = len(_load_kehadiran_admin_db(key))
            self.detail_hari_lbl.setText(f"{n} Hari")
            self.section_title.setText("Kehadiran")
        else:
            self.section_title.setText("Kehadiran Harian")
        self._refresh_table()

    def _show_slip(self):
        def _on_saved(nama, total):
            self._refresh_table()
            # Beritahu PembayaranMainWidget agar angka stat card diperbarui
            if hasattr(self, "_on_stat_changed") and self._on_stat_changed:
                self._on_stat_changed()
        dlg = SlipGajiDialog(self, self._selected_admin, on_saved=_on_saved,
                             current_user=self._current_user)
        dlg.setMinimumSize(600, 700)
        dlg.exec_()

    def _stat_card(self, title, val, highlight=False):
        f = QFrame()
        f.setFixedHeight(110)
        if highlight:
            f.setStyleSheet(f"""
                QFrame{{background:{C.ACCENT_BG};border:1.5px solid {C.ACCENT_BORDER};border-radius:14px;}}
                QLabel{{background:transparent;border:none;}}
            """)
        else:
            f.setStyleSheet(f"""
                QFrame{{background:white;border:1.5px solid {C.BORDER};border-radius:14px;}}
                QLabel{{background:transparent;border:none;}}
            """)
        fl = QVBoxLayout(f)
        fl.setContentsMargins(20, 16, 20, 16)
        fl.setSpacing(8)
        t = QLabel(title)
        t.setStyleSheet(f"font-size:11px;font-weight:bold;"
                        f"color:{f'{C.ACCENT}' if highlight else f'{C.TEXT_FAINT}'};"
                        "letter-spacing:0.5px;")
        n = QLabel(val)
        n.setStyleSheet(f"font-size:32px;font-weight:bold;color:{C.TEXT_PRIMARY};")
        fl.addWidget(t); fl.addWidget(n)
        return f

    def _lbl(self, text, style):
        l = QLabel(text); l.setStyleSheet(style); return l


#  HELPER: DATA GURU UNTUK SLIP GAJI

def _get_guru_info_db(guru_name):
    """Ambil data guru dari tabel 'guru' untuk slip gaji."""
    base = {}
    try:
        from database import DB
        row = DB.fetch_one("SELECT nama, no_hp, alamat FROM guru WHERE nama=?", (guru_name,))
        if row:
            base["nama"]        = row["nama"]
            base["nama_staff"]  = row["nama"]
            base["jabatan"]     = "Guru"
            base["alamat"]      = row["alamat"] or "-"
            base["telp"]        = row["no_hp"] or "-"
            base["periode"]     = datetime.today().strftime("%B %Y")
            base["ttd_name"]    = "Aris Suryahadi"
            base["ttd_jabatan"] = "Chief Operating Officer"
            base["tarif_murid"] = {}
            return base
    except Exception:
        pass
    base.setdefault("nama",        guru_name)
    base.setdefault("nama_staff",  guru_name)
    base.setdefault("jabatan",     "Guru")
    base.setdefault("alamat",      "-")
    base.setdefault("telp",        "-")
    base.setdefault("periode",     datetime.today().strftime("%B %Y"))
    base.setdefault("ttd_name",    "Aris Suryahadi")
    base.setdefault("ttd_jabatan", "Chief Operating Officer")
    base.setdefault("tarif_murid", {})
    return base


#  DIALOG: SLIP GAJI GURU

class SlipGajiGuruDialog(QDialog):
    def __init__(self, parent=None, guru_name="Ms. Happy", on_saved=None, preview_only=False, current_user=None):
        super().__init__(parent)
        self.setWindowTitle("Slip Gaji Guru")
        self.setMinimumWidth(580)
        self.setStyleSheet("QDialog{background:#F0F4F8;}")

        self._guru_name  = guru_name
        self._on_saved   = on_saved   # callback(guru_name, total) setelah simpan
        self._preview_only = preview_only

        sd = _get_guru_info_db(guru_name)

        # ── Tarif dari Pengaturan: gaji_guru=Offline, gaji_guru_online=Online, gaji_guru_home_visit=Home Visit ──
        try:
            cfg = DB.get_pengaturan_gaji()
            _fallback           = cfg.get("gaji_guru_visit_online", 35000)
            _tarif_offline      = cfg.get("gaji_guru", 40000)
            _tarif_online       = cfg.get("gaji_guru_online", _fallback)
            _tarif_home_visit   = cfg.get("gaji_guru_home_visit", _fallback)
        except Exception:
            _tarif_offline      = 40000
            _tarif_online       = 35000
            _tarif_home_visit   = 35000

        # Generate otomatis
        tanggal_slip = datetime.today().strftime("%d-%m-%Y")
        no_ref       = _gen_no_ref()
        # Nama staff: utamakan current_user (staff yang sedang login)
        nama_staff   = current_user if current_user else sd.get("nama_staff", "-")

        # Mode bayar: sesi belum dibayar saja. Mode preview: tampilkan semua sesi.
        sesi_db = _load_sesi_terlaksana(guru_filter=guru_name)
        sesi_per_murid = {}   # (murid, metode) -> {"tanggal_list": [...], "ids": [...], "transport_total": 0}
        for sesi in sesi_db:
            if not preview_only and sesi.get("status_gaji", "Pending") != "Pending":
                continue
            m = sesi["nama_murid"]
            metode = sesi.get("metode") or "Offline"
            key = (m, metode)
            entry = sesi_per_murid.setdefault(
                key, {"tanggal_list": [], "ids": [], "transport_total": 0})
            entry["tanggal_list"].append(sesi["tanggal"])
            entry["ids"].append(sesi["id"])
            entry["transport_total"] += sesi.get("transport", 0)

        # Pakai tarif_murid custom jika ada, kalau tidak pakai tarif Pengaturan; Home Visit + transport_total
        grand_total = 0
        murid_rows = []
        all_sesi_ids = []
        for idx, ((murid, metode), info) in enumerate(sesi_per_murid.items()):
            n_sesi = len(info["tanggal_list"])
            custom_tarif = sd["tarif_murid"].get(murid)
            if custom_tarif is not None:
                tarif = custom_tarif
            elif metode == "Offline":
                tarif = _tarif_offline
            elif metode == "Online":
                tarif = _tarif_online
            else:
                tarif = _tarif_home_visit
            transport_total = info["transport_total"]
            subtotal = tarif * n_sesi + transport_total
            grand_total += subtotal
            all_sesi_ids.extend(info["ids"])
            murid_rows.append({
                "no": idx + 1,
                "murid": murid,
                "metode": metode,
                "tarif": tarif,
                "transport_total": transport_total,
                "tanggal_list": info["tanggal_list"],
                "subtotal": subtotal,
            })

        # Simpan untuk dipakai saat simpan pembayaran
        self._total_gaji = grand_total
        self._no_ref      = no_ref
        self._periode     = datetime.today().strftime("%B %Y")
        self._sesi_ids    = all_sesi_ids

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")

        body = QWidget()
        body.setStyleSheet("background:white;")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(40, 32, 40, 32)
        bv.setSpacing(0)

        # ── Kop ──────────────────────────────────────────────────────
        kop = QHBoxLayout()

        import os
        from PyQt5.QtGui import QPixmap
        logo_frame = QLabel()
        logo_frame.setFixedSize(80, 80)
        _logo_path = resource_path("mvs.png")
        _logo_pix = QPixmap(_logo_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_frame.setPixmap(_logo_pix)
        logo_frame.setAlignment(Qt.AlignCenter)
        logo_frame.setStyleSheet("background:transparent;border:none;")

        school_col = QVBoxLayout(); school_col.setSpacing(2)
        school_col.addWidget(self._lbl("MELODY VIOLIN SCHOOL",
            f"font-size:16px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        school_col.addWidget(self._lbl("Jl. S. Parman 14a, Kota Bantul, Daerah",
            f"font-size:10px;color:{C.TEXT_MUTED};"))
        school_col.addWidget(self._lbl("Istimewa Yogyakarta",
            f"font-size:10px;color:{C.TEXT_MUTED};"))
        school_col.addWidget(self._lbl("Hotline: 089636833384",
            f"font-size:10px;color:{C.TEXT_MUTED};"))

        kop_left = QHBoxLayout(); kop_left.setSpacing(14)
        kop_left.addWidget(logo_frame)
        kop_left.addLayout(school_col)

        kop_right = QVBoxLayout(); kop_right.setSpacing(4); kop_right.setAlignment(Qt.AlignTop)
        slip_title = QLabel("SLIP GAJI")
        slip_title.setStyleSheet(f"font-size:22px;font-weight:bold;color:{C.TEXT_PRIMARY};")
        slip_title.setAlignment(Qt.AlignRight)

        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame{border:none;}")
        info_lay = QVBoxLayout(info_frame); info_lay.setSpacing(2); info_lay.setContentsMargins(0,0,0,0)
        for label, val in [("Tanggal",    tanggal_slip),
                            ("No Ref",    no_ref),
                            ("Nama Staff", nama_staff)]:
            r = QHBoxLayout()
            r.addWidget(self._lbl(label, f"font-size:11px;color:{C.TEXT_MUTED};"))
            r.addWidget(self._lbl(f":  {val}", f"font-size:11px;color:{C.TEXT_PRIMARY};"))
            r.addStretch()
            info_lay.addLayout(r)

        kop_right.addWidget(slip_title)
        kop_right.addWidget(info_frame)

        kop.addLayout(kop_left, 1)
        kop.addLayout(kop_right)
        bv.addLayout(kop)
        bv.addSpacing(18)
        bv.addWidget(self._hdiv())
        bv.addSpacing(14)

        # ── Info pegawai ─────────────────────────────────────────────
        info_grid = QHBoxLayout()
        left_col = QVBoxLayout(); left_col.setSpacing(6)
        right_col = QVBoxLayout(); right_col.setSpacing(6)
        for label, val in [("Nama", sd['nama']), ("Jabatan", sd['jabatan'])]:
            r = QHBoxLayout()
            r.addWidget(self._lbl(label, f"font-size:12px;color:{C.TEXT_MUTED};font-weight:600;"))
            r.addWidget(self._lbl(f":  {val}", f"font-size:12px;color:{C.TEXT_PRIMARY};"))
            r.addStretch()
            left_col.addLayout(r)
        for label, val in [("Alamat", sd['alamat']), ("No. Tlpon", sd['telp'])]:
            r = QHBoxLayout()
            r.addWidget(self._lbl(label, f"font-size:12px;color:{C.TEXT_MUTED};font-weight:600;"))
            r.addWidget(self._lbl(f":  {val}", f"font-size:12px;color:{C.TEXT_PRIMARY};"))
            r.addStretch()
            right_col.addLayout(r)
        info_grid.addLayout(left_col, 1)
        info_grid.addLayout(right_col, 1)
        bv.addLayout(info_grid)
        bv.addSpacing(18)

        # ── Tabel rincian per murid ──────────────────────────────────
        n_rows = len(murid_rows)
        tbl = QTableWidget(n_rows, 3)
        tbl.setHorizontalHeaderLabels(["NO", "KETERANGAN", "JUMLAH"])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setShowGrid(True)
        tbl.setFocusPolicy(Qt.NoFocus)
        tbl.setStyleSheet(f"""
            QTableWidget{{border:1px solid {C.BORDER};background:white;}}
            QHeaderView::section{{
                background:{C.SURFACE_ALT};padding:10px 12px;border:none;
                border-bottom:1px solid {C.BORDER};border-right:1px solid {C.BORDER};
                color:{C.TEXT_MUTED_STRONG};font-weight:bold;font-size:11px;
            }}
            QTableWidget::item{{padding:10px 12px;color:{C.TEXT_PRIMARY};font-size:12px;}}
        """)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        tbl.setColumnWidth(0, 50)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        tbl.setColumnWidth(2, 130)

        ROW_H = 70
        for row_data in murid_rows:
            r = row_data["no"] - 1
            tbl.setItem(r, 0, QTableWidgetItem(str(row_data["no"])))
            tgl_str = ", ".join(row_data["tanggal_list"])
            tarif_info = f"*{row_data['tarif']:,}"
            if row_data.get("transport_total"):
                tarif_info += f" +transport {_fmt_rp(row_data['transport_total'])}"
            ket = QTableWidgetItem(
                f"{row_data['murid']} - {row_data['metode']} ({tarif_info})\n{tgl_str}"
            )
            ket.setFont(QFont("Segoe UI", 10))
            tbl.setItem(r, 1, ket)
            j_item = QTableWidgetItem(_fmt_rp(row_data["subtotal"]))
            j_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            j_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            tbl.setItem(r, 2, j_item)
            tbl.setRowHeight(r, ROW_H)

        tbl.setFixedHeight(36 + ROW_H * n_rows + 4)
        bv.addWidget(tbl)
        bv.addSpacing(14)

        # ── Total ────────────────────────────────────────────────────
        total_row = QHBoxLayout()
        terbilang_lbl = QLabel(_terbilang(grand_total).capitalize())
        terbilang_lbl.setStyleSheet(
            f"font-size:11px;color:{C.TEXT_BODY};font-style:italic;"
            f"background:{C.SURFACE_ALT};border:1px solid {C.BORDER};"
            "border-radius:6px;padding:6px 12px;")
        total_row.addWidget(terbilang_lbl, 1)
        total_row.addStretch()

        total_box = QFrame()
        total_box.setStyleSheet("QFrame{border:none;}")
        tbl_v = QHBoxLayout(total_box); tbl_v.setSpacing(16)
        tbl_v.addWidget(self._lbl("TOTAL DITERIMA :",
            f"font-size:12px;font-weight:bold;color:{C.TEXT_BODY};background:transparent;"))
        tbl_v.addWidget(self._lbl(_fmt_rp(grand_total).replace(",-",""),
            f"font-size:16px;font-weight:bold;color:{C.ACCENT};background:transparent;"))
        total_row.addWidget(total_box)
        bv.addLayout(total_row)
        bv.addSpacing(28)

        # ── TTD ──────────────────────────────────────────────────────
        bv.addWidget(self._hdiv())
        bv.addSpacing(20)

        ttd_row = QHBoxLayout()
        ttd_row.addStretch()

        ttd_col = QVBoxLayout(); ttd_col.setSpacing(4); ttd_col.setAlignment(Qt.AlignHCenter)
        ttd_col.addWidget(self._lbl(tanggal_slip,
            f"font-size:11px;color:{C.TEXT_MUTED};background:transparent;"))
        ttd_col.addSpacing(6)
        # Tanda tangan (gambar tanda tangan asli). Fallback ke teks kursif
        # jika file ttd_gm.png belum diletakkan di folder yang sama.
        _TTD_H = 46
        ttd_sign = QLabel()
        ttd_sign.setAlignment(Qt.AlignCenter)
        ttd_sign.setStyleSheet("background:transparent;border:none;")
        _ttd_path = resource_path("ttd_gm.png")
        if os.path.exists(_ttd_path):
            _ttd_px = QPixmap(_ttd_path).scaledToHeight(_TTD_H, Qt.SmoothTransformation)
            ttd_sign.setPixmap(_ttd_px)
            ttd_sign.setFixedSize(_ttd_px.size())
        else:
            ttd_sign.setText(sd['ttd_name'])
            ttd_sign.setStyleSheet(
                f"font-size:18px;font-family:cursive;color:{C.ACCENT_DARKER};background:transparent;")
        ttd_col.addWidget(ttd_sign, 0, Qt.AlignHCenter)
        garis = QFrame(); garis.setFrameShape(QFrame.HLine)
        garis.setStyleSheet(f"color:{C.TEXT_PRIMARY};max-height:1px;")
        ttd_col.addWidget(garis)
        ttd_col.addWidget(self._lbl(sd['ttd_name'],
            f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;"))
        ttd_col.addWidget(self._lbl(sd['ttd_jabatan'],
            f"font-size:10px;color:{C.TEXT_MUTED};background:transparent;"))
        ttd_col.addWidget(self._lbl("MELODY VIOLIN SCHOOL",
            f"font-size:10px;color:{C.TEXT_MUTED};background:transparent;"))

        penerima_col = QVBoxLayout(); penerima_col.setSpacing(4)
        penerima_col.addWidget(self._lbl("Penerima",
            f"font-size:11px;color:{C.TEXT_MUTED};background:transparent;"))
        penerima_col.addSpacing(40)
        penerima_col.addWidget(self._lbl(sd['nama'],
            f"font-size:12px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;"))

        ttd_row.addLayout(penerima_col)
        ttd_row.addStretch()
        ttd_row.addLayout(ttd_col)
        bv.addLayout(ttd_row)

        scroll.setWidget(body)
        root.addWidget(scroll)

        # ── Bottom bar ────────────────────────────────────────────────
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"QFrame{{background:white;border-top:1px solid {C.BORDER};}}")
        bl = QHBoxLayout(bar); bl.setContentsMargins(20,0,20,0); bl.setSpacing(12)

        kembali_btn = QPushButton(" Kembali")
        kembali_btn.setIcon(svg_icon("arrow-left", C.TEXT_PRIMARY, 13))
        kembali_btn.setFixedHeight(36)
        kembali_btn.setCursor(Qt.PointingHandCursor)
        kembali_btn.setStyleSheet(f"""
            QPushButton{{background:white;color:{C.TEXT_PRIMARY};border:1.5px solid {C.BORDER};
                border-radius:8px;font-size:12px;font-weight:bold;padding:0 16px;}}
            QPushButton:hover{{background:{C.SURFACE_ALT};}}
        """)
        kembali_btn.clicked.connect(self.reject)

        # Sudah dibayar jika tidak ada sesi Pending untuk guru ini
        _sudah_dibayar = len(self._sesi_ids) == 0

        simpan_btn = QPushButton("Simpan Pembayaran")
        simpan_btn.setFixedHeight(36)
        simpan_btn.setCursor(Qt.PointingHandCursor)
        simpan_btn.setEnabled(not _sudah_dibayar)
        simpan_btn.setStyleSheet(f"""
            QPushButton{{background:{C.ACCENT};color:white;border:none;
                border-radius:8px;font-size:12px;font-weight:bold;padding:0 18px;}}
            QPushButton:hover{{background:{C.ACCENT_DARK};}}
            QPushButton:disabled{{background:{C.ACCENT_BORDER};color:{C.ACCENT_BG};}}
        """)
        if _sudah_dibayar:
            simpan_btn.setText(" Tersimpan")
            simpan_btn.setIcon(svg_icon("check", "white", 13))
        simpan_btn.clicked.connect(self._simpan_pembayaran)
        self._simpan_btn = simpan_btn
        simpan_btn.setVisible(not self._preview_only)

        dl_btn = QPushButton(" Download PDF")
        dl_btn.setIcon(svg_icon("download", C.ACCENT, 14))
        dl_btn.setFixedHeight(36)
        dl_btn.setCursor(Qt.PointingHandCursor)
        dl_btn.setStyleSheet(f"""
            QPushButton{{background:white;color:{C.ACCENT};border:1.5px solid {C.ACCENT};
                border-radius:8px;font-size:12px;font-weight:bold;padding:0 18px;}}
            QPushButton:hover{{background:{C.ACCENT_BG};}}
        """)
        self._slip_body   = body
        self._slip_no_ref = no_ref
        dl_btn.clicked.connect(self._download_pdf)

        bl.addWidget(kembali_btn)
        bl.addStretch()
        bl.addWidget(simpan_btn)
        bl.addWidget(dl_btn)
        root.addWidget(bar)

    def _download_pdf(self):
        from PyQt5.QtWidgets import QFileDialog
        from PyQt5.QtPrintSupport import QPrinter
        from PyQt5.QtGui import QPainter

        default_name = f"SlipGaji_{self._guru_name.replace(' ', '_')}_{self._slip_no_ref}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan PDF", default_name, "PDF Files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPrinter.A4)
        printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)

        body = self._slip_body
        painter = QPainter(printer)
        scale = printer.width() / max(body.width(), 1)
        painter.scale(scale, scale)
        body.render(painter)
        painter.end()

        show_toast(self, "Berhasil", f"PDF berhasil disimpan:\n{path}", "success")

    @_no_double_submit
    def _simpan_pembayaran(self):
        nama    = self._guru_name
        total   = self._total_gaji
        periode = self._periode
        tgl     = datetime.today().strftime("%Y-%m-%d")
        sesi_ids = self._sesi_ids

        if not sesi_ids:
            show_toast(self, "Info", f"Tidak ada sesi yang perlu dibayar untuk {nama}.", "warning")
            return

        # 1. Cari guru_id dari tabel guru
        guru_id = None
        try:
            row = DB.fetch_one("SELECT id FROM guru WHERE nama=?", (nama,))
            if row:
                guru_id = row["id"]
        except Exception:
            pass

        # 2. Update status_gaji di jadwal_sesi untuk semua sesi yang dibayar
        try:
            try:
                DB.execute("ALTER TABLE jadwal_sesi ADD COLUMN status_gaji TEXT DEFAULT 'Pending'")
            except Exception:
                pass
            placeholders = ",".join("?" * len(sesi_ids))
            DB.execute(
                f"UPDATE jadwal_sesi SET status_gaji='Dibayar' WHERE id IN ({placeholders})",
                tuple(sesi_ids)
            )
        except Exception:
            pass

        # 3. Simpan ke tabel gaji_guru — cek duplikat (guru + periode) dulu
        #    agar klik ganda atau buka-tutup dialog tidak membuat baris ganda.
        gaji_guru_id = None
        if guru_id:
            try:
                existing_gg = DB.fetch_one(
                    "SELECT id FROM gaji_guru WHERE guru_id=? AND periode=?",
                    (guru_id, periode)
                )
                if existing_gg:
                    gaji_guru_id = existing_gg["id"]
                    DB.execute(
                        "UPDATE gaji_guru SET jumlah_sesi=?, nominal_total=?,"
                        " tanggal_bayar=?, status='Sudah Dibayar'"
                        " WHERE id=?",
                        (len(sesi_ids), total, tgl, gaji_guru_id)
                    )
                else:
                    gaji_guru_id = DB.execute(
                        "INSERT INTO gaji_guru "
                        "(guru_id, periode, jumlah_sesi, nominal_total,"
                        " tanggal_bayar, no_referensi, status) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'Sudah Dibayar')",
                        (guru_id, periode, len(sesi_ids), total, tgl, self._no_ref)
                    )
            except Exception:
                pass

        # 4. Simpan ke transaksi_keuangan [GAJI-GURU] — format harus sama dgn _sinkron_db() di LaporanKeuangan.py
        try:
            id_str   = str(gaji_guru_id) if gaji_guru_id else "auto"
            ket      = f"[GAJI-GURU] {nama} | {periode} | {len(sesi_ids)} sesi | ID:{id_str}"
            prefix   = f"[GAJI-GURU] {nama} | {periode} |"
            tgl_disp = datetime.today().strftime("%d/%m/%Y")
            bukti_marker = f"SLIP-GURU:{nama}:{periode}"
            existing_trx = DB.fetch_one(
                "SELECT id FROM transaksi_keuangan WHERE keterangan LIKE ?",
                (prefix + "%",)
            )
            if existing_trx:
                DB.execute(
                    "UPDATE transaksi_keuangan SET keterangan=?, nominal=?, bukti_path=?"
                    " WHERE id=?",
                    (ket, total, bukti_marker, existing_trx["id"])
                )
            else:
                DB.execute(
                    "INSERT INTO transaksi_keuangan"
                    " (tanggal, jenis, keterangan, nominal, bukti_path)"
                    " VALUES (?, 'Kredit', ?, ?, ?)",
                    (tgl_disp, ket, total, bukti_marker)
                )
        except Exception:
            pass

        # 5. Disable tombol, beri feedback
        self._simpan_btn.setEnabled(False)
        self._simpan_btn.setText(" Tersimpan")
        self._simpan_btn.setIcon(svg_icon("check", "white", 13))
        self._sesi_ids = []

        # 6. Panggil callback agar tabel sesi guru di-refresh
        if self._on_saved:
            self._on_saved(nama, total)

        show_toast(self, "Berhasil", f"Pembayaran gaji {nama} ({periode}) sebesar Rp{total:,.0f} telah disimpan.", "success")

    def _lbl(self, text, style):
        l = QLabel(text); l.setStyleSheet(style); return l

    def _hdiv(self):
        f = QFrame(); f.setFrameShape(QFrame.HLine)
        f.setStyleSheet(f"color:{C.BORDER};"); return f


#  HELPER: Load sesi terlaksana dari jadwal_sesi (per guru optional)

_DURASI_METODE = {"Offline": 45, "Home Visit": 45, "Online": 30}

def _load_sesi_terlaksana(guru_filter="all", murid_filter="all"):
    """
    Ambil semua sesi dengan status='Terlaksana' dari jadwal_sesi,
    join dengan murid, guru, kursus untuk detail tampilan.

    Total gaji per sesi dihitung LIVE dari tarif di Pengaturan
    (tabel pengaturan_gaji), dipisah per metode:
        Offline    -> gaji_guru             x 1 sesi
        Online     -> gaji_guru_online      x 1 sesi
        Home Visit -> gaji_guru_home_visit  x 1 sesi
                      + bagian transport per sesi

    Bagian transport per sesi (khusus Home Visit) = total biaya_transport
    yang tercatat di pembayaran_sesi_murid utk pendaftaran tsb, dibagi
    total jumlah_sesi yang tercatat di sana — supaya biaya transport satu
    paket Home Visit terbagi rata ke tiap sesi yang sudah Terlaksana,
    bukan dihitung penuh berkali-kali per sesi.
    """
    try:
        from database import DB
    except ImportError:
        return []

    # Pastikan kolom status_gaji ada di jadwal_sesi (migration-safe)
    try:
        DB.execute("ALTER TABLE jadwal_sesi ADD COLUMN status_gaji TEXT DEFAULT 'Pending'")
    except Exception:
        pass

    try:
        cfg = DB.get_pengaturan_gaji()
    except Exception:
        cfg = {}
    _fallback = cfg.get("gaji_guru_visit_online", 35000)
    _rate = {
        "Offline":    cfg.get("gaji_guru", 40000),
        "Online":     cfg.get("gaji_guru_online", _fallback),
        "Home Visit": cfg.get("gaji_guru_home_visit", _fallback),
    }

    where_parts = ["js.status = 'Terlaksana'"]
    params = []
    if guru_filter != "all":
        where_parts.append("g.nama = ?")
        params.append(guru_filter)
    if murid_filter != "all":
        where_parts.append("m.nama = ?")
        params.append(murid_filter)

    where_clause = " AND ".join(where_parts)

    rows = DB.fetch_all(f"""
        SELECT
            js.id,
            js.pendaftaran_id,
            js.tanggal,
            COALESCE(g.nama, '–')  AS nama_guru,
            m.nama                  AS nama_murid,
            k.nama                  AS nama_kursus,
            js.metode,
            js.status,
            COALESCE(js.status_gaji, 'Pending') AS status_gaji
        FROM jadwal_sesi js
        JOIN pendaftaran_kursus pk ON pk.id = js.pendaftaran_id
        JOIN murid  m ON m.id  = pk.murid_id
        JOIN kursus k ON k.id  = pk.kursus_id
        LEFT JOIN guru g ON g.id = js.guru_id
        WHERE {where_clause}
        ORDER BY js.tanggal DESC, js.jam_mulai, m.nama
    """, tuple(params))

    # total biaya_transport ÷ total jumlah_sesi dari pembayaran_sesi_murid,
    # dikelompokkan via pembayaran_murid.pendaftaran_id.
    _transport_per_sesi = {}  # pendaftaran_id -> rupiah / sesi
    try:
        tr_rows = DB.fetch_all("""
            SELECT pm.pendaftaran_id          AS pendaftaran_id,
                   SUM(psm.biaya_transport)   AS total_transport,
                   SUM(psm.jumlah_sesi)       AS total_sesi
            FROM pembayaran_sesi_murid psm
            JOIN pembayaran_murid pm ON pm.id = psm.pembayaran_id
            WHERE psm.metode = 'Home Visit' AND pm.pendaftaran_id IS NOT NULL
            GROUP BY pm.pendaftaran_id
        """)
        for tr in tr_rows:
            total_sesi = tr["total_sesi"] or 0
            if total_sesi > 0:
                _transport_per_sesi[tr["pendaftaran_id"]] = (tr["total_transport"] or 0) / total_sesi
    except Exception:
        pass

    result = []
    for r in rows:
        metode    = r["metode"] or "Offline"
        durasi    = _DURASI_METODE.get(metode, 45)
        biaya_les = _rate.get(metode, _rate["Offline"])

        transport = 0
        if metode == "Home Visit":
            transport = _transport_per_sesi.get(r["pendaftaran_id"], 0)

        total = biaya_les + transport
        result.append({
            "id":             r["id"],
            "pendaftaran_id": r["pendaftaran_id"],
            "tanggal":        r["tanggal"] or "-",
            "nama_guru":      r["nama_guru"],
            "nama_murid":     r["nama_murid"],
            "nama_kursus":    r["nama_kursus"],
            "metode":         metode,
            "durasi":         durasi,
            "biaya_les":      biaya_les,
            "transport":      transport,
            "total":          total,
            "status":         r["status"] or "Terlaksana",
            "status_gaji":    r["status_gaji"] or "Pending",
        })
    return result


def _load_guru_list_db():
    """Ambil daftar nama guru aktif dari database."""
    try:
        from database import DB
        rows = DB.fetch_all("SELECT nama FROM guru WHERE status='Aktif' ORDER BY nama")
        return [r["nama"] for r in rows]
    except Exception:
        return []


#  WIDGET: SESI GURU  (redesign — data dari jadwal_sesi)

class SesiGuruWidget(QWidget):
    def __init__(self, current_user=None):
        super().__init__()
        _bersihkan_duplikat_transaksi_gaji()
        self.setStyleSheet(f"background-color: {C.SURFACE_ALT};")
        self._current_user   = current_user
        self._selected_guru  = "all"
        self._selected_murid = "all"
        self.init_ui()

    def init_ui(self):
        v = QVBoxLayout(self)
        # Margin kiri-kanan 0 — sudah diberi 35px oleh PembayaranMainWidget di level atas
        v.setContentsMargins(0, 20, 0, 30)
        v.setSpacing(20)

        # ── Filter row ────────────────────────────────────────────────
        filter_row = QHBoxLayout(); filter_row.setSpacing(10)

        filter_lbl = QLabel("Filter Guru:")
        filter_lbl.setStyleSheet(f"font-size:13px;color:{C.TEXT_BODY};background:transparent;")

        self._guru_combo = QComboBox()
        self._guru_combo.addItem("Seluruh Guru", "all")
        for g in _load_guru_list_db():
            self._guru_combo.addItem(g, g)
        self._guru_combo.setFixedHeight(38)
        self._guru_combo.setMinimumWidth(200)
        self._guru_combo.setCursor(Qt.PointingHandCursor)
        style_combo(self._guru_combo)
        self._guru_combo.currentIndexChanged.connect(self._on_guru_combo_changed)

        # Filter murid muncul setelah guru dipilih, terisi otomatis dari murid yang diajar guru tsb
        self._murid_combo = QComboBox()
        self._murid_combo.addItem("Seluruh Murid", "all")
        self._murid_combo.setFixedHeight(38)
        self._murid_combo.setMinimumWidth(170)
        self._murid_combo.setCursor(Qt.PointingHandCursor)
        style_combo(self._murid_combo)
        self._murid_combo.currentIndexChanged.connect(self._on_murid_combo_changed)
        self._murid_combo.setVisible(False)

        bulan_list = [
            "Januari", "Februari", "Maret", "April",
            "Mei", "Juni", "Juli", "Agustus",
            "September", "Oktober", "November", "Desember"
        ]
        self._bulan_combo = QComboBox()
        self._bulan_combo.addItem("Semua Bulan", 0)
        for i, nama in enumerate(bulan_list, start=1):
            self._bulan_combo.addItem(nama, i)
        self._bulan_combo.setCurrentIndex(datetime.now().month)
        self._bulan_combo.setFixedHeight(38)
        self._bulan_combo.setCursor(Qt.PointingHandCursor)
        style_combo(self._bulan_combo)
        self._bulan_combo.currentIndexChanged.connect(self._refresh_table)

        self._tahun_spin = QSpinBox()
        self._tahun_spin.setRange(2000, 2100)
        self._tahun_spin.setValue(datetime.now().year)
        self._tahun_spin.setFixedHeight(38)
        self._tahun_spin.setFixedWidth(90)
        self._tahun_spin.setCursor(Qt.PointingHandCursor)
        self._tahun_spin.setStyleSheet(f"""
            QSpinBox{{border:1.5px solid {C.ACCENT_BORDER};border-radius:10px;
                background:white;padding:0 10px;font-size:13px;color:{C.TEXT_PRIMARY};}}
            QSpinBox:focus{{border:2px solid {C.ACCENT};}}
        """)
        self._tahun_spin.valueChanged.connect(self._refresh_table)

        # Tombol Slip Gaji Guru
        self._slip_btn = QPushButton("Lihat Slip Gaji")
        self._slip_btn.setFixedHeight(38)
        self._slip_btn.setCursor(Qt.PointingHandCursor)
        self._slip_btn.setStyleSheet(f"""
            QPushButton{{background:{C.ACCENT};color:white;border:none;
                border-radius:8px;font-weight:bold;font-size:13px;padding:0 20px;}}
            QPushButton:hover{{background:{C.ACCENT_DARK};}}
        """)
        self._slip_btn.clicked.connect(self._show_slip_guru)
        self._slip_btn.setVisible(False)

        filter_row.addWidget(filter_lbl)
        filter_row.addWidget(self._guru_combo)
        filter_row.addWidget(self._murid_combo)
        filter_row.addWidget(self._bulan_combo)
        filter_row.addWidget(self._tahun_spin)
        filter_row.addStretch()
        filter_row.addWidget(self._slip_btn)
        v.addLayout(filter_row)

        # ── Detail card (total sesi guru) ─────────────────────────────
        self.detail_card = self._build_detail_card()
        self.detail_card.setVisible(False)
        v.addWidget(self.detail_card)

        # ── Table card ────────────────────────────────────────────────
        table_frame = QFrame()
        table_frame.setStyleSheet("QFrame{background:white;border-radius:14px;border:none;}")
        tv = QVBoxLayout(table_frame)
        tv.setContentsMargins(22, 20, 22, 16)
        tv.setSpacing(14)

        # Title toolbar
        tb = QHBoxLayout()
        self.section_title = QLabel("Sesi Terlaksana Guru")
        self.section_title.setStyleSheet(
            f"font-size:18px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;")
        tb.addWidget(self.section_title)
        tb.addStretch()
        tv.addLayout(tb)

        cols = ["NO", "TANGGAL", "GURU", "MURID", "LES",
                "METODE", "DURASI", "TOTAL", "STATUS SESI", "STATUS GAJI"]

        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(f"""
            QTableWidget{{border:none;background:white;}}
            QHeaderView::section{{
                background:{C.SURFACE_ALT};padding:10px 8px;border:none;
                border-bottom:2px solid {C.SURFACE_HOVER};
                color:{C.TEXT_MUTED_STRONG};font-weight:bold;font-size:10px;
            }}
            QTableWidget::item{{
                padding:12px 8px;border-bottom:1px solid {C.SURFACE_HOVER};
                color:{C.TEXT_BODY};font-size:12px;
            }}
            QTableWidget::item:selected{{background:{C.ACCENT_BG};color:{C.TEXT_PRIMARY};}}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        # Kolom tetap lebar
        hdr.setSectionResizeMode(0, QHeaderView.Fixed); self.table.setColumnWidth(0, 44)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed); self.table.setColumnWidth(6, 80)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed); self.table.setColumnWidth(7, 120)
        hdr.setSectionResizeMode(8, QHeaderView.Fixed); self.table.setColumnWidth(8, 130)
        hdr.setSectionResizeMode(9, QHeaderView.Fixed); self.table.setColumnWidth(9, 130)
        # Delegate kolom 8 STATUS (Terlaksana hijau) & 9 STATUS GAJI (Dibayar/Pending)
        self.table.setItemDelegateForColumn(8, TerlaksanaDelegate(self.table))
        self._status_gaji_delegate_guru = StatusGajiDelegate(self.table)
        self.table.setItemDelegateForColumn(9, self._status_gaji_delegate_guru)
        tv.addWidget(self.table)

        # Footer info
        self._info_lbl_sesi = QLabel("Menampilkan 0 sesi")
        self._info_lbl_sesi.setStyleSheet(
            f"font-size:11px;color:{C.TEXT_FAINT};padding:10px 18px;background:transparent;")
        tv.addWidget(self._info_lbl_sesi)
        v.addWidget(table_frame)

        self._refresh_table()

    def _build_detail_card(self):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame{{background:white;border-radius:14px;border:1.5px solid {C.ACCENT_BG_STRONG};}}
            QLabel{{background:transparent;border:none;}}
        """)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(30)

        left = QVBoxLayout(); left.setSpacing(4)
        self.detail_sesi_title = QLabel("TOTAL SESI TERLAKSANA")
        self.detail_sesi_title.setStyleSheet(
            f"font-size:11px;font-weight:bold;color:{C.ACCENT};background:transparent;")
        self.detail_sesi_lbl = QLabel("0")
        self.detail_sesi_lbl.setStyleSheet(
            f"font-size:26px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;")
        left.addWidget(self.detail_sesi_title)
        left.addWidget(self.detail_sesi_lbl)

        lay.addLayout(left)
        lay.addStretch()
        return card

    def _get_rows(self):
        rows = _load_sesi_terlaksana(self._selected_guru, self._selected_murid)

        bulan_filter = self._bulan_combo.currentData() if hasattr(self, '_bulan_combo') else 0
        tahun_filter = self._tahun_spin.value() if hasattr(self, '_tahun_spin') else None
        if not bulan_filter and tahun_filter is None:
            return rows

        filtered = []
        for r in rows:
            try:
                parts = (r["tanggal"] or "").split("-")
                bulan_data = int(parts[1])
                tahun_data = int(parts[2])
            except Exception:
                continue
            if bulan_filter and bulan_data != bulan_filter:
                continue
            if tahun_filter is not None and tahun_data != tahun_filter:
                continue
            filtered.append(r)
        return filtered

    def _refresh_table(self):
        rows = self._get_rows()

        self.table.setRowCount(0)
        for i, row in enumerate(rows):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 50)

            def _item(text, bold=False, color=f"{C.TEXT_BODY}",
                      align=Qt.AlignVCenter | Qt.AlignLeft):
                it = QTableWidgetItem(str(text))
                if bold:
                    it.setFont(QFont("Segoe UI", 10, QFont.Bold))
                it.setForeground(QColor(color))
                it.setTextAlignment(align)
                return it

            metode_val = row["metode"]
            metode_colors = {
                "Home Visit": f"{C.SUCCESS_DARK}",
                "Online":     f"{C.ACCENT_DARKER}",
                "Offline":    "#92400E",
            }
            m_color = metode_colors.get(metode_val, f"{C.TEXT_MUTED}")

            # 0 NO
            self.table.setItem(r, 0, _item(f"{i+1:02d}",
                align=Qt.AlignCenter | Qt.AlignVCenter))
            # 1 TANGGAL
            self.table.setItem(r, 1, _item(row["tanggal"],
                bold=True, color=f"{C.TEXT_PRIMARY}"))
            # 2 GURU
            self.table.setItem(r, 2, _item(row["nama_guru"]))
            # 3 MURID
            self.table.setItem(r, 3, _item(row["nama_murid"],
                bold=True, color=f"{C.ACCENT}"))
            # 4 LES
            self.table.setItem(r, 4, _item(row.get("nama_kursus") or "-"))
            # 5 METODE
            self.table.setItem(r, 5, _item(metode_val, bold=True, color=m_color))
            # 6 DURASI
            self.table.setItem(r, 6, _item(f"{row['durasi']} Menit",
                align=Qt.AlignCenter | Qt.AlignVCenter))
            # 7 TOTAL
            total_val = row["total"]
            it_tot = QTableWidgetItem(f"Rp {total_val:,.0f}".replace(",", "."))
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot.setFont(QFont("Segoe UI", 10, QFont.Bold))
            it_tot.setForeground(QColor(f"{C.TEXT_PRIMARY}"))
            self.table.setItem(r, 7, it_tot)
            # 8 STATUS — TerlaksanaDelegate paints badge hijau
            self.table.setItem(r, 8, QTableWidgetItem("Terlaksana"))
            # 9 STATUS GAJI — StatusGajiDelegate paints badge biru/abu
            sg_item = QTableWidgetItem(row.get("status_gaji", "Pending"))
            sg_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.table.setItem(r, 9, sg_item)

        if hasattr(self, '_info_lbl_sesi'):
            self._info_lbl_sesi.setText(f"Menampilkan {len(rows)} sesi")

    def _on_guru_combo_changed(self, index):
        key = self._guru_combo.itemData(index)
        self._selected_guru  = key
        self._selected_murid = "all"

        show_extra = key != "all"
        self.detail_card.setVisible(show_extra)
        self._slip_btn.setVisible(show_extra)
        self._murid_combo.setVisible(show_extra)

        # Isi ulang daftar murid sesuai guru yang dipilih
        self._murid_combo.blockSignals(True)
        self._murid_combo.clear()
        self._murid_combo.addItem("Seluruh Murid", "all")

        if show_extra:
            self.section_title.setText(f"Sesi Terlaksana – {key}")
            all_rows = _load_sesi_terlaksana(key)
            # Daftar murid unik yang diajar guru ini (satu guru bisa
            # mengajar banyak murid)
            murid_names = sorted({
                row["nama_murid"] for row in all_rows if row.get("nama_murid")
            })
            for nama in murid_names:
                self._murid_combo.addItem(nama, nama)
            # Update total sesi card
            self.detail_sesi_lbl.setText(str(len(all_rows)))
        else:
            self.section_title.setText("Sesi Terlaksana Guru")

        self._murid_combo.blockSignals(False)

        self._refresh_table()

    def _on_murid_combo_changed(self, index):
        if index < 0:
            return
        key = self._murid_combo.itemData(index)
        self._selected_murid = key if key else "all"

        if self._selected_guru != "all":
            if self._selected_murid != "all":
                self.section_title.setText(
                    f"Sesi Terlaksana – {self._selected_guru} – {self._selected_murid}")
            else:
                self.section_title.setText(f"Sesi Terlaksana – {self._selected_guru}")
            # Update total sesi card sesuai kombinasi filter guru + murid
            filtered_rows = _load_sesi_terlaksana(self._selected_guru, self._selected_murid)
            self.detail_sesi_lbl.setText(str(len(filtered_rows)))

        self._refresh_table()

    def _show_slip_guru(self):
        dlg = SlipGajiGuruDialog(self, self._selected_guru, on_saved=self._on_slip_saved,
                                 current_user=self._current_user)
        dlg.setMinimumSize(600, 700)
        dlg.exec_()

    def _on_slip_saved(self, guru_name, total):
        self._refresh_table()
        if hasattr(self, "_on_stat_changed") and self._on_stat_changed:
            self._on_stat_changed()

    def _lbl(self, text, style):
        l = QLabel(text); l.setStyleSheet(style); return l


#  WIDGET UTAMA: CONTAINER DENGAN STAT CARDS CLICKABLE

class PembayaranMainWidget(QWidget):
    """
    Container utama. Stat cards di atas bisa diklik untuk berpindah halaman:
      0 → Kehadiran Admin  (PembayaranWidget)
      1 → Sesi Guru        (SesiGuruWidget)
      2 → Pembayaran Murid (placeholder)
    """
    _CARDS = [
        ("KEHADIRAN ADMIN",    "120",  0),
        ("SESI TERLAKSANA GURU", "–", 1),
        ("PEMBAYARAN MURID",   "–",    2),
    ]

    def __init__(self, current_user=None):
        super().__init__()
        self.setStyleSheet(f"background:{C.SURFACE_ALT};")
        self._current_user = current_user
        self._active_page = 0
        self._card_frames = []
        self._card_titles = []
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(35, 30, 35, 30)
        root.setSpacing(20)

        # ── Stat cards row ────────────────────────────────────────────
        sc = QHBoxLayout(); sc.setSpacing(16)
        self._stat_labels = []  # simpan referensi label nilai tiap card
        for title, val, page_idx in self._CARDS:
            card = self._make_card(title, val, page_idx)
            sc.addWidget(card)
        root.addLayout(sc)

        # ── Stacked content ───────────────────────────────────────────
        self._stack = QStackedWidget()
        self._w_kehadiran = PembayaranWidget(current_user=self._current_user)
        self._w_sesi      = SesiGuruWidget(current_user=self._current_user)
        self._w_murid     = PembayaranMuridWidget()
        self._stack.addWidget(self._w_kehadiran)  # 0
        self._stack.addWidget(self._w_sesi)        # 1
        self._stack.addWidget(self._w_murid)       # 2
        self._stack.setCurrentIndex(0)
        root.addWidget(self._stack)

        # Sambungkan callback after-save ke refresh_stats agar angka stat card
        # langsung berubah setelah data baru disimpan, tanpa perlu klik ulang.
        self._w_kehadiran._on_stat_changed = self.refresh_stats
        self._w_sesi._on_stat_changed      = self.refresh_stats
        self._w_murid._on_stat_changed     = self.refresh_stats

        self._highlight(0)
        self.refresh_stats()

    def refresh_stats(self):
        """Ambil data terbaru dari DB dan update semua angka stat card."""
        try:
            from database import DB
            queries = [
                "SELECT COUNT(*) FROM kehadiran_admin",
                "SELECT COUNT(*) FROM jadwal_sesi WHERE status='Terlaksana'",
                "SELECT COUNT(*) FROM pembayaran_sesi_murid",
            ]
            for i, sql in enumerate(queries):
                row = DB.fetch_one(sql)
                if row and i < len(self._stat_labels):
                    self._stat_labels[i].setText(str(row[0]))
        except Exception:
            pass

    def _make_card(self, title, val, page_idx):
        f = QFrame()
        f.setFixedHeight(110)
        f.setCursor(Qt.PointingHandCursor)
        f.setProperty("page", page_idx)
        f.mousePressEvent = lambda e, p=page_idx: self._switch(p)

        fl = QVBoxLayout(f)
        fl.setContentsMargins(20, 16, 20, 16)
        fl.setSpacing(8)

        t = QLabel(title)
        t.setStyleSheet("font-size:11px;font-weight:bold;letter-spacing:0.5px;background:transparent;")
        n = QLabel(val)
        n.setStyleSheet(f"font-size:32px;font-weight:bold;color:{C.TEXT_PRIMARY};background:transparent;")

        fl.addWidget(t); fl.addWidget(n)
        self._card_frames.append(f)
        self._card_titles.append(t)
        self._stat_labels.append(n)  # simpan referensi untuk refresh nanti
        return f

    def _switch(self, page_idx):
        self._active_page = page_idx
        self._stack.setCurrentIndex(page_idx)
        self._highlight(page_idx)
        self.refresh_stats()
        self._refresh_active_widget()

    def _refresh_active_widget(self):
        """Muat ulang data tabel widget yang sedang aktif dari DB."""
        w = self._stack.currentWidget()
        if hasattr(w, "_refresh_table"):
            w._refresh_table()
        elif hasattr(w, "_refresh"):
            w._refresh()

    def _highlight(self, active):
        for i, (f, t) in enumerate(zip(self._card_frames, self._card_titles)):
            if i == active:
                f.setStyleSheet(f"""
                    QFrame{{background:{C.ACCENT_BG};border:1.5px solid {C.ACCENT_BORDER};border-radius:14px;}}
                    QLabel{{background:transparent;border:none;}}
                """)
                t.setStyleSheet(f"font-size:11px;font-weight:bold;color:{C.ACCENT};"
                                "letter-spacing:0.5px;background:transparent;")
            else:
                f.setStyleSheet(f"""
                    QFrame{{background:white;border:1.5px solid {C.BORDER};border-radius:14px;}}
                    QLabel{{background:transparent;border:none;}}
                """)
                t.setStyleSheet(f"font-size:11px;font-weight:bold;color:{C.TEXT_FAINT};"
                                "letter-spacing:0.5px;background:transparent;")


    def showEvent(self, event):
        """Refresh stat card & tabel yang aktif setiap kali halaman Pembayaran dibuka."""
        super().showEvent(event)
        self.refresh_stats()
        self._refresh_active_widget()

    def set_current_user(self, username: str):
        """Dipanggil dari DashboardAdmin setelah login agar nama_staff di slip
        selalu mengikuti admin yang sedang aktif."""
        self._current_user = username
        # Propagate ke sub-widget (PembayaranWidget & SesiGuruWidget)
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            if hasattr(w, '_current_user'):
                w._current_user = username

    def _placeholder(self):
        return PembayaranMuridWidget()


#  DATA: PEMBAYARAN MURID

#  DIALOG: TAMBAH PEMBAYARAN MURID
#  Menyimpan ke tabel pembayaran_sesi_murid

class TambahPembayaranMuridDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tambah Pembayaran Murid")
        self.setFixedWidth(460)
        self.setStyleSheet("QDialog{background:white;} QWidget{background:white;} QLabel{background:transparent;}")
        self._build()

    def _build(self):
        from database import DB
        root = QVBoxLayout(self); root.setContentsMargins(28, 24, 28, 22); root.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("Tambah Pembayaran Murid")
        t.setStyleSheet(f"font-size:16px;font-weight:700;color:{C.TEXT_PRIMARY};")
        x = QPushButton(); x.setFixedSize(28,28); x.setCursor(Qt.PointingHandCursor)
        x.setIcon(svg_icon("x", C.TEXT_MUTED, 12))
        x.setStyleSheet(f"QPushButton{{border:none;background:{C.SURFACE_HOVER};border-radius:6px;}}QPushButton:hover{{background:{C.BORDER};}}")
        x.clicked.connect(self.reject)
        hdr.addWidget(t); hdr.addStretch(); hdr.addWidget(x)
        root.addLayout(hdr); root.addSpacing(20)

        def lbl(txt):
            l = QLabel(txt); l.setStyleSheet(f"font-size:12px;font-weight:600;color:{C.TEXT_SECONDARY};")
            return l

        def field(placeholder=""):
            e = QLineEdit(); e.setPlaceholderText(placeholder); e.setFixedHeight(36)
            e.setStyleSheet(f"""QLineEdit{{border:1px solid {C.BORDER_LIGHT};border-radius:7px;
                padding-left:10px;font-size:12px;color:{C.TEXT_DARKEST};background:white;}}
                QLineEdit:focus{{border:1px solid {C.ACCENT};}}""")
            return e

        def combo(items):
            c = QComboBox(); c.addItems(items); c.setFixedHeight(36)
            style_combo(c, radius=7, height=36, font_size=12, border=C.BORDER_LIGHT)
            return c

        form = QVBoxLayout(); form.setSpacing(12)

        # Tanggal Bayar
        r0 = QVBoxLayout(); r0.setSpacing(4)
        r0.addWidget(lbl("Tanggal Bayar"))
        self._tgl = field("YYYY-MM-DD")
        self._tgl.setText(datetime.now().strftime("%Y-%m-%d"))
        r0.addWidget(self._tgl); form.addLayout(r0)

        # Murid & Kursus (linked)
        r1 = QHBoxLayout(); r1.setSpacing(12)
        c1 = QVBoxLayout(); c1.setSpacing(4); c1.addWidget(lbl("Murid"))
        murid_rows = DB.fetch_all("SELECT id, nama FROM murid WHERE status='Aktif' ORDER BY nama")
        self._murid_combo = combo(["-- Pilih Murid --"] + [r["nama"] for r in murid_rows])
        self._murid_ids = {r["nama"]: r["id"] for r in murid_rows}
        c1.addWidget(self._murid_combo)
        c2 = QVBoxLayout(); c2.setSpacing(4); c2.addWidget(lbl("Kursus"))
        self._kursus_combo = combo(["-- Pilih Kursus --"])
        c2.addWidget(self._kursus_combo)
        r1.addLayout(c1); r1.addLayout(c2); form.addLayout(r1)
        self._murid_combo.currentIndexChanged.connect(self._on_murid_changed)

        # Guru & Metode
        r2 = QHBoxLayout(); r2.setSpacing(12)
        c3 = QVBoxLayout(); c3.setSpacing(4); c3.addWidget(lbl("Guru"))
        guru_rows = DB.fetch_all("SELECT id, nama FROM guru WHERE status='Aktif' ORDER BY nama")
        self._guru_combo = combo(["-- Pilih Guru --"] + [r["nama"] for r in guru_rows])
        self._guru_ids = {r["nama"]: r["id"] for r in guru_rows}
        c3.addWidget(self._guru_combo)
        c4 = QVBoxLayout(); c4.setSpacing(4); c4.addWidget(lbl("Metode"))
        self._metode_combo = combo(["Offline", "Online", "Home Visit"])
        c4.addWidget(self._metode_combo)
        r2.addLayout(c3); r2.addLayout(c4); form.addLayout(r2)
        self._metode_combo.currentIndexChanged.connect(self._on_metode_changed)

        # Jumlah Sesi & Biaya Les
        r3 = QHBoxLayout(); r3.setSpacing(12)
        c5 = QVBoxLayout(); c5.setSpacing(4); c5.addWidget(lbl("Jumlah Sesi"))
        self._sesi_spin = QSpinBox(); self._sesi_spin.setRange(1, 99)
        self._sesi_spin.setValue(4); self._sesi_spin.setFixedHeight(36)
        self._sesi_spin.setStyleSheet(f"""QSpinBox{{border:1px solid {C.BORDER_LIGHT};border-radius:7px;
            padding-left:10px;font-size:12px;color:{C.TEXT_DARKEST};background:white;}}
            QSpinBox:focus{{border:1px solid {C.ACCENT};}}""")
        c5.addWidget(self._sesi_spin)
        c6 = QVBoxLayout(); c6.setSpacing(4); c6.addWidget(lbl("Biaya Les / Sesi (Rp)"))
        self._biaya_les = field("cth: 80000")
        c6.addWidget(self._biaya_les)
        r3.addLayout(c5); r3.addLayout(c6); form.addLayout(r3)
        self._sesi_spin.valueChanged.connect(self._hitung_total)
        self._biaya_les.textChanged.connect(self._hitung_total)

        # Transport (muncul saat Home Visit)
        self._tr_row = QVBoxLayout(); self._tr_row.setSpacing(4)
        self._tr_row.addWidget(lbl("Biaya Transport (Rp)"))
        self._biaya_tr = field("cth: 15000")
        self._biaya_tr.setText("0")
        self._tr_row.addWidget(self._biaya_tr)
        self._tr_widget = QWidget()
        self._tr_widget.setLayout(self._tr_row)
        self._tr_widget.setVisible(False)
        form.addWidget(self._tr_widget)
        self._biaya_tr.textChanged.connect(self._hitung_total)

        # Total
        total_row = QHBoxLayout(); total_row.setSpacing(0)
        total_row.addWidget(lbl("TOTAL :"))
        total_row.addStretch()
        self._total_lbl = QLabel("Rp 0")
        self._total_lbl.setStyleSheet(f"font-size:15px;font-weight:700;color:{C.ACCENT};background:transparent;")
        total_row.addWidget(self._total_lbl)
        form.addLayout(total_row)

        root.addLayout(form); root.addSpacing(20)

        # Footer
        footer = QHBoxLayout()
        btn_batal = QPushButton(" Kembali")
        btn_batal.setIcon(svg_icon("arrow-left", C.TEXT_MUTED, 13))
        btn_batal.setFixedHeight(38); btn_batal.setCursor(Qt.PointingHandCursor)
        btn_batal.setStyleSheet(f"""QPushButton{{background:white;color:{C.TEXT_MUTED};border:1.5px solid {C.BORDER};
            border-radius:8px;font-size:13px;padding:0 16px;}}QPushButton:hover{{background:{C.SURFACE_ALT};}}""")
        btn_batal.clicked.connect(self.reject)

        btn_simpan = QPushButton("Simpan Pembayaran")
        btn_simpan.setFixedHeight(38); btn_simpan.setCursor(Qt.PointingHandCursor)
        btn_simpan.setStyleSheet(f"""QPushButton{{background:{C.ACCENT};color:white;border:none;
            border-radius:8px;font-size:13px;font-weight:700;padding:0 20px;}}
            QPushButton:hover{{background:{C.ACCENT_DARK};}}""")
        btn_simpan.clicked.connect(self._simpan)

        footer.addWidget(btn_batal); footer.addStretch(); footer.addWidget(btn_simpan)
        root.addLayout(footer)

        # Init tarif dari pengaturan_gaji
        tarif = DB.get_pengaturan_gaji()
        self._tarif_map = {
            "Offline":    tarif.get("gaji_guru", 40000),
            "Online":     tarif.get("gaji_guru_online", 35000),
            "Home Visit": tarif.get("gaji_guru_home_visit", 35000),
        }
        self._biaya_les.setText(str(self._tarif_map["Offline"]))
        self._hitung_total()

    def _on_murid_changed(self):
        from database import DB
        nama = self._murid_combo.currentText()
        mid  = self._murid_ids.get(nama)
        self._kursus_combo.clear()
        self._kursus_combo.addItem("-- Pilih Kursus --")
        if mid:
            rows = DB.fetch_all("""
                SELECT DISTINCT k.id, k.nama FROM pendaftaran_kursus pk
                JOIN kursus k ON k.id=pk.kursus_id
                WHERE pk.murid_id=? AND pk.status='Aktif'
                ORDER BY k.nama
            """, (mid,))
            self._kursus_ids = {r["nama"]: r["id"] for r in rows}
            for r in rows:
                self._kursus_combo.addItem(r["nama"])
        else:
            self._kursus_ids = {}

    def _on_metode_changed(self):
        metode = self._metode_combo.currentText()
        self._tr_widget.setVisible(metode == "Home Visit")
        self._biaya_les.setText(str(self._tarif_map.get(metode, 40000)))
        self._hitung_total()

    def _hitung_total(self):
        try:
            n    = self._sesi_spin.value()
            bl   = int(self._biaya_les.text().replace(".", "").replace(",", "") or 0)
            tr   = int(self._biaya_tr.text().replace(".", "").replace(",", "") or 0)
            tot  = bl * n + tr
            self._total_lbl.setText(f"Rp {tot:,.0f}".replace(",", "."))
        except Exception:
            self._total_lbl.setText("Rp 0")

    @_no_double_submit
    def _simpan(self):
        from database import DB

        nama_murid  = self._murid_combo.currentText()
        nama_kursus = self._kursus_combo.currentText()
        nama_guru   = self._guru_combo.currentText()
        tgl         = self._tgl.text().strip()
        metode      = self._metode_combo.currentText()
        n_sesi      = self._sesi_spin.value()

        errors = []
        if nama_murid.startswith("--"):  errors.append("• Murid")
        if nama_kursus.startswith("--"): errors.append("• Kursus")
        if not tgl:                       errors.append("• Tanggal Bayar")
        if errors:
            show_toast(self, "Perhatian", "Field berikut wajib diisi:\n" + "\n".join(errors), "warning")
            return

        murid_id  = self._murid_ids.get(nama_murid)
        guru_id   = self._guru_ids.get(nama_guru)
        kursus_id = getattr(self, "_kursus_ids", {}).get(nama_kursus)

        try:
            bl  = int(self._biaya_les.text().replace(".", "").replace(",", "") or 0)
            tr  = int(self._biaya_tr.text().replace(".", "").replace(",", "") or 0)
        except Exception:
            bl, tr = 0, 0

        total = bl * n_sesi + tr

        try:
            DB.execute("""
                INSERT INTO pembayaran_sesi_murid
                    (murid_id, guru_id, kursus_id, tanggal_bayar,
                     jumlah_sesi, metode, biaya_les, biaya_transport, total_bayar, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Lunas')
            """, (murid_id, guru_id, kursus_id, tgl, n_sesi, metode, bl, tr, total))
            show_toast(self, "Berhasil", f"Pembayaran {nama_murid} – {nama_kursus} ({n_sesi}x sesi) berhasil disimpan.", "success")
            self.accept()
        except Exception as e:
            show_toast(self, "Gagal", f"Gagal menyimpan:\n{str(e)}", "error")


#  WIDGET: PEMBAYARAN MURID
#  Menampilkan data dari transaksi_keuangan — hanya Les & Pendaftaran

class PembayaranMuridWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color:{C.SURFACE_ALT};")
        self._init_ui()

    def _init_ui(self):
        v = QVBoxLayout(self)
        # Margin kiri-kanan 0 — sudah diberi 35px oleh PembayaranMainWidget di level atas
        v.setContentsMargins(0, 20, 0, 30)
        v.setSpacing(20)

        # ── Heading ───────────────────────────────────────────────────
        head = QVBoxLayout(); head.setSpacing(2)
        head.addWidget(self._lbl("Pembayaran Murid",
                                 f"font-size:20px;font-weight:bold;color:{C.TEXT_PRIMARY};"))
        head.addWidget(self._lbl("Riwayat pembayaran les murid",
                                 f"font-size:12px;color:{C.TEXT_FAINT};"))
        v.addLayout(head)

        # ── Summary cards ─────────────────────────────────────────────
        cards_row = QHBoxLayout(); cards_row.setSpacing(16)
        self._card_total   = self._stat_card("TOTAL TRANSAKSI", "0",   f"{C.ACCENT_BG}", f"{C.ACCENT}")
        self._card_nominal = self._stat_card("TOTAL PEMASUKAN",  "Rp0", f"{C.SUCCESS_BG}", f"{C.SUCCESS_HOVER}")
        for c in [self._card_total, self._card_nominal]:
            cards_row.addWidget(c, 1)
        v.addLayout(cards_row)

        # ── Filter row ────────────────────────────────────────────────
        fr = QHBoxLayout(); fr.setSpacing(10)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Cari keterangan atau nama murid…")
        self._search.addAction(svg_icon("search", C.TEXT_FAINT, 15), QLineEdit.LeadingPosition)
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(f"""
            QLineEdit{{border:1.5px solid {C.BORDER};border-radius:8px;
                background:{C.SURFACE_ALT};padding-left:12px;font-size:12px;color:{C.TEXT_PRIMARY};}}
            QLineEdit:focus{{border:1.5px solid {C.ACCENT};background:white;}}
        """)
        self._search.textChanged.connect(self._refresh)

        # Filter Sumber — hanya Les
        self._sumber_combo = QComboBox()
        self._sumber_combo.addItems(["Semua", "Les"])
        self._sumber_combo.setFixedHeight(36); self._sumber_combo.setFixedWidth(120)
        style_combo(self._sumber_combo, radius=8, height=36, font_size=12, border=C.BORDER)
        self._sumber_combo.currentIndexChanged.connect(self._refresh)

        # Filter Bulan
        bulan_list = ["Januari","Februari","Maret","April","Mei","Juni",
                      "Juli","Agustus","September","Oktober","November","Desember"]
        self._bulan_combo = QComboBox()
        self._bulan_combo.addItem("Semua Bulan", 0)
        for i, nm in enumerate(bulan_list, 1):
            self._bulan_combo.addItem(nm, i)
        self._bulan_combo.setCurrentIndex(datetime.now().month)
        self._bulan_combo.setFixedHeight(36)
        style_combo(self._bulan_combo, radius=8, height=36, font_size=12, border=C.BORDER)
        self._bulan_combo.currentIndexChanged.connect(self._refresh)

        # Filter Tahun
        self._tahun_spin = QSpinBox()
        self._tahun_spin.setRange(2000, 2100)
        self._tahun_spin.setValue(datetime.now().year)
        self._tahun_spin.setFixedHeight(36); self._tahun_spin.setFixedWidth(90)
        self._tahun_spin.setStyleSheet(f"""
            QSpinBox{{border:1.5px solid {C.BORDER};border-radius:8px;
                background:white;padding-left:8px;font-size:12px;color:{C.TEXT_PRIMARY};}}
            QSpinBox:focus{{border:1.5px solid {C.ACCENT};}}
        """)
        self._tahun_spin.valueChanged.connect(self._refresh)

        fr.addWidget(self._search, 1)
        fr.addWidget(self._bulan_combo)
        fr.addWidget(self._tahun_spin)
        v.addLayout(fr)

        # ── Tabel ─────────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet("QFrame{background:white;border-radius:14px;border:none;}")
        cv = QVBoxLayout(card); cv.setContentsMargins(0, 0, 0, 0)

        cols = ["NO", "TANGGAL", "NAMA MURID", "LES", "GURU",
                "METODE", "SESI", "BIAYA LES", "TRANSPORT", "TOTAL"]
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setStyleSheet(f"""
            QTableWidget{{border:none;background:white;border-radius:14px;}}
            QHeaderView::section{{background:{C.SURFACE_ALT};padding:12px 10px;border:none;
                border-bottom:2px solid {C.SURFACE_HOVER};color:{C.TEXT_MUTED_STRONG};font-weight:bold;font-size:10px;
                letter-spacing:0.5px;}}
            QTableWidget::item{{padding:14px 10px;border-bottom:1px solid {C.SURFACE_ALT};
                color:{C.TEXT_BODY};font-size:12px;}}
            QTableWidget::item:selected{{background:{C.ACCENT_BG};color:{C.TEXT_PRIMARY};}}
        """)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.Fixed); self._table.setColumnWidth(0, 50)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed); self._table.setColumnWidth(1, 110)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed); self._table.setColumnWidth(3, 130)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed); self._table.setColumnWidth(4, 140)

        cv.addWidget(self._table)

        # Footer info
        self._info_lbl = QLabel("Menampilkan 0 transaksi")
        self._info_lbl.setStyleSheet(
            f"font-size:11px;color:{C.TEXT_FAINT};padding:10px 18px;background:transparent;")
        cv.addWidget(self._info_lbl)
        v.addWidget(card)

        self._refresh()

    def _refresh(self):
        from database import DB

        kw           = self._search.text().lower()
        bulan_filter = self._bulan_combo.currentData()
        tahun_filter = self._tahun_spin.value()

        raw = DB.fetch_all("""
            SELECT
                psm.id,
                psm.tanggal_bayar,
                psm.jumlah_sesi,
                psm.metode,
                psm.biaya_les,
                psm.biaya_transport,
                psm.total_bayar,
                psm.status,
                m.nama  AS nama_murid,
                g.nama  AS nama_guru,
                k.nama  AS nama_kursus
            FROM pembayaran_sesi_murid psm
            JOIN murid  m ON m.id = psm.murid_id
            JOIN kursus k ON k.id = psm.kursus_id
            LEFT JOIN guru g ON g.id = psm.guru_id
            ORDER BY psm.tanggal_bayar DESC, psm.id DESC
        """)

        rows = []
        for r in raw:
            tgl = r["tanggal_bayar"] or ""
            # Filter bulan/tahun — format YYYY-MM-DD
            try:
                parts = tgl.split("-")
                tahun_data = int(parts[0])
                bulan_data = int(parts[1])
                tgl_display = f"{parts[2]}/{parts[1]}/{parts[0]}"
            except Exception:
                tahun_data = bulan_data = 0
                tgl_display = tgl

            if bulan_filter and bulan_data != bulan_filter:
                continue
            if tahun_data != tahun_filter:
                continue

            # Filter keyword
            nama_murid  = r["nama_murid"]  or "-"
            nama_kursus = r["nama_kursus"] or "-"
            nama_guru   = r["nama_guru"]   or "-"
            if kw and kw not in nama_murid.lower() \
                   and kw not in nama_kursus.lower() \
                   and kw not in nama_guru.lower():
                continue

            rows.append({
                "tanggal":    tgl_display,
                "nama_murid": nama_murid,
                "nama_kursus":nama_kursus,
                "nama_guru":  nama_guru,
                "jumlah_sesi":r["jumlah_sesi"] or 0,
                "metode":     r["metode"] or "Offline",
                "biaya_les":  r["biaya_les"] or 0,
                "biaya_tr":   r["biaya_transport"] or 0,
                "total":      r["total_bayar"] or 0,
            })

        # Summary
        self._set_card_val(self._card_total,   str(len(rows)))
        self._set_card_val(self._card_nominal, _fmt_rp(sum(r["total"] for r in rows)))
        self._info_lbl.setText(f"Menampilkan {len(rows)} transaksi")

        # Rebuild table columns to match full data
        self._table.setColumnCount(0)
        cols = ["NO", "TANGGAL", "NAMA MURID", "LES", "GURU",
                "METODE", "SESI", "BIAYA LES", "TRANSPORT", "TOTAL"]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.Fixed); self._table.setColumnWidth(0, 44)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed); self._table.setColumnWidth(1, 100)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed); self._table.setColumnWidth(5, 100)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed); self._table.setColumnWidth(6, 54)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed); self._table.setColumnWidth(7, 110)
        hdr.setSectionResizeMode(8, QHeaderView.Fixed); self._table.setColumnWidth(8, 100)
        hdr.setSectionResizeMode(9, QHeaderView.Fixed); self._table.setColumnWidth(9, 110)

        self._table.setRowCount(0)
        for i, r in enumerate(rows):
            self._table.insertRow(i)
            self._table.setRowHeight(i, 52)

            def _item(text, bold=False, color=f"{C.TEXT_BODY}",
                      align=Qt.AlignVCenter | Qt.AlignLeft):
                it = QTableWidgetItem(str(text))
                if bold: it.setFont(QFont("Segoe UI", 10, QFont.Bold))
                it.setForeground(QColor(color))
                it.setTextAlignment(align)
                return it

            metode_col = {"Home Visit": f"{C.SUCCESS_DARK}", "Online": f"{C.ACCENT_DARKER}",
                          "Offline": "#92400E"}.get(r["metode"], f"{C.TEXT_MUTED}")

            self._table.setItem(i, 0, _item(f"{i+1}", align=Qt.AlignCenter|Qt.AlignVCenter, color=f"{C.TEXT_FAINT}"))
            self._table.setItem(i, 1, _item(r["tanggal"], color=f"{C.TEXT_BODY}"))
            self._table.setItem(i, 2, _item(r["nama_murid"], bold=True, color=f"{C.ACCENT}"))
            self._table.setItem(i, 3, _item(r["nama_kursus"]))
            self._table.setItem(i, 4, _item(r["nama_guru"]))
            self._table.setItem(i, 5, _item(r["metode"], bold=True, color=metode_col))
            self._table.setItem(i, 6, _item(f"{r['jumlah_sesi']}x", align=Qt.AlignCenter|Qt.AlignVCenter))

            bl = QTableWidgetItem(_fmt_rp(r["biaya_les"]))
            bl.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(i, 7, bl)

            tr_val = r["biaya_tr"]
            tr = QTableWidgetItem(_fmt_rp(tr_val) if tr_val else "–")
            tr.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tr.setForeground(QColor(f"{C.SUCCESS_DARK}" if tr_val else f"{C.BORDER_STRONG}"))
            if tr_val: tr.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self._table.setItem(i, 8, tr)

            tot = QTableWidgetItem(_fmt_rp(r["total"]))
            tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot.setFont(QFont("Segoe UI", 10, QFont.Bold))
            tot.setForeground(QColor(f"{C.SUCCESS_HOVER}"))
            self._table.setItem(i, 9, tot)

    def _tambah_pembayaran(self):
        dlg = TambahPembayaranMuridDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._refresh()
            if hasattr(self, "_on_stat_changed") and self._on_stat_changed:
                self._on_stat_changed()

    def _stat_card(self, title, value, bg, accent):
        f = QFrame()
        f.setStyleSheet(f"QFrame{{background:{bg};border-radius:12px;border:none;}}"
                        f"QLabel{{background:transparent;border:none;}}")
        fl = QVBoxLayout(f); fl.setContentsMargins(18, 14, 18, 14); fl.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet(f"font-size:10px;font-weight:bold;color:{accent};letter-spacing:0.5px;")
        v_lbl = QLabel(value)
        v_lbl.setStyleSheet(f"font-size:22px;font-weight:bold;color:{C.TEXT_PRIMARY};")
        v_lbl.setObjectName("val")
        fl.addWidget(t); fl.addWidget(v_lbl)
        return f

    def _set_card_val(self, card, text):
        lbl = card.findChild(QLabel, "val")
        if lbl: lbl.setText(text)

    def _lbl(self, text, style):
        l = QLabel(text); l.setStyleSheet(style); return l


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    # Gunakan font native macOS agar tidak trigger font-alias scan yang lambat
    for f in [".AppleSystemUIFont", "Helvetica Neue", "Arial"]:
        if QFont(f).exactMatch():
            app.setFont(QFont(f, 10))
            break
    else:
        app.setFont(QFont("Arial", 10))
    w = PembayaranMainWidget()
    w.setWindowTitle("Pembayaran – Melody Violin School")
    w.resize(1150, 780)
    w.show()
    sys.exit(app.exec_())