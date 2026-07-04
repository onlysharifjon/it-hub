import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPen, faToggleOn, faToggleOff, faPlus,
  faMagnifyingGlass, faUserGraduate, faPhone,
  faBoxArchive, faArrowUpFromBracket, faCamera,
} from '@fortawesome/free-solid-svg-icons'
import { faTelegram as faTelegramBrand } from '@fortawesome/free-brands-svg-icons'
import { fetchStudents, createStudent, updateStudent, archiveStudent, unarchiveStudent, uploadStudentPhoto, API_BASE } from '../api'
import Pagination from './Pagination'
import DateFilter from './DateFilter'

const EMPTY = {
  full_name: '', phone1: '',
  father_name: '', father_phone: '',
  mother_name: '', mother_phone: '',
  telegram_id: '', notes: '',
}

function StudentAvatar({ photoUrl, size = 60 }) {
  if (!photoUrl) return (
    <div style={{ width: size, height: size, borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <FontAwesomeIcon icon={faUserGraduate} style={{ color: '#94a3b8', fontSize: size * 0.4 }} />
    </div>
  )
  return (
    <img
      src={`${API_BASE}${photoUrl}`}
      alt=""
      style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
    />
  )
}

export default function Students() {
  const [tab, setTab] = useState('active')          // 'active' | 'archived'
  const [data, setData] = useState({ items: [], meta: null })
  const [search, setSearch] = useState('')
  const [dateFilter, setDateFilter] = useState({ preset: 'all', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [editStudent, setEditStudent] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [photoUploading, setPhotoUploading] = useState(false)

  useEffect(() => { load(search, dateFilter, page, tab) }, [tab])

  async function load(s = search, df = dateFilter, p = page, t = tab) {
    setLoading(true)
    try {
      const res = await fetchStudents({
        search: s || undefined,
        is_archived: t === 'archived' ? true : false,
        date_from: df.date_from || undefined,
        date_to: df.date_to || undefined,
        page: p, page_size: 20,
      })
      setData(res)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function handleSearch(e) {
    const val = e.target.value
    setSearch(val)
    setPage(1)
    if (val.length === 0 || val.length >= 2) load(val, dateFilter, 1, tab)
  }

  function handleDateFilter(df) {
    setDateFilter(df)
    setPage(1)
    load(search, df, 1, tab)
  }

  function handlePageChange(p) {
    setPage(p)
    load(search, dateFilter, p, tab)
  }

  function switchTab(t) {
    setTab(t)
    setPage(1)
    setSearch('')
  }

  function openAdd() { setForm(EMPTY); setEditStudent(null); setModal('add') }
  function openEdit(s) {
    setForm({
      full_name: s.full_name, phone1: s.phone1,
      father_name: s.father_name || '', father_phone: s.father_phone || '',
      mother_name: s.mother_name || '', mother_phone: s.mother_phone || '',
      telegram_id: s.telegram_id || '', notes: s.notes || '',
    })
    setEditStudent(s)
    setModal(s)
  }

  async function handlePhotoUpload(file) {
    if (!editStudent?.id) return
    setPhotoUploading(true)
    try {
      const res = await uploadStudentPhoto(editStudent.id, file)
      setEditStudent(prev => ({ ...prev, photo_url: res.photo_url }))
      toast.success('Rasm yuklandi')
      load()
    } catch (e) { toast.error(e.message) }
    finally { setPhotoUploading(false) }
  }

  async function handleSave() {
    if (!form.full_name.trim() || !form.phone1.trim()) return toast.error("Ism va telefon majburiy")
    setSaving(true)
    try {
      if (modal === 'add') {
        await createStudent(form)
        toast.success("Talaba qo'shildi")
      } else {
        await updateStudent(modal.id, form)
        toast.success('Saqlandi')
      }
      setModal(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleArchive(s) {
    if (!confirm(`"${s.full_name}" ni arxivga o'tkazishni tasdiqlaysizmi?`)) return
    try {
      await archiveStudent(s.id)
      toast.success("Arxivga o'tkazildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleUnarchive(s) {
    try {
      await unarchiveStudent(s.id)
      toast.success("Arxivdan chiqarildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(s) {
    try {
      await updateStudent(s.id, { is_active: !s.is_active })
      load()
    } catch { toast.error('Xatolik') }
  }

  const students = data.items || []
  const meta = data.meta

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          <FontAwesomeIcon icon={faUserGraduate} className="page-icon" />
          Talabalar
        </h1>
        {tab === 'active' && (
          <button className="button primary" onClick={openAdd}>
            <FontAwesomeIcon icon={faPlus} /> Talaba qo'shish
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        <button
          className={`tab-btn ${tab === 'active' ? 'active' : ''}`}
          onClick={() => switchTab('active')}
        >
          <FontAwesomeIcon icon={faUserGraduate} /> Faol talabalar
        </button>
        <button
          className={`tab-btn ${tab === 'archived' ? 'active' : ''}`}
          onClick={() => switchTab('archived')}
        >
          <FontAwesomeIcon icon={faBoxArchive} /> Arxiv
        </button>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
          <input
            className="search-input"
            placeholder="Ism yoki telefon..."
            value={search}
            onChange={handleSearch}
          />
        </div>
        <span style={{ flex: 1 }} />
        <DateFilter value={dateFilter} onChange={handleDateFilter} />
        {meta && <span className="toolbar-count">Jami: <strong>{meta.total}</strong> ta talaba</span>}
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Ism Familiya</th>
                  <th><FontAwesomeIcon icon={faPhone} /> Telefon</th>
                  <th>Ota-ona</th>
                  <th>Telegram</th>
                  <th>Guruhlar</th>
                  <th>Holat</th>
                  <th>Amallar</th>
                </tr>
              </thead>
              <tbody>
                {students.map((s, i) => (
                  <tr key={s.id} className={!s.is_active ? 'row-inactive' : ''}>
                    <td className="text-muted">{(page - 1) * 20 + i + 1}</td>
                    <td><strong>{s.full_name}</strong></td>
                    <td>
                      <div>{s.phone1}</div>
                    </td>
                    <td>
                      {(s.father_name || s.mother_name) ? (
                        <div style={{ fontSize: 12 }}>
                          {s.father_name && <div>{s.father_name}{s.father_phone ? ` — ${s.father_phone}` : ''}</div>}
                          {s.mother_name && <div>{s.mother_name}{s.mother_phone ? ` — ${s.mother_phone}` : ''}</div>}
                        </div>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      {s.telegram_id
                        ? <span className="tg-badge"><FontAwesomeIcon icon={faTelegramBrand} /> {s.telegram_id}</span>
                        : <span className="text-muted">—</span>}
                    </td>
                    <td><span className="badge">{s.group_count || 0}</span></td>
                    <td>
                      <span className={`status-badge ${s.is_active ? 'active' : 'inactive'}`}>
                        {s.is_active ? 'Faol' : 'Nofaol'}
                      </span>
                    </td>
                    <td className="actions">
                      {tab === 'active' ? (
                        <>
                          <button className="btn-icon" onClick={() => openEdit(s)} title="Tahrirlash">
                            <FontAwesomeIcon icon={faPen} />
                          </button>
                          <button className="btn-icon" onClick={() => handleToggle(s)} title={s.is_active ? "Nofaollashtirish" : "Faollashtirish"}>
                            <FontAwesomeIcon icon={s.is_active ? faToggleOn : faToggleOff} style={{ color: s.is_active ? '#22c55e' : '#ef4444' }} />
                          </button>
                          <button className="btn-icon danger" onClick={() => handleArchive(s)} title="Arxivga o'tkazish">
                            <FontAwesomeIcon icon={faBoxArchive} />
                          </button>
                        </>
                      ) : (
                        <button className="btn-icon" onClick={() => handleUnarchive(s)} title="Arxivdan chiqarish" style={{ color: '#2563eb' }}>
                          <FontAwesomeIcon icon={faArrowUpFromBracket} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {students.length === 0 && (
                  <tr>
                    <td colSpan={8} className="muted center py-4">
                      {tab === 'archived' ? 'Arxivlangan talabalar yo\'q' : 'Talabalar topilmadi'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <Pagination meta={meta} onPageChange={handlePageChange} />
        </>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal === 'add' ? "Yangi talaba" : "Talabani tahrirlash"}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              {modal !== 'add' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                  <StudentAvatar photoUrl={editStudent?.photo_url} size={72} />
                  <div>
                    <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 6 }}>
                      Kamera tizimi uchun yuz rasmi
                    </div>
                    <label className="button secondary" style={{ cursor: 'pointer', fontSize: 13 }}>
                      <FontAwesomeIcon icon={faCamera} style={{ marginRight: 6 }} />
                      {photoUploading ? 'Yuklanmoqda...' : 'Rasm yuklash'}
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        style={{ display: 'none' }}
                        disabled={photoUploading}
                        onChange={e => e.target.files[0] && handlePhotoUpload(e.target.files[0])}
                      />
                    </label>
                  </div>
                </div>
              )}
              <label>Ism Familiya *</label>
              <input className="field" value={form.full_name} onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))} placeholder="To'liq ism" />
              <label><FontAwesomeIcon icon={faPhone} /> Telefon *</label>
              <input className="field" value={form.phone1} onChange={e => setForm(p => ({ ...p, phone1: e.target.value }))} placeholder="+998901234567" />
              <div className="row-2">
                <div>
                  <label>Otasining ismi</label>
                  <input className="field" value={form.father_name} onChange={e => setForm(p => ({ ...p, father_name: e.target.value }))} placeholder="Ixtiyoriy" />
                </div>
                <div>
                  <label>Otasining telefoni</label>
                  <input className="field" value={form.father_phone} onChange={e => setForm(p => ({ ...p, father_phone: e.target.value }))} placeholder="+998..." />
                </div>
              </div>
              <div className="row-2">
                <div>
                  <label>Onasining ismi</label>
                  <input className="field" value={form.mother_name} onChange={e => setForm(p => ({ ...p, mother_name: e.target.value }))} placeholder="Ixtiyoriy" />
                </div>
                <div>
                  <label>Onasining telefoni</label>
                  <input className="field" value={form.mother_phone} onChange={e => setForm(p => ({ ...p, mother_phone: e.target.value }))} placeholder="+998..." />
                </div>
              </div>
              <label>Telegram ID</label>
              <input className="field" value={form.telegram_id} onChange={e => setForm(p => ({ ...p, telegram_id: e.target.value }))} placeholder="username (@ siz)" />
              <label>Izoh</label>
              <textarea className="field" rows={2} value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Qo'shimcha ma'lumot..." />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(null)}>Bekor</button>
              <button className="button primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
