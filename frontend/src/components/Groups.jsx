import { PageIntro, Initials, ViewTabs } from './ui/Workspace'
import Overlay from './ui/Overlay'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPlus, faPen, faUsers, faUserPlus, faUserMinus,
  faBoxArchive, faBoxOpen, faArrowRight, faClock, faBookOpen,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchGroups, createGroup, updateGroup,
  getGroup, addStudentToGroup, removeStudentFromGroup,
  fetchStudents, fetchTeachers, fetchTariffs,
} from '../api'
import useConfirm from './ui/useConfirm'
import DateFilter from './DateFilter'
import Pagination from './Pagination'
import { STAGE_COLORS, STAGE_LABELS, STAGE_OPTIONS } from '../constants/domain'

const EMPTY_GROUP = { name: '', stage: 'foundation', teacher_id: '', tariff_id: '', course_price: '', schedule: '', lesson_time: '', start_date: '', telegram_chat_id: '' }


export default function Groups({ onOpenGroup }) {
  const [confirmUI, ask] = useConfirm()
  const [data, setData] = useState({ items: [], meta: null })
  const [dateFilter, setDateFilter] = useState({ preset: 'all', date_from: '', date_to: '' })
  const [statusFilter, setStatusFilter] = useState('active')   // active | archived | all
  const [dayFilter, setDayFilter] = useState('all')   // all | Juft kunlar | Toq kunlar
  const [page, setPage] = useState(1)
  const [teachers, setTeachers] = useState([])
  const [allStudents, setAllStudents] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY_GROUP)
  const [saving, setSaving] = useState(false)
  const [detailGroup, setDetailGroup] = useState(null)
  const [addStudentId, setAddStudentId] = useState('')
  const [addTariffId, setAddTariffId] = useState('')
  const [tariffs, setTariffs] = useState([])

  useEffect(() => {
    load(dateFilter, page)
    fetchTeachers().then(r => setTeachers(r || [])).catch(() => setTeachers([]))
    fetchStudents({ is_active: true, page_size: 100 }).then(r => setAllStudents(r.items || []))
    fetchTariffs().then(r => setTariffs(r || []))
  }, [])

  async function load(df = dateFilter, p = page, sf = statusFilter, dyf = dayFilter) {
    setLoading(true)
    try {
      const res = await fetchGroups({
        is_active: sf === 'all' ? undefined : sf === 'active',
        schedule: dyf === 'all' ? undefined : dyf,
        date_from: df.date_from || undefined,
        date_to: df.date_to || undefined,
        page: p, page_size: 20,
      })
      setData(res)
    }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function handleDateFilter(df) {
    setDateFilter(df)
    setPage(1)
    load(df, 1)
  }

  function handleStatusFilter(sf) {
    setStatusFilter(sf)
    setPage(1)
    load(dateFilter, 1, sf)
  }

  function handleDayFilter(dyf) {
    setDayFilter(dyf)
    setPage(1)
    load(dateFilter, 1, statusFilter, dyf)
  }

  function handlePageChange(p) {
    setPage(p)
    load(dateFilter, p)
  }

  async function loadDetail(id) {
    const g = await getGroup(id)
    setDetailGroup(g)
  }

  function openAdd() {
    // Default tanlov — "Pro" tarifi (bo'lsa), narxi avtomatik to'ladi
    const pro = tariffs.find(t => t.is_active && t.name.toLowerCase() === 'pro')
    setForm({ ...EMPTY_GROUP, tariff_id: pro ? String(pro.id) : '', course_price: pro ? pro.price : '' })
    setModal('add')
  }
  function openEdit(g) {
    // Mavjud narxga mos tarifni topamiz (bo'lsa) — tanlangan holda ko'rsatish uchun
    const matched = tariffs.find(t => Number(t.price) === Number(g.course_price))
    setForm({
      name: g.name, stage: g.stage || 'foundation',
      teacher_id: g.teacher_id || '',
      tariff_id: matched ? String(matched.id) : '',
      course_price: g.course_price,
      schedule: g.schedule || '',
      lesson_time: g.lesson_time || '',
      start_date: g.start_date ? g.start_date.slice(0, 10) : '',
      telegram_chat_id: g.telegram_chat_id || '',
    })
    setModal(g)
  }

  async function handleSave() {
    if (!form.name.trim()) return toast.error("Guruh nomi majburiy")
    if (!form.tariff_id) return toast.error("Iltimos tarif tanlang")
    setSaving(true)
    const payload = {
      name: form.name,
      stage: form.stage || 'foundation',
      teacher_id: form.teacher_id ? parseInt(form.teacher_id) : null,
      // Narx tarifdan avtomatik keladi — qo'lda kiritilmaydi
      course_price: parseFloat(form.course_price) || 0,
      schedule: form.schedule || null,
      lesson_time: form.lesson_time || null,
      start_date: form.start_date ? new Date(form.start_date).toISOString() : null,
      telegram_chat_id: form.telegram_chat_id.trim() || null,
    }
    try {
      if (modal === 'add') {
        await createGroup(payload)
        toast.success("Guruh qo'shildi")
      } else {
        await updateGroup(modal.id, payload)
        toast.success('Saqlandi')
      }
      setModal(null)
      load(dateFilter, page)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleToggle(g) {
    if (g.is_active) {
      const ok = await ask({
        title: 'Guruhni arxivlash',
        message: `"${g.name}" guruhi arxivga olinsinmi?`,
        detail: "Arxivdagi guruh moliya, maosh va qarzdorlik hisobotlarida ko'rinmaydi. Keyin qaytarish mumkin.",
        confirmLabel: 'Ha, arxivlash',
      })
      if (!ok) return
    }
    try {
      await updateGroup(g.id, { is_active: !g.is_active })
      toast.success(g.is_active ? 'Guruh arxivga olindi' : 'Guruh arxivdan chiqarildi')
      load(dateFilter, page)
    } catch { toast.error('Xatolik') }
  }

  async function handleAddStudent() {
    if (!addStudentId) return
    if (!addTariffId) return toast.error("Iltimos tarif tanlang")
    try {
      await addStudentToGroup(detailGroup.id, parseInt(addStudentId), parseInt(addTariffId))
      await loadDetail(detailGroup.id)
      setAddStudentId('')
      setAddTariffId('')
      toast.success("Talaba qo'shildi")
    } catch (e) { toast.error(e.message) }
  }

  async function handleRemoveStudent(studentId) {
    try {
      await removeStudentFromGroup(detailGroup.id, studentId)
      await loadDetail(detailGroup.id)
      toast.success("Talaba chiqarildi")
    } catch (e) { toast.error(e.message) }
  }

  const membersInDetail = detailGroup?.members?.map(m => m.student_id) || []
  const availableStudents = allStudents.filter(s => !membersInDetail.includes(s.id))

  return (
    <div className="page groups-studio">
      {confirmUI}
      <PageIntro title="Guruhlar" eyebrow="Ta’lim jarayoni" description="Guruhlar, jadval va o‘quv dasturi bir joyda." actions={<button className="button" onClick={openAdd}><FontAwesomeIcon icon={faPlus} /> Guruh yaratish</button>} />
      <ViewTabs value={statusFilter} onChange={handleStatusFilter} items={[{ key: 'active', label: 'Faol guruhlar' }, { key: 'archived', label: 'Arxiv' }, { key: 'all', label: 'Barcha guruhlar' }]} />
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Kun bo'yicha filtr">
          {[['all', 'Barchasi'], ['Juft kunlar', 'Juft'], ['Toq kunlar', 'Toq']].map(([val, label]) => (
            <button key={val} className={dayFilter === val ? 'active' : ''}
              onClick={() => handleDayFilter(val)}>
              {label}
            </button>
          ))}
        </div>
        <DateFilter value={dateFilter} onChange={handleDateFilter} />
        {data.meta && <span className="table-count">Jami: <strong>{data.meta.total}</strong> ta guruh</span>}
      </div>

      {loading ? <div className="muted center">Yuklanmoqda...</div> : (
        <>
          <div className="cohort-list">
            <div className="cohort-list-labels"><span>Guruh / o‘qituvchi</span><span>Dars jadvali</span><span>O‘quv jarayoni</span><span>Guruh boshqaruvi</span></div>
            {(data.items || []).map((g, i) => <article key={g.id} className={'cohort-row' + (!g.is_active ? ' is-archived' : '')}>
              <button className="cohort-identity" onClick={() => onOpenGroup(g)} aria-label={g.name + ' guruhini ochish'}><span className={'cohort-symbol tone-' + (i % 3)}><FontAwesomeIcon icon={faBookOpen} /></span><span><small>{g.course_name || STAGE_LABELS[g.stage || 'foundation']}</small><strong>{g.name}</strong><span><Initials name={g.teacher_name} />{g.teacher_name || 'Ustoz biriktirilmagan'}</span></span></button>
              <div className="cohort-schedule"><strong><FontAwesomeIcon icon={faClock} />{g.lesson_time || 'Vaqt belgilanmagan'}</strong><span>{g.schedule || 'Jadval belgilanmagan'}</span><small>{g.student_count} ta talaba · {Number(g.course_price).toLocaleString()} so‘m / oy</small></div>
              <div className="cohort-progress"><div><span>{g.completed_lessons}/{g.total_lessons} dars</span><strong>{g.progress_pct}%</strong></div><div className="cohort-track"><i style={{ width: Math.min(100, Math.max(0, Number(g.progress_pct) || 0)) + '%' }} /></div><small>{g.remaining_lessons > 0 ? g.remaining_lessons + ' ta dars qoldi' : 'Kurs yakunlangan'}</small></div>
              <div className="cohort-actions"><button className="button secondary small" onClick={() => loadDetail(g.id)}><FontAwesomeIcon icon={faUsers} /> Talabalar</button><div><button className="btn-icon" aria-label={g.name + ' guruhini tahrirlash'} title="Tahrirlash" onClick={() => openEdit(g)}><FontAwesomeIcon icon={faPen} /></button><button className="btn-icon" aria-label={g.is_active ? 'Arxivlash' : 'Arxivdan chiqarish'} title={g.is_active ? 'Arxivlash' : 'Arxivdan chiqarish'} onClick={() => handleToggle(g)}><FontAwesomeIcon icon={g.is_active ? faBoxArchive : faBoxOpen} /></button><button className="btn-icon" aria-label={g.name + ' tafsilotlari'} title="Guruhni ochish" onClick={() => onOpenGroup(g)}><FontAwesomeIcon icon={faArrowRight} /></button></div></div>
            </article>)}
            {(data.items || []).length === 0 && <div className="cohort-empty"><FontAwesomeIcon icon={faUsers} /><h3>Guruhlar topilmadi</h3><p>Filtrlarni o‘zgartiring yoki yangi guruh yarating.</p></div>}
          </div>
          <Pagination meta={data.meta} onPageChange={handlePageChange} />
        </>
      )}

      {/* Group form modal */}
      {modal && (
        <Overlay className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal === 'add' ? 'Yangi guruh' : 'Guruhni tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Guruh nomi *</label>
              <input className="field" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Masalan: Python 1-guruh" />
              <label>Daraja</label>
              <select className="field" value={form.stage || 'foundation'} onChange={e => setForm(p => ({ ...p, stage: e.target.value }))}>
                {STAGE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <label>Ustoz</label>
              <select className="field" value={form.teacher_id} onChange={e => setForm(p => ({ ...p, teacher_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {teachers.map(t => <option key={t.id} value={t.id}>{t.full_name || t.username}</option>)}
              </select>
              <label>Tarif *</label>
              <select
                className="field"
                value={form.tariff_id}
                onChange={e => {
                  const tid = e.target.value
                  const t = tariffs.find(x => String(x.id) === tid)
                  setForm(p => ({ ...p, tariff_id: tid, course_price: t ? t.price : '' }))
                }}
              >
                <option value="">— Tarif tanlang —</option>
                {tariffs.filter(t => t.is_active).map(t => (
                  <option key={t.id} value={t.id}>{t.name} — {Number(t.price).toLocaleString()} so'm</option>
                ))}
              </select>
              {form.course_price !== '' && form.course_price != null && (
                <p className="text-muted" style={{ fontSize: 13, margin: '4px 0 0' }}>
                  Narx: <strong>{Number(form.course_price).toLocaleString()} so'm/oy</strong>
                </p>
              )}
              <div className="row-2">
                <div>
                  <label>Dars jadvali</label>
                  <select className="field" value={form.schedule} onChange={e => setForm(p => ({ ...p, schedule: e.target.value }))}>
                    <option value="">— Tanlang —</option>
                    <option value="Juft kunlar">Juft kunlar</option>
                    <option value="Toq kunlar">Toq kunlar</option>
                  </select>
                </div>
                <div>
                  <label>Dars vaqti (soat)</label>
                  <input className="field" type="time" lang="uz-UZ" value={form.lesson_time} onChange={e => setForm(p => ({ ...p, lesson_time: e.target.value }))} />
                </div>
              </div>
              <label>Boshlanish sanasi</label>
              <input className="field" type="date" value={form.start_date} onChange={e => setForm(p => ({ ...p, start_date: e.target.value }))} />
              <label>Telegram chat ID (uy vazifasi uchun)</label>
              <input className="field" value={form.telegram_chat_id} onChange={e => setForm(p => ({ ...p, telegram_chat_id: e.target.value }))} placeholder="-1001234567890" />
              <p className="text-muted" style={{ fontSize: 12, margin: '4px 0 0' }}>
                Botni guruhga qo'shib, guruh chat ID'sini shu yerga kiriting — uy vazifalari avtomatik yuboriladi.
              </p>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(null)}>Bekor</button>
              <button className="button" onClick={handleSave} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Detail modal */}
      {detailGroup && (
        <Overlay className="modal-overlay" onClick={() => setDetailGroup(null)}>
          <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>👥 {detailGroup.name} — O'quvchilar</h3>
              <button className="modal-close" onClick={() => setDetailGroup(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="add-student-row" style={{ flexWrap: 'wrap', gap: 8 }}>
                <select className="field flex-1" value={addStudentId} onChange={e => setAddStudentId(e.target.value)} style={{ minWidth: 180 }}>
                  <option value="">— Talaba tanlang —</option>
                  {availableStudents.map(s => (
                    <option key={s.id} value={s.id}>{s.full_name} ({s.phone1})</option>
                  ))}
                </select>
                <select className="field" value={addTariffId} onChange={e => setAddTariffId(e.target.value)} style={{ minWidth: 160 }}>
                  <option value="">— Tarif tanlang —</option>
                  {tariffs.filter(t => t.is_active).map(t => (
                    <option key={t.id} value={t.id}>{t.name} — {Number(t.price).toLocaleString()} so'm</option>
                  ))}
                </select>
                <button className="button" onClick={handleAddStudent}>
                  <FontAwesomeIcon icon={faUserPlus} /> Qo'shish
                </button>
              </div>
              <table className="data-table mt-1">
                <thead>
                  <tr><th>#</th><th>Ism</th><th>Telefon</th><th>Tarif</th><th>Qo'shilgan</th><th></th></tr>
                </thead>
                <tbody>
                  {(detailGroup.members || []).map((m, i) => (
                    <tr key={m.id}>
                      <td>{i + 1}</td>
                      <td>{m.student_name}</td>
                      <td>{m.student_phone}</td>
                      <td>
                        {m.tariff_name
                          ? <span>{m.tariff_name} <span className="text-muted" style={{ fontSize: 11 }}>({Number(m.tariff_price).toLocaleString()} so'm)</span></span>
                          : <span className="text-muted">—</span>}
                      </td>
                      <td>{new Date(m.joined_at).toLocaleDateString('uz')}</td>
                      <td><button className="btn-icon danger" onClick={() => handleRemoveStudent(m.student_id)} title="Chiqarish"><FontAwesomeIcon icon={faUserMinus} /></button></td>
                    </tr>
                  ))}
                  {(detailGroup.members || []).length === 0 && (
                    <tr><td colSpan={5} className="muted center">Hali o'quvchi yo'q</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </Overlay>
      )}
    </div>
  )
}
