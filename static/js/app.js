const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const overlay=$('#overlay');
function openModal(id){closeModals();overlay.hidden=false;document.getElementById(id).hidden=false}
function closeModals(){const wm=$('#who-menu');if(wm)wm.hidden=true;overlay.hidden=true;$$('.modal').forEach(m=>m.hidden=true);$$('.select.open').forEach(s=>s.classList.remove('open'));$$('.fileop').forEach(f=>f.classList.remove('show'))}
overlay.addEventListener('click',closeModals);
document.addEventListener('keydown',e=>e.key==='Escape'&&closeModals());
function confirmDel(text,url){$('#cf-text').textContent=text;$('#cf-yes').href=url;openModal('m-confirm')}
/* popup profil guru: <span data-pj='{"nama":..,"wa":..,"foto":..}'> */
function showPj(p){
  const img=$('#pj-foto');img.onerror=()=>{img.onerror=null;img.src=PATH.av};
  img.src=p.foto?PATH.up+p.foto:PATH.av;
  $('#pj-nama').textContent=p.nama;
  const wa=$('#pj-wa');wa.textContent=p.wa||'-';
  wa.href=p.wa?'https://wa.me/'+p.wa.replace(/\D/g,'').replace(/^0/,'62'):'#';
  openModal('m-pj')}
document.addEventListener('click',e=>{
  const c=e.target.closest('[data-close]');if(c){closeModals();return}
  /* menu pengguna (navbar): buka/tutup + keluar dengan konfirmasi */
  const wm=$('#who-menu');
  if(e.target.closest('#who-btn')){wm.hidden=!wm.hidden;$('#who-btn').setAttribute('aria-expanded',String(!wm.hidden));return}
  if(e.target.closest('[data-logout]')){confirmDel('Yakin ingin keluar?',PATH.out);return}
  if(wm&&!wm.hidden&&!e.target.closest('.who-wrap')){wm.hidden=true;$('#who-btn').setAttribute('aria-expanded','false')}
  const pj=e.target.closest('[data-pj]');if(pj){showPj(JSON.parse(pj.dataset.pj));return}
  const o=e.target.closest('[data-open]');if(o){e.stopPropagation();openModal(o.dataset.open)}
  const d=e.target.closest('[data-confirm]');if(d){e.stopPropagation();confirmDel(d.dataset.confirm,d.dataset.url)}
  if(!e.target.closest('.select'))$$('.select.open').forEach(s=>s.classList.remove('open'));
});
/* dropdown kustom */
$$('.select').forEach(s=>{
  const box=$('.sel-box',s),txt=$('.sel-text',s),multi=s.classList.contains('multi'),ph=s.dataset.ph||'';
  const form=s.closest('form'),chips=s.parentElement.querySelector('.chips');let sel=[];
  const hid=multi?$$('input[type=hidden]',s.parentElement):[$('input[type=hidden]',s)];
  txt.textContent=ph;box.classList.add('ph');
  s.setValue=(v,t)=>{hid[0].value=v;txt.textContent=t||ph;box.classList.toggle('ph',!v);hid[0].dispatchEvent(new Event('change'))};
  box.onclick=ev=>{ev.stopPropagation();const was=s.classList.contains('open');$$('.select.open').forEach(x=>x.classList.remove('open'));if(!was)s.classList.add('open')};
  $$('.sel-opts div',s).forEach(op=>op.onclick=ev=>{ev.stopPropagation();
    if(multi){const v=op.dataset.v;if(sel.some(x=>x.v==v))return;
      if(sel.length>=(+s.dataset.max||2)){alert('Maksimal '+s.dataset.max+' pengajar per kelas.');return}
      sel.push({v,t:op.dataset.t});draw()}
    else s.setValue(op.dataset.v,op.textContent);
    s.classList.remove('open')});
  function draw(){hid.forEach((h,i)=>h.value=sel[i]?sel[i].v:'');chips.innerHTML='';
    sel.forEach((x,i)=>{const c=document.createElement('span');c.className='chip';c.textContent=x.t;c.onclick=()=>{sel.splice(i,1);draw()};chips.appendChild(c)});
    hid[0].dispatchEvent(new Event('change'))}
  s.reset=()=>{sel=[];multi?draw():s.setValue('','')};
});
/* pilih peran -> tampilkan field pengajar */
$$('[data-role-toggle]').forEach(h=>h.addEventListener('change',()=>{
  $$('.pengajar-only',h.closest('form')).forEach(x=>x.hidden=h.value!=='pengajar');
  $$('.siswa-only',h.closest('form')).forEach(x=>x.hidden=h.value!=='siswa')}));
