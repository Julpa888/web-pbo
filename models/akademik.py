import os
import re
from datetime import date, datetime, time
import database

HARI_VALID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

# 3 gambar latar kartu kelas yang boleh dipilih admin
HEADER_KELAS = {
    "header_winter.png": "Winter",
    "header_autum.png": "Autumn",
    "header_spring.png": "Spring",
}
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]


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


def _punya(row, kolom):
    """Cek kolom ada di row sqlite (row.get() nggak ada di sqlite3.Row)."""
    return kolom in row.keys()


class Kelas:
    # data kelas (nama, 1-2 pengajar, daftar siswa) + aturan tambah/hapus

    def __init__(self, id, nama_kelas, pengajar_id, pengajar_id2=None, header=None):
        self.id = id
        self.nama_kelas = nama_kelas
        self.pengajar_id = pengajar_id
        self.pengajar_id2 = pengajar_id2  # guru ke-2 (opsional)
        self.header = header             
        self.daftar_siswa = []

    # dari_row() dan muat() menyembunyikan proses pengambilan dan pengolahan data kelas dari database menjadi objek Kelas.
    @classmethod
    def dari_row(cls, row):
        nama = row["nama"] if _punya(row, "nama") else row["nama_kelas"]
        pengajar_id2 = row["pengajar_id2"] if _punya(row, "pengajar_id2") else None
        header = row["header"] if _punya(row, "header") else None
        kelas = cls(row["id"], nama, row["pengajar_id"], pengajar_id2, header)
        kelas.daftar_siswa = [s["id"] for s in database.ambil_siswa_by_kelas(row["id"])]
        return kelas

    @classmethod
    def muat(cls, kelas_id):
        row = database.ambil_kelas_by_id(_ke_int(kelas_id, "Kelas"))
        if row is None:
            raise ValueError("Kelas tidak ditemukan.")
        return cls.dari_row(row)

    # exclude_id digunakan saat mengedit kelas agar kelas yang sedang diedit tidak dianggap sebagai kelas duplikat.
    @staticmethod
    def cek_input(nama_kelas, pengajar_id, pengajar_id2=None, exclude_id=None, header=None):
        nama = (nama_kelas or "").strip()
        if not nama:
            raise ValueError("Nama kelas tidak boleh kosong.")

        #background wajib dipilih, dan hanya boleh salah satu dari 3
        header = (header or "").strip()
        if not header:
            raise ValueError("Background kelas wajib dipilih.")
        if header not in HEADER_KELAS:
            raise ValueError("Background kelas yang dipilih tidak dikenal.")

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
        return nama, pengajar_id, pengajar_id2, header  # DIUBAH: + header

    def tambah_siswa(self, siswa):
        """siswa boleh objek Siswa atau id-nya."""
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

    # Menghitung jumlah siswa yang terdaftar di kelas.
    def get_total_siswa(self):
        return len(self.daftar_siswa)


