# PEMBAGIAN TUGAS DI models/akademik.py
# Kelas -> ANGGOTA 1
# Materi, Tugas, Pengumpulan, Komentar -> ANGGOTA 2 & 3
# Jadwal -> ANGGOTA 1

from datetime import date, datetime
import database

HARI_VALID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _ke_int(nilai, nama):
    try:
        return int(nilai)
    except (TypeError, ValueError):
        raise ValueError(f"{nama} tidak valid.")


def _ke_menit(teks):
    try:
        jam, menit = str(teks).strip().replace(":", ".").split(".")
        jam, menit = int(jam), int(menit)
    except (ValueError, AttributeError):
        raise ValueError("Format jam tidak valid.")
    if not (0 <= jam <= 23 and 0 <= menit <= 59):
        raise ValueError("Format jam tidak valid.")
    return jam * 60 + menit


class Kelas:
    def __init__(self, id, nama_kelas, pengajar_id, pengajar_id2=None):
        self.id = id
        self.nama_kelas = nama_kelas
        self.pengajar_id = pengajar_id
        self.pengajar_id2 = pengajar_id2  # guru ke-2 (opsional)
        self.daftar_siswa = []

    @classmethod
    def dari_row(cls, row):
        nama = row["nama"] if "nama" in row.keys() else row["nama_kelas"]
        pengajar_id2 = row["pengajar_id2"] if "pengajar_id2" in row.keys() else None
        kelas = cls(row["id"], nama, row["pengajar_id"], pengajar_id2)
        kelas.daftar_siswa = [s["id"] for s in database.ambil_siswa_by_kelas(row["id"])]
        return kelas

    @classmethod
    def muat(cls, kelas_id):
        row = database.ambil_kelas_by_id(_ke_int(kelas_id, "Kelas"))
        if row is None:
            raise ValueError("Kelas tidak ditemukan.")
        return cls.dari_row(row)

    @staticmethod
    def cek_input(nama_kelas, pengajar_id, pengajar_id2=None, exclude_id=None):
        nama = (nama_kelas or "").strip()
        if not nama:
            raise ValueError("Nama kelas tidak boleh kosong.")

        pengajar_id = _ke_int(pengajar_id, "Pengajar")
        pengajar = database.ambil_user_by_id(pengajar_id)
        if pengajar is None or pengajar["role"] != "pengajar":
            raise ValueError("Pengajar tidak valid.")

        # guru ke-2 boleh kosong
        if pengajar_id2 in (None, "", 0, "0"):
            pengajar_id2 = None
        else:
            pengajar_id2 = _ke_int(pengajar_id2, "Pengajar ke-2")
            if pengajar_id2 == pengajar_id:
                raise ValueError("Pengajar ke-2 tidak boleh sama dengan pengajar pertama.")
            pengajar2 = database.ambil_user_by_id(pengajar_id2)
            if pengajar2 is None or pengajar2["role"] != "pengajar":
                raise ValueError("Pengajar ke-2 tidak valid.")

        kembar = database.ambil_kelas_by_nama(nama)
        if kembar is not None and kembar["id"] != exclude_id:
            raise ValueError(f"Kelas dengan nama '{nama}' sudah ada.")
        return nama, pengajar_id, pengajar_id2

    def tambah_siswa(self, siswa):
        siswa_id = _ke_int(getattr(siswa, "id", siswa), "Siswa")
        row = database.ambil_user_by_id(siswa_id)
        if row is None or row["role"] != "siswa":
            raise ValueError("Siswa tidak ditemukan.")
        kelas_lain = database.ambil_kelas_siswa(siswa_id)
        if kelas_lain is not None:
            if kelas_lain["id"] == self.id:
                raise ValueError(f"{row['nama']} sudah ada di kelas ini.")
            raise ValueError(
                f"{row['nama']} sudah terdaftar di kelas {kelas_lain['nama']}. "
                "Keluarkan dulu dari kelas tersebut."
            )
        database.tambah_siswa_ke_kelas(self.id, siswa_id)
        self.daftar_siswa.append(siswa_id)

    def hapus_siswa(self, siswa):
        siswa_id = _ke_int(getattr(siswa, "id", siswa), "Siswa")
        if siswa_id not in self.daftar_siswa:
            raise ValueError("Siswa tidak ada di kelas ini.")
        database.hapus_siswa_dari_kelas(self.id, siswa_id)
        self.daftar_siswa.remove(siswa_id)

    def get_total_siswa(self):
        return len(self.daftar_siswa)


