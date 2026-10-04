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
def ambil_kelas_by_id(kelas_id):
    """TODO (Anggota 1)"""
    pass


def ambil_jadwal_by_kelas(kelas_id):
    """TODO (Anggota 1)"""
    pass


def ambil_jadwal_by_pengajar(pengajar_id):
    """TODO (Anggota 1)"""
    pass


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
