import os
import re
import sys

from PyQt5.QtCore import QObject, pyqtSignal, Qt, QByteArray
from PyQt5.QtGui import QKeySequence, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QShortcut, QComboBox


def resource_path(relative_path: str) -> str:
  ap ketemu baik saat development maupun setelah di-compile.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


# ── PALET WARNA (design tokens) ─────────────────────────────────
class C:
    ACCENT            = "#3B82F6"   # biru utama (aksi, highlight, link)
    ACCENT_DARK       = "#2563EB"   # biru lebih gelap (hover/teks di atas bg terang)
    ACCENT_DARKER     = "#1D4ED8"   # biru paling gelap (hover/pressed tombol accent)
    ACCENT_BG         = "#EFF6FF"   # latar biru sangat muda (badge/highlight ringan)
    ACCENT_BG_STRONG  = "#DBEAFE"   # latar biru muda, sedikit lebih pekat dari ACCENT_BG
    ACCENT_BORDER     = "#BFDBFE"   # garis biru muda (border kartu/badge accent)

    DANGER            = "#EF4444"   # merah (hapus, kredit/keluar uang)
    DANGER_DARK       = "#DC2626"   # merah lebih gelap (hover/pressed)
    DANGER_DARKER     = "#B91C1C"   # merah paling gelap (pressed/teks di atas bg terang)
    DANGER_BG         = "#FEF2F2"   # latar merah muda
    DANGER_BORDER     = "#FCA5A5"   # garis merah muda (border tombol/badge danger outline)

    SUCCESS           = "#22C55E"   # hijau (berhasil, debit/masuk uang)
    SUCCESS_HOVER     = "#16A34A"   # hijau lebih gelap (hover)
    SUCCESS_DARK      = "#15803D"   # hijau paling gelap (teks di atas bg hijau muda)
    SUCCESS_BG        = "#F0FDF4"   # latar hijau muda
    SUCCESS_BG_STRONG = "#DCFCE7"   # latar hijau muda, sedikit lebih pekat

    WARNING           = "#F59E0B"   # oranye (peringatan, konfirmasi)
    WARNING_DARK      = "#EA580C"   # oranye lebih gelap (hover/teks)
    WARNING_BG        = "#FFF7ED"   # latar oranye muda

    TEXT_PRIMARY      = "#1E293B"   # teks utama
    TEXT_PRIMARY_DARK = "#0F172A"   # teks/permukaan paling gelap (pressed state tombol gelap)
    TEXT_SECONDARY    = "#374151"   # teks sekunder yang lebih gelap dari TEXT_MUTED
    TEXT_BODY         = "#475569"   # teks isi/label (antara TEXT_PRIMARY & TEXT_MUTED)
    TEXT_MUTED        = "#64748B"   # teks sekunder
    TEXT_MUTED_STRONG = "#5B6B82"   # varian TEXT_MUTED dg kontras lebih tinggi (AA), utk ikon kecil
    TEXT_FAINT        = "#94A3B8"   # teks tersier/placeholder
    TEXT_DARKEST      = "#111827"   # teks paling gelap (judul besar)

    SURFACE           = "#FFFFFF"   # permukaan kartu/panel
    SURFACE_ALT       = "#F8FAFC"   # latar halaman
    SURFACE_SUBTLE    = "#F9FAFB"   # latar nyaris putih (mis. baris tabel selang-seling)
    SURFACE_HOVER     = "#F1F5F9"   # latar hover (item menu, baris tabel, dsb.)

    BORDER            = "#E2E8F0"   # garis pembatas
    BORDER_LIGHT      = "#D1D5DB"   # garis pembatas lebih terang/lembut
    BORDER_STRONG     = "#CBD5E1"   # garis pembatas lebih tegas


