import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { saveGroupCertificates } from '../api'
import { BRAND_ASSETS, BRAND_NAME } from '../constants/brand'

// Guruh uchun ommaviy sertifikat generatsiyasi — hunter/admin/o'qituvchi
// bitta tugma bilan guruhdagi barcha o'quvchilar uchun bosma sertifikat
// sahifalarini oladi. Yozuvlar backendda saqlanadi (group_certificates),
// shu sababli qayta ochilganda/regenerate qilinganda avvalgi tahrirlar
// yo'qolmaydi va "Saqlash" bilan yangi tahrirlarni yozib qo'yish mumkin.

/* Sertifikat — CHOP hujjati. Varaqning o'zi (`.mcert-cert`) ikkala rejimda
   ham OQ qoladi: u qog'ozga chiqadigan hujjat, ekran mavzusi emas.
   Atrofidagi ish maydoni va asboblar paneli esa mavzuga ergashadi —
   aks holda qorong'i rejimda ekran to'satdan oqarib ketardi. */
const CSS = `
.mcert-wrap{
  --blue:#2961FF; --blue-deep:#1B44C7; --green:#20CE94;
  --ink:#0E1B4D; --muted:#5b6a9a; --soft:#eef2ff;
  position:fixed; inset:0; z-index:2000; overflow:auto;
  background:var(--bg);
  font-family:'Segoe UI','Poppins',system-ui,-apple-system,sans-serif;
}
.mcert-wrap *{box-sizing:border-box}
.mcert-toolbar{
  position:sticky; top:0; z-index:10;
  background:var(--surface); color:var(--text);
  border-bottom:1px solid var(--border);
  padding:14px 20px;
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  box-shadow:var(--shadow-sm);
}
.mcert-toolbar .grow{flex:1; color:var(--text); font-weight:700}
.mcert-toolbar .hint{width:100%; font-size:12px; color:var(--muted)}
.mcert-btn{
  border:none; background:var(--primary); color:var(--primary-on); font-weight:700; font-size:14px;
  padding:10px 18px; border-radius:10px; cursor:pointer; font-family:inherit;
}
.mcert-btn:hover{background:var(--primary-hover)}
.mcert-btn:disabled{opacity:.6; cursor:default}
.mcert-btn.secondary{
  background:var(--surface); color:var(--text-2);
  border:1px solid var(--border-2); box-shadow:none;
}
.mcert-btn.secondary:hover{background:var(--surface-hover); color:var(--text)}
.mcert-btn.green{background:var(--green)}
.mcert-btn.green:hover{background:#19b382}

.mcert-stage{ display:flex; flex-direction:column; align-items:center; gap:28px; padding:28px 16px 60px }
.mcert-page{ width:1000px; max-width:100%; }
.mcert-cert{
  position:relative; width:1000px; height:707px; background:#fff; overflow:hidden;
  box-shadow:0 20px 60px rgba(20,40,110,.25); margin:0 auto;
}
.mcert-cert::before{
  content:""; position:absolute; inset:0; z-index:0;
  background:
    radial-gradient(120% 80% at 50% -10%, rgba(41,97,255,.06), transparent 60%),
    radial-gradient(120% 80% at 50% 110%, rgba(32,206,148,.06), transparent 60%);
}
.mcert-strip{position:absolute; inset:20px; z-index:1; border-radius:4px; overflow:hidden}
.mcert-strip .pat{position:absolute; inset:0; opacity:.14}
.mcert-frame{
  position:absolute; inset:46px; z-index:3; background:#fff; border-radius:3px;
  box-shadow:0 0 0 2px var(--blue), 0 0 0 3px #fff, 0 0 0 4px rgba(41,97,255,.35);
}
.mcert-corner{position:absolute; z-index:4; width:66px; height:66px; color:var(--blue)}
.mcert-corner.tl{top:34px; left:34px}
.mcert-corner.tr{top:34px; right:34px; transform:scaleX(-1)}
.mcert-corner.bl{bottom:34px; left:34px; transform:scaleY(-1)}
.mcert-corner.br{bottom:34px; right:34px; transform:scale(-1,-1)}
.mcert-watermark{
  position:absolute; z-index:2; width:480px; height:480px;
  left:50%; top:55%; transform:translate(-50%,-50%); opacity:.045; color:var(--blue);
}
.mcert-content{
  position:absolute; inset:56px 90px 200px; z-index:5; overflow:hidden;
  display:flex; flex-direction:column; align-items:center; text-align:center;
}
/* Sertifikat sarlavhasi — rasmiy lokap. Ilgari bu yerda qo'lda chizilgan
   SVG belgi va alohida "Minar / Academy" matni turardi: ya'ni chop etilgan
   hujjatda brendning aslidan farq qiladigan nusxasi chiqardi. Chop uchun
   3200px kenglikdagi aktiv olinadi — A4 landshaftda ham keskin qoladi. */
.mcert-brand{display:flex; align-items:center; justify-content:center}
.mcert-logo{height:58px; width:auto; object-fit:contain; display:block}
.mcert-title{margin-top:12px; font-size:44px; letter-spacing:13px; font-weight:800; color:var(--ink); text-transform:uppercase}
.mcert-subtitle{margin-top:4px; font-size:13px; letter-spacing:4px; text-transform:uppercase; color:var(--blue); font-weight:700}
.mcert-divider{display:flex; align-items:center; gap:12px; margin:10px 0 6px}
.mcert-divider .l{width:90px; height:2px; background:linear-gradient(90deg,transparent,var(--blue))}
.mcert-divider .r{width:90px; height:2px; background:linear-gradient(90deg,var(--blue),transparent)}
.mcert-divider .d{width:9px; height:9px; background:var(--blue); transform:rotate(45deg); flex-shrink:0}
.mcert-awarded{font-size:14px; color:var(--muted)}
.mcert-student{
  font-family:'Georgia','Times New Roman',serif; font-size:38px; line-height:1.2; color:var(--blue);
  font-weight:700; margin:6px 0 2px; padding:0 24px 6px; min-width:440px; max-width:100%;
  border-bottom:2px solid #d7ddf2; outline:none; overflow-wrap:break-word;
}
.mcert-student:focus{border-bottom-color:var(--blue)}
.mcert-body{font-size:14px; color:var(--ink); line-height:1.5; max-width:640px; margin-top:8px}
.mcert-body b{color:var(--blue)}
.mcert-badge{
  display:inline-block; margin-top:6px; background:var(--soft); color:var(--blue-deep);
  font-weight:700; padding:5px 16px; border-radius:22px; letter-spacing:.5px; font-size:13px;
  border:1px solid rgba(41,97,255,.2); max-width:100%; overflow-wrap:break-word;
}
.mcert-footer{
  position:absolute; z-index:5; left:96px; right:96px; bottom:64px;
  display:flex; align-items:flex-end; justify-content:space-between;
}
.mcert-sign{display:flex; flex-direction:column; align-items:center; min-width:200px}
.mcert-sign .val{font-size:15px; color:var(--ink); font-weight:700; margin-bottom:4px; outline:none; font-family:'Georgia',serif}
.mcert-sign .line{width:190px; border-top:1.6px solid var(--ink); margin-bottom:6px}
.mcert-sign .role{font-size:13px; color:var(--muted); font-weight:600}
.mcert-medal{position:relative; width:132px; height:150px; display:flex; justify-content:center}
.mcert-medal .rl,.mcert-medal .rr{position:absolute; top:66px; width:22px; height:56px; background:var(--blue)}
.mcert-medal .rl{left:44px; transform:skewX(8deg); clip-path:polygon(0 0,100% 0,100% 100%,50% 82%,0 100%)}
.mcert-medal .rr{right:44px; transform:skewX(-8deg); clip-path:polygon(0 0,100% 0,100% 100%,50% 82%,0 100%); background:var(--green)}
.mcert-medal .disc{
  position:absolute; top:0; width:96px; height:96px; border-radius:50%;
  background:radial-gradient(circle at 35% 30%,#5a83ff,var(--blue) 60%,var(--blue-deep));
  display:flex; align-items:center; justify-content:center;
  box-shadow:0 6px 16px rgba(41,97,255,.4), inset 0 2px 4px rgba(255,255,255,.5);
}
.mcert-medal .disc::before{content:""; position:absolute; inset:7px; border-radius:50%; border:2px dashed rgba(255,255,255,.55)}
.mcert-medal .disc .mark{width:52px; height:52px; color:#fff; position:relative}
.mcert-meta{position:absolute; z-index:5; left:96px; bottom:34px; font-size:11px; color:var(--muted); letter-spacing:.5px}
.mcert-meta b{color:var(--ink)}

@media print{
  @page{ size:A4 landscape; margin:0 }
  /* Brauzer chop etishda fon/rasm ranglarini o'chirib qo'ymasin */
  .mcert-wrap, .mcert-wrap *{ -webkit-print-color-adjust:exact; print-color-adjust:exact }
  body *{ visibility:hidden }
  .mcert-wrap, .mcert-wrap *{ visibility:visible }
  .mcert-wrap{ position:absolute; inset:0; background:#fff }
  .mcert-toolbar{ display:none }
  .mcert-stage{ padding:0; gap:0 }
  .mcert-page{ width:100%; height:100vh; page-break-after:always }
  .mcert-page:last-child{ page-break-after:auto }
  .mcert-cert{ box-shadow:none; width:100%; height:100vh }
}
`

