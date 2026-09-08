import { PageIntro } from './ui/Workspace'
import { Initials, SummaryRow, ViewTabs } from './ui/Workspace'
import Overlay from './ui/Overlay'
import PersonName from './ui/PersonName'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPeopleRoof, faPlus, faKey, faToggleOn, faToggleOff,
  faCopy, faSearch, faUserPlus, faXmark, faMobileScreen, faPaperPlane,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchParents, createParent, updateParent, resetParentPassword,
  linkParentChild, unlinkParentChild, fetchStudents, broadcastToParents,
} from '../api'
import useConfirm from './ui/useConfirm'
import DataTable, { RowActions } from './ui/DataTable'

const EMPTY = { full_name: '', phone: '', username: '', password: '', student_ids: [] }

export default function Parents({ currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const canManage = currentUser?.role === 'hunter' || currentUser?.role === 'admin'
  const isAdmin = currentUser?.role === 'admin'

  const [items, setItems] = useState([])
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [parentView, setParentView] = useState('families')

  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  // Yaratilgandan keyin login/parol BIR MARTA ko'rsatiladi
  const [creds, setCreds] = useState(null)          // { full_name, username, password }
  const [linkFor, setLinkFor] = useState(null)      // farzand biriktirish modali (parent obj)

  // Telegram orqali barcha ota-onalarga xabar yuborish
  const [broadcastModal, setBroadcastModal] = useState(false)
  const [broadcastText, setBroadcastText] = useState('')
  const [broadcasting, setBroadcasting] = useState(false)

  async function handleBroadcast() {
    if (!broadcastText.trim()) { toast.error('Xabar matnini kiriting'); return }
    setBroadcasting(true)
    try {
      const r = await broadcastToParents(broadcastText.trim())
      if (r.sent > 0) {
        toast.success(`Yuborildi: ${r.sent}/${r.total} ota-onaga`)
        setBroadcastModal(false)
        setBroadcastText('')
      } else {
        toast.error(
          `Hech kimga yetmadi (0/${r.total}).` +
          (r.sample_errors?.length ? ` Sabab: ${r.sample_errors[0]}` : ''),
          { duration: 8000 }
        )
      }
    } catch (e) { toast.error(e.message) }
    finally { setBroadcasting(false) }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    fetchStudents({ page_size: 100 }).then(r => setStudents(r.items || [])).catch(() => {})
  }, [])

  async function load(q) {
    setLoading(true)
    try { setItems(await fetchParents(q)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function handleSearch(e) {
    e.preventDefault()
    load(search.trim() || undefined)
  }

  function toggleStudent(id) {
    setForm(p => ({
      ...p,
      student_ids: p.student_ids.includes(id)
        ? p.student_ids.filter(x => x !== id)
        : [...p.student_ids, id],
    }))
  }

  async function handleCreate() {
    if (!form.full_name.trim()) return toast.error("Ism-familiyani kiriting")
    if (!form.phone.trim()) return toast.error("Telefon raqamini kiriting")
    if (form.student_ids.length === 0) return toast.error("Kamida bitta farzand (talaba) tanlang")
    if (form.password && form.password.length < 6) return toast.error("Parol kamida 6 belgi")
    setSaving(true)
    try {
      const res = await createParent({
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        username: form.username.trim() || null,
        password: form.password || null,
        student_ids: form.student_ids,
      })
      toast.success("Akkaunt yaratildi")
      setModal(false)
      setForm(EMPTY)
      setCreds({ full_name: res.full_name, username: res.username, password: res.generated_password })
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleToggle(p) {
    try {
      await updateParent(p.id, { is_active: !p.is_active })
      toast.success(p.is_active ? "Akkaunt bloklandi" : "Akkaunt faollashtirildi")
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
  }

  async function handleReset(p) {
    const ok = await ask({
      title: 'Parolni yangilash',
      message: `${p.full_name} uchun yangi parol yaratilsinmi?`,
      detail: 'Eski parol darhol ishlamay qoladi — yangi parol bir marta ko\'rsatiladi.',
      confirmLabel: 'Ha, yangilash',
    })
    if (!ok) return
    try {
      const res = await resetParentPassword(p.id)
      setCreds({ full_name: p.full_name, username: p.username, password: res.generated_password })
      toast.success("Yangi parol yaratildi")
    } catch (e) { toast.error(e.message) }
  }

  async function handleLink(studentId) {
    try {
      await linkParentChild(linkFor.id, studentId)
      toast.success("Farzand biriktirildi")
      setLinkFor(null)
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
  }

  async function handleUnlink(p, child) {
    const ok = await ask({
      title: 'Farzandni uzish',
      message: `${child.student_name} ushbu ota-onadan uzilsinmi?`,
      detail: "Ota-ona mobil ilovada bu farzandning ma'lumotlarini ko'ra olmaydi.",
      confirmLabel: 'Ha, uzish',
    })
    if (!ok) return
    try {
      await unlinkParentChild(p.id, child.student_id)
      toast.success("Uzildi")
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
  }

  function copy(text) {
    navigator.clipboard.writeText(text).then(
      () => toast.success("Nusxalandi"),
      () => toast.error("Nusxalab bo'lmadi"),
    )
  }

  const columns = [
    { key: 'full_name', header: 'Ota-ona', sortable: true, render: p => <PersonName name={p.full_name} /> },
    { key: 'phone', header: 'Telefon', sortable: true },
    {
      key: 'username', header: 'Login', sortable: true,
      render: p => (
        <span className="cell-copy">
          <code>{p.username}</code>
          <button className="btn-icon" title="Loginni nusxalash" aria-label="Loginni nusxalash" onClick={() => copy(p.username)}>
            <FontAwesomeIcon icon={faCopy} />
          </button>
        </span>
      ),
    },
    {
      key: 'children', header: 'Farzandlari', sortable: true,
      sortValue: p => p.children.length,
      render: p => p.children.length === 0
        ? <span className="text-muted">—</span>
        : (
          <div className="chip-row">
            {p.children.map(c => (
              <span key={c.student_id} className="ui-badge ui-badge-sm ui-badge-primary">
                {c.student_name}
                {canManage && (
                  <button className="chip-x" title="Uzish" aria-label="Uzish" onClick={() => handleUnlink(p, c)}>
                    <FontAwesomeIcon icon={faXmark} />
                  </button>
                )}
              </span>
            ))}
          </div>
        ),
    },
    {
      key: 'is_active', header: 'Holat', sortable: true,
      render: p => (
        <span className={`status-badge ${p.is_active ? 'active' : 'inactive'}`}>
          {p.is_active ? 'Faol' : 'Bloklangan'}
        </span>
      ),
    },
    ...(canManage ? [{
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: p => (
        <RowActions>
          <button className="btn-icon" title="Farzand biriktirish" aria-label="Farzand biriktirish" onClick={() => setLinkFor(p)}>
            <FontAwesomeIcon icon={faUserPlus} />
          </button>
          <button className="btn-icon" title="Parolni yangilash" aria-label="Parolni yangilash" onClick={() => handleReset(p)}>
            <FontAwesomeIcon icon={faKey} />
          </button>
          <button className="btn-icon" title={p.is_active ? 'Bloklash' : 'Faollashtirish'}
            aria-label={p.is_active ? 'Bloklash' : 'Faollashtirish'} onClick={() => handleToggle(p)}>
            <FontAwesomeIcon icon={p.is_active ? faToggleOn : faToggleOff} />
          </button>
        </RowActions>
      ),
    }] : []),
  ]

  return (
    <div className="page parents-studio">
      {confirmUI}
      <PageIntro title={<>Ota-onalar</>} description={<><FontAwesomeIcon icon={faMobileScreen} /> Mobil ilova akkauntlari — davomat, baho va to'lovlar.
            Parol faqat yaratilganda bir marta ko'rsatiladi.</>} actions={<><div className="header-actions">
          {isAdmin && (
            <button className="button secondary" onClick={() => { setBroadcastText(''); setBroadcastModal(true) }}>
              <FontAwesomeIcon icon={faPaperPlane} /> Telegram orqali xabar
            </button>
          )}
          {canManage && (
            <button className="button" onClick={() => { setForm(EMPTY); setModal(true) }}>
              <FontAwesomeIcon icon={faPlus} /> Akkaunt ochish
            </button>
          )}
        </div></>} />

      <SummaryRow items={[{ label: 'Ro‘yxatdagi ota-onalar', value: items.length }, { label: 'Faol akkauntlar', value: items.filter(p => p.is_active).length }, { label: 'Biriktirilgan farzandlar', value: items.reduce((n,p) => n + (p.children || []).length, 0) }]} />
      <div className="directory-toolbar"><ViewTabs value={parentView} onChange={setParentView} items={[{ key: 'families', label: 'Oilalar' }, { key: 'table', label: 'Jadval' }]} /><form onSubmit={handleSearch}><input className="field" value={search} onChange={e => setSearch(e.target.value)} placeholder="Ism yoki telefon bo‘yicha qidirish" aria-label="Ota-onani qidirish" /></form></div>
      {parentView === 'families' && !loading && items.length > 0 ? <div className="family-grid">{items.map(p => <article key={p.id} className="family-card"><header><Initials name={p.full_name} /><div><h2>{p.full_name}</h2><a href={'tel:' + p.phone}>{p.phone || 'Telefon kiritilmagan'}</a></div><span className={'family-status' + (p.is_active ? ' is-active' : '')}>{p.is_active ? 'Faol' : 'Bloklangan'}</span></header><div className="family-children"><span className="studio-eyebrow">Farzandlar</span>{p.children?.length ? p.children.map(c => <div key={c.student_id ?? c.id}><Initials name={c.full_name || c.student_name} /><span>{c.full_name || c.student_name}</span>{canManage && <button className="btn-icon danger" title="Farzandni ajratish" aria-label="Farzandni ajratish" onClick={() => handleUnlink(p, c)}><FontAwesomeIcon icon={faXmark} /></button>}</div>) : <p>Hali farzand biriktirilmagan</p>}</div>{canManage && <footer><button className="button secondary small" onClick={() => setLinkFor(p)}><FontAwesomeIcon icon={faUserPlus} /> Biriktirish</button><button className="btn-icon" title="Parolni yangilash" aria-label="Parolni yangilash" onClick={() => handleReset(p)}><FontAwesomeIcon icon={faKey} /></button><button className="btn-icon" title={p.is_active ? 'Bloklash' : 'Faollashtirish'} aria-label={p.is_active ? 'Bloklash' : 'Faollashtirish'} onClick={() => handleToggle(p)}><FontAwesomeIcon icon={p.is_active ? faToggleOn : faToggleOff} /></button></footer>}</article>)}</div> : <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        rowClassName={p => (!p.is_active ? 'row-inactive' : undefined)}
        clientPageSize={25}
        densityToggle densityKey="parents"
        empty={{
          icon: faPeopleRoof,
          title: search ? 'Hech narsa topilmadi' : "Ota-ona akkauntlari yo'q",
          description: search
            ? "Qidiruv so'zini o'zgartirib ko'ring."
            : 'Akkaunt ochilgach, ota-ona mobil ilovaga kira oladi.',
        }}
      />}

      {/* Yangi akkaunt modali */}
      {modal && (
        <Overlay className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faPeopleRoof} /> Ota-ona akkaunti ochish</h3>
              <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Ism-familiya *</label>
              <input className="field" value={form.full_name}
                onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
                placeholder="Muqumov Amon" />

              <label>Telefon *</label>
              <input className="field" value={form.phone}
                onChange={e => setForm(p => ({ ...p, phone: e.target.value }))}
                placeholder="+998901234567" />

              <div className="row-2">
                <div>
                  <label>Login</label>
                  <input className="field" value={form.username}
                    onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
                    placeholder="Bo'sh qolsa — telefon" />
                </div>
                <div>
                  <label>Parol</label>
                  <input className="field" value={form.password}
                    onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                    placeholder="Bo'sh qolsa — avto" />
                </div>
              </div>

              <label>Farzandlari (talabalar) *</label>
              <div style={{
                maxHeight: 180, overflowY: 'auto', border: '1px solid var(--border, var(--border))',
                borderRadius: 8, padding: '6px 10px',
              }}>
                {students.map(s => (
                  <label key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={form.student_ids.includes(s.id)}
                      onChange={() => toggleStudent(s.id)}
                    />
                    {s.full_name} <span className="text-muted" style={{ fontSize: 12 }}>({s.phone1})</span>
                  </label>
                ))}
                {students.length === 0 && <div className="muted py-2">Talabalar topilmadi</div>}
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(false)}>Bekor</button>
              <button className="button" onClick={handleCreate} disabled={saving}>
                {saving ? 'Yaratilmoqda...' : 'Yaratish'}
              </button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Login/parol modali — bir marta ko'rsatiladi */}
      {creds && (
        <Overlay className="modal-overlay" onClick={() => setCreds(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faKey} /> Kirish ma'lumotlari</h3>
              <button className="modal-close" onClick={() => setCreds(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 10px' }}>
                <strong>{creds.full_name}</strong> uchun mobil ilova kirish ma'lumotlari.
                Parol <strong>faqat hozir</strong> ko'rinadi — ota-onaga yozib bering yoki yuboring.
              </p>
              <label>Login</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input className="field" readOnly value={creds.username} style={{ fontFamily: 'monospace' }} />
                <button className="button secondary" onClick={() => copy(creds.username)}>
                  <FontAwesomeIcon icon={faCopy} />
                </button>
              </div>
              <label>Parol</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input className="field" readOnly value={creds.password || ''} style={{ fontFamily: 'monospace' }} />
                <button className="button secondary" onClick={() => copy(creds.password || '')}>
                  <FontAwesomeIcon icon={faCopy} />
                </button>
              </div>
              <button
                className="button secondary" style={{ marginTop: 10 }}
                onClick={() => copy(`Minar Academy ota-onalar ilovasi\nLogin: ${creds.username}\nParol: ${creds.password}`)}
              >
                <FontAwesomeIcon icon={faCopy} /> Hammasini nusxalash
              </button>
            </div>
            <div className="modal-footer">
              <button className="button" onClick={() => setCreds(null)}>Yopdim, saqlab oldim</button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Farzand biriktirish modali */}
      {linkFor && (
        <Overlay className="modal-overlay" onClick={() => setLinkFor(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faUserPlus} /> Farzand biriktirish</h3>
              <button className="modal-close" onClick={() => setLinkFor(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 10px' }}><strong>{linkFor.full_name}</strong> ga talaba biriktirish:</p>
              <div style={{ maxHeight: 260, overflowY: 'auto' }}>
                {students
                  .filter(s => !linkFor.children.some(c => c.student_id === s.id))
                  .map(s => (
                    <button
                      key={s.id} className="button secondary"
                      style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 6 }}
                      onClick={() => handleLink(s.id)}
                    >
                      {s.full_name} <span className="text-muted" style={{ fontSize: 12 }}>({s.phone1})</span>
                    </button>
                  ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setLinkFor(null)}>Yopish</button>
            </div>
          </div>
        </Overlay>
      )}

      {broadcastModal && (
        <Overlay className="modal-overlay" onClick={() => setBroadcastModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faPaperPlane} /> Barcha ota-onalarga xabar</h3>
              <button className="modal-close" onClick={() => setBroadcastModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
                Xabar Telegram orqali — talabaga bog'langan Telegram ID'si bor barcha ota-onalarga yuboriladi
                (mobil ilova akkountiga emas).
              </p>
              <label className="form-label">Xabar matni *</label>
              <textarea className="field" rows={5} value={broadcastText}
                onChange={e => setBroadcastText(e.target.value)}
                placeholder="Xabar matnini shu yerga yozing..." />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setBroadcastModal(false)}>Bekor</button>
              <button className="button" onClick={handleBroadcast} disabled={broadcasting}>
                {broadcasting ? 'Yuborilmoqda...' : 'Yuborish'}
              </button>
            </div>
          </div>
        </Overlay>
      )}
    </div>
  )
}
