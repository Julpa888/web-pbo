"""
models/user.py
Penanggung jawab utama: JULPA (Backend Auth) untuk class User & Admin.
Siswa & Pengajar: isi method sesuai TODO masing-masing (lihat nama di
komentar). Pola User.login()/cek_password() JANGAN diubah, karena app.py
sudah memanggilnya persis seperti ini.
"""

from abc import ABC, abstractmethod
import database


class User(ABC):
    """Class dasar (abstract) untuk semua jenis akun di sistem."""

    def __init__(self, id, nama, username, password):
        self.id = id
        self.nama = nama
        self.username = username
        self.__password = password 

    def cek_password(self, password):
        """Satu-satunya cara mengecek password dari luar class."""
        return self.__password == password

    @abstractmethod
    def tampilkan_menu(self):
        """Wajib di-override di tiap class turunan (POLYMORPHISM)."""
        pass


class Siswa(User):
    def __init__(self, id, nama, username, password, kelas_id=None):
        super().__init__(id, nama, username, password)
        self.kelas_id = kelas_id

    def lihat_jadwal(self):
        """TODO (Anggota 1): ambil jadwal berdasarkan self.kelas_id."""
        pass

    def kumpul_tugas(self, tugas, jawaban):
        """TODO (Anggota 2): panggil Pengumpulan.submit_jawaban()."""
        pass

    def komentar_tugas(self, tugas, isi):
        """TODO (Anggota 2): panggil Komentar.tambah_komentar()."""
        pass

    def lihat_monitoring(self):
        """TODO (Anggota 3): kumpulkan presensi + nilai jadi satu, untuk
        menu Monitoring Anak."""
        pass

    def tampilkan_menu(self):
        return ["Jadwal", "Materi", "Tugas", "Monitoring Anak"]


class Pengajar(User):
    def __init__(self, id, nama, username, password, foto=None, whatsapp=None, biodata=None):
        super().__init__(id, nama, username, password)
        self.foto = foto
        self.whatsapp = whatsapp
        self.biodata = biodata

    def edit_profil(self, foto=None, whatsapp=None, biodata=None):
        """TODO (Julpa/Aya, bagian profil ringan): update atribut di atas."""
        pass

    def upload_materi(self, kelas, judul, kategori, file):
        """TODO (Anggota 2): buat objek Materi, simpan ke database."""
        pass

    def buat_tugas(self, kelas, judul, deskripsi, deadline):
        """TODO (Anggota 2): buat objek Tugas, simpan ke database."""
        pass

    def beri_nilai(self, pengumpulan, nilai):
        """TODO (Anggota 3): panggil Pengumpulan.beri_nilai()."""
        pass

    def komentar_tugas(self, tugas, isi):
        """TODO (Anggota 2): sama seperti versi Siswa, untuk balas diskusi."""
        pass

    def catat_presensi(self, kelas, siswa, status):
        """TODO (Anggota 4): panggil Presensi.update_status()."""
        pass

    def tampilkan_menu(self):
        return ["Profil", "Jadwal Mengajar", "Materi", "Tugas", "Presensi"]


class Admin(User):
    def kelola_akun(self, aksi, **data):
        """Kelola akun siswa & pengajar: tambah, edit, hapus.

        aksi: 'tambah' | 'edit' | 'hapus'
        - tambah  -> data: nama, username, password, role, (opsional kelas_id/foto/dll)
        - edit    -> data: user_id, + field yang mau diubah
        - hapus   -> data: user_id
        """
        if aksi == "tambah":
            return database.tambah_user(
                nama=data["nama"],
                username=data["username"],
                password=data["password"],
                role=data["role"],
                foto=data.get("foto"),
                no_whatsapp=data.get("whatsapp"),
                biodata=data.get("biodata"),
            )
        elif aksi == "edit":
            user_id = data.pop("user_id")
            return database.edit_user(user_id, **data)
        elif aksi == "hapus":
            return database.hapus_user(data["user_id"])
        else:
            raise ValueError(f"Aksi tidak dikenal: {aksi}")

    def kelola_kelas(self, aksi, **data):
        """TODO (Anggota 1): tambah/edit/hapus Kelas + atur siswa."""
        pass

    def kelola_jadwal(self, aksi, **data):
        """TODO (Anggota 1): tambah/edit/hapus Jadwal."""
        pass

    def monitoring_sistem(self):
        """TODO (Anggota 3): rekap materi, tugas, presensi, nilai, catatan
        dari seluruh sistem (read-only — admin tidak bisa edit/buat ini)."""
        pass

    def tampilkan_menu(self):
        return ["Kelola Akun", "Kelola Jadwal", "Kelola Kelas", "Monitoring"]


# FUNGSI BANTU: ubah baris database (dict) jadi objek User yang tepat

def buat_objek_user(row):
    """row: hasil satu baris dari tabel users (sqlite3.Row atau dict).
    Dipakai login() di app.py supaya tidak perlu tahu role-nya apa dulu."""
    role = row["role"]
    if role == "siswa":
        return Siswa(row["id"], row["nama"], row["username"], row["password"],
                     row["kelas_id"] if "kelas_id" in row.keys() else None)
    elif role == "pengajar":
        return Pengajar(row["id"], row["nama"], row["username"], row["password"],
                         row["foto"], row["no_whatsapp"], row["biodata"])
    elif role == "admin":
        return Admin(row["id"], row["nama"], row["username"], row["password"])
    raise ValueError(f"Role tidak dikenal: {role}")
