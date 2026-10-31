// Fluenglo: interaksi umum (modal, tab, dropdown, multi-select, toggle password)
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const openM = m => { if (m) { m.hidden = false; document.body.classList.add('no-scroll'); } };
  const closeM = m => { m.hidden = true; if (!$('.modal:not([hidden])')) document.body.classList.remove('no-scroll'); };

  // Simpan kondisi awal form saat popup dibuka. Tombol Batal mengembalikan kondisi ini
  // tanpa menutup popup, sehingga perubahan yang belum disimpan benar-benar dibatalkan.
  const ambilStateForm = f => [...f.elements].map(i => ({
    name: i.name,
    type: i.type,
    value: i.type === 'checkbox' || i.type === 'radio' ? '' : i.value,
    checked: i.checked
  }));
  const simpanStateAwal = m => {
    const f = $('form', m);
    if (f) m._stateAwal = ambilStateForm(f);
  };
  const pulihkanStateForm = m => {
    const f = $('form', m);
    if (!f) return;
    if (!m._stateAwal) { f.reset(); return; }
    const daftar = m._stateAwal;
    for (const state of daftar) {
      const fields = [...f.elements].filter(i => i.name === state.name && i.type === state.type);
      if (!fields.length) continue;
      if (state.type === 'checkbox' || state.type === 'radio') {
        // Radio/checkbox perlu dipulihkan per elemen, bukan hanya berdasarkan name.
        const idx = daftar.filter(x => x.name === state.name && x.type === state.type).indexOf(state);
        if (fields[idx]) fields[idx].checked = state.checked;
      } else {
        fields[0].value = state.value ?? '';
      }
    }
    // File input tidak bisa diisi ulang oleh browser; Batal selalu mengosongkannya.
    $$('input[type="file"]', f).forEach(i => { i.value = ''; });
    bersihkanPesan(f);
    $$('[data-multi]', f).forEach(w => syncMulti(w));
    saringGuru(f);
    saringJurusan(f);
  };

  const syncMulti = w => {
    const on = $$('input[type=checkbox]:checked', w), lab = $('[data-label]', w);
    $$('input[type=hidden]', w).forEach((h, i) => h.value = on[i] ? on[i].value : '');
    lab.textContent = on.length ? on.map(c => c.dataset.name).join(', ') : lab.dataset.ph;
    $('.multi-btn', w).classList.toggle('has-value', on.length > 0);
  };

  // mengisi form sebuah modal lalu membukanya. Dipakai dua kali: waktu tombol Edit
  // ditekan, dan waktu server menolak isian (modalnya dibuka lagi dengan isi yang sama).
  const isiForm = (m, data, aksi) => {
    const f = $('form', m);
    if (!f) return openM(m);
    f.reset();
    if (aksi) f.action = aksi;
    // Pada modal Edit Siswa, opsi kelas utama hanya memuat kelas dengan progress 0.
    // Jika siswa saat ini berada di kelas yang sudah berjalan, tampilkan kelas saat ini
    // khusus untuk akun tersebut agar perubahan password/biodata tetap dapat disimpan.
    const selKelas = m.id === 'modal-edit-siswa' ? f.elements['kelas_id'] : null;
    if (selKelas) {
      $$('option[data-current-only]', selKelas).forEach(o => o.remove());
      const kid = data && data.kelas_id != null ? String(data.kelas_id) : '';
      if (kid && !$$('option', selKelas).some(o => o.value === kid)) {
        const opt = document.createElement('option');
        opt.value = kid;
        opt.textContent = (data && data.kelas_nama) ? `${data.kelas_nama} (Kelas saat ini)` : `Kelas #${kid}`;
        opt.dataset.currentOnly = '1';
        selKelas.appendChild(opt);
      }
    }
    Object.entries(data || {}).forEach(([k, v]) => {
      const i = f.elements[k];
      if (!i || i.type === 'file') return;
      // checkbox diisi lewat .checked, bukan .value (mis. centang "guru pengganti")
      if (i.type === 'checkbox') i.checked = !!v && v !== '0';
      else i.value = v ?? '';
    });
    $$('[data-multi]', f).forEach(w => {
      $$('input[type=checkbox]', w).forEach(c => c.checked = (data.pengajar_ids || []).includes(+c.value));
      syncMulti(w);
    });
    saringGuru(f);                       // dropdown pengajar ikut disesuaikan kelasnya
    if (data && data.pengajar_id) {      // nilainya dipasang lagi, karena penyaringan bisa mengosongkannya
      const g = f.elements['pengajar_id'];
      if (g) g.value = data.pengajar_id;
    }
    // kolom "Jurusan Lainnya" ikut dibuka kalau jurusannya di luar daftar.
    // Dipanggil SETELAH isian terpasang, supaya yang dibaca nilai yang baru, bukan yang lama.
    const jl = data && data.jurusan_lain;
    saringJurusan(f);
    if (jl) { const i = f.elements['jurusan_lain']; if (i) i.value = jl; }
    simpanStateAwal(m);
    openM(m);
  };

  // ----------  pesan kesalahan di dalam modal ----------
  // Dulu isian yang salah format baru ketahuan setelah form terkirim, dan modalnya
  // terlanjur tertutup sehingga semua ketikan hilang. Sekarang dicek dulu di browser:
  // modal tetap terbuka, isian utuh, pesannya muncul di dalam modal. Validasi di
  // server tetap jalan sebagai pengaman — ini cuma supaya tidak perlu mengetik ulang.
  const pesanSalah = i => {
    // isian tertentu (mis. pilihan background kelas) punya kalimatnya sendiri
    // waktu dibiarkan kosong, lewat data-pesan-kosong.
    if (i.validity.valueMissing) return i.dataset.pesanKosong || 'Bagian ini wajib diisi dulu.';
    return i.dataset.pesan || 'Isian ini belum sesuai format yang diminta.';
  };
  const bersihkanPesan = f => {
    const k = $('.form-error', f); if (k) k.remove();
    $$('.is-salah', f).forEach(i => i.classList.remove('is-salah'));
  };
  const tampilkanPesan = (f, inp) => {
    bersihkanPesan(f);
    const kotak = document.createElement('p');
    kotak.className = 'form-error';
    kotak.textContent = pesanSalah(inp);
    ($('.modal-body', f) || f).prepend(kotak);
    inp.classList.add('is-salah');
    inp.focus({ preventScroll: true });
    if (inp.scrollIntoView) inp.scrollIntoView({ block: 'center', behavior: 'smooth' });
  };

  // Pengajar tetap hanya boleh dipilih dari pengajar kelas tersebut.
  // Pengajar pengganti dipilih terpisah dan hanya ditugaskan ke satu jadwal.
  const saringGuru = form => {
    const kelas = $('[data-kelas-pick]', form), guru = $('[data-guru-pick]', form);
    if (!kelas || !guru) return;
    $$('option', guru).forEach(o => {
      if (!o.value) return;
      const miliknya = (o.dataset.kelas || '').split(' ').includes(kelas.value);
      o.hidden = !(kelas.value && miliknya);
      o.disabled = !(kelas.value && miliknya);
    });
    const dipilih = guru.selectedOptions[0];
    if (dipilih && dipilih.disabled) guru.value = '';
  };

  // ---------- jurusan "Lainnya" di form akun pengajar ----------
  // Dropdown jurusan punya 3 pilihan tetap + "Lainnya". Waktu "Lainnya" dipilih,
  // kolom ketik manual di sebelahnya dibuka DAN dijadikan wajib; selain itu kolomnya
  // disembunyikan sekaligus dilepas kewajibannya — kalau tidak, form jadi tidak bisa
  // dikirim gara-gara menunggu kolom yang tidak kelihatan.
  const saringJurusan = form => {
    const pilih = $('[data-jurusan-pick]', form), kotak = $('[data-jurusan-lain]', form);
    if (!pilih || !kotak) return;
    const lain = pilih.value && pilih.value === pilih.dataset.lain;
    kotak.hidden = !lain;
    const isi = $('input', kotak);
    if (!isi) return;
    isi.required = !!lain;
    if (!lain) isi.value = '';
  };

  // ---------- tab yang terbuka diingat lewat URL ----------
  // Sehabis menyimpan sesuatu, halaman dimuat ulang dari server dan tab-nya balik ke
  // yang paling kiri. Sekarang tab tujuannya dititipkan di URL (?tab= / ?pane= dari
  // server, atau #tab= waktu penggunanya sendiri yang mengeklik).
  const simpanTab = (kunci, nilai) => {
    try { history.replaceState(null, '', location.pathname + location.search + '#' + kunci + '=' + nilai); }
    catch (_) { /* browser lama: tidak apa-apa, cuma tidak diingat */ }
  };
  const bukaTabDariUrl = () => {
    const par = new URLSearchParams(location.search);
    ['tab', 'pane'].forEach(kunci => {
      const dariHash = location.hash.startsWith('#' + kunci + '=')
        ? decodeURIComponent(location.hash.slice(kunci.length + 2)) : '';
      const nilai = dariHash || par.get(kunci) || '';          // hash menang: itu klik terakhir pengguna
      if (!nilai) return;
      const tombol = $$('[data-' + kunci + ']').find(b => b.dataset[kunci] === nilai);
      if (tombol) tombol.click();
    });
  };

  document.addEventListener('click', e => {
    const t = e.target, up = s => t.closest(s);
    let el;

    if (!up('.usermenu')) { const dd = $('.user-dropdown'); if (dd) dd.hidden = true; }
    if (!up('.multi')) $$('.multi-list').forEach(l => l.hidden = true);

    if ((el = up('[data-open]'))) {
      const m = $('#' + el.dataset.open);
      if (m) {
        const f = $('form', m);
        // Modal Tambah selalu dimulai dari kondisi kosong. Modal edit/profil tetap
        // memakai nilai yang sudah dirender halaman sebagai kondisi awal.
        if (m.id.startsWith('modal-tambah-') && f) {
          f.reset();
          $$('[data-multi]', f).forEach(w => syncMulti(w));
          saringGuru(f);
          saringJurusan(f);
        }
        simpanStateAwal(m);
        openM(m);
      }
      return;
    }
    if ((el = up('[data-reset-form]'))) {
      const m = up('.modal'); pulihkanStateForm(m); return;
    }
    if (up('[data-close]')) return closeM(up('.modal'));
    if (t.classList.contains('modal')) {
      // Popup formulir hanya boleh ditutup lewat tombol X. Klik area gelap di luar
      // formulir tidak membuang isian yang sedang diedit.
      if ($('.modal-box.modal-form', t)) return;
      return closeM(t);
    }

    if ((el = up('[data-edit]'))) {            // isi form edit dari data-fill (JSON)
      const m = $('#' + el.dataset.edit);
      bersihkanPesan(m);                      // sisa pesan kesalahan dibuang dulu
      $$('[data-del-btn]', m).forEach(b => { b.dataset.confirm = el.dataset.del || ''; b.dataset.text = el.dataset.delText || ''; });
      return isiForm(m, JSON.parse(el.dataset.fill || '{}'), el.dataset.action);
    }
    if ((el = up('[data-confirm]'))) {         // konfirmasi hapus / keluar akun
      $$('.modal:not([hidden])').forEach(m => closeM(m));
      const dd = $('.user-dropdown'); if (dd) dd.hidden = true;   // tutup dropdown dulu
      $('#confirm-text').textContent = el.dataset.text || 'Yakin ingin menghapus data ini?';
      // judul & tombolnya bisa diganti tombol pemanggil (dipakai konfirmasi Logout).
      // Tanpa data-judul/data-ok/data-warna, bunyinya tetap seperti dulu.
      $('#confirm-judul').textContent = el.dataset.judul || 'Hapus Data';
      const ok = $('#confirm-ok');
      ok.textContent = el.dataset.ok || 'Ya, Hapus';
      ok.className = 'btn ' + (el.dataset.warna || 'btn-red');
      ok.href = el.dataset.confirm;
      return openM($('#modal-confirm'));
    }
    if ((el = up('[data-tab]'))) {             // tab Siswa / Pengajar
      const v = el.dataset.tab;
      $$('[data-tab]').forEach(b => b.classList.toggle('is-active', b === el));
      $$('[data-panel]').forEach(p => p.hidden = p.dataset.panel !== v);
      $$('[data-for]').forEach(b => b.hidden = b.dataset.for !== v);
      simpanTab('tab', v);                     // diingat, jadi refresh tidak balik ke tab awal
      return;
    }
    if ((el = up('[data-pane]'))) {            // subtab (Petunjuk | Pengumpulan, Login | Tentang Kami)
      $$('[data-pane]').forEach(b => b.classList.toggle('is-active', b === el));
      $$('[data-pane-id]').forEach(p => p.hidden = p.dataset.paneId !== el.dataset.pane);
      simpanTab('pane', el.dataset.pane);   
      return;
    }
    if (up('[data-lupa]')) { const h = $('#lupa-hint'); h.hidden = !h.hidden; return; }
    if ((el = up('.pw-toggle'))) {
      const i = $('input', el.parentElement), show = i.type === 'password';
      i.type = show ? 'text' : 'password'; el.classList.toggle('is-shown', show); return;
    }
    if ((el = up('[data-menu]'))) {
      const dd = $('.user-dropdown'); dd.hidden = !dd.hidden;
      el.setAttribute('aria-expanded', String(!dd.hidden)); return;
    }
    if ((el = up('.multi-btn'))) {
      const l = $('.multi-list', el.parentElement); l.hidden = !l.hidden;
      el.setAttribute('aria-expanded', String(!l.hidden)); return;
    }
    // Ikon mata di kolom Password (Kelola Akun): buka/tutup password aslinya.
    if ((el = up('[data-pw-cell]'))) {
      const sel = el.parentElement, tampil = $('.pw-asli', sel).hidden;
      $('.pw-mask', sel).hidden = tampil;
      $('.pw-asli', sel).hidden = !tampil;
      el.classList.toggle('is-shown', tampil);
      el.setAttribute('aria-label', tampil ? 'Sembunyikan password' : 'Tampilkan password');
      return;
    }

    if ((el = up('[data-flash-x]'))) el.closest('.flash').remove();
  });

  document.addEventListener('change', e => {
    const t = e.target, w = t.closest('[data-multi]');
    if (w && t.type === 'checkbox') {          // maksimal 2 pengajar per kelas
      if ($$('input:checked', w).length > 2) t.checked = false;
      syncMulti(w);
    }
    if (t.matches('[data-auto-hari]') && t.value && t.form.elements.hari) {   // hari otomatis dari tanggal
      t.form.elements.hari.value = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'][new Date(t.value + 'T00:00').getDay()];
    }

    // ganti kelas -> dropdown pengajar tetap disaring ulang
    if (t.matches('[data-kelas-pick]')) {
      const form = t.closest('form');
      if (form) saringGuru(form);
      return;
    }

    // ganti pilihan jurusan -> kolom "Jurusan Lainnya" dibuka/ditutupp
    if (t.matches('[data-jurusan-pick]')) {
      const form = t.closest('form');
      if (form) saringJurusan(form);
      return;
    }

    // pilih tanggal pertemuan -> tampilkan tabel presensi tanggal tersebut
    if (t.matches('[data-presensi-pick]')) {
      $$('.presensi-panel').forEach(f => f.hidden = f.id !== t.value);
      return;
    }

    // Centang "Semua" pada setiap status -> semua siswa langsung diberi status itu.
    // Diklik lagi -> seluruh status itu dikosongkan kembali.
    if (t.matches('[data-semua-status]')) {
      const form = t.closest('form');
      const kode = t.dataset.semuaStatus;
      $$('input[type=radio][value="' + kode + '"]', form).forEach(r => { if (!r.disabled) r.checked = t.checked; });
      if (t.checked) {
        $$('[data-semua-status]', form).forEach(s => { if (s !== t) s.checked = false; });
      }
      return;
    }

    // Kalau satu baris diubah manual, tombol "Semua" disinkronkan.
    if (t.type === 'radio' && t.name.startsWith('st_')) {
      const form = t.closest('form') || document;
      $$('[data-semua-status]', form).forEach(s => {
        const radios = $$('input[type=radio][value="' + s.dataset.semuaStatus + '"]:not(:disabled)', form);
        s.checked = radios.length > 0 && radios.every(r => r.checked);
      });
    }
  });

  // centang presensi bisa dibatalkan. Radio bawaan browser nggak bisa dilepas
  // sekali terpilih, jadi status "sudah tercentang sebelum diklik" diingat dulu di
  // mousedown, lalu dilepas waktu klik-nya terjadi.
  let radioSebelum = null;
  document.addEventListener('mousedown', e => {
    const w = e.target.closest ? e.target.closest('.chk-wrap') : null;
    const i = w && $('input[type=radio]', w);
    radioSebelum = (i && i.checked && !i.disabled) ? i : null;
  });
  document.addEventListener('click', e => {
    const w = e.target.closest ? e.target.closest('.chk-wrap') : null;
    const i = w && $('input[type=radio]', w);
    if (i && i === radioSebelum) {
      i.checked = false;
      radioSebelum = null;
      const form = i.closest('form') || document;
      $$('[data-semua-status]', form).forEach(s => { s.checked = false; });
    }
  });

  // form dicegat dulu sebelum terkirim. Balon bawaan browser dimatikan
  // (noValidate) supaya pesannya memakai gaya web ini dan muncul di dalam modal.
  $$('form').forEach(f => f.noValidate = true);

  document.addEventListener('submit', e => {
    const f = e.target;
    if (f.checkValidity()) { bersihkanPesan(f); return; }
    e.preventDefault();
    const salah = $$('input, select, textarea', f).find(i => i.willValidate && !i.checkValidity());
    if (salah) tampilkanPesan(f, salah);
  });

  // Preflight username sebelum form akun dikirim: saat duplikat, file upload tetap ada.
  document.addEventListener('submit', async e => {
    const f = e.target;
    if (!f.matches('[data-check-username]') || !f.checkValidity()) return;
    e.preventDefault();
    if (f.dataset.cekSedang === '1') return;
    f.dataset.cekSedang = '1';
    const submit = f.querySelector('[type="submit"], button:not([type])');
    if (submit) submit.disabled = true;
    try {
      const username = f.elements.username?.value.trim() || '';
      const cocok = /\/edit\/(\d+)/.exec(f.action);
      const url = new URL(f.dataset.checkUsername, location.origin);
      url.searchParams.set('username', username);
      if (cocok) url.searchParams.set('exclude', cocok[1]);
      const response = await fetch(url, {credentials: 'same-origin'});
      if (!response.ok) throw new Error('Gagal memeriksa username.');
      const data = await response.json();
      if (!data.available) {
        const inp = f.elements.username;
        bersihkanPesan(f);
        const box = document.createElement('p');
        box.className = 'form-error'; box.textContent = 'Username sudah digunakan.';
        ($('.modal-body', f) || f).prepend(box);
        inp.classList.add('is-salah'); inp.focus();
        return;
      }
      HTMLFormElement.prototype.submit.call(f);
    } catch (error) {
      bersihkanPesan(f);
      const box = document.createElement('p');
      box.className = 'form-error';
      box.textContent = error.message || 'Pemeriksaan username gagal. Coba lagi.';
      ($('.modal-body', f) || f).prepend(box);
    } finally {
      f.dataset.cekSedang = '0';
      if (submit) submit.disabled = false;
    }
  });

  // pesan hilang sendiri begitu isian yang salah sudah dibetulkan
  document.addEventListener('input', e => {
    const t = e.target;
    if (t.form && t.classList.contains('is-salah') && t.checkValidity()) bersihkanPesan(t.form);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') $$('.modal:not([hidden])').forEach(m => { if (!$('.modal-box.modal-form', m)) closeM(m); });
  });
  setTimeout(() => $$('.flash').forEach(f => f.remove()), 6000);

  // buka tab sesuai URL, saring dropdown pengajar, lalu buka lagi modal yang ditolak server.
  bukaTabDariUrl();
  $$('form').forEach(f => { if ($('[data-guru-pick]', f)) saringGuru(f); });
  $$('form').forEach(f => saringJurusan(f));   // BARU (revisi 3)
  const ulang = $('[data-reopen]');
  if (ulang) {
    const m = $('#' + ulang.dataset.reopen);
    if (m) isiForm(m, JSON.parse(ulang.dataset.fill || '{}'), ulang.dataset.aksi || '');
  }
})();

