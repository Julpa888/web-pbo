# PEMBAGIAN TUGAS DI models/user.py
# Penanggung jawab utama: JULPA (Backend Auth) untuk class User & Admin.

from abc import ABC, abstractmethod
import re
import database


# ABSTRACTION: User jadi kerangka dasar, ga boleh dibuat objeknya langsung (ABC)
class User(ABC):
    def __init__(self, id, nama, username, password, role):
        self.id = id
        self.nama = nama
        self.username = username
        # ENCAPSULATION: password private (__), dari luar class ga bisa diutak-atik
        self.__password = password
        self.role = role

    # ENCAPSULATION: cuma bisa dicek lewat method ini, nilainya ga pernah keluar
    def cek_password(self, password):
        return self.__password == password

    # ENCAPSULATION: satu-satunya pintu buat ganti password, lama diverifikasi dulu
    def ganti_password(self, password_lama, password_baru):
        if not self.cek_password(password_lama):
            raise ValueError("Password lama salah.")
        if not User.validasi_password(password_baru):
            raise ValueError("Password minimal 8 karakter dan wajib kombinasi huruf + angka.")
        if password_baru == password_lama:
            raise ValueError("Password baru tidak boleh sama dengan password lama.")
        database.edit_user(self.id, password=password_baru)
        self.__password = password_baru

    # ENCAPSULATION: aturan validasi ditaruh di class-nya sendiri
    @staticmethod
    def validasi_username(username):
        return len(username or "") >= 5

    @staticmethod
    def validasi_password(password):
        pwd = password or ""
        if len(pwd) < 8:
            return False
        has_letter = re.search(r'[a-zA-Z]', pwd)
        has_digit = re.search(r'\d', pwd)
        return bool(has_letter and has_digit)

    @staticmethod
    def validasi_email(email):
        return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email or ""))

    # ABSTRACTION: wajib ditulis ulang di tiap subclass
    @abstractmethod
    def tampilkan_menu(self):
        pass


# INHERITANCE: Siswa turunan User, id/nama/username/cek_password ikut diwarisi
class Siswa(User):
    def __init__(self, id, nama, username, password, kelas_id=None):
        super().__init__(id, nama, username, password, role="siswa")
        self.kelas_id = kelas_id

    def lihat_profil(self):
        kelas = database.ambil_kelas_siswa(self.id)
        return {
            "id": self.id,
            "nama": self.nama,
            "username": self.username,
            "kelas": kelas["nama"] if kelas else "-",
        }

    def lihat_kelas(self):
        # TODO (Anggota 1): kelas yang diikuti beserta nama pengajarnya
        pass

    def lihat_jadwal(self):
        if self.kelas_id is None:
            return []
        return database.ambil_jadwal_by_kelas(self.kelas_id)

    def kumpul_tugas(self, tugas, jawaban):
        # TODO (Anggota 2): kumpulkan jawaban tugas
        pass

    def komentar_tugas(self, tugas, isi):
        # TODO (Anggota 2): komentar di tugas
        pass

    def lihat_monitoring(self):
        # TODO (Anggota 3): rekap presensi, rekap nilai, dan catatan akhir
        pass

    # POLYMORPHISM: tampilkan_menu() di-override, isinya menu khusus siswa
    def tampilkan_menu(self):
        return ["Profil", "Kelas", "Jadwal", "Materi", "Tugas", "Monitoring Anak"]


# INHERITANCE: Pengajar juga turunan User, plus atribut sendiri (foto, wa, alamat, email, nik)
class Pengajar(User):
    def __init__(self, id, nama, username, password, foto=None, whatsapp=None,
                 biodata=None, alamat=None, email=None, nik=None):
        super().__init__(id, nama, username, password, role="pengajar")
        self.foto = foto or "default_avatar.png"
        self.whatsapp = whatsapp
        self.biodata = biodata
        self.alamat = alamat
        self.email = email
        self.nik = nik

    @staticmethod
    def validasi_whatsapp(nomor):
        clean_num = re.sub(r'\D', '', nomor or "")
        return len(clean_num) >= 10

    @staticmethod
    def validasi_nik(nik):
        return bool(re.fullmatch(r'\d{16}', (nik or "").strip()))

    @staticmethod
    def cek_data_admin(whatsapp, alamat, nik):
        """Data pengajar yang diisi admin: WA, alamat, NIK semuanya wajib."""
        whatsapp = (whatsapp or "").strip()
        alamat = (alamat or "").strip()
        nik = (nik or "").strip()
        if not whatsapp or not Pengajar.validasi_whatsapp(whatsapp):
            raise ValueError("Nomor WhatsApp wajib diisi dan valid (minimal 10 angka).")
        if not alamat:
            raise ValueError("Alamat pengajar wajib diisi.")
        if not Pengajar.validasi_nik(nik):
            raise ValueError("Nomor KTP harus 16 digit angka.")
        return whatsapp, alamat, nik

    def lihat_profil(self):
        """Profil lengkap (alamat & NIK ikut). Hanya buat admin dan pengajar ybs."""
        return {
            "id": self.id, "nama": self.nama, "username": self.username,
            "foto": self.foto, "whatsapp": self.whatsapp, "email": self.email,
            "biodata": self.biodata, "alamat": self.alamat, "nik": self.nik,
        }

    def profil_publik(self):
        """Versi buat siswa: tanpa alamat dan NIK."""
        return {
            "id": self.id, "nama": self.nama, "foto": self.foto,
            "whatsapp": self.whatsapp, "biodata": self.biodata,
        }

    def edit_profil(self, whatsapp, email="", foto=None):
        # WA wajib & valid, email boleh kosong tapi kalau diisi harus valid
        whatsapp = (whatsapp or "").strip()
        email = (email or "").strip()
        if not whatsapp or not Pengajar.validasi_whatsapp(whatsapp):
            raise ValueError("Nomor WhatsApp wajib diisi dan valid (minimal 10 angka).")
        if email and not User.validasi_email(email):
            raise ValueError("Format email tidak valid.")

        perubahan = {"no_whatsapp": whatsapp, "email": email or None}
        if foto:
            perubahan["foto"] = foto
        database.edit_user(self.id, **perubahan)

        self.whatsapp = whatsapp
        self.email = email or None
        if foto:
            self.foto = foto

    def lihat_jadwal_mengajar(self):
        return database.ambil_jadwal_by_pengajar(self.id)

    def upload_materi(self, kelas, judul, kategori, file):
        # TODO (Anggota 2): upload materi ke kelas
        pass

    def buat_tugas(self, kelas, judul, deskripsi, deadline):
        # TODO (Anggota 2): buat tugas untuk kelas
        pass

    def beri_nilai(self, pengumpulan, nilai):
        # TODO (Anggota 3): beri nilai ke pengumpulan tugas siswa
        pass

    def komentar_tugas(self, tugas, isi):
        # TODO (Anggota 2): komentar di tugas (dipakai juga buat masukan per pertemuan)
        pass

    def catat_presensi(self, kelas, siswa, status):
        # TODO (Anggota 4): catat presensi siswa
        pass

    def beri_catatan_akhir(self, kelas, siswa, isi):
        # TODO (Anggota 3): tulis atau edit catatan akhir per siswa
        pass

    # POLYMORPHISM: nama method sama, isi menu beda dari Siswa
    def tampilkan_menu(self):
        return ["Profil", "Kelas dan Jadwal Mengajar", "Materi", "Tugas", "Presensi", "Catatan Akhir"]


