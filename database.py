import sqlite3
import hashlib
import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional


def _get_persistent_data_dir() -> str:
    """
    Folder tempat mvs.db disimpan.

    PENTING (khusus hasil compile PyInstaller):
    - Saat dijalankan sebagai .exe/.app hasil PyInstaller, sys.frozen == True
      dan os.path.dirname(__file__) akan mengarah ke folder temporary
      (_MEIPASS) yang dihapus setiap aplikasi ditutup. Kalau mvs.db
      disimpan di sana, data akan hilang/reset tiap kali app dibuka ulang.
    - Jadi saat frozen, database disimpan di folder data aplikasi milik
      user (persisten), BUKAN di folder sementara tempat exe diekstrak.
    - Saat dijalankan sebagai script biasa (python main.py), tetap pakai
      folder project seperti sebelumnya supaya tidak mengubah perilaku
      development.
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support/MVS")
        elif sys.platform.startswith("win"):
            base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MVS")
        else:
            base = os.path.expanduser("~/.local/share/MVS")
        os.makedirs(base, exist_ok=True)
        return base
    return os.path.dirname(os.path.abspath(__file__))


DB_PATH = os.path.join(_get_persistent_data_dir(), "mvs.db")


#  KONEKSI

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # akses kolom by name
    conn.execute("PRAGMA foreign_keys = ON") # aktifkan FK enforcement
    return conn


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _parse_tgl_ddmmyyyy(tanggal_str: str) -> Optional[datetime]:
    """'DD-MM-YYYY' → datetime, atau None kalau tidak valid/kosong. Dipakai
    logika Batal/Reschedule khusus untuk menghitung pola hari & mencari
    tanggal sesi pengganti berikutnya."""
    if not tanggal_str:
        return None
    try:
        return datetime.strptime(tanggal_str, "%d-%m-%Y")
    except ValueError:
        return None


#  INISIALISASI SKEMA

_DDL = """
-- ─────────────────────────────────────────────
--  1. USERS  (login: admin & owner)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password      TEXT    NOT NULL,
    password_plain TEXT,                  -- simpan plain text utk ditampilkan di form Edit Owner
    display_name  TEXT    DEFAULT 'Admin',
    role          TEXT    DEFAULT 'admin'   -- 'admin' | 'owner'
);

-- ─────────────────────────────────────────────
--  2. ADMIN  (staf operasional)
--     FK → users(id) agar bisa login
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admin (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    nama       TEXT    NOT NULL,
    email      TEXT,
    no_hp      TEXT,
    alamat     TEXT,
    status     TEXT    DEFAULT 'Aktif'     -- 'Aktif' | 'Nonaktif'
);

-- ─────────────────────────────────────────────
--  3. GURU  (instruktur)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guru (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kode        TEXT    UNIQUE,             -- mis. TCH-001
    nama        TEXT    NOT NULL,
    email       TEXT,
    jenis_kel   TEXT,                       -- 'L' | 'P'
    keahlian    TEXT,                       -- 'Violin', 'Piano', dst.
    no_hp       TEXT,
    jadwal_hari TEXT,                       -- 'Sen, Rab, Jum'
    metode      TEXT    DEFAULT 'Offline',  -- 'Offline'|'Online'|'Keduanya'
    status      TEXT    DEFAULT 'Aktif',    -- 'Aktif' | 'Cuti' | 'Nonaktif'
    alamat      TEXT,
    gaji_per_sesi INTEGER DEFAULT 0
);

-- ─────────────────────────────────────────────
--  4. MURID
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS murid (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    no_pendaft  TEXT    UNIQUE,             -- mis. MV-2024-001
    nama        TEXT    NOT NULL,
    jenis_kel   TEXT,
    usia        INTEGER,
    no_hp       TEXT,
    alamat      TEXT,
    wali        TEXT,                       -- Nama Wali (Ayah/Ibu/Wali)
    tgl_masuk   TEXT,                       -- 'YYYY-MM-DD'
    status      TEXT    DEFAULT 'Aktif'     -- 'Aktif' | 'Nonaktif'
);

-- ─────────────────────────────────────────────
--  5. KURSUS  (jenis les yang tersedia)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kursus (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nama        TEXT    UNIQUE NOT NULL    -- 'Violin', 'Piano', dst.
);

-- ─────────────────────────────────────────────
--  6. PENDAFTARAN_KURSUS
--     Murid bisa daftar lebih dari satu kursus
--     FK → murid + kursus + guru
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pendaftaran_kursus (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    murid_id          INTEGER NOT NULL REFERENCES murid(id)  ON DELETE CASCADE,
    kursus_id         INTEGER NOT NULL REFERENCES kursus(id) ON DELETE RESTRICT,
    guru_id           INTEGER          REFERENCES guru(id)   ON DELETE SET NULL,
    tgl_mulai         TEXT,                       -- 'YYYY-MM-DD'
    status            TEXT    DEFAULT 'Aktif',    -- 'Aktif' | 'Selesai' | 'Berhenti'
    jumlah_sesi_paket INTEGER DEFAULT 0           -- total sesi yang didaftarkan (0 = tak terbatas/lama)
);

-- ─────────────────────────────────────────────
--  7. JADWAL_SESI
--     Setiap sesi kursus yang dijadwalkan
--     FK → pendaftaran_kursus + guru
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jadwal_sesi (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pendaftaran_id  INTEGER NOT NULL REFERENCES pendaftaran_kursus(id) ON DELETE CASCADE,
    guru_id         INTEGER          REFERENCES guru(id)  ON DELETE SET NULL,
    no_sesi         INTEGER DEFAULT 1,
    tanggal         TEXT    NOT NULL,       -- 'DD-MM-YYYY'
    jam_mulai       TEXT,                   -- 'HH:MM'
    jam_selesai     TEXT,
    metode          TEXT    DEFAULT 'Offline',
    status          TEXT    DEFAULT 'Pending',
    -- 'Pending' | 'Terlaksana' | 'Batal' | 'Reschedule'
    tipe_sesi       TEXT    DEFAULT 'Reguler',
    -- 'Reguler'   = mengikuti pola jadwal rutin (Senin/Rabu, dst) — dipakai
    --               untuk menghitung "Hari Les" & sebagai patokan hari saat
    --               membuat sesi pengganti otomatis (lihat batalkan_sesi).
    -- 'Reschedule'= sesi pengganti hasil Reschedule KHUSUS (di luar pola
    --               rutin, mis. sekali pindah ke Kamis) — TIDAK ikut
    --               dihitung sebagai bagian dari pola hari rutin.
    sesi_asal_id    INTEGER
    -- id sesi yang digantikan (Batal atau Reschedule) — dipakai Undo Batal
    -- untuk tahu sesi pengganti mana yang harus dihapus. NULL untuk sesi
    -- yang dibuat langsung dari jadwal awal (bukan pengganti apa pun).
);

-- ─────────────────────────────────────────────
--  8. PEMBAYARAN_MURID  (SPP / bayar kursus)
--     FK → murid + pendaftaran_kursus
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pembayaran_murid (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    murid_id        INTEGER NOT NULL REFERENCES murid(id) ON DELETE CASCADE,
    pendaftaran_id  INTEGER          REFERENCES pendaftaran_kursus(id) ON DELETE SET NULL,
    tanggal         TEXT    NOT NULL,
    keterangan      TEXT,
    nominal         INTEGER NOT NULL,
    status          TEXT    DEFAULT 'Lunas' -- 'Lunas' | 'Belum Lunas'
);

-- ─────────────────────────────────────────────
--  8b. PEMBAYARAN_SESI_MURID
--      Rincian pembayaran per jadwal: berapa sesi,
--      les apa, guru siapa, metode (home visit / offline / online),
--      biaya les + biaya transport (home visit).
--      FK → pembayaran_murid + jadwal_sesi (opsional)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pembayaran_sesi_murid (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pembayaran_id   INTEGER NOT NULL REFERENCES pembayaran_murid(id) ON DELETE CASCADE,
    murid_id        INTEGER NOT NULL REFERENCES murid(id) ON DELETE CASCADE,
    guru_id         INTEGER          REFERENCES guru(id)  ON DELETE SET NULL,
    kursus_id       INTEGER          REFERENCES kursus(id) ON DELETE SET NULL,
    tanggal_bayar   TEXT    NOT NULL,           -- 'DD-MM-YYYY'
    jumlah_sesi     INTEGER NOT NULL DEFAULT 1,
    metode          TEXT    DEFAULT 'Offline',  -- 'Offline'|'Online'|'Home Visit'
    biaya_les       INTEGER DEFAULT 0,          -- total biaya les  (gaji_guru × jumlah_sesi)
    biaya_transport INTEGER DEFAULT 0,          -- total transport  (transport_guru × jumlah_sesi)
    total_bayar     INTEGER DEFAULT 0,          -- biaya_les + biaya_transport
    catatan         TEXT    DEFAULT '',
    status          TEXT    DEFAULT 'Lunas'     -- 'Lunas' | 'Belum Lunas'
);

