from flask import Flask, render_template, request, redirect, session

import database
from models.user import Admin, buat_objek_user

app = Flask(__name__)
app.secret_key = "ganti-sebelum-deploy-publik"  # TODO (Julpa): ganti dengan nilai acak sebelum deploy

# DATA CONTOH (dummy)

NAMA_SISWA = "Budi Santoso"
KELAS_SISWA = "A"

DAFTAR_JADWAL = [
    {"hari": "Senin", "jam": "15.00 - 16.30", "materi": "Greetings, Introductions, and Self Introduction", "pengajar": "Bu Rina", "ruang": "Ruang A"},
    {"hari": "Rabu",  "jam": "16.00 - 17.30", "materi": "Descriptive Text", "pengajar": "Pak Dedi", "ruang": "Ruang B"},
    {"hari": "Jumat", "jam": "15.00 - 16.30", "materi": "Recount Text", "pengajar": "Bu Rina", "ruang": "Ruang A"},
]

DAFTAR_MATERI = [
    {"judul": "Greetings, Introductions, and Self Introduction", "ringkasan": "Cara menyapa dan memperkenalkan diri dalam Bahasa Inggris."},
    {"judul": "Descriptive Text", "ringkasan": "Menggambarkan orang, benda, atau tempat secara detail."},
    {"judul": "Recount Text", "ringkasan": "Menceritakan kembali pengalaman atau kejadian masa lalu."},
    {"judul": "Narrative Text", "ringkasan": "Menyusun cerita dengan alur dan tokoh."},
    {"judul": "Procedure Text", "ringkasan": "Menjelaskan langkah-langkah melakukan sesuatu."},
    {"judul": "Report Text", "ringkasan": "Menyajikan informasi umum tentang suatu hal secara faktual."},
]

DAFTAR_TUGAS = [
    {"id": 1, "judul": "Recount Text", "deadline": "3 Okt 2026", "status": "Belum", "status_kelas": "belum",
     "deskripsi": "Kerjakan soal nomor 1-10 pada modul di halaman 12, lalu unggah hasilnya dalam format PDF."},
    {"id": 2, "judul": "Descriptive Text", "deadline": "5 Okt 2026", "status": "Belum", "status_kelas": "belum",
     "deskripsi": "Tulis deskripsi singkat tentang anggota keluargamu, minimal 100 kata."},
    {"id": 3, "judul": "Greetings, Introductions, and Self Introduction", "deadline": "28 Sep 2026", "status": "Sudah", "status_kelas": "sudah",
     "deskripsi": "Rekam video perkenalan diri selama 1 menit."},
]

STATISTIK_MONITORING = {"kehadiran": 92, "rata_nilai": 85, "tugas_selesai": "8 / 10"}

DAFTAR_PRESENSI = [
    {"tanggal": "25 Sep", "materi": "Greetings, Introductions...", "status": "Hadir"},
    {"tanggal": "28 Sep", "materi": "Descriptive Text", "status": "Hadir"},
    {"tanggal": "30 Sep", "materi": "Recount Text", "status": "Izin"},
    {"tanggal": "2 Okt",  "materi": "Narrative Text", "status": "Hadir"},
]

DAFTAR_NILAI = [
    {"materi": "Greetings, Introductions...", "tugas": "Tugas 1", "nilai": 88},
    {"materi": "Descriptive Text", "tugas": "Tugas 2", "nilai": 82},
    {"materi": "Recount Text", "tugas": "Tugas 3", "nilai": 90},
    {"materi": "Narrative Text", "tugas": "Tugas 4", "nilai": 80},
]


# AUTH — JULPA (sudah bisa jalan)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        row = database.ambil_user_by_username(username)
        if row is None:
            return render_template("login.html", error="Username tidak ditemukan.")

        user = buat_objek_user(row)
        if not user.cek_password(password):
            return render_template("login.html", error="Password salah.")

        # simpan info penting di session (jangan simpan objek User-nya langsung)
        session["user_id"] = user.id
        session["nama"] = user.nama
        session["role"] = row["role"]

        if row["role"] == "admin":
            return redirect("/admin/akun")
        elif row["role"] == "pengajar":
            return redirect("/pengajar/jadwal")
        else:  # siswa
            return redirect("/siswa/jadwal")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


def wajib_login(role_dibutuhkan=None):
    """Helper sederhana: True kalau sudah login (dan role cocok kalau diisi)."""
    if "user_id" not in session:
        return False
    if role_dibutuhkan and session.get("role") != role_dibutuhkan:
        return False
    return True


# ======================================================
# SISWA — sudah jalan (pakai data contoh, menyusul data asli
# dari Anggota 1/2/3)
# ======================================================
@app.route("/siswa/jadwal")
def siswa_jadwal():
    return render_template(
        "siswa_jadwal.html",
        judul_halaman="Lihat Jadwal Minggu Ini",
        halaman_aktif="jadwal",
        nama_siswa=session.get("nama", NAMA_SISWA),
        daftar_jadwal=DAFTAR_JADWAL,
    )