class Jadwal:
    # hari, tanggal, jam, materi + aturan bentrok dibungkus di class Jadwal.
    def __init__(self, id, hari, jam, kelas_id, pengajar_id, tanggal=None, materi=None, pengganti_id=None):
        self.id = id
        self.hari = hari
        self.jam = jam
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id
        self.tanggal = tanggal
        self.materi = materi
        self.pengganti_id = pengganti_id

    @classmethod
    def dari_row(cls, row):
        return cls(row["id"], row["hari"], row["jam"], row["kelas_id"], row["pengajar_id"],
                   row["tanggal"] if _punya(row, "tanggal") else None,
                   row["materi"] if _punya(row, "materi") else None,
                   row["pengganti_id"] if _punya(row, "pengganti_id") else None)

    def get_info_jadwal(self):
        """'Senin, 5 Oktober 2026, 08.00 - 09.30' (tanpa tanggal: 'Senin, 08.00 - 09.30')."""
        if self.tanggal:
            try:
                d = datetime.strptime(self.tanggal, "%Y-%m-%d").date()
                return f"{self.hari}, {d.day} {BULAN[d.month - 1]} {d.year}, {self.jam}"
            except ValueError:
                pass
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
                  tanggal=None, materi=None, pengganti_id=None, ruangan=None):
        if hari not in HARI_VALID:
            raise ValueError("Hari tidak valid.")

        tanggal = (tanggal or "").strip()
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
        pengajar_id = _ke_int(pengajar_id, "Pengajar tetap")
        kelas = database.ambil_kelas_by_id(kelas_id)
        if kelas is None:
            raise ValueError("Kelas tidak ditemukan.")
        guru_tetap = (kelas["pengajar_id"], kelas["pengajar_id2"])
        if pengajar_id not in guru_tetap:
            raise ValueError("Pengajar tetap harus dipilih dari pengajar yang terdaftar pada kelas ini.")

        if pengganti_id in (None, "", 0, "0"):
            pengganti_id = None
        else:
            pengganti_id = _ke_int(pengganti_id, "Pengajar pengganti")
            pengganti = database.ambil_user_by_id(pengganti_id)
            if not pengganti or pengganti["role"] != "pengajar":
                raise ValueError("Pengajar pengganti tidak valid.")
            if pengganti_id in guru_tetap:
                raise ValueError("Pengajar pengganti harus berbeda dari pengajar tetap kelas.")

        if not tanggal:
            raise ValueError('Tanggal wajib diisi agar jadwal tidak bentrok.')
        ruangan = (ruangan or '').strip().upper()
        if ruangan not in ('A01', 'A02', 'A03'):
            raise ValueError('Ruangan wajib dipilih: A01, A02, atau A03.')

        # Bentrok dicek menurut tanggal, irisan jam, kelas, ruangan, dan pengajar
        # yang benar-benar bertugas (pengganti jika ada, bukan nama guru tetap).
        pengajar_aktif = pengganti_id or pengajar_id
        # Bentrok dicek pada tanggal yang sama; jadwal tanpa tanggal dianggap mingguan.
        kandidat = (database.ambil_jadwal_by_tanggal(tanggal) if tanggal else
                    [j for j in database.ambil_jadwal_by_hari(hari) if not j["tanggal"]])
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
                if j['ruangan'] and j['ruangan'] == ruangan:
                    raise ValueError(f"Ruangan {ruangan} sudah terpakai pada tanggal/jam tersebut.")
                pengajar_lain = j['pengganti_id'] or j['pengajar_id']
                if pengajar_aktif == pengajar_lain:
                    raise ValueError(f"Pengajar yang bertugas sudah memiliki jadwal lain pada {j['hari']} {j['jam']}.")
        return (kelas_id, pengajar_id, Jadwal.format_jam(mulai, selesai),
                (tanggal or None), materi, pengganti_id, ruangan)


class Materi:
    # atribut di sini sengaja publik karena cuma dibaca untuk ditampilkan.
    def __init__(self, id, judul, kategori, file_path, kelas_id, pengajar_id,
                 tanggal_upload=None, tanggal_edit=None):
        self.id = id
        self.judul = judul
        self.kategori = kategori
        self.file_path = file_path
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id
        self.tanggal_upload = tanggal_upload
        self.tanggal_edit = tanggal_edit

    @classmethod
    def dari_row(cls, row):
        return cls(row["id"], row["judul"], row["kategori"], row["file_path"],
                   row["kelas_id"], row["pengajar_id"],
                   row["tanggal_upload"] if _punya(row, "tanggal_upload") else None,
                   row["tanggal_edit"] if _punya(row, "tanggal_edit") else None)

    @classmethod
    def muat(cls, materi_id):
        row = database.ambil_materi_by_id(_ke_int(materi_id, "Materi"))
        if row is None:
            raise ValueError("Materi tidak ditemukan.")
        return cls.dari_row(row)

    def get_file_url(self):
        # file disimpan di static/uploads (lihat UPLOAD_FOLDER di app.py)
        return f"/static/uploads/{self.file_path}"

    def get_nama_asli(self):
        """Nama file tanpa awalan unik 8 karakter yang ditambah simpan_file() di app.py."""
        return re.sub(r"^[0-9a-f]{8}_", "", self.file_path or "")

    # urusan "file ini tipenya apa dan ukurannya berapa" ikut dibungkus
    # di class Materi, jadi template tinggal menampilkan, nggak ngitung sendiri.
    def get_tipe(self):
        """Ekstensi huruf besar buat label di halaman materi, contoh: 'PDF'."""
        ekstensi = os.path.splitext(self.file_path or "")[1].lstrip(".")
        return ekstensi.upper() or "FILE"

    def get_ukuran(self):
        """Ukuran file terbaca manusia ('1,2 MB'), atau '-' kalau filenya sudah tidak ada."""
        if not self.file_path:
            return "-"
        lokasi = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "static", "uploads", self.file_path)
        try:
            ukuran = os.path.getsize(lokasi)
        except OSError:
            return "-"
        for satuan in ("B", "KB", "MB", "GB"):
            if ukuran < 1024 or satuan == "GB":
                angka = f"{ukuran:.1f}".replace(".", ",") if satuan in ("MB", "GB") else f"{ukuran:.0f}"
                return f"{angka} {satuan}"
            ukuran /= 1024


