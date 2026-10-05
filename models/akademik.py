"""
models/akademik.py
Kelas -> ANGGOTA 1
Materi, Tugas, Pengumpulan, Komentar -> ANGGOTA 2 (Materi/Tugas) & ANGGOTA 3 (Pengumpulan nilai)
Jadwal -> ANGGOTA 1

Nama method mengikuti tabel class diagram terbaru. Isi bertahap sesuai TODO.
"""

from datetime import date
import database

HARI_VALID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# ======================================================
# FUNGSI BANTU (ANGGOTA 1)
# ======================================================
def _ke_int(nilai, nama):
    try:
        return int(nilai)
    except (TypeError, ValueError):
        raise ValueError(f"{nama} tidak valid.")


def _ke_menit(teks):
    """'15.00' atau '15:00' -> 900 (menit sejak tengah malam)."""
    try:
        jam, menit = str(teks).strip().replace(":", ".").split(".")
        jam, menit = int(jam), int(menit)
    except (ValueError, AttributeError):
        raise ValueError("Format jam tidak valid.")
    if not (0 <= jam <= 23 and 0 <= menit <= 59):
        raise ValueError("Format jam tidak valid.")
    return jam * 60 + menit


# ======================================================
# ANGGOTA 1 — Kelas
# ======================================================
class Kelas:
    def __init__(self, id, nama_kelas, pengajar_id):
        self.id = id
        self.nama_kelas = nama_kelas
        self.pengajar_id = pengajar_id
        self.daftar_siswa = []       # berisi id siswa

    # ---------- membangun objek dari database ----------
    @classmethod
    def dari_row(cls, row):
        kelas = cls(row["id"], row["nama"], row["pengajar_id"])
        kelas.daftar_siswa = [s["id"] for s in database.ambil_siswa_by_kelas(row["id"])]
        return kelas

    @classmethod
    def muat(cls, kelas_id):
        """Ambil kelas dari database. ValueError kalau tidak ada."""
        row = database.ambil_kelas_by_id(_ke_int(kelas_id, "Kelas"))
        if row is None:
            raise ValueError("Kelas tidak ditemukan.")
        return cls.dari_row(row)

    # ---------- validasi input form ----------
    @staticmethod
    def cek_input(nama_kelas, pengajar_id, exclude_id=None):
        """Validasi nama & pengajar. Mengembalikan (nama_bersih, pengajar_id_int)."""
        nama = (nama_kelas or "").strip()
        if not nama:
            raise ValueError("Nama kelas tidak boleh kosong.")
        pengajar_id = _ke_int(pengajar_id, "Pengajar")
        pengajar = database.ambil_user_by_id(pengajar_id)
        if pengajar is None or pengajar["role"] != "pengajar":
            raise ValueError("Pengajar tidak valid.")
        kembar = database.ambil_kelas_by_nama(nama)
        if kembar is not None and kembar["id"] != exclude_id:
            raise ValueError(f"Kelas dengan nama '{nama}' sudah ada.")
        return nama, pengajar_id

    # ---------- method sesuai class diagram ----------
    def tambah_siswa(self, siswa):
        """siswa: objek Siswa atau id (int). Satu siswa hanya boleh di satu kelas."""
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


