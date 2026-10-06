"""
models/user.py
Penanggung jawab utama: JULPA (Backend Auth) untuk class User & Admin.
"""

from abc import ABC, abstractmethod
import re
import database


class User(ABC):
    """Class dasar (abstract) untuk semua jenis akun di sistem."""

    def __init__(self, id, nama, username, password, role):
        self.id = id
        self.nama = nama
        self.username = username
        self.__password = password 
        self.role = role  # Atribut role ditambahkan di sini

    def cek_password(self, password):
        """Satu-satunya cara mengecek password dari luar class."""
        return self.__password == password

    @staticmethod
    def validasi_username(username):
        """Username minimal 5 karakter."""
        return len(username or "") >= 5

    @staticmethod
    def validasi_password(password):
        """Password minimal 8 karakter, wajib kombinasi huruf dan angka."""
        pwd = password or ""
        if len(pwd) < 8:
            return False
        has_letter = re.search(r'[a-zA-Z]', pwd)
        has_digit = re.search(r'\d', pwd)
        return bool(has_letter and has_digit)

    @abstractmethod
    def tampilkan_menu(self):
        """Wajib di-override di tiap class turunan (POLYMORPHISM)."""
        pass


class Siswa(User):
    def __init__(self, id, nama, username, password, kelas_id=None):
        super().__init__(id, nama, username, password, role="siswa")
        self.kelas_id = kelas_id

    def lihat_jadwal(self):
        if self.kelas_id is None:
            return []
        return database.ambil_jadwal_by_kelas(self.kelas_id)

    def kumpul_tugas(self, tugas, jawaban):
        pass

    def komentar_tugas(self, tugas, isi):
        pass

    def lihat_monitoring(self):
        pass

    def tampilkan_menu(self):
        return ["Jadwal", "Materi", "Tugas", "Monitoring Anak"]


class Pengajar(User):
    def __init__(self, id, nama, username, password, foto=None, whatsapp=None, biodata=None):
        super().__init__(id, nama, username, password, role="pengajar")
        self.foto = foto or "default_avatar.png"
        self.whatsapp = whatsapp
        self.biodata = biodata

    @staticmethod
    def validasi_whatsapp(nomor):
        clean_num = re.sub(r'\D', '', nomor or "")
        return len(clean_num) >= 10

    def edit_profil(self, foto=None, whatsapp=None, biodata=None):
        if foto:
            self.foto = foto
        if whatsapp:
            self.whatsapp = whatsapp
        if biodata:
            self.biodata = biodata

    def lihat_jadwal_mengajar(self):
        return database.ambil_jadwal_by_pengajar(self.id)

    def upload_materi(self, kelas, judul, kategori, file):
        pass

    def buat_tugas(self, kelas, judul, deskripsi, deadline):
        pass

    def beri_nilai(self, pengumpulan, nilai):
        pass

    def komentar_tugas(self, tugas, isi):
        pass

    def catat_presensi(self, kelas, siswa, status):
        pass

    def tampilkan_menu(self):
        return ["Profil", "Jadwal Mengajar", "Materi", "Tugas", "Presensi"]


