"""
models/akademik.py
Kelas -> ANGGOTA 1
Materi, Tugas, Pengumpulan, Komentar -> ANGGOTA 2 (Materi/Tugas) & ANGGOTA 3 (Pengumpulan nilai)
Jadwal -> ANGGOTA 1

Nama method mengikuti tabel class diagram terbaru. Isi bertahap sesuai TODO.
"""

from datetime import date


class Kelas:
    def __init__(self, id, nama_kelas, pengajar_id):
        self.id = id
        self.nama_kelas = nama_kelas
        self.pengajar_id = pengajar_id
        self.daftar_siswa = []       

    def tambah_siswa(self, siswa):
        """TODO (Anggota 1)"""
        pass

    def hapus_siswa(self, siswa):
        """TODO (Anggota 1)"""
        pass

    def get_total_siswa(self):
        """TODO (Anggota 1): kembalikan len(self.daftar_siswa)."""
        pass


class Jadwal:
    def __init__(self, id, hari, jam, kelas_id, pengajar_id):
        self.id = id
        self.hari = hari
        self.jam = jam
        self.kelas_id = kelas_id     
        self.pengajar_id = pengajar_id

    def get_info_jadwal(self):
        """TODO (Anggota 1): kembalikan string ringkas, misal 'Senin, 15.00'."""
        pass


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