function Star8Corner({ className }) {
  return (
    <svg className={className} viewBox="0 0 100 100" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <use href="#mcertStar8" transform="translate(0 0) scale(.62)" />
      <use href="#mcertStar8" transform="translate(38 38) scale(.42)" opacity=".55" />
    </svg>
  )
}

function CertificateCard({ cert, groupName, onEdit }) {
  return (
    <div className="mcert-page">
      <div className="mcert-cert">
        <div className="mcert-strip">
          <svg className="pat" viewBox="0 0 1000 707" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id={`tile-${cert.id}`} width="110" height="110" patternUnits="userSpaceOnUse">
                <path d="M55 6 71 24 89 24 89 42 107 60 89 78 89 96 71 96 55 114 39 96 21 96 21 78 3 60 21 42 21 24 39 24 Z"
                      fill="none" stroke="#2961FF" strokeWidth="2" />
              </pattern>
            </defs>
            <rect width="1000" height="707" fill={`url(#tile-${cert.id})`} />
          </svg>
        </div>

        <svg className="mcert-watermark" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><use href="#mcertMark" /></svg>

        <div className="mcert-frame" />

        <Star8Corner className="mcert-corner tl" />
        <Star8Corner className="mcert-corner tr" />
        <Star8Corner className="mcert-corner bl" />
        <Star8Corner className="mcert-corner br" />

        <div className="mcert-content">
          <div className="mcert-brand">
            <img
              className="mcert-logo"
              src={BRAND_ASSETS.print.brand.src}
              alt={BRAND_NAME}
              draggable="false"
            />
          </div>

          <div className="mcert-title">Sertifikat</div>
          <div className="mcert-subtitle">Certificate of Completion</div>

          <div className="mcert-divider"><span className="l" /><span className="d" /><span className="r" /></div>

          <div className="mcert-awarded">Ushbu sertifikat</div>
          <div
            className="mcert-student" contentEditable suppressContentEditableWarning
            onBlur={e => onEdit(cert.id, 'student_name', e.currentTarget.textContent.trim())}
          >{cert.student_name}</div>

          <div className="mcert-body">
            ga <b>«{cert.course_label || 'kurs'}»</b> kursini muvaffaqiyatli tamomlaganligi va barcha
            bosqichlarni o'zlashtirganligi uchun taqdim etiladi.
            <br />
            <span className="mcert-badge">{cert.course_label || 'Kurs'} · {groupName}</span>
          </div>
        </div>

        <div className="mcert-footer">
          <div className="mcert-sign">
            <div
              className="val" contentEditable suppressContentEditableWarning
              onBlur={e => onEdit(cert.id, 'issue_date', e.currentTarget.textContent.trim())}
            >{cert.issue_date}</div>
            <div className="line" /><div className="role">Berilgan sana</div>
          </div>

          <div className="mcert-medal">
            <div className="rl" /><div className="rr" />
            <div className="disc"><svg className="mark" viewBox="0 0 200 200"><use href="#mcertMark" /></svg></div>
          </div>

          <div className="mcert-sign">
            <div
              className="val" contentEditable suppressContentEditableWarning
              onBlur={e => onEdit(cert.id, 'signer_name', e.currentTarget.textContent.trim())}
            >{cert.signer_name}</div>
            <div className="line" /><div className="role">{cert.signer_title}</div>
          </div>
        </div>

        <div className="mcert-meta">
          Sertifikat №: <b
            contentEditable suppressContentEditableWarning
            onBlur={e => onEdit(cert.id, 'cert_number', e.currentTarget.textContent.trim())}
          >{cert.cert_number}</b> &nbsp;·&nbsp; minaracademy.uz
        </div>
      </div>
    </div>
  )
}

