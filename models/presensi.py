from datetime import datetime
import database

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

def _ke_int(nilai, nama):
    try:
        return int(nilai)
    except (TypeError, ValueError):
        raise ValueError(f"{nama} tidak valid.")

class Presensi:
    # data kehadiran (id, tanggal, siswa_id, kelas_id, status) dan
    STATUS_DEFAULT = "Belum Hadir"
    STATUS_VALID = ["Hadir", "Izin", "Sakit", "Alfa"]
    # ENCAPSULATION: awalan underscore (_ALIAS) = detail internal, jangan dipakai dari luar.
    _ALIAS = {"hadir": "Hadir", "izin": "Izin", "sakit": "Sakit",
              "alfa": "Alfa", "alpha": "Alfa", "alpa": "Alfa"}

    def __init__(self, id, tanggal, siswa_id, kelas_id, status="Belum Hadir"):
        self.id = id
        self.tanggal = tanggal
        self.siswa_id = siswa_id
        self.kelas_id = kelas_id
        self.status = status

    # ---------- pembuatan objek ----------
    # Pemanggil cukup terima objek Presensi, nggak perlu tau tabel & kolomnya.
    @classmethod
    def dari_row(cls, row):
        return cls(row["id"], row["tanggal"], row["siswa_id"], row["kelas_id"], row["status"])

    @classmethod
    def muat(cls, presensi_id):
        row = database.ambil_presensi_by_id(_ke_int(presensi_id, "Presensi"))
        if row is None:
            raise ValueError("Data presensi tidak ditemukan.")
        return cls.dari_row(row)

    @classmethod
    def ambil_kelas(cls, kelas_id, tanggal, jadwal_id=None):
        """Satu objek Presensi untuk SETIAP siswa di kelas pada tanggal tsb.
        Siswa yang belum dicatat otomatis berstatus 'Belum Hadir' (id=None)."""
        tersimpan = {r["siswa_id"]: r for r in database.ambil_presensi_kelas_tanggal(kelas_id, tanggal, jadwal_id)}
        hasil = []
        for s in database.ambil_siswa_by_kelas(kelas_id):
            if s["id"] in tersimpan:
                hasil.append(cls.dari_row(tersimpan[s["id"]]))
            else:
                hasil.append(cls(None, tanggal, s["id"], kelas_id))
        return hasil

    @classmethod
    def riwayat_siswa(cls, siswa_id):
        """Semua presensi seorang siswa, tanggal terbaru di atas."""
        return [cls.dari_row(r) for r in database.ambil_presensi_siswa(_ke_int(siswa_id, "Siswa"))]

    # ---------- validasi ----------
    # semua aturan validasi presensi dikunci di class ini,
    # jadi data yang masuk database pasti lolos pemeriksaan yang sama.
    @staticmethod
    def normalisasi_status(status):
        kunci = (status or "").strip().lower()
        if kunci not in Presensi._ALIAS:
            raise ValueError("Status presensi harus salah satu dari: Hadir, Izin, Sakit, Alfa.")
        return Presensi._ALIAS[kunci]

    @staticmethod
    def cek_tanggal(tanggal):
        """Pastikan format YYYY-MM-DD, kembalikan string yang sudah dirapikan."""
        try:
            return datetime.strptime((tanggal or "").strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ValueError("Tanggal presensi tidak valid.")

    @staticmethod
    def format_label(tanggal):
        """'2026-10-05' -> 'Senin, 5 Oktober 2026'"""
        d = datetime.strptime(tanggal, "%Y-%m-%d").date()
        return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"

    @staticmethod
    def cek_input(kelas_id, tanggal, siswa_ids):
        """Validasi satu sesi presensi. Kembalikan (kelas_id, tanggal_rapi)."""
        kelas_id = _ke_int(kelas_id, "Kelas")
        if database.ambil_kelas_by_id(kelas_id) is None:
            raise ValueError("Kelas tidak ditemukan.")

        tanggal = Presensi.cek_tanggal(tanggal)
        if tanggal not in database.ambil_tanggal_jadwal_kelas(kelas_id):
            raise ValueError("Tidak ada jadwal untuk kelas ini pada tanggal tersebut.")

        anggota = {s["id"] for s in database.ambil_siswa_by_kelas(kelas_id)}
        for sid in siswa_ids:
            if sid not in anggota:
                raise ValueError("Ada siswa yang bukan anggota kelas ini.")
        return kelas_id, tanggal

    # ---------- aksi ----------
    # Di dalamnya ada validasi, upsert (nggak duplikat), dan transaksi database,
    # tapi pemanggil (Pengajar / route Flask) nggak perlu tau.
    @staticmethod
    def simpan_massal(kelas_id, tanggal, data_status, pengajar_id=None, jadwal_id=None):
        """Simpan presensi banyak siswa sekaligus.
        data_status: {siswa_id: 'hadir' / 'Izin' / ...}. Semua divalidasi dulu,
        kalau ada satu yang salah nggak ada yang tersimpan. Return jumlah siswa."""
        if not data_status:
            raise ValueError("Belum ada status kehadiran yang dipilih.")
        bersih = {}
        for sid, st in data_status.items():
            bersih[_ke_int(sid, "Siswa")] = Presensi.normalisasi_status(st)
        kelas_id, tanggal = Presensi.cek_input(kelas_id, tanggal, bersih.keys())
        database.simpan_presensi_massal(kelas_id, tanggal, bersih, pengajar_id, jadwal_id)
        return len(bersih)

    @staticmethod
    def hapus_banyak(kelas_id, tanggal, siswa_ids, jadwal_id=None):
        """BARU: kosongkan kehadiran beberapa siswa pada satu pertemuan (centang dibatalkan).
        ABSTRACTION: pemanggil cukup menyebut siswa mana yang dibatalkan; validasi tanggal
        dan penghapusan barisnya diurus di sini."""
        siswa_ids = [_ke_int(s, "Siswa") for s in siswa_ids]
        if not siswa_ids:
            return 0
        kelas_id, tanggal = Presensi.cek_input(kelas_id, tanggal, siswa_ids)
        jumlah = 0
        for sid in siswa_ids:
            jumlah += database.hapus_presensi(kelas_id, tanggal, sid, jadwal_id)
        return jumlah

    @staticmethod
    def batalkan_pertemuan(kelas_id, tanggal, jadwal_id=None):
        """Membatalkan (mengosongkan) seluruh kehadiran siswa pada satu pertemuan yang dipilih."""
        kelas_id, tanggal = Presensi.cek_input(kelas_id, tanggal, [])
        return database.hapus_presensi_pertemuan(kelas_id, tanggal, jadwal_id=jadwal_id)

    def simpan(self, pengajar_id=None, jadwal_id=None):
        """Simpan objek ini (insert, atau update kalau siswa+kelas+tanggal sudah ada)."""
        self.status = Presensi.normalisasi_status(self.status)
        self.kelas_id, self.tanggal = Presensi.cek_input(self.kelas_id, self.tanggal, [self.siswa_id])
        self.id = database.simpan_presensi(self.tanggal, self.siswa_id, self.kelas_id, self.status,
                                           pengajar_id=pengajar_id, jadwal_id=jadwal_id)
        return self.id

    def update_status(self, status):
        # status cuma diubah lewat method ini, jadi selalu divalidasi dulu
        # (Hadir/Izin/Sakit/Alfa) sebelum masuk ke objek & database.
        self.status = Presensi.normalisasi_status(status)
        if self.id:
            database.update_status_presensi(self.id, self.status)
        else:
            self.simpan()
        return self.status

    @staticmethod
    def tandai_semua_hadir(daftar_presensi, jadwal_id=None):
        """Tandai semua Presensi di daftar jadi 'Hadir' (tombol 'hadir semua' buat pengajar).
        Disimpan per kelas+tanggal dalam satu transaksi. Return jumlah yang diubah."""
        kelompok = {}
        for p in daftar_presensi:
            kelompok.setdefault((p.kelas_id, p.tanggal), []).append(p)

        for (kelas_id, tanggal), daftar in kelompok.items():
            Presensi.simpan_massal(kelas_id, tanggal, {p.siswa_id: "Hadir" for p in daftar},
                                   jadwal_id=jadwal_id)
            id_tersimpan = {r["siswa_id"]: r["id"]
                            for r in database.ambil_presensi_kelas_tanggal(kelas_id, tanggal, jadwal_id)}
            for p in daftar:  # sinkronkan objek dengan yang sudah masuk database
                p.status = "Hadir"
                p.id = id_tersimpan.get(p.siswa_id, p.id)
        return len(daftar_presensi)

    # ---------- rekap ----------
    # (jumlah per status, persen hadir) tanpa buka detail query GROUP BY ke pemanggil.
    @staticmethod
    def _status_baku(status):
        """Status dari database -> salah satu STATUS_VALID (data lama 'alpha' ikut jadi 'Alfa'), atau None."""
        return Presensi._ALIAS.get((status or "").strip().lower())

    @staticmethod
    def rekap_siswa(siswa_id):
        """{'Hadir': n, 'Izin': n, 'Sakit': n, 'Alfa': n, 'total': n, 'persen_hadir': x}"""
        hasil = {st: 0 for st in Presensi.STATUS_VALID}
        for r in database.rekap_presensi_siswa(siswa_id):
            baku = Presensi._status_baku(r["status"])
            if baku:
                hasil[baku] += r["jumlah"]
        total = sum(hasil.values())
        hasil["total"] = total
        hasil["persen_hadir"] = round(hasil["Hadir"] * 100 / total, 1) if total else 0
        return hasil

    @staticmethod
    def rekap_kelas(kelas_id):
        """Daftar rekap per siswa di kelas: [{'siswa_id','nama','Hadir','Izin','Sakit','Alfa'}, ...]"""
        data = {}
        for s in database.ambil_siswa_by_kelas(kelas_id):
            data[s["id"]] = {"siswa_id": s["id"], "nama": s["nama"],
                             **{st: 0 for st in Presensi.STATUS_VALID}}
        for r in database.rekap_presensi_kelas(kelas_id):
            baku = Presensi._status_baku(r["status"])
            if r["siswa_id"] in data and baku:
                data[r["siswa_id"]][baku] += r["jumlah"]
        return list(data.values())


class CatatanPengajar:
    # Catatan akhir: 1 catatan per siswa per kelas, ditulis pengajar setelah seluruh pertemuan selesai, tampil di Monitoring Anak.
    def __init__(self, id, siswa_id, pengajar_id, kelas_id, isi_catatan, tanggal=None):
        self.id = id
        self.siswa_id = siswa_id
        self.pengajar_id = pengajar_id
        self.kelas_id = kelas_id
        self.isi_catatan = isi_catatan
        self.tanggal = tanggal

    # aturan "guru 1 & guru 2 kelas tsb boleh nulis" dan "siswa harus anggota kelas" sudah dicek di sana
    @classmethod
    def dari_row(cls, row):
        return cls(row["id"], row["siswa_id"], row["pengajar_id"], row["kelas_id"],
                   row["catatan"], row["tanggal_dibuat"])

    @classmethod
    def ambil_siswa(cls, siswa_id):
        """Semua catatan akhir seorang siswa (terbaru di atas), buat Monitoring Anak."""
        return [cls.dari_row(r) for r in database.ambil_catatan_akhir_by_siswa(_ke_int(siswa_id, "Siswa"))]

    @classmethod
    def ambil(cls, siswa_id, kelas_id):
        """Catatan akhir siswa di satu kelas, None kalau belum ada."""
        kelas_id = _ke_int(kelas_id, "Kelas")
        for c in cls.ambil_siswa(siswa_id):
            if c.kelas_id == kelas_id:
                return c
        return None

    def _baris_database(self):
        """Baris catatan ini (lengkap dengan nama pengajar & nama kelas), None kalau belum tersimpan."""
        if self.id is None:
            return None
        for r in database.ambil_catatan_akhir_by_siswa(self.siswa_id):
            if r["id"] == self.id and r["kelas_id"] == self.kelas_id:
                return r
        return None

    def simpan_catatan(self):
        """Simpan catatan akhir. Kalau siswa ini sudah punya catatan di kelas tsb,
        isinya diperbarui (satu siswa satu catatan per kelas), bukan dobel."""
        isi = (self.isi_catatan or "").strip()
        if not isi:
            raise ValueError("Catatan tidak boleh kosong.")

        self.id = database.tambah_catatan_akhir(self.siswa_id, self.kelas_id, self.pengajar_id, isi)
        self.isi_catatan = isi
        baris = self._baris_database()
        self.tanggal = baris["tanggal_dibuat"] if baris else self.tanggal
        return self.id

    def ubah_catatan(self, isi_baru):
        """Ubah catatan akhir yang sudah tersimpan. Return False kalau catatannya sudah nggak ada."""
        isi_baru = (isi_baru or "").strip()
        if not isi_baru:
            raise ValueError("Catatan baru tidak boleh kosong.")
        if self.id is None:
            raise ValueError("Catatan belum memiliki ID.")
        if self._baris_database() is None:
            return False

        database.tambah_catatan_akhir(self.siswa_id, self.kelas_id, self.pengajar_id, isi_baru)
        self.isi_catatan = isi_baru
        baris = self._baris_database()
        self.tanggal = baris["tanggal_dibuat"] if baris else self.tanggal
        return True

    def get_detail_catatan(self):
        """Detail catatan buat Monitoring Anak (dict: id, siswa_id, kelas_id, pengajar_id,
        catatan, tanggal_dibuat, nama_pengajar, nama_kelas), None kalau belum tersimpan."""
        baris = self._baris_database()
        return dict(baris) if baris else None