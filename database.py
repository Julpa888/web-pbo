import os
import sqlite3
from datetime import datetime
# password disimpan apa adanya supaya admin bisa membacanya lewat tombol mata
# di Kelola Akun. check_password_hash cuma dipakai untuk membaca akun lama yang
# terlanjur tersimpan ter-hash (lihat User.cek_password di models/user.py).
from werkzeug.security import check_password_hash

# Setiap kelas memiliki delapan pertemuan; jumlah selesai ditentukan dari presensi.
TOTAL_PERTEMUAN_KELAS = 8

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# path absolut, jadi nggak peduli app dijalankan dari folder mana
DB_NAME = os.path.join(BASE_DIR, 'fluenglo.db')

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# waktu lokal (WITA/WIB sesuai komputer), bukan UTC-nya CURRENT_TIMESTAMP,
# biar jam yang tampil di komentar & materi sama dengan jam di jam dinding.
def sekarang():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def password_sudah_hash(nilai):
    """True kalau nilai di kolom password masih berupa hash dari versi lama."""
    return isinstance(nilai, str) and nilai.startswith(('pbkdf2:', 'scrypt:', 'argon2'))


def cocok_hash_lama(tersimpan, password):
    """Cocokkan password dengan hash lama. Dipakai sekali saja waktu akun lama login,
    setelah itu passwordnya ditulis ulang apa adanya supaya bisa dibaca admin."""
    try:
        return check_password_hash(tersimpan, password or "")
    except Exception:
        return False

def migrasi():
    """Samain fluenglo.db lama dengan schema terbaru (aman dijalankan berulang kali).
    - tabel yang belum ada (pengumpulan, komentar, catatan_akhir, dst) dibuat dari schema.sql
    - kelas.pengajar_id2 : guru kedua (opsional) tiap kelas
    - jadwal.tanggal / jadwal.materi / jadwal.pengganti_id : data pertemuan dan pengajar pengganti
    - users.alamat / users.nik / users.email : data profil (revisi dosen)
    """
    conn = get_connection()
    try:
        with open(os.path.join(BASE_DIR, 'schema.sql'), 'r', encoding='utf-8') as f:
            conn.executescript(f.read())

        def kolom(tabel):
            return [r['name'] for r in conn.execute(f'PRAGMA table_info({tabel})')]
        tambahan = [
            ('kelas', 'pengajar_id2', 'INTEGER'),
            ('jadwal', 'tanggal', 'TEXT'),
            ('jadwal', 'materi', 'TEXT'),
            ('jadwal', 'ruangan', 'TEXT'),
            ('jadwal', 'pengganti', 'INTEGER'),  # kolom lama untuk kompatibilitas migrasi
            ('jadwal', 'pengganti_id', 'INTEGER REFERENCES users(id)'),
            ('users', 'alamat', 'TEXT'),
            ('users', 'nik', 'TEXT'),
            ('users', 'email', 'TEXT'),
            ('kelas', 'deskripsi', 'TEXT'),
            # gambar latar kartu kelas yang dipilih admin
            ('kelas', 'header', 'TEXT'),
            # tanggal posting & tanggal edit materi/tugas (dipakai di feed kelas)
            ('materi', 'tanggal_upload', 'TEXT'),
            ('materi', 'tanggal_edit', 'TEXT'),
            ('tugas', 'tanggal_dibuat', 'TEXT'),
            ('tugas', 'tanggal_edit', 'TEXT'),
            ('tugas', 'file_lampiran', 'TEXT'),
            # komentar jadi percakapan privat per siswa, bukan satu kelas ramai-ramai
            ('komentar', 'siswa_id', 'INTEGER'),
            # penanda siswa sudah lulus kelas tsb (dicentang pengajar di catatan akhir)
            ('catatan_akhir', 'lulus', 'INTEGER'),
            # isi password lama & baru di riwayat penggantian password
            ('riwayat_password', 'password_lama', 'TEXT'),
            ('riwayat_password', 'password_baru', 'TEXT'),
            # Pengajar yang benar-benar menyimpan/mengubah presensi per pertemuan.
            ('presensi', 'pengajar_id', 'INTEGER'),
        ]
        for tabel, nama, tipe in tambahan:
            ada = kolom(tabel)
            if ada and nama not in ada:
                conn.execute(f'ALTER TABLE {tabel} ADD COLUMN {nama} {tipe}')
        # Database lama menegakkan UNIQUE(tanggal, siswa_id, kelas_id).
        # Untuk 2 sesi di hari sama, gunakan UNIQUE(jadwal_id, siswa_id).
        # Rekonstruksi hanya sekali; ID/status/riwayat lama dipertahankan.
        presensi_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='presensi'").fetchone()[0]
        if 'jadwal_id' not in kolom('presensi') or 'UNIQUE (tanggal, siswa_id, kelas_id)' in presensi_sql or 'UNIQUE(tanggal, siswa_id, kelas_id)' in presensi_sql:
            conn.execute('DROP TABLE IF EXISTS presensi_migrasi')
            conn.execute("""CREATE TABLE presensi_migrasi (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tanggal TEXT NOT NULL,
                siswa_id INTEGER NOT NULL, kelas_id INTEGER NOT NULL,
                status TEXT DEFAULT 'Belum Hadir', pengajar_id INTEGER,
                jadwal_id INTEGER REFERENCES jadwal(id),
                UNIQUE(jadwal_id, siswa_id)
            )""")
            # Tidak mungkin menebak sesi asli jika dulu satu kelas punya dua sesi
            # di tanggal yang sama; tautkan data warisan hanya ke sesi pertama.
            conn.execute("""INSERT INTO presensi_migrasi(id,tanggal,siswa_id,kelas_id,status,pengajar_id,jadwal_id)
                SELECT p.id,p.tanggal,p.siswa_id,p.kelas_id,p.status,p.pengajar_id,
                    (SELECT j.id FROM jadwal j WHERE j.kelas_id=p.kelas_id AND j.tanggal=p.tanggal
                     ORDER BY j.jam,j.id LIMIT 1)
                FROM presensi p""")
            conn.execute('DROP TABLE presensi')
            conn.execute('ALTER TABLE presensi_migrasi RENAME TO presensi')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_presensi_jadwal ON presensi(jadwal_id)')
        # Jadwal lama belum memiliki ruangan; sengaja dibiarkan NULL, bukan
        # menebak A01/A02/A03 yang dapat menghasilkan bentrok palsu.
        # Migrasi data lama: dulu pengganti disimpan sebagai pengajar_id + flag.
        # Kembalikan pengajar_id ke pengajar tetap kelas dan pindahkan ID lama.
        if 'pengganti' in kolom('jadwal') and 'pengganti_id' in kolom('jadwal'):
            conn.execute("""
                UPDATE jadwal
                SET pengganti_id = pengajar_id,
                    pengajar_id = (SELECT k.pengajar_id FROM kelas k WHERE k.id = jadwal.kelas_id),
                    pengganti = 0
                WHERE pengganti = 1 AND pengganti_id IS NULL
                  AND EXISTS (SELECT 1 FROM kelas k WHERE k.id = jadwal.kelas_id)
            """)
        # Data yang sudah ada hanya menyimpan kelas aktif. Backfill satu kali
        # dari jadwal pertama kelas sebagai perkiraan awal keanggotaan lama;
        # tidak membuat/menghapus catatan presensi, nilai, atau tugas apa pun.
        conn.execute("""
            INSERT INTO riwayat_kelas(siswa_id, kelas_id, tanggal_mulai)
            SELECT u.id, u.kelas_id,
                   COALESCE((SELECT MIN(j.tanggal) FROM jadwal j
                             WHERE j.kelas_id = u.kelas_id AND j.tanggal IS NOT NULL),
                            date('now','localtime'))
            FROM users u WHERE u.role = 'siswa' AND u.kelas_id IS NOT NULL
              AND NOT EXISTS(SELECT 1 FROM riwayat_kelas r
                             WHERE r.siswa_id = u.id AND r.kelas_id = u.kelas_id
                               AND r.tanggal_selesai IS NULL)
        """)
        conn.execute("""
            INSERT INTO riwayat_kelas(siswa_id, kelas_id, tanggal_mulai, tanggal_selesai)
            SELECT c.siswa_id, c.kelas_id,
                   COALESCE((SELECT MIN(j.tanggal) FROM jadwal j
                             WHERE j.kelas_id = c.kelas_id AND j.tanggal IS NOT NULL),
                            substr(c.tanggal_dibuat, 1, 10)),
                   substr(c.tanggal_dibuat, 1, 10)
            FROM catatan_akhir c
            WHERE c.lulus = 1 AND NOT EXISTS
                (SELECT 1 FROM riwayat_kelas r
                 WHERE r.siswa_id = c.siswa_id AND r.kelas_id = c.kelas_id)
        """)
        conn.commit()
    finally:
        conn.close()

# --- USER FUNCTIONS ---
def ambil_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return row

def ambil_user_by_username(username):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return row

def ambil_semua_user():
    conn = get_connection()
    rows = conn.execute('''
        SELECT u.*, k.nama AS kelas_nama,
               CASE WHEN u.role = 'siswa' AND u.kelas_id IS NOT NULL AND EXISTS (
                   SELECT 1 FROM catatan_akhir c
                   WHERE c.siswa_id = u.id AND c.kelas_id = u.kelas_id AND c.lulus = 1
               ) THEN 1 ELSE 0 END AS lulus
        FROM users u
        LEFT JOIN kelas k ON u.kelas_id = k.id
    ''').fetchall()
    conn.close()
    return rows

def ambil_semua_pengajar():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users WHERE role = 'pengajar'").fetchall()
    conn.close()
    return rows

def tambah_user(nama, username, password, role, foto=None, no_whatsapp=None, biodata=None,
                kelas_id=None, alamat=None, nik=None, email=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (nama, username, password, role, foto, no_whatsapp, biodata,
                               kelas_id, alamat, nik, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nama, username, password, role,  # password disimpan apa adanya
              foto or 'default_avatar.png', no_whatsapp,
              biodata, kelas_id, alamat, nik, email))
        if role == 'siswa' and kelas_id:
            conn.execute('INSERT INTO riwayat_kelas(siswa_id, kelas_id, tanggal_mulai) VALUES(?,?,?)',
                         (cursor.lastrowid, kelas_id, sekarang()[:10]))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Username sudah digunakan.")
    finally:
        conn.close()


