import os
import re
import uuid
from datetime import datetime, timedelta
from flask import (Flask, render_template, request, redirect, url_for, session, flash,
                   send_from_directory)
from werkzeug.utils import secure_filename
import database
from models.akademik import Jadwal, Materi, Tugas, HARI_VALID, HEADER_KELAS
from models.user import buat_objek_user, Pendidikan
from models.presensi import Presensi


app = Flask(__name__)
app.secret_key = 'fluenglo_secret_key_pbo'
# path absolut, jadi upload nggak nyasar kalau app dijalankan dari folder lain
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database.migrasi()  # bikin tabel/kolom yang belum ada (alamat/nik/email, pengumpulan, catatan_akhir, riwayat_password, deskripsi kelas, dst)

BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli',
         'Agustus', 'September', 'Oktober', 'November', 'Desember']
EKSTENSI_FOTO = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
FORMAT_WAKTU = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d')


# kumpulan filter tampilan. Ditaruh di satu tempat biar aturan "data sensitif
# disamarkan" dan "tanggal ditulis gaya Indonesia" cuma ada satu versi di seluruh web.
def _ke_waktu(teks):
    """Teks waktu dari database -> datetime, atau None kalau kosong/rusak."""
    teks = str(teks or '').strip()
    for fmt in FORMAT_WAKTU:
        try:
            return datetime.strptime(teks, fmt)
        except ValueError:
            continue
    return None


@app.template_filter('samar')
def samar(nilai, tampil=4):
    """Tampilkan beberapa karakter awal, sisanya jadi titik. Dipakai untuk NIK di tabel
    Kelola Akun — lengkapnya cuma ada di halaman Profil Lengkap."""
    teks = str(nilai or '').strip()
    if not teks:
        return '-'
    if len(teks) <= tampil:
        return teks
    return teks[:tampil] + '•' * (len(teks) - tampil)


@app.template_filter('tgl')
def tgl(nilai, tahun=True):
    """'2026-10-02 08:30:00' -> '02 Oktober 2026' (atau tanpa tahun kalau tahun=False)."""
    d = _ke_waktu(nilai)
    if not d:
        return '-'
    hasil = f"{d.day:02d} {BULAN[d.month - 1]}"
    return f"{hasil} {d.year}" if tahun else hasil


@app.template_filter('tgl_jam')
def tgl_jam(nilai):
    """'2026-10-06 19:45:00' -> '06 Oktober 2026, 19.45'."""
    d = _ke_waktu(nilai)
    if not d:
        return '-'
    return f"{d.day:02d} {BULAN[d.month - 1]} {d.year}, {d.hour:02d}.{d.minute:02d}"


@app.template_filter('tgl_singkat')
def tgl_singkat(nilai):
    """'2026-10-02 08:30:00' -> '02/10/2026', buat kolom tabel yang sempit."""
    d = _ke_waktu(nilai)
    return d.strftime('%d/%m/%Y') if d else '-'

@app.template_filter('wa')
def wa(nomor):
    """BARU: nomor WhatsApp -> tautan wa.me. Nomor disimpan dalam bentuk lokal
    (08xxx), sedangkan WhatsApp minta format internasional tanpa tanda plus,
    jadi awalan 0 diganti 62. Dibuka lewat wa.me supaya tetap jalan baik di
    komputer yang sudah punya aplikasi WhatsApp Desktop maupun yang belum."""
    digit = re.sub(r'\D', '', str(nomor or ''))
    if not digit:
        return ''
    if digit.startswith('0'):
        digit = '62' + digit[1:]
    elif not digit.startswith('62'):
        digit = '62' + digit
    return 'https://wa.me/' + digit

# isian form yang ditolak server disimpan sebentar di session, lalu dipakai sekali
# oleh halaman berikutnya untuk membuka ulang modalnya lengkap dengan isi terakhir.
def ingat_isian(modal, aksi=None, **isian):
    session['isian_ulang'] = {
        'modal': modal,
        'aksi': aksi,
        'data': {k: (v if v is not None else '') for k, v in isian.items()},
    }

@app.template_filter('telat')
def telat(waktu_kumpul, deadline):
    """dipakai badge "Terlambat". Aturannya tetap milik class Tugas — filter ini
    cuma jembatan supaya template bisa memanggilnya tanpa mengimpor apa-apa.
    Pemakaian: {% if b.waktu_kumpul|telat(tugas.deadline) %}"""
    return Tugas.kumpul_terlambat(deadline, waktu_kumpul)

@app.template_filter('pw_hash')
def pw_hash(nilai):
    """True kalau password akun itu masih tersimpan ter-hash dari versi lama,
    jadi tabel Kelola Akun bisa menulis 'Perlu direset' alih-alih menampilkan hash."""
    return database.password_sudah_hash(nilai)


@app.template_filter('nama_berkas')
def nama_berkas(nilai):
    """Buang awalan unik 8 karakter yang ditambahkan simpan_file(), jadi yang tampil
    nama asli berkasnya ('Tugas1_Budi.pdf', bukan '4dd1a4d2_Tugas1_Budi.pdf')."""
    return re.sub(r'^[0-9a-f]{8}_', '', str(nilai or '')) or '-'


@app.template_filter('tgl_posting')
def tgl_posting(baris):
    """'02 Oktober (Diedit 03 Oktober)' seperti di desain. baris boleh materi atau tugas:
    yang dibaca pasangan tanggal_upload/tanggal_dibuat dan tanggal_edit."""
    kunci = baris.keys() if hasattr(baris, 'keys') else []
    dibuat = baris['tanggal_upload'] if 'tanggal_upload' in kunci else (
        baris['tanggal_dibuat'] if 'tanggal_dibuat' in kunci else None)
    diedit = baris['tanggal_edit'] if 'tanggal_edit' in kunci else None

    teks = tgl(dibuat, tahun=False)
    if diedit:
        teks += f" (Diedit {tgl(diedit, tahun=False)})"
    return teks


def simpan_file(field, ekstensi_boleh=None):
    """Simpan file upload ke folder uploads dengan nama unik (biar file orang lain nggak
    ketimpa kalau namanya sama). Balikin nama file tersimpan, atau None kalau nggak ada file."""
    file = request.files.get(field)
    if not file or not file.filename:
        return None
    nama = secure_filename(file.filename)
    if not nama:
        raise ValueError('Nama file tidak valid.')
    if ekstensi_boleh and os.path.splitext(nama)[1].lower() not in ekstensi_boleh:
        raise ValueError('Format file tidak didukung.')
    nama_unik = f"{uuid.uuid4().hex[:8]}_{nama}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], nama_unik))
    return nama_unik


def simpan_foto(field='foto'):
    """Simpan foto profil, kembalikan nama file (atau None). Bisa raise ValueError kalau bukan gambar."""
    return simpan_file(field, EKSTENSI_FOTO)


def hapus_file(nama):
    """Buang file upload yang sudah terlanjur disimpan tapi datanya gagal masuk database."""
    if nama:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], nama))
        except OSError:
            pass


def get_current_user():
    if 'user_id' not in session:
        return None
    row = database.ambil_user_by_id(session['user_id'])
    return buat_objek_user(row) if row else None


def tujuan_back(user):
    """Back bertingkat hanya untuk isi kelas; fitur utama kembali ke dashboard."""
    ep = request.endpoint
    arg = request.view_args or {}
    if ep == 'biodata_akun':
        return url_for('kelola_akun')
    if ep == 'detail_materi' and arg.get('materi_id'):
        materi = database.ambil_materi_by_id(arg['materi_id'])
        if materi:
            return url_for('kelola_materi', kelas_id=materi['kelas_id'])
    if ep == 'detail_tugas' and arg.get('tugas_id'):
        tugas = database.ambil_tugas_by_id(arg['tugas_id'])
        if tugas:
            return url_for('daftar_tugas', kelas_id=tugas['kelas_id'])
    if ep in ('kelola_materi', 'daftar_tugas', 'detail_kelas'):
        return url_for('kelola_kelas' if user.role == 'admin' else 'lihat_kelas')
    if ep == 'presensi_jadwal':
        # Guru pengganti mengakses presensi melalui jadwal, bukan kelas penuh.
        return url_for('lihat_jadwal')
    return url_for('dashboard')