# ── STYLE SIDEBAR ───────────────────────────────────────────────
def sidebar_styles(accent: str = C.ACCENT, accent_bg: str = "#EEF2FF"):
    """
    Mengembalikan 4 string QSS: (SIDEBAR_STYLE, MENU_ACTIVE, MENU_NORMAL, LOGOUT_STYLE)

    Desain "pill" minimalis: item aktif punya latar rounded penuh (bukan
    cuma garis kiri), dengan sedikit inset margin dari tepi sidebar —
    meniru referensi desain (rounded rect biru muda, ikon+teks biru).
    """
    SIDEBAR_STYLE = f"""
        QFrame#sidebar {{
            background-color: {C.SURFACE};
            border-right: 1px solid {C.BORDER};
        }}
    """

    MENU_NORMAL = f"""
        QPushButton {{
            text-align: left;
            padding-left: 14px;
            margin: 3px 12px;
            border: none;
            border-radius: 10px;
            background-color: transparent;
            color: {C.TEXT_MUTED};
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: #F1F5F9;
            color: {C.TEXT_PRIMARY};
        }}
        QPushButton:focus {{
            outline: none;
            background-color: #F1F5F9;
        }}
    """

    MENU_ACTIVE = f"""
        QPushButton {{
            text-align: left;
            padding-left: 14px;
            margin: 3px 12px;
            border: none;
            border-radius: 10px;
            background-color: {accent_bg};
            color: {accent};
            font-size: 13px;
            font-weight: bold;
        }}
    """

    LOGOUT_STYLE = f"""
        QPushButton {{
            text-align: left;
            padding-left: 14px;
            margin: 3px 12px;
            border: none;
            border-radius: 10px;
            background-color: transparent;
            color: {C.DANGER};
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: #FEF2F2;
        }}
    """

    return SIDEBAR_STYLE, MENU_ACTIVE, MENU_NORMAL, LOGOUT_STYLE


# ── DROPDOWN (QComboBox) — gaya standar termasuk popup item view ───────────
def combo_box_style(radius: int = 10, height: int = 38, font_size: int = 13,
                     border: str = None) -> str:
    """QSS lengkap untuk QComboBox (border, focus, panah custom, & popup
    item list) — dipakai untuk dropdown filter di halaman-halaman list.
    Panggil dengan radius/height/font_size lebih kecil untuk combo box
    yang lebih ringkas (mis. di dalam form dialog)."""
    border = border or C.ACCENT_BORDER
    return f"""
        QComboBox {{
            border: 1.5px solid {border}; border-radius: {radius}px;
            background: white; padding: 0 14px;
            font-size: {font_size}px; color: {C.TEXT_PRIMARY};
        }}
        QComboBox:hover {{ border-color: {C.ACCENT}; background-color: {C.ACCENT_BG}; }}
        QComboBox:focus {{ border: 2px solid {C.ACCENT}; }}
        QComboBox::drop-down {{ border: none; width: 30px; }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {C.TEXT_MUTED};
            width: 0; height: 0; margin-right: 10px;
        }}
        QComboBox QAbstractItemView {{
            selection-background-color: {C.ACCENT}; selection-color: white;
        }}
        QComboBox QAbstractItemView::item {{ min-height: 30px; padding-left: 10px; border-radius: 4px; }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {C.ACCENT}; color: white;
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {C.ACCENT}; color: white;
        }}
    """


def _combo_popup_qss(radius: int = 10, font_size: int = 13, border: str = None) -> str:
    """QSS untuk popup list QComboBox, dipakai lewat style_combo() dan
    diterapkan LANGSUNG ke widget combo.view() (bukan cuma lewat selector
    turunan 'QComboBox QAbstractItemView' di style combo box induknya).
    Popup QComboBox adalah top-level window terpisah — di sebagian
    platform/tema OS, selector turunan itu tidak konsisten menempel ke
    popup ini sehingga style hover/selected item jadi tidak pernah
    kelihatan walau QSS-nya sendiri sudah benar. Styling langsung ke
    objek view menjamin style-nya selalu kepakai."""
    border = border or C.BORDER
    return f"""
        QListView {{
            border: 1px solid {border}; border-radius: 0px;
            background: white; padding: 4px; outline: none;
            font-size: {font_size}px; color: {C.TEXT_PRIMARY};
        }}
        QListView::item {{ min-height: 30px; padding-left: 10px; border-radius: 4px; }}
        QListView::item:hover {{ background-color: {C.ACCENT}; color: white; }}
        QListView::item:selected {{ background-color: {C.ACCENT}; color: white; }}
    """


