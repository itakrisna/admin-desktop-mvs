"""
Absensi.py
"""

import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QLineEdit,
    QStackedWidget, QDialog, QProgressBar,
    QDateEdit, QGraphicsDropShadowEffect, QButtonGroup, QTextEdit
)
from PyQt5.QtCore import Qt, QSize, QDate
from PyQt5.QtGui import QFont, QColor
from toast_notification import show_toast, confirm_action
from theme import C, svg_icon, svg_pixmap, style_combo, action_button_style, primary_button_style

# ── Helper bersama (dipakai juga oleh DashboardAdmin.py untuk panel ringkasan) ────

_BADGE_CFG = {
    "Terlaksana": (f"{C.SUCCESS_BG_STRONG}", f"{C.SUCCESS_DARK}", "Hadir"),
    "Selesai":    (f"{C.SUCCESS_BG_STRONG}", f"{C.SUCCESS_DARK}", "Hadir"),
    "Batal":      (f"{C.DANGER_BG}", f"{C.DANGER_DARK}", "Tidak Hadir"),
    "Reschedule": (f"{C.WARNING_BG}", f"{C.WARNING_DARK}", "Reschedule"),
    "Pending":    (f"{C.ACCENT_BG}", f"{C.ACCENT_DARKER}", "Belum Absen"),
}


def _STATUS_BADGE(status: str):
    """Kembalikan (bg, fg, label) untuk badge status kehadiran sesi."""
    return _BADGE_CFG.get(status, (f"{C.SURFACE_HOVER}", f"{C.TEXT_MUTED}", status or "-"))


def _parse_tanggal(tanggal_str: str):
    """'DD-MM-YYYY' → datetime, atau None kalau tidak valid."""
    if not tanggal_str:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(tanggal_str, fmt)
        except ValueError:
            continue
    return None


def _sesi_sort_key(sesi_row):
    dt = _parse_tanggal(sesi_row["tanggal"]) or datetime.max
    return (dt, sesi_row["jam_mulai"] or "")


def _load_jadwal_tanggal(tanggal_str: str) -> list:
    """Dipakai oleh DashboardAdmin.py — semua sesi pada satu tanggal,
    dikelompokkan per murid (urutan berdasarkan jam paling awal)."""
    try:
        from database import DB
    except ImportError:
        return []

    rows = DB.fetch_all("""
        SELECT js.id, js.pendaftaran_id, js.guru_id,
               m.nama AS murid, k.nama AS les,
               js.no_sesi AS no, js.tanggal,
               COALESCE(g.nama, '–') AS guru,
               js.jam_mulai, js.jam_selesai,
               js.metode, js.status
        FROM jadwal_sesi js
        JOIN pendaftaran_kursus pk ON pk.id = js.pendaftaran_id
        JOIN murid  m ON m.id  = pk.murid_id
        JOIN kursus k ON k.id  = pk.kursus_id
        LEFT JOIN guru g ON g.id = js.guru_id
        WHERE js.tanggal = ?
        ORDER BY
            (SELECT MIN(js2.jam_mulai) FROM jadwal_sesi js2
             JOIN pendaftaran_kursus pk2 ON pk2.id = js2.pendaftaran_id
             WHERE js2.tanggal = ? AND pk2.murid_id = pk.murid_id),
            m.nama, js.no_sesi, js.jam_mulai
    """, (tanggal_str, tanggal_str))

    result = []
    for r in rows:
        jam_mulai   = r["jam_mulai"] or ""
        jam_selesai = r["jam_selesai"] or ""
        jam = f"{jam_mulai} – {jam_selesai}" if jam_selesai else jam_mulai
        result.append({
            "id": r["id"], "pendaftaran_id": r["pendaftaran_id"],
            "guru_id": r["guru_id"], "murid": r["murid"], "les": r["les"],
            "no": r["no"], "tanggal": r["tanggal"], "guru": r["guru"],
            "jam_mulai": jam_mulai, "jam_selesai": jam_selesai, "jam": jam,
            "metode": r["metode"] or "Offline", "status": r["status"] or "Pending",
        })
    return result


#  format tiap entri: (bg, border, teks, nama_icon, label) — nama_icon merujuk ke _ICON_SVGS di theme.py
_STATUS_ABSEN_BADGE = {
    "Terlaksana": (f"{C.SUCCESS_BG}", "#BBF7D0", f"{C.SUCCESS_HOVER}", "check", "TERLAKSANA"),
    "Batal":      (f"{C.DANGER_BG}", "#FECACA", f"{C.DANGER_DARK}", "x", "TIDAK HADIR"),
    "Reschedule": (f"{C.WARNING_BG}", "#FED7AA", f"{C.WARNING_DARK}", "calendar-check", "RESCHEDULE"),
}
_STATUS_ABSEN_DEFAULT = ("#EEF2FF", "#E0E7FF", "#6366F1", "clock", "BELUM ABSEN")


def _badge_widget(icon_name, text, bg, border, fg, icon_size=10):
    """Badge kecil ikon+teks (mis. status SUDAH MASUK / TIDAK HADIR /
    BELUM ABSEN, atau tag H-1 di kartu Reminder Besok) — menggantikan
    badge lama yang menaruh karakter emoji (✓ ✕ 🕐 🔔) di depan teks,
    supaya tampilannya ikon vektor rapi & konsisten dengan gaya ikon
    sidebar, bukan bergantung pada font emoji bawaan sistem operasi.
    Ukuran dibuat ringkas/proporsional (padding & font kecil) supaya
    tidak terlihat kebesaran dibanding elemen tabel/kartu di sekitarnya."""
    badge = QFrame()
    badge.setStyleSheet(
        f"QFrame {{ background:{bg}; border:1px solid {border}; border-radius:11px; }}"
    )
    lay = QHBoxLayout(badge)
    lay.setContentsMargins(8, 2, 9, 2)
    lay.setSpacing(4)
    icon_lbl = QLabel()
    icon_lbl.setPixmap(svg_pixmap(icon_name, fg, icon_size))
    icon_lbl.setStyleSheet("background:transparent;border:none;")
    txt_lbl = QLabel(text)
    txt_lbl.setStyleSheet(f"color:{fg};font-size:9px;font-weight:600;background:transparent;border:none;")
    lay.addWidget(icon_lbl)
    lay.addWidget(txt_lbl)
    return badge