@app.route("/siswa/materi")
def siswa_materi():
    return render_template(
        "siswa_materi.html",
        judul_halaman="Lihat Materi",
        halaman_aktif="materi",
        nama_siswa=session.get("nama", NAMA_SISWA),
        daftar_materi=DAFTAR_MATERI,
    )


@app.route("/siswa/tugas")
def siswa_tugas():
    tugas_id = request.args.get("tugas_id", type=int)
    tugas_terpilih = next((t for t in DAFTAR_TUGAS if t["id"] == tugas_id), DAFTAR_TUGAS[0] if DAFTAR_TUGAS else None)
    return render_template(
        "siswa_tugas.html",
        judul_halaman="Kumpul Tugas",
        halaman_aktif="tugas",
        nama_siswa=session.get("nama", NAMA_SISWA),
        daftar_tugas=DAFTAR_TUGAS,
        tugas_terpilih=tugas_terpilih,
    )


@app.route("/siswa/tugas/<int:tugas_id>/kumpul", methods=["POST"])
def siswa_kumpul_tugas(tugas_id):
    # TODO (Anggota 2): sambungkan ke Siswa.kumpul_tugas() + simpan file asli
    print(f"Tugas {tugas_id} dikumpulkan.")
    return redirect(f"/siswa/tugas?tugas_id={tugas_id}")


@app.route("/siswa/monitoring")
def siswa_monitoring():
    return render_template(
        "siswa_monitoring.html",
        judul_halaman="Lihat Presensi dan Nilai",
        halaman_aktif="monitoring",
        nama_siswa=session.get("nama", NAMA_SISWA),
        kelas=KELAS_SISWA,
        statistik=STATISTIK_MONITORING,
        daftar_presensi=DAFTAR_PRESENSI,
        daftar_nilai=DAFTAR_NILAI,
    )


# ======================================================
# PENGAJAR — TODO (Anggota 1 untuk jadwal, Anggota 2 untuk materi/tugas,
# Anggota 4 untuk presensi). Template belum ada (menyusul dari Aya).
# ======================================================
@app.route("/pengajar/profil")
def pengajar_profil():
    """TODO: tampilkan & bisa edit profil (foto, whatsapp, biodata)."""
    pass


@app.route("/pengajar/jadwal")
def pengajar_jadwal():
    """TODO (Anggota 1): tampilkan jadwal_mengajar milik pengajar ini saja."""
    pass


@app.route("/pengajar/materi")
def pengajar_materi():
    """TODO (Anggota 2): list materi + form upload/hapus."""
    pass


@app.route("/pengajar/tugas")
def pengajar_tugas():
    """TODO (Anggota 2): list tugas + form buat tugas + lihat pengumpulan + beri nilai + komentar."""
    pass


@app.route("/pengajar/presensi")
def pengajar_presensi():
    """TODO (Anggota 4): daftar siswa per kelas, checkbox hadir satu-satu/semua."""
    pass


# ======================================================
# ADMIN — Kelola Akun sudah jalan (Julpa). Jadwal/Kelas/Monitoring
# masih TODO Anggota 1 & 3.
# ======================================================
@app.route("/admin/akun")
def admin_akun():
    if not wajib_login("admin"):
        return redirect("/")
    daftar_akun = database.ambil_semua_user()
    return render_template("admin_akun.html", daftar_akun=daftar_akun, nama_admin=session.get("nama"))


@app.route("/admin/akun/tambah", methods=["POST"])
def admin_akun_tambah():
    if not wajib_login("admin"):
        return redirect("/")
    admin = Admin(session["user_id"], session["nama"], "", "")
    admin.kelola_akun(
        "tambah",
        nama=request.form["nama"],
        username=request.form["username"],
        password=request.form["password"],
        role=request.form["role"],
    )
    return redirect("/admin/akun")


@app.route("/admin/akun/<int:user_id>/hapus", methods=["POST"])
def admin_akun_hapus(user_id):
    if not wajib_login("admin"):
        return redirect("/")
    admin = Admin(session["user_id"], session["nama"], "", "")
    admin.kelola_akun("hapus", user_id=user_id)
    return redirect("/admin/akun")


@app.route("/admin/jadwal")
def admin_jadwal():
    """TODO (Anggota 1): kelola_jadwal() — buat/edit/hapus jadwal + pilih pengajar."""
    pass


@app.route("/admin/kelas")
def admin_kelas():
    """TODO (Anggota 1): kelola_kelas() — buat/edit/hapus kelas + atur siswa."""
    pass


@app.route("/admin/monitoring")
def admin_monitoring():
    """TODO (Anggota 3): monitoring_sistem() — rekap materi, tugas, presensi,
    nilai, catatan dari semua kelas (read-only)."""
    pass


if __name__ == "__main__":
    app.run(debug=True)
