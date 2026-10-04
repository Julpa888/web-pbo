-- schema.sql
-- Penanggung jawab: JULPA (Koordinator/Integrator)
-- Dibuat sesuai class diagram final. Tiap anggota boleh menambah kolom
-- di tabel modulnya sendiri kalau memang dibutuhkan saat coding,
-- tapi infokan dulu di grup supaya tabel lain tidak ikut rusak.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('siswa', 'pengajar', 'admin')),
    -- kolom khusus Siswa:
    kelas_id INTEGER REFERENCES kelas(id),
    -- kolom khusus Pengajar (boleh NULL untuk role lain):
    foto TEXT,
    no_whatsapp TEXT,
    biodata TEXT
);

CREATE TABLE IF NOT EXISTS kelas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    pengajar_id INTEGER NOT NULL,
    FOREIGN KEY (pengajar_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS kelas_siswa (
    kelas_id INTEGER NOT NULL,
    siswa_id INTEGER NOT NULL,
    PRIMARY KEY (kelas_id, siswa_id),
    FOREIGN KEY (kelas_id) REFERENCES kelas(id),
    FOREIGN KEY (siswa_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS jadwal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hari TEXT NOT NULL,
    jam TEXT NOT NULL,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    FOREIGN KEY (kelas_id) REFERENCES kelas(id),
    FOREIGN KEY (pengajar_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS materi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    kategori TEXT NOT NULL,
    file TEXT,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    FOREIGN KEY (kelas_id) REFERENCES kelas(id),
    FOREIGN KEY (pengajar_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tugas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    deskripsi TEXT,
    deadline TEXT NOT NULL,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    FOREIGN KEY (kelas_id) REFERENCES kelas(id),
    FOREIGN KEY (pengajar_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS pengumpulan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tugas_id INTEGER NOT NULL,
    siswa_id INTEGER NOT NULL,
    jawaban TEXT,
    waktu_kumpul TEXT,
    nilai INTEGER,
    FOREIGN KEY (tugas_id) REFERENCES tugas(id),
    FOREIGN KEY (siswa_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS komentar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tugas_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    isi TEXT NOT NULL,
    waktu TEXT NOT NULL,
    FOREIGN KEY (tugas_id) REFERENCES tugas(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS presensi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal TEXT NOT NULL,
    siswa_id INTEGER NOT NULL,
    kelas_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Belum Hadir',
    FOREIGN KEY (siswa_id) REFERENCES users(id),
    FOREIGN KEY (kelas_id) REFERENCES kelas(id)
);

CREATE TABLE IF NOT EXISTS catatan_pengajar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    isi TEXT NOT NULL,
    tanggal TEXT NOT NULL,
    FOREIGN KEY (siswa_id) REFERENCES users(id),
    FOREIGN KEY (pengajar_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS rating (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    nilai INTEGER NOT NULL CHECK (nilai BETWEEN 1 AND 5),
    FOREIGN KEY (siswa_id) REFERENCES users(id),
    FOREIGN KEY (pengajar_id) REFERENCES users(id)
);
