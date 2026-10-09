import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import database
from models.akademik import Jadwal, HARI_VALID
from models.user import buat_objek_user, Admin

app = Flask(__name__)
app.secret_key = 'fluenglo_secret_key_pbo'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database.migrasi()  # pastikan kolom baru (guru ke-2, jadwal, alamat/nik/email) ada di fluenglo.db

BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli',
         'Agustus', 'September', 'Oktober', 'November', 'Desember']


def simpan_foto(field='foto'):
    """Simpan file foto dari form ke folder uploads, kembalikan nama file (atau None)."""
    file = request.files.get(field)
    if file and file.filename:
        filename = secure_filename(file.filename)
        if filename:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return filename
    return None


def get_current_user():
    if 'user_id' not in session:
        return None
    row = database.ambil_user_by_id(session['user_id'])
    return buat_objek_user(row) if row else None


@app.context_processor
def info_pengguna():
    """Nama pengguna + daftar menu navbar, dipakai di semua template."""
    user = get_current_user()
    return {
        'nama_login': user.nama if user else '',
        # POLYMORPHISM: cukup panggil tampilkan_menu(), ga perlu cek role satu-satu
        'menu_user': user.tampilkan_menu() if user else [],
    }


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_row = database.ambil_user_by_username(username)
        if user_row:
            user_obj = buat_objek_user(user_row)
            if user_obj and user_obj.cek_password(password):
                session['user_id'] = user_obj.id
                session['nama'] = user_obj.nama
                session['role'] = user_obj.role
                return redirect(url_for('dashboard'))
            else:
                flash('Password salah!', 'danger')
        else:
            flash('Username tidak ditemukan!', 'danger')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    if user.role == 'admin':
        return redirect(url_for('kelola_akun'))
    return redirect(url_for('profil'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- ROUTE PROFIL (SISWA & PENGAJAR) ---
@app.route('/profil')
def profil():
    user = get_current_user()
    if not user or user.role == 'admin':
        return redirect(url_for('login'))

    # POLYMORPHISM: lihat_profil() dipanggil sama, hasilnya beda tiap role
    data = user.lihat_profil()
    if user.role == 'pengajar':
        return render_template('profil_pengajar.html', data=data, lengkap=True, bisa_ubah=True)
    return render_template('profil_siswa.html', data=data, lengkap=True, bisa_ubah=True)


@app.route('/profil/password', methods=['POST'])
def ganti_password():
    user = get_current_user()
    if not user or user.role == 'admin':
        return redirect(url_for('login'))

    password_lama = request.form.get('password_lama', '')
    password_baru = request.form.get('password_baru', '')
    konfirmasi = request.form.get('konfirmasi_password', '')

    try:
        if password_baru != konfirmasi:
            raise ValueError('Konfirmasi password tidak cocok.')
        user.ganti_password(password_lama, password_baru)
        flash('Password berhasil diganti!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('profil'))


@app.route('/profil/ubah', methods=['POST'])
def ubah_profil():
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    try:
        user.edit_profil(whatsapp=request.form.get('whatsapp', ''),
                         email=request.form.get('email', ''),
                         foto=simpan_foto())
        flash('Profil berhasil diperbarui!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('profil'))


@app.route('/pengajar/<int:pengajar_id>')
def profil_pengajar(pengajar_id):
    """Profil pengajar. Admin & pengajar ybs lihat lengkap, siswa cuma versi publik."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    row = database.ambil_user_by_id(pengajar_id)
    if not row or row['role'] != 'pengajar':
        flash('Pengajar tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    # siswa cuma boleh lihat pengajar kelasnya sendiri
    if user.role == 'siswa':
        kelas = database.ambil_kelas_siswa(user.id)
        ids = [p['id'] for p in database.ambil_pengajar_kelas(kelas)] if kelas else []
        if pengajar_id not in ids:
            flash('Kamu hanya bisa melihat profil pengajar kelasmu.', 'danger')
            return redirect(url_for('profil'))

    target = buat_objek_user(row)
    lengkap = user.role == 'admin' or user.id == target.id
    data = target.lihat_profil() if lengkap else target.profil_publik()
    return render_template('profil_pengajar.html', data=data, lengkap=lengkap,
                           bisa_ubah=(user.id == target.id))


# --- ROUTE KELOLA AKUN ---
@app.route('/admin/users', methods=['GET', 'POST'])
def kelola_akun():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama = request.form['nama']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        whatsapp = request.form.get('whatsapp', '')
        alamat = request.form.get('alamat', '')
        nik = request.form.get('nik', '')
        kelas_id = request.form.get('kelas_id', '')

        foto_filename = 'default_avatar.png'
        if role == 'pengajar':
            foto_filename = simpan_foto() or foto_filename

        try:
            user.kelola_akun('tambah', nama=nama, username=username, password=password,
                             role=role, whatsapp=whatsapp, alamat=alamat, nik=nik,
                             foto=foto_filename, kelas_id=kelas_id)
            flash('Akun berhasil dibuat!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')

        return redirect(url_for('kelola_akun'))

    users = database.ambil_semua_user()
    return render_template('kelola_akun.html', users=users, kelas_list=database.ambil_semua_kelas())


@app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
def edit_akun(user_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    target = database.ambil_user_by_id(user_id)
    if not target or target['role'] == 'admin':
        flash('Akun tidak ditemukan.', 'danger')
        return redirect(url_for('kelola_akun'))

    foto = simpan_foto() if target['role'] == 'pengajar' else None
    try:
        user.kelola_akun('edit', user_id=user_id,
                         nama=request.form.get('nama', ''),
                         username=request.form.get('username', ''),
                         password=request.form.get('password', ''),
                         whatsapp=request.form.get('whatsapp', ''),
                         alamat=request.form.get('alamat', ''),
                         nik=request.form.get('nik', ''),
                         foto=foto)
        flash('Akun berhasil diperbarui!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_akun'))


@app.route('/admin/users/delete/<int:user_id>')
def hapus_akun(user_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_akun('hapus', user_id=user_id)
        flash('Akun berhasil dihapus!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_akun'))


@app.route('/admin/users/<int:user_id>/biodata')
def biodata_akun(user_id):
    """Tombol 'Biodata Lengkap' di tabel Kelola Akun (pengajar maupun siswa)."""
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    row = database.ambil_user_by_id(user_id)
    if not row or row['role'] == 'admin':
        flash('Akun tidak ditemukan.', 'danger')
        return redirect(url_for('kelola_akun'))

    target = buat_objek_user(row)
    data = target.lihat_profil()  # POLYMORPHISM: Siswa & Pengajar punya lihat_profil() sendiri-sendiri
    if target.role == 'pengajar':
        return render_template('profil_pengajar.html', data=data, lengkap=True, bisa_ubah=False)
    return render_template('profil_siswa.html', data=data, lengkap=True, bisa_ubah=False)


# --- ROUTE KELOLA KELAS ---
@app.route('/admin/kelas', methods=['GET', 'POST'])
def kelola_kelas():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama_kelas = request.form['nama_kelas']
        pengajar_id = request.form.get('pengajar_id', '')
        pengajar_id2 = request.form.get('pengajar_id2', '')

        try:
            user.kelola_kelas('tambah', nama_kelas=nama_kelas, pengajar_id=pengajar_id,
                              pengajar_id2=pengajar_id2)
            flash('Kelas berhasil dibuat!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')

        return redirect(url_for('kelola_kelas'))

    kelas_list = database.ambil_semua_kelas()
    pengajar_list = database.ambil_semua_pengajar()
    return render_template('kelola_kelas.html', kelas_list=kelas_list, pengajar_list=pengajar_list)


@app.route('/admin/kelas/delete/<int:kelas_id>')
def hapus_kelas(kelas_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_kelas('hapus', kelas_id=kelas_id)
        flash('Kelas berhasil dihapus!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_kelas'))


@app.route('/admin/kelas/<int:kelas_id>')
def detail_kelas(kelas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    kelas_row = database.ambil_kelas_by_id(kelas_id)
    if not kelas_row:
        flash('Kelas tidak ditemukan.', 'danger')
        return redirect(url_for('kelola_kelas'))

    pengajar_list = database.ambil_pengajar_kelas(kelas_row)
    siswa_list = database.ambil_siswa_by_kelas(kelas_id)

    return render_template('detail_kelas.html', kelas=kelas_row, pengajar_list=pengajar_list,
                           siswa_list=siswa_list)


# --- ROUTE KELOLA JADWAL ---
def siapkan_jadwal_list(rows):
    """Ubah baris tabel jadwal jadi data siap tampil di tabel:
    kelas_id, hari, tanggal, nama_pengajar, jam_mulai, jam_selesai, materi, minggu.
    Minggu ke-1 = minggu (Senin-Minggu) tempat jadwal paling awal kelas tersebut."""
    def ke_tanggal(teks):
        try:
            return datetime.strptime(teks, '%Y-%m-%d').date() if teks else None
        except ValueError:
            return None

    awal = {}  # kelas_id -> Senin pada minggu jadwal paling awal
    for r in rows:
        d = ke_tanggal(r['tanggal'])
        if d:
            senin = d - timedelta(days=d.weekday())
            if r['kelas_id'] not in awal or senin < awal[r['kelas_id']]:
                awal[r['kelas_id']] = senin

    hasil = []
    for r in rows:
        d = ke_tanggal(r['tanggal'])
        try:
            jam_mulai, jam_selesai = Jadwal.pecah_jam(r['jam'])
        except ValueError:
            jam_mulai, jam_selesai = r['jam'], ''
        minggu = 1
        if d:
            minggu = ((d - timedelta(days=d.weekday())) - awal[r['kelas_id']]).days // 7 + 1
        hasil.append({
            'id': r['id'],
            'kelas_id': r['kelas_id'],
            'hari': r['hari'],
            'tanggal': f"{d.day} {BULAN[d.month - 1]} {d.year}" if d else '-',
            'nama_pengajar': r['pengajar_nama'],
            'jam_mulai': jam_mulai,
            'jam_selesai': jam_selesai,
            'materi': r['materi'] or '-',
            'minggu': minggu,
            '_urut': (minggu, r['tanggal'] or '', HARI_VALID.index(r['hari']) if r['hari'] in HARI_VALID else 9, jam_mulai),
        })
    hasil.sort(key=lambda x: x['_urut'])
    return hasil


@app.route('/admin/jadwal', methods=['GET', 'POST'])
def kelola_jadwal():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        hari = request.form['hari']
        jam_mulai = request.form['jam_mulai']
        jam_selesai = request.form['jam_selesai']
        kelas_id = request.form['kelas_id']
        pengajar_id = request.form['pengajar_id']
        tanggal = request.form.get('tanggal', '')
        materi = request.form.get('materi', '')

        try:
            user.kelola_jadwal('tambah', hari=hari, jam_mulai=jam_mulai, jam_selesai=jam_selesai,
                               kelas_id=kelas_id, pengajar_id=pengajar_id,
                               tanggal=tanggal, materi=materi)
            flash('Jadwal berhasil ditambahkan!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')

        return redirect(url_for('kelola_jadwal'))

    jadwal_list = siapkan_jadwal_list(database.ambil_semua_jadwal())
    kelas_list = database.ambil_semua_kelas()
    pengajar_list = database.ambil_semua_pengajar()

    return render_template('kelola_jadwal.html', jadwal_list=jadwal_list, kelas_list=kelas_list, pengajar_list=pengajar_list)


# --- ROUTE MATERI, TUGAS, PENILAIAN, MONITORING, PRESENSI ---
# TODO (Anggota 2): route Materi (upload/download/hapus) dan Tugas (buat, kumpul, komentar)
# TODO (Anggota 3): route penilaian tugas, Monitoring (rekap nilai, rekap presensi, catatan akhir)
# TODO (Anggota 4): route Presensi (hadir, sakit, izin, alfa)


if __name__ == '__main__':
    app.run(debug=True)