class Admin(User):
    def __init__(self, id, nama, username, password):
        super().__init__(id, nama, username, password, role="admin")

    def kelola_akun(self, aksi, **data):
        if aksi == "tambah":
            username = data.get("username")
            password = data.get("password")
            role = data.get("role")
            no_wa = data.get("whatsapp")

            if not User.validasi_username(username):
                raise ValueError("Username minimal 5 karakter.")
            if not User.validasi_password(password):
                raise ValueError("Password minimal 8 karakter dan wajib kombinasi huruf + angka.")
            if role == "pengajar" and no_wa and not Pengajar.validasi_whatsapp(no_wa):
                raise ValueError("Nomor WhatsApp tidak valid (minimal 10 angka).")

            kelas_id = None
            if role == "siswa":
                if not database.ambil_semua_kelas():
                    raise ValueError("Belum ada kelas. Buat kelas terlebih dahulu sebelum membuat akun siswa.")
                try:
                    kelas_id = int(data.get("kelas_id"))
                except (TypeError, ValueError):
                    raise ValueError("Pilih kelas untuk siswa.")
                if database.ambil_kelas_by_id(kelas_id) is None:
                    raise ValueError("Kelas yang dipilih tidak ditemukan.")

            return database.tambah_user(
                nama=data["nama"],
                username=username,
                password=password,
                role=role,
                foto=data.get("foto"),
                no_whatsapp=no_wa,
                biodata=data.get("biodata"),
                kelas_id=kelas_id,
            )
        elif aksi == "edit":
            try:
                user_id = int(data["user_id"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Akun tidak valid.")
            target = database.ambil_user_by_id(user_id)
            if target is None or target["role"] == "admin":
                raise ValueError("Akun tidak ditemukan.")

            username = (data.get("username") or "").strip()
            password = data.get("password")
            no_wa = data.get("whatsapp")
            nama = (data.get("nama") or "").strip()

            if not nama:
                raise ValueError("Nama lengkap wajib diisi.")
            if not User.validasi_username(username):
                raise ValueError("Username minimal 5 karakter.")
            if password and not User.validasi_password(password):
                raise ValueError("Password minimal 8 karakter dan wajib kombinasi huruf + angka.")

            perubahan = {"nama": nama, "username": username}
            if password:  # kosong = password tidak diubah
                perubahan["password"] = password
            if target["role"] == "pengajar":
                if no_wa and not Pengajar.validasi_whatsapp(no_wa):
                    raise ValueError("Nomor WhatsApp tidak valid (minimal 10 angka).")
                perubahan["no_whatsapp"] = no_wa or None
                if data.get("foto"):
                    perubahan["foto"] = data["foto"]
            return database.edit_user(user_id, **perubahan)
        elif aksi == "hapus":
            return database.hapus_user(data["user_id"])
        else:
            raise ValueError(f"Aksi tidak dikenal: {aksi}")

    def kelola_kelas(self, aksi, **data):
        from models.akademik import Kelas
        if aksi == "tambah":
            nama, pengajar_id, pengajar_id2 = Kelas.cek_input(
                data["nama_kelas"], data["pengajar_id"], data.get("pengajar_id2")
            )
            return database.tambah_kelas(nama, pengajar_id, pengajar_id2)

        kelas = Kelas.muat(data["kelas_id"])

        if aksi == "edit":
            nama, pengajar_id, pengajar_id2 = Kelas.cek_input(
                data["nama_kelas"], data["pengajar_id"], data.get("pengajar_id2"), exclude_id=kelas.id
            )
            return database.edit_kelas(kelas.id, nama, pengajar_id, pengajar_id2)

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
        from models.akademik import Jadwal
        if aksi == "tambah":
            kelas_id, pengajar_id, jam, tanggal, materi = Jadwal.cek_input(
                data["hari"], data["jam_mulai"], data["jam_selesai"],
                data["kelas_id"], data["pengajar_id"],
                tanggal=data.get("tanggal"), materi=data.get("materi"),
            )
            return database.tambah_jadwal(data["hari"], jam, kelas_id, pengajar_id, tanggal, materi)

        try:
            jadwal_id = int(data["jadwal_id"])
        except (TypeError, ValueError):
            raise ValueError("Jadwal tidak valid.")
            
        if database.ambil_jadwal_by_id(jadwal_id) is None:
            raise ValueError("Jadwal tidak ditemukan.")

        if aksi == "edit":
            kelas_id, pengajar_id, jam, tanggal, materi = Jadwal.cek_input(
                data["hari"], data["jam_mulai"], data["jam_selesai"],
                data["kelas_id"], data["pengajar_id"], exclude_id=jadwal_id,
                tanggal=data.get("tanggal"), materi=data.get("materi"),
            )
            return database.edit_jadwal(jadwal_id, data["hari"], jam, kelas_id, pengajar_id, tanggal, materi)

        elif aksi == "hapus":
            return database.hapus_jadwal(jadwal_id)

        else:
            raise ValueError(f"Aksi tidak dikenal: {aksi}")

    def monitoring_sistem(self):
        pass

    def tampilkan_menu(self):
        return ["Kelola Akun", "Kelola Jadwal", "Kelola Kelas", "Monitoring"]


def buat_objek_user(row):
    if not row:
        return None
    role = row["role"]
    no_wa = row["no_whatsapp"] if "no_whatsapp" in row.keys() else (row["whatsapp"] if "whatsapp" in row.keys() else None)
    foto = row["foto"] if "foto" in row.keys() else "default_avatar.png"
    biodata = row["biodata"] if "biodata" in row.keys() else None
    kelas_id = row["kelas_id"] if "kelas_id" in row.keys() else None

    if role == "siswa":
        return Siswa(row["id"], row["nama"], row["username"], row["password"], kelas_id)
    elif role == "pengajar":
        return Pengajar(row["id"], row["nama"], row["username"], row["password"], foto, no_wa, biodata)
    elif role == "admin":
        return Admin(row["id"], row["nama"], row["username"], row["password"])
    raise ValueError(f"Role tidak dikenal: {role}")