def style_combo(combo: QComboBox, radius: int = 10, height: int = 38,
                 font_size: int = 13, border: str = None) -> None:
    """Cara STANDAR & satu-satunya yang seharusnya dipakai untuk men-style
    QComboBox filter di seluruh modul (gantikan pola lama
    `combo.setStyleSheet(combo_box_style(...))`). Selain men-style combo
    box-nya sendiri, fungsi ini juga men-style combo.view() secara
    langsung supaya highlight hover pada tiap item popup PASTI kelihatan
    ketika kursor lewat di atasnya, apa pun platform/tema OS yang dipakai."""
    combo.setStyleSheet(combo_box_style(radius=radius, height=height,
                                         font_size=font_size, border=border))
    combo.view().setStyleSheet(_combo_popup_qss(radius=radius, font_size=font_size, border=border))
    # Aktifkan mouseTracking di view() & viewport() agar hover popup konsisten
    combo.view().setMouseTracking(True)
    combo.view().viewport().setMouseTracking(True)


# ── TOMBOL AKSI TABEL — gaya standar Edit/Hapus/Lihat Detail (pill outline) ──
def action_button_style(kind: str = "accent") -> str:
    """kind: 'accent' (Edit/Lihat Detail — aksi netral) atau
    'danger' (Hapus — aksi destruktif)."""
    if kind == "danger":
        color, border, hover_bg, hover_border = C.DANGER_DARK, C.DANGER_BORDER, C.DANGER_BG, C.DANGER
    else:
        color, border, hover_bg, hover_border = C.ACCENT, C.ACCENT_BORDER, C.ACCENT_BG, C.ACCENT
    return f"""
        QPushButton {{
            background: white; color: {color};
            border: 1.5px solid {border};
            border-radius: 6px;
            font-size: 11px; font-weight: bold;
            padding: 0 14px;
        }}
        QPushButton:hover {{ background: {hover_bg}; border-color: {hover_border}; }}
    """


# ── TOMBOL "+ TAMBAH ..." — warna biru standar (ACCENT) di semua modul ──────
def primary_button_style() -> str:
    return f"""
        QPushButton {{
            background-color: {C.ACCENT}; color: white; border: none;
            border-radius: 8px; padding: 0 18px;
            font-size: 12px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {C.ACCENT_DARK}; }}
    """


