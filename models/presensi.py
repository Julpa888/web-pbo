# pEMBAGIAN TUGAS DI models/presensi.py
# Penanggung jawab: ANGGOTA 4

class Presensi:
    def __init__(self, id, tanggal, siswa_id, kelas_id, status="Belum Hadir"):
        self.id = id
        self.tanggal = tanggal
        self.siswa_id = siswa_id 
        self.kelas_id = kelas_id  
        self.status = status

    def update_status(self, status):
        pass

    @staticmethod
    def tandai_semua_hadir(daftar_presensi):
        pass


class CatatanPengajar:
    def __init__(self, id, siswa_id, pengajar_id, isi_catatan, tanggal):                                                
        self.id = id
        self.siswa_id = siswa_id      
        self.pengajar_id = pengajar_id
        self.isi_catatan = isi_catatan
        self.tanggal = tanggal

    def get_detail_catatan(self):
        pass