export default function GroupCertificates({ group, records, onClose }) {
  const [certs, setCerts] = useState(records)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)

  function handleEdit(id, field, value) {
    setCerts(prev => prev.map(c => (c.id === id ? { ...c, [field]: value } : c)))
    setDirty(true)
  }

  async function handleSave() {
    setSaving(true)
    try {
      const items = certs.map(c => ({
        id: c.id,
        student_name: c.student_name,
        cert_number: c.cert_number,
        course_label: c.course_label,
        issue_date: c.issue_date,
        signer_name: c.signer_name,
        signer_title: c.signer_title,
      }))
      const saved = await saveGroupCertificates(group.id, items)
      setCerts(saved)
      setDirty(false)
      toast.success('Sertifikatlar saqlandi')
    } catch (err) {
      toast.error(err.message || "Saqlab bo'lmadi")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mcert-wrap">
      <style>{CSS}</style>

      {/* shared SVG defs — reused by every certificate via <use href="#..."> */}
      <svg width="0" height="0" style={{ position: 'absolute' }} xmlns="http://www.w3.org/2000/svg">
        <defs>
          <mask id="mcertStarHole">
            <rect width="200" height="200" fill="#fff" />
            <g fill="#000">
              <rect x="70.3" y="70.3" width="59.4" height="59.4" />
              <rect x="70.3" y="70.3" width="59.4" height="59.4" transform="rotate(45 100 100)" />
            </g>
          </mask>
          <g id="mcertMark" mask="url(#mcertStarHole)">
            <g fill="currentColor">
              <circle cx="100" cy="60" r="34" /><circle cx="128" cy="72" r="34" />
              <circle cx="140" cy="100" r="34" /><circle cx="128" cy="128" r="34" />
              <circle cx="100" cy="140" r="34" /><circle cx="72" cy="128" r="34" />
              <circle cx="60" cy="100" r="34" /><circle cx="72" cy="72" r="34" />
              <circle cx="100" cy="100" r="48" />
            </g>
          </g>
          <g id="mcertStar8">
            <path d="M50 4 63 21 84 16 79 37 96 50 79 63 84 84 63 79 50 96 37 79 16 84 21 63 4 50 21 37 16 16 37 21 Z" />
          </g>
        </defs>
      </svg>

      <div className="mcert-toolbar">
        <strong style={{ fontSize: 15 }}>{group.name} — {certs.length} ta sertifikat</strong>
        <span className="grow" />
        <button className="mcert-btn secondary" onClick={onClose}>Yopish</button>
        <button className="mcert-btn green" onClick={handleSave} disabled={saving || !dirty}>
          {saving ? 'Saqlanmoqda...' : dirty ? 'Saqlash' : 'Saqlangan ✓'}
        </button>
        <button className="mcert-btn" onClick={() => window.print()}>🖨️ Chop etish / PDF</button>
        <p className="hint" style={{ width: '100%', fontSize: 12, color: 'var(--muted)', margin: 0 }}>
          Har bir o'quvchining ismi, sanasi, imzo va sertifikat raqamini sertifikat ustida bosib to'g'ridan-to'g'ri
          tahrirlashingiz mumkin — «Saqlash» bosilmaguncha tahrirlar faqat shu ekranda ko'rinadi. Yuklab olish uchun
          «Chop etish» → «PDF sifatida saqlash» (har bir o'quvchi alohida sahifada).
        </p>
      </div>

      <div className="mcert-stage">
        {certs.map(c => (
          <CertificateCard key={c.id} cert={c} groupName={group.name} onEdit={handleEdit} />
        ))}
        {certs.length === 0 && (
          <div style={{ color: 'var(--muted)', padding: 40 }}>Guruhda o'quvchilar yo'q</div>
        )}
      </div>
    </div>
  )
}