/* upload foto */
$$('.photo').forEach(p=>{
  const inp=$('input[type=file]',p),show=$('.fname',p),op=$('.fileop',p);
  $('.pbox',p).onclick=ev=>{ev.stopPropagation();op.classList.toggle('show')};
  op.onclick=()=>{op.classList.remove('show');inp.click()};
  inp.onchange=()=>{show.textContent=inp.files[0]?inp.files[0].name:'file png';show.style.color=inp.files[0]?'#000':'#999'};
});
/* validasi */
const RULES={
  required:v=>v.trim()?'':'Wajib diisi',
  nama:v=>v.trim()?'':'Nama lengkap wajib diisi',
  username:v=>v.trim().length>=5?'':'Username minimal 5 karakter',
  password:v=>/^(?=.*[A-Za-z])(?=.*\d).{8,}$/.test(v)?'':'Password harus kombinasi huruf dan angka, minimal 8 karakter',
  role:v=>v?'':'Pilih peran terlebih dahulu',
  wa:v=>/^(\+62|62|0)8[1-9]\d{6,10}$/.test(v.replace(/[\s-]/g,''))?'':'Format nomor WhatsApp tidak valid (contoh: 08123456789)',
  foto:(v,el)=>{const f=el.files[0];return f&&f.type.startsWith('image/')?'':f?'File harus berupa gambar':'Foto profil wajib dipilih'}
};
function setErr(el,msg){const f=el.closest('.field');if(!f)return;$('.err',f)?.remove();f.classList.toggle('bad',!!msg);
  if(msg){const s=document.createElement('small');s.className='err';s.textContent=msg;f.appendChild(s)}}
function check(el){
  if(el.closest('.pengajar-only[hidden], .siswa-only[hidden]'))return true;
  const v=el.value||'';if(el.dataset.optional!==undefined&&!v&&!(el.files&&el.files.length)){setErr(el,'');return true}
  let m=RULES[el.dataset.rule](v,el);
  if(!m&&el.dataset.after){const a=$(el.dataset.after,el.closest('form'));if(a.value&&v&&v<=a.value)m='Jam selesai harus setelah jam mulai'}
  if(m&&el.dataset.msg&&el.dataset.rule!=='password')m=el.dataset.msg;
  setErr(el,m);return !m}
$$('form[data-validate]').forEach(f=>{
  f.addEventListener('submit',e=>{let ok=true;$$('[data-rule]',f).forEach(el=>{if(!check(el))ok=false});if(!ok)e.preventDefault()});
  $$('[data-rule]',f).forEach(el=>['input','change'].forEach(ev=>el.addEventListener(ev,()=>el.closest('.field')?.classList.contains('bad')&&check(el))))});
/* tab kelas */
$$('.tabs a[data-p]').forEach(a=>a.onclick=()=>{const g=a.parentElement.dataset.g;
  $$(`.tabs[data-g="${g}"] a`).forEach(x=>x.classList.toggle('on',x===a));
  $$(`[data-pg="${g}"]`).forEach(p=>p.hidden=p.id!==a.dataset.p)});
$$('.item[data-toggle]').forEach(i=>i.onclick=()=>{const t=document.getElementById(i.dataset.toggle);t.hidden=!t.hidden});
$('#hadir-semua')?.addEventListener('click',()=>$$('input.ck[value=hadir]').forEach(r=>r.checked=true));