def edit_user(user_id, *, record_password_history=True, **kwargs):
    """Memperbarui kolom user yang diizinkan saja."""
    kolom_diizinkan = {
        "nama", "username", "password", "role", "foto",
        "no_whatsapp", "biodata", "kelas_id", "alamat",
        "nik", "email"
    }

    if not kwargs:
        return False

    kolom_tidak_valid = set(kwargs) - kolom_diizinkan
    if kolom_tidak_valid:
        raise ValueError(
            "Kolom user tidak diizinkan: "
            + ", ".join(sorted(kolom_tidak_valid))
        )

    kolom = list(kwargs.keys())
    assignments = ", ".join(f"{nama} = ?" for nama in kolom)
    values = [kwargs[nama] for nama in kolom]
    values.append(user_id)

    conn = get_connection()
    try:
        sebelumnya = conn.execute('SELECT role, kelas_id, password FROM users WHERE id=?', (user_id,)).fetchone()
        pindah = (sebelumnya and sebelumnya['role'] == 'siswa' and 'kelas_id' in kwargs
                  and sebelumnya['kelas_id'] != kwargs['kelas_id'])
        if pindah and sebelumnya['kelas_id']:
            lulus = conn.execute('''SELECT 1 FROM catatan_akhir
                WHERE siswa_id=? AND kelas_id=? AND lulus=1''',
                (user_id, sebelumnya['kelas_id'])).fetchone()
            ada_presensi_siswa = conn.execute('''SELECT 1 FROM presensi
                WHERE siswa_id=? AND kelas_id=?
                  AND LOWER(TRIM(status)) IN ('hadir','izin','sakit','alfa','alpha','alpa')
                LIMIT 1''', (user_id, sebelumnya['kelas_id'])).fetchone()
            ada_presensi_kelas = conn.execute('''SELECT 1 FROM presensi
                WHERE kelas_id=? AND jadwal_id IS NOT NULL
                  AND LOWER(TRIM(status)) IN ('hadir','izin','sakit','alfa','alpha','alpa')
                LIMIT 1''', (sebelumnya['kelas_id'],)).fetchone()
            if (ada_presensi_siswa or ada_presensi_kelas) and not lulus:
                raise ValueError('Siswa belum dinyatakan lulus dari kelas sebelumnya oleh pengajar.')
        cursor = conn.execute(f"UPDATE users SET {assignments} WHERE id = ?", values)
        if (record_password_history and sebelumnya and 'password' in kwargs
                and kwargs['password'] != sebelumnya['password']):
            conn.execute('''INSERT INTO riwayat_password (user_id, waktu, password_lama, password_baru)
                VALUES (?, ?, ?, ?)''', (user_id, sekarang(), sebelumnya['password'], kwargs['password']))
            _pangkas_riwayat_password(conn, limit=5)
        if pindah:
            conn.execute('UPDATE riwayat_kelas SET tanggal_selesai=? WHERE siswa_id=? AND tanggal_selesai IS NULL',
                         (sekarang()[:10], user_id))
            if kwargs['kelas_id']:
                conn.execute('DELETE FROM catatan_akhir WHERE siswa_id=? AND kelas_id=?',
                             (user_id, kwargs['kelas_id']))
                conn.execute('INSERT INTO riwayat_kelas(siswa_id, kelas_id, tanggal_mulai) VALUES(?,?,?)',
                             (user_id, kwargs['kelas_id'], sekarang()[:10]))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            "Username sudah digunakan atau data melanggar aturan database."
        ) from exc
    finally:
        conn.close()


