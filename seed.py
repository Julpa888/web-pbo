"""
seed.py
Penanggung jawab: JULPA (Koordinator/Integrator)

Jalankan SEKALI untuk membuat akun admin pertama. Akun admin berikutnya
(kalau perlu lebih dari satu) dibuat oleh admin ini lewat fitur
"Kelola Akun" di web, bukan lewat file ini lagi.

Cara pakai: python seed.py
"""

import database

# TODO: ganti username/password default ini sebelum deploy publik
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_NAMA = "Admin Fluenglo"


def buat_admin_pertama():
    sudah_ada = database.ambil_user_by_username(ADMIN_USERNAME)
    if sudah_ada:
        print(f"Akun '{ADMIN_USERNAME}' sudah ada, tidak dibuat ulang.")
        return
    database.tambah_user(
        nama=ADMIN_NAMA,
        username=ADMIN_USERNAME,
        password=ADMIN_PASSWORD,
        role="admin",
    )
    print(f"Akun admin '{ADMIN_USERNAME}' berhasil dibuat.")


if __name__ == "__main__":
    database.buat_tabel()
    buat_admin_pertama()
    print("Selesai. Login dengan username:", ADMIN_USERNAME)
