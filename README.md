# Fluenglo — Sistem Kursus Bahasa Inggris SMA

Proyek UTS PBO — Kelompok B3

## Cara menjalankan

```
pip install -r requirements.txt
python seed.py       # sekali saja, bikin database + akun admin pertama
python app.py
```

Buka `http://127.0.0.1:5000`

## Sudah jalan (Julpa)

- Login & Logout (session, bukan dummy lagi)
- Kelola Akun: lihat daftar, tambah akun, hapus akun — semua sudah
  tersambung ke database asli (`fluenglo.db`)
- Semua halaman Siswa (Jadwal, Materi, Tugas, Monitoring) — masih pakai
  data contoh, menyusul disambungkan ke database oleh Anggota 1/2/3

## Struktur folder & siapa mengerjakan apa

```
fluenglo/
├── app.py              # Julpa — route sudah ada semua. Bagian Siswa &
│                        # Admin/Kelola Akun sudah jalan, sisanya TODO
│                        # per nama di komentar.
├── database.py         # Julpa — koneksi + query users() sudah jalan.
│                        # Anggota lain isi query modulnya di bagian TODO.
├── schema.sql           # Julpa — jangan diubah sendiri, diskusi dulu
├── seed.py              # Julpa — sudah jalan, buat akun admin pertama
├── models/
│   ├── user.py          # Siswa & Pengajar: isi TODO (Anggota 1/2/3/4)
│   ├── akademik.py      # ANGGOTA 1 (Kelas, Jadwal) + ANGGOTA 2 (Materi, Tugas, Komentar)
│   └── presensi.py      # ANGGOTA 4 (Presensi, CatatanPengajar)
├── templates/            # AYA — 4 halaman Siswa sudah selesai.
│                          # admin_akun.html masih polos (belum ada desain),
│                          # tinggal distyle tanpa ubah nama field form.
└── static/
```

Tiap method yang masih kosong ditandai `pass` + komentar `TODO (Anggota n)`.
Jangan ubah nama method/parameter tanpa bilang di grup dulu, karena
`app.py` dan file lain sudah memanggil method-method itu persis seperti itu.

## Pembagian backend per modul

- **Anggota 1**: Kelola Kelas & Jadwal → `models/akademik.py` (Kelas, Jadwal)
  + `Admin.kelola_kelas()` / `Admin.kelola_jadwal()` di `models/user.py`
- **Anggota 2**: Materi & Tugas → `models/akademik.py` (Materi, Tugas, Komentar)
  + method terkait di `Siswa`/`Pengajar` (`kumpul_tugas`, `komentar_tugas`, dst)
- **Anggota 3**: Penilaian & Monitoring → `Pengumpulan.beri_nilai()` di
  `akademik.py` + `Admin.monitoring_sistem()` / `Siswa.lihat_monitoring()`
- **Anggota 4**: Presensi & Catatan → `models/presensi.py` (Presensi, CatatanPengajar)

## Alur kerja

1. Isi method di modulmu (lihat TODO).
2. Tes modulmu sendiri dulu sebelum bilang "selesai" — bisa jalankan
   file-nya langsung atau coba lewat Python interaktif.
3. Push ke branch sendiri, bikin Pull Request, Julpa yang merge.
4. Setelah di-merge, `git pull` dulu sebelum lanjut kerja.

## Akun demo (dari seed.py)

- Admin: `admin` / `admin123` (ganti sebelum deploy publik)
