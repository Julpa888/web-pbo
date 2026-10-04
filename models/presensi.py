"""
models/presensi.py
Penanggung jawab: ANGGOTA 4 (Backend Presensi & Catatan Pengajar)

Presensi, CatatanPengajar — dipakai untuk menu "Kelola Presensi" (Pengajar)
dan "Monitoring Anak" (Siswa).
"""


class Presensi:
    def __init__(self, id, tanggal, siswa_id, kelas_id, status="Belum Hadir"):
        self.id = id
        self.tanggal = tanggal
        self.siswa_id = siswa_id 
        self.kelas_id = kelas_id  
        self.status = status       # "Hadir" / "Izin" / "Alfa" / dll

    def update_status(self, status):
        """TODO (Anggota 4): set self.status, simpan ke database.
        Dipanggil dari Pengajar.catat_presensi() untuk satu siswa."""
        pass

    @staticmethod
    def tandai_semua_hadir(daftar_presensi):
        """TODO (Anggota 4): loop semua objek Presensi satu kelas,
        panggil update_status('Hadir') untuk masing-masing."""
        pass


class CatatanPengajar:
    def __init__(self, id, siswa_id, pengajar_id, isi_catatan, tanggal):
        self.id = id
        self.siswa_id = siswa_id      
        self.pengajar_id = pengajar_id
        self.isi_catatan = isi_catatan
        self.tanggal = tanggal

    def get_detail_catatan(self):
        """TODO (Anggota 4): kembalikan dict/ringkasan catatan ini untuk
        ditampilkan di menu Monitoring Anak (Siswa) dan Monitoring (Admin)."""
        pass