-- ─────────────────────────────────────────────
--  9. KEHADIRAN_ADMIN
--     FK → admin
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kehadiran_admin (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id    INTEGER NOT NULL REFERENCES admin(id) ON DELETE CASCADE,
    tanggal     TEXT    NOT NULL,           -- 'DD-MM-YYYY'
    jam_masuk   TEXT,
    jam_pulang  TEXT,
    uang_makan  INTEGER DEFAULT 0           -- 0 atau nominal
);

-- ─────────────────────────────────────────────
--  10. GAJI_GURU
--      Slip gaji per guru per periode
--      FK → guru
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gaji_guru (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guru_id         INTEGER NOT NULL REFERENCES guru(id) ON DELETE CASCADE,
    periode         TEXT    NOT NULL,       -- 'Februari 2026'
    jumlah_sesi     INTEGER DEFAULT 0,
    nominal_total   INTEGER DEFAULT 0,
    tanggal_bayar   TEXT,
    no_referensi    TEXT,
    status          TEXT    DEFAULT 'Belum Dibayar'
    -- 'Belum Dibayar' | 'Sudah Dibayar'
);

-- ─────────────────────────────────────────────
--  11. GAJI_ADMIN
--      Slip gaji per admin per periode
--      FK → admin
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gaji_admin (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id        INTEGER NOT NULL REFERENCES admin(id) ON DELETE CASCADE,
    periode         TEXT    NOT NULL,
    hari_kerja      INTEGER DEFAULT 0,
    gaji_harian     INTEGER DEFAULT 25000,
    uang_makan      INTEGER DEFAULT 0,
    nominal_total   INTEGER DEFAULT 0,
    tanggal_bayar   TEXT,
    no_referensi    TEXT,
    status          TEXT    DEFAULT 'Belum Dibayar'
);

-- ─────────────────────────────────────────────
--  12. PENGATURAN_GAJI  (tarif gaji dari halaman Pengaturan)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pengaturan_gaji (
    id              INTEGER PRIMARY KEY CHECK (id = 1),  -- hanya 1 baris
    gaji_admin      INTEGER DEFAULT 25000,   -- per kehadiran
    uang_makan_admin INTEGER DEFAULT 12000,  -- per kehadiran
    gaji_guru       INTEGER DEFAULT 40000,   -- per sesi, Offline (Sanggar)
    gaji_guru_visit_online INTEGER DEFAULT 35000, -- DEPRECATED: dulu gabungan Home Visit & Online,
                                                    -- dipertahankan utk kompatibilitas data lama
    transport_guru  INTEGER DEFAULT 0,       -- auto / home visit
    gaji_guru_online      INTEGER DEFAULT 35000, -- per sesi, Online
    gaji_guru_home_visit  INTEGER DEFAULT 35000, -- per sesi, Home Visit (belum termasuk transport)
    durasi_online      INTEGER DEFAULT 30,   -- menit per sesi, Online
    durasi_offline     INTEGER DEFAULT 45,   -- menit per sesi, Offline / Sanggar
    durasi_home_visit  INTEGER DEFAULT 45    -- menit per sesi, Home Visit
);