# ======================================================
# ANGGOTA 1 — Jadwal
# ======================================================
class Jadwal:
    def __init__(self, id, hari, jam, kelas_id, pengajar_id):
        self.id = id
        self.hari = hari
        self.jam = jam               # teks, contoh "15.00 - 16.30"
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id

    def get_info_jadwal(self):
        """Contoh hasil: 'Senin, 15.00 - 16.30'."""
        return f"{self.hari}, {self.jam}"

    # ---------- format jam ----------
    @staticmethod
    def format_jam(mulai, selesai):
        """Menit -> '15.00 - 16.30'."""
        return f"{mulai // 60:02d}.{mulai % 60:02d} - {selesai // 60:02d}.{selesai % 60:02d}"

    @staticmethod
    def parse_jam(jam):
        """'15.00 - 16.30' -> (900, 990)."""
        try:
            awal, akhir = jam.split(" - ")
        except (ValueError, AttributeError):
            raise ValueError("Format jam tidak valid.")
        return _ke_menit(awal), _ke_menit(akhir)

    @staticmethod
    def pecah_jam(jam):
        """'15.00 - 16.30' -> ('15:00', '16:30'), untuk isi <input type="time">."""
        mulai, selesai = Jadwal.parse_jam(jam)
        return f"{mulai // 60:02d}:{mulai % 60:02d}", f"{selesai // 60:02d}:{selesai % 60:02d}"

    # ---------- validasi input form ----------
    @staticmethod
    def cek_input(hari, jam_mulai, jam_selesai, kelas_id, pengajar_id, exclude_id=None):
        """Validasi lengkap + cek bentrok.
        Mengembalikan (kelas_id_int, pengajar_id_int, jam_teks)."""
        if hari not in HARI_VALID:
            raise ValueError("Hari tidak valid.")
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

        # cek bentrok: jadwal lain di hari yang sama dengan jam yang beririsan
        for j in database.ambil_jadwal_by_hari(hari):
            if exclude_id is not None and j["id"] == exclude_id:
                continue
            try:
                mulai_lain, selesai_lain = Jadwal.parse_jam(j["jam"])
            except ValueError:
                continue  # data lama dengan format aneh, lewati
            if mulai < selesai_lain and mulai_lain < selesai:
                if j["kelas_id"] == kelas_id:
                    raise ValueError(
                        f"Bentrok: kelas {j['kelas_nama']} sudah punya jadwal "
                        f"{j['hari']} {j['jam']}."
                    )
                if j["pengajar_id"] == pengajar_id:
                    raise ValueError(
                        f"Bentrok: {j['pengajar_nama']} sudah mengajar kelas "
                        f"{j['kelas_nama']} pada {j['hari']} {j['jam']}."
                    )
        return kelas_id, pengajar_id, Jadwal.format_jam(mulai, selesai)


# ======================================================
# ANGGOTA 2 & 3 — di bawah ini JANGAN diubah Anggota 1
# ======================================================
class Materi:
    def __init__(self, id, judul, kategori, file_path, kelas_id, pengajar_id):
        self.id = id
        self.judul = judul
        self.kategori = kategori
        self.file_path = file_path
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id

    def get_file_url(self):
        """TODO (Anggota 2): kembalikan URL/path untuk tombol download
        (dipakai Siswa & Pengajar, jadi cukup satu tempat di sini)."""
        pass


class Tugas:
    def __init__(self, id, judul, deskripsi, deadline, kelas_id, pengajar_id):
        self.id = id
        self.judul = judul
        self.deskripsi = deskripsi
        self.deadline = deadline   # objek date
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id

    def is_expired(self):
        """TODO (Anggota 2): True kalau date.today() > self.deadline."""
        pass


class Pengumpulan:
    def __init__(self, id, tugas_id, siswa_id, file_jawaban=None, nilai=None, waktu_kumpul=None):
        self.id = id
        self.tugas_id = tugas_id   # asosiasi
        self.siswa_id = siswa_id   # asosiasi
        self.file_jawaban = file_jawaban
        self.nilai = nilai
        self.waktu_kumpul = waktu_kumpul

    def submit_jawaban(self, file_jawaban):
        """TODO (Anggota 2): set self.file_jawaban & self.waktu_kumpul,
        simpan ke database. Dipanggil dari Siswa.kumpul_tugas()."""
        pass

    def beri_nilai(self, nilai):
        """TODO (Anggota 3): validasi 0-100, set self.nilai, simpan ke
        database. Dipanggil dari Pengajar.beri_nilai()."""
        pass


class Komentar:
    def __init__(self, id, tugas_id, user_id, isi_komentar, waktu):
        self.id = id
        self.tugas_id = tugas_id   # asosiasi
        self.user_id = user_id     # asosiasi: Siswa atau Pengajar
        self.isi_komentar = isi_komentar
        self.waktu = waktu

    def tambah_komentar(self):
        """TODO (Anggota 2): simpan komentar ini ke database.
        Dipanggil dari Siswa.komentar_tugas() / Pengajar.komentar_tugas()."""
        pass

    @staticmethod
    def get_list_komentar(tugas_id):
        """TODO (Anggota 2): ambil semua komentar untuk satu tugas,
        urut berdasarkan waktu."""
        pass