# ── IKON SIDEBAR — outline/minimalis (Lucide), dirender dari SVG inline ─────
_ICON_SVGS = {
    "dashboard": (
        '<rect x="3" y="3" width="7" height="9" rx="1.5"/>'
        '<rect x="14" y="3" width="7" height="5" rx="1.5"/>'
        '<rect x="14" y="12" width="7" height="9" rx="1.5"/>'
        '<rect x="3" y="16" width="7" height="5" rx="1.5"/>'
    ),
    "murid": (
        '<path d="M2 9l10-5 10 5-10 5z"/>'
        '<path d="M6 11v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5"/>'
        '<path d="M22 9v6"/>'
    ),
    "guru": (
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2"/>'
        '<path d="m16 11 2 2 4-4"/>'
    ),
    "absensi": (
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>'
        '<path d="m9 16 2 2 4-4"/>'
    ),
    "pembayaran": (
        '<rect x="2" y="5" width="20" height="14" rx="2"/>'
        '<line x1="2" y1="10" x2="22" y2="10"/>'
    ),
    "laporan": (
        '<rect x="2" y="6" width="20" height="12" rx="2"/>'
        '<circle cx="12" cy="12" r="2"/>'
        '<path d="M6 12h.01"/><path d="M18 12h.01"/>'
    ),
    "admin": (
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2"/>'
    ),
    "pengaturan": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73'
        'l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73'
        'l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2'
        'v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73'
        'l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73'
        'l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "logout": (
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
        '<polyline points="16 17 21 12 16 7"/>'
        '<line x1="21" y1="12" x2="9" y2="12"/>'
    ),
    # ── Ikon umum non-sidebar (pengganti emoji ✓ ✕ 🕐 📅 📋 🔔 ♪) ──────
    "check": (
        '<polyline points="20 6 9 17 4 12"/>'
    ),
    "x": (
        '<line x1="18" y1="6" x2="6" y2="18"/>'
        '<line x1="6" y1="6" x2="18" y2="18"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="9"/>'
        '<polyline points="12 7 12 12 15.5 14"/>'
    ),
    "calendar-check": (
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>'
        '<path d="m9 16 2 2 4-4"/>'
    ),
    "copy": (
        '<rect x="9" y="9" width="12" height="12" rx="2"/>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
    ),
    "bell": (
        '<path d="M18 8a6 6 0 0 0-12 0c0 6-3 8-3 8h18s-3-2-3-8"/>'
        '<path d="M13.73 20a2 2 0 0 1-3.46 0"/>'
    ),
    "music": (
        '<path d="M9 18V5l11-2v13"/>'
        '<circle cx="6" cy="18" r="3"/>'
        '<circle cx="17" cy="16" r="3"/>'
    ),
    "search": (
        '<circle cx="11" cy="11" r="7"/>'
        '<line x1="21" y1="21" x2="16.65" y2="16.65"/>'
    ),
    "pencil": (
        '<path d="M12 20h9"/>'
        '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>'
    ),
    "trash": (
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
        '<path d="M10 11v6"/><path d="M14 11v6"/>'
        '<path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>'
    ),
    "plus": (
        '<line x1="12" y1="5" x2="12" y2="19"/>'
        '<line x1="5" y1="12" x2="19" y2="12"/>'
    ),
    "arrow-right": (
        '<line x1="5" y1="12" x2="19" y2="12"/>'
        '<polyline points="12 5 19 12 12 19"/>'
    ),
    "arrow-left": (
        '<line x1="19" y1="12" x2="5" y2="12"/>'
        '<polyline points="12 19 5 12 12 5"/>'
    ),
    "arrow-up": (
        '<line x1="12" y1="19" x2="12" y2="5"/>'
        '<polyline points="5 12 12 5 19 12"/>'
    ),
    "arrow-down": (
        '<line x1="12" y1="5" x2="12" y2="19"/>'
        '<polyline points="5 12 12 19 19 12"/>'
    ),
    "upload": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="17 8 12 3 7 8"/>'
        '<line x1="12" y1="3" x2="12" y2="15"/>'
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" y1="15" x2="12" y2="3"/>'
    ),
    "file-text": (
        '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="14" y2="17"/>'
    ),
    "paperclip": (
        '<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66'
        'l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>'
    ),
    "lock": (
        '<rect x="3" y="11" width="18" height="11" rx="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    "equals": (
        '<line x1="5" y1="9" x2="19" y2="9"/>'
        '<line x1="5" y1="15" x2="19" y2="15"/>'
    ),
    "refresh": (
        '<polyline points="23 4 23 10 17 10"/>'
        '<polyline points="1 20 1 14 7 14"/>'
        '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10"/>'
        '<path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14"/>'
    ),
    "more-vertical": (
        '<circle cx="12" cy="5" r="1"/>'
        '<circle cx="12" cy="12" r="1"/>'
        '<circle cx="12" cy="19" r="1"/>'
    ),
}


def _render_svg_icon(name: str, color: str, size: int = 20) -> QIcon:
    body = _ICON_SVGS.get(name, "")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def sidebar_icon(name: str, active: bool = False, size: int = 20,
                  muted_color: str = None, accent: str = None) -> QIcon:
    """Ikon outline minimalis untuk item sidebar — abu-abu saat non-aktif,
    biru (accent) saat aktif. `name` salah satu dari _ICON_SVGS."""
    muted_color = muted_color or C.TEXT_MUTED
    accent = accent or C.ACCENT
    return _render_svg_icon(name, accent if active else muted_color, size)