class Jadwal:
    def __init__(self, id, hari, jam, kelas_id, pengajar_id, tanggal=None, materi=None):
        self.id = id
        self.hari = hari
        self.jam = jam
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id
        self.tanggal = tanggal
        self.materi = materi

    def get_info_jadwal(self):
        return f"{self.hari}, {self.jam}"

    @staticmethod
    def format_jam(mulai, selesai):
        return f"{mulai // 60:02d}.{mulai % 60:02d} - {selesai // 60:02d}.{selesai % 60:02d}"

    @staticmethod
    def parse_jam(jam):
        try:
            awal, akhir = jam.split(" - ")
        except (ValueError, AttributeError):
            raise ValueError("Format jam tidak valid.")
        return _ke_menit(awal), _ke_menit(akhir)

    @staticmethod
    def pecah_jam(jam):
        mulai, selesai = Jadwal.parse_jam(jam)
        return f"{mulai // 60:02d}:{mulai % 60:02d}", f"{selesai // 60:02d}:{selesai % 60:02d}"

    @staticmethod
    def cek_input(hari, jam_mulai, jam_selesai, kelas_id, pengajar_id, exclude_id=None,
                  tanggal=None, materi=None):
        if hari not in HARI_VALID:
            raise ValueError("Hari tidak valid.")

        tanggal = (tanggal or "").strip()
        tgl = None
        if tanggal:
            try:
                tgl = datetime.strptime(tanggal, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Format tanggal tidak valid.")
            if HARI_VALID[tgl.weekday()] != hari:
                raise ValueError(
                    f"Tanggal {tgl.strftime('%d-%m-%Y')} jatuh pada hari {HARI_VALID[tgl.weekday()]}, "
                    f"bukan {hari}."
                )
        materi = (materi or "").strip() or None

        mulai = _ke_menit(jam_mulai)
        selesai = _ke_menit(jam_selesai)
        if mulai >= selesai:
            raise ValueError("Jam selesai harus lebih besar dari jam mulai.")

        kelas_id = _ke_int(kelas_id, "Kelas")
        pengajar_id = _ke_int(pengajar_id, "Pengajar")
        if database.ambil_kelas_by_id(kelas_id) is None:
            raise ValueError("Kelas tidak ditemukan.")
        pengajar = database.ambil_user_by_id(pengajar_id)
        if pengajar is None or pengajar["role"] != "pengajar":
            raise ValueError("Pengajar tidak valid.")

        # bentrok dicek pada tanggal yang sama
        if tanggal:
            kandidat = database.ambil_jadwal_by_tanggal(tanggal)
        else:
            kandidat = [j for j in database.ambil_jadwal_by_hari(hari) if not j["tanggal"]]
        for j in kandidat:
            if exclude_id is not None and j["id"] == exclude_id:
                continue
            try:
                mulai_lain, selesai_lain = Jadwal.parse_jam(j["jam"])
            except ValueError:
                continue
            if mulai < selesai_lain and mulai_lain < selesai:
                if j["kelas_id"] == kelas_id:
                    raise ValueError(
                        f"Bentrok: kelas {j['kelas_nama']} sudah punya jadwal {j['hari']} {j['jam']}."
                    )
                if j["pengajar_id"] == pengajar_id:
                    raise ValueError(
                        f"Bentrok: {j['pengajar_nama']} sudah mengajar kelas {j['kelas_nama']} pada {j['hari']} {j['jam']}."
                    )
        return kelas_id, pengajar_id, Jadwal.format_jam(mulai, selesai), (tanggal or None), materi


class Materi:
    def __init__(self, id, judul, kategori, file_path, kelas_id, pengajar_id):
        self.id = id
        self.judul = judul
        self.kategori = kategori
        self.file_path = file_path
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id

    def get_file_url(self):
        return f"/uploads/{self.file_path}"


class Tugas:
    def __init__(self, id, judul, deskripsi, deadline, kelas_id, pengajar_id):
        self.id = id
        self.judul = judul
        self.deskripsi = deskripsi
        self.deadline = deadline
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id

    def is_expired(self):
        return date.today() > self.deadline


class Pengumpulan:
    def __init__(self, id, tugas_id, siswa_id, file_jawaban=None, nilai=None, waktu_kumpul=None):
        self.id = id
        self.tugas_id = tugas_id
        self.siswa_id = siswa_id
        self.file_jawaban = file_jawaban
        self.nilai = nilai
        self.waktu_kumpul = waktu_kumpul

    def submit_jawaban(self, file_jawaban):
        pass

    def beri_nilai(self, nilai):
        pass


class Komentar:
    def __init__(self, id, tugas_id, user_id, isi_komentar, waktu):
        self.id = id
        self.tugas_id = tugas_id
        self.user_id = user_id
        self.isi_komentar = isi_komentar
        self.waktu = waktu

    def tambah_komentar(self):
        pass

    @staticmethod
    def get_list_komentar(tugas_id):
        pass