# INHERITANCE: Admin turunan User juga
class Admin(User):
    def __init__(self, id, nama, username, password):
        super().__init__(id, nama, username, password, role="admin")

    def lihat_profil(self):
        return {"id": self.id, "nama": self.nama, "username": self.username}

    def kelola_akun(self, aksi, **data):
        if aksi == "tambah":
            username = data.get("username")
            password = data.get("password")
            role = data.get("role")

            if role not in ("siswa", "pengajar"):
                raise ValueError("Role harus siswa atau pengajar.")
            if not (data.get("nama") or "").strip():
                raise ValueError("Nama lengkap wajib diisi.")
            if not User.validasi_username(username):
                raise ValueError("Username minimal 5 karakter.")
            if not User.validasi_password(password):
                raise ValueError("Password minimal 8 karakter dan wajib kombinasi huruf + angka.")

            no_wa = alamat = nik = None
            if role == "pengajar":
                no_wa, alamat, nik = Pengajar.cek_data_admin(
                    data.get("whatsapp"), data.get("alamat"), data.get("nik")
                )

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
                nama=data["nama"].strip(),
                username=username,
                password=password,
                role=role,
                foto=data.get("foto"),
                no_whatsapp=no_wa,
                biodata=data.get("biodata"),
                kelas_id=kelas_id,
                alamat=alamat,
                nik=nik,
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
                no_wa, alamat, nik = Pengajar.cek_data_admin(
                    data.get("whatsapp"), data.get("alamat"), data.get("nik")
                )
                perubahan["no_whatsapp"] = no_wa
                perubahan["alamat"] = alamat
                perubahan["nik"] = nik
                if data.get("foto"):
                    perubahan["foto"] = data["foto"]
            return database.edit_user(user_id, **perubahan)
        elif aksi == "hapus":
            target = database.ambil_user_by_id(data["user_id"])
            if target is None or target["role"] == "admin":
                raise ValueError("Akun tidak ditemukan.")
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
        # TODO (Anggota 3): menu monitoring lengkap (materi, tugas, presensi, nilai, catatan akhir)
        pass

    # POLYMORPHISM: lagi-lagi override, menu admin
    def tampilkan_menu(self):
        return ["Kelola Akun", "Kelola Jadwal", "Kelola Kelas", "Monitoring"]


# dipanggil pas login / get_current_user, tinggal kasih row, objek yang cocok keluar sendiri
def buat_objek_user(row):
    if not row:
        return None
    keys = row.keys()
    role = row["role"]
    no_wa = row["no_whatsapp"] if "no_whatsapp" in keys else (row["whatsapp"] if "whatsapp" in keys else None)
    foto = row["foto"] if "foto" in keys else "default_avatar.png"
    biodata = row["biodata"] if "biodata" in keys else None
    kelas_id = row["kelas_id"] if "kelas_id" in keys else None
    alamat = row["alamat"] if "alamat" in keys else None
    email = row["email"] if "email" in keys else None
    nik = row["nik"] if "nik" in keys else None

    if role == "siswa":
        return Siswa(row["id"], row["nama"], row["username"], row["password"], kelas_id)
    elif role == "pengajar":
        return Pengajar(row["id"], row["nama"], row["username"], row["password"],
                        foto, no_wa, biodata, alamat, email, nik)
    elif role == "admin":
        return Admin(row["id"], row["nama"], row["username"], row["password"])
    raise ValueError(f"Role tidak dikenal: {role}")