class Tugas:
    FORMAT_DEADLINE = ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")

    def __init__(self, id, judul, deskripsi, deadline, kelas_id, pengajar_id,
                 tanggal_dibuat=None, tanggal_edit=None):
        self.id = id
        self.judul = judul
        self.deskripsi = deskripsi
        self.deadline = deadline  # string dari database (atau date/datetime)
        self.kelas_id = kelas_id
        self.pengajar_id = pengajar_id
        self.tanggal_dibuat = tanggal_dibuat
        self.tanggal_edit = tanggal_edit

    @classmethod
    def dari_row(cls, row):
        return cls(row["id"], row["judul"], row["deskripsi"], row["deadline"],
                   row["kelas_id"], row["pengajar_id"],
                   row["tanggal_dibuat"] if _punya(row, "tanggal_dibuat") else None,
                   row["tanggal_edit"] if _punya(row, "tanggal_edit") else None)

    @classmethod
    def muat(cls, tugas_id):
        row = database.ambil_tugas_by_id(_ke_int(tugas_id, "Tugas"))
        if row is None:
            raise ValueError("Tugas tidak ditemukan.")
        return cls.dari_row(row)

    @staticmethod
    def parse_deadline(deadline):
        """Deadline di database berupa teks, jadi diubah dulu ke datetime.
        Kalau cuma tanggal (tanpa jam), batasnya sampai akhir hari itu."""
        if isinstance(deadline, datetime):
            return deadline
        if isinstance(deadline, date):
            return datetime.combine(deadline, time(23, 59, 59))
        teks = str(deadline or "").strip()
        for fmt in Tugas.FORMAT_DEADLINE:
            try:
                hasil = datetime.strptime(teks, fmt)
            except ValueError:
                continue
            if fmt == "%Y-%m-%d":
                hasil = hasil.replace(hour=23, minute=59, second=59)
            return hasil
        raise ValueError("Format deadline tidak valid.")

    def is_expired(self):
        try:
            batas = Tugas.parse_deadline(self.deadline)
        except ValueError:
            return False  # deadline kosong/rusak dianggap belum lewat
        return datetime.now() > batas

    # BARU: penanda pengumpulan terlambat. Siswa TETAP boleh mengumpulkan setelah tenggat,
    # tapi berkasnya ditandai "Terlambat" supaya pengajar tahu waktu menilai.
    @staticmethod
    def kumpul_terlambat(deadline, waktu_kumpul):
        if not waktu_kumpul:
            return False  # belum mengumpulkan itu bukan "terlambat", statusnya "belum kumpul"
        try:
            # parse_deadline dipakai dua-duanya karena sama-sama teks waktu dari database
            batas = Tugas.parse_deadline(deadline)
            masuk = Tugas.parse_deadline(waktu_kumpul)
        except ValueError:
            return False
        return masuk > batas

    def telat(self, waktu_kumpul):
        return Tugas.kumpul_terlambat(self.deadline, waktu_kumpul)


