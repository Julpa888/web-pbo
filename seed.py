import sqlite3
import database

def init_db():
    conn = sqlite3.connect('fluenglo.db')
    with open('schema.sql', 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    database.migrasi()  # tambah kolom baru jika fluenglo.db masih versi lama

    cursor = conn.cursor()
    # Bersihkan data lama jika ada
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM kelas')
    cursor.execute('DELETE FROM jadwal')

    # Seed Hanya Akun Admin Utama
    cursor.execute('''
        INSERT INTO users (nama, username, password, role, foto, no_whatsapp, biodata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('Siti Julpa Admin', 'admin', 'admin123', 'admin', 'default_avatar.png', None, None))

    conn.commit()
    conn.close()
    print("Database fluenglo.db berhasil dibuat hanya dengan akun Admin!")

if __name__ == '__main__':
    init_db()