@app.context_processor
def info_pengguna():
    """Nama pengguna + daftar menu navbar, dipakai di semua template."""
    user = get_current_user()
    return {
        'nama_login': user.nama if user else '',
        'foto_login': database.ambil_user_by_id(user.id)['foto'] if user else None,
        'id_login': user.id if user else None,
        # POLYMORPHISM: cukup panggil tampilkan_menu(), ga perlu cek role satu-satuu
        'menu_user': user.tampilkan_menu() if user else [],
        'back_url': tujuan_back(user) if user and request.endpoint not in ('dashboard', 'login') else None,
    }


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user_row = database.ambil_user_by_username(username)
        if user_row:
            user_obj = buat_objek_user(user_row)
            if user_obj and user_obj.cek_password(password):
                session.clear()
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
        try:
            tahun = int(request.args.get('tahun', datetime.now().year))
            if not 2000 <= tahun <= 2100:
                raise ValueError()
        except (ValueError, TypeError):
            tahun = datetime.now().year
        return render_template('dashboard_admin.html', user=user,
                               data=database.data_dashboard_admin(tahun))
    if user.role == 'pengajar':
        pilih = request.args.get('kelas', type=int)
        panel = request.args.get('panel')
        if panel not in ('siswa', 'dinilai', 'belum', 'materi'):
            panel = None
        try:
            data = database.data_dashboard_pengajar(user.id, pilih, panel)
        except ValueError:
            flash('Kelas yang dipilih bukan tanggung jawab pengajar.', 'danger')
            return redirect(url_for('dashboard'))
        return render_template('dashboard_pengajar.html', user=user, data=data, panel=panel)
    kelas_list = user.lihat_semua_kelas()
    pilihan = request.args.get('kelas', type=int)
    if pilihan is not None and pilihan not in {k['id'] for k in kelas_list}:
        flash('Kelas tidak tersedia.', 'danger')
        return redirect(url_for('dashboard'))
    kelas_id = pilihan if pilihan is not None else user.kelas_id
    panel = request.args.get('panel')
    if panel not in ('dikerjakan', 'belum_tugas', 'dinilai', 'belum_nilai'):
        panel = None
    return render_template('dashboard_siswa.html', user=user, kelas_list=kelas_list,
                           kelas_id=kelas_id, kelas=database.ambil_kelas_by_id(kelas_id) if kelas_id else None,
                           data=database.data_dashboard_siswa(user.id, kelas_id, panel), panel=panel)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- ROUTE PROFIL (SISWA & PENGAJAR) ---
@app.route('/profil')
def profil():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user.role == 'admin':
        return render_template('profil_admin.html', user=user)

    # POLYMORPHISM: lihat_profil() dipanggil sama, hasilnya beda tiap role
    data = user.lihat_profil()
    if user.role == 'pengajar':
        return render_template('profil_pengajar.html', data=data, lengkap=True, bisa_ubah=True)
    # DIUBAH: siswa_id & kelas_id ikut dikirim buat tombol "Buka Menu Monitoring"
    return render_template('profil_siswa.html', data=data, lengkap=True, bisa_ubah=True,
                           boleh_hapus_foto=True, siswa_id=user.id, kelas_id=user.kelas_id)