def render_absensi_card_list(sesi_list, layout, refresh_callback=None, parent_widget=None):
    """Render daftar sesi (panel "Absensi Hari Ini" di Dashboard) sebagai
    KARTU terpisah (background putih, border, bayangan halus) dengan tombol
    Hadir & Reschedule. Dipakai oleh DashboardAdmin.py.

    ── Perbaikan desain ────────────────────────────────────────────────
    - Baris flat (hanya dipisah garis tipis) diganti kartu sungguhan dengan
      jarak antar-kartu, supaya tiap sesi lebih mudah dipindai satu-satu.
    - Nama murid sekarang elemen paling menonjol (bukan jam), karena itu
      informasi utama yang dicari admin sekilas.
    - Jam dipindah ke badge kecil bergaya monospace di pojok kiri atas,
      supaya tidak bersaing dengan nama murid.
    - Badge status diberi border tipis senada agar kontur lebih jelas.
    - Tombol RESCHEDULE benar-benar dinonaktifkan (bukan cuma warna pudar)
      saat sesi sudah tercatat Hadir, lengkap dengan tooltip penjelasan —
      sebelumnya tombol tetap bisa diklik meski terlihat "mati".
    """
    from database import DB

    total = len(sesi_list)
    for idx, sesi in enumerate(sesi_list):
        status = sesi["status"]
        # Sesi yang sudah punya status final (Terlaksana/Batal/Reschedule)
        # dianggap "sudah diedit" -> kartu dikunci: warna dipudarkan abu-abu
        # dan ketiga tombol aksi dinonaktifkan supaya tidak bisa diedit lagi.
        is_locked = status in _STATUS_ABSEN_BADGE

        card = QFrame()
        card.setObjectName("sesiCard")
        if is_locked:
            card.setStyleSheet(f"""
                QFrame#sesiCard {{
                    background-color:{C.SURFACE_ALT};
                    border:1px solid {C.BORDER};
                    border-radius:14px;
                }}
            """)
        else:
            card.setStyleSheet(f"""
                QFrame#sesiCard {{
                    background-color:{C.SURFACE};
                    border:1px solid {C.BORDER};
                    border-radius:14px;
                }}
            """)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(15, 23, 42, 22))
        card.setGraphicsEffect(shadow)

        cv = QVBoxLayout(card)
        cv.setContentsMargins(18, 16, 18, 16)
        cv.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        jl = QLabel(sesi["jam"])
        jl.setStyleSheet(
            f"background:{C.SURFACE_ALT};color:{C.ACCENT_DARK};"
            "font-family:'Consolas','Courier New',monospace;font-weight:bold;"
            "font-size:12px;padding:5px 10px;border-radius:8px;border:none;"
        )
        top_row.addWidget(jl)
        top_row.addStretch()

        bg, border_c, fg, icon_name, label = _STATUS_ABSEN_BADGE.get(status, _STATUS_ABSEN_DEFAULT)
        st_badge = _badge_widget(icon_name, label, bg, border_c, fg)
        top_row.addWidget(st_badge)
        cv.addLayout(top_row)

        nl = QLabel(sesi["murid"])
        nl_color = C.TEXT_MUTED if is_locked else C.TEXT_PRIMARY
        nl.setStyleSheet(f"font-weight:700;color:{nl_color};font-size:16px;background:transparent;border:none;")
        cv.addWidget(nl)

        dl_row = QHBoxLayout()
        dl_row.setSpacing(6)
        dl_icon = QLabel()
        dl_icon.setPixmap(svg_pixmap("music", C.TEXT_MUTED, 12))
        dl_icon.setStyleSheet("background:transparent;border:none;")
        dl = QLabel(f"{sesi['les']}  ·  {sesi['guru']}")
        dl.setStyleSheet(f"color:{C.TEXT_MUTED};font-size:12px;background:transparent;border:none;")
        dl_row.addWidget(dl_icon)
        dl_row.addWidget(dl)
        dl_row.addStretch()
        cv.addLayout(dl_row)

        cv.addSpacing(2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # 3 tombol aksi (HADIR/BATAL/RESCHEDULE) aktif hanya selama sesi
        # belum diedit. Begitu status sesi diset (Terlaksana/Batal/
        # Reschedule) kartu terkunci: tombol dinonaktifkan & warnanya
        # dipudarkan abu-abu supaya jelas sesi ini tidak bisa diedit lagi.
        _locked_qss = f"""
            QPushButton:disabled {{ background:{C.SURFACE_HOVER}; color:{C.TEXT_FAINT};
                          border:1.5px solid {C.BORDER}; }}
        """

        btn_hadir = QPushButton("HADIR")
        btn_hadir.setFixedHeight(38)
        btn_hadir.setCursor(Qt.ArrowCursor if is_locked else Qt.PointingHandCursor)
        btn_hadir.setIcon(svg_icon("check", f"{C.TEXT_FAINT}" if is_locked else f"{C.SUCCESS_DARK}", 14))
        btn_hadir.setIconSize(QSize(14, 14))
        btn_hadir.setToolTip("Sesi sudah diedit dan terkunci" if is_locked else "Tandai sesi ini sebagai Terlaksana (hadir)")
        btn_hadir.setStyleSheet(f"""
            QPushButton {{ background:white; color:{C.SUCCESS_DARK}; border:1.5px solid #86EFAC;
                          border-radius:8px; font-size:11px; font-weight:bold; }}
            QPushButton:hover {{ background-color:{C.SUCCESS_BG}; }}
        """ + _locked_qss)
        btn_hadir.setEnabled(not is_locked)

        btn_batal = QPushButton("BATAL")
        btn_batal.setFixedHeight(38)
        btn_batal.setCursor(Qt.ArrowCursor if is_locked else Qt.PointingHandCursor)
        btn_batal.setIcon(svg_icon("x", f"{C.TEXT_FAINT}" if is_locked else f"{C.DANGER_DARK}", 14))
        btn_batal.setIconSize(QSize(14, 14))
        btn_batal.setToolTip("Sesi sudah diedit dan terkunci" if is_locked else "Tandai sesi ini sebagai Batal (tidak hadir)")
        btn_batal.setStyleSheet(f"""
            QPushButton {{ background:white; color:{C.DANGER_DARK}; border:1.5px solid {C.DANGER_BORDER};
                          border-radius:8px; font-size:11px; font-weight:bold; }}
            QPushButton:hover {{ background-color:{C.DANGER_BG}; }}
        """ + _locked_qss)
        btn_batal.setEnabled(not is_locked)

        btn_reschedule = QPushButton("RESCHEDULE")
        btn_reschedule.setFixedHeight(38)
        btn_reschedule.setCursor(Qt.ArrowCursor if is_locked else Qt.PointingHandCursor)
        btn_reschedule.setIcon(svg_icon("calendar-check", f"{C.TEXT_FAINT}" if is_locked else "#D97706", 14))
        btn_reschedule.setIconSize(QSize(14, 14))
        btn_reschedule.setToolTip("Sesi sudah diedit dan terkunci" if is_locked else "Ubah tanggal/jam sesi ini")
        btn_reschedule.setStyleSheet(f"""
            QPushButton {{ background:white; color:#D97706; border:1.5px solid #FCD34D;
                          border-radius:8px; font-size:11px; font-weight:bold; }}
            QPushButton:hover {{ background-color:#FFFBEB; }}
        """ + _locked_qss)
        btn_reschedule.setEnabled(not is_locked)

        def _tandai_hadir(_, sid=sesi["id"], s=sesi):
            jawab = confirm_action(
                parent_widget, "Tandai Hadir",
                f"Tandai sesi {s['murid']} ({s['jam']}) sebagai Hadir/Terlaksana?",
                yes_text="Ya, Hadir", no_text="Batal"
            )
            if jawab:
                DB.set_status_sesi(sid, "Terlaksana")
                show_toast(parent_widget, "Berhasil", "Sesi ditandai Hadir.", "success")
                if refresh_callback:
                    refresh_callback()

        def _tandai_batal(_, sid=sesi["id"], s=sesi):
            jawab = confirm_action(
                parent_widget, "Tandai Tidak Hadir",
                f"Tandai sesi {s['murid']} ({s['jam']}) sebagai Batal/Tidak Hadir? "
                f"Sistem akan otomatis membuat sesi pengganti sesuai pola jadwal "
                f"rutin kalau kuota paket masih tersedia.",
                yes_text="Ya, Batal", no_text="Batal"
            )
            if jawab:
                hasil = DB.batalkan_sesi(sid)
                show_toast(parent_widget, "Berhasil" if hasil["ok"] else "Gagal",
                           hasil["pesan"], "success" if hasil["ok"] else "warning")
                if refresh_callback:
                    refresh_callback()

        def _reschedule(_, s=sesi):
            dlg = RescheduleSesiDialog(parent_widget, sesi_row=s, on_saved=refresh_callback)
            dlg.exec_()

        btn_hadir.clicked.connect(_tandai_hadir)
        btn_batal.clicked.connect(_tandai_batal)
        btn_reschedule.clicked.connect(_reschedule)

        btn_row.addWidget(btn_hadir, 1)
        btn_row.addWidget(btn_batal, 1)
        btn_row.addWidget(btn_reschedule, 1)
        cv.addLayout(btn_row)

        layout.addWidget(card)
        if idx < total - 1:
            layout.addSpacing(10)


# ── DIALOG — RESCHEDULE SESI (dipakai tombol "Reschedule" di Reminder Besok) ────
class RescheduleSesiDialog(QDialog):
    """
    Ubah tanggal & jam satu sesi les. sesi_row wajib punya key:
    id, tanggal ('DD-MM-YYYY'), jam_mulai/jam_selesai ('HH:MM'), murid.
    on_saved dipanggil setelah berhasil disimpan ke database.
    """
    def __init__(self, parent=None, sesi_row=None, on_saved=None):
        super().__init__(parent)
        self._sesi = sesi_row
        self._on_saved = on_saved
        # Durasi per sesi mengikuti aturan yang sama dengan form "Tambah
        # Les Baru" (DURASI_PER_METODE di DataMurid.py): Offline/Home
        # Visit 45 menit, Online 30 menit — supaya Jam Selesai saat
        # reschedule otomatis konsisten, tidak perlu diketik manual.
        from DataMurid import DURASI_PER_METODE
        self._durasi_menit = DURASI_PER_METODE.get(self._sesi.get("metode", "Offline") if self._sesi else "Offline", 45)
        self.setWindowTitle("Reschedule Sesi")
        self.setFixedWidth(360)
        self.setStyleSheet(f"QDialog {{ background:{C.SURFACE_ALT}; }}")
        self._build_ui()

    def _field_label(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:11px;font-weight:bold;color:{C.TEXT_MUTED};")
        return l

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(10)

        title = QLabel("Reschedule Sesi")
        title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C.TEXT_PRIMARY};")
        root.addWidget(title)
        sub = QLabel(f"{self._sesi['murid']} — {self._sesi['les']} / {self._sesi['guru']}")
        sub.setStyleSheet(f"font-size:10px;color:{C.TEXT_MUTED};")
        sub.setWordWrap(True)
        root.addWidget(sub)
        root.addSpacing(6)

        _input_qss = f"""
            QLineEdit, QDateEdit {{
                border:1px solid {C.BORDER}; border-radius:8px; padding:0 10px;
                font-size:12px; background:{C.SURFACE}; color:{C.TEXT_PRIMARY};
            }}
            QLineEdit:focus, QDateEdit:focus {{ border:1.5px solid {C.ACCENT}; }}
        """

        root.addWidget(self._field_label("Tanggal Baru"))
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd-MM-yyyy")
        d, m, y = (self._sesi["tanggal"] or "").split("-") if self._sesi.get("tanggal") else (None, None, None)
        try:
            self.date_input.setDate(QDate(int(y), int(m), int(d)))
        except Exception:
            self.date_input.setDate(QDate.currentDate())
        self.date_input.setFixedHeight(38)
        self.date_input.setStyleSheet(_input_qss)
        root.addWidget(self.date_input)

        jam_row = QHBoxLayout()
        jam_row.setSpacing(10)
        col_mulai = QVBoxLayout()
        col_mulai.addWidget(self._field_label("Jam Mulai"))
        self.input_mulai = QLineEdit(self._sesi.get("jam_mulai", "") or "")
        self.input_mulai.setPlaceholderText("cth. 09:00")
        self.input_mulai.setFixedHeight(38)
        self.input_mulai.setStyleSheet(_input_qss)
        col_mulai.addWidget(self.input_mulai)
        col_selesai = QVBoxLayout()
        col_selesai.addWidget(self._field_label("Jam Selesai"))
        self.input_selesai = QLineEdit(self._sesi.get("jam_selesai", "") or "")
        self.input_selesai.setPlaceholderText("cth. 09:45")
        self.input_selesai.setFixedHeight(38)
        self.input_selesai.setReadOnly(True)
        self.input_selesai.setToolTip(
            f"Otomatis: Jam Mulai + durasi {self._durasi_menit} menit "
            f"({self._sesi.get('metode', 'Offline')}), sesuai pengaturan di Tambah Les Baru."
        )
        self.input_selesai.setStyleSheet(_input_qss + f"""
            QLineEdit {{ background:{C.SURFACE_ALT}; color:{C.TEXT_MUTED}; }}
        """)
        col_selesai.addWidget(self.input_selesai)
        jam_row.addLayout(col_mulai)
        jam_row.addLayout(col_selesai)
        root.addLayout(jam_row)

        durasi_note = QLabel(f"Durasi {self._durasi_menit} menit/sesi ({self._sesi.get('metode', 'Offline')}) — Jam Selesai otomatis mengikuti Jam Mulai.")
        durasi_note.setStyleSheet(f"font-size:10px;color:{C.TEXT_MUTED};font-style:italic;")
        durasi_note.setWordWrap(True)
        root.addWidget(durasi_note)

        self.input_mulai.textChanged.connect(self._update_jam_selesai)
        self._update_jam_selesai()

        root.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_kembali = QPushButton(" Kembali")
        btn_kembali.setIcon(svg_icon("arrow-left", C.TEXT_SECONDARY, 13))
        btn_kembali.setFixedHeight(40)
        btn_kembali.setCursor(Qt.PointingHandCursor)
        btn_kembali.setStyleSheet(f"""
            QPushButton {{ background:white; color:{C.TEXT_SECONDARY}; border:1px solid {C.BORDER};
                          border-radius:8px; font-size:12px; font-weight:600; }}
            QPushButton:hover {{ background-color:{C.SURFACE_ALT}; }}
        """)
        btn_kembali.clicked.connect(self.reject)
        btn_simpan = QPushButton("Simpan")
        btn_simpan.setFixedHeight(40)
        btn_simpan.setCursor(Qt.PointingHandCursor)
        btn_simpan.setStyleSheet(f"""
            QPushButton {{ background-color:{C.ACCENT_DARK}; color:white; border:none;
                          border-radius:8px; font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background-color:{C.ACCENT_DARKER}; }}
        """)
        btn_simpan.clicked.connect(self._simpan)
        btn_row.addWidget(btn_kembali, 1)
        btn_row.addWidget(btn_simpan, 1)
        root.addLayout(btn_row)

    def _update_jam_selesai(self):
        """Hitung ulang Jam Selesai = Jam Mulai + durasi per metode
        (sama seperti aturan di Tambah Les Baru), setiap kali Jam Mulai
        diketik ulang. Kalau Jam Mulai belum berformat HH:MM yang valid,
        Jam Selesai dikosongkan dulu."""
        teks = self.input_mulai.text().strip()
        try:
            mulai = datetime.strptime(teks, "%H:%M")
        except ValueError:
            self.input_selesai.setText("")
            return
        selesai = mulai + timedelta(minutes=self._durasi_menit)
        self.input_selesai.setText(selesai.strftime("%H:%M"))

    def _simpan(self):
        from database import DB

        jam_mulai = self.input_mulai.text().strip()
        jam_selesai = self.input_selesai.text().strip()
        if not jam_mulai or not jam_selesai:
            show_toast(self, "Perhatian", "Jam Mulai wajib diisi format HH:MM (mis. 09:00).", "warning")
            return

        tanggal = self.date_input.date().toString("dd-MM-yyyy")
        # Sesi asal ditandai 'Reschedule', lalu dibuat sesi baru (no_sesi sama); cek kuota & bentrok jadwal dulu
        hasil = DB.reschedule_khusus_sesi(self._sesi["id"], tanggal, jam_mulai, jam_selesai)
        if not hasil["ok"]:
            show_toast(self, "Gagal", hasil["pesan"], "warning")
            return  # dialog tetap terbuka supaya admin bisa pilih tanggal/jam lain

        show_toast(self, "Berhasil", hasil["pesan"], "success")
        if self._on_saved:
            self._on_saved()
        self.accept()


# ── DIALOG — EDIT STATUS KEHADIRAN (gaya sama dengan RescheduleSesiDialog) ──
class EditStatusSesiDialog(QDialog):
    """
    Ubah status kehadiran (Terlaksana/Batal) satu sesi. sesi_row wajib
    punya key: id, murid, tanggal, jam, status. on_saved dipanggil setelah
    berhasil disimpan ke database.
    """
    def __init__(self, parent=None, sesi_row=None, on_saved=None):
        super().__init__(parent)
        self._sesi = sesi_row
        self._on_saved = on_saved
        self.setWindowTitle("Ubah Status Kehadiran")
        self.setFixedWidth(360)
        self.setStyleSheet(f"QDialog {{ background:{C.SURFACE_ALT}; }}")
        self._build_ui()

    def _field_label(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:11px;font-weight:bold;color:{C.TEXT_MUTED};")
        return l

    def _style_opt(self, btn, active, border_c, bg_c, fg_c):
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{ background:{bg_c}; color:{fg_c}; border:1.5px solid {border_c};
                              border-radius:8px; font-size:11px; font-weight:bold; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{ background:{C.SURFACE}; color:{C.TEXT_MUTED}; border:1.5px solid {C.BORDER};
                              border-radius:8px; font-size:11px; font-weight:600; }}
                QPushButton:hover {{ background-color:{C.SURFACE_ALT}; }}
            """)

    def _refresh_opt_styles(self):
        self._style_opt(self.btn_opt_terlaksana, self.btn_opt_terlaksana.isChecked(),
                         "#86EFAC", f"{C.SUCCESS_BG}", f"{C.SUCCESS_DARK}")
        self._style_opt(self.btn_opt_batal, self.btn_opt_batal.isChecked(),
                         f"{C.DANGER_BORDER}", f"{C.DANGER_BG}", f"{C.DANGER_DARK}")
        self._style_opt(self.btn_opt_belum, self.btn_opt_belum.isChecked(),
                         "#C7D2FE", "#EEF2FF", "#4338CA")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(10)

        title = QLabel("Ubah Status Kehadiran")
        title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C.TEXT_PRIMARY};")
        root.addWidget(title)
        sub = QLabel(f"{self._sesi['murid']} — {self._sesi['tanggal']}, {self._sesi['jam']}")
        sub.setStyleSheet(f"font-size:10px;color:{C.TEXT_MUTED};")
        sub.setWordWrap(True)
        root.addWidget(sub)
        root.addSpacing(6)

        root.addWidget(self._field_label("Status Kehadiran"))

        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)

        self.btn_opt_terlaksana = QPushButton()
        self.btn_opt_terlaksana.setIcon(svg_icon("check", f"{C.SUCCESS_DARK}", 13))
        self.btn_opt_terlaksana.setText("  Terlaksana")
        self.btn_opt_terlaksana.setCheckable(True)
        self.btn_opt_terlaksana.setFixedHeight(38)
        self.btn_opt_terlaksana.setCursor(Qt.PointingHandCursor)

        # "Batal" selalu memicu batalkan_sesi (tandai Batal + buat sesi pengganti otomatis)
        self.btn_opt_batal = QPushButton()
        self.btn_opt_batal.setIcon(svg_icon("x", f"{C.DANGER_DARK}", 13))
        self.btn_opt_batal.setText("  Batal")
        self.btn_opt_batal.setCheckable(True)
        self.btn_opt_batal.setFixedHeight(38)
        self.btn_opt_batal.setCursor(Qt.PointingHandCursor)

        # "Belum Absen": kalau status sekarang Batal, ini undo batal (sesi pengganti ikut dihapus)
        self.btn_opt_belum = QPushButton()
        self.btn_opt_belum.setIcon(svg_icon("clock", "#4338CA", 13))
        self.btn_opt_belum.setText("  Belum Absen")
        self.btn_opt_belum.setCheckable(True)
        self.btn_opt_belum.setFixedHeight(38)
        self.btn_opt_belum.setCursor(Qt.PointingHandCursor)

        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.btn_opt_terlaksana)
        group.addButton(self.btn_opt_batal)
        group.addButton(self.btn_opt_belum)
        self._opt_group = group  # simpan referensi supaya tidak di-GC

        status_awal = (self._sesi.get("status") or "").strip()
        self.btn_opt_terlaksana.setChecked(status_awal == "Terlaksana")
        self.btn_opt_batal.setChecked(status_awal == "Batal")
        self.btn_opt_belum.setChecked(status_awal not in ("Terlaksana", "Batal"))
        self._refresh_opt_styles()
        self.btn_opt_terlaksana.clicked.connect(self._refresh_opt_styles)
        self.btn_opt_batal.clicked.connect(self._refresh_opt_styles)
        self.btn_opt_belum.clicked.connect(self._refresh_opt_styles)

        opt_row.addWidget(self.btn_opt_terlaksana)
        opt_row.addWidget(self.btn_opt_batal)
        opt_row.addWidget(self.btn_opt_belum)
        root.addLayout(opt_row)

        if status_awal == "Batal":
            hint = QLabel(
                "Memilih \"Belum Absen\" akan membatalkan pembatalan (Undo) — "
                "sesi pengganti otomatis yang sudah dibuat akan ikut dihapus.")
            hint.setWordWrap(True)
            hint.setStyleSheet(f"font-size:9px;color:{C.TEXT_MUTED};font-style:italic;")
            root.addWidget(hint)

        root.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_batal_dialog = QPushButton("Batal")
        btn_batal_dialog.setFixedHeight(40)
        btn_batal_dialog.setCursor(Qt.PointingHandCursor)
        btn_batal_dialog.setStyleSheet(f"""
            QPushButton {{ background:{C.SURFACE}; color:{C.TEXT_MUTED}; border:1px solid {C.BORDER};
                          border-radius:8px; font-size:12px; font-weight:600; }}
            QPushButton:hover {{ background-color:{C.SURFACE_ALT}; }}
        """)
        btn_batal_dialog.clicked.connect(self.reject)
        btn_simpan = QPushButton("Simpan")
        btn_simpan.setFixedHeight(40)
        btn_simpan.setCursor(Qt.PointingHandCursor)
        btn_simpan.setStyleSheet(f"""
            QPushButton {{ background-color:{C.ACCENT_DARK}; color:white; border:none;
                          border-radius:8px; font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background-color:{C.ACCENT_DARKER}; }}
        """)
        btn_simpan.clicked.connect(self._simpan)
        btn_row.addWidget(btn_batal_dialog, 1)
        btn_row.addWidget(btn_simpan, 1)
        root.addLayout(btn_row)

    def _simpan(self):
        from database import DB

        status_awal = (self._sesi.get("status") or "").strip()
        sesi_id = self._sesi["id"]

        if self.btn_opt_terlaksana.isChecked():
            DB.set_status_sesi(sesi_id, "Terlaksana")

        elif self.btn_opt_batal.isChecked():
            if status_awal == "Batal":
                # sudah Batal & tetap dipilih Batal -> tidak ada perubahan
                self.accept()
                return
            hasil = DB.batalkan_sesi(sesi_id)
            show_toast(self, "Berhasil" if hasil["ok"] else "Gagal",
                       hasil["pesan"], "success" if hasil["ok"] else "warning")
            if not hasil["ok"]:
                return  # dialog tetap terbuka

        elif self.btn_opt_belum.isChecked():
            if status_awal == "Batal":
                # UNDO BATAL — kembalikan status + hapus sesi pengganti
                # otomatis (kalau sudah sempat dibuat) supaya kuota tidak dobel
                hasil = DB.undo_batal_sesi(sesi_id)
                show_toast(self, "Berhasil" if hasil["ok"] else "Gagal",
                           hasil["pesan"], "success" if hasil["ok"] else "warning")
                if not hasil["ok"]:
                    return
            else:
                DB.set_status_sesi(sesi_id, "Pending")
        else:
            show_toast(self, "Perhatian", "Pilih status kehadiran terlebih dahulu.", "warning")
            return

        if self._on_saved:
            self._on_saved()
        self.accept()


# ── DIALOG — SALIN PENGINGAT SESI (pratinjau dulu, baru disalin lewat tombol) ──
class SalinPengingatDialog(QDialog):
    """
    Pratinjau & salin teks pengingat WA satu sesi. sesi_row wajib punya
    key: murid, tanggal, jam. `teks` adalah isi pesan yang sudah disusun
    (lihat _teks_pengingat_sesi).
    """
    def __init__(self, parent=None, sesi_row=None, teks=""):
        super().__init__(parent)
        self._sesi = sesi_row
        self._teks = teks
        self.setWindowTitle("Salin Pengingat Sesi")
        self.setFixedWidth(400)
        self.setStyleSheet(f"QDialog {{ background:{C.SURFACE_ALT}; }}")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(10)

        title = QLabel("Salin Pengingat Sesi")
        title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C.TEXT_PRIMARY};background:transparent;border:none;")
        root.addWidget(title)
        sub = QLabel(f"{self._sesi['murid']} — {self._sesi['tanggal']}, {self._sesi['jam']}")
        sub.setStyleSheet(f"font-size:10px;color:{C.TEXT_MUTED};background:transparent;border:none;")
        sub.setWordWrap(True)
        root.addWidget(sub)
        root.addSpacing(6)

        # Kotak pratinjau bisa diedit; teks yang disalin adalah versi terbaru di kotak ini
        self.preview = QTextEdit()
        self.preview.setPlainText(self._teks)
        self.preview.setFixedHeight(230)
        self.preview.setStyleSheet(f"""
            QTextEdit {{ border:1px solid {C.BORDER}; border-radius:8px; padding:10px;
                        font-size:11px; background:transparent; color:{C.TEXT_PRIMARY}; }}
            QTextEdit:focus {{ border:1.5px solid {C.ACCENT}; }}
        """)
        root.addWidget(self.preview)

        edit_hint = QLabel("Teks di atas bisa diedit sebelum disalin.")
        edit_hint.setStyleSheet(f"font-size:9px;color:{C.TEXT_MUTED};font-style:italic;background:transparent;border:none;")
        root.addWidget(edit_hint)

        root.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_tutup = QPushButton("Tutup")
        btn_tutup.setFixedHeight(40)
        btn_tutup.setCursor(Qt.PointingHandCursor)
        btn_tutup.setStyleSheet(f"""
            QPushButton {{ background:{C.SURFACE}; color:{C.TEXT_MUTED}; border:1px solid {C.BORDER};
                          border-radius:8px; font-size:12px; font-weight:600; }}
            QPushButton:hover {{ background-color:{C.SURFACE_ALT}; }}
        """)
        btn_tutup.clicked.connect(self.reject)
        btn_salin = QPushButton("  Salin ke Clipboard")
        btn_salin.setIcon(svg_icon("copy", "white", 14))
        btn_salin.setFixedHeight(40)
        btn_salin.setCursor(Qt.PointingHandCursor)
        btn_salin.setStyleSheet(f"""
            QPushButton {{ background-color:{C.ACCENT_DARK}; color:white; border:none;
                          border-radius:8px; font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background-color:{C.ACCENT_DARKER}; }}
        """)
        btn_salin.clicked.connect(self._salin)
        btn_row.addWidget(btn_tutup, 1)
        btn_row.addWidget(btn_salin, 1)
        root.addLayout(btn_row)

    def _salin(self):
        QApplication.clipboard().setText(self.preview.toPlainText())
        show_toast(self, "Disalin", "Teks pengingat disalin ke clipboard.", "success")
        self.accept()


def _teks_pengingat_sesi(nama: str, kursus: str, guru: str, tanggal: str,
                          jam: str, metode: str, is_last: bool = False) -> str:
    """Susun teks pengingat WA terstruktur untuk satu sesi — dipakai tombol
    Salin Pengingat baik di panel "Reminder Besok" (Dashboard Admin) maupun
    kolom AKSI dialog Detail Absensi (Absensi Murid).

    `is_last=True` menambahkan blok "Tambahan khusus sesi terakhir" di
    bawah teks utama, sebagai pengingat bagi orang tua murid untuk
    memperpanjang paket les."""
    teks = (
        f"Selamat siang {nama}. Kami ingin mengingatkan bahwa besok terdapat "
        f"jadwal les {kursus}.\n\n"
        f"Guru       : {guru}\n"
        f"Siswa      : {nama}\n"
        f"Tanggal    : {tanggal}\n"
        f"Jam        : {jam}\n"
        f"Metode     : {metode}\n\n"
        f"Mohon hadir tepat waktu.\n\n"
        f"Terima kasih."
    )
    if is_last:
        teks += (
            f"\n\n⭐ Pertemuan besok merupakan sesi terakhir dari paket les {nama}. "
            f"Untuk melanjutkan les pada paket berikutnya, silakan menghubungi "
            f"admin untuk perpanjangan paket."
        )
    return teks


def _teks_pengingat(sesi: dict) -> str:
    """Wrapper lama (dipakai render_reminder_besok_card_list) — susun teks
    pengingat WA dari dict sesi hasil _load_jadwal_tanggal."""
    jam = sesi.get("jam_mulai", "") or ""
    if sesi.get("jam_selesai"):
        jam += f" – {sesi['jam_selesai']}"
    return _teks_pengingat_sesi(
        nama=sesi.get("murid", "-"), kursus=sesi.get("les", "-"),
        guru=sesi.get("guru", "-"), tanggal=sesi.get("tanggal", "-"),
        jam=jam, metode=sesi.get("metode", "Offline"),
    )


def render_reminder_besok_card_list(sesi_list, layout, refresh_callback=None, parent_widget=None):
    """
    Render daftar sesi BESOK (panel "Reminder Besok" di Dashboard Admin)
    sebagai KARTU terpisah — selaras dengan gaya kartu di
    render_absensi_card_list (background putih, border, bayangan halus,
    jam sebagai badge, nama murid sebagai elemen utama) — tiap kartu punya
    tombol "Salin Pengingat" (copy teks WA ke clipboard) & "Reschedule"
    (ubah tanggal/jam sesi).
    """
    from database import DB

    total = len(sesi_list)
    for idx, sesi in enumerate(sesi_list):
        status = sesi.get("status", "Pending")
        # Sesi yang BATAL/RESCHEDULE-nya sudah diklik dianggap terkunci —
        # kartu dipudarkan abu-abu & tombol BATAL/RESCHEDULE dinonaktifkan,
        # sama seperti kartu di "Absensi Hari Ini". SALIN PENGINGAT sengaja
        # dikecualikan (tetap aktif) karena admin mungkin masih perlu
        # menyalin ulang teks pengingat kapan saja.
        is_locked = status in _STATUS_ABSEN_BADGE

        card = QFrame()
        card.setObjectName("reminderCard")
        card.setStyleSheet(f"""
            QFrame#reminderCard {{
                background-color:{C.SURFACE_ALT if is_locked else C.SURFACE};
                border:1px solid {C.BORDER};
                border-radius:14px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(15, 23, 42, 22))
        card.setGraphicsEffect(shadow)

        cv = QVBoxLayout(card)
        cv.setContentsMargins(18, 16, 18, 16)
        cv.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        jl = QLabel(sesi["jam"])
        jl.setStyleSheet(
            f"background:{C.SURFACE_ALT};color:{C.ACCENT_DARK};"
            "font-family:'Consolas','Courier New',monospace;font-weight:bold;"
            "font-size:12px;padding:5px 10px;border-radius:8px;border:none;"
        )
        top_row.addWidget(jl)
        top_row.addStretch()
        if is_locked:
            bg, border_c, fg, icon_name, label = _STATUS_ABSEN_BADGE[status]
            top_row.addWidget(_badge_widget(icon_name, label, bg, border_c, fg))
        cv.addLayout(top_row)

        nl = QLabel(sesi["murid"])
        nl_color = C.TEXT_MUTED if is_locked else C.TEXT_PRIMARY
        nl.setStyleSheet(f"font-weight:700;color:{nl_color};font-size:16px;background:transparent;border:none;")
        cv.addWidget(nl)

        dl_row = QHBoxLayout()
        dl_row.setSpacing(6)
        dl_icon = QLabel()
        dl_icon.setPixmap(svg_pixmap("music", C.TEXT_MUTED, 12))
        dl_icon.setStyleSheet("background:transparent;border:none;")
        dl = QLabel(f"{sesi['les']}  ·  {sesi['guru']}")
        dl.setStyleSheet(f"color:{C.TEXT_MUTED};font-size:12px;background:transparent;border:none;")
        dl_row.addWidget(dl_icon)
        dl_row.addWidget(dl)
        dl_row.addStretch()
        cv.addLayout(dl_row)

        cv.addSpacing(2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_salin = QPushButton("SALIN PENGINGAT")
        btn_salin.setCursor(Qt.PointingHandCursor)
        btn_salin.setFixedHeight(38)
        btn_salin.setIcon(svg_icon("copy", C.ACCENT_DARK, 14))
        btn_salin.setIconSize(QSize(14, 14))
        btn_salin.setStyleSheet(f"""
            QPushButton {{ background:white; color:{C.ACCENT_DARK}; border:1.5px solid #93C5FD;
                          border-radius:8px; font-size:11px; font-weight:bold; }}
            QPushButton:hover {{ background-color:{C.ACCENT_BG}; }}
        """)

        btn_batal = QPushButton("BATAL")
        btn_batal.setCursor(Qt.ArrowCursor if is_locked else Qt.PointingHandCursor)
        btn_batal.setFixedHeight(38)
        btn_batal.setIcon(svg_icon("x", f"{C.TEXT_FAINT}" if is_locked else f"{C.DANGER_DARK}", 14))
        btn_batal.setIconSize(QSize(14, 14))
        btn_batal.setToolTip("Sesi sudah diedit dan terkunci" if is_locked else "Tandai sesi ini sebagai Batal (tidak hadir)")
        btn_batal.setStyleSheet(f"""
            QPushButton {{ background:white; color:{C.DANGER_DARK}; border:1.5px solid {C.DANGER_BORDER};
                          border-radius:8px; font-size:11px; font-weight:bold; }}
            QPushButton:hover {{ background-color:{C.DANGER_BG}; }}
            QPushButton:disabled {{ background:{C.SURFACE_HOVER}; color:{C.TEXT_FAINT};
                          border:1.5px solid {C.BORDER}; }}
        """)
        btn_batal.setEnabled(not is_locked)

        btn_reschedule = QPushButton("RESCHEDULE")
        btn_reschedule.setCursor(Qt.ArrowCursor if is_locked else Qt.PointingHandCursor)
        btn_reschedule.setFixedHeight(38)
        btn_reschedule.setIcon(svg_icon("calendar-check", f"{C.TEXT_FAINT}" if is_locked else "#D97706", 14))
        btn_reschedule.setIconSize(QSize(14, 14))
        btn_reschedule.setToolTip("Sesi sudah diedit dan terkunci" if is_locked else "Ubah tanggal/jam sesi ini")
        btn_reschedule.setStyleSheet(f"""
            QPushButton {{ background:white; color:#D97706; border:1.5px solid #FCD34D;
                          border-radius:8px; font-size:11px; font-weight:bold; }}
            QPushButton:hover {{ background-color:#FFFBEB; }}
            QPushButton:disabled {{ background:{C.SURFACE_HOVER}; color:{C.TEXT_FAINT};
                          border:1.5px solid {C.BORDER}; }}
        """)
        btn_reschedule.setEnabled(not is_locked)

        def _salin(_, s=sesi, btn=btn_salin):
            QApplication.clipboard().setText(_teks_pengingat(s))
            show_toast(parent_widget or btn, "Disalin", "Teks pengingat disalin ke clipboard.", "success", anchor=btn)

        def _tandai_batal(_, sid=sesi["id"], s=sesi):
            jawab = confirm_action(
                parent_widget, "Tandai Tidak Hadir",
                f"Tandai sesi {s['murid']} ({s['jam']}) sebagai Batal/Tidak Hadir? "
                f"Sistem akan otomatis membuat sesi pengganti sesuai pola jadwal "
                f"rutin kalau kuota paket masih tersedia.",
                yes_text="Ya, Batal", no_text="Batal"
            )
            if jawab:
                hasil = DB.batalkan_sesi(sid)
                show_toast(parent_widget, "Berhasil" if hasil["ok"] else "Gagal",
                           hasil["pesan"], "success" if hasil["ok"] else "warning")
                if refresh_callback:
                    refresh_callback()

        def _reschedule(_, s=sesi):
            dlg = RescheduleSesiDialog(parent_widget, sesi_row=s, on_saved=refresh_callback)
            dlg.exec_()

        btn_salin.clicked.connect(_salin)
        btn_batal.clicked.connect(_tandai_batal)
        btn_reschedule.clicked.connect(_reschedule)

        btn_row.addWidget(btn_salin, 1)
        btn_row.addWidget(btn_batal, 1)
        btn_row.addWidget(btn_reschedule, 1)
        cv.addLayout(btn_row)

        layout.addWidget(card)
        if idx < total - 1:
            layout.addSpacing(10)


# ── Widget kecil: fraksi sesi + progress bar ("2 / 4"  ▬▬░░) ────
class _SesiProgress(QWidget):
    def __init__(self, terlaksana: int, total: int, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(3)

        total_disp = total if total > 0 else max(terlaksana, 1)
        lbl = QLabel(f"{terlaksana} / {total if total > 0 else '∞'}")
        lbl.setStyleSheet(f"font-size:11px;font-weight:600;color:{C.TEXT_PRIMARY};background:transparent;border:none;")

        bar = QProgressBar()
        bar.setFixedHeight(6)
        bar.setFixedWidth(90)
        bar.setTextVisible(False)
        bar.setMinimum(0)
        bar.setMaximum(total_disp)
        bar.setValue(min(terlaksana, total_disp))
        bar.setStyleSheet(f"""
            QProgressBar {{ background-color:{C.BORDER}; border:none; border-radius:3px; }}
            QProgressBar::chunk {{ background-color:{C.ACCENT}; border-radius:3px; }}
        """)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(bar)
        lay.addWidget(lbl)
        lay.addLayout(row)


# ── Dialog: Detail Absensi (riwayat sesi + tandai Hadir/Tidak Hadir) ────
class DetailAbsensiDialog(QDialog):
    def __init__(self, parent=None, judul="Detail Absensi", pendaftaran_id=None,
                 guru_id=None, on_change=None):
        super().__init__(parent)
        self.setWindowTitle(judul)
        self._judul = judul
        self._pendaftaran_id = pendaftaran_id
        self._guru_id = guru_id
        self._on_change = on_change
        # Sisi guru: tampilkan kolom "Murid" tambahan, read-only (kehadiran hanya ditandai dari sisi Murid)
        self._show_murid_col = guru_id is not None
        self._read_only = guru_id is not None

        # Kartu info murid hanya muncul kalau dibuka dari sisi murid (pendaftaran_id terisi)
        self._info = None
        if self._pendaftaran_id is not None:
            from database import DB
            self._info = DB.get_pendaftaran_by_id(self._pendaftaran_id)

        self.setMinimumSize(760 if self._show_murid_col else 700, 620)
        self.setStyleSheet("background-color:white;")
        self._build(judul)
        self._reload()

    # ── header: kartu murid (avatar + nama + badge instrumen + info) ──
    def _build_header_murid(self):
        info = self._info
        nama = info["murid"] if info else "-"
        instrumen = info["instrumen"] if info else "-"
        guru = info["guru"] if info else "-"

        hl = QHBoxLayout()
        hl.setSpacing(14)

        info_col = QVBoxLayout()
        info_col.setSpacing(6)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_lbl = QLabel(nama or "-")
        name_lbl.setStyleSheet(f"font-size:16px;font-weight:800;color:{C.TEXT_PRIMARY};")
        name_row.addWidget(name_lbl)
        badge = QLabel((instrumen or "-").upper())
        badge.setStyleSheet(f"""
            background-color:{C.ACCENT_BG}; color:{C.ACCENT_DARK}; font-size:10px;
            font-weight:800; border-radius:10px; padding:3px 10px;
        """)
        name_row.addWidget(badge)
        name_row.addStretch()
        info_col.addLayout(name_row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(16)
        self.instruktur_lbl = QLabel(f"Instruktur: {guru or '-'}")
        self.instruktur_lbl.setStyleSheet(f"color:{C.TEXT_MUTED};font-size:11px;")
        self.lokasi_lbl = QLabel("Lokasi: -")
        self.lokasi_lbl.setStyleSheet(f"color:{C.TEXT_MUTED};font-size:11px;")
        meta_row.addWidget(self.instruktur_lbl)
        meta_row.addWidget(self.lokasi_lbl)
        meta_row.addStretch()
        info_col.addLayout(meta_row)

        hl.addLayout(info_col, 1)

        total_col = QVBoxLayout()
        total_col.setSpacing(2)
        cap_lbl = QLabel("TOTAL SESI")
        cap_lbl.setAlignment(Qt.AlignRight)
        cap_lbl.setStyleSheet(f"color:{C.TEXT_FAINT};font-size:9px;font-weight:800;")
        total_col.addWidget(cap_lbl)
        self.total_sesi_lbl = QLabel("0 sesi")
        self.total_sesi_lbl.setAlignment(Qt.AlignRight)
        self.total_sesi_lbl.setStyleSheet(f"color:{C.ACCENT_DARK};font-size:16px;font-weight:800;")
        total_col.addWidget(self.total_sesi_lbl)
        hl.addLayout(total_col)

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedHeight(38)
        divider.setStyleSheet(f"color:{C.BORDER};")
        hl.addWidget(divider)

        close_btn = QPushButton()
        close_btn.setIcon(svg_icon("x", f"{C.TEXT_MUTED}", 13))
        close_btn.setIconSize(QSize(13, 13))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Tutup")
        close_btn.setStyleSheet(f"""
            QPushButton {{ border:none; background:{C.SURFACE_HOVER}; border-radius:6px; }}
            QPushButton:hover {{ background:{C.BORDER}; }}
        """)
        close_btn.clicked.connect(self.close)
        hl.addWidget(close_btn, 0, Qt.AlignTop)

        return hl

    # ── header sederhana (judul + tombol tutup) dipakai sisi guru ──
    def _build_header_simple(self, judul):
        hdr = QHBoxLayout()
        t = QLabel(judul)
        t.setStyleSheet(f"font-size:16px;font-weight:700;color:{C.TEXT_PRIMARY};")
        hdr.addWidget(t)
        if self._read_only:
            ro_label = QLabel("Hanya lihat, data otomatis")
            ro_label.setStyleSheet(f"color:{C.TEXT_FAINT};font-size:11px;font-style:italic;")
            hdr.addSpacing(10)
            hdr.addWidget(ro_label)
        hdr.addStretch()
        close_btn = QPushButton()
        close_btn.setIcon(svg_icon("x", f"{C.TEXT_MUTED}", 13))
        close_btn.setIconSize(QSize(13, 13))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Tutup")
        close_btn.setStyleSheet(f"""
            QPushButton {{ border:none; background:{C.SURFACE_HOVER}; border-radius:6px; }}
            QPushButton:hover {{ background:{C.BORDER}; }}
        """)
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        return hdr

    def _build(self, judul):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(16)

        if self._info is not None:
            root.addLayout(self._build_header_murid())
        else:
            root.addLayout(self._build_header_simple(judul))

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{C.BORDER};")
        root.addWidget(line)

        # Sisi murid: kolom Tanggal/Waktu/Status/Aksi (ikon Reschedule & Duplikat). Sisi guru pakai kolom lama
        if self._info is not None:
            self._headers = ["NO", "TANGGAL PELAKSANAAN", "WAKTU / SESI", "STATUS KEHADIRAN"]
            if not self._read_only:
                self._headers = self._headers + ["AKSI"]
        elif self._show_murid_col:
            self._headers = ["No", "Murid", "Tanggal", "Jam", "Metode", "Status"]
        else:
            self._headers = ["No", "Tanggal", "Jam", "Metode", "Status"]
            if not self._read_only:
                self._headers = self._headers + ["Aksi"]

        self.table = QTableWidget(0, len(self._headers))
        self.table.setHorizontalHeaderLabels(self._headers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)          # No
        status_idx = len(self._headers) - 1 if self._read_only else len(self._headers) - 2
        header.setSectionResizeMode(status_idx, QHeaderView.ResizeToContents)  # Status
        if not self._read_only:
            # Lebar Aksi ditetapkan (bukan ResizeToContents) agar tidak kepotong scrollbar vertikal
            aksi_idx = len(self._headers) - 1
            header.setSectionResizeMode(aksi_idx, QHeaderView.Fixed)
            header.resizeSection(aksi_idx, 140 if self._info is not None else 100)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setAlternatingRowColors(True)
        # Scroll per baris (bukan per pixel) agar tidak terpotong separuh di tepi viewport
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerItem)
        self.table.setStyleSheet(f"""
            QTableWidget {{ border:1px solid {C.BORDER}; border-radius:8px; gridline-color:{C.SURFACE_HOVER}; }}
            QTableWidget::item:alternate {{ background-color:#FAFBFC; }}
            QHeaderView::section {{ background-color:{C.SURFACE_ALT}; color:{C.TEXT_MUTED_STRONG}; font-size:10px;
                                    font-weight:bold; border:none; padding:8px; }}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER_STRONG}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        root.addWidget(self.table, 1)

        if self._info is not None:
            note = QLabel(
                "Gunakan ikon di kolom AKSI: pensil untuk buka dialog ubah status "
                "(Terlaksana/Batal), kalender untuk reschedule jadwal, dan salin "
                "untuk pratinjau + salin teks pengingat sesi. Sesi berstatus "
                "Terlaksana otomatis dipindah ke bawah daftar.")
        elif self._read_only:
            note = QLabel(
                "Kehadiran ditandai otomatis lewat tab Absensi Murid, sesi di sini hanya untuk dilihat.")
        else:
            note = QLabel("Klik ikon centang / silang pada kolom Aksi untuk menandai kehadiran sesi.")
        note.setStyleSheet(f"color:{C.TEXT_FAINT};font-size:10px;")
        note.setWordWrap(True)
        root.addWidget(note)

    def _reload(self):
        from database import DB
        if self._pendaftaran_id is not None:
            rows = list(DB.get_sesi_by_pendaftaran(self._pendaftaran_id))
            rows.sort(key=_sesi_sort_key)

            if self._info is not None:
                # ── mode kartu murid (desain baru) ──
                # Total Sesi mengikuti kuota paket yang didaftarkan murid
                # (jumlah_sesi_paket), BUKAN jumlah baris jadwal_sesi — karena
                # setiap sesi yang dibatalkan otomatis membuat 1 baris sesi
                # pengganti, sehingga len(rows) terus bertambah walau kuota
                # paket yang terdaftar tidak berubah.
                kuota = self._info["jumlah_sesi_paket"] or 0
                self.total_sesi_lbl.setText(f"{kuota} sesi" if kuota > 0 else "∞ sesi")
                lokasi = rows[0]["metode"] if rows else None
                self.lokasi_lbl.setText(f"Lokasi: {lokasi or 'Offline'}")

                # "id sesi terakhir" dihitung dari urutan kronologis asli (sebelum diurutkan ulang)
                last_id = rows[-1]["id"] if rows else None

                # Sesi Terlaksana dipindah ke bawah agar sesi yang perlu ditindaklanjuti terlihat dulu
                belum_selesai = [r for r in rows if r["status"] != "Terlaksana"]
                sudah_selesai = [r for r in rows if r["status"] == "Terlaksana"]
                display_rows = belum_selesai + sudah_selesai

                self.table.clearSpans()
                self.table.setRowCount(len(display_rows))
                for i, r in enumerate(display_rows):
                    self._render_row_murid(i, r, is_last=(r["id"] == last_id))
                return
        elif self._guru_id is not None:
            rows = list(DB.get_sesi_guru(self._guru_id))
            # Urutkan per nama murid dulu (baru per tanggal) agar sesi milik murid sama berurutan
            rows.sort(key=lambda r: (
                r["nama_murid"] if "nama_murid" in r.keys() else "", _sesi_sort_key(r)))
        else:
            rows = []

        col_no, col_murid, col_tgl, col_jam, col_metode, col_status, col_aksi = (
            self._col_indices())

        self.table.clearSpans()
        self.table.setRowCount(len(rows))

        if col_murid is None:
            for i, r in enumerate(rows):
                self._render_row(i, r, col_no, col_tgl, col_jam, col_metode, col_status, col_aksi)
            return

        # ── dikelompokkan per murid: nama digabung (merge), label "X sesi"
        # muncul kalau murid itu punya lebih dari satu sesi dengan guru ini ──
        i = 0
        while i < len(rows):
            nama = rows[i]["nama_murid"] if "nama_murid" in rows[i].keys() else "-"
            j = i
            while j < len(rows) and (rows[j]["nama_murid"] if "nama_murid" in rows[j].keys() else "-") == nama:
                j += 1
            group_size = j - i

            name_widget = QWidget()
            nl = QVBoxLayout(name_widget)
            nl.setContentsMargins(8, 6, 8, 6)
            nl.setSpacing(2)
            name_lbl = QLabel(nama or "-")
            name_lbl.setStyleSheet(f"font-weight:bold;color:{C.TEXT_PRIMARY};font-size:12px;background:transparent;")
            nl.addWidget(name_lbl)
            if group_size > 1:
                sub_lbl = QLabel(f"{group_size} sesi")
                sub_lbl.setStyleSheet(f"color:{C.ACCENT_DARK};font-size:9px;font-weight:600;background:transparent;")
                nl.addWidget(sub_lbl)
            nl.addStretch()
            self.table.setCellWidget(i, col_murid, name_widget)
            if group_size > 1:
                self.table.setSpan(i, col_murid, group_size, 1)

            for k in range(i, j):
                self._render_row(k, rows[k], col_no, col_tgl, col_jam, col_metode, col_status, col_aksi)
            i = j

    def _render_row(self, i, r, col_no, col_tgl, col_jam, col_metode, col_status, col_aksi):
        jam = r["jam_mulai"] or ""
        if r["jam_selesai"]:
            jam += f" – {r['jam_selesai']}"

        no_item = QTableWidgetItem(str(i + 1))
        no_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(i, col_no, no_item)

        self.table.setItem(i, col_tgl, QTableWidgetItem(r["tanggal"] or "-"))
        jam_item = QTableWidgetItem(jam or "-")
        jam_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(i, col_jam, jam_item)
        self.table.setItem(i, col_metode, QTableWidgetItem(r["metode"] or "Offline"))

        # ── kolom Status: hanya badge, diberi lebar cukup agar tidak terpotong ──
        st_bg, st_fg, st_label = _STATUS_BADGE(r["status"])
        status_wrap = QWidget()
        sl = QHBoxLayout(status_wrap)
        sl.setContentsMargins(8, 4, 8, 4)
        badge = QLabel(st_label)
        badge.setMinimumWidth(84)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{st_bg};color:{st_fg};border-radius:5px;"
            "font-size:9px;font-weight:bold;padding:4px 8px;")
        sl.addWidget(badge)
        sl.addStretch()
        self.table.setCellWidget(i, col_status, status_wrap)

        # ── kolom Aksi: hanya ada di sisi murid (bisa edit) ──
        if col_aksi is None:
            return

        aksi_wrap = QWidget()
        al = QHBoxLayout(aksi_wrap)
        al.setContentsMargins(8, 2, 8, 2)
        al.setSpacing(8)

        btn_ok = QPushButton()
        btn_ok.setIcon(svg_icon("check", f"{C.SUCCESS_DARK}", 14))
        btn_ok.setIconSize(QSize(14, 14))
        btn_ok.setFixedSize(26, 26)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setToolTip("Tandai Hadir")
        btn_ok.setStyleSheet(f"""
            QPushButton {{ border:1px solid #86EFAC; border-radius:5px; background:white; }}
            QPushButton:hover {{ background-color:{C.SUCCESS_BG}; }}
        """)
        btn_no = QPushButton()
        btn_no.setIcon(svg_icon("x", f"{C.DANGER_DARK}", 14))
        btn_no.setIconSize(QSize(14, 14))
        btn_no.setFixedSize(26, 26)
        btn_no.setCursor(Qt.PointingHandCursor)
        btn_no.setToolTip("Tandai Tidak Hadir")
        btn_no.setStyleSheet(f"""
            QPushButton {{ border:1px solid {C.DANGER_BORDER}; border-radius:5px; background:white; }}
            QPushButton:hover {{ background-color:{C.DANGER_BG}; }}
        """)
        sesi_id = r["id"]
        btn_ok.clicked.connect(lambda _, sid=sesi_id: self._tandai(sid, "Terlaksana"))
        btn_no.clicked.connect(lambda _, sid=sesi_id: self._tandai(sid, "Batal"))
        al.addWidget(btn_ok)
        al.addWidget(btn_no)
        al.addStretch()
        self.table.setCellWidget(i, col_aksi, aksi_wrap)

    def _render_row_murid(self, i, r, is_last=False):
        """Render satu baris tabel gaya baru (kartu murid): No, Tanggal
        Pelaksanaan, Waktu/Sesi, badge Status Kehadiran (pakai gaya
        _STATUS_ABSEN_BADGE/_STATUS_ABSEN_DEFAULT — sama seperti badge
        SUDAH MASUK/TIDAK HADIR/BELUM ABSEN di Dashboard), dan kolom Aksi
        berisi ikon Reschedule + Duplikat Sesi.

        `is_last=True` untuk baris sesi PALING TERAKHIR milik murid ini —
        tombol Duplikat diberi warna merah (bukan biru) sebagai penanda
        visual "sesi terakhir yang terjadwal", sekaligus jadi pengingat
        agar admin menawarkan perpanjangan/pembayaran les berikutnya saat
        menduplikat sesi ini."""
        jam = r["jam_mulai"] or ""
        if r["jam_selesai"]:
            jam += f" – {r['jam_selesai']}"

        no_item = QTableWidgetItem(str(i + 1))
        no_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(i, 0, no_item)

        tgl_wrap = QWidget()
        tl = QHBoxLayout(tgl_wrap)
        tl.setContentsMargins(8, 4, 8, 4)
        tl.setSpacing(6)
        tgl_icon = QLabel()
        tgl_icon.setPixmap(svg_pixmap("calendar-check", f"{C.TEXT_FAINT}", 12))
        tgl_icon.setStyleSheet("background:transparent;border:none;")
        tgl_lbl = QLabel(r["tanggal"] or "-")
        tgl_lbl.setStyleSheet(f"color:{C.TEXT_PRIMARY};font-size:12px;font-weight:600;background:transparent;")
        tl.addWidget(tgl_icon)
        tl.addWidget(tgl_lbl)
        tl.addStretch()
        self.table.setCellWidget(i, 1, tgl_wrap)

        jam_wrap = QWidget()
        jl = QHBoxLayout(jam_wrap)
        jl.setContentsMargins(8, 4, 8, 4)
        jl.setSpacing(6)
        jam_icon = QLabel()
        jam_icon.setPixmap(svg_pixmap("clock", f"{C.TEXT_FAINT}", 12))
        jam_icon.setStyleSheet("background:transparent;border:none;")
        jam_lbl = QLabel(jam or "-")
        jam_lbl.setStyleSheet(f"color:{C.TEXT_BODY};font-size:12px;background:transparent;")
        jl.addWidget(jam_icon)
        jl.addWidget(jam_lbl)
        jl.addStretch()
        self.table.setCellWidget(i, 2, jam_wrap)

        st_bg, st_border, st_fg, st_icon, st_label = _STATUS_ABSEN_BADGE.get(
            r["status"], _STATUS_ABSEN_DEFAULT)
        status_wrap = QWidget()
        sl = QHBoxLayout(status_wrap)
        sl.setContentsMargins(8, 0, 8, 0)
        status_badge = _badge_widget(st_icon, st_label, st_bg, st_border, st_fg)
        # Tinggi disamakan 30px dengan tombol ikon Edit/Reschedule/Salin di kolom AKSI
        status_badge.setFixedHeight(30)
        sl.addWidget(status_badge)
        sl.addStretch()
        self.table.setCellWidget(i, 3, status_wrap)

        if self._read_only:
            return

        aksi_wrap = QWidget()
        al = QHBoxLayout(aksi_wrap)
        al.setContentsMargins(8, 2, 8, 2)
        al.setSpacing(8)

        # ── Data sesi dipakai bersama ketiga dialog aksi (Edit/Reschedule/Salin) ──
        nama = self._info["murid"] if self._info else "-"
        kursus = self._info["instrumen"] if self._info else "-"
        guru = r["nama_guru"] or (self._info["guru"] if self._info else "-")
        metode = r["metode"] or "Offline"
        sesi_untuk_aksi = {
            "id": r["id"],
            "tanggal": r["tanggal"],
            "jam_mulai": r["jam_mulai"],
            "jam_selesai": r["jam_selesai"],
            "jam": jam,
            "murid": nama,
            "les": kursus,
            "kursus": kursus,
            "guru": guru,
            "metode": metode,
            "status": r["status"],
        }

        # ── 1) EDIT — buka dialog pilih status Terlaksana/Batal, gaya & alurnya sama dengan Reschedule ──
        btn_edit = QPushButton()
        btn_edit.setIcon(svg_icon("pencil", f"{C.ACCENT_DARK}", 14))
        btn_edit.setIconSize(QSize(14, 14))
        btn_edit.setFixedSize(30, 30)
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setToolTip("Ubah status kehadiran (Terlaksana / Batal)")
        btn_edit.setStyleSheet(f"""
            QPushButton {{ border:1px solid {C.ACCENT_BORDER}; border-radius:7px; background:{C.ACCENT_BG}; }}
            QPushButton:hover {{ background-color:{C.ACCENT_BG_STRONG}; }}
        """)

        def _edit_status(_, s=sesi_untuk_aksi):
            dlg = EditStatusSesiDialog(self, sesi_row=s, on_saved=self._on_data_changed)
            dlg.exec_()

        btn_edit.clicked.connect(_edit_status)

        # ── 2) RESCHEDULE — ubah tanggal/jam sesi ───────────────────────
        btn_reschedule = QPushButton()
        btn_reschedule.setIcon(svg_icon("calendar-check", f"{C.WARNING_DARK}", 14))
        btn_reschedule.setIconSize(QSize(14, 14))
        btn_reschedule.setFixedSize(30, 30)
        btn_reschedule.setCursor(Qt.PointingHandCursor)
        btn_reschedule.setToolTip("Reschedule sesi ini")
        btn_reschedule.setStyleSheet(f"""
            QPushButton {{ border:1px solid #FED7AA; border-radius:7px; background:{C.WARNING_BG}; }}
            QPushButton:hover {{ background-color:#FFEDD5; }}
        """)
        btn_reschedule.clicked.connect(
            lambda _, s=sesi_untuk_aksi: self._reschedule(s))

        # ── 3) SALIN PENGINGAT — pratinjau teks WA, disalin lewat tombol "Salin ke Clipboard" ──
        btn_salin = QPushButton()
        if is_last:
            btn_salin.setIcon(svg_icon("copy", f"{C.DANGER_DARK}", 14))
            btn_salin.setToolTip(
                "Sesi terakhir yang terjadwal — salin pengingat sekaligus "
                "berisi info perpanjangan paket")
            btn_salin.setStyleSheet(f"""
                QPushButton {{ border:1px solid #FECACA; border-radius:7px; background:{C.DANGER_BG}; }}
                QPushButton:hover {{ background-color:#FEE2E2; }}
            """)
        else:
            btn_salin.setIcon(svg_icon("copy", f"{C.ACCENT_DARK}", 14))
            btn_salin.setToolTip("Salin pengingat sesi ini ke clipboard")
            btn_salin.setStyleSheet(f"""
                QPushButton {{ border:1px solid {C.ACCENT_BORDER}; border-radius:7px; background:{C.ACCENT_BG}; }}
                QPushButton:hover {{ background-color:{C.ACCENT_BG_STRONG}; }}
            """)
        btn_salin.setIconSize(QSize(14, 14))
        btn_salin.setFixedSize(30, 30)
        btn_salin.setCursor(Qt.PointingHandCursor)

        def _salin_pengingat(_, s=sesi_untuk_aksi, last=is_last):
            teks = _teks_pengingat_sesi(
                s["murid"], s["kursus"], s["guru"], s["tanggal"] or "-",
                s["jam"] or "-", s["metode"], is_last=last)
            dlg = SalinPengingatDialog(self, sesi_row=s, teks=teks)
            dlg.exec_()

        btn_salin.clicked.connect(_salin_pengingat)

        al.addWidget(btn_edit)
        al.addWidget(btn_reschedule)
        al.addWidget(btn_salin)
        al.addStretch()
        self.table.setCellWidget(i, 4, aksi_wrap)

    def _reschedule(self, sesi_row):
        dlg = RescheduleSesiDialog(self, sesi_row=sesi_row, on_saved=self._on_data_changed)
        dlg.exec_()

    def _duplikat(self, sesi_id):
        from database import DB
        jawab = confirm_action(
            self,
            "Duplikat Sesi",
            "Buat sesi baru dengan jam & guru yang sama, seminggu setelah sesi ini?",
            yes_text="Ya, Duplikat",
            no_text="Batal"
        )
        if not jawab:
            return
        hasil = DB.duplikat_sesi(sesi_id)
        if hasil["ok"]:
            show_toast(self, "Berhasil", hasil["pesan"], "success")
            self._on_data_changed()
        else:
            show_toast(self, "Gagal", hasil["pesan"], "warning")

    def _duplikat_sesi_terakhir(self, sesi_id):
        """Sama seperti _duplikat, tapi khusus dipanggil dari sesi PALING
        TERAKHIR murid ini — dialog konfirmasinya menambahkan pengingat
        agar admin menawarkan pembayaran/perpanjangan les berikutnya ke
        orang tua murid, karena setelah sesi ini murid belum punya jadwal
        lanjutan."""
        from database import DB
        jawab = confirm_action(
            self,
            "Duplikat Sesi Terakhir",
            "Ini sesi terakhir yang terjadwal untuk murid ini. Buat sesi baru "
            "dengan jam & guru yang sama, seminggu setelah sesi ini — dan "
            "jangan lupa ingatkan orang tua murid untuk membayar les berikutnya.",
            yes_text="Ya, Duplikat",
            no_text="Batal"
        )
        if not jawab:
            return
        hasil = DB.duplikat_sesi(sesi_id)
        if hasil["ok"]:
            show_toast(
                self, "Berhasil",
                hasil["pesan"] + " Jangan lupa ingatkan pembayaran les berikutnya.",
                "success")
            self._on_data_changed()
        else:
            show_toast(self, "Gagal", hasil["pesan"], "warning")

    def _on_data_changed(self):
        self._reload()
        if self._on_change:
            self._on_change()

    def _col_indices(self):
        """Kembalikan indeks kolom (No, Murid, Tanggal, Jam, Metode, Status, Aksi);
        Murid/Aksi bernilai None kalau kolom itu tidak ditampilkan."""
        if self._show_murid_col:
            no, murid, tgl, jam, metode, status = 0, 1, 2, 3, 4, 5
        else:
            no, murid, tgl, jam, metode, status = 0, None, 1, 2, 3, 4
        aksi = None if self._read_only else status + 1
        return no, murid, tgl, jam, metode, status, aksi

    def _tandai(self, sesi_id, status):
        if self._read_only:
            return
        from database import DB
        if status == "Batal":
            hasil = DB.batalkan_sesi(sesi_id)
            show_toast(self, "Berhasil" if hasil["ok"] else "Gagal",
                       hasil["pesan"], "success" if hasil["ok"] else "warning")
        else:
            DB.set_status_sesi(sesi_id, status)
        self._reload()
        if self._on_change:
            self._on_change()


# ── TAB 1 — ABSENSI MURID ───────────────────────────────────────
_HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
             "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def _hari_les(sesi_list):
    """Ambil pola hari les (mis. 'Senin, Kamis') dari kumpulan tanggal sesi
    milik satu pendaftaran. Dihitung otomatis dari hari-dalam-minggu yang
    benar-benar muncul di jadwal sesi (bukan field terpisah yang diisi
    manual), supaya kalau jadwalnya di-reschedule, "Hari Les" ikut update
    dengan sendirinya tanpa perlu disunting ulang.

    Sesi bertipe 'Reschedule' (pindah KHUSUS di luar pola rutin, mis.
    sekali pindah ke Kamis lewat dialog Reschedule) SENGAJA dikecualikan
    — supaya satu kali pindah jadwal tidak membuat "Hari Les" melebar
    (mis. jadi ikut menampilkan Kamis padahal itu bukan hari rutin).
    Selaras dengan _pola_hari_pendaftaran di database.py."""
    hari_set = set()
    for s in sesi_list:
        tipe = s["tipe_sesi"] if "tipe_sesi" in s.keys() else "Reguler"
        if (tipe or "Reguler") != "Reguler":
            continue
        tgl = s["tanggal"]
        dt = None
        for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(tgl, fmt)
                break
            except (ValueError, TypeError):
                continue
        if dt is not None:
            hari_set.add(dt.weekday())
    if not hari_set:
        return "-"
    return ", ".join(_HARI_ID[w] for w in sorted(hari_set))


def _metode_pendaftaran(sesi_list):
    """Ambil metode les (Offline/Online/dst.) dari kumpulan sesi milik satu
    pendaftaran — sama seperti _hari_les(), sesi 'Reschedule' dikecualikan
    supaya satu kali pindah metode (mis. reschedule ke Online) tidak
    membuat kolom Metode ikut menampilkan metode sesi pengganti tsb.
    Kalau ada lebih dari satu metode dalam pola rutin, semua ditampilkan
    dipisah koma (mis. 'Offline, Online' untuk jadwal campuran)."""
    metode_set = set()
    for s in sesi_list:
        tipe = s["tipe_sesi"] if "tipe_sesi" in s.keys() else "Reguler"
        if (tipe or "Reguler") != "Reguler":
            continue
        metode_set.add(s["metode"] or "Offline")
    if not metode_set:
        return "-"
    return ", ".join(sorted(metode_set))


class AbsensiMuridWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color:{C.SURFACE_ALT};")
        self._rows_cache = []
        self._filter_periode_diset = False  # supaya default bulan/tahun ini hanya diterapkan sekali di awal
        self._build_ui()
        self._reload_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("Absensi Semua Murid")
        t.setStyleSheet(f"font-size:16px;font-weight:700;color:{C.TEXT_PRIMARY};")
        s = QLabel("Kelola kehadiran harian dan pantau sisa sesi kursus murid.")
        s.setStyleSheet(f"font-size:11px;color:{C.TEXT_MUTED};")
        col.addWidget(t); col.addWidget(s)
        hdr.addLayout(col)
        hdr.addStretch()

        btn_tambah = QPushButton("+  Tambah Les Baru")
        btn_tambah.setCursor(Qt.PointingHandCursor)
        btn_tambah.setFixedHeight(38)
        btn_tambah.setStyleSheet(primary_button_style())
        btn_tambah.clicked.connect(self._tambah_les_baru)
        hdr.addWidget(btn_tambah)
        root.addLayout(hdr)

        # ── Search & Filter — search sendiri baris pertama, 5 filter sekunder langsung terlihat ──
        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Cari nama murid atau guru...")
        self.search_box.addAction(svg_icon("search", C.TEXT_FAINT, 15), QLineEdit.LeadingPosition)
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedHeight(36)
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                border:1.5px solid {C.BORDER}; border-radius:8px;
                background:{C.SURFACE_ALT}; padding-left:12px;
                font-size:12px; color:{C.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{ border:1.5px solid {C.ACCENT}; background:white; }}
        """)
        self.search_box.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_box, 1)

        root.addLayout(search_row)

        # ── panel filter (collapsible) — 5 dropdown gaya "pill" sejajar ──
        self.filter_panel = QFrame()
        self.filter_panel.setStyleSheet("QFrame { background:transparent; border:none; }")
        panel_lay = QHBoxLayout(self.filter_panel)
        panel_lay.setContentsMargins(0, 4, 0, 4)
        panel_lay.setSpacing(12)

        label_filter = QLabel("Filter")
        label_filter.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{C.TEXT_BODY};background:transparent;")
        panel_lay.addWidget(label_filter)

        self.filter_murid = QComboBox()
        self.filter_murid.setFixedHeight(40)
        self._style_combo(self.filter_murid)
        self.filter_murid.currentIndexChanged.connect(self._apply_filter)

        self.filter_guru = QComboBox()
        self.filter_guru.setFixedHeight(40)
        self._style_combo(self.filter_guru)
        self.filter_guru.currentIndexChanged.connect(self._apply_filter)

        # ── filter Bulan & Tahun — cocokkan murid yang punya sesi di bulan/tahun terpilih ──
        self.filter_bulan = QComboBox()
        self.filter_bulan.setFixedHeight(40)
        self._style_combo(self.filter_bulan)
        self.filter_bulan.addItem("Semua Bulan", "all")
        for idx_bulan, nama_bulan in enumerate(_BULAN_ID, start=1):
            self.filter_bulan.addItem(nama_bulan, idx_bulan)
        self.filter_bulan.currentIndexChanged.connect(self._apply_filter)

        self.filter_tahun = QComboBox()
        self.filter_tahun.setFixedHeight(40)
        self._style_combo(self.filter_tahun)
        self.filter_tahun.addItem("Semua Tahun", "all")
        self.filter_tahun.currentIndexChanged.connect(self._apply_filter)

        # ── filter Status Paket — default "Masih Berlangsung" (kondisi yang paling sering dicek) ──
        self.filter_status_paket = QComboBox()
        self.filter_status_paket.setFixedHeight(40)
        self._style_combo(self.filter_status_paket)
        self.filter_status_paket.addItem("Semua Status", "all")
        self.filter_status_paket.addItem("Masih Berlangsung", "berlangsung")
        self.filter_status_paket.addItem("Sudah Terlaksana Semua", "selesai")
        self.filter_status_paket.setCurrentIndex(1)
        self.filter_status_paket.currentIndexChanged.connect(self._apply_filter)

        panel_lay.addWidget(self.filter_murid, 1)
        panel_lay.addWidget(self.filter_guru, 1)
        panel_lay.addWidget(self.filter_bulan, 1)
        panel_lay.addWidget(self.filter_tahun, 1)
        panel_lay.addWidget(self.filter_status_paket, 1)

        root.addWidget(self.filter_panel)

        # ── table ──
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["MURID", "INSTRUMEN", "GURU PEMBIMBING", "METODE", "HARI LES", "SESI TERSISA", "AKSI"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        # Lebar Aksi ditetapkan (bukan ResizeToContents) agar tombol "Lihat Detail" tidak kepotong scrollbar
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.resizeSection(6, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background-color:white; border:1px solid {C.BORDER}; border-radius:10px; }}
            QHeaderView::section {{ background-color:{C.SURFACE_ALT}; color:{C.TEXT_MUTED_STRONG}; font-size:10px;
                                    font-weight:bold; border:none; border-bottom:1px solid {C.BORDER}; padding:10px; }}
            QTableWidget::item {{ border-bottom:1px solid {C.SURFACE_HOVER}; padding:6px; }}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER_STRONG}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        self.table.verticalHeader().setDefaultSectionSize(56)
        root.addWidget(self.table, 1)

    def _style_combo(self, combo: QComboBox):
        style_combo(combo, radius=10, height=36, font_size=12)

    def _tambah_les_baru(self):
        from DataMurid import TambahJadwalDialog
        dlg = TambahJadwalDialog(self)
        dlg.exec_()
        self._reload_data()

    def _reload_data(self):
        from database import DB
        DB.sinkronkan_paket_selesai()
        # Pakai get_pendaftaran_semua() (bukan get_pendaftaran_aktif()) supaya paket yang
        # sesinya sudah terlaksana semua ('Selesai') tidak hilang, tapi tetap tampil sebagai
        # riwayat/arsip lewat filter Status Paket "Sudah Terlaksana Semua".
        pendaftaran_list = DB.get_pendaftaran_semua()

        rows = []
        tahun_set = set()
        for pk in pendaftaran_list:
            sesi_list = DB.get_sesi_by_pendaftaran(pk["pendaftaran_id"])
            terlaksana = [s for s in sesi_list if s["status"] in ("Terlaksana", "Selesai")]
            terlaksana.sort(key=_sesi_sort_key)
            hari_les = _hari_les(sesi_list)
            metode = _metode_pendaftaran(sesi_list)

            # kumpulan (bulan, tahun) dari semua sesi paket ini, dihitung dari tanggal sesi untuk filter
            bulan_tahun = set()
            for s in sesi_list:
                dt = _parse_tanggal(s["tanggal"])
                if dt is not None:
                    bulan_tahun.add((dt.month, dt.year))
                    tahun_set.add(dt.year)

            rows.append({
                "pendaftaran_id": pk["pendaftaran_id"],
                "murid": pk["murid"],
                "instrumen": pk["instrumen"],
                "guru": pk["guru"],
                "hari_les": hari_les,
                "metode": metode,
                "terlaksana": len(terlaksana),
                "total": pk["jumlah_sesi_paket"] or 0,
                "bulan_tahun": bulan_tahun,
            })
        # Urutkan per nama murid agar baris-baris kursus milik murid yang sama berurutan
        rows.sort(key=lambda r: (r["murid"], r["instrumen"]))
        self._rows_cache = rows

        # isi ulang filter combo tanpa memicu loop sinyal
        cur_m = self.filter_murid.currentData()
        cur_g = self.filter_guru.currentData()
        self.filter_murid.blockSignals(True)
        self.filter_guru.blockSignals(True)
        self.filter_murid.clear()
        self.filter_murid.addItem("Semua Murid", "all")
        for nama in sorted({r["murid"] for r in rows}):
            self.filter_murid.addItem(nama, nama)
        self.filter_guru.clear()
        self.filter_guru.addItem("Semua Guru", "all")
        for nama in sorted({r["guru"] for r in rows if r["guru"] and r["guru"] != "–"}):
            self.filter_guru.addItem(nama, nama)
        idx_m = self.filter_murid.findData(cur_m)
        idx_g = self.filter_guru.findData(cur_g)
        self.filter_murid.setCurrentIndex(idx_m if idx_m >= 0 else 0)
        self.filter_guru.setCurrentIndex(idx_g if idx_g >= 0 else 0)
        self.filter_murid.blockSignals(False)
        self.filter_guru.blockSignals(False)

        cur_t = self.filter_tahun.currentData()
        self.filter_tahun.blockSignals(True)
        self.filter_tahun.clear()
        self.filter_tahun.addItem("Semua Tahun", "all")
        for y in sorted(tahun_set):
            self.filter_tahun.addItem(str(y), y)
        idx_t = self.filter_tahun.findData(cur_t)
        self.filter_tahun.setCurrentIndex(idx_t if idx_t >= 0 else 0)
        self.filter_tahun.blockSignals(False)

        # ── Default filter saat halaman pertama kali dibuka: bulan & tahun berjalan
        # ("bulan ini, tahun ini") + status "Masih Berlangsung" (sudah default dari _build_ui).
        # Hanya diterapkan sekali di awal — supaya tidak menimpa filter yang sedang dipilih
        # pengguna setiap kali data di-reload (mis. setelah tambah les baru).
        if not self._filter_periode_diset:
            self._filter_periode_diset = True
            now = datetime.now()
            idx_bulan_ini = self.filter_bulan.findData(now.month)
            if idx_bulan_ini >= 0:
                self.filter_bulan.blockSignals(True)
                self.filter_bulan.setCurrentIndex(idx_bulan_ini)
                self.filter_bulan.blockSignals(False)
            idx_tahun_ini = self.filter_tahun.findData(now.year)
            if idx_tahun_ini >= 0:
                self.filter_tahun.blockSignals(True)
                self.filter_tahun.setCurrentIndex(idx_tahun_ini)
                self.filter_tahun.blockSignals(False)

        self._apply_filter()

    def _apply_filter(self):
        q = self.search_box.text().strip().lower()
        f_murid = self.filter_murid.currentData() or "all"
        f_guru  = self.filter_guru.currentData() or "all"
        f_bulan = self.filter_bulan.currentData() or "all"
        f_tahun = self.filter_tahun.currentData() or "all"
        f_status_paket = self.filter_status_paket.currentData() or "all"

        rows = self._rows_cache
        if f_murid != "all":
            rows = [r for r in rows if r["murid"] == f_murid]
        if f_guru != "all":
            rows = [r for r in rows if r["guru"] == f_guru]
        if q:
            rows = [r for r in rows if q in r["murid"].lower() or q in r["guru"].lower()]

        if f_bulan != "all" or f_tahun != "all":
            def _cocok_periode(r):
                for (b, y) in r["bulan_tahun"]:
                    if (f_bulan == "all" or b == f_bulan) and (f_tahun == "all" or y == f_tahun):
                        return True
                return False
            rows = [r for r in rows if _cocok_periode(r)]

        if f_status_paket != "all":
            def _status_paket(r):
                if r["total"] and r["total"] > 0 and r["terlaksana"] >= r["total"]:
                    return "selesai"
                return "berlangsung"
            rows = [r for r in rows if _status_paket(r) == f_status_paket]

        self._render_rows(rows)

    def _render_rows(self, rows):
        self.table.clearSpans()
        self.table.setRowCount(len(rows))

        # `rows` sudah terurut per nama murid (lihat _reload_data) sehingga bisa dikelompokkan
        i = 0
        while i < len(rows):
            nama = rows[i]["murid"]
            j = i
            while j < len(rows) and rows[j]["murid"] == nama:
                j += 1
            group_size = j - i

            # ── kolom MURID digabung (merge) agar murid dengan 2+ kursus tidak terlihat duplikat ──
            name_widget = QWidget()
            nl = QVBoxLayout(name_widget)
            nl.setContentsMargins(8, 6, 8, 6)
            nl.setSpacing(2)
            name_lbl = QLabel(nama)
            name_lbl.setStyleSheet(f"font-weight:bold;color:{C.TEXT_PRIMARY};font-size:12px;background:transparent;")
            nl.addWidget(name_lbl)
            if group_size > 1:
                sub_lbl = QLabel(f"{group_size} kursus aktif")
                sub_lbl.setStyleSheet(f"color:{C.ACCENT_DARK};font-size:9px;font-weight:600;background:transparent;")
                nl.addWidget(sub_lbl)
            nl.addStretch()
            self.table.setCellWidget(i, 0, name_widget)
            if group_size > 1:
                self.table.setSpan(i, 0, group_size, 1)

            for k in range(i, j):
                r = rows[k]
                self.table.setItem(k, 1, self._cell(r["instrumen"]))
                self.table.setItem(k, 2, self._cell(r["guru"]))
                self.table.setItem(k, 3, self._cell(r["metode"]))
                self.table.setItem(k, 4, self._cell(r["hari_les"]))
                self.table.setCellWidget(k, 5, _SesiProgress(r["terlaksana"], r["total"]))

                btn = QPushButton("Lihat Detail")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setFixedHeight(32)
                btn.setMinimumWidth(100)
                btn.setStyleSheet(action_button_style())
                pid = r["pendaftaran_id"]
                judul = f"Absensi — {r['murid']} ({r['instrumen']})"
                btn.clicked.connect(lambda _, pid=pid, judul=judul: self._lihat_detail(pid, judul))
                wrap = QWidget()
                wl = QHBoxLayout(wrap)
                wl.setContentsMargins(8, 0, 8, 0)
                wl.addWidget(btn)
                self.table.setCellWidget(k, 6, wrap)

            i = j

        if not rows:
            self.table.setRowCount(1)
            empty = QTableWidgetItem("Belum ada murid dengan pendaftaran kursus aktif.")
            empty.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 0, empty)
            self.table.setSpan(0, 0, 1, 7)

    def _cell(self, text, bold=False):
        item = QTableWidgetItem(str(text))
        if bold:
            f = QFont("Segoe UI", 10, QFont.Bold)
            item.setFont(f)
            item.setForeground(QColor(f"{C.TEXT_PRIMARY}"))
        else:
            item.setForeground(QColor(f"{C.TEXT_BODY}"))
        return item

    def _lihat_detail(self, pendaftaran_id, judul):
        dlg = DetailAbsensiDialog(self, judul=judul, pendaftaran_id=pendaftaran_id,
                                   on_change=self._reload_data)
        dlg.exec_()


# ── DIALOG — FORM ABSENSI ADMIN (input manual, dipakai untuk Tambah & Edit) ────
class FormAbsensiAdminDialog(QDialog):
    """
    Form input manual satu baris kehadiran admin.
    - existing=None            -> mode Tambah (INSERT baris baru).
    - existing=<sqlite3.Row>   -> mode Edit (UPDATE baris r["id"]).
    on_saved dipanggil setelah data berhasil disimpan ke database.
    """
    def __init__(self, parent=None, existing=None, on_saved=None):
        super().__init__(parent)
        self._existing = existing
        self._on_saved = on_saved
        self.setWindowTitle("Edit Absensi Admin" if existing else "Tambah Absensi Admin")
        self.setFixedWidth(380)
        self.setStyleSheet(f"QDialog {{ background:{C.SURFACE_ALT}; }}")
        self._build_ui()
        if existing:
            self._prefill(existing)

    def _field_label(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:11px;font-weight:bold;color:{C.TEXT_MUTED};")
        return l

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(10)

        title = QLabel("Edit Absensi Admin" if self._existing else "Tambah Absensi Admin")
        title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C.TEXT_PRIMARY};")
        root.addWidget(title)
        sub = QLabel("Kehadiran diketik manual — bukan otomatis dari login/logout.")
        sub.setStyleSheet(f"font-size:10px;color:{C.TEXT_MUTED};")
        sub.setWordWrap(True)
        root.addWidget(sub)
        root.addSpacing(6)

        _input_qss = f"""
            QLineEdit, QComboBox, QDateEdit {{
                border:1px solid {C.BORDER}; border-radius:8px; padding:0 10px;
                font-size:12px; background:{C.SURFACE}; color:{C.TEXT_PRIMARY};
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border:1.5px solid {C.ACCENT}; }}
        """

        root.addWidget(self._field_label("Admin"))
        self.combo_admin = QComboBox()
        self.combo_admin.setFixedHeight(38)
        # Dipakai style_combo() dari theme.py agar konsisten dengan dropdown filter lain
        style_combo(self.combo_admin, radius=8, height=38, font_size=12)
        from database import DB
        for a in DB.get_admin_aktif():
            self.combo_admin.addItem(a["nama"], a["id"])
        root.addWidget(self.combo_admin)

        root.addWidget(self._field_label("Tanggal"))
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd-MM-yyyy")
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setFixedHeight(38)
        self.date_input.setStyleSheet(_input_qss)
        root.addWidget(self.date_input)

        jam_row = QHBoxLayout()
        jam_row.setSpacing(10)
        col_masuk = QVBoxLayout()
        col_masuk.addWidget(self._field_label("Jam Masuk"))
        self.input_masuk = QLineEdit()
        self.input_masuk.setPlaceholderText("cth. 08.00")
        self.input_masuk.setFixedHeight(38)
        self.input_masuk.setStyleSheet(_input_qss)
        col_masuk.addWidget(self.input_masuk)
        col_pulang = QVBoxLayout()
        col_pulang.addWidget(self._field_label("Jam Pulang"))
        self.input_pulang = QLineEdit()
        self.input_pulang.setPlaceholderText("cth. 16.00")
        self.input_pulang.setFixedHeight(38)
        self.input_pulang.setStyleSheet(_input_qss)
        col_pulang.addWidget(self.input_pulang)
        jam_row.addLayout(col_masuk)
        jam_row.addLayout(col_pulang)
        root.addLayout(jam_row)

        root.addWidget(self._field_label("Uang Makan (Rp)"))
        self.input_uang_makan = QLineEdit()
        self.input_uang_makan.setText("1")
        self.input_uang_makan.setPlaceholderText("0")
        self.input_uang_makan.setFixedHeight(38)
        self.input_uang_makan.setStyleSheet(_input_qss)
        root.addWidget(self.input_uang_makan)

        root.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_batal = QPushButton("Batal")
        btn_batal.setFixedHeight(40)
        btn_batal.setCursor(Qt.PointingHandCursor)
        btn_batal.setStyleSheet(f"""
            QPushButton {{ background:{C.SURFACE}; color:{C.TEXT_MUTED}; border:1px solid {C.BORDER};
                          border-radius:8px; font-size:12px; font-weight:600; }}
            QPushButton:hover {{ background-color:{C.SURFACE_ALT}; }}
        """)
        btn_batal.clicked.connect(self.reject)
        btn_simpan = QPushButton("Simpan")
        btn_simpan.setFixedHeight(40)
        btn_simpan.setCursor(Qt.PointingHandCursor)
        btn_simpan.setStyleSheet(f"""
            QPushButton {{ background-color:{C.ACCENT_DARK}; color:white; border:none;
                          border-radius:8px; font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background-color:{C.ACCENT_DARKER}; }}
        """)
        btn_simpan.clicked.connect(self._simpan)
        btn_row.addWidget(btn_batal, 1)
        btn_row.addWidget(btn_simpan, 1)
        root.addLayout(btn_row)

    def _prefill(self, r):
        idx = self.combo_admin.findText(r["nama_admin"])
        if idx >= 0:
            self.combo_admin.setCurrentIndex(idx)
        try:
            d, m, y = r["tanggal"].split("-")
            self.date_input.setDate(QDate(int(y), int(m), int(d)))
        except Exception:
            pass
        self.input_masuk.setText(r["jam_masuk"] or "")
        self.input_pulang.setText(r["jam_pulang"] or "")
        self.input_uang_makan.setText(str(r["uang_makan"] or 0))

    def _simpan(self):
        from database import DB

        admin_id = self.combo_admin.currentData()
        if admin_id is None:
            show_toast(self, "Perhatian", "Belum ada admin aktif untuk dipilih.", "warning")
            return

        tanggal = self.date_input.date().toString("dd-MM-yyyy")
        jam_masuk = self.input_masuk.text().strip()
        jam_pulang = self.input_pulang.text().strip()

        if not jam_masuk and not jam_pulang:
            show_toast(self, "Perhatian", "Isi minimal Jam Masuk atau Jam Pulang.", "warning")
            return

        uang_text = self.input_uang_makan.text().strip().replace(".", "").replace(",", "")
        try:
            uang_makan = int(uang_text) if uang_text else 0
        except ValueError:
            show_toast(self, "Perhatian", "Uang Makan harus berupa angka.", "warning")
            return

        kehadiran_id = self._existing["id"] if self._existing else None
        DB.simpan_kehadiran_admin_manual(
            admin_id, tanggal, jam_masuk, jam_pulang, uang_makan, kehadiran_id=kehadiran_id
        )

        if self._on_saved:
            self._on_saved()
        self.accept()


# ── TAB 2 — ABSENSI ADMIN  (jam masuk / jam pulang staf admin — input manual) ────
class AbsensiAdminWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color:{C.SURFACE_ALT};")
        self._build_ui()
        self._reload_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("Absensi Admin")
        t.setStyleSheet(f"font-size:16px;font-weight:700;color:{C.TEXT_PRIMARY};")
        s = QLabel("Jam masuk & jam pulang staf admin — diketik manual, klik \"+ Tambah Absensi\".")
        s.setStyleSheet(f"font-size:11px;color:{C.TEXT_MUTED};")
        col.addWidget(t); col.addWidget(s)
        hdr.addLayout(col)
        hdr.addStretch()

        self.filter_admin = QComboBox()
        self.filter_admin.setFixedHeight(36)
        self.filter_admin.setFixedWidth(200)
        style_combo(self.filter_admin, radius=10, height=36, font_size=12)
        self.filter_admin.currentIndexChanged.connect(self._reload_data)
        hdr.addWidget(self.filter_admin)

        btn_tambah = QPushButton("+  Tambah Absensi")
        btn_tambah.setCursor(Qt.PointingHandCursor)
        btn_tambah.setFixedHeight(36)
        btn_tambah.setStyleSheet(primary_button_style())
        btn_tambah.clicked.connect(self._tambah_absensi)
        hdr.addWidget(btn_tambah)
        root.addLayout(hdr)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["TANGGAL", "ADMIN", "JAM MASUK", "JAM PULANG", "UANG MAKAN", "AKSI"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        # Lebar Aksi ditetapkan (bukan ResizeToContents) agar tombol Edit/Hapus tidak kepotong scrollbar
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.resizeSection(5, 170)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background-color:{C.SURFACE}; border:1px solid {C.BORDER}; border-radius:10px; }}
            QHeaderView::section {{ background-color:{C.SURFACE_ALT}; color:{C.TEXT_MUTED_STRONG}; font-size:10px;
                                    font-weight:bold; border:none; border-bottom:1px solid {C.BORDER}; padding:10px; }}
            QTableWidget::item {{ border-bottom:1px solid {C.SURFACE_HOVER}; padding:6px; }}
            QScrollBar:vertical {{ background:{C.SURFACE_HOVER}; width:10px; margin:2px 2px 2px 0;
                                  border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{C.BORDER_STRONG}; border-radius:5px; min-height:28px; }}
            QScrollBar::handle:vertical:hover {{ background:{C.TEXT_FAINT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
        """)
        self.table.verticalHeader().setDefaultSectionSize(44)
        root.addWidget(self.table, 1)

    def _reload_data(self):
        from database import DB

        cur = self.filter_admin.currentData()
        self.filter_admin.blockSignals(True)
        self.filter_admin.clear()
        self.filter_admin.addItem("Semua Admin", "all")
        for a in DB.get_admin_aktif():
            self.filter_admin.addItem(a["nama"], a["nama"])
        idx = self.filter_admin.findData(cur)
        self.filter_admin.setCurrentIndex(idx if idx >= 0 else 0)
        self.filter_admin.blockSignals(False)

        filt = self.filter_admin.currentData() or "all"
        self._rows_cache = list(DB.get_kehadiran_admin(filt))
        self._render_table()

    def _render_table(self):
        rows = self._rows_cache
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["tanggal"] or "-"))
            self.table.setItem(i, 1, QTableWidgetItem(r["nama_admin"] or "-"))
            self.table.setItem(i, 2, QTableWidgetItem(r["jam_masuk"] or "—"))
            self.table.setItem(i, 3, QTableWidgetItem(r["jam_pulang"] or "—"))
            uang = r["uang_makan"] or 0
            self.table.setItem(i, 4, QTableWidgetItem(f"Rp {uang:,.0f}".replace(",", ".")))

            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(8, 0, 8, 0)
            wl.setSpacing(10)
            btn_edit = QPushButton("Edit")
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setFixedHeight(32)
            btn_edit.setMinimumWidth(64)
            btn_edit.setStyleSheet(action_button_style())
            btn_hapus = QPushButton("Hapus")
            btn_hapus.setCursor(Qt.PointingHandCursor)
            btn_hapus.setFixedHeight(32)
            btn_hapus.setMinimumWidth(64)
            btn_hapus.setStyleSheet(action_button_style("danger"))
            row_id = r["id"]
            btn_edit.clicked.connect(lambda _, rid=row_id: self._edit_absensi(rid))
            btn_hapus.clicked.connect(lambda _, rid=row_id: self._hapus_absensi(rid))
            wl.addWidget(btn_edit)
            wl.addWidget(btn_hapus)
            self.table.setCellWidget(i, 5, wrap)

        if not rows:
            self.table.setRowCount(1)
            empty = QTableWidgetItem("Belum ada riwayat kehadiran admin. Klik \"+ Tambah Absensi\" untuk mencatat.")
            empty.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 0, empty)
            self.table.setSpan(0, 0, 1, 6)

    def _tambah_absensi(self):
        from database import DB
        if not DB.get_admin_aktif():
            show_toast(self, "Perhatian", "Belum ada admin aktif. Tambahkan admin terlebih dahulu.", "warning")
            return
        dlg = FormAbsensiAdminDialog(self, existing=None, on_saved=self._reload_data)
        dlg.exec_()

    def _edit_absensi(self, kehadiran_id):
        from database import DB
        r = DB.get_kehadiran_admin_by_id(kehadiran_id)
        if not r:
            return
        dlg = FormAbsensiAdminDialog(self, existing=r, on_saved=self._reload_data)
        dlg.exec_()

    def _hapus_absensi(self, kehadiran_id):
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
            self._reload_data()
            show_toast(self, "Berhasil", "Data kehadiran admin dihapus.", "success")


# ── WIDGET UTAMA — 2 TAB (Absensi Murid / Absensi Admin) ────────
class AbsensiWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color:{C.SURFACE_ALT};")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(20)

        top = QHBoxLayout()
        title = QLabel("Melody Violin School Yogyakarta")
        title.setStyleSheet(f"font-size:17px;font-weight:500;color:{C.TEXT_PRIMARY};")
        top.addWidget(title)
        top.addStretch()
        root.addLayout(top)

        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(8)
        self.tab_btns = []
        tab_labels = ["Absensi Murid", "Absensi Admin"]

        for i, lbl in enumerate(tab_labels):
            btn = QPushButton(lbl)
            btn.setFixedHeight(40)
            btn.setFixedWidth(160)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._switch_tab(idx))
            self.tab_btns.append(btn)
            tab_bar.addWidget(btn)

        tab_bar.addStretch()
        root.addLayout(tab_bar)
        self._active_tab = 0
        self._apply_tab_styles()

        self.stack = QStackedWidget()
        self.stack.addWidget(AbsensiMuridWidget())
        self.stack.addWidget(AbsensiAdminWidget())
        root.addWidget(self.stack)

    def _switch_tab(self, idx):
        self._active_tab = idx
        self.stack.setCurrentIndex(idx)
        self._apply_tab_styles()
        w = self.stack.widget(idx)
        if hasattr(w, "_reload_data"):
            w._reload_data()

    def _apply_tab_styles(self):
        for i, btn in enumerate(self.tab_btns):
            if i == self._active_tab:
                btn.setStyleSheet(f"""
                    QPushButton {{ background-color:{C.TEXT_PRIMARY}; color:white; border:none;
                                  border-radius:8px; font-size:13px; font-weight:500; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{ background-color:white; color:{C.TEXT_BODY}; border:1px solid {C.BORDER};
                                  border-radius:8px; font-size:13px; font-weight:400; }}
                    QPushButton:hover {{ background-color:{C.SURFACE_ALT}; }}
                """)

    def showEvent(self, event):
        """Muat ulang data tab aktif setiap kali halaman Absensi dibuka."""
        super().showEvent(event)
        w = self.stack.currentWidget()
        if hasattr(w, "_reload_data"):
            w._reload_data()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar konsisten dengan main.py
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    w = AbsensiWidget()
    w.setWindowTitle("Absensi – Melody Violin School")
    w.resize(1200, 780)
    w.show()
    sys.exit(app.exec_())