-- ─────────────────────────────────────────────
--  13. TRANSAKSI_KEUANGAN  (buku kas umum)
--      Debit = pemasukan, Kredit = pengeluaran
--      FK → admin (yang mencatat)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transaksi_keuangan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal     TEXT    NOT NULL,           -- 'DD/MM/YYYY'
    jenis       TEXT    NOT NULL,           -- 'Debit' | 'Kredit'
    keterangan  TEXT    NOT NULL,
    nominal     INTEGER NOT NULL,
    bukti_path  TEXT    DEFAULT '',
    admin_id    INTEGER REFERENCES admin(id) ON DELETE SET NULL,
    created_at  TEXT    DEFAULT (datetime('now','localtime'))
);
"""


#  DATA AWAL (SEED)

def _seed(conn: sqlite3.Connection):
    cur = conn.cursor()

    # ── Pengaturan Gaji (default) ──────────────────────────────
    cur.execute("SELECT id FROM pengaturan_gaji WHERE id=1")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO pengaturan_gaji
                (id,gaji_admin,uang_makan_admin,gaji_guru,gaji_guru_visit_online,
                 transport_guru,gaji_guru_online,gaji_guru_home_visit,
                 durasi_online,durasi_offline,durasi_home_visit)
            VALUES(1,25000,12000,40000,35000,0,35000,35000,30,45,45)
        """)

    # ── Users ──────────────────────────────────────────────────
    for uname, pw, dname, role in [
        ("admin", "1", "Admin Utama", "admin"),
        ("owner", "1", "Owner MVS",   "owner"),
    ]:
        cur.execute("SELECT id, password_plain FROM users WHERE username=?", (uname,))
        existing = cur.fetchone()
        if not existing:
            cur.execute(
                "INSERT INTO users(username,password,password_plain,display_name,role) VALUES(?,?,?,?,?)",
                (uname, _hash(pw), pw, dname, role)
            )
        elif existing["password_plain"] is None:
            # DB lama (sebelum kolom password_plain ada) -> backfill nilai default
            cur.execute("UPDATE users SET password_plain=? WHERE id=?", (pw, existing["id"]))

    # ── Kursus ─────────────────────────────────────────────────
    # Hanya 5 kursus yang tersedia di lapangan
    for nama in ("Biola", "Piano", "Vocal", "Drum", "Gitar"):
        cur.execute("INSERT OR IGNORE INTO kursus(nama) VALUES(?)", (nama,))

    # ── Guru ───────────────────────────────────────────────────
    guru_seed = [
        # kode, nama, jk, keahlian, no_hp, email, hari, metode, status, gaji
        # Biola
        ("TCH-001", "Ms. Fu",     "P", "Biola",            "0812-9034-1256", "ms.fu@mvs.edu",     "Sen-Sab", "Offline",  "Aktif", 150_000),
        ("TCH-002", "Ms. Fabhie", "P", "Biola",            "0813-2245-7890", "ms.fabhie@mvs.edu", "Sen-Sab", "Offline",  "Aktif", 150_000),
        ("TCH-003", "Ms. Shelma", "P", "Biola",            "0857-6612-3345", "ms.shelma@mvs.edu", "Sen-Sab", "Offline",  "Aktif", 150_000),
        ("TCH-004", "Ms. Nida",   "P", "Biola",            "0878-4432-9981", "ms.nida@mvs.edu",   "Sen-Sab", "Online",   "Aktif", 150_000),
        ("TCH-005", "Ms. Elisa",  "P", "Biola, Piano, Vocal", "0812-5567-2234", "ms.elisa@mvs.edu", "Sen-Sab", "Keduanya","Aktif", 150_000),
        # Piano
        ("TCH-006", "Ms. Happy",  "P", "Piano",            "0821-3345-6678", "ms.happy@mvs.edu",  "Sen-Sab", "Offline",  "Aktif", 150_000),
        ("TCH-007", "Ms. Febe",   "P", "Piano, Vocal",     "0813-9987-1123", "ms.febe@mvs.edu",   "Sen-Sab", "Offline",  "Aktif", 150_000),
        # Vocal
        ("TCH-008", "Ms. Ida",    "P", "Vocal",            "0895-3421-7765", "ms.ida@mvs.edu",    "Sen-Sab", "Online",   "Aktif", 150_000),
        # Drum & Gitar
        ("TCH-009", "Mr. Hany",   "L", "Drum, Gitar",      "0812-7789-4432", "mr.hany@mvs.edu",   "Sen-Sab", "Offline",  "Aktif", 150_000),
        ("TCH-010", "Mr. Fathur", "L", "Drum",             "0857-1123-6690", "mr.fathur@mvs.edu", "Sen-Sab", "Offline",  "Aktif", 150_000),
        ("TCH-011", "Mr. Riko",   "L", "Gitar",            "0813-4456-8821", "mr.riko@mvs.edu",   "Sen-Sab", "Offline",  "Aktif", 150_000),
    ]
    for kode, nama, jk, keahlian, hp, email, hari, metode, status, gaji in guru_seed:
        cur.execute("SELECT id FROM guru WHERE kode=?", (kode,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO guru(kode,nama,jenis_kel,keahlian,no_hp,email,jadwal_hari,
                                 metode,status,gaji_per_sesi)
                VALUES(?,?,?,?,?,?,?,?,?,?)
            """, (kode, nama, jk, keahlian, hp, email, hari, metode, status, gaji))

    # Admin, Murid, Jadwal, Transaksi, dan Kehadiran dikelola lewat UI.

    conn.commit()


#  FUNGSI INISIALISASI UTAMA

def init_db():
    """Buat semua tabel dan isi data awal. Aman dipanggil berulang kali."""
    conn = get_conn()
    conn.executescript(_DDL)
    conn.commit()

    # Migrasi: tambahkan kolom password_plain jika DB lama belum punya kolom ini
    try:
        conn.execute("ALTER TABLE users ADD COLUMN password_plain TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # kolom sudah ada

    # Migrasi: hapus tabel kursus lama (ada tarif_sesi/deskripsi), buat ulang bersih
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(kursus)").fetchall()]
        if "tarif_sesi" in cols or "deskripsi" in cols:
            conn.execute("DROP TABLE kursus")
            conn.commit()
            conn.executescript("CREATE TABLE IF NOT EXISTS kursus (id INTEGER PRIMARY KEY AUTOINCREMENT, nama TEXT UNIQUE NOT NULL);")
            conn.commit()
    except Exception:
        pass

    # Migrasi: tambahkan kolom gaji_guru_visit_online jika DB lama belum punya kolom ini
    # (tarif gaji guru khusus utk Home Visit & Online, terpisah dari tarif Sanggar)
    try:
        conn.execute(
            "ALTER TABLE pengaturan_gaji ADD COLUMN gaji_guru_visit_online INTEGER DEFAULT 35000")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # kolom sudah ada

    # Migrasi: pecah gaji_guru_visit_online jadi gaji_guru_online & gaji_guru_home_visit, seed dari nilai lama
    for _col in ("gaji_guru_online", "gaji_guru_home_visit"):
        try:
            conn.execute(
                f"ALTER TABLE pengaturan_gaji ADD COLUMN {_col} INTEGER DEFAULT 35000")
            conn.commit()
            conn.execute(f"""
                UPDATE pengaturan_gaji
                SET {_col} = COALESCE(gaji_guru_visit_online, 35000)
                WHERE id = 1
            """)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # kolom sudah ada

    # Migrasi: tambahkan kolom durasi sesi per metode (Online 30 menit, Offline/Home Visit 45 menit)
    for _col, _default in (
        ("durasi_online", 30),
        ("durasi_offline", 45),
        ("durasi_home_visit", 45),
    ):
        try:
            conn.execute(
                f"ALTER TABLE pengaturan_gaji ADD COLUMN {_col} INTEGER DEFAULT {_default}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # kolom sudah ada

    # Migrasi: kolom tipe_sesi & sesi_asal_id (dipakai batalkan_sesi/reschedule_khusus_sesi/undo_batal_sesi)
    try:
        conn.execute("ALTER TABLE jadwal_sesi ADD COLUMN tipe_sesi TEXT DEFAULT 'Reguler'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # kolom sudah ada
    try:
        conn.execute("ALTER TABLE jadwal_sesi ADD COLUMN sesi_asal_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # kolom sudah ada

    # Migrasi: kolom nama_ortu -> wali (mengganti istilah "Nama Orang Tua" jadi "Wali")
    try:
        cols_murid = [r[1] for r in conn.execute("PRAGMA table_info(murid)").fetchall()]
        if "wali" not in cols_murid:
            if "nama_ortu" in cols_murid:
                conn.execute("ALTER TABLE murid RENAME COLUMN nama_ortu TO wali")
            else:
                conn.execute("ALTER TABLE murid ADD COLUMN wali TEXT")
            conn.commit()
    except sqlite3.OperationalError:
        pass  # kolom sudah sesuai

    _seed(conn)
    conn.close()

    # Sinkronkan paket/murid yang sudah selesai tapi belum ter-tandai (untuk DB lama)
    DB.sinkronkan_paket_selesai()

    # Bersihkan transaksi_keuangan duplikat (bug lama: penulisan langsung
    # les/pendaftaran ID-nya beda dgn hasil tarik _sinkron_db, sehingga
    # sempat tercatat dobel). Aman dijalankan berkali-kali (idempotent).
    _bersihkan_duplikat_transaksi()


def _bersihkan_duplikat_transaksi():
    """Hapus baris transaksi_keuangan duplikat: sama tanggal, jenis, nominal,
    dan sama isi keterangan sebelum "| ID:" (nomor ID boleh beda — itu
    penyebab dobelnya). Baris dengan id terkecil (paling lama) dipertahankan."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, tanggal, jenis, keterangan, nominal FROM transaksi_keuangan "
            "WHERE keterangan LIKE '%| ID:%' ORDER BY id"
        ).fetchall()
        seen = {}
        hapus_ids = []
        for r in rows:
            prefix = r["keterangan"].split("| ID:")[0]
            key = (r["tanggal"], r["jenis"], prefix, r["nominal"])
            if key in seen:
                hapus_ids.append(r["id"])
            else:
                seen[key] = r["id"]
        if hapus_ids:
            conn.executemany(
                "DELETE FROM transaksi_keuangan WHERE id=?",
                [(i,) for i in hapus_ids]
            )
            conn.commit()
    except sqlite3.OperationalError:
        pass  # tabel belum ada (DB baru)
    finally:
        conn.close()


#  DATABASE HELPER CLASS (singleton)

class _Database:
    """Singleton helper untuk query umum ke SQLite."""

    def fetch_all(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        conn = get_conn()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        conn = get_conn()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Jalankan INSERT/UPDATE/DELETE. Return lastrowid."""
        conn = get_conn()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def executemany(self, sql: str, params_list: List[tuple]) -> None:
        conn = get_conn()
        try:
            conn.executemany(sql, params_list)
            conn.commit()
        finally:
            conn.close()

    # ── Shortcut queries yang sering dipakai ──────────────────

    def get_pengaturan_gaji(self) -> dict:
        """Ambil tarif gaji dari tabel pengaturan_gaji. Return dict dengan semua field tarif."""
        row = self.fetch_one("SELECT * FROM pengaturan_gaji WHERE id=1")
        if row:
            d = dict(row)
            # Jaga-jaga jika kolom baru belum ter-migrasi di baris lama
            if d.get("gaji_guru_visit_online") is None:
                d["gaji_guru_visit_online"] = 35000
            if d.get("gaji_guru_online") is None:
                d["gaji_guru_online"] = d["gaji_guru_visit_online"]
            if d.get("gaji_guru_home_visit") is None:
                d["gaji_guru_home_visit"] = d["gaji_guru_visit_online"]
            if d.get("durasi_online") is None:
                d["durasi_online"] = 30
            if d.get("durasi_offline") is None:
                d["durasi_offline"] = 45
            if d.get("durasi_home_visit") is None:
                d["durasi_home_visit"] = 45
            return d
        # fallback default jika tabel belum ter-seed
        return {
            "gaji_admin": 25000,
            "uang_makan_admin": 12000,
            "gaji_guru": 40000,
            "gaji_guru_online": 35000,
            "gaji_guru_home_visit": 35000,
            "gaji_guru_visit_online": 35000,
            "transport_guru": 0,
            "durasi_online": 30,
            "durasi_offline": 45,
            "durasi_home_visit": 45,
        }

    def set_pengaturan_gaji(self,
                            gaji_admin: int,
                            uang_makan_admin: int,
                            gaji_guru: int,
                            gaji_guru_visit_online: int,
                            transport_guru: int = 0,
                            gaji_guru_online: int = None,
                            gaji_guru_home_visit: int = None,
                            durasi_online: int = None,
                            durasi_offline: int = None,
                            durasi_home_visit: int = None) -> None:
        """Simpan / update tarif gaji. Parameter opsional di-fallback ke nilai sebelumnya."""
        if gaji_guru_online is None:
            gaji_guru_online = gaji_guru_visit_online
        if gaji_guru_home_visit is None:
            gaji_guru_home_visit = gaji_guru_visit_online
        if durasi_online is None:
            durasi_online = 30
        if durasi_offline is None:
            durasi_offline = 45
        if durasi_home_visit is None:
            durasi_home_visit = 45
        self.execute("""
            INSERT INTO pengaturan_gaji
                (id, gaji_admin, uang_makan_admin, gaji_guru, gaji_guru_visit_online,
                 transport_guru, gaji_guru_online, gaji_guru_home_visit,
                 durasi_online, durasi_offline, durasi_home_visit)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                gaji_admin             = excluded.gaji_admin,
                uang_makan_admin       = excluded.uang_makan_admin,
                gaji_guru              = excluded.gaji_guru,
                gaji_guru_visit_online = excluded.gaji_guru_visit_online,
                transport_guru         = excluded.transport_guru,
                gaji_guru_online       = excluded.gaji_guru_online,
                gaji_guru_home_visit   = excluded.gaji_guru_home_visit,
                durasi_online          = excluded.durasi_online,
                durasi_offline         = excluded.durasi_offline,
                durasi_home_visit      = excluded.durasi_home_visit
        """, (gaji_admin, uang_makan_admin, gaji_guru, gaji_guru_visit_online,
              transport_guru, gaji_guru_online, gaji_guru_home_visit,
              durasi_online, durasi_offline, durasi_home_visit))

    def get_durasi_sesi(self) -> dict:
        """Durasi sesi (menit) per metode: {"Offline": .., "Online": .., "Home Visit": ..}."""
        cfg = self.get_pengaturan_gaji()
        return {
            "Offline":    cfg.get("durasi_offline", 45),
            "Online":     cfg.get("durasi_online", 30),
            "Home Visit": cfg.get("durasi_home_visit", 45),
        }

    def get_pembayaran_murid(self, murid_id: int = None) -> List[sqlite3.Row]:
        """Ambil pembayaran sesi murid. Filter per murid_id jika diberikan."""
        where = "WHERE psm.murid_id = ?" if murid_id else ""
        params = (murid_id,) if murid_id else ()
        return self.fetch_all(f"""
            SELECT
                psm.id,
                psm.tanggal_bayar,
                psm.jumlah_sesi,
                psm.metode,
                psm.biaya_les,
                psm.biaya_transport,
                psm.total_bayar,
                psm.status,
                psm.catatan,
                m.nama      AS nama_murid,
                m.no_pendaft,
                g.nama      AS nama_guru,
                k.nama      AS nama_kursus
            FROM pembayaran_sesi_murid psm
            JOIN murid  m ON m.id = psm.murid_id
            LEFT JOIN guru   g ON g.id  = psm.guru_id
            LEFT JOIN kursus k ON k.id  = psm.kursus_id
            {where}
            ORDER BY psm.tanggal_bayar DESC, psm.id DESC
        """, params)

    def get_murid_aktif(self) -> List[sqlite3.Row]:
        return self.fetch_all("SELECT * FROM murid WHERE status='Aktif' ORDER BY nama")

    def get_guru_aktif(self) -> List[sqlite3.Row]:
        return self.fetch_all("SELECT * FROM guru WHERE status='Aktif' ORDER BY nama")

    def get_password_plain(self, user_id: int) -> str:
        """Ambil password plain dari tabel users berdasarkan user_id."""
        row = self.fetch_one(
            "SELECT password_plain FROM users WHERE id=?", (user_id,)
        )
        return row["password_plain"] if row and row["password_plain"] else ""

    def update_admin_password(self, admin_id: int, pw_plain: str) -> bool:
        """
        Update password admin via relasi admin.user_id → users.
        Return True jika berhasil, False jika admin belum punya akun login (user_id NULL).
        """
        row = self.fetch_one("SELECT user_id FROM admin WHERE id=?", (admin_id,))
        if not row or not row["user_id"]:
            return False
        self.execute(
            "UPDATE users SET password=?, password_plain=? WHERE id=?",
            (_hash(pw_plain), pw_plain, row["user_id"])
        )
        return True

    def get_admin_by_user_id(self, user_id: int) -> Optional[sqlite3.Row]:
        """Cari baris admin berdasarkan user_id (relasi users.id = admin.user_id)."""
        return self.fetch_one("SELECT * FROM admin WHERE user_id=?", (user_id,))

    def catat_login_admin(self, admin_id: int, tanggal: str, jam: str) -> None:
        """Catat jam_masuk. Tidak menimpa jika sudah ada (login pertama tetap tercatat)."""
        row = self.fetch_one(
            "SELECT id, jam_masuk FROM kehadiran_admin WHERE admin_id=? AND tanggal=?",
            (admin_id, tanggal)
        )
        if row:
            if not row["jam_masuk"]:
                self.execute(
                    "UPDATE kehadiran_admin SET jam_masuk=? WHERE id=?",
                    (jam, row["id"])
                )
        else:
            self.execute(
                "INSERT INTO kehadiran_admin (admin_id, tanggal, jam_masuk, jam_pulang, uang_makan) "
                "VALUES (?, ?, ?, NULL, 0)",
                (admin_id, tanggal, jam)
            )

    def catat_logout_admin(self, admin_id: int, tanggal: str, jam: str) -> None:
        """Catat jam_pulang (selalu ditimpa dengan waktu logout terakhir)."""
        row = self.fetch_one(
            "SELECT id FROM kehadiran_admin WHERE admin_id=? AND tanggal=?",
            (admin_id, tanggal)
        )
        if row:
            self.execute(
                "UPDATE kehadiran_admin SET jam_pulang=? WHERE id=?",
                (jam, row["id"])
            )
        else:
            # Logout tanpa ada baris login (kasus jarang) — tetap simpan
            self.execute(
                "INSERT INTO kehadiran_admin (admin_id, tanggal, jam_masuk, jam_pulang, uang_makan) "
                "VALUES (?, ?, NULL, ?, 0)",
                (admin_id, tanggal, jam)
            )

    def simpan_kehadiran_admin_manual(self, admin_id: int, tanggal: str, jam_masuk: str,
                                       jam_pulang: str, uang_makan: int = 0,
                                       kehadiran_id: Optional[int] = None) -> int:
        """
        Simpan input MANUAL kehadiran admin (diketik sendiri oleh admin/owner
        lewat tab Absensi Admin), bukan hasil catat otomatis saat login/logout.
        - kehadiran_id kosong  -> INSERT baris baru.
        - kehadiran_id diisi   -> UPDATE baris yang sudah ada (mode edit).
        Return: id baris kehadiran_admin yang tersimpan.
        """
        jam_masuk_val  = jam_masuk.strip() if jam_masuk and jam_masuk.strip() else None
        jam_pulang_val = jam_pulang.strip() if jam_pulang and jam_pulang.strip() else None
        if kehadiran_id:
            self.execute(
                "UPDATE kehadiran_admin SET admin_id=?, tanggal=?, jam_masuk=?, jam_pulang=?, uang_makan=? "
                "WHERE id=?",
                (admin_id, tanggal, jam_masuk_val, jam_pulang_val, uang_makan, kehadiran_id)
            )
            return kehadiran_id
        return self.execute(
            "INSERT INTO kehadiran_admin (admin_id, tanggal, jam_masuk, jam_pulang, uang_makan) "
            "VALUES (?, ?, ?, ?, ?)",
            (admin_id, tanggal, jam_masuk_val, jam_pulang_val, uang_makan)
        )

    def hapus_kehadiran_admin(self, kehadiran_id: int) -> None:
        """Hapus satu baris riwayat kehadiran admin (input manual)."""
        self.execute("DELETE FROM kehadiran_admin WHERE id=?", (kehadiran_id,))

    def get_kehadiran_admin_by_id(self, kehadiran_id: int) -> Optional[sqlite3.Row]:
        """Ambil satu baris kehadiran_admin (dipakai saat membuka form edit)."""
        return self.fetch_one("""
            SELECT ka.*, a.nama AS nama_admin
            FROM kehadiran_admin ka
            JOIN admin a ON a.id = ka.admin_id
            WHERE ka.id = ?
        """, (kehadiran_id,))

    def get_kehadiran_admin(self, admin_filter: str = "all") -> List[sqlite3.Row]:
        """Ambil riwayat kehadiran. admin_filter: 'all' atau nama admin."""
        # Migration-safe: pastikan kolom status_gaji ada
        try:
            self.execute("ALTER TABLE kehadiran_admin ADD COLUMN status_gaji TEXT DEFAULT 'Pending'")
        except Exception:
            pass

        where = ""
        params: tuple = ()
        if admin_filter != "all":
            where = "WHERE a.nama = ?"
            params = (admin_filter,)
        return self.fetch_all(f"""
            SELECT
                ka.id, ka.tanggal, ka.jam_masuk, ka.jam_pulang, ka.uang_makan,
                COALESCE(ka.status_gaji, 'Pending') AS status_gaji,
                a.nama AS nama_admin
            FROM kehadiran_admin ka
            JOIN admin a ON a.id = ka.admin_id
            {where}
            ORDER BY ka.tanggal DESC, ka.id DESC
        """, params)

    def get_jadwal_hari_ini(self, tanggal: str) -> List[sqlite3.Row]:
        """tanggal format: 'DD-MM-YYYY'"""
        return self.fetch_all("""
            SELECT js.*, m.nama AS nama_murid, g.nama AS nama_guru,
                   k.nama AS nama_kursus
            FROM jadwal_sesi js
            JOIN pendaftaran_kursus pk ON pk.id = js.pendaftaran_id
            JOIN murid  m ON m.id = pk.murid_id
            JOIN kursus k ON k.id = pk.kursus_id
            LEFT JOIN guru g ON g.id  = js.guru_id
            WHERE js.tanggal = ?
            ORDER BY js.jam_mulai
        """, (tanggal,))

    def get_sesi_murid(self, murid_id: int) -> List[sqlite3.Row]:
        return self.fetch_all("""
            SELECT js.*, k.nama AS nama_kursus, g.nama AS nama_guru
            FROM jadwal_sesi js
            JOIN pendaftaran_kursus pk ON pk.id = js.pendaftaran_id
            JOIN kursus k ON k.id = pk.kursus_id
            LEFT JOIN guru g ON g.id = js.guru_id
            WHERE pk.murid_id = ?
            ORDER BY js.tanggal, js.jam_mulai
        """, (murid_id,))

    def get_sesi_guru(self, guru_id: int) -> List[sqlite3.Row]:
        return self.fetch_all("""
            SELECT js.*, m.nama AS nama_murid, k.nama AS nama_kursus
            FROM jadwal_sesi js
            JOIN pendaftaran_kursus pk ON pk.id = js.pendaftaran_id
            JOIN murid  m ON m.id = pk.murid_id
            JOIN kursus k ON k.id = pk.kursus_id
            WHERE js.guru_id = ?
            ORDER BY js.tanggal, js.jam_mulai
        """, (guru_id,))

    # ── Absensi — dipakai oleh modul Absensi.py ─────────────────────────
    def get_pendaftaran_aktif(self) -> List[sqlite3.Row]:
        """Semua pendaftaran kursus aktif, dipakai untuk halaman Absensi Murid."""
        return self.fetch_all("""
            SELECT pk.id AS pendaftaran_id, pk.murid_id, pk.kursus_id, pk.guru_id,
                   pk.jumlah_sesi_paket, pk.tgl_mulai,
                   m.nama AS murid, k.nama AS instrumen,
                   COALESCE(g.nama, '–') AS guru
            FROM pendaftaran_kursus pk
            JOIN murid  m ON m.id = pk.murid_id
            JOIN kursus k ON k.id = pk.kursus_id
            LEFT JOIN guru g ON g.id = pk.guru_id
            WHERE pk.status = 'Aktif'
            ORDER BY m.nama
        """)

    def get_pendaftaran_semua(self) -> List[sqlite3.Row]:
        """Semua pendaftaran kursus — 'Aktif' maupun 'Selesai' — dipakai
        halaman Absensi Murid supaya paket yang sesinya sudah terlaksana
        semua tetap tampil (sebagai riwayat/arsip), tidak hilang begitu
        saja dari daftar seperti pada get_pendaftaran_aktif()."""
        return self.fetch_all("""
            SELECT pk.id AS pendaftaran_id, pk.murid_id, pk.kursus_id, pk.guru_id,
                   pk.jumlah_sesi_paket, pk.tgl_mulai, pk.status,
                   m.nama AS murid, k.nama AS instrumen,
                   COALESCE(g.nama, '–') AS guru
            FROM pendaftaran_kursus pk
            JOIN murid  m ON m.id = pk.murid_id
            JOIN kursus k ON k.id = pk.kursus_id
            LEFT JOIN guru g ON g.id = pk.guru_id
            WHERE pk.status IN ('Aktif', 'Selesai')
            ORDER BY m.nama
        """)

    def get_pendaftaran_by_id(self, pendaftaran_id: int) -> Optional[sqlite3.Row]:
        """Detail satu pendaftaran (murid, instrumen, guru) — dipakai header
        kartu murid di dialog Detail Absensi (avatar, nama, badge instrumen,
        Instruktur, Lokasi)."""
        return self.fetch_one("""
            SELECT pk.id AS pendaftaran_id, pk.murid_id, pk.kursus_id, pk.guru_id,
                   pk.jumlah_sesi_paket,
                   m.nama AS murid, k.nama AS instrumen,
                   COALESCE(g.nama, '–') AS guru
            FROM pendaftaran_kursus pk
            JOIN murid  m ON m.id = pk.murid_id
            JOIN kursus k ON k.id = pk.kursus_id
            LEFT JOIN guru g ON g.id = pk.guru_id
            WHERE pk.id = ?
        """, (pendaftaran_id,))

    def get_sesi_by_pendaftaran(self, pendaftaran_id: int) -> List[sqlite3.Row]:
        """Semua sesi (jadwal_sesi) milik satu pendaftaran, dipakai untuk
        menghitung Sesi Terakhir / Sesi Tersisa & untuk dialog Detail Absensi."""
        return self.fetch_all("""
            SELECT js.*, g.nama AS nama_guru
            FROM jadwal_sesi js
            LEFT JOIN guru g ON g.id = js.guru_id
            WHERE js.pendaftaran_id = ?
            ORDER BY js.no_sesi, js.id
        """, (pendaftaran_id,))

    def set_status_sesi(self, sesi_id: int, status: str) -> None:
        """Tandai satu sesi sebagai 'Terlaksana' | 'Batal' | 'Pending' (absensi murid/guru).

        Kalau status menjadi 'Terlaksana' dan itu membuat jumlah sesi yang
        sudah terlaksana mencapai kuota paket (jumlah_sesi_paket), paket
        (pendaftaran_kursus) tsb otomatis ditandai 'Selesai'. Kalau murid
        yang bersangkutan tidak punya pendaftaran_kursus lain berstatus
        'Aktif', murid tsb otomatis dipindah ke status 'Nonaktif' —
        sehingga "Hari Les" & "Alat Musik" murid itu otomatis kosong ('-')
        di Data Murid (keduanya dihitung hanya dari pendaftaran berstatus
        'Aktif')."""
        self.execute("UPDATE jadwal_sesi SET status=? WHERE id=?", (status, sesi_id))
        if status == "Terlaksana":
            self._cek_dan_selesaikan_paket(sesi_id)

    def _cek_dan_selesaikan_paket(self, sesi_id: int) -> None:
        """Cek apakah paket (pendaftaran_kursus) dari satu sesi sudah
        terlaksana penuh sesuai kuota; kalau ya, tandai paket 'Selesai' lalu
        — kalau murid tidak punya pendaftaran aktif lain — pindahkan murid
        ke status 'Nonaktif' secara otomatis."""
        sesi = self.fetch_one("SELECT pendaftaran_id FROM jadwal_sesi WHERE id=?", (sesi_id,))
        if not sesi:
            return
        pendaftaran_id = sesi["pendaftaran_id"]
        pk = self.fetch_one(
            "SELECT id, murid_id, jumlah_sesi_paket, status FROM pendaftaran_kursus WHERE id=?",
            (pendaftaran_id,)
        )
        if not pk or pk["status"] != "Aktif":
            return
        total = pk["jumlah_sesi_paket"] or 0
        if total <= 0:
            return  # paket tak terbatas (lama) — tidak pernah otomatis selesai
        terlaksana = self.fetch_one(
            "SELECT COUNT(*) AS n FROM jadwal_sesi WHERE pendaftaran_id=? AND status='Terlaksana'",
            (pendaftaran_id,)
        )["n"]
        if terlaksana < total:
            return
        self.execute("UPDATE pendaftaran_kursus SET status='Selesai' WHERE id=?", (pk["id"],))
        masih_aktif = self.fetch_one(
            "SELECT COUNT(*) AS n FROM pendaftaran_kursus WHERE murid_id=? AND status='Aktif'",
            (pk["murid_id"],)
        )["n"]
        if masih_aktif == 0:
            self.execute("UPDATE murid SET status='Nonaktif' WHERE id=?", (pk["murid_id"],))

    def sinkronkan_paket_selesai(self) -> None:
        """Sinkronkan status pendaftaran_kursus & murid dengan progres sesi
        yang sebenarnya (versi massal/SQL-langsung dari `_cek_dan_selesaikan_paket`).

        Dipanggil di init_db() saat aplikasi start — supaya data lama yang
        sesi-nya sudah pernah ditandai 'Terlaksana' SEBELUM logika auto-
        selesai ini ada (mis. hasil import/DB lama) tetap ikut ter-update —
        dan juga dipanggil ulang setiap kali halaman Data Murid / Absensi
        dimuat, supaya selalu konsisten (self-healing) walau ada perubahan
        status sesi dari jalur lain.

        1) Paket berstatus 'Aktif' dengan kuota (jumlah_sesi_paket > 0) yang
           sesi 'Terlaksana'-nya sudah mencapai/melebihi kuota → 'Selesai'.
        2) Murid berstatus 'Aktif' yang pernah punya pendaftaran kursus tapi
           sudah tidak punya satu pun pendaftaran berstatus 'Aktif' lagi →
           'Nonaktif'.
        """
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE pendaftaran_kursus
                SET status = 'Selesai'
                WHERE status = 'Aktif'
                  AND jumlah_sesi_paket > 0
                  AND (
                        SELECT COUNT(*) FROM jadwal_sesi
                        WHERE jadwal_sesi.pendaftaran_id = pendaftaran_kursus.id
                          AND jadwal_sesi.status = 'Terlaksana'
                      ) >= jumlah_sesi_paket
            """)
            conn.execute("""
                UPDATE murid
                SET status = 'Nonaktif'
                WHERE status = 'Aktif'
                  AND id IN (SELECT DISTINCT murid_id FROM pendaftaran_kursus)
                  AND id NOT IN (SELECT murid_id FROM pendaftaran_kursus WHERE status = 'Aktif')
            """)
            conn.commit()
        finally:
            conn.close()

    def reschedule_sesi(self, sesi_id: int, tanggal: str, jam_mulai: str, jam_selesai: str) -> None:
        """
        Ubah tanggal & jam satu sesi les (dipakai tombol "Reschedule" di
        panel Reminder Besok, Dashboard Admin). Status sesi tidak diubah.
        """
        self.execute(
            "UPDATE jadwal_sesi SET tanggal=?, jam_mulai=?, jam_selesai=? WHERE id=?",
            (tanggal, jam_mulai, jam_selesai, sesi_id)
        )

    def duplikat_sesi(self, sesi_id: int) -> dict:
        """Duplikat satu sesi (jadwal_sesi) jadi sesi baru seminggu setelahnya
        (tanggal +7 hari), jam/metode/guru sama persis, status direset ke
        'Pending'. Dipakai tombol ikon 'copy' pada kolom AKSI dialog Detail
        Absensi (murid) — menggantikan tombol Tandai Hadir/Tidak Hadir lama,
        yang sekarang hanya bisa ditandai lewat tabel Absensi Murid utama.
        Sebelum membuat sesi baru, dicek dulu apakah guru atau murid yang
        sama sudah punya sesi lain yang jamnya tumpang tindih pada tanggal
        (+7 hari) itu — kalau bentrok, sesi baru TIDAK dibuat.
        Return dict: {"ok": bool, "pesan": str, "sesi_baru_id": int|None}"""
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM jadwal_sesi WHERE id=?", (sesi_id,)).fetchone()
            if not row:
                return {"ok": False, "pesan": "Sesi asal tidak ditemukan.", "sesi_baru_id": None}

            tanggal_baru = row["tanggal"]
            for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                try:
                    tgl = datetime.strptime(row["tanggal"], fmt)
                    tanggal_baru = (tgl + timedelta(days=7)).strftime(fmt)
                    break
                except (ValueError, TypeError):
                    continue

            murid_row = conn.execute(
                "SELECT murid_id FROM pendaftaran_kursus WHERE id=?", (row["pendaftaran_id"],)
            ).fetchone()
            murid_id = murid_row["murid_id"] if murid_row else None

            if self._ada_bentrok_jadwal(conn, row["guru_id"], tanggal_baru,
                                         row["jam_mulai"], row["jam_selesai"], murid_id):
                return {"ok": False,
                        "pesan": f"Jadwal bentrok: guru atau murid sudah punya sesi lain "
                                 f"yang jamnya tumpang tindih pada {tanggal_baru}.",
                        "sesi_baru_id": None}

            max_no_row = conn.execute(
                "SELECT COALESCE(MAX(no_sesi), 0) AS m FROM jadwal_sesi WHERE pendaftaran_id=?",
                (row["pendaftaran_id"],)
            ).fetchone()
            no_sesi_baru = (max_no_row["m"] if max_no_row else 0) + 1

            cur = conn.execute("""
                INSERT INTO jadwal_sesi (pendaftaran_id, guru_id, no_sesi, tanggal,
                                          jam_mulai, jam_selesai, metode, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
            """, (row["pendaftaran_id"], row["guru_id"], no_sesi_baru, tanggal_baru,
                  row["jam_mulai"], row["jam_selesai"], row["metode"] or "Offline"))
            sesi_baru_id = cur.lastrowid
            conn.commit()
            return {"ok": True,
                    "pesan": f"Sesi baru berhasil dibuat pada {tanggal_baru}.",
                    "sesi_baru_id": sesi_baru_id}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Batal / Reschedule khusus / Undo Batal — masing-masing satu transaksi SQLite penuh ──

    def _pola_hari_pendaftaran(self, conn: sqlite3.Connection, pendaftaran_id: int) -> set:
        """Kumpulan hari-dalam-minggu (0=Senin..6=Minggu) dari sesi bertipe
        'Reguler' pada satu pendaftaran — dipakai sebagai patokan pola
        jadwal rutin (mis. {0, 2} untuk Senin & Rabu) saat mencari tanggal
        sesi pengganti akibat Batal. Sesi bertipe 'Reschedule' (pindah
        khusus di luar pola) SENGAJA tidak ikut dihitung, supaya pola
        rutin tidak melebar gara-gara satu kali pindah ke hari lain."""
        rows = conn.execute("""
            SELECT tanggal FROM jadwal_sesi
            WHERE pendaftaran_id=? AND COALESCE(tipe_sesi,'Reguler')='Reguler'
        """, (pendaftaran_id,)).fetchall()
        pola = set()
        for r in rows:
            dt = _parse_tgl_ddmmyyyy(r["tanggal"])
            if dt is not None:
                pola.add(dt.weekday())
        return pola

    def _sesi_aktif_pendaftaran(self, conn: sqlite3.Connection, pendaftaran_id: int) -> int:
        """Jumlah sesi yang dihitung 'aktif' terhadap kuota paket — semua
        sesi KECUALI yang berstatus Batal (dibatalkan, tidak terjadi) atau
        Reschedule (sudah dipindah sepenuhnya ke sesi baru, jadi baris
        asalnya tidak lagi mewakili satu kali pertemuan)."""
        row = conn.execute("""
            SELECT COUNT(*) AS n FROM jadwal_sesi
            WHERE pendaftaran_id=? AND status NOT IN ('Batal','Reschedule')
        """, (pendaftaran_id,)).fetchone()
        return row["n"] if row else 0

    def _ada_bentrok_jadwal(self, conn: sqlite3.Connection, guru_id: Optional[int],
                             tanggal: str, jam_mulai: str, jam_selesai: Optional[str] = None,
                             murid_id: Optional[int] = None,
                             exclude_id: Optional[int] = None) -> bool:
        """True kalau guru ATAU murid yang sama sudah punya sesi lain
        (status bukan Batal) yang jam-nya TUMPANG TINDIH pada tanggal yang
        sama — dipakai mencegah jadwal bentrok, baik untuk sesi pengganti
        otomatis (Batal), sesi hasil Reschedule khusus, maupun jadwal les
        baru. Kalau jam_selesai tidak diberikan, dianggap sama dengan
        jam_mulai (fallback ke perbandingan jam mulai persis, kompatibel
        dengan pemanggilan lama)."""
        if guru_id is None and murid_id is None:
            return False  # tidak ada guru/murid tertentu, tidak ada yang bisa bentrok
        js_baru = jam_selesai or jam_mulai
        params = [tanggal, js_baru, jam_mulai,
                  guru_id if guru_id is not None else -1,
                  murid_id if murid_id is not None else -1]
        sql = """
            SELECT js.id FROM jadwal_sesi js
            JOIN pendaftaran_kursus pk ON js.pendaftaran_id = pk.id
            WHERE js.tanggal=? AND js.status NOT IN ('Batal', 'Reschedule')
              AND js.jam_mulai < ? AND ? < js.jam_selesai
              AND (js.guru_id=? OR pk.murid_id=?)
        """
        if exclude_id is not None:
            sql += " AND js.id != ?"
            params.append(exclude_id)
        return conn.execute(sql, tuple(params)).fetchone() is not None

    def batalkan_sesi(self, sesi_id: int) -> dict:
        """
        Tandai satu sesi sebagai 'Batal', lalu OTOMATIS buat satu sesi
        pengganti mengikuti pola jadwal rutin pendaftaran ini (mis. kalau
        biasanya Senin/Rabu berselang-seling dan sesi Senin dibatalkan,
        sesi pengganti tetap jatuh di Senin/Rabu berikutnya — bukan hari
        acak), dengan no_sesi yang SAMA seperti sesi yang dibatalkan
        (jumlah sesi di paket tidak bertambah).

        Sesi pengganti HANYA dibuat kalau:
          1) kuota masih tersedia — jumlah sesi aktif (di luar Batal &
             Reschedule) belum mencapai jumlah_sesi_paket (0/kosong =
             paket tak terbatas, selalu dianggap tersedia), dan
          2) tidak terjadi bentrok jadwal (guru+tanggal+jam yang sama
             belum dipakai sesi lain yang masih aktif).
        Kalau salah satu syarat tidak terpenuhi, sesi tetap ditandai
        Batal, hanya saja sesi penggantinya tidak dibuat.

        Return dict: {"ok": bool, "pesan": str, "sesi_pengganti_id": int|None}
        """
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM jadwal_sesi WHERE id=?", (sesi_id,)).fetchone()
            if not row:
                return {"ok": False, "pesan": "Sesi tidak ditemukan.", "sesi_pengganti_id": None}
            if row["status"] == "Batal":
                return {"ok": False, "pesan": "Sesi ini sudah berstatus Batal.", "sesi_pengganti_id": None}

            pendaftaran_id = row["pendaftaran_id"]

            # pola hari dihitung sebelum status diubah, agar sesi ini tetap menyumbang pola
            pola = self._pola_hari_pendaftaran(conn, pendaftaran_id)

            conn.execute("UPDATE jadwal_sesi SET status='Batal' WHERE id=?", (sesi_id,))

            pk = conn.execute(
                "SELECT jumlah_sesi_paket FROM pendaftaran_kursus WHERE id=?", (pendaftaran_id,)
            ).fetchone()
            jumlah_sesi_paket = (pk["jumlah_sesi_paket"] if pk else 0) or 0
            aktif = self._sesi_aktif_pendaftaran(conn, pendaftaran_id)
            kuota_tersedia = (jumlah_sesi_paket <= 0) or (aktif < jumlah_sesi_paket)

            if not pola:
                conn.commit()
                return {"ok": True,
                        "pesan": "Sesi ditandai Batal. Pola hari les belum bisa dihitung, "
                                 "sesi pengganti tidak dibuat.",
                        "sesi_pengganti_id": None}
            if not kuota_tersedia:
                conn.commit()
                return {"ok": True,
                        "pesan": "Sesi ditandai Batal. Kuota paket sudah penuh, "
                                 "sesi pengganti tidak dibuat.",
                        "sesi_pengganti_id": None}

            # cari tanggal pengganti: hari yang cocok pola, setelah tanggal paling akhir yang terjadwal
            semua_tgl = conn.execute(
                "SELECT tanggal FROM jadwal_sesi WHERE pendaftaran_id=?", (pendaftaran_id,)
            ).fetchall()
            tanggal_terakhir = None
            for r in semua_tgl:
                dt = _parse_tgl_ddmmyyyy(r["tanggal"])
                if dt is not None and (tanggal_terakhir is None or dt > tanggal_terakhir):
                    tanggal_terakhir = dt
            if tanggal_terakhir is None:
                tanggal_terakhir = datetime.now()

            murid_row = conn.execute(
                "SELECT murid_id FROM pendaftaran_kursus WHERE id=?", (pendaftaran_id,)
            ).fetchone()
            murid_id = murid_row["murid_id"] if murid_row else None

            tanggal_baru = None
            cursor_dt = tanggal_terakhir + timedelta(days=1)
            for _ in range(370):  # batas aman ~1 tahun ke depan
                if cursor_dt.weekday() in pola and not self._ada_bentrok_jadwal(
                        conn, row["guru_id"], cursor_dt.strftime("%d-%m-%Y"),
                        row["jam_mulai"], row["jam_selesai"], murid_id):
                    tanggal_baru = cursor_dt
                    break
                cursor_dt += timedelta(days=1)

            if tanggal_baru is None:
                conn.commit()
                return {"ok": True,
                        "pesan": "Sesi ditandai Batal. Tidak ditemukan tanggal pengganti "
                                 "tanpa bentrok jadwal dalam 1 tahun ke depan.",
                        "sesi_pengganti_id": None}

            cur = conn.execute("""
                INSERT INTO jadwal_sesi
                    (pendaftaran_id, guru_id, no_sesi, tanggal, jam_mulai, jam_selesai,
                     metode, status, tipe_sesi, sesi_asal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Reguler', ?)
            """, (pendaftaran_id, row["guru_id"], row["no_sesi"],
                  tanggal_baru.strftime("%d-%m-%Y"), row["jam_mulai"], row["jam_selesai"],
                  row["metode"] or "Offline", sesi_id))
            sesi_pengganti_id = cur.lastrowid
            conn.commit()
            return {"ok": True,
                    "pesan": f"Sesi ditandai Batal. Sesi pengganti dibuat pada "
                             f"{tanggal_baru.strftime('%d-%m-%Y')} (sesi {row['no_sesi']}).",
                    "sesi_pengganti_id": sesi_pengganti_id}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reschedule_khusus_sesi(self, sesi_id: int, tanggal_baru: str,
                                jam_mulai: str, jam_selesai: str) -> dict:
        """
        Reschedule KHUSUS satu sesi ke tanggal/jam pilihan admin, DI LUAR
        pola jadwal rutin (mis. biasanya Senin/Rabu, kali ini pindah
        sekali ke Kamis). Sesi asal ditandai status 'Reschedule' (baris
        asal berhenti dihitung sebagai pertemuan aktif — sudah sepenuhnya
        digantikan oleh sesi baru), lalu dibuat SATU sesi baru pada
        tanggal/jam pilihan admin dengan no_sesi yang SAMA seperti sesi
        asal (jumlah sesi di paket tidak bertambah). Sesi baru diberi
        tipe_sesi='Reschedule' supaya tidak ikut menggeser pola hari rutin
        (lihat _pola_hari_pendaftaran).

        Sama seperti Batal, tetap memeriksa kuota paket & bentrok jadwal
        SEBELUM melakukan perubahan apa pun — kalau salah satu gagal,
        tidak ada yang diubah sama sekali (status asal tetap seperti
        semula) supaya admin bisa memilih tanggal/jam lain.

        Return dict: {"ok": bool, "pesan": str, "sesi_baru_id": int|None}
        """
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM jadwal_sesi WHERE id=?", (sesi_id,)).fetchone()
            if not row:
                return {"ok": False, "pesan": "Sesi tidak ditemukan.", "sesi_baru_id": None}
            if row["status"] in ("Batal", "Reschedule"):
                return {"ok": False,
                        "pesan": f"Sesi berstatus {row['status']} tidak bisa di-reschedule lagi.",
                        "sesi_baru_id": None}

            pendaftaran_id = row["pendaftaran_id"]
            murid_row = conn.execute(
                "SELECT murid_id FROM pendaftaran_kursus WHERE id=?", (pendaftaran_id,)
            ).fetchone()
            murid_id = murid_row["murid_id"] if murid_row else None

            # 1) cek bentrok jadwal DULU, sebelum ada perubahan apa pun
            if self._ada_bentrok_jadwal(conn, row["guru_id"], tanggal_baru, jam_mulai,
                                         jam_selesai, murid_id, exclude_id=sesi_id):
                return {"ok": False,
                        "pesan": "Jadwal bentrok: guru atau murid sudah punya sesi lain "
                                 "yang jamnya tumpang tindih di tanggal itu.",
                        "sesi_baru_id": None}

            # 2) cek kuota — hitung seolah sesi asal SUDAH jadi Reschedule
            # (tidak lagi dihitung aktif), tapi sesi baru BELUM ditambahkan
            pk = conn.execute(
                "SELECT jumlah_sesi_paket FROM pendaftaran_kursus WHERE id=?", (pendaftaran_id,)
            ).fetchone()
            jumlah_sesi_paket = (pk["jumlah_sesi_paket"] if pk else 0) or 0
            aktif_tanpa_asal = conn.execute("""
                SELECT COUNT(*) AS n FROM jadwal_sesi
                WHERE pendaftaran_id=? AND status NOT IN ('Batal','Reschedule') AND id != ?
            """, (pendaftaran_id, sesi_id)).fetchone()["n"]
            kuota_tersedia = (jumlah_sesi_paket <= 0) or (aktif_tanpa_asal < jumlah_sesi_paket)
            if not kuota_tersedia:
                return {"ok": False,
                        "pesan": "Kuota sesi paket sudah penuh, tidak bisa membuat sesi baru.",
                        "sesi_baru_id": None}

            # semua validasi lolos → baru sekarang ubah status + insert
            conn.execute("UPDATE jadwal_sesi SET status='Reschedule' WHERE id=?", (sesi_id,))
            cur = conn.execute("""
                INSERT INTO jadwal_sesi
                    (pendaftaran_id, guru_id, no_sesi, tanggal, jam_mulai, jam_selesai,
                     metode, status, tipe_sesi, sesi_asal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', 'Reschedule', ?)
            """, (pendaftaran_id, row["guru_id"], row["no_sesi"],
                  tanggal_baru, jam_mulai, jam_selesai, row["metode"] or "Offline", sesi_id))
            sesi_baru_id = cur.lastrowid
            conn.commit()
            return {"ok": True,
                    "pesan": f"Sesi berhasil di-reschedule ke {tanggal_baru} (sesi {row['no_sesi']}).",
                    "sesi_baru_id": sesi_baru_id}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def undo_batal_sesi(self, sesi_id: int) -> dict:
        """
        Batalkan pembatalan: status sesi 'Batal' -> 'Pending' (belum
        absen) lagi. Kalau sesi pengganti otomatis sudah sempat dibuat
        (baris lain dengan sesi_asal_id = sesi ini), sesi pengganti itu
        DIHAPUS supaya jumlah sesi tidak dobel / tetap sesuai kuota
        paket.

        Return dict: {"ok": bool, "pesan": str}
        """
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM jadwal_sesi WHERE id=?", (sesi_id,)).fetchone()
            if not row:
                return {"ok": False, "pesan": "Sesi tidak ditemukan."}
            if row["status"] != "Batal":
                return {"ok": False, "pesan": "Sesi ini tidak sedang berstatus Batal."}

            conn.execute("UPDATE jadwal_sesi SET status='Pending' WHERE id=?", (sesi_id,))
            pengganti = conn.execute(
                "SELECT id FROM jadwal_sesi WHERE sesi_asal_id=?", (sesi_id,)
            ).fetchall()
            for p in pengganti:
                conn.execute("DELETE FROM jadwal_sesi WHERE id=?", (p["id"],))
            conn.commit()

            pesan = "Pembatalan dibatalkan, sesi kembali Belum Absen."
            if pengganti:
                pesan += f" {len(pengganti)} sesi pengganti otomatis ikut dihapus."
            return {"ok": True, "pesan": pesan}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_admin_aktif(self) -> List[sqlite3.Row]:
        return self.fetch_all("SELECT * FROM admin WHERE status='Aktif' ORDER BY nama")

    def get_transaksi_bulan(self, bulan: int, tahun: int) -> List[sqlite3.Row]:
        """Ambil transaksi berdasarkan bulan & tahun dari kolom tanggal 'DD/MM/YYYY'."""
        return self.fetch_all("""
            SELECT * FROM transaksi_keuangan
            WHERE SUBSTR(tanggal,4,2) = ? AND SUBSTR(tanggal,7,4) = ?
            ORDER BY tanggal
        """, (f"{bulan:02d}", str(tahun)))

    # ── Owner (username, nama, password) ──────────────────────

    def get_owner_info(self) -> dict:
        """Ambil data akun Owner: username, nama (display_name), password plain."""
        row = self.fetch_one(
            "SELECT username, display_name, password_plain FROM users WHERE role='owner' LIMIT 1"
        )
        if row:
            return {
                "username": row["username"],
                "nama": row["display_name"],
                "password": row["password_plain"] or "",
            }
        return {"username": "", "nama": "", "password": ""}

    def get_owner_password_plain(self) -> str:
        """Ambil password plain Owner (untuk prefill form Edit)."""
        row = self.fetch_one(
            "SELECT password_plain FROM users WHERE role='owner' LIMIT 1"
        )
        return row["password_plain"] if row and row["password_plain"] else ""

    def update_owner(self, nama: str, username: str, password: str = None) -> bool:
        """Update data Owner. Return False jika tidak ditemukan. Raise ValueError jika username duplikat."""
        owner = self.fetch_one("SELECT id FROM users WHERE role='owner' LIMIT 1")
        if not owner:
            return False

        dup = self.fetch_one(
            "SELECT id FROM users WHERE username=? AND id!=?",
            (username, owner["id"])
        )
        if dup:
            raise ValueError(f"Username '{username}' sudah digunakan!")

        if password:
            self.execute(
                "UPDATE users SET display_name=?, username=?, password=?, password_plain=? WHERE id=?",
                (nama, username, _hash(password), password, owner["id"])
            )
        else:
            self.execute(
                "UPDATE users SET display_name=?, username=? WHERE id=?",
                (nama, username, owner["id"])
            )
        return True