@app.route('/profil/password', methods=['POST'])
def ganti_password():
    user = get_current_user()
    if not user or user.role == 'admin':
        return redirect(url_for('login'))

    password_lama = request.form.get('password_lama', '')
    password_baru = request.form.get('password_baru', '')

    try:
        # kolom konfirmasi dicek hanya kalau memang ada di form
        if 'konfirmasi_password' in request.form and password_baru != request.form['konfirmasi_password']:
            raise ValueError('Konfirmasi password tidak cocok.')
        user.ganti_password(password_lama, password_baru)  # sekaligus tercatat di riwayat_password
        flash('Password berhasil diganti!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('profil'))


@app.route('/profil/ubah', methods=['POST'])
def ubah_profil():
    """Ubah Profil siswa & pengajar: foto, no WA (wajib valid), email (opsional), alamat."""
    user = get_current_user()
    if not user or user.role not in ('siswa', 'pengajar'):
        return redirect(url_for('login'))

    foto = None
    try:
        foto = simpan_foto()
        # POLYMORPHISM: edit_profil() dipanggil sama, aturan tiap role ada di class-nya masing-masing
        user.edit_profil(whatsapp=request.form.get('whatsapp', ''),
                         email=request.form.get('email', ''),
                         foto=foto,
                         alamat=request.form.get('alamat'))  # None = field alamat nggak ada di form
        flash('Profil berhasil diperbarui!', 'success')
    except ValueError as e:
        hapus_file(foto)
        flash(str(e), 'danger')
    return redirect(url_for('profil'))


@app.route('/pengajar/<int:pengajar_id>')
def profil_pengajar(pengajar_id):
    """Profil pengajar. Admin & pengajar ybs lihat lengkap (ada NIK), siswa lihat versi publik (tanpa NIK)."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    row = database.ambil_user_by_id(pengajar_id)
    if not row or row['role'] != 'pengajar':
        flash('Pengajar tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    # POLYMORPHISM: siapa boleh lihat siapa diputuskan tiap role sendiri
    if not user.boleh_lihat_pengajar(pengajar_id):
        flash('Kamu hanya bisa melihat profil pengajar kelasmu.', 'danger')
        return redirect(url_for('profil'))

    target = buat_objek_user(row)
    lengkap = user.role == 'admin' or user.id == target.id
    data = target.lihat_profil() if lengkap else target.profil_publik()
    return render_template('profil_pengajar.html', data=data, lengkap=lengkap,
                           bisa_ubah=(user.id == target.id))


@app.route('/siswa/<int:siswa_id>')
def profil_siswa(siswa_id):
    """Profil siswa. Admin, pengajar kelas siswa tsb (dibuka dari presensi / tugas), dan siswa ybs."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    row = database.ambil_user_by_id(siswa_id)
    if not row or row['role'] != 'siswa':
        flash('Siswa tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    if not user.boleh_lihat_siswa(row):
        flash('Kamu tidak punya akses ke profil siswa ini.', 'danger')
        return redirect(url_for('dashboard'))

    target = buat_objek_user(row)
    # catatan akhir dipindah ke halaman Monitoring (sesuai desain, profil cuma punya
    # tombol "Buka Menu Monitoring"), jadi di sini tinggal data profil + tombolnya.
    return render_template('profil_siswa.html', data=target.lihat_profil(), lengkap=True,
                           bisa_ubah=(user.id == target.id),
                           boleh_hapus_foto=(user.role == 'admin' or user.id == target.id),
                           kelas_id=row['kelas_id'], siswa_id=siswa_id)


@app.route('/siswa/<int:siswa_id>/foto/hapus', methods=['POST'])
def hapus_foto_siswa(siswa_id):
    """Hapus foto siswa (fallback inisial) oleh pemilik akun atau admin saja.

    Hanya ubah referensi DB; berkas lama sengaja tidak dihapus untuk mencegah
    penghapusan berkas bersama/tidak sengaja dan menjaga integritas unggahan.
    """
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user.role != 'admin' and not (user.role == 'siswa' and user.id == siswa_id):
        flash('Tidak berhak menghapus foto profil siswa ini.', 'danger')
        return redirect(url_for('dashboard'))
    row = database.ambil_user_by_id(siswa_id)
    if not row or row['role'] != 'siswa':
        flash('Akun siswa tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))
    if row['foto'] and row['foto'] != 'default_avatar.png':
        database.edit_user(siswa_id, foto='default_avatar.png')
        flash('Foto profil siswa berhasil dihapus.', 'success')
    else:
        flash('Siswa belum memiliki foto profil.', 'danger')
    if user.role == 'admin':
        if request.form.get('asal') == 'profil_siswa':
            return redirect(url_for('profil_siswa', siswa_id=siswa_id))
        return redirect(url_for('biodata_akun', user_id=siswa_id))
    return redirect(url_for('profil'))


# --- ROUTE KELOLA AKUN ---
@app.route('/admin/users', methods=['GET', 'POST'])
def kelola_akun():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama = request.form.get('nama', '')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        whatsapp = request.form.get('whatsapp', '')
        alamat = request.form.get('alamat', '')
        nik = request.form.get('nik', '')
        kelas_id = request.form.get('kelas_id', '')
        # BARU (revisi 3): pendidikan terakhir pengajar, diisi admin
        gelar = request.form.get('gelar', '')
        jurusan = request.form.get('jurusan', '')
        jurusan_lain = request.form.get('jurusan_lain', '')
        institusi = request.form.get('institusi', '')

        foto_filename = 'default_avatar.png'
        # tab yang sedang dibuka ikut dibawa pulang lewat ?tab=, biar admin yang
        # sedang menambah pengajar nggak terlempar balik ke tab Siswa.
        tab = role if role in ('siswa', 'pengajar') else 'siswa'
        try:
            if database.ambil_user_by_username(username.strip()):
                raise ValueError('Username sudah digunakan.')
            # Foto pengajar wajib saat akun dibuat oleh admin.
            if role == 'pengajar':
                foto_filename = simpan_foto()
                if not foto_filename:
                    raise ValueError('Foto profil pengajar wajib diisi.')
            user.kelola_akun('tambah', nama=nama, username=username, password=password,
                             role=role, whatsapp=whatsapp, alamat=alamat, nik=nik,
                             foto=foto_filename, kelas_id=kelas_id,
                             gelar=gelar, jurusan=jurusan, jurusan_lain=jurusan_lain,
                             institusi=institusi)  # BARU (revisi 3)
            flash('Akun berhasil dibuat!', 'success')
        except ValueError as e:
            if foto_filename != 'default_avatar.png':
                hapus_file(foto_filename)
            flash(str(e), 'danger')
            # isian yang ditolak disimpan sebentar, supaya modalnya kebuka lagi
            # dengan isi yang sama dan admin tinggal membetulkan bagian yang salah.
            ingat_isian('modal-tambah-' + tab, nama=nama, username=username, password=password,
                        whatsapp=whatsapp, alamat=alamat, nik=nik, kelas_id=kelas_id,
                        gelar=gelar, jurusan=jurusan, jurusan_lain=jurusan_lain,
                        institusi=institusi)  # BARU (revisi 3)

        return redirect(url_for('kelola_akun', tab=tab))

    users = database.ambil_semua_user()
    # + isian_ulang, dipakai membuka kembali modal yang isinya ditolak
    # + pendidikan (buat kolom tabel pengajar & isian modal edit) dan daftar
    # + riwayat_password (kartu Riwayat Perubahan Password) dan terakhir_ubah (kolom Password Diubah)
    # pilihan gelar/jurusan, supaya template tidak menulis ulang daftarnya sendiri.
    semua_kelas = database.ambil_semua_kelas()
    return render_template('kelola_akun.html', users=users,
                           kelas_list=database.ambil_kelas_tersedia_siswa(),
                           semua_kelas_map={k['id']: k['nama_kelas'] for k in semua_kelas},
                           riwayat_password=database.ambil_riwayat_password(limit=5),
                           terakhir_ubah=database.ambil_terakhir_ubah_password(),
                           pendidikan={u['id']: database.ambil_pendidikan(u['id'])
                                       for u in users if u['role'] == 'pengajar'},
                           gelar_list=Pendidikan.GELAR_VALID,
                           jurusan_list=Pendidikan.JURUSAN_VALID,
                           jurusan_lain=Pendidikan.JURUSAN_LAIN,
                           isian_ulang=session.pop('isian_ulang', None))


@app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
def edit_akun(user_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    target = database.ambil_user_by_id(user_id)
    if not target or target['role'] == 'admin':
        flash('Akun tidak ditemukan.', 'danger')
        return redirect(url_for('kelola_akun'))

    tab = target['role']  # balik ke tab asal akun yang barusan diedit
    foto = None
    try:
        existing = database.ambil_user_by_username(request.form.get('username', '').strip())
        if existing and existing['id'] != user_id:
            raise ValueError('Username sudah digunakan.')
        foto = simpan_foto() if target['role'] == 'pengajar' else None
        user.kelola_akun('edit', user_id=user_id,
                         nama=request.form.get('nama', ''),
                         username=request.form.get('username', ''),
                         password=request.form.get('password', ''),
                         whatsapp=request.form.get('whatsapp', ''),
                         alamat=request.form.get('alamat', ''),
                         nik=request.form.get('nik', ''),
                         kelas_id=request.form.get('kelas_id', ''),  # admin bisa pindah kelas siswa
                         # pendidikan terakhir pengajar
                         gelar=request.form.get('gelar', ''),
                         jurusan=request.form.get('jurusan', ''),
                         jurusan_lain=request.form.get('jurusan_lain', ''),
                         institusi=request.form.get('institusi', ''),
                         foto=foto)
        flash('Akun berhasil diperbarui!', 'success')
    except ValueError as e:
        hapus_file(foto)
        flash(str(e), 'danger')
        # modal edit dibuka lagi dengan isian terakhir + action-nya, jadi tombol
        # Simpan tetap menuju akun yang sama.
        kelas_target = database.ambil_kelas_by_id(target['kelas_id']) if target['kelas_id'] else None
        ingat_isian('modal-edit-' + tab, aksi=url_for('edit_akun', user_id=user_id),
                    nama=request.form.get('nama', ''),
                    username=request.form.get('username', ''),
                    password=request.form.get('password', ''),
                    whatsapp=request.form.get('whatsapp', ''),
                    alamat=request.form.get('alamat', ''),
                    nik=request.form.get('nik', ''),
                    kelas_id=request.form.get('kelas_id', '') or target['kelas_id'],
                    kelas_nama=kelas_target['nama_kelas'] if kelas_target else '',
                    gelar=request.form.get('gelar', ''),       
                    jurusan=request.form.get('jurusan', ''),
                    jurusan_lain=request.form.get('jurusan_lain', ''),
                    institusi=request.form.get('institusi', ''))
    return redirect(url_for('kelola_akun', tab=tab))


@app.route('/admin/users/cek-username')
def cek_username_admin():
    user = get_current_user()
    if not user or user.role != 'admin':
        return {'error': 'Akses ditolak'}, 403
    username = request.args.get('username', '').strip()
    exclude = request.args.get('exclude', default=0, type=int)
    existing = database.ambil_user_by_username(username) if username else None
    return {'available': not existing or existing['id'] == exclude}


@app.route('/admin/users/delete/<int:user_id>')
def hapus_akun(user_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    # role dibaca dulu sebelum akunnya hilang, buat menentukan tab tujuan
    target = database.ambil_user_by_id(user_id)
    tab = target['role'] if target and target['role'] in ('siswa', 'pengajar') else 'siswa'
    try:
        user.kelola_akun('hapus', user_id=user_id)
        flash('Akun berhasil dihapus!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_akun', tab=tab))


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
    return render_template('profil_siswa.html', data=data, lengkap=True, bisa_ubah=False,
                           boleh_hapus_foto=True, kelas_id=row['kelas_id'], siswa_id=user_id)


# --- ROUTE KELAS ---
# "Segera hadir" di kartu kelas.
def jadwal_segera(kelas_list, user):
    """{kelas_id: {'teks': 'Senin, 19 Oktober 2026, 08.00'}} berisi SATU pertemuan terdekat
    yang belum lewat untuk tiap kelas. Kelas yang semua jadwalnya sudah lewat tidak masuk
    ke dict ini sama sekali, jadi kartunya memang tidak menampilkan apa-apa.
    Pengajar hanya diberi tahu pertemuan yang DIA ajar; siswa & admin semua pertemuan kelas itu."""
    sekarang = datetime.now()
    ids = {k['id'] for k in kelas_list}
    hasil = {}
    # mundur sehari supaya pertemuan hari ini ikut terbaca, lalu disaring lagi pakai jam selesai
    mulai = (sekarang.date() - timedelta(days=1)).isoformat()
    for r in database.ambil_jadwal_mendatang(mulai):
        kelas_id = r['kelas_id']
        if kelas_id not in ids or kelas_id in hasil:
            continue
        if user.role == 'pengajar' and r['pengajar_id'] != user.id:
            continue
        try:
            d = datetime.strptime(r['tanggal'], '%Y-%m-%d')
            jam_mulai, jam_selesai = Jadwal.pecah_jam(r['jam'])
            jam, menit = (int(x) for x in jam_selesai.split(':'))
        except ValueError:
            continue
        # pertemuan yang jamnya sudah lewat hari ini tidak dihitung "segera hadir"
        if d.replace(hour=jam, minute=menit) < sekarang:
            continue
        hasil[kelas_id] = {
            'teks': f"{r['hari']}, {d.day} {BULAN[d.month - 1]} {d.year}, "
                    f"{jam_mulai.replace(':', '.')}",
        }
    return hasil


def kelas_terpilih(kelas_list, bawaan=None):
    """baca ?kelas=<id> dari URL untuk memilih kelas mana yang jadwalnya ditampilkan.
    Balikin None kalau pengguna memilih "Semua Kelas". `bawaan` dipakai kalau URL belum
    menyebut pilihan sama sekali (buat siswa: kelas aktifnya yang diprioritaskan)."""
    tersedia = [k['id'] for k in kelas_list]
    if 'kelas' not in request.args:
        return bawaan if bawaan in tersedia else None
    try:
        pilih = int(request.args.get('kelas', ''))
    except (TypeError, ValueError):
        return None
    return pilih if pilih in tersedia else None


@app.route('/kelas')
def lihat_kelas():
    """Lihat Kelas untuk siswa (kelas yang diikuti) dan pengajar (kelas yang diajar)."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user.role == 'admin':
        return redirect(url_for('kelola_kelas'))

    # siswa melihat kelas aktif + kelas lama yang sudah dia tamatkan (bertanda Selesai)
    kelas_list = user.lihat_semua_kelas() if user.role == 'siswa' else user.lihat_kelas_diajar()
    # bisa_kelola=False: template sembunyikan tombol tambah & edit kalau False
    # + segera (revisi 5) dan header_list (revisi 2)
    kelas_list = database.status_kelas_list(kelas_list)
    return render_template('kelola_kelas.html', kelas_list=kelas_list, pengajar_list=[],
                           bisa_kelola=False, segera=jadwal_segera(kelas_list, user),
                           header_list=HEADER_KELAS)


@app.route('/admin/kelas', methods=['GET', 'POST'])
def kelola_kelas():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama_kelas = request.form.get('nama_kelas', '')
        pengajar_id = request.form.get('pengajar_id', '')
        pengajar_id2 = request.form.get('pengajar_id2', '')

        try:  # kelas tidak lagi punya deskripsi, tapi sekarang punya header (revisi 2)
            user.kelola_kelas('tambah', nama_kelas=nama_kelas, pengajar_id=pengajar_id,
                              pengajar_id2=pengajar_id2,
                              header=request.form.get('header', ''))
            flash('Kelas berhasil dibuat!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')

        return redirect(url_for('kelola_kelas'))

    kelas_list = database.status_kelas_list(database.ambil_semua_kelas())
    pengajar_list = database.ambil_semua_pengajar()
    # + segera (revisi 5) dan header_list (revisi 2)
    return render_template('kelola_kelas.html', kelas_list=kelas_list, pengajar_list=pengajar_list,
                           bisa_kelola=True, segera=jadwal_segera(kelas_list, user),
                           header_list=HEADER_KELAS)


@app.route('/admin/kelas/edit/<int:kelas_id>', methods=['POST'])  # route edit kelas (tombol pensil)
def edit_kelas(kelas_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_kelas('edit', kelas_id=kelas_id,
                          nama_kelas=request.form.get('nama_kelas', ''),
                          pengajar_id=request.form.get('pengajar_id', ''),
                          pengajar_id2=request.form.get('pengajar_id2', ''),
                          header=request.form.get('header', ''))
        flash('Kelas berhasil diperbarui!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_kelas'))


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


# URL-nya dulu /admin/kelas/<id> padahal dipakai siswa & pengajar juga.
# Sekarang jadi tab "Presensi" di dalam sebuah kelas, sesuai desain (Materi | Tugas | Presensi).
@app.route('/kelas/<int:kelas_id>/presensi')
def detail_kelas(kelas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    kelas_row = database.ambil_kelas_by_id(kelas_id)
    if not kelas_row:
        flash('Kelas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    # POLYMORPHISM: siswa cuma kelasnya sendiri, pengajar cuma kelas yang diajar, admin semuanya
    if not user.boleh_akses_kelas(kelas_id):
        flash('Kamu tidak punya akses ke kelas ini.', 'danger')
        return redirect(url_for('dashboard'))

    pengajar_list = database.ambil_pengajar_kelas(kelas_row)
    siswa_list = database.ambil_siswa_by_kelas(kelas_id)
    # siswa cuma boleh lihat kehadiran dirinya sendiri, bukan absensi teman sekelas
    if user.role == 'siswa':
        siswa_list = [database.ambil_user_by_id(user.id)]

    # Pengganti tidak bisa membuka halaman kelas penuh; hanya pengajar tetap/admin sampai di sini.
    tanggal_boleh = None
    return render_template('detail_kelas.html', kelas=kelas_row, pengajar_list=pengajar_list,
                           siswa_list=siswa_list, user=user, tab='presensi',
                           presensi_list=siapkan_presensi_list(kelas_id),
                           tanggal_boleh=tanggal_boleh)


# --- ROUTE JADWAL ---
def siapkan_jadwal_list(rows, user=None):
    """Ubah baris tabel jadwal jadi data siap tampil di tabel:
    kelas_id, hari, tanggal, pengajar_id, nama_pengajar, jam_mulai, jam_selesai, materi, minggu.
    Minggu ke-1 = minggu (Senin-Minggu) tempat jadwal paling awal kelas tersebut."""
    def ke_tanggal(teks):
        try:
            return datetime.strptime(teks, '%Y-%m-%d').date() if teks else None
        except ValueError:
            return None

    awal = {}  # kelas_id -> Senin pada minggu jadwal paling awal

    # Hitung minggu berdasarkan seluruh jadwal kelas,
    # bukan hanya jadwal yang terlihat oleh pengajar yang login.
    kelas_ids = {r['kelas_id'] for r in rows}

    for kelas_id in kelas_ids:
        semua_jadwal = database.ambil_jadwal_by_kelas(kelas_id)

        for j in semua_jadwal:
            d = ke_tanggal(j['tanggal'])
            if d:
                senin = d - timedelta(days=d.weekday())

                if kelas_id not in awal or senin < awal[kelas_id]:
                    awal[kelas_id] = senin

    # Set status tiap jadwal dari catatan presensi kelas pada tanggal jadwal,
    # bukan dari tanggal yang sudah lewat. Query dibatasi pada jadwal yang tampil.
    jadwal_terpresensi = database.ambil_jadwal_terpresensi([r['id'] for r in rows])

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
            'selesai': r['id'] in jadwal_terpresensi,
            'kelas_id': r['kelas_id'],
            'hari': r['hari'],
            'tanggal': f"{d.day} {BULAN[d.month - 1]} {d.year}" if d else '-',
            'pengajar_id': r['pengajar_id'],  # buat link ke profil pengajar
            'nama_pengajar': (r['pengganti_nama'] if r['pengganti_id'] else r['pengajar_nama']),
            'nama_pengajar_tetap': r['pengajar_nama'],
            'pengajar_tetap_id': r['pengajar_id'],
            'tampilan_pengajar_id': (r['pengganti_id'] if r['pengganti_id'] else r['pengajar_id']),
            'pengganti_id': r['pengganti_id'] if 'pengganti_id' in r.keys() else None,
            'is_pengganti_saya': bool(user and user.role == 'pengajar' and r['pengganti_id'] == user.id),
            'jam_mulai': jam_mulai,
            'jam_selesai': jam_selesai,
            'materi': r['materi'] or '-',
            'ruangan': r['ruangan'] or '—',
            'pengganti': bool(r['pengganti_id']) if 'pengganti_id' in r.keys() else False,
            'minggu': minggu,
            '_urut': (minggu, r['tanggal'] or '', HARI_VALID.index(r['hari']) if r['hari'] in HARI_VALID else 9, jam_mulai),
        })
    hasil.sort(key=lambda x: x['_urut'])
    return hasil


@app.route('/jadwal')
def lihat_jadwal():
    """Lihat Jadwal: siswa (jadwal kelasnya) dan pengajar (jadwal yang dia ajar). Cuma lihat, nggak bisa ubah."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user.role == 'admin':
        return redirect(url_for('kelola_jadwal'))

    # jadwal bisa disaring per kelas. Siswa default ke kelas aktifnya,
    # pengajar hanya dapat daftar kelas yang dia ajar.
    if user.role == 'siswa':
        kelas_list = user.lihat_semua_kelas()
        pilih = kelas_terpilih(kelas_list, bawaan=user.kelas_id)
        rows = user.lihat_jadwal(pilih) if pilih else [
            j for k in kelas_list for j in database.ambil_jadwal_by_kelas(k['id'])]
    else:
        # kelas yang cuma dia gantikan ikut masuk daftar filter, kalau tidak
        # baris jadwalnya muncul tapi kelasnya tidak ada di pilihan (membingungkan).
        kelas_list = user.lihat_kelas_diajar()
        ada = {k['id'] for k in kelas_list}
        for kelas_id in sorted(user.kelas_pengganti() - ada):
            kelas_row = database.ambil_kelas_by_id(kelas_id)
            if kelas_row:
                kelas_list.append(database.kelas_jadi_dict(kelas_row))
        pilih = kelas_terpilih(kelas_list)
        rows = user.lihat_jadwal_mengajar()
        if pilih:
            rows = [j for j in rows if j['kelas_id'] == pilih]

    kelas_list = database.status_kelas_list(kelas_list)
    return render_template('kelola_jadwal.html', jadwal_list=siapkan_jadwal_list(rows, user),
                           kelas_list=kelas_list, pengajar_list=[], bisa_kelola=False,
                           kelas_pilih=pilih, user=user)


@app.route('/admin/jadwal', methods=['GET', 'POST'])
def kelola_jadwal():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        hari = request.form.get('hari', '')
        jam_mulai = request.form.get('jam_mulai', '')
        jam_selesai = request.form.get('jam_selesai', '')
        kelas_id = request.form.get('kelas_id', '')
        pengajar_id = request.form.get('pengajar_id', '')
        tanggal = request.form.get('tanggal', '')
        materi = request.form.get('materi', '')
        pengganti_id = request.form.get('pengganti_id') or None
        ruangan = request.form.get('ruangan', '')

        try:
            user.kelola_jadwal('tambah', hari=hari, jam_mulai=jam_mulai, jam_selesai=jam_selesai,
                               kelas_id=kelas_id, pengajar_id=pengajar_id,
                               tanggal=tanggal, materi=materi, pengganti_id=pengganti_id, ruangan=ruangan)
            flash('Jadwal berhasil ditambahkan!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')

        return redirect(url_for('kelola_jadwal'))

    kelas_list = database.ambil_semua_kelas()
    pilih = kelas_terpilih(kelas_list)  # admin bisa menyaring jadwal per kelas
    rows = database.ambil_semua_jadwal()
    if pilih:
        rows = [j for j in rows if j['kelas_id'] == pilih]

    kelas_list = database.status_kelas_list(kelas_list)
    return render_template('kelola_jadwal.html', jadwal_list=siapkan_jadwal_list(rows, user),
                           kelas_list=kelas_list, pengajar_list=database.ambil_semua_pengajar(),
                           bisa_kelola=True, kelas_pilih=pilih, user=user)


@app.route('/admin/jadwal/edit/<int:jadwal_id>', methods=['POST'])  # route edit jadwal
def edit_jadwal(jadwal_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_jadwal('edit', jadwal_id=jadwal_id,
                           hari=request.form.get('hari', ''),
                           jam_mulai=request.form.get('jam_mulai', ''),
                           jam_selesai=request.form.get('jam_selesai', ''),
                           kelas_id=request.form.get('kelas_id', ''),
                           pengajar_id=request.form.get('pengajar_id', ''),
                           tanggal=request.form.get('tanggal', ''),
                           materi=request.form.get('materi', ''),
                           pengganti_id=request.form.get('pengganti_id') or None,
                           ruangan=request.form.get('ruangan', ''))
        flash('Jadwal berhasil diperbarui!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_jadwal'))


@app.route('/admin/jadwal/delete/<int:jadwal_id>')  # route hapus jadwal
def hapus_jadwal(jadwal_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_jadwal('hapus', jadwal_id=jadwal_id)
        flash('Jadwal berhasil dihapus!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_jadwal'))


# --- ROUTE MATERI (UPLOAD, EDIT, DOWNLOAD, HAPUS) ---

@app.route('/kelas/<int:kelas_id>/materi', methods=['GET', 'POST'])
def kelola_materi(kelas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    kelas = database.ambil_kelas_by_id(kelas_id)
    if not kelas:
        flash('Kelas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    if not user.boleh_akses_kelas(kelas_id):
        flash('Kamu tidak punya akses ke kelas ini.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        if user.role != 'pengajar':
            flash('Hanya pengajar yang dapat mengunggah materi.', 'danger')
            return redirect(url_for('kelola_materi', kelas_id=kelas_id))

        filename = None
        try:
            filename = simpan_file('file_materi')
            user.upload_materi(kelas_id, request.form.get('judul', ''),
                               request.form.get('kategori', ''), filename)
            flash('Materi berhasil diunggah!', 'success')
        except ValueError as e:
            hapus_file(filename)
            flash(str(e), 'danger')
        return redirect(url_for('kelola_materi', kelas_id=kelas_id))

    materi_list = database.ambil_materi_by_kelas(kelas_id)
    return render_template('materi.html', kelas=kelas, materi_list=materi_list, user=user,
                           tab='materi', pengajar_list=database.ambil_pengajar_kelas(kelas))


@app.route('/materi/<int:materi_id>')  # halaman detail satu materi (lihat + unduh berkas)
def detail_materi(materi_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    row = database.ambil_materi_by_id(materi_id)
    if not row:
        flash('Materi tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))
    if not user.boleh_akses_kelas(row['kelas_id']):
        flash('Kamu tidak punya akses ke materi ini.', 'danger')
        return redirect(url_for('dashboard'))

    kelas = database.ambil_kelas_by_id(row['kelas_id'])
    penulis = database.ambil_user_by_id(row['pengajar_id'])
    materi = Materi.dari_row(row)
    return render_template('detail_materi.html', kelas=kelas, materi=materi, baris=row, user=user,
                           tab='materi', pengajar_list=database.ambil_pengajar_kelas(kelas),
                           nama_pengajar=penulis['nama'] if penulis else 'Pengajar')


@app.route('/materi/edit/<int:materi_id>', methods=['POST'])
def edit_materi(materi_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    materi = database.ambil_materi_by_id(materi_id)
    if not materi:
        flash('Materi tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    filename = None
    try:
        filename = simpan_file('file_materi')  # opsional, kosong = pakai file lama
        user.edit_materi(materi_id, request.form.get('judul', ''),
                         request.form.get('kategori', ''), filename)
        flash('Materi berhasil diperbarui!', 'success')
    except ValueError as e:
        hapus_file(filename)
        flash(str(e), 'danger')
    return redirect(url_for('kelola_materi', kelas_id=materi['kelas_id']))


@app.route('/materi/download/<int:materi_id>')
def download_materi(materi_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    materi = database.ambil_materi_by_id(materi_id)
    if not materi or not materi['file_path']:
        flash('Materi tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))
    if not user.boleh_akses_kelas(materi['kelas_id']):
        flash('Kamu tidak punya akses ke materi ini.', 'danger')
        return redirect(url_for('dashboard'))

    nama_asli = re.sub(r'^[0-9a-f]{8}_', '', materi['file_path'])  # buang awalan unik
    return send_from_directory(app.config['UPLOAD_FOLDER'], materi['file_path'],
                               as_attachment=True, download_name=nama_asli)


@app.route('/materi/hapus/<int:materi_id>')
def hapus_materi(materi_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    try:
        kelas_id = user.hapus_materi(materi_id)
        flash('Materi berhasil dihapus!', 'success')
        return redirect(url_for('kelola_materi', kelas_id=kelas_id))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('dashboard'))


# --- ROUTE TUGAS (BUAT, KUMPUL, KOMENTAR, NILAI) ---

@app.route('/kelas/<int:kelas_id>/tugas')
def daftar_tugas(kelas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    kelas = database.ambil_kelas_by_id(kelas_id)
    if not kelas:
        flash('Kelas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))
    if not user.boleh_akses_kelas(kelas_id):
        flash('Kamu tidak punya akses ke kelas ini.', 'danger')
        return redirect(url_for('dashboard'))

    tugas_list = database.ambil_tugas_by_kelas(kelas_id)
    return render_template('tugas.html', kelas=kelas, tugas_list=tugas_list, user=user,
                           tab='tugas', pengajar_list=database.ambil_pengajar_kelas(kelas))


@app.route('/tugas/tambah/<int:kelas_id>', methods=['POST'])
def buat_tugas(kelas_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    filename = None
    try:
        # Validasi dasar sebelum menyimpan file, agar upload gagal tidak meninggalkan berkas.
        filename = simpan_file('file_lampiran')
        user.buat_tugas(kelas_id, request.form.get('judul', ''),
                        request.form.get('deskripsi', ''), request.form.get('deadline', ''), filename)
        flash('Tugas berhasil dibuat!', 'success')
    except ValueError as e:
        hapus_file(filename)
        flash(str(e), 'danger')
    return redirect(url_for('daftar_tugas', kelas_id=kelas_id))


@app.route('/tugas/<int:tugas_id>', methods=['GET'])
def detail_tugas(tugas_id):
    """Tab Petunjuk + Tugas Siswa. Siswa lihat pengumpulan & percakapan privatnya sendiri;
    pengajar/admin lihat daftar seluruh siswa kelas itu, satu percakapan privat per siswa."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    tugas = database.ambil_tugas_by_id(tugas_id)
    if not tugas:
        flash('Tugas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))
    if not user.boleh_akses_kelas(tugas['kelas_id']):
        flash('Kamu tidak punya akses ke tugas ini.', 'danger')
        return redirect(url_for('dashboard'))

    kelas = database.ambil_kelas_by_id(tugas['kelas_id'])
    baris_siswa, komentar = [], {}

    if user.role == 'siswa':
        pengumpulan = database.ambil_pengumpulan_by_tugas_siswa(tugas_id, user.id)
        # komentar sekarang privat, jadi siswa hanya menerima percakapannya sendiri
        komentar[user.id] = database.ambil_komentar_tugas(tugas_id, user.id)
    else:
        pengumpulan = None
        baris_siswa = database.ambil_pengumpulan_lengkap(tugas_id, tugas['kelas_id'])
        for b in baris_siswa:
            komentar[b['siswa_id']] = database.ambil_komentar_tugas(tugas_id, b['siswa_id'])

    penulis = database.ambil_user_by_id(tugas['pengajar_id'])
    return render_template('detail_tugas.html', tugas=tugas, kelas=kelas, pengumpulan=pengumpulan,
                           baris_siswa=baris_siswa, komentar=komentar, user=user, tab='tugas',
                           pengajar_list=database.ambil_pengajar_kelas(kelas),
                           nama_pengajar=penulis['nama'] if penulis else 'Pengajar',
                           sudah_lewat=Tugas.dari_row(tugas).is_expired())


@app.route('/tugas/edit/<int:tugas_id>', methods=['POST'])  # pengajar mengubah tugasnya
def edit_tugas(tugas_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))
    filename = None
    lama = database.ambil_tugas_by_id(tugas_id)
    try:
        hapus_lampiran = request.form.get('hapus_lampiran') == '1'
        if hapus_lampiran and request.files.get('file_lampiran') and request.files['file_lampiran'].filename:
            raise ValueError('Pilih ganti file atau hapus lampiran, bukan keduanya.')
        filename = simpan_file('file_lampiran')
        kelas_id = user.edit_tugas(tugas_id, request.form.get('judul', ''),
                                   request.form.get('deskripsi', ''),
                                   request.form.get('deadline', ''), filename, hapus_lampiran)
        # Berkas lama dibuang hanya SETELAH data berhasil diperbarui.
        if lama and lama['file_lampiran'] and (filename or hapus_lampiran):
            hapus_file(lama['file_lampiran'])
        flash('Tugas berhasil diperbarui!', 'success')
        return redirect(url_for('daftar_tugas', kelas_id=kelas_id))
    except ValueError as e:
        hapus_file(filename)
        flash(str(e), 'danger')
        return redirect(url_for('daftar_tugas', kelas_id=lama['kelas_id']) if lama else url_for('dashboard'))


@app.route('/tugas/hapus/<int:tugas_id>')  # pengajar menghapus tugasnya
def hapus_tugas(tugas_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))
    try:
        data_lama = database.ambil_tugas_by_id(tugas_id)
        kelas_id = user.hapus_tugas(tugas_id)
        if data_lama and data_lama['file_lampiran']:
            hapus_file(data_lama['file_lampiran'])
        flash('Tugas berhasil dihapus!', 'success')
        return redirect(url_for('daftar_tugas', kelas_id=kelas_id))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('dashboard'))


@app.route('/tugas/<int:tugas_id>/lampiran')
def unduh_lampiran_tugas(tugas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    tugas = database.ambil_tugas_by_id(tugas_id)
    if not tugas or not user.boleh_akses_kelas(tugas['kelas_id']) or not tugas['file_lampiran']:
        flash('Lampiran tugas tidak tersedia.', 'danger')
        return redirect(url_for('dashboard'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], tugas['file_lampiran'],
                               as_attachment=True, download_name=nama_berkas(tugas['file_lampiran']))


@app.route('/tugas/<int:tugas_id>/kumpul', methods=['POST'])
def kumpul_tugas(tugas_id):
    user = get_current_user()
    if not user or user.role != 'siswa':
        return redirect(url_for('login'))

    filename = None
    try:
        filename = simpan_file('file_jawaban')
        if not filename:
            raise ValueError('Pilih file jawaban terlebih dahulu!')
        sebelumnya = database.ambil_pengumpulan_by_tugas_siswa(tugas_id, user.id)
        user.kumpul_tugas(tugas_id, filename)
        if sebelumnya and sebelumnya['file_jawaban'] and sebelumnya['file_jawaban'] != filename:
            hapus_file(sebelumnya['file_jawaban'])
        flash('Tugas berhasil dikumpulkan!', 'success')
    except ValueError as e:
        hapus_file(filename)
        flash(str(e), 'danger')
    return redirect(url_for('detail_tugas', tugas_id=tugas_id, pane='siswa'))


@app.route('/tugas/<int:tugas_id>/jawaban/hapus', methods=['POST'])
def tarik_kembali_jawaban(tugas_id):
    user = get_current_user()
    if not user or user.role != 'siswa':
        return redirect(url_for('login'))
    tugas = database.ambil_tugas_by_id(tugas_id)
    if not tugas or not user.boleh_akses_kelas(tugas['kelas_id']):
        flash('Tugas tidak ditemukan atau bukan kelas kamu.', 'danger')
        return redirect(url_for('dashboard'))
    try:
        nama = database.hapus_jawaban_belum_dinilai(tugas_id, user.id)
        hapus_file(nama)
        flash('File jawaban dihapus. Tugas bisa dikumpulkan kembali nanti.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('detail_tugas', tugas_id=tugas_id, pane='siswa'))


@app.route('/tugas/<int:tugas_id>/komentar', methods=['POST'])
def tambah_komentar_tugas(tugas_id):
    """komentar masuk ke percakapan privat satu siswa. Siswa otomatis ke percakapannya
    sendiri; pengajar wajib menyebut siswa yang dibalas (dikirim lewat field tersembunyi)."""
    user = get_current_user()
    if not user or user.role not in ('siswa', 'pengajar'):
        return redirect(url_for('login'))

    siswa_id = request.form.get('siswa_id', '')
    try:
        # POLYMORPHISM: nama methodnya sama, tapi Siswa mengisi siswa_id sendiri sedangkan
        # Pengajar menerimanya sebagai parameter — aturannya ada di class masing-masing.
        if user.role == 'siswa':
            user.komentar_tugas(tugas_id, request.form.get('isi_komentar', ''))
        else:
            user.komentar_tugas(tugas_id, request.form.get('isi_komentar', ''), siswa_id)
        flash('Komentar berhasil dikirim.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('detail_tugas', tugas_id=tugas_id, pane='siswa'))


@app.route('/pengumpulan/<int:pengumpulan_id>/nilai', methods=['POST'])
def beri_nilai_tugas(pengumpulan_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    data = database.ambil_pengumpulan_by_id(pengumpulan_id)
    if not data:
        flash('Pengumpulan tugas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        user.beri_nilai(pengumpulan_id, request.form.get('nilai', ''))
        flash('Nilai berhasil disimpan!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('detail_tugas', tugas_id=data['tugas_id'], pane='siswa'))


@app.route('/pengumpulan/<int:pengumpulan_id>/nilai/hapus', methods=['GET', 'POST'])
def hapus_nilai_tugas(pengumpulan_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    data = database.ambil_pengumpulan_by_id(pengumpulan_id)
    if not data:
        flash('Pengumpulan tugas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        tugas_id = user.hapus_nilai(pengumpulan_id)
        flash('Nilai berhasil dihapus!', 'success')
        return redirect(url_for('detail_tugas', tugas_id=tugas_id, pane='siswa'))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('detail_tugas', tugas_id=data['tugas_id'], pane='siswa'))


# --- ROUTE CATATAN AKHIR (dari profil siswa, oleh pengajar) ---
@app.route('/kelas/<int:kelas_id>/catatan/<int:siswa_id>', methods=['POST'])
def simpan_catatan_akhir(kelas_id, siswa_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    try:
        # + penanda kelulusan yang dicentang pengajar di form catatan akhir
        user.beri_catatan_akhir(kelas_id, siswa_id, request.form.get('catatan', ''),
                                lulus=bool(request.form.get('lulus')))
        flash('Catatan akhir berhasil disimpan!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('monitoring_siswa', siswa_id=siswa_id))  # balik ke Monitoring



@app.route('/catatan/<int:catatan_id>/hapus')  # pengajar menghapus catatan akhirnya
def hapus_catatan_akhir(catatan_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))
    try:
        siswa_id = user.hapus_catatan_akhir(catatan_id)
        flash('Catatan akhir berhasil dihapus.', 'success')
        return redirect(url_for('monitoring_siswa', siswa_id=siswa_id))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('monitoring'))


# --- ROUTE MONITORING ---
#   siswa    -> user.lihat_monitoring()
#   pengajar -> user.lihat_monitoring_siswa(siswa_id)   (dibuka dari tombol di profil siswa)
#   admin    -> user.monitoring_sistem()  /  user.lihat_monitoring_siswa(siswa_id)
@app.route('/monitoring')
def monitoring():
    """Siswa langsung melihat monitoringnya sendiri. Admin & pengajar melihat daftar siswa
    dulu, baru masuk ke monitoring per anak."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    if user.role == 'siswa':
        row = database.ambil_user_by_id(user.id)
        daftar_kelas = user.lihat_semua_kelas()
        pilih = request.args.get('kelas', type=int) or row['kelas_id']
        if pilih and pilih not in {k['id'] for k in daftar_kelas}:
            flash('Kelas tidak tersedia.', 'danger')
            return redirect(url_for('monitoring'))
        kelas = database.ambil_kelas_by_id(pilih) if pilih else None
        return render_template('monitoring.html', user=user, data=user.lihat_monitoring(pilih),
                               siswa=row, daftar=None, ringkasan=None, daftar_kelas=daftar_kelas,
                               bisa_beri_catatan=False, kelas_id=pilih, kelas=kelas,
                               pengajar_list=database.ambil_pengajar_kelas(kelas) if kelas else [])

    daftar = database.ambil_monitoring_semua_siswa()
    kelas_monitoring = database.ambil_semua_kelas() if user.role == 'admin' else user.lihat_kelas_diajar()
    pilih_monitoring = kelas_terpilih(kelas_monitoring)
    if pilih_monitoring:
        daftar = [d for d in daftar if d['kelas_id'] == pilih_monitoring]
    # Statistik keseluruhan tersedia di Dashboard, tidak diduplikasi di Monitoring.
    if user.role != 'admin':
        # pengajar cuma melihat siswa di kelas yang dia ajar
        kelas_diajar = {k['id'] for k in user.lihat_kelas_diajar()}
        daftar = [d for d in daftar if d['kelas_id'] in kelas_diajar]

    kelas_monitoring = database.status_kelas_list(kelas_monitoring)
    return render_template('monitoring.html', user=user, data=None, siswa=None,
                           daftar=daftar, ringkasan=None, bisa_beri_catatan=False,
                           kelas_list=kelas_monitoring, kelas_pilih=pilih_monitoring)


@app.route('/monitoring/<int:siswa_id>')
def monitoring_siswa(siswa_id):
    """Monitoring satu anak: rekap presensi, rekap nilai, dan catatan akhir pengajar."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    row = database.ambil_user_by_id(siswa_id)
    if not row or row['role'] != 'siswa':
        flash('Siswa tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    # POLYMORPHISM: aturan "siapa boleh lihat siswa ini" ada di class tiap role
    if not user.boleh_lihat_siswa(row):
        flash('Kamu tidak punya akses ke monitoring siswa ini.', 'danger')
        return redirect(url_for('dashboard'))

    daftar_kelas = [dict(r) for r in database.ambil_riwayat_kelas_siswa(siswa_id)]
    pilih = request.args.get('kelas', type=int) or row['kelas_id']
    if pilih and pilih not in {k['id'] for k in daftar_kelas}:
        flash('Riwayat kelas tidak tersedia.', 'danger')
        return redirect(url_for('monitoring_siswa', siswa_id=siswa_id))
    if user.role == 'pengajar' and pilih and not user.mengajar_kelas(pilih):
        flash('Kelas bukan tanggung jawab pengajar.', 'danger')
        return redirect(url_for('monitoring'))
    siswa_objek = buat_objek_user(row)
    data = siswa_objek.lihat_monitoring(pilih)
    kelas = database.ambil_kelas_by_id(pilih) if pilih else None
    return render_template('monitoring.html', user=user, data=data, siswa=row, daftar=None,
                           ringkasan=None, kelas_id=pilih, kelas=kelas, daftar_kelas=daftar_kelas,
                           pengajar_list=database.ambil_pengajar_kelas(kelas) if kelas else [],
                           bisa_beri_catatan=(user.role == 'pengajar' and bool(pilih)
                                              and user.mengajar_kelas(pilih)
                                              and row['kelas_id'] == pilih))

# --- ROUTE PRESENSI ---
def siapkan_presensi_list(kelas_id):
    """Satu panel per ID jadwal, termasuk dua pertemuan di tanggal yang sama."""
    jadwal_kelas = sorted(database.ambil_jadwal_by_kelas(kelas_id),
                         key=lambda j: (j['tanggal'] or '', j['jam'] or '', j['id']), reverse=True)
    hasil = []
    for j in jadwal_kelas:
        tanggal = j['tanggal']
        if not tanggal: continue
        try: label = Presensi.format_label(tanggal)
        except ValueError: continue
        rows = database.ambil_presensi_kelas_tanggal(kelas_id, tanggal, j['id'])
        status = {p['siswa_id']: p['status'].lower() for p in rows
                  if p['status'] and p['status'].lower() in ('hadir','izin','sakit','alfa','alpha','alpa')}
        id_guru = next((p['pengajar_id'] for p in rows if p['pengajar_id']), None)
        guru = database.ambil_user_by_id(id_guru) if id_guru else None
        nama_pengajar = guru['nama'] if guru else (j['pengganti_nama'] or j['pengajar_nama'])
        hasil.append({'jadwal_id': j['id'], 'tanggal': tanggal, 'label': label,
                      'jam': j['jam'], 'ruangan': j['ruangan'] or '—',
                      'status': status, 'materi': j['materi'], 'nama_pengajar': nama_pengajar,
                      'pengganti_id': j['pengganti_id']})
    return hasil


@app.route('/kelas/<int:kelas_id>/presensi', methods=['POST'])
def simpan_presensi(kelas_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    # siswa yang tampil di form tapi centangnya dilepas ikut dikirim, supaya
    # presensinya dihapus (sebelumnya centang yang salah pencet tidak bisa dibatalkan).
    tampil = {int(x) for x in request.form.get('siswa_tampil', '').split(',') if x.strip().isdigit()}
    data_status, kosongkan = {}, []
    for s in database.ambil_siswa_by_kelas(kelas_id):
        st = request.form.get(f"st_{s['id']}")
        if st:
            data_status[s['id']] = st
        elif s['id'] in tampil:
            kosongkan.append(s['id'])

    try:
        jumlah = user.catat_presensi_kelas(kelas_id, request.form.get('tanggal', ''),
                                           data_status, kosongkan,
                                           jadwal_id=request.form.get('jadwal_id', type=int))
        flash(f'Presensi {jumlah} siswa berhasil disimpan!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    # tanggal pertemuan yang barusan diisi ikut dibawa, biar pilihan tanggalnya
    # tidak balik sendiri ke pertemuan paling baru.
    return redirect(url_for('detail_kelas', kelas_id=kelas_id,
                            jadwal=request.form.get('jadwal_id', '') or None))


@app.route('/kelas/<int:kelas_id>/presensi/batal/<int:jadwal_id>', methods=['GET', 'POST'])
def batalkan_presensi(kelas_id, jadwal_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    jadwal = database.ambil_jadwal_by_id(jadwal_id)
    try:
        if not jadwal or jadwal['kelas_id'] != kelas_id:
            raise ValueError('Pertemuan tidak ditemukan.')
        user.batalkan_presensi_kelas(kelas_id, jadwal['tanggal'], jadwal_id=jadwal_id)
        flash('Presensi pertemuan berhasil dibatalkan!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('detail_kelas', kelas_id=kelas_id, jadwal=jadwal_id))


@app.route('/jadwal/<int:jadwal_id>/presensi/batal', methods=['GET', 'POST'])
def batalkan_presensi_jadwal(jadwal_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    jadwal = database.ambil_jadwal_by_id(jadwal_id)
    if not jadwal or not jadwal['tanggal'] or not user.boleh_presensi_jadwal(jadwal):
        flash('Kamu tidak memiliki akses presensi untuk jadwal ini.', 'danger')
        return redirect(url_for('lihat_jadwal'))

    try:
        user.batalkan_presensi_kelas(jadwal['kelas_id'], jadwal['tanggal'], jadwal_id=jadwal_id)
        flash('Presensi pertemuan berhasil dibatalkan!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('presensi_jadwal', jadwal_id=jadwal_id))


@app.route('/jadwal/<int:jadwal_id>/presensi', methods=['GET', 'POST'])
def presensi_jadwal(jadwal_id):
    """Halaman presensi terbatas untuk satu jadwal, terutama bagi pengajar pengganti."""
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    jadwal = database.ambil_jadwal_by_id(jadwal_id)
    if not jadwal or not jadwal['tanggal'] or not user.boleh_presensi_jadwal(jadwal):
        flash('Kamu tidak memiliki akses presensi untuk jadwal ini.', 'danger')
        return redirect(url_for('lihat_jadwal'))

    kelas_id = jadwal['kelas_id']
    tanggal = jadwal['tanggal']
    if request.method == 'POST':
        tampil = {int(x) for x in request.form.get('siswa_tampil', '').split(',') if x.strip().isdigit()}
        data_status, kosongkan = {}, []
        for siswa in database.ambil_siswa_by_kelas(kelas_id):
            st = request.form.get(f"st_{siswa['id']}")
            if st:
                data_status[siswa['id']] = st
            elif siswa['id'] in tampil:
                kosongkan.append(siswa['id'])
        try:
            # Pastikan form tidak dapat mengganti tanggal jadwal lewat POST.
            if request.form.get('tanggal') != tanggal:
                raise ValueError('Tanggal presensi tidak sesuai dengan jadwal yang ditugaskan.')
            jumlah = user.catat_presensi_kelas(kelas_id, tanggal, data_status, kosongkan, jadwal_id=jadwal_id)
            flash(f'Presensi {jumlah} siswa berhasil disimpan!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        return redirect(url_for('presensi_jadwal', jadwal_id=jadwal_id))

    siswa_list = database.ambil_siswa_by_kelas(kelas_id)
    status = {p.siswa_id: p.status.lower() for p in Presensi.ambil_kelas(kelas_id, tanggal, jadwal_id)
              if p.status in Presensi.STATUS_VALID}
    try:
        label_tanggal = Presensi.format_label(tanggal)
    except ValueError:
        label_tanggal = tanggal
    return render_template('presensi_jadwal.html', user=user, jadwal=jadwal,
                           kelas=database.ambil_kelas_by_id(kelas_id), siswa_list=siswa_list,
                           status=status, label_tanggal=label_tanggal)


if __name__ == '__main__':
    app.run(debug=True)