def hapus_user(user_id):
    conn = get_connection()
    try:
        # data turunan ikut dibersihkan supaya tidak ada data yatim
        # (SQLite nggak otomatis nolak/ngikut hapus lewat FOREIGN KEY)
        conn.execute('DELETE FROM presensi WHERE siswa_id = ?', (user_id,))
        conn.execute('DELETE FROM pengumpulan WHERE siswa_id = ?', (user_id,))
        conn.execute('DELETE FROM catatan_akhir WHERE siswa_id = ?', (user_id,))
        conn.execute('DELETE FROM riwayat_kelas WHERE siswa_id = ?', (user_id,))
        conn.execute('DELETE FROM komentar WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM riwayat_password WHERE user_id = ?', (user_id,))
        # BARU (revisi 3): data pendidikan ikut dibuang biar nggak jadi data yatim
        conn.execute('DELETE FROM pendidikan WHERE pengajar_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
    finally:
        conn.close()

def hitung_keterkaitan_pengajar(pengajar_id):
    """Berapa kelas / jadwal / materi / tugas yang masih nunjuk ke pengajar ini.
    Dipakai buat nolak hapus akun pengajar yang masih punya data."""
    conn = get_connection()
    try:
        return {
            'kelas': conn.execute('SELECT COUNT(*) FROM kelas WHERE pengajar_id = ? OR pengajar_id2 = ?',
                                  (pengajar_id, pengajar_id)).fetchone()[0],
            'jadwal': conn.execute('SELECT COUNT(*) FROM jadwal WHERE pengajar_id = ? OR pengganti_id = ?',
                                   (pengajar_id, pengajar_id)).fetchone()[0],
            'materi': conn.execute('SELECT COUNT(*) FROM materi WHERE pengajar_id = ?',
                                   (pengajar_id,)).fetchone()[0],
            'tugas': conn.execute('SELECT COUNT(*) FROM tugas WHERE pengajar_id = ?',
                                  (pengajar_id,)).fetchone()[0],
        }
    finally:
        conn.close()

def _pangkas_riwayat_password(conn, limit=5):
    """Pertahankan maksimal `limit` riwayat perubahan password terbaru (FIFO:
    yang paling lama keluar terlebih dahulu). Tetap simpan 1 riwayat terakhir
    untuk akun lain yang tidak termasuk 5 terbaru global agar kolom 'Diubah'
    pada tabel akun tidak kehilangan tanggal perubahan terakhirnya."""
    conn.execute('''
        DELETE FROM riwayat_password
        WHERE id NOT IN (
            SELECT id FROM riwayat_password
            ORDER BY waktu DESC, id DESC
            LIMIT ?
        )
        AND id NOT IN (
            SELECT MAX(id) FROM riwayat_password
            GROUP BY user_id
        )
    ''', (limit,))


def catat_riwayat_password(user_id, password_lama=None, password_baru=None):
    """DIUBAH: + password lama & baru, supaya admin bisa melihat perubahannya."""
    conn = get_connection()
    try:
        conn.execute('''
            INSERT INTO riwayat_password (user_id, waktu, password_lama, password_baru)
            VALUES (?, ?, ?, ?)
        ''', (user_id, sekarang(), password_lama, password_baru))
        _pangkas_riwayat_password(conn, limit=5)
        conn.commit()
    finally:
        conn.close()


def ambil_riwayat_password(limit=5):
    """Riwayat terbaru masuk dari atas (paling baru di urutan pertama), maksimal 5 entri;
    saat lebih dari 5, riwayat yang paling lama di paling bawah keluar terlebih dahulu."""
    conn = get_connection()
    try:
        return conn.execute('''
            SELECT r.id, r.waktu, r.password_lama, r.password_baru,
                   u.nama, u.role, u.username
            FROM riwayat_password r JOIN users u ON u.id = r.user_id
            ORDER BY r.waktu DESC, r.id DESC LIMIT ?
        ''', (limit,)).fetchall()
    finally:
        conn.close()

# --- PENDIDIKAN PENGAJAR ---
# Satu pengajar satu baris. Diisi admin lewat Kelola Akun; pengajar sendiri tidak punya
# route untuk mengubahnya, jadi datanya memang cuma bisa masuk dari sisi admin.
def ambil_pendidikan(pengajar_id):
    conn = get_connection()
    try:
        return conn.execute('SELECT * FROM pendidikan WHERE pengajar_id = ?',
                            (pengajar_id,)).fetchone()
    finally:
        conn.close()


def simpan_pendidikan(pengajar_id, gelar, jurusan, institusi):
    """Simpan atau perbarui pendidikan terakhir seorang pengajar."""
    conn = get_connection()
    try:
        lama = conn.execute('SELECT id FROM pendidikan WHERE pengajar_id = ?',
                            (pengajar_id,)).fetchone()
        if lama:
            conn.execute('UPDATE pendidikan SET gelar = ?, jurusan = ?, institusi = ? WHERE id = ?',
                         (gelar, jurusan, institusi, lama['id']))
            hasil = lama['id']
        else:
            cur = conn.execute('INSERT INTO pendidikan (pengajar_id, gelar, jurusan, institusi) '
                               'VALUES (?, ?, ?, ?)', (pengajar_id, gelar, jurusan, institusi))
            hasil = cur.lastrowid
        conn.commit()
        return hasil
    finally:
        conn.close()


def ambil_terakhir_ubah_password():
    """{user_id: waktu perubahan terakhir}, buat kolom 'Password Diubah'."""
    conn = get_connection()
    try:
        rows = conn.execute('SELECT user_id, MAX(waktu) AS waktu FROM riwayat_password GROUP BY user_id').fetchall()
        return {r['user_id']: r['waktu'] for r in rows}
    finally:
        conn.close()

# --- KELAS FUNCTIONS ---
def kelas_memiliki_aktivitas(kelas_id, siswa_id=None):
    """True jika kelas sudah memiliki presensi yang tercentang atau progress > 0
    (atau siswa tersebut sudah memiliki catatan presensi di kelas itu)."""
    conn = get_connection()
    try:
        ada_progress = conn.execute('''
            SELECT 1 FROM presensi
            WHERE kelas_id = ?
              AND LOWER(TRIM(status)) IN ('hadir','izin','sakit','alfa','alpha','alpa')
            LIMIT 1
        ''', (kelas_id,)).fetchone()
        if ada_progress:
            return True
        if siswa_id is not None:
            ada_siswa = conn.execute('''
                SELECT 1 FROM presensi
                WHERE kelas_id = ? AND siswa_id = ?
                  AND LOWER(TRIM(status)) IN ('hadir','izin','sakit','alfa','alpha','alpa')
                LIMIT 1
            ''', (kelas_id, siswa_id)).fetchone()
            if ada_siswa:
                return True
        return False
    finally:
        conn.close()


def ambil_kelas_tersedia_siswa(siswa_id=None):
    """Daftar kelas yang belum memiliki presensi tercentang dan progress = 0
    (untuk pilihan kelas pada Tambah Siswa / Edit Siswa di Kelola Akun)."""
    semua = status_kelas_list(ambil_semua_kelas())
    hasil = []
    for k in semua:
        if k.get('pertemuan_selesai', 0) == 0 and not kelas_memiliki_aktivitas(k['id'], siswa_id):
            hasil.append(k)
    return sorted(hasil, key=lambda x: x['id'])


def status_kelas_list(kelas_list):
    """Urutkan belum mulai/berlangsung sebelum selesai (8 sesi dengan presensi).
    Ambil sesi unik, bukan jumlah siswa. Tidak mengubah status kelulusan per siswa.
    """
    if not kelas_list:
        return []
    conn = get_connection()
    try:
        hasil = []
        for row in kelas_list:
            kelas = dict(row)
            selesai = conn.execute("""SELECT COUNT(DISTINCT jadwal_id) FROM presensi
                WHERE kelas_id=? AND jadwal_id IS NOT NULL
                  AND LOWER(TRIM(status)) IN ('hadir','izin','sakit','alfa','alpha','alpa')""",
                  (kelas['id'],)).fetchone()[0]
            selesai = min(TOTAL_PERTEMUAN_KELAS, selesai)
            kelas['pertemuan_selesai'] = selesai
            kelas['status_kelas'] = ('Selesai' if selesai >= TOTAL_PERTEMUAN_KELAS else
                                     'Berlangsung' if selesai else 'Belum Mulai')
            hasil.append(kelas)
        return sorted(hasil, key=lambda k: (k['status_kelas'] == 'Selesai',
                       k['status_kelas'] == 'Belum Mulai', k.get('nama_kelas',k.get('nama','')).casefold()))
    finally:
        conn.close()


def ambil_kelas_by_id(kelas_id):
    conn = get_connection()
    row = conn.execute('SELECT *, nama AS nama_kelas FROM kelas WHERE id = ?', (kelas_id,)).fetchone()
    conn.close()
    return row

def ambil_kelas_by_nama(nama):
    conn = get_connection()
    row = conn.execute('SELECT * FROM kelas WHERE nama = ?', (nama,)).fetchone()
    conn.close()
    return row

def ambil_pengajar_kelas(kelas_row):
    """Daftar guru sebuah kelas (1 atau 2), tiap item: id, nama, username, no_whatsapp, foto."""
    ids = [kelas_row['pengajar_id']]
    if 'pengajar_id2' in kelas_row.keys() and kelas_row['pengajar_id2']:
        ids.append(kelas_row['pengajar_id2'])
    hasil = []
    for uid in ids:
        u = ambil_user_by_id(uid)
        if u:
            hasil.append({'id': u['id'], 'nama': u['nama'], 'username': u['username'],
                          'no_whatsapp': u['no_whatsapp'], 'foto': u['foto']})
    return hasil

def kelas_jadi_dict(row):
    """Row kelas -> dict + pengajar_list (1-2 guru) + nama_pengajar (nama guru digabung)."""
    k = dict(row)
    k['pengajar_list'] = ambil_pengajar_kelas(row)
    k['nama_pengajar'] = ', '.join(p['nama'] for p in k['pengajar_list'])
    return k

def ambil_semua_kelas():
    """Tiap kelas dikembalikan sebagai dict: id, nama, nama_kelas, pengajar_id, pengajar_id2,
    pengajar_list (1-2 guru) dan nama_pengajar (nama guru digabung)."""
    conn = get_connection()
    rows = conn.execute('SELECT *, nama AS nama_kelas FROM kelas ORDER BY id').fetchall()
    conn.close()
    return [kelas_jadi_dict(r) for r in rows]

def ambil_kelas_by_pengajar(pengajar_id):
    """Kelas yang diajar seorang pengajar (jadi guru 1 maupun guru 2), format sama dgn ambil_semua_kelas."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT *, nama AS nama_kelas FROM kelas
        WHERE pengajar_id = ? OR pengajar_id2 = ? ORDER BY id
    ''', (pengajar_id, pengajar_id)).fetchall()
    conn.close()
    return [kelas_jadi_dict(r) for r in rows]

# + header, nama berkas gambar latar kartu kelas
def tambah_kelas(nama, pengajar_id, pengajar_id2=None, deskripsi=None, header=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO kelas (nama, pengajar_id, pengajar_id2, deskripsi, header) '
                   'VALUES (?, ?, ?, ?, ?)',
                   (nama, pengajar_id, pengajar_id2, deskripsi, header))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def edit_kelas(kelas_id, nama, pengajar_id, pengajar_id2=None, deskripsi=None, header=None):
    conn = get_connection()
    conn.execute('UPDATE kelas SET nama = ?, pengajar_id = ?, pengajar_id2 = ?, deskripsi = ?, '
                 'header = ? WHERE id = ?',
                 (nama, pengajar_id, pengajar_id2, deskripsi, header, kelas_id))
    conn.commit()
    conn.close()

def hapus_kelas(kelas_id):
    conn = get_connection()
    # Kelas yang pernah diikuti siswa tidak boleh menghapus histori pendidikan.
    if conn.execute('SELECT 1 FROM riwayat_kelas WHERE kelas_id=? LIMIT 1', (kelas_id,)).fetchone():
        conn.close()
        raise ValueError('Kelas tidak dapat dihapus karena memiliki riwayat keanggotaan siswa.')
    # jadwal & catatan akhir kelas ikut dihapus, siswa dilepas dari kelas, supaya tidak ada data yatim
    conn.execute('DELETE FROM jadwal WHERE kelas_id = ?', (kelas_id,))
    conn.execute('DELETE FROM catatan_akhir WHERE kelas_id = ?', (kelas_id,))
    conn.execute('DELETE FROM riwayat_kelas WHERE kelas_id = ?', (kelas_id,))
    conn.execute('UPDATE users SET kelas_id = NULL WHERE kelas_id = ?', (kelas_id,))
    conn.execute('DELETE FROM kelas WHERE id = ?', (kelas_id,))
    conn.commit()
    conn.close()

def ambil_siswa_by_kelas(kelas_id):
    conn = get_connection()
    rows = conn.execute('SELECT * FROM users WHERE role = "siswa" AND kelas_id = ? ORDER BY nama',
                        (kelas_id,)).fetchall()  # urut nama biar presensi stabil urutannya
    conn.close()
    return rows

def ambil_kelas_siswa(siswa_id):
    conn = get_connection()
    row = conn.execute('''
        SELECT k.*, k.nama AS nama_kelas FROM kelas k
        JOIN users u ON u.kelas_id = k.id
        WHERE u.id = ?
    ''', (siswa_id,)).fetchone()  # + alias nama_kelas, dipakai kartu kelas & pemilih jadwal
    conn.close()
    return row

def tambah_siswa_ke_kelas(kelas_id, siswa_id):
    conn = get_connection()
    conn.close()
    return edit_user(siswa_id, kelas_id=kelas_id)

def hapus_siswa_dari_kelas(kelas_id, siswa_id):
    """Lepas siswa hanya setelah lulus; gunakan jalur yang mencatat riwayat."""
    row = ambil_user_by_id(siswa_id)
    if not row or row['kelas_id'] != kelas_id:
        raise ValueError('Siswa tidak ada di kelas ini.')
    return edit_user(siswa_id, kelas_id=None)

def hitung_data_terkait_kelas(kelas_id):
    conn = get_connection()
    materi = conn.execute('SELECT COUNT(*) FROM materi WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    tugas = conn.execute('SELECT COUNT(*) FROM tugas WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    presensi = conn.execute('SELECT COUNT(*) FROM presensi WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    conn.close()
    return {'materi': materi, 'tugas': tugas, 'presensi': presensi}

# --- JADWAL FUNCTIONS ---
_SELECT_JADWAL = '''
    SELECT j.*, k.nama AS kelas_nama, u.nama AS pengajar_nama,
           ug.nama AS pengganti_nama
    FROM jadwal j
    JOIN kelas k ON j.kelas_id = k.id
    JOIN users u ON j.pengajar_id = u.id
    LEFT JOIN users ug ON j.pengganti_id = ug.id
'''

def ambil_jadwal_by_id(jadwal_id):
    conn = get_connection()
    try:
        return conn.execute(_SELECT_JADWAL + ' WHERE j.id = ?', (jadwal_id,)).fetchone()
    finally:
        conn.close()

def ambil_semua_jadwal():
    conn = get_connection()
    try:
        return conn.execute(_SELECT_JADWAL + ' ORDER BY j.tanggal, j.jam').fetchall()
    finally:
        conn.close()

def ambil_jadwal_by_hari(hari):
    conn = get_connection()
    try:
        return conn.execute(_SELECT_JADWAL + ' WHERE j.hari = ?', (hari,)).fetchall()
    finally:
        conn.close()

def ambil_jadwal_by_tanggal(tanggal):
    conn = get_connection()
    try:
        return conn.execute(_SELECT_JADWAL + ' WHERE j.tanggal = ?', (tanggal,)).fetchall()
    finally:
        conn.close()

def ambil_jadwal_by_kelas(kelas_id):
    conn = get_connection()
    try:
        return conn.execute(_SELECT_JADWAL + ' WHERE j.kelas_id = ?', (kelas_id,)).fetchall()
    finally:
        conn.close()

def ambil_jadwal_by_pengajar(pengajar_id):
    """Jadwal sebagai pengajar tetap saja; jadwal pengganti ditambahkan terpisah."""
    conn = get_connection()
    try:
        return conn.execute(_SELECT_JADWAL + ' WHERE j.pengajar_id = ?', (pengajar_id,)).fetchall()
    finally:
        conn.close()

def _cek_bentrok_jadwal_terkunci(conn, hari, jam, kelas_id, pengajar_id,
                                    tanggal, pengganti_id, ruangan, exclude_id=None):
    """Cek ulang dalam transaksi write lock agar dua admin tidak bisa lolos bersamaan."""
    from models.akademik import Jadwal
    mulai, akhir = Jadwal.parse_jam(jam)
    pelaksana = int(pengganti_id or pengajar_id)
    rows = conn.execute('SELECT * FROM jadwal WHERE tanggal=?', (tanggal,)).fetchall()
    for row in rows:
        if row['id'] == exclude_id: continue
        try: other_mulai, other_akhir = Jadwal.parse_jam(row['jam'])
        except ValueError: continue
        if mulai >= other_akhir or other_mulai >= akhir: continue
        if row['kelas_id'] == int(kelas_id):
            raise ValueError('Bentrok: kelas sudah memiliki jadwal di waktu tersebut.')
        if ruangan and row['ruangan'] == ruangan:
            raise ValueError(f'Bentrok: ruangan {ruangan} sudah digunakan pada tanggal dan jam tersebut.')
        if pelaksana == int(row['pengganti_id'] or row['pengajar_id']):
            raise ValueError('Bentrok: pengajar yang bertugas sudah memiliki jadwal lain.')


def tambah_jadwal(hari, jam, kelas_id, pengajar_id, tanggal=None, materi=None, pengganti_id=None, ruangan=None):
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        _cek_bentrok_jadwal_terkunci(conn,hari,jam,kelas_id,pengajar_id,tanggal,pengganti_id,ruangan)
        cursor = conn.execute("""INSERT INTO jadwal
            (hari, jam, kelas_id, pengajar_id, tanggal, materi, pengganti_id, ruangan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (hari, jam, kelas_id, pengajar_id, tanggal, materi, pengganti_id or None, ruangan))
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()


def edit_jadwal(jadwal_id, hari, jam, kelas_id, pengajar_id, tanggal=None, materi=None, pengganti_id=None, ruangan=None):
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        lama = conn.execute('SELECT * FROM jadwal WHERE id=?',(jadwal_id,)).fetchone()
        if not lama: raise ValueError('Jadwal tidak ditemukan.')
        ada_presensi = conn.execute('SELECT 1 FROM presensi WHERE jadwal_id=? LIMIT 1',(jadwal_id,)).fetchone()
        if ada_presensi and (lama['tanggal'] != tanggal or lama['kelas_id'] != int(kelas_id) or lama['jam'] != jam):
            raise ValueError('Jadwal sudah memiliki presensi. Kelas, tanggal, dan jam tidak dapat diubah.')
        _cek_bentrok_jadwal_terkunci(conn,hari,jam,kelas_id,pengajar_id,tanggal,pengganti_id,ruangan,jadwal_id)
        conn.execute("""UPDATE jadwal SET hari=?, jam=?, kelas_id=?, pengajar_id=?, tanggal=?,
                       materi=?, pengganti_id=?, ruangan=? WHERE id=?""",
                     (hari,jam,kelas_id,pengajar_id,tanggal,materi,pengganti_id or None,ruangan,jadwal_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()

def ambil_jadwal_mendatang(sejak):
    conn = get_connection()
    try:
        return conn.execute(
            _SELECT_JADWAL + " WHERE j.tanggal IS NOT NULL AND j.tanggal != '' AND j.tanggal >= ? "
                             "ORDER BY j.tanggal ASC, j.jam ASC", (sejak,)).fetchall()
    finally:
        conn.close()

def ambil_jadwal_pengganti(pengajar_id):
    """Jadwal spesifik yang ditugaskan kepada pengajar sebagai pengganti."""
    conn = get_connection()
    try:
        return conn.execute(_SELECT_JADWAL + ' WHERE j.pengganti_id = ? ORDER BY j.tanggal, j.jam',
                            (pengajar_id,)).fetchall()
    finally:
        conn.close()

def hapus_jadwal(jadwal_id):
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM presensi WHERE jadwal_id=? LIMIT 1',(jadwal_id,)).fetchone():
            raise ValueError('Jadwal sudah memiliki presensi dan tidak dapat dihapus.')
        conn.execute('DELETE FROM jadwal WHERE id=?',(jadwal_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()

def _cek_pengajar_kelas(conn, kelas_id, pengajar_id):
    """Pastikan kelas ada dan pengajar ini guru 1 / guru 2 di kelas tsb."""
    # Aturan hak akses pengajar dicek lagi di lapisan database, jadi walaupun ada route
    # yang lupa mengecek, data tetap tidak bisa masuk ke kelas yang bukan miliknya.
    kelas = conn.execute(
        "SELECT pengajar_id, pengajar_id2 FROM kelas WHERE id = ?",
        (kelas_id,)
    ).fetchone()

    if not kelas:
        raise ValueError("Kelas tidak ditemukan.")

    if pengajar_id not in (kelas["pengajar_id"], kelas["pengajar_id2"]):
        raise ValueError("Pengajar tidak memiliki akses ke kelas ini.")

def tambah_materi(kelas_id, pengajar_id, judul, kategori, file_path):
    """Menyimpan materi baru. Pengajar harus ditugaskan pada kelas tersebut."""
    conn = get_connection()
    try:
        _cek_pengajar_kelas(conn, kelas_id, pengajar_id)

        cursor = conn.execute("""
            INSERT INTO materi
                (kelas_id, pengajar_id, judul, kategori, file_path, tanggal_upload)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (kelas_id, pengajar_id, judul, kategori, file_path, sekarang()))  # + tanggal upload

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def ambil_materi_by_kelas(kelas_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT m.*, u.nama AS nama_pengajar
            FROM materi m
            LEFT JOIN users u ON u.id = m.pengajar_id
            WHERE m.kelas_id = ?
            ORDER BY m.id DESC
        """, (kelas_id,)).fetchall()
    finally:
        conn.close()


def ambil_materi_by_id(materi_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM materi WHERE id = ?",
            (materi_id,)
        ).fetchone()
    finally:
        conn.close()


def edit_materi(materi_id, judul, kategori, file_path=None):
    """Ubah judul/kategori materi. file_path diisi kalau pengajar upload file pengganti."""
    conn = get_connection()
    try:
        # tiap edit mencatat tanggal_edit, dipakai label "(Diedit 03 Oktober)" di feed
        if file_path:
            cursor = conn.execute(
                "UPDATE materi SET judul = ?, kategori = ?, file_path = ?, tanggal_edit = ? WHERE id = ?",
                (judul, kategori, file_path, sekarang(), materi_id))
        else:
            cursor = conn.execute(
                "UPDATE materi SET judul = ?, kategori = ?, tanggal_edit = ? WHERE id = ?",
                (judul, kategori, sekarang(), materi_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def hapus_materi(materi_id):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM materi WHERE id = ?",
            (materi_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def tambah_tugas(kelas_id, pengajar_id, judul, deskripsi, deadline, file_lampiran=None):
    """Menyimpan tugas baru untuk kelas yang diajar pengajar."""
    conn = get_connection()
    try:
        _cek_pengajar_kelas(conn, kelas_id, pengajar_id)

        cursor = conn.execute("""
            INSERT INTO tugas
                (kelas_id, pengajar_id, judul, deskripsi, deadline, tanggal_dibuat, file_lampiran)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (kelas_id, pengajar_id, judul, deskripsi, deadline, sekarang(), file_lampiran))  # DIUBAH: + tanggal dibuat

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def edit_tugas(tugas_id, judul, deskripsi, deadline, file_lampiran=None, hapus_lampiran=False):
    """BARU: ubah tugas yang sudah ada. Tanggal edit dicatat buat label '(Diedit ...)'."""
    conn = get_connection()
    try:
        # Berkas lama tetap dipakai bila pengajar tidak memilih berkas baru.
        # Hapus adalah aksi eksplisit dari pengajar, bukan akibat input kosong.
        lampiran_sql = ', file_lampiran = ?' if file_lampiran or hapus_lampiran else ''
        params = [judul, deskripsi, deadline, sekarang()]
        if lampiran_sql:
            params.append(None if hapus_lampiran and not file_lampiran else file_lampiran)
        params.append(tugas_id)
        cursor = conn.execute(f"""
            UPDATE tugas SET judul = ?, deskripsi = ?, deadline = ?, tanggal_edit = ?{lampiran_sql}
            WHERE id = ?
        """, params)
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def hapus_tugas(tugas_id):
    """BARU: hapus tugas beserta pengumpulan & komentarnya, biar tidak ada data yatim."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM komentar WHERE tugas_id = ?", (tugas_id,))
        conn.execute("DELETE FROM pengumpulan WHERE tugas_id = ?", (tugas_id,))
        cursor = conn.execute("DELETE FROM tugas WHERE id = ?", (tugas_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def ambil_tugas_by_kelas(kelas_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT t.*, u.nama AS nama_pengajar
            FROM tugas t
            LEFT JOIN users u ON u.id = t.pengajar_id
            WHERE t.kelas_id = ?
            ORDER BY t.id DESC
        """, (kelas_id,)).fetchall()
    finally:
        conn.close()


def ambil_tugas_by_id(tugas_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM tugas WHERE id = ?",
            (tugas_id,)
        ).fetchone()
    finally:
        conn.close()


def simpan_pengumpulan(tugas_id, siswa_id, file_jawaban):
    """Simpan pengumpulan baru atau perbarui jawaban siswa."""
    conn = get_connection()
    try:
        tugas = conn.execute(
            "SELECT id, kelas_id FROM tugas WHERE id = ?",
            (tugas_id,)
        ).fetchone()

        siswa = conn.execute(
            "SELECT id, kelas_id, role FROM users WHERE id = ?",
            (siswa_id,)
        ).fetchone()

        if not tugas:
            raise ValueError("Tugas tidak ditemukan.")

        if not siswa or siswa["role"] != "siswa":
            raise ValueError("Akun siswa tidak ditemukan.")

        if not siswa_anggota_kelas(siswa_id, tugas['kelas_id']):
            raise ValueError('Siswa bukan anggota kelas tugas ini.')

        existing = conn.execute("""
            SELECT id,nilai FROM pengumpulan
            WHERE tugas_id = ? AND siswa_id = ?
        """, (tugas_id, siswa_id)).fetchone()

        # pakai waktu lokal, bukan CURRENT_TIMESTAMP yang UTC (beda 8 jam di WITA)
        if existing:
            if existing['nilai'] is not None:
                raise ValueError('Tugas sudah dinilai. Hubungi pengajar untuk revisi jawaban.')
            # Mengganti file sebelum dinilai tidak mencampur berkas lama dan baru.
            conn.execute("""
                UPDATE pengumpulan
                SET file_jawaban = ?,
                    nilai = NULL,
                    waktu_kumpul = ?
                WHERE id = ?
            """, (file_jawaban, sekarang(), existing["id"]))
            pengumpulan_id = existing["id"]
        else:
            cursor = conn.execute("""
                INSERT INTO pengumpulan
                    (tugas_id, siswa_id, file_jawaban, waktu_kumpul)
                VALUES (?, ?, ?, ?)
            """, (tugas_id, siswa_id, file_jawaban, sekarang()))
            pengumpulan_id = cursor.lastrowid

        conn.commit()
        return pengumpulan_id
    finally:
        conn.close()


def hapus_jawaban_belum_dinilai(tugas_id, siswa_id):
    """Tarik kembali pengumpulan sendiri yang belum dinilai; tidak mengubah nilai historis."""
    conn = get_connection()
    try:
        row = conn.execute('SELECT file_jawaban,nilai FROM pengumpulan WHERE tugas_id=? AND siswa_id=?',
                           (tugas_id, siswa_id)).fetchone()
        if not row or not row['file_jawaban']:
            raise ValueError('Belum ada file jawaban yang bisa dihapus.')
        if row['nilai'] is not None:
            raise ValueError('Tugas sudah dinilai. Hubungi pengajar sebelum mengubah jawaban.')
        conn.execute('DELETE FROM pengumpulan WHERE tugas_id=? AND siswa_id=? AND nilai IS NULL',
                     (tugas_id, siswa_id))
        conn.commit()
        return row['file_jawaban']
    finally:
        conn.close()


def ambil_pengumpulan_by_tugas_siswa(tugas_id, siswa_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT *
            FROM pengumpulan
            WHERE tugas_id = ? AND siswa_id = ?
        """, (tugas_id, siswa_id)).fetchone()
    finally:
        conn.close()


def ambil_pengumpulan_by_tugas(tugas_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT p.*, u.nama AS siswa_nama,
                   u.username AS siswa_username
            FROM pengumpulan p
            JOIN users u ON u.id = p.siswa_id
            WHERE p.tugas_id = ?
            ORDER BY u.nama
        """, (tugas_id,)).fetchall()
    finally:
        conn.close()


def ambil_pengumpulan_lengkap(tugas_id, kelas_id):
    """SEMUA siswa kelas tsb + pengumpulannya (kalau ada), buat tabel 'Tugas Siswa'.
    Siswa yang belum mengumpulkan tetap muncul dengan file_jawaban/nilai NULL,
    jadi pengajar langsung kelihatan siapa yang belum setor."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT u.id AS siswa_id, u.nama AS siswa_nama, u.username AS siswa_username,
                   u.foto AS siswa_foto,
                   p.id AS pengumpulan_id, p.file_jawaban, p.nilai, p.waktu_kumpul
            FROM users u
            LEFT JOIN pengumpulan p ON p.siswa_id = u.id AND p.tugas_id = ?
            WHERE u.role = 'siswa' AND u.kelas_id = ?
            ORDER BY u.nama
        """, (tugas_id, kelas_id)).fetchall()
    finally:
        conn.close()


def ambil_pengumpulan_by_id(pengumpulan_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM pengumpulan WHERE id = ?",
            (pengumpulan_id,)
        ).fetchone()
    finally:
        conn.close()


def update_nilai_pengumpulan(pengumpulan_id, nilai):
    """Memperbarui kolom nilai pada tabel pengumpulan."""
    try:
        nilai = float(nilai)
    except (TypeError, ValueError):
        raise ValueError("Nilai harus berupa angka.")

    if not 0 <= nilai <= 100:
        raise ValueError("Nilai harus berada antara 0 sampai 100.")

    conn = get_connection()
    try:
        cursor = conn.execute("""
            UPDATE pengumpulan
            SET nilai = ?
            WHERE id = ?
        """, (nilai, pengumpulan_id))

        conn.commit()

        if cursor.rowcount == 0:
            raise ValueError("Data pengumpulan tidak ditemukan.")

        return True
    finally:
        conn.close()


def tambah_komentar(tugas_id, user_id, isi, siswa_id):
    """komentar sekarang selalu menempel ke satu siswa (percakapan privat),
    jadi siswa_id wajib diisi. Siswa harus anggota kelas tugas tersebut."""
    isi = (isi or "").strip()
    if not isi:
        raise ValueError("Isi komentar tidak boleh kosong.")

    conn = get_connection()
    try:
        tugas = conn.execute(
            "SELECT id, kelas_id FROM tugas WHERE id = ?",
            (tugas_id,)
        ).fetchone()

        pengguna = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        siswa = conn.execute(
            "SELECT id, kelas_id, role FROM users WHERE id = ?",
            (siswa_id,)
        ).fetchone()

        if not tugas:
            raise ValueError("Tugas tidak ditemukan.")

        if not pengguna:
            raise ValueError("Pengguna tidak ditemukan.")

        if not siswa or siswa["role"] != "siswa":
            raise ValueError("Siswa tujuan komentar tidak ditemukan.")

        if not siswa_anggota_kelas(siswa_id, tugas['kelas_id']):
            raise ValueError('Siswa bukan anggota kelas tugas ini.')

        cursor = conn.execute("""
            INSERT INTO komentar (tugas_id, user_id, siswa_id, isi_komentar, waktu)
            VALUES (?, ?, ?, ?, ?)
        """, (tugas_id, user_id, siswa_id, isi, sekarang()))

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def ambil_komentar_tugas(tugas_id, siswa_id):
    """cuma percakapan milik siswa tsb yang keluar, bukan komentar sekelas."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT k.*, u.nama AS user_nama, u.role AS user_role, u.foto AS user_foto
            FROM komentar k
            JOIN users u ON u.id = k.user_id
            WHERE k.tugas_id = ? AND k.siswa_id = ?
            ORDER BY k.id ASC
        """, (tugas_id, siswa_id)).fetchall()
    finally:
        conn.close()


def hitung_komentar_tugas(tugas_id):
    """{siswa_id: jumlah komentar}, buat kolom 'Komentar (n)' di tabel pengumpulan."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT siswa_id, COUNT(*) AS jumlah FROM komentar
            WHERE tugas_id = ? AND siswa_id IS NOT NULL
            GROUP BY siswa_id
        """, (tugas_id,)).fetchall()
        return {r["siswa_id"]: r["jumlah"] for r in rows}
    finally:
        conn.close()


# --- PRESENSI FUNCTIONS ---
def ambil_presensi_by_id(presensi_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM presensi WHERE id = ?', (presensi_id,)).fetchone()
    conn.close()
    return row

def ambil_presensi_kelas_tanggal(kelas_id, tanggal, jadwal_id=None):
    conn = get_connection()
    try:
        if jadwal_id is None:
            return conn.execute('SELECT * FROM presensi WHERE kelas_id=? AND tanggal=?', (kelas_id,tanggal)).fetchall()
        return conn.execute('SELECT * FROM presensi WHERE kelas_id=? AND tanggal=? AND jadwal_id=?',
                            (kelas_id,tanggal,jadwal_id)).fetchall()
    finally:
        conn.close()

def ambil_presensi_siswa(siswa_id):
    conn = get_connection()
    rows = conn.execute('SELECT * FROM presensi WHERE siswa_id = ? ORDER BY tanggal DESC',
                        (siswa_id,)).fetchall()
    conn.close()
    return rows

def ambil_tanggal_jadwal_kelas(kelas_id):
    """Daftar tanggal (string YYYY-MM-DD) pertemuan kelas menurut tabel jadwal."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT DISTINCT tanggal FROM jadwal
        WHERE kelas_id = ? AND tanggal IS NOT NULL AND tanggal != ''
    ''', (kelas_id,)).fetchall()
    conn.close()
    return [r['tanggal'] for r in rows]

def ambil_jadwal_terpresensi(jadwal_ids):
    """Per jadwal.id, bukan per kelas/tanggal (termasuk dua sesi sehari)."""
    ids = list(dict.fromkeys(int(j) for j in jadwal_ids))
    if not ids: return set()
    conn = get_connection()
    try:
        selesai = set()
        for offset in range(0,len(ids),800):
            potongan=ids[offset:offset+800]
            mark=','.join('?' for _ in potongan)
            rows=conn.execute(f"""SELECT DISTINCT p.jadwal_id FROM presensi p
                WHERE p.jadwal_id IN ({mark}) AND LOWER(TRIM(p.status))
                IN ('hadir','izin','sakit','alfa','alpha','alpa')""",potongan).fetchall()
            selesai.update(r[0] for r in rows)
        return selesai
    finally: conn.close()

def ambil_tanggal_presensi_kelas(kelas_id):
    conn = get_connection()
    rows = conn.execute('SELECT DISTINCT tanggal FROM presensi WHERE kelas_id = ?', (kelas_id,)).fetchall()
    conn.close()
    return [r['tanggal'] for r in rows]

def _tentukan_jadwal_presensi(conn, kelas_id, tanggal, jadwal_id=None):
    if jadwal_id is None:
        rows=conn.execute('SELECT id FROM jadwal WHERE kelas_id=? AND tanggal=? ORDER BY jam,id',
                          (kelas_id,tanggal)).fetchall()
        if len(rows)!=1:
            raise ValueError('Pilih pertemuan/jam secara spesifik untuk mencatat presensi.')
        jadwal_id=rows[0]['id']
    try: jadwal_id=int(jadwal_id)
    except (TypeError, ValueError): raise ValueError('ID pertemuan tidak valid.')
    row=conn.execute('SELECT id FROM jadwal WHERE id=? AND kelas_id=? AND tanggal=?',
                     (jadwal_id,kelas_id,tanggal)).fetchone()
    if not row: raise ValueError('Pertemuan tidak sesuai kelas dan tanggal.')
    return jadwal_id

def _simpan_presensi(conn, tanggal, siswa_id, kelas_id, status, pengajar_id=None, jadwal_id=None):
    jadwal_id=_tentukan_jadwal_presensi(conn,kelas_id,tanggal,jadwal_id)
    row=conn.execute('SELECT id FROM presensi WHERE jadwal_id=? AND siswa_id=?',
                     (jadwal_id,siswa_id)).fetchone()
    if row:
        conn.execute('UPDATE presensi SET status=?,pengajar_id=?,tanggal=?,kelas_id=? WHERE id=?',
                     (status,pengajar_id,tanggal,kelas_id,row['id']))
        return row['id']
    cur=conn.execute('INSERT INTO presensi(tanggal,siswa_id,kelas_id,status,pengajar_id,jadwal_id) VALUES(?,?,?,?,?,?)',
                     (tanggal,siswa_id,kelas_id,status,pengajar_id,jadwal_id))
    return cur.lastrowid

def simpan_presensi(tanggal, siswa_id, kelas_id, status, pengajar_id=None, jadwal_id=None):
    conn=get_connection()
    try:
        presensi_id=_simpan_presensi(conn,tanggal,siswa_id,kelas_id,status,pengajar_id,jadwal_id)
        conn.commit()
        return presensi_id
    finally: conn.close()

def simpan_presensi_massal(kelas_id, tanggal, data_status, pengajar_id=None, jadwal_id=None):
    conn=get_connection()
    try:
        jadwal_id=_tentukan_jadwal_presensi(conn,kelas_id,tanggal,jadwal_id)
        for siswa_id,status in data_status.items():
            _simpan_presensi(conn,tanggal,siswa_id,kelas_id,status,pengajar_id,jadwal_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()

def hapus_presensi(kelas_id, tanggal, siswa_id, jadwal_id=None):
    conn=get_connection()
    try:
        jadwal_id=_tentukan_jadwal_presensi(conn,kelas_id,tanggal,jadwal_id)
        cursor=conn.execute('DELETE FROM presensi WHERE jadwal_id=? AND kelas_id=? AND tanggal=? AND siswa_id=?',
                            (jadwal_id,kelas_id,tanggal,siswa_id))
        conn.commit()
        return cursor.rowcount
    finally: conn.close()

def hapus_presensi_pertemuan(kelas_id, tanggal, jadwal_id=None):
    """Menghapus (membatalkan) seluruh data presensi siswa pada satu jadwal pertemuan."""
    conn = get_connection()
    try:
        jadwal_id = _tentukan_jadwal_presensi(conn, kelas_id, tanggal, jadwal_id)
        cursor = conn.execute('DELETE FROM presensi WHERE jadwal_id=? AND kelas_id=? AND tanggal=?',
                              (jadwal_id, kelas_id, tanggal))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def update_status_presensi(presensi_id, status):
    conn = get_connection()
    conn.execute('UPDATE presensi SET status = ? WHERE id = ?', (status, presensi_id))
    conn.commit()
    conn.close()

def rekap_presensi_siswa(siswa_id, kelas_id=None):
    conn = get_connection()
    rows = conn.execute('SELECT status, COUNT(*) AS jumlah FROM presensi WHERE siswa_id = ? AND (? IS NULL OR kelas_id = ?) GROUP BY status',
                        (siswa_id, kelas_id, kelas_id)).fetchall()
    conn.close()
    return rows

def rekap_presensi_kelas(kelas_id):
    conn = get_connection()
    rows = conn.execute('''
        SELECT siswa_id, status, COUNT(*) AS jumlah FROM presensi
        WHERE kelas_id = ? GROUP BY siswa_id, status
    ''', (kelas_id,)).fetchall()
    conn.close()
    return rows


# Penilaian tugas, Rekap nilai, dan Catatan akhir Pengajar
# Nilai disimpan di pengumpulan.nilai (satu-satunya sumber nilai).

def beri_nilai(tugas_id, siswa_id, pengajar_id, nilai, komentar=None):
    """Memberi / memperbarui nilai pengumpulan siswa pada sebuah tugas.
    komentar nggak dipakai lagi: masukan ke siswa lewat tabel komentar (Komentar Tugas)."""
    try:
        nilai = float(nilai)
    except (TypeError, ValueError):
        raise ValueError("Nilai harus berupa angka.")

    if not 0 <= nilai <= 100:
        raise ValueError("Nilai harus berada antara 0 sampai 100.")

    conn = get_connection()
    try:
        tugas = conn.execute(
            'SELECT id, kelas_id FROM tugas WHERE id = ?',
            (tugas_id,)
        ).fetchone()
        if not tugas:
            raise ValueError("Tugas tidak ditemukan.")

        # guru 1 maupun guru 2 kelas tsb boleh menilai, nggak cuma yang bikin tugas
        _cek_pengajar_kelas(conn, tugas['kelas_id'], pengajar_id)

        pengumpulan = conn.execute(
            'SELECT id FROM pengumpulan WHERE tugas_id = ? AND siswa_id = ?',
            (tugas_id, siswa_id)
        ).fetchone()
        if not pengumpulan:
            raise ValueError("Siswa ini belum mengumpulkan tugas, jadi belum bisa dinilai.")

        conn.execute('UPDATE pengumpulan SET nilai = ? WHERE id = ?', (nilai, pengumpulan['id']))
        conn.commit()
        return pengumpulan['id']
    finally:
        conn.close()

def hapus_nilai_pengumpulan(pengumpulan_id):
    """Menghapus (mengosongkan) nilai pengumpulan siswa. Nilai jadi NULL,
    berkas jawaban tetap ada — pengajar tinggal menilai ulang nanti."""
    conn = get_connection()
    try:
        row = conn.execute('SELECT id, nilai FROM pengumpulan WHERE id = ?',
                           (pengumpulan_id,)).fetchone()
        if not row:
            raise ValueError("Data pengumpulan tidak ditemukan.")
        if row['nilai'] is None:
            raise ValueError("Pengumpulan ini belum memiliki nilai.")
        conn.execute('UPDATE pengumpulan SET nilai = NULL WHERE id = ?',
                     (pengumpulan_id,))
        conn.commit()
        return True
    finally:
        conn.close()

def ambil_penilaian_by_id(penilaian_id):
    """penilaian_id = id pengumpulan yang sudah dinilai."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT p.*, u.nama AS nama_siswa,
                   t.judul AS judul_tugas,
                   g.nama AS nama_pengajar
            FROM pengumpulan p
            JOIN users u ON u.id = p.siswa_id
            JOIN tugas t ON t.id = p.tugas_id
            JOIN users g ON g.id = t.pengajar_id
            WHERE p.id = ? AND p.nilai IS NOT NULL
        """, (penilaian_id,)).fetchone()
    finally:
        conn.close()

def ambil_penilaian_by_siswa(siswa_id):
    """Semua nilai milik seorang siswa (yang sudah dinilai saja)."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT p.*, t.judul AS judul_tugas,
                   g.nama AS nama_pengajar
            FROM pengumpulan p
            JOIN tugas t ON t.id = p.tugas_id
            JOIN users g ON g.id = t.pengajar_id
            WHERE p.siswa_id = ? AND p.nilai IS NOT NULL
            ORDER BY p.waktu_kumpul DESC
        """, (siswa_id,)).fetchall()
    finally:
        conn.close()

def ambil_penilaian_by_tugas(tugas_id):
    """Nilai seluruh siswa pada sebuah tugas (yang sudah dinilai saja)."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT p.*, u.nama AS nama_siswa,
                   u.username AS username_siswa
            FROM pengumpulan p
            JOIN users u ON u.id = p.siswa_id
            WHERE p.tugas_id = ? AND p.nilai IS NOT NULL
            ORDER BY u.nama
        """, (tugas_id,)).fetchall()
    finally:
        conn.close()

def ambil_daftar_nilai_siswa(siswa_id, kelas_id=None):
    """Semua tugas di kelas siswa + nilainya. Tugas yang belum dikumpul/dinilai nilainya None."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT t.id AS tugas_id, t.judul AS judul_tugas, t.deadline,
                   p.file_jawaban, p.nilai, p.waktu_kumpul
            FROM users u
            JOIN tugas t ON t.kelas_id = COALESCE(?, u.kelas_id)
            LEFT JOIN pengumpulan p ON p.tugas_id = t.id AND p.siswa_id = u.id
            WHERE u.id = ?
            ORDER BY t.id DESC
        """, (kelas_id, siswa_id)).fetchall()
    finally:
        conn.close()

def rekap_nilai_siswa(siswa_id, kelas_id=None):
    """Menghitung jumlah nilai, rata-rata, tertinggi, dan terendah."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT
                COUNT(nilai) AS jumlah_tugas_dinilai,
                ROUND(AVG(nilai), 2) AS rata_rata,
                MAX(nilai) AS nilai_tertinggi,
                MIN(nilai) AS nilai_terendah
            FROM pengumpulan p JOIN tugas t ON t.id = p.tugas_id
            WHERE p.siswa_id = ? AND (? IS NULL OR t.kelas_id = ?)
        """, (siswa_id, kelas_id, kelas_id)).fetchone()
    finally:
        conn.close()

def rekap_nilai_kelas(kelas_id):
    """Rekap nilai setiap siswa dalam suatu kelas."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT
                u.id AS siswa_id,
                u.nama AS nama_siswa,
                COUNT(p.nilai) AS jumlah_tugas_dinilai,
                ROUND(AVG(p.nilai), 2) AS rata_rata,
                MAX(p.nilai) AS nilai_tertinggi,
                MIN(p.nilai) AS nilai_terendah
            FROM users u
            LEFT JOIN pengumpulan p ON p.siswa_id = u.id
            WHERE u.role = 'siswa' AND u.kelas_id = ?
            GROUP BY u.id, u.nama
            ORDER BY u.nama
        """, (kelas_id,)).fetchall()
    finally:
        conn.close()

def ambil_monitoring_semua_siswa():
    """Satu baris per siswa buat Monitoring admin: kelas, rata-rata nilai, rekap presensi, jumlah catatan akhir."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT u.id AS siswa_id, u.nama AS nama_siswa, u.foto AS foto_siswa,
                   k.id AS kelas_id, k.nama AS nama_kelas,
                   (SELECT ROUND(AVG(p.nilai), 2) FROM pengumpulan p JOIN tugas t ON t.id=p.tugas_id WHERE p.siswa_id=u.id AND t.kelas_id=u.kelas_id) AS rata_rata,
                   (SELECT COUNT(*) FROM presensi WHERE siswa_id = u.id AND kelas_id=u.kelas_id AND LOWER(status) = 'hadir') AS hadir,
                   (SELECT COUNT(*) FROM presensi WHERE siswa_id = u.id AND kelas_id=u.kelas_id AND LOWER(status) = 'izin') AS izin,
                   (SELECT COUNT(*) FROM presensi WHERE siswa_id = u.id AND kelas_id=u.kelas_id AND LOWER(status) = 'sakit') AS sakit,
                   (SELECT COUNT(*) FROM presensi WHERE siswa_id = u.id AND kelas_id=u.kelas_id
                        AND LOWER(status) IN ('alfa', 'alpha')) AS alfa,
                   (SELECT COUNT(*) FROM catatan_akhir WHERE siswa_id = u.id AND kelas_id=u.kelas_id) AS jumlah_catatan
            FROM users u
            LEFT JOIN kelas k ON k.id = u.kelas_id
            WHERE u.role = 'siswa'
            ORDER BY k.nama, u.nama
        """).fetchall()
    finally:
        conn.close()

def tambah_catatan_akhir(siswa_id, kelas_id, pengajar_id, catatan, lulus=0):
    """Satu siswa satu catatan akhir per kelas. Sudah ada = diedit (guru 1 & guru 2 sama-sama bisa edit).
    DIUBAH: + lulus, penanda siswa sudah menamatkan kelas ini."""
    catatan = (catatan or "").strip()
    if not catatan:
        raise ValueError("Catatan akhir tidak boleh kosong.")

    conn = get_connection()
    try:
        kelas = conn.execute("""
            SELECT pengajar_id, pengajar_id2
            FROM kelas WHERE id = ?
        """, (kelas_id,)).fetchone()

        siswa = conn.execute("""
            SELECT id, kelas_id, role
            FROM users WHERE id = ?
        """, (siswa_id,)).fetchone()

        if not kelas:
            raise ValueError("Kelas tidak ditemukan.")
        if pengajar_id not in (
            kelas["pengajar_id"], kelas["pengajar_id2"]
        ):
            raise ValueError("Kamu bukan pengajar di kelas ini.")
        if not siswa or siswa["role"] != "siswa":
            raise ValueError("Siswa tidak ditemukan.")
        if siswa["kelas_id"] != kelas_id:
            raise ValueError("Siswa bukan anggota kelas ini.")

        catatan_lama = conn.execute("""
            SELECT id FROM catatan_akhir
            WHERE siswa_id = ? AND kelas_id = ?
        """, (siswa_id, kelas_id)).fetchone()

        if catatan_lama:
            conn.execute("""
                UPDATE catatan_akhir
                SET catatan = ?, pengajar_id = ?, tanggal_dibuat = ?, lulus = ?
                WHERE id = ?
            """, (catatan, pengajar_id, sekarang(), 1 if lulus else 0, catatan_lama["id"]))
            hasil = catatan_lama["id"]
        else:
            cursor = conn.execute("""
                INSERT INTO catatan_akhir
                    (siswa_id, kelas_id, pengajar_id, catatan, tanggal_dibuat, lulus)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (siswa_id, kelas_id, pengajar_id, catatan, sekarang(), 1 if lulus else 0))
            hasil = cursor.lastrowid

        conn.commit()
        return hasil
    finally:
        conn.close()

def ambil_riwayat_kelas_siswa(siswa_id):
    """Kelas aktif dan kelas lampau; hasil dibatasi ke pemilik akun."""
    conn = get_connection()
    try:
        return conn.execute("""
          SELECT DISTINCT k.id, k.nama AS nama_kelas,
                 CASE WHEN u.kelas_id=k.id THEN 0 ELSE 1 END AS selesai
          FROM riwayat_kelas r JOIN kelas k ON k.id=r.kelas_id
          JOIN users u ON u.id=r.siswa_id
          WHERE r.siswa_id=?
          ORDER BY selesai, k.nama
        """, (siswa_id,)).fetchall()
    finally:
        conn.close()


def siswa_anggota_kelas(siswa_id, kelas_id):
    conn = get_connection()
    try:
        return conn.execute('SELECT 1 FROM riwayat_kelas WHERE siswa_id=? AND kelas_id=? LIMIT 1',
                            (siswa_id, kelas_id)).fetchone() is not None
    finally:
        conn.close()


def kelas_lulus(siswa_id, kelas_id):
    conn = get_connection()
    try:
        return conn.execute('SELECT 1 FROM catatan_akhir WHERE siswa_id=? AND kelas_id=? AND lulus=1',
                            (siswa_id, kelas_id)).fetchone() is not None
    finally:
        conn.close()


def ambil_kelas_lulus_siswa(siswa_id):
    """BARU: kelas-kelas yang sudah DITAMATKAN siswa (ditandai lulus oleh pengajar).
    Dipakai buat menampilkan kelas lama bertanda 'Selesai' dan jadwalnya yang masih bisa dilihat."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT k.*, k.nama AS nama_kelas, c.tanggal_dibuat AS tanggal_lulus
            FROM catatan_akhir c JOIN kelas k ON k.id = c.kelas_id
            WHERE c.siswa_id = ? AND c.lulus = 1
            ORDER BY c.tanggal_dibuat DESC
        """, (siswa_id,)).fetchall()
    finally:
        conn.close()
    return rows


def ambil_catatan_akhir_by_siswa(siswa_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT c.*, u.nama AS nama_pengajar,
                   k.nama AS nama_kelas
            FROM catatan_akhir c
            JOIN users u ON u.id = c.pengajar_id
            JOIN kelas k ON k.id = c.kelas_id
            WHERE c.siswa_id = ?
            ORDER BY c.tanggal_dibuat DESC
        """, (siswa_id,)).fetchall()
    finally:
        conn.close()

def ambil_catatan_akhir_by_id(catatan_id):
    """satu baris catatan akhir. Dipakai sebelum menghapus, buat tahu catatan ini
    milik kelas & siswa yang mana (hak aksesnya dicek dari situ)."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM catatan_akhir WHERE id = ?", (catatan_id,)
        ).fetchone()
    finally:
        conn.close()

def hapus_catatan_akhir(catatan_id, pengajar_id):
    """Guru 1 / guru 2 kelas tsb boleh menghapus catatan akhir di kelasnya."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            DELETE FROM catatan_akhir
            WHERE id = ? AND kelas_id IN (
                SELECT id FROM kelas WHERE pengajar_id = ? OR pengajar_id2 = ?
            )
        """, (catatan_id, pengajar_id, pengajar_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()# --- DASHBOARD BERDASARKAN DATA NYATA ---
def data_dashboard_admin(tahun):
    conn = get_connection()
    try:
        tahun = int(tahun)
        def rekap(y):
            periode = str(y)
            # Hitung KEIKUTSERTAAN berdasarkan riwayat pendaftaran siswa ke kelas (riwayat_kelas),
            # bukan berdasarkan jumlah akun pada Kelola Akun. Satu akun siswa yang terdaftar
            # di beberapa kelas pada tahun tersebut dihitung sesuai jumlah riwayat pendaftarannya.
            siswa_sql = """SELECT COUNT(*) FROM riwayat_kelas r
                JOIN users u ON u.id=r.siswa_id AND u.role='siswa'
                WHERE substr(r.tanggal_mulai,1,4)=?
                   OR (
                       substr(r.tanggal_mulai,1,4) < ?
                       AND (r.tanggal_selesai IS NULL OR substr(r.tanggal_selesai,1,4) >= ?)
                       AND EXISTS (
                           SELECT 1 FROM jadwal j
                           WHERE j.kelas_id=r.kelas_id AND substr(j.tanggal,1,4)=?
                             AND date(r.tanggal_mulai) <= date(j.tanggal)
                             AND (r.tanggal_selesai IS NULL
                                  OR date(r.tanggal_selesai) >= date(j.tanggal))
                       )
                   )"""
            q = lambda sql: conn.execute(sql, (periode,)).fetchone()[0]
            siswa_jml = conn.execute(siswa_sql, (periode, periode, periode, periode)).fetchone()[0]
            return dict(siswa=siswa_jml, pengajar=conn.execute("""SELECT COUNT(DISTINCT id) FROM (
                   SELECT k.pengajar_id AS id FROM kelas k JOIN jadwal j ON j.kelas_id=k.id
                        WHERE substr(j.tanggal,1,4)=?
                   UNION SELECT k.pengajar_id2 FROM kelas k JOIN jadwal j ON j.kelas_id=k.id
                        WHERE substr(j.tanggal,1,4)=? AND k.pengajar_id2 IS NOT NULL
                   )""",(periode,periode)).fetchone()[0],
                kelas=q('SELECT COUNT(DISTINCT kelas_id) FROM jadwal WHERE substr(tanggal,1,4)=?'),
                materi=q('SELECT COUNT(*) FROM materi WHERE substr(tanggal_upload,1,4)=?'),
                tugas=q('SELECT COUNT(*) FROM tugas WHERE substr(tanggal_dibuat,1,4)=?'),
                pertemuan=q('SELECT COUNT(*) FROM jadwal WHERE substr(tanggal,1,4)=?'))
        # Opsi hanya tahun dengan data yang benar-benar ada (termasuk tahun riwayat pendaftaran kelas).
        tahun_opsi = [int(r[0]) for r in conn.execute("""
            SELECT tahun FROM (
                SELECT substr(tanggal_mulai,1,4) AS tahun FROM riwayat_kelas
                UNION ALL SELECT substr(tanggal,1,4) AS tahun FROM jadwal
                UNION ALL SELECT substr(tanggal_upload,1,4) FROM materi
                UNION ALL SELECT substr(tanggal_dibuat,1,4) FROM tugas
            ) WHERE tahun GLOB '[0-9][0-9][0-9][0-9]'
              AND CAST(tahun AS INTEGER) BETWEEN 2000 AND 2100
            GROUP BY tahun ORDER BY tahun DESC
        """)]
        # Link tahun yang tak tersedia tidak boleh menghasilkan dashboard kosong.
        if tahun_opsi and tahun not in tahun_opsi:
            tahun = tahun_opsi[0]
        bulanan = []
        for month in range(1,13):
            ym = f'{tahun}-{month:02d}'
            q = conn.execute('''SELECT COUNT(*)
                FROM riwayat_kelas r
                JOIN users u ON u.id=r.siswa_id AND u.role='siswa'
                WHERE substr(r.tanggal_mulai,1,7)=?
                   OR EXISTS (
                       SELECT 1 FROM jadwal j
                       WHERE j.kelas_id=r.kelas_id AND substr(j.tanggal,1,7)=?
                         AND date(r.tanggal_mulai)<=date(j.tanggal)
                         AND (r.tanggal_selesai IS NULL
                              OR date(r.tanggal_selesai)>=date(j.tanggal))
                   )''',
                (ym, ym)).fetchone()[0]
            bulanan.append(q)
        rekap3 = [(y, rekap(y)) for y in tahun_opsi if y <= tahun][:3]
        # Progress adalah jumlah tanggal pertemuan yang sudah dipresensi,
        # maksimal 8; lewatnya tanggal jadwal bukan bukti pertemuan terlaksana.
        progress = [dict(r) for r in conn.execute('''SELECT k.id,k.nama,
             ? AS total,
             MIN(?, (SELECT COUNT(DISTINCT p.jadwal_id) FROM presensi p
                  JOIN jadwal jp ON jp.id=p.jadwal_id
                  WHERE p.kelas_id=k.id AND substr(jp.tanggal,1,4)=?
                    AND LOWER(TRIM(p.status))
                    IN ('hadir','izin','sakit','alfa','alpha','alpa'))) AS selesai
             FROM kelas k
             WHERE EXISTS (SELECT 1 FROM jadwal j WHERE j.kelas_id=k.id
                           AND substr(j.tanggal,1,4)=?)
             ORDER BY k.nama''', (TOTAL_PERTEMUAN_KELAS,TOTAL_PERTEMUAN_KELAS,str(tahun),str(tahun)))]
        aktivitas = [dict(r) for r in conn.execute('''SELECT tipe, judul, waktu, kelas_id FROM (
          SELECT 'materi' tipe, 'Materi: '||judul judul, tanggal_upload waktu, kelas_id FROM materi
          UNION ALL SELECT 'tugas', 'Tugas: '||judul, tanggal_dibuat, kelas_id FROM tugas
          UNION ALL SELECT 'jadwal', 'Pertemuan: '||COALESCE(materi, 'Kelas'), tanggal, kelas_id FROM jadwal
          UNION ALL SELECT 'nilai', 'Pengumpulan tugas', waktu_kumpul, t.kelas_id FROM pengumpulan p JOIN tugas t ON t.id=p.tugas_id
        ) WHERE waktu IS NOT NULL AND substr(waktu,1,4)=? ORDER BY waktu DESC LIMIT 5''',(str(tahun),))]
        rekap_tahunan = rekap(tahun)
        stats = dict(rekap_tahunan)
        # Berbeda dari pengajar TERJADWAL di rekap tahunan, kartu utama harus
        # mencerminkan jumlah akun pengajar pada menu Kelola Akun.
        stats['pengajar'] = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='pengajar'"
        ).fetchone()[0]
        # Setiap irisan diagram benar-benar mewakili kategori tersendiri.
        # Nilai nol tetap dicatat untuk legenda, tetapi tanpa lebar irisan.
        warna = (
            ('siswa', '#5297fa'), ('pengajar', '#ffd260'),
            ('kelas', '#50d5b1'), ('materi', '#86c7f8'),
            ('tugas', '#c276f1'), ('pertemuan', '#387af0'),
        )
        total_rekap = sum(rekap_tahunan[k] for k, _ in warna)
        posisi = 0.0
        irisan = []
        warna_diagram = []
        for k, color in warna:
            jumlah = rekap_tahunan[k]
            persen = 100.0 * jumlah / total_rekap if total_rekap else 0.0
            irisan.append(dict(kategori=k, jumlah=jumlah, warna=color, persen=persen))
            if persen:
                warna_diagram.append(f'{color} {posisi:.5f}% {posisi+persen:.5f}%')
                posisi += persen
        gradien = 'conic-gradient(' + ', '.join(warna_diagram) + ')' if warna_diagram else '#e6eef9'
        return dict(tahun=tahun, tahun_opsi=tahun_opsi, stat=stats, rekap_tahunan=rekap_tahunan, bulanan=bulanan,
                    rekap=rekap3, progress=progress, aktivitas=aktivitas,
                    diagram_rekap=dict(total=total_rekap, irisan=irisan, gradien=gradien))
    finally:
        conn.close()


def data_dashboard_pengajar(pengajar_id, kelas_id=None, panel=None):
    kelas_list = ambil_kelas_by_pengajar(pengajar_id)
    boleh = {k['id'] for k in kelas_list}
    if kelas_id is not None and kelas_id not in boleh:
        raise ValueError('Kelas bukan tanggung jawab pengajar.')
    ids = [kelas_id] if kelas_id is not None else list(boleh)
    if not ids:
        return dict(kelas_list=kelas_list, kelas_id=kelas_id, stat=dict(kelas=0,siswa=0,rata=None,sisa=0,
              dinilai=0,belum=0,materi=0), minggu=[], aktivitas=[], progress=[], daftar=[])
    mark = ','.join('?' for _ in ids)
    conn = get_connection()
    try:
        def satu(sql, params=()):return conn.execute(sql, tuple(params)).fetchone()[0]
        siswa = satu(f'''SELECT COUNT(*) FROM riwayat_kelas r
            JOIN users u ON u.id=r.siswa_id AND u.role="siswa"
            WHERE r.kelas_id IN ({mark})''',ids)
        # Sisa pertemuan dihitung di bawah dari progres presensi tiap kelas;
        # jadwal yang hanya lewat tanggalnya belum dianggap terlaksana.
        row = conn.execute(f'''SELECT COUNT(CASE WHEN p.nilai IS NOT NULL THEN 1 END) dinilai,
              COUNT(CASE WHEN p.nilai IS NULL THEN 1 END) belum, AVG(p.nilai) rata
              FROM pengumpulan p JOIN tugas t ON t.id=p.tugas_id
              WHERE t.kelas_id IN ({mark})''',ids).fetchone()
        materi = satu(f'SELECT COUNT(*) FROM materi WHERE pengajar_id=? AND kelas_id IN ({mark})',[pengajar_id,*ids])
        # Pengukuran mingguan mengikuti tanggal pengumpulan karena kolom tanggal penilaian belum tersedia.
        minggu = [dict(r) for r in conn.execute(f'''SELECT strftime('%Y-W%W', p.waktu_kumpul) label,
             ROUND(AVG(p.nilai),2) nilai FROM pengumpulan p JOIN tugas t ON t.id=p.tugas_id
             WHERE t.kelas_id IN ({mark}) AND p.nilai IS NOT NULL
             GROUP BY strftime('%Y-W%W', p.waktu_kumpul) ORDER BY label DESC LIMIT 8''',ids)][::-1]
        aktivitas = [dict(r) for r in conn.execute(f'''SELECT tipe,judul,waktu,kelas_id FROM (
          SELECT 'materi' tipe,'Materi: '||judul judul,tanggal_upload waktu,kelas_id,pengajar_id FROM materi
          UNION ALL SELECT 'tugas','Tugas: '||judul,tanggal_dibuat,kelas_id,pengajar_id FROM tugas
          UNION ALL SELECT 'jadwal','Pertemuan: '||COALESCE(materi,'Kelas'),tanggal,kelas_id,pengajar_id FROM jadwal
        ) WHERE kelas_id IN ({mark}) AND pengajar_id=? AND waktu IS NOT NULL ORDER BY waktu DESC LIMIT 5''',[*ids,pengajar_id])]
        progress = [dict(r) for r in conn.execute(f'''SELECT k.id,k.nama,
          ? AS total,
          MIN(?, (SELECT COUNT(DISTINCT p.jadwal_id) FROM presensi p
             WHERE p.kelas_id=k.id AND LOWER(TRIM(p.status))
               IN ('hadir','izin','sakit','alfa','alpha','alpa'))) AS selesai
          FROM kelas k WHERE k.id IN ({mark}) ORDER BY k.nama''',
          [TOTAL_PERTEMUAN_KELAS,TOTAL_PERTEMUAN_KELAS,*ids])]
        sisa = sum(k['total'] - k['selesai'] for k in progress)
        daftar=[]
        if panel=='siswa':
            daftar=[dict(r) for r in conn.execute(f'SELECT u.id,u.nama,k.nama kelas_nama,k.id kelas_id FROM users u JOIN kelas k ON k.id=u.kelas_id WHERE k.id IN ({mark}) AND u.role="siswa" ORDER BY k.nama,u.nama',ids)]
        if panel in ('dinilai','belum'):
            daftar=[dict(r) for r in conn.execute(f'''SELECT p.id,p.nilai,u.nama,t.judul,k.nama kelas_nama,t.id tugas_id
                FROM pengumpulan p JOIN tugas t ON t.id=p.tugas_id
                JOIN users u ON u.id=p.siswa_id JOIN kelas k ON k.id=t.kelas_id
                WHERE t.kelas_id IN ({mark}) AND p.nilai IS {'NOT ' if panel=='dinilai' else ''}NULL
                ORDER BY p.waktu_kumpul DESC''',ids)]
        if panel=='materi':
            daftar=[dict(r) for r in conn.execute(f'''SELECT m.id,m.judul,k.nama kelas_nama,m.kelas_id
                FROM materi m JOIN kelas k ON k.id=m.kelas_id WHERE m.kelas_id IN ({mark})
                AND m.pengajar_id=? ORDER BY m.tanggal_upload DESC''',[*ids,pengajar_id])]
        return dict(kelas_list=kelas_list,kelas_id=kelas_id,stat=dict(kelas=len(ids),siswa=siswa,
            rata=round(row['rata'],2) if row['rata'] is not None else None,sisa=sisa,
            dinilai=row['dinilai'],belum=row['belum'],materi=materi),
            minggu=minggu,aktivitas=aktivitas,progress=progress,daftar=daftar)
    finally:
        conn.close()


def grafik_presensi_siswa(siswa_id, kelas_id):
    """Kumulatif hanya jadwal lampau yang benar-benar memiliki catatan presensi."""
    conn = get_connection()
    try:
        rows=conn.execute('''SELECT j.id, j.tanggal, LOWER(p.status) status
            FROM jadwal j LEFT JOIN presensi p ON p.jadwal_id=j.id AND p.siswa_id=?
            WHERE j.kelas_id=? AND j.tanggal<date('now','localtime') ORDER BY j.tanggal,j.jam,j.id''',
            (siswa_id,kelas_id)).fetchall()
        nilai={'hadir':1,'izin':.5,'sakit':.5,'alfa':0,'alpha':0}
        total=0; hasil=[]
        for r in rows:
            if r['status'] not in nilai:continue
            total+=nilai[r['status']]
            score=round(total/(len(hasil)+1)*100,2)
            prev=hasil[-1]['nilai'] if hasil else None
            delta=None if prev is None else round(score-prev,2)
            hasil.append(dict(label=len(hasil)+1, tanggal=r['tanggal'],nilai=score,
                              delta=delta,arah='tetap' if delta is not None and abs(delta)<.1
                              else ('naik' if delta is not None and delta>0 else 'turun' if delta is not None else None)))
        return hasil
    finally:
        conn.close()


def data_dashboard_siswa(siswa_id,kelas_id,panel=None):
    if kelas_id is None:
        return dict(stat={}, presensi=[], aktivitas=[], kelas=None, daftar=[])
    if not siswa_anggota_kelas(siswa_id, kelas_id):
        raise ValueError('Kelas bukan milik siswa.')
    conn=get_connection()
    try:
        q=lambda sql,params=():conn.execute(sql,tuple(params)).fetchone()[0]
        total=TOTAL_PERTEMUAN_KELAS
        # Satu hari presensi tercatat = satu pertemuan terlaksana untuk kelas,
        # tanpa menghitung jumlah siswa dan tanpa melihat tanggal sudah lewat.
        terlaksana=min(total,q("""SELECT COUNT(DISTINCT jadwal_id) FROM presensi
            WHERE kelas_id=? AND LOWER(TRIM(status))
              IN ('hadir','izin','sakit','alfa','alpha','alpa')""",(kelas_id,)))
        sisa=total-terlaksana
        tugas=q('SELECT COUNT(*) FROM tugas WHERE kelas_id=?',(kelas_id,))
        dikerjakan=q('''SELECT COUNT(*) FROM pengumpulan p JOIN tugas t ON t.id=p.tugas_id
              WHERE p.siswa_id=? AND t.kelas_id=?''',(siswa_id,kelas_id))
        dinilai=q('''SELECT COUNT(*) FROM pengumpulan p JOIN tugas t ON t.id=p.tugas_id
              WHERE p.siswa_id=? AND t.kelas_id=? AND p.nilai IS NOT NULL''',(siswa_id,kelas_id))
        belum=q('''SELECT COUNT(*) FROM pengumpulan p JOIN tugas t ON t.id=p.tugas_id
              WHERE p.siswa_id=? AND t.kelas_id=? AND p.nilai IS NULL''',(siswa_id,kelas_id))
        materi=q('SELECT COUNT(*) FROM materi WHERE kelas_id=?',(kelas_id,))
        aktivitas=[dict(r) for r in conn.execute('''SELECT tipe,judul,waktu,kelas_id FROM (
           SELECT 'materi' tipe,'Materi: '||judul judul,tanggal_upload waktu,kelas_id FROM materi
           UNION ALL SELECT 'tugas','Tugas: '||judul,tanggal_dibuat,kelas_id FROM tugas
           UNION ALL SELECT 'jadwal','Jadwal: '||COALESCE(materi,'Pertemuan'),tanggal,kelas_id FROM jadwal
           ) WHERE kelas_id=? AND waktu IS NOT NULL ORDER BY waktu DESC LIMIT 5''',(kelas_id,))]
        # Detail kartu tugas ditampilkan di bawah dashboard, bukan dialihkan
        # ke halaman lain; seluruh query selalu dibatasi kelas dan siswa login.
        daftar=[]
        kriteria={
            'dikerjakan': 'p.id IS NOT NULL',
            'belum_tugas': 'p.id IS NULL',
            'dinilai': 'p.nilai IS NOT NULL',
            'belum_nilai': 'p.id IS NOT NULL AND p.nilai IS NULL',
        }
        if panel in kriteria:
            daftar=[dict(r) for r in conn.execute(f"""SELECT t.id,t.judul,
                 t.deadline,p.nilai,p.waktu_kumpul,
                 CASE WHEN p.id IS NULL THEN 'Belum dikerjakan'
                      WHEN p.nilai IS NULL THEN 'Menunggu nilai'
                      ELSE 'Sudah dinilai' END AS status
                 FROM tugas t LEFT JOIN pengumpulan p
                   ON p.tugas_id=t.id AND p.siswa_id=?
                 WHERE t.kelas_id=? AND {kriteria[panel]}
                 ORDER BY t.id DESC""",(siswa_id,kelas_id))]
        presensi=grafik_presensi_siswa(siswa_id,kelas_id)
        return dict(stat=dict(kehadiran=presensi[-1]['nilai'] if presensi else None,
              dikerjakan=dikerjakan,belum_tugas=max(0,tugas-dikerjakan),total=total,
              selesai=terlaksana,sisa=sisa,
              dinilai=dinilai,belum_nilai=belum,materi=materi,total_tugas=tugas),
              presensi=presensi,aktivitas=aktivitas,daftar=daftar)
    finally:
        conn.close()