def svg_icon(name: str, color: str, size: int = 16) -> QIcon:
    """Ikon outline umum (dipakai di tombol/badge di luar sidebar —
    mis. tombol Hadir/Reschedule/Salin Pengingat di kartu Absensi),
    dalam warna & ukuran bebas. `name` salah satu dari _ICON_SVGS."""
    return _render_svg_icon(name, color, size)


def svg_pixmap(name: str, color: str, size: int = 16) -> QPixmap:
    """Sama seperti svg_icon tapi mengembalikan QPixmap — dipakai saat
    ikon perlu ditaruh di dalam QLabel (mis. badge status berbentuk
    QLabel+QLabel di dalam QFrame, bukan QPushButton)."""
    body = _ICON_SVGS.get(name, "")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.4" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


# ── PAGE HEADER (breadcrumb di topbar: "MELODY VIOLIN SCHOOL  ›  Dashboard") ────
class PageHeader(QWidget):
    def __init__(self, title: str, section: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)

        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {C.TEXT_PRIMARY}; letter-spacing: 0.5px;"
        )

        self._section_lbl = QLabel(section)
        self._section_lbl.setStyleSheet(
            f"font-size: 11px; color: {C.TEXT_MUTED};"
        )

        lay.addWidget(self._title_lbl)
        lay.addWidget(self._section_lbl)

        self._title = title
        self._section = section

    def set_page(self, title: str, section: str):
        """Perbarui judul & sub-bagian halaman (dipanggil saat pindah menu)."""
        self._title = title
        self._section = section
        self._title_lbl.setText(title.upper())
        self._section_lbl.setText(section)


# ── ACCESSIBILITY — Perbesar/perkecil ukuran teks (Ctrl +/-/0) ────
class TextScaleController(QObject):
    """
    Singleton global untuk skala ukuran teks seluruh aplikasi.
    factor 1.0 = ukuran normal, 1.1 = +10%, dst.
    """
    scaleChanged = pyqtSignal(float)

    _instance = None

    MIN_FACTOR = 0.85
    MAX_FACTOR = 1.4
    STEP = 0.1

    def __init__(self):
        super().__init__()
        self.factor = 1.0

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def increase(self):
        self.factor = round(min(self.MAX_FACTOR, self.factor + self.STEP), 2)
        self.scaleChanged.emit(self.factor)

    def decrease(self):
        self.factor = round(max(self.MIN_FACTOR, self.factor - self.STEP), 2)
        self.scaleChanged.emit(self.factor)

    def reset(self):
        self.factor = 1.0
        self.scaleChanged.emit(self.factor)


_FONT_SIZE_RE = re.compile(r"font-size:\s*(\d+(?:\.\d+)?)px")


def scale_stylesheet(qss: str, factor: float) -> str:
    """Kalikan semua nilai `font-size: Npx` di dalam string QSS dengan factor."""
    def _sub(m):
        px = float(m.group(1))
        return f"font-size: {round(px * factor)}px"
    return _FONT_SIZE_RE.sub(_sub, qss)


def install_text_scale_shortcuts(widget: QWidget):
    """Pasang shortcut Ctrl+= (perbesar), Ctrl+- (perkecil), Ctrl+0 (reset)."""
    ctrl = TextScaleController.instance()

    sc_plus = QShortcut(QKeySequence("Ctrl+="), widget)
    sc_plus.setContext(Qt.ApplicationShortcut)
    sc_plus.activated.connect(ctrl.increase)

    sc_minus = QShortcut(QKeySequence("Ctrl+-"), widget)
    sc_minus.setContext(Qt.ApplicationShortcut)
    sc_minus.activated.connect(ctrl.decrease)

    sc_reset = QShortcut(QKeySequence("Ctrl+0"), widget)
    sc_reset.setContext(Qt.ApplicationShortcut)
    sc_reset.activated.connect(ctrl.reset)
