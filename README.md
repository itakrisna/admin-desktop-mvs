# Admin Desktop MVS

Aplikasi desktop untuk manajemen administrasi Melody Violin School Yogyakarta
(absensi, pembayaran, data murid, data guru, laporan keuangan, dll).
Dibuat dengan Python + PyQt5.

## Cara Menjalankan (untuk mencoba aplikasi)

### 1. Install Python
Pastikan Python 3.9–3.11 sudah terinstal di komputer.
Cek dengan menjalankan:
```
python --version
```

### 2. Clone repository ini
```
git clone <URL_REPO_INI>
cd admin-desktop-mvs
```

### 3. (Opsional tapi disarankan) Buat virtual environment
```
python -m venv venv
```
Aktifkan:
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

### 4. Install dependency
```
pip install -r requirements.txt
```

### 5. Jalankan aplikasi
```
python main.py
```

Database (`mvs.db`) akan otomatis dibuat saat pertama kali dijalankan, lengkap
dengan akun default untuk login:

| Role  | Username | Password |
|-------|----------|----------|
| Admin | admin    | 1        |
| Owner | owner    | 1        |

> Silakan ganti password ini setelah login pertama kali (menu Pengaturan).

## Struktur Project
- `main.py` — entry point aplikasi
- `login.py` — halaman login
- `DashboardAdmin.py` / `DashboardOwner.py` — dashboard sesuai role
- `Absensi.py`, `Pembayaran.py`, `DataMurid.py`, `DataGuru.py`, `DataAdmin.py`,
  `LaporanKeuangan.py`, `Pengaturan.py` — modul-modul fitur
- `database.py` — koneksi & skema database (SQLite)
- `theme.py`, `toast_notification.py` — komponen UI pendukung

## Catatan
File `mvs.db` (data asli sekolah), folder `venv/`, `dist/`, `build/`, dan
`__pycache__/` sengaja tidak disertakan dalam repository ini (lihat
`.gitignore`).