DB = _Database()


#  ENTRY POINT  —  jalankan langsung untuk inisialisasi

if __name__ == "__main__":
    print("Menginisialisasi database Melody Violin School...")
    init_db()
    print(f"Database berhasil dibuat: {DB_PATH}")

    # Verifikasi
    checks = [
        ("users",               "SELECT COUNT(*) FROM users"),
        ("admin",               "SELECT COUNT(*) FROM admin"),
        ("guru",                "SELECT COUNT(*) FROM guru"),
        ("murid",               "SELECT COUNT(*) FROM murid"),
        ("kursus",              "SELECT COUNT(*) FROM kursus"),
        ("pendaftaran_kursus",  "SELECT COUNT(*) FROM pendaftaran_kursus"),
        ("jadwal_sesi",         "SELECT COUNT(*) FROM jadwal_sesi"),
        ("transaksi_keuangan",  "SELECT COUNT(*) FROM transaksi_keuangan"),
        ("kehadiran_admin",     "SELECT COUNT(*) FROM kehadiran_admin"),
    ]
    print("\n── Jumlah baris per tabel ──")
    for nama, sql in checks:
        n = DB.fetch_one(sql)[0]
        print(f"  {nama:<25} {n} baris")

    print("\n── Contoh: Jadwal hari ini (10-06-2026) ──")
    for r in DB.get_jadwal_hari_ini("10-06-2026"):
        print(f"  {r['jam_mulai']} | {r['nama_murid']:<18} | {r['nama_kursus']:<8} | {r['nama_guru']}")