class Pengumpulan:
    # file jawaban & nilai cuma berubah lewat submit_jawaban() / beri_nilai(),
    # jadi selalu lewat validasi dulu.
    def __init__(self, id, tugas_id, siswa_id, file_jawaban=None, nilai=None, waktu_kumpul=None):
        self.id = id
        self.tugas_id = tugas_id
        self.siswa_id = siswa_id
        self.file_jawaban = file_jawaban
        self.nilai = nilai
        self.waktu_kumpul = waktu_kumpul

    @classmethod
    def dari_row(cls, row):
        return cls(row["id"], row["tugas_id"], row["siswa_id"], row["file_jawaban"],
                   row["nilai"], row["waktu_kumpul"])

    @classmethod
    def muat(cls, pengumpulan_id):
        row = database.ambil_pengumpulan_by_id(_ke_int(pengumpulan_id, "Pengumpulan"))
        if row is None:
            raise ValueError("Pengumpulan tugas tidak ditemukan.")
        return cls.dari_row(row)

    def submit_jawaban(self, file_jawaban):
        file_jawaban = (file_jawaban or "").strip()
        if not file_jawaban:
            raise ValueError("File jawaban tidak boleh kosong.")
        self.id = database.simpan_pengumpulan(self.tugas_id, self.siswa_id, file_jawaban)
        self.file_jawaban = file_jawaban
        self.nilai = None  # jawaban diganti = nilai lama hangus (sama kayak di database)
        return self.id

    def beri_nilai(self, nilai):
        # nilai cuma bisa masuk lewat method ini, jadi mustahil ada nilai
        # di luar 0-100 atau bukan angka yang nyelip ke database.
        try:
            nilai = float(nilai)
        except (TypeError, ValueError):
            raise ValueError("Nilai harus berupa angka.")
        if not (0 <= nilai <= 100):
            raise ValueError("Nilai harus berada di antara 0 sampai 100.")

        if self.id is None:  # objek dibuat tanpa id, cari dulu pengumpulannya
            row = database.ambil_pengumpulan_by_tugas_siswa(self.tugas_id, self.siswa_id)
            if row is None:
                raise ValueError("Siswa ini belum mengumpulkan tugas, jadi belum bisa dinilai.")
            self.id = row["id"]

        database.update_nilai_pengumpulan(self.id, nilai)
        self.nilai = nilai
        return self.nilai

    def hapus_nilai(self):
        if self.id is None:
            row = database.ambil_pengumpulan_by_tugas_siswa(self.tugas_id, self.siswa_id)
            if row is None:
                raise ValueError("Pengumpulan tugas tidak ditemukan.")
            self.id = row["id"]
        database.hapus_nilai_pengumpulan(self.id)
        self.nilai = None
        return None


class Komentar:
    def __init__(self, id, tugas_id, user_id, isi_komentar, waktu, siswa_id=None):
        self.id = id
        self.tugas_id = tugas_id
        self.user_id = user_id
        self.isi_komentar = isi_komentar
        self.waktu = waktu
        self.siswa_id = siswa_id

    @classmethod
    def dari_row(cls, row):
        return cls(row["id"], row["tugas_id"], row["user_id"], row["isi_komentar"], row["waktu"],
                   row["siswa_id"] if _punya(row, "siswa_id") else None)

    def tambah_komentar(self):
        isi = (self.isi_komentar or "").strip()
        if not isi:
            raise ValueError("Isi komentar tidak boleh kosong.")
        if self.siswa_id is None:
            raise ValueError("Komentar harus ditujukan ke salah satu siswa.")
        self.id = database.tambah_komentar(self.tugas_id, self.user_id, isi, self.siswa_id)
        self.isi_komentar = isi
        return self.id

    @staticmethod
    def get_list_komentar(tugas_id, siswa_id):
        """DIUBAH: isi percakapan satu siswa saja pada tugas tsb."""
        tugas_id = _ke_int(tugas_id, "Tugas")
        siswa_id = _ke_int(siswa_id, "Siswa")
        return database.ambil_komentar_tugas(tugas_id, siswa_id)