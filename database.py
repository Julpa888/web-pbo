import sqlite3

DB_NAME = 'fluenglo.db'

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def migrasi():
    """Tambah kolom baru ke fluenglo.db lama (aman dijalankan berulang kali).
    - kelas.pengajar_id2 : guru kedua (opsional) tiap kelas
    - jadwal.tanggal / jadwal.materi : dipakai form Buat Jadwal & tabel jadwal
    - users.alamat / users.nik / users.email : data pengajar (revisi dosen)
    """
    conn = get_connection()
    def kolom(tabel):
        return [r['name'] for r in conn.execute(f'PRAGMA table_info({tabel})')]
    tambahan = [
        ('kelas', 'pengajar_id2', 'INTEGER'),
        ('jadwal', 'tanggal', 'TEXT'),
        ('jadwal', 'materi', 'TEXT'),
        ('users', 'alamat', 'TEXT'),
        ('users', 'nik', 'TEXT'),
        ('users', 'email', 'TEXT'),
    ]
    for tabel, nama, tipe in tambahan:
        ada = kolom(tabel)
        if ada and nama not in ada:
            conn.execute(f'ALTER TABLE {tabel} ADD COLUMN {nama} {tipe}')
    conn.commit()
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
        SELECT u.*, k.nama AS kelas_nama
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
        ''', (nama, username, password, role, foto or 'default_avatar.png', no_whatsapp,
              biodata, kelas_id, alamat, nik, email))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Username sudah digunakan.")
    finally:
        conn.close()

def edit_user(user_id, **kwargs):
    conn = get_connection()
    fields = []
    values = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        values.append(v)
    values.append(user_id)
    sql = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
    try:
        conn.execute(sql, values)
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Username sudah digunakan.")
    finally:
        conn.close()

def hapus_user(user_id):
    conn = get_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()


# --- KELAS FUNCTIONS ---
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

def ambil_semua_kelas():
    """Tiap kelas dikembalikan sebagai dict: id, nama, nama_kelas, pengajar_id, pengajar_id2,
    pengajar_list (1-2 guru) dan nama_pengajar (nama guru digabung)."""
    conn = get_connection()
    rows = conn.execute('SELECT *, nama AS nama_kelas FROM kelas ORDER BY id').fetchall()
    conn.close()
    hasil = []
    for r in rows:
        k = dict(r)
        k['pengajar_list'] = ambil_pengajar_kelas(r)
        k['nama_pengajar'] = ', '.join(p['nama'] for p in k['pengajar_list'])
        hasil.append(k)
    return hasil

def tambah_kelas(nama, pengajar_id, pengajar_id2=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO kelas (nama, pengajar_id, pengajar_id2) VALUES (?, ?, ?)',
                   (nama, pengajar_id, pengajar_id2))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def edit_kelas(kelas_id, nama, pengajar_id, pengajar_id2=None):
    conn = get_connection()
    conn.execute('UPDATE kelas SET nama = ?, pengajar_id = ?, pengajar_id2 = ? WHERE id = ?',
                 (nama, pengajar_id, pengajar_id2, kelas_id))
    conn.commit()
    conn.close()

def hapus_kelas(kelas_id):
    conn = get_connection()
    # jadwal kelas ikut dihapus & siswa dilepas dari kelas, supaya tidak ada data yatim
    conn.execute('DELETE FROM jadwal WHERE kelas_id = ?', (kelas_id,))
    conn.execute('UPDATE users SET kelas_id = NULL WHERE kelas_id = ?', (kelas_id,))
    conn.execute('DELETE FROM kelas WHERE id = ?', (kelas_id,))
    conn.commit()
    conn.close()

def ambil_siswa_by_kelas(kelas_id):
    conn = get_connection()
    rows = conn.execute('SELECT * FROM users WHERE role = "siswa" AND kelas_id = ?', (kelas_id,)).fetchall()
    conn.close()
    return rows

def ambil_kelas_siswa(siswa_id):
    conn = get_connection()
    row = conn.execute('''
        SELECT k.* FROM kelas k
        JOIN users u ON u.kelas_id = k.id
        WHERE u.id = ?
    ''', (siswa_id,)).fetchone()
    conn.close()
    return row

def tambah_siswa_ke_kelas(kelas_id, siswa_id):
    conn = get_connection()
    conn.execute('UPDATE users SET kelas_id = ? WHERE id = ?', (kelas_id, siswa_id))
    conn.commit()
    conn.close()

def hapus_siswa_dari_kelas(kelas_id, siswa_id):
    conn = get_connection()
    conn.execute('UPDATE users SET kelas_id = NULL WHERE id = ? AND kelas_id = ?', (siswa_id, kelas_id))
    conn.commit()
    conn.close()

def hitung_data_terkait_kelas(kelas_id):
    conn = get_connection()
    materi = conn.execute('SELECT COUNT(*) FROM materi WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    tugas = conn.execute('SELECT COUNT(*) FROM tugas WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    presensi = conn.execute('SELECT COUNT(*) FROM presensi WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    conn.close()
    return {'materi': materi, 'tugas': tugas, 'presensi': presensi}


# --- JADWAL FUNCTIONS ---
def ambil_jadwal_by_id(jadwal_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM jadwal WHERE id = ?', (jadwal_id,)).fetchone()
    conn.close()
    return row

def ambil_semua_jadwal():
    conn = get_connection()
    rows = conn.execute('''
        SELECT j.*, k.nama as kelas_nama, u.nama as pengajar_nama
        FROM jadwal j
        JOIN kelas k ON j.kelas_id = k.id
        JOIN users u ON j.pengajar_id = u.id
    ''').fetchall()
    conn.close()
    return rows

def ambil_jadwal_by_hari(hari):
    conn = get_connection()
    rows = conn.execute('''
        SELECT j.*, k.nama as kelas_nama, u.nama as pengajar_nama
        FROM jadwal j
        JOIN kelas k ON j.kelas_id = k.id
        JOIN users u ON j.pengajar_id = u.id
        WHERE j.hari = ?
    ''', (hari,)).fetchall()
    conn.close()
    return rows

def ambil_jadwal_by_tanggal(tanggal):
    conn = get_connection()
    rows = conn.execute('''
        SELECT j.*, k.nama as kelas_nama, u.nama as pengajar_nama
        FROM jadwal j
        JOIN kelas k ON j.kelas_id = k.id
        JOIN users u ON j.pengajar_id = u.id
        WHERE j.tanggal = ?
    ''', (tanggal,)).fetchall()
    conn.close()
    return rows

def ambil_jadwal_by_kelas(kelas_id):
    conn = get_connection()
    rows = conn.execute('SELECT * FROM jadwal WHERE kelas_id = ?', (kelas_id,)).fetchall()
    conn.close()
    return rows

def ambil_jadwal_by_pengajar(pengajar_id):
    conn = get_connection()
    rows = conn.execute('SELECT * FROM jadwal WHERE pengajar_id = ?', (pengajar_id,)).fetchall()
    conn.close()
    return rows

def tambah_jadwal(hari, jam, kelas_id, pengajar_id, tanggal=None, materi=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO jadwal (hari, jam, kelas_id, pengajar_id, tanggal, materi) VALUES (?, ?, ?, ?, ?, ?)',
                   (hari, jam, kelas_id, pengajar_id, tanggal, materi))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def edit_jadwal(jadwal_id, hari, jam, kelas_id, pengajar_id, tanggal=None, materi=None):
    conn = get_connection()
    conn.execute('''
        UPDATE jadwal SET hari = ?, jam = ?, kelas_id = ?, pengajar_id = ?, tanggal = ?, materi = ?
        WHERE id = ?
    ''', (hari, jam, kelas_id, pengajar_id, tanggal, materi, jadwal_id))
    conn.commit()
    conn.close()

def hapus_jadwal(jadwal_id):
    conn = get_connection()
    conn.execute('DELETE FROM jadwal WHERE id = ?', (jadwal_id,))
    conn.commit()
    conn.close()


# --- MATERI & TUGAS FUNCTIONS ---
# TODO (Anggota 2): query materi (upload, ambil, hapus) dan tugas (buat, ambil, kumpul, komentar)

# --- PENILAIAN & CATATAN AKHIR FUNCTIONS ---
# TODO (Anggota 3): query penilaian tugas, rekap nilai, dan catatan akhir pengajar

# --- PRESENSI FUNCTIONS ---
# TODO (Anggota 4): query presensi (catat, update status, rekap per siswa/kelas)