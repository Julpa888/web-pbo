"""
database.py
Penanggung jawab: JULPA (Koordinator/Integrator)

Koneksi dasar ke SQLite. Fungsi untuk tabel `users` (bagian Julpa) sudah
diisi penuh. Anggota lain menambahkan fungsi query modulnya masing-masing
di bagian yang sudah ditandai — jangan bikin file koneksi sendiri-sendiri,
supaya satu database dipakai bersama.
"""

import sqlite3

NAMA_DATABASE = "fluenglo.db"


def koneksi():
    conn = sqlite3.connect(NAMA_DATABASE)
    conn.row_factory = sqlite3.Row  # supaya bisa akses kolom lewat nama: row["username"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def buat_tabel():
    conn = koneksi()
    with open("schema.sql") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


# ======================================================
# JULPA — query untuk users (akun), dipakai login() & Admin.kelola_akun()
# ======================================================
def ambil_user_by_username(username):
    conn = koneksi()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def ambil_user_by_id(user_id):
    conn = koneksi()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def ambil_semua_user(role=None):
    conn = koneksi()
    if role:
        rows = conn.execute("SELECT * FROM users WHERE role = ?", (role,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return rows


def tambah_user(nama, username, password, role, kelas_id=None, foto=None, no_whatsapp=None, biodata=None):
    conn = koneksi()
    cursor = conn.execute(
        """INSERT INTO users (nama, username, password, role, kelas_id, foto, no_whatsapp, biodata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (nama, username, password, role, kelas_id, foto, no_whatsapp, biodata),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def edit_user(user_id, **perubahan):
    """perubahan: dict berisi kolom yang mau diubah, misal nama="Budi Baru".
    Kolom yang tidak dikirim tidak akan diubah."""
    if not perubahan:
        return False
    kolom_valid = {"nama", "username", "password", "role", "kelas_id", "foto", "no_whatsapp", "biodata"}
    perubahan = {k: v for k, v in perubahan.items() if k in kolom_valid}
    if not perubahan:
        return False

    set_clause = ", ".join(f"{kolom} = ?" for kolom in perubahan)
    nilai = list(perubahan.values()) + [user_id]

    conn = koneksi()
    conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", nilai)
    conn.commit()
    conn.close()
    return True


def hapus_user(user_id):
    conn = koneksi()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True


# ======================================================
# ANGGOTA 1 — query untuk kelas, jadwal
# ======================================================
_SQL_KELAS = """
    SELECT k.id, k.nama, k.pengajar_id, u.nama AS pengajar_nama,
            (SELECT COUNT(*) FROM kelas_siswa ks WHERE ks.kelas_id = k.id) AS jumlah_siswa
    FROM kelas k
    JOIN users u ON u.id = k.pengajar_id
"""

_SQL_JADWAL = """
    SELECT j.id, j.hari, j.jam, j.kelas_id, j.pengajar_id,
            k.nama AS kelas_nama, u.nama AS pengajar_nama
    FROM jadwal j
    JOIN kelas k ON k.id = j.kelas_id
    JOIN users u ON u.id = j.pengajar_id
"""

# Urut Senin -> Minggu, lalu berdasarkan jam
_URUT_JADWAL = """
    ORDER BY CASE j.hari
        WHEN 'Senin' THEN 1 WHEN 'Selasa' THEN 2 WHEN 'Rabu' THEN 3
        WHEN 'Kamis' THEN 4 WHEN 'Jumat' THEN 5 WHEN 'Sabtu' THEN 6
        ELSE 7 END, j.jam
"""

def _ambil_semua(sql, params=()):
    conn = koneksi()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def _ambil_satu(sql, params=()):
    conn = koneksi()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return row

# ---------- KELAS ----------
def ambil_semua_kelas():
    """Semua kelas + nama pengajar + jumlah siswa."""
    return _ambil_semua(_SQL_KELAS + " ORDER BY k.nama")

def ambil_kelas_by_id(kelas_id):
    return _ambil_satu(_SQL_KELAS + " WHERE k.id = ?", (kelas_id,))

def ambil_kelas_by_nama(nama):
    """Cari kelas dengan nama sama (tidak peka huruf besar/kecil)."""
    return _ambil_satu("SELECT * FROM kelas WHERE LOWER(nama) = LOWER(?)", (nama,))


def tambah_kelas(nama, pengajar_id):
    conn = koneksi()
    cursor = conn.execute(
        "INSERT INTO kelas (nama, pengajar_id) VALUES (?, ?)", (nama, pengajar_id)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def edit_kelas(kelas_id, nama, pengajar_id):
    conn = koneksi()
    conn.execute(
        "UPDATE kelas SET nama = ?, pengajar_id = ? WHERE id = ?",
        (nama, pengajar_id, kelas_id),
    )
    conn.commit()
    conn.close()
    return True


def hitung_data_terkait_kelas(kelas_id):
    """Hitung data Anggota 2/4 yang masih menempel di kelas ini.
    Dipakai untuk mencegah kelas dihapus kalau masih punya materi/tugas/presensi."""
    conn = koneksi()
    hasil = {}
    for tabel in ("materi", "tugas", "presensi"):
        hasil[tabel] = conn.execute(
            f"SELECT COUNT(*) FROM {tabel} WHERE kelas_id = ?", (kelas_id,)
        ).fetchone()[0]
    conn.close()
    return hasil


def hapus_kelas(kelas_id):
    """Hapus kelas beserta jadwal dan keanggotaan siswanya (satu transaksi)."""
    conn = koneksi()
    conn.execute("DELETE FROM jadwal WHERE kelas_id = ?", (kelas_id,))
    conn.execute("DELETE FROM kelas_siswa WHERE kelas_id = ?", (kelas_id,))
    conn.execute("UPDATE users SET kelas_id = NULL WHERE kelas_id = ?", (kelas_id,))
    conn.execute("DELETE FROM kelas WHERE id = ?", (kelas_id,))
    conn.commit()
    conn.close()
    return True


# ---------- SISWA DI KELAS ----------
def ambil_siswa_by_kelas(kelas_id):
    return _ambil_semua(
        """SELECT u.* FROM users u
            JOIN kelas_siswa ks ON ks.siswa_id = u.id
            WHERE ks.kelas_id = ? ORDER BY u.nama""",
        (kelas_id,),
    )


def ambil_siswa_tanpa_kelas():
    return _ambil_semua(
        """SELECT * FROM users
            WHERE role = 'siswa' AND id NOT IN (SELECT siswa_id FROM kelas_siswa)
            ORDER BY nama"""
    )



def ambil_kelas_siswa(siswa_id):
    """Kelas tempat siswa ini terdaftar (None kalau belum punya kelas)."""
    return _ambil_satu(
        """SELECT k.* FROM kelas k
            JOIN kelas_siswa ks ON ks.kelas_id = k.id
            WHERE ks.siswa_id = ?""",
        (siswa_id,),
    )

def tambah_siswa_ke_kelas(kelas_id, siswa_id):
    conn = koneksi()
    conn.execute(
        "INSERT INTO kelas_siswa (kelas_id, siswa_id) VALUES (?, ?)", (kelas_id, siswa_id)
    )
    conn.execute("UPDATE users SET kelas_id = ? WHERE id = ?", (kelas_id, siswa_id))
    conn.commit()
    conn.close()
    return True

def hapus_siswa_dari_kelas(kelas_id, siswa_id):
    conn = koneksi()
    conn.execute(
        "DELETE FROM kelas_siswa WHERE kelas_id = ? AND siswa_id = ?", (kelas_id, siswa_id)
    )
    conn.execute(
        "UPDATE users SET kelas_id = NULL WHERE id = ? AND kelas_id = ?", (siswa_id, kelas_id)
    )
    conn.commit()
    conn.close()
    return True
 
 
# ---------- JADWAL ----------
def ambil_semua_jadwal():
    return _ambil_semua(_SQL_JADWAL + _URUT_JADWAL)
 
 
def ambil_jadwal_by_id(jadwal_id):
    return _ambil_satu(_SQL_JADWAL + " WHERE j.id = ?", (jadwal_id,))


def ambil_jadwal_by_kelas(kelas_id):
    """Dipakai Siswa.lihat_jadwal() (Anggota 1 -> tampil di halaman siswa)."""
    return _ambil_semua(_SQL_JADWAL + " WHERE j.kelas_id = ?" + _URUT_JADWAL, (kelas_id,))


def ambil_jadwal_by_pengajar(pengajar_id):
    """Dipakai halaman Jadwal Mengajar milik pengajar."""
    return _ambil_semua(_SQL_JADWAL + " WHERE j.pengajar_id = ?" + _URUT_JADWAL, (pengajar_id,))


def ambil_jadwal_by_hari(hari):
    """Dipakai untuk cek bentrok jadwal."""
    return _ambil_semua(_SQL_JADWAL + " WHERE j.hari = ?", (hari,))


def tambah_jadwal(hari, jam, kelas_id, pengajar_id):
    conn = koneksi()
    cursor = conn.execute(
        "INSERT INTO jadwal (hari, jam, kelas_id, pengajar_id) VALUES (?, ?, ?, ?)",
        (hari, jam, kelas_id, pengajar_id),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def edit_jadwal(jadwal_id, hari, jam, kelas_id, pengajar_id):
    conn = koneksi()
    conn.execute(
        "UPDATE jadwal SET hari = ?, jam = ?, kelas_id = ?, pengajar_id = ? WHERE id = ?",
        (hari, jam, kelas_id, pengajar_id, jadwal_id),
    )
    conn.commit()
    conn.close()
    return True

def hapus_jadwal(jadwal_id):
    conn = koneksi()
    conn.execute("DELETE FROM jadwal WHERE id = ?", (jadwal_id,))
    conn.commit()
    conn.close()
    return True



# ======================================================
# ANGGOTA 2 — query untuk materi, tugas, pengumpulan, komentar
# ======================================================
def ambil_materi_by_kelas(kelas_id):
    """TODO (Anggota 2)"""
    pass


def ambil_tugas_by_kelas(kelas_id):
    """TODO (Anggota 2)"""
    pass


def tambah_pengumpulan(tugas_id, siswa_id, jawaban, waktu_kumpul):
    """TODO (Anggota 2)"""
    pass


def tambah_komentar(tugas_id, user_id, isi, waktu):
    """TODO (Anggota 2)"""
    pass


# ======================================================
# ANGGOTA 3 — query untuk nilai & monitoring
# ======================================================
def ambil_nilai_by_siswa(siswa_id):
    """TODO (Anggota 3)"""
    pass


def beri_nilai_pengumpulan(pengumpulan_id, nilai):
    """TODO (Anggota 3)"""
    pass


# ======================================================
# ANGGOTA 4 — query untuk presensi, catatan_pengajar
# ======================================================
def ambil_presensi_by_siswa(siswa_id):
    """TODO (Anggota 4)"""
    pass


def ambil_catatan_by_siswa(siswa_id):
    """TODO (Anggota 4)"""
    pass


if __name__ == "__main__":
    # Jalankan file ini langsung (python database.py) untuk membuat
    # fluenglo.db dari schema.sql.
    buat_tabel()
    print("Tabel berhasil dibuat di", NAMA_DATABASE)
