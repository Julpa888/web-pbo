CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    kelas_id INTEGER,
    foto TEXT DEFAULT 'default_avatar.png',
    no_whatsapp TEXT,
    biodata TEXT,
    FOREIGN KEY(kelas_id) REFERENCES kelas(id)
);

CREATE TABLE IF NOT EXISTS kelas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT UNIQUE NOT NULL,
    pengajar_id INTEGER NOT NULL,
    pengajar_id2 INTEGER,
    FOREIGN KEY(pengajar_id) REFERENCES users(id),
    FOREIGN KEY(pengajar_id2) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS jadwal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hari TEXT NOT NULL,
    jam TEXT NOT NULL,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    tanggal TEXT,
    materi TEXT,
    FOREIGN KEY(kelas_id) REFERENCES kelas(id),
    FOREIGN KEY(pengajar_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS materi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    kategori TEXT,
    file_path TEXT,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tugas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    deskripsi TEXT,
    deadline TEXT,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS presensi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal TEXT NOT NULL,
    siswa_id INTEGER NOT NULL,
    kelas_id INTEGER NOT NULL,
    status TEXT DEFAULT 'Belum Hadir'
);