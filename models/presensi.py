# PEMBAGIAN TUGAS DI models/presensi.py
# Presensi -> ANGGOTA 4
# CatatanPengajar (Catatan Akhir) -> ANGGOTA 3 (Monitoring)


class Presensi:
    def __init__(self, id, tanggal, siswa_id, kelas_id, status="Belum Hadir"):
        self.id = id
        self.tanggal = tanggal
        self.siswa_id = siswa_id
        self.kelas_id = kelas_id
        self.status = status

    def update_status(self, status):
        # TODO (Anggota 4): ubah status presensi (hadir, sakit, izin, alfa)
        pass

    @staticmethod
    def tandai_semua_hadir(daftar_presensi):
        # TODO (Anggota 4): centang hadir sekaligus untuk seluruh siswa
        pass


class CatatanPengajar:
    # Catatan akhir: 1 catatan per siswa per kelas, ditulis setelah seluruh pertemuan selesai
    def __init__(self, id, siswa_id, pengajar_id, kelas_id, isi_catatan, tanggal=None):
        self.id = id
        self.siswa_id = siswa_id
        self.pengajar_id = pengajar_id
        self.kelas_id = kelas_id
        self.isi_catatan = isi_catatan
        self.tanggal = tanggal

    def simpan_catatan(self):
        # TODO (Anggota 3): simpan catatan akhir baru ke database
        pass

    def ubah_catatan(self, isi_baru):
        # TODO (Anggota 3): edit catatan akhir yang sudah ada
        pass

    def get_detail_catatan(self):
        # TODO (Anggota 3): ambil detail catatan untuk ditampilkan di Monitoring Anak
        pass