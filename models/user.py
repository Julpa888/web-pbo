"""
models/user.py
Penanggung jawab utama: JULPA (Backend Auth) untuk class User & Admin.
Siswa & Pengajar: isi method sesuai TODO masing-masing (lihat nama di
komentar). Pola User.login()/cek_password() JANGAN diubah, karena app.py
sudah memanggilnya persis seperti ini.
"""

from abc import ABC, abstractmethod
import database
from models.akademik import Kelas, Jadwal


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
        """Jadwal kelas siswa ini (kosong kalau belum punya kelas)."""
        if self.kelas_id is None:
            return []
        return database.ambil_jadwal_by_kelas(self.kelas_id)

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

    def lihat_jadwal_mengajar(self):
        """Jadwal mengajar milik pengajar ini saja (dipakai route /pengajar/jadwal)."""
        return database.ambil_jadwal_by_pengajar(self.id)

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

    # ==================================================
    # ANGGOTA 1 — Kelola Kelas & Kelola Jadwal
    # Semua kegagalan validasi dilempar sebagai ValueError (pesannya siap
    # ditampilkan ke admin lewat flash di app.py).
    # ==================================================
    def kelola_kelas(self, aksi, **data):
        """Kelola kelas + siswa di dalamnya.

        aksi:
        - 'tambah'       -> data: nama_kelas, pengajar_id            (return id baru)
        - 'edit'         -> data: kelas_id, nama_kelas, pengajar_id
        - 'hapus'        -> data: kelas_id
        - 'tambah_siswa' -> data: kelas_id, siswa_id
        - 'hapus_siswa'  -> data: kelas_id, siswa_id
        """
        if aksi == "tambah":
            nama, pengajar_id = Kelas.cek_input(data["nama_kelas"], data["pengajar_id"])
            return database.tambah_kelas(nama, pengajar_id)

        kelas = Kelas.muat(data["kelas_id"])  # semua aksi di bawah butuh kelasnya ada

        if aksi == "edit":
            nama, pengajar_id = Kelas.cek_input(
                data["nama_kelas"], data["pengajar_id"], exclude_id=kelas.id
            )
            return database.edit_kelas(kelas.id, nama, pengajar_id)

        elif aksi == "hapus":
            terkait = database.hitung_data_terkait_kelas(kelas.id)
            if any(terkait.values()):
                raise ValueError(
                    f"Kelas '{kelas.nama_kelas}' tidak bisa dihapus karena masih punya "
                    f"{terkait['materi']} materi, {terkait['tugas']} tugas, dan "
                    f"{terkait['presensi']} data presensi."
                )
            return database.hapus_kelas(kelas.id)

        elif aksi == "tambah_siswa":
            return kelas.tambah_siswa(data["siswa_id"])

        elif aksi == "hapus_siswa":
            return kelas.hapus_siswa(data["siswa_id"])

        else:
            raise ValueError(f"Aksi tidak dikenal: {aksi}")

    def kelola_jadwal(self, aksi, **data):
        """Kelola jadwal kelas (hari, jam, pengajar).

        aksi:
        - 'tambah' -> data: hari, jam_mulai, jam_selesai, kelas_id, pengajar_id
        - 'edit'   -> data: jadwal_id + field yang sama seperti 'tambah'
        - 'hapus'  -> data: jadwal_id
        jam_mulai/jam_selesai berformat 'HH:MM' atau 'HH.MM'.
        """
        if aksi == "tambah":
            kelas_id, pengajar_id, jam = Jadwal.cek_input(
                data["hari"], data["jam_mulai"], data["jam_selesai"],
                data["kelas_id"], data["pengajar_id"],
            )
            return database.tambah_jadwal(data["hari"], jam, kelas_id, pengajar_id)

        # edit & hapus: pastikan jadwalnya ada
        try:
            jadwal_id = int(data["jadwal_id"])
        except (TypeError, ValueError):
            raise ValueError("Jadwal tidak valid.")
        if database.ambil_jadwal_by_id(jadwal_id) is None:
            raise ValueError("Jadwal tidak ditemukan.")

        if aksi == "edit":
            kelas_id, pengajar_id, jam = Jadwal.cek_input(
                data["hari"], data["jam_mulai"], data["jam_selesai"],
                data["kelas_id"], data["pengajar_id"], exclude_id=jadwal_id,
            )
            return database.edit_jadwal(jadwal_id, data["hari"], jam, kelas_id, pengajar_id)

        elif aksi == "hapus":
            return database.hapus_jadwal(jadwal_id)

        else:
            raise ValueError(f"Aksi tidak dikenal: {aksi}")

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