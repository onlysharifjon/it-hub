import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft, faUserGraduate, faPhone, faCamera, faFloppyDisk,
  faClockRotateLeft, faArrowRightToBracket, faArrowRightFromBracket,
  faUmbrellaBeach, faTrash, faPlus, faBoxArchive, faArrowUpFromBracket,
  faToggleOn, faToggleOff, faHourglassHalf, faLayerGroup, faRotateLeft,
  faWallet, faIdCard, faVideo, faSliders, faLink, faReceipt,
  faPaperPlane, faSpinner,
} from '@fortawesome/free-solid-svg-icons'
import {
  getStudent, updateStudent, uploadStudentPhoto, archiveStudent, unarchiveStudent,
  fetchStudentCameraAttendance, fetchStudentPaymentSummary,
  fetchStudentVacations, createStudentVacation, deleteStudentVacation,
  fetchGroups, addStudentToGroup, checkStudentTelegram, API_BASE,
} from '../api'

const fmtSum = n => Number(n || 0).toLocaleString('uz-UZ')
const VAC_TODAY = new Date().toISOString().slice(0, 10)

export default function StudentDetail({ student: studentProp, onBack, currentUser, onChanged }) {
  const isHunter = currentUser?.role === 'hunter' || currentUser?.role === 'admin'
  const [s, setS] = useState(studentProp)
  const [form, setForm] = useState(() => toForm(studentProp))
  const [saving, setSaving] = useState(false)
  const [photoUploading, setPhotoUploading] = useState(false)

  const [mainTab, setMainTab] = useState('info')   // 'info' | 'payment' | 'attendance' | 'vacation'

  const [attendanceDays, setAttendanceDays] = useState(30)
  const [attendanceData, setAttendanceData] = useState([])
  const [attendanceLoading, setAttendanceLoading] = useState(false)
  const [attendanceLoaded, setAttendanceLoaded] = useState(false)

  const [pay, setPay] = useState(null)
  const [payLoading, setPayLoading] = useState(false)
  const [payLoaded, setPayLoaded] = useState(false)

  const [vacations, setVacations] = useState([])
  const [vacForm, setVacForm] = useState({ start_date: VAC_TODAY, end_date: VAC_TODAY, reason: '' })
  const [vacSaving, setVacSaving] = useState(false)
  const [vacLoaded, setVacLoaded] = useState(false)

  const [groups, setGroups] = useState([])
  const [attachGroupId, setAttachGroupId] = useState('')
  const [attaching, setAttaching] = useState(false)

  const [tgCheck, setTgCheck] = useState(null)   // null | 'checking' | 'ok' | 'fail'

  function toForm(st) {
    return {
      full_name: st.full_name || '', phone1: st.phone1 || '',
      father_name: st.father_name || '', father_phone: st.father_phone || '',
      mother_name: st.mother_name || '', mother_phone: st.mother_phone || '',
      telegram_user_id: st.telegram_user_id || '', notes: st.notes || '',
    }
  }

  useEffect(() => { refresh() }, [studentProp.id])
  useEffect(() => { if (s.is_demo) loadGroups() }, [s.is_demo])

  useEffect(() => {
    if (mainTab === 'payment' && !payLoaded) loadPay()
    if (mainTab === 'attendance' && !attendanceLoaded) loadAttendance(attendanceDays)
    if (mainTab === 'vacation' && isHunter && !vacLoaded) loadVacations()
  }, [mainTab])

  async function refresh() {
    try {
      const fresh = await getStudent(studentProp.id)
      setS(fresh)
      setForm(toForm(fresh))
      onChanged?.(fresh)
    } catch { toast.error("Ma'lumot yuklanmadi") }
  }

  async function loadAttendance(days) {
    setAttendanceLoading(true)
    try { setAttendanceData(await fetchStudentCameraAttendance(studentProp.id, days)) }
    catch { setAttendanceData([]) } finally { setAttendanceLoading(false); setAttendanceLoaded(true) }
  }

  async function loadPay() {
    setPayLoading(true)
    try { setPay(await fetchStudentPaymentSummary(studentProp.id)) }
    catch { setPay(null) } finally { setPayLoading(false); setPayLoaded(true) }
  }

  async function loadVacations() {
    try { setVacations(await fetchStudentVacations(studentProp.id)) } catch {} finally { setVacLoaded(true) }
  }

  async function loadGroups() {
    try {
      const res = await fetchGroups({ is_active: true, page_size: 100 })
      setGroups(res.items || res || [])
    } catch {}
  }

  async function handleSave() {
    if (!form.full_name.trim() || !form.phone1.trim()) return toast.error('Ism va telefon majburiy')
    setSaving(true)
    try {
      const updated = await updateStudent(s.id, form)
      setS(updated)
      onChanged?.(updated)
      toast.success('Saqlandi')
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  async function handlePhotoUpload(file) {
    setPhotoUploading(true)
    try {
      const res = await uploadStudentPhoto(s.id, file)
      setS(prev => ({ ...prev, photo_url: res.photo_url }))
      toast.success('Rasm yuklandi')
    } catch (e) { toast.error(e.message) } finally { setPhotoUploading(false) }
  }

  async function handleToggleActive() {
    try {
      const updated = await updateStudent(s.id, { is_active: !s.is_active })
      setS(updated)
      onChanged?.(updated)
    } catch { toast.error('Xatolik') }
  }

  async function handleArchiveToggle() {
    try {
      const updated = s.is_archived
        ? await unarchiveStudent(s.id)
        : (confirm(`"${s.full_name}" ni arxivga o'tkazishni tasdiqlaysizmi?`) ? await archiveStudent(s.id) : null)
      if (updated) { setS(updated); onChanged?.(updated); toast.success(s.is_archived ? "Arxivdan chiqarildi" : "Arxivga o'tkazildi") }
    } catch (e) { toast.error(e.message) }
  }

  async function handleDemoToggle() {
    try {
      const updated = await updateStudent(s.id, { is_demo: !s.is_demo })
      setS(updated)
      onChanged?.(updated)
      toast.success(updated.is_demo ? "Demo bo'limiga o'tkazildi" : "Demo holatidan chiqarildi")
    } catch (e) { toast.error(e.message) }
  }

  async function handleAttach() {
    if (!attachGroupId) return toast.error('Guruhni tanlang')
    setAttaching(true)
    try {
      await addStudentToGroup(parseInt(attachGroupId), s.id)
      toast.success("Guruhga biriktirildi — endi haqiqiy talaba")
      setAttachGroupId('')
      await refresh()
    } catch (e) { toast.error(e.message) } finally { setAttaching(false) }
  }

  async function handleTelegramCheck() {
    setTgCheck('checking')
    try {
      const res = await checkStudentTelegram(s.id)
      setTgCheck(res.ok ? 'ok' : 'fail')
      if (res.ok) toast.success("Sinov xabari yuborildi — yetkazish mumkin")
      else toast.error(res.detail || 'Xabar yuborib bo\'lmadi')
    } catch (e) { setTgCheck('fail'); toast.error(e.message) }
  }

  async function handleVacSave() {
    if (!vacForm.start_date || !vacForm.end_date) return toast.error('Sanalarni kiriting')
    if (vacForm.end_date < vacForm.start_date) return toast.error("Tugash sanasi boshlanishdan oldin bo'lmasin")
    setVacSaving(true)
    try {
      await createStudentVacation(s.id, {
        start_date: vacForm.start_date, end_date: vacForm.end_date, reason: vacForm.reason.trim() || null,
      })
      toast.success("Ta'til belgilandi")
      setVacForm({ start_date: VAC_TODAY, end_date: VAC_TODAY, reason: '' })
      await loadVacations()
    } catch (e) { toast.error(e.message) } finally { setVacSaving(false) }
  }

  async function handleVacDelete(id) {
    if (!confirm("Bu ta'til yozuvini o'chirishni tasdiqlaysizmi?")) return
    try { await deleteStudentVacation(s.id, id); toast.success("O'chirildi"); await loadVacations() }
    catch (e) { toast.error(e.message) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <button className="btn-sm" onClick={onBack}>
            <FontAwesomeIcon icon={faArrowLeft} /> Orqaga
          </button>
          <h1 style={{ margin: 0 }}>
            <FontAwesomeIcon icon={faUserGraduate} className="page-icon" />
            {s.full_name}
          </h1>
          {s.is_demo
            ? <span className="status-badge inactive" style={{ background: '#fef3c7', color: '#b45309' }}>Demo darsga kelmagan</span>
            : <span className={`status-badge ${s.is_active ? 'active' : 'inactive'}`}>{s.is_active ? 'Faol' : 'Nofaol'}</span>}
          {s.is_archived && <span className="status-badge inactive">Arxivda</span>}
        </div>
      </div>

      <div className="group-detail-layout">
        {/* ── Chap panel: profil, aloqa, guruhlar, tezkor amallar ── */}
        <div className="group-detail-sidebar">
          <div className="info-card" style={{ textAlign: 'center' }}>
            <StudentAvatar photoUrl={s.photo_url} size={92} />
            <div style={{ fontWeight: 700, fontSize: 15, marginTop: 10 }}>{s.full_name}</div>
            <div className="text-muted" style={{ fontSize: 12.5, marginBottom: 10 }}>
              <FontAwesomeIcon icon={faPhone} /> {s.phone1}
            </div>
            <label className="button secondary" style={{ cursor: 'pointer', fontSize: 12.5, display: 'inline-flex' }}>
              <FontAwesomeIcon icon={faCamera} style={{ marginRight: 6 }} />
              {photoUploading ? 'Yuklanmoqda...' : 'Rasm yuklash'}
              <input type="file" accept="image/jpeg,image/png,image/webp" style={{ display: 'none' }}
                disabled={photoUploading} onChange={e => e.target.files[0] && handlePhotoUpload(e.target.files[0])} />
            </label>
          </div>

          <div className="info-card">
            <div className="info-card-title"><FontAwesomeIcon icon={faPhone} /> Aloqa</div>
            {s.father_name && <div className="stat-row"><span>Ota</span><strong>{s.father_name}{s.father_phone ? ` · ${s.father_phone}` : ''}</strong></div>}
            {s.mother_name && <div className="stat-row"><span>Ona</span><strong>{s.mother_name}{s.mother_phone ? ` · ${s.mother_phone}` : ''}</strong></div>}
            {s.telegram_user_id && (
              <div className="stat-row">
                <span>Telegram ID</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <strong style={{ color: tgCheck === 'fail' ? '#b45309' : undefined }}>{s.telegram_user_id}</strong>
                  <button
                    className="btn-icon"
                    title="Yetkazishni sinab ko'rish (sinov xabari yuboradi)"
                    style={{ padding: 4 }}
                    disabled={tgCheck === 'checking'}
                    onClick={handleTelegramCheck}
                  >
                    <FontAwesomeIcon icon={tgCheck === 'checking' ? faSpinner : faPaperPlane} spin={tgCheck === 'checking'} style={{ fontSize: 11 }} />
                  </button>
                </span>
              </div>
            )}
            {!s.father_name && !s.mother_name && !s.telegram_user_id && (
              <span className="text-muted">Qo'shimcha aloqa ma'lumoti yo'q</span>
            )}
          </div>

          <div className="info-card">
            <div className="info-card-title"><FontAwesomeIcon icon={faLayerGroup} /> Guruhlar</div>
            {(s.group_names && s.group_names.length > 0)
              ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {s.group_names.map((n, i) => <span key={i} className="badge">{n}</span>)}
                </div>
              : <span className="text-muted">Hech qaysi guruhda emas</span>}
          </div>

          {s.is_demo && (
            <div className="info-card">
              <div className="info-card-title"><FontAwesomeIcon icon={faLink} /> Guruhga biriktirish</div>
              <p className="text-muted" style={{ fontSize: 12, marginTop: 0 }}>
                Guruh tanlansa, talaba avtomatik "Faol talabalar"ga o'tadi.
              </p>
              <select className="field" value={attachGroupId} onChange={e => setAttachGroupId(e.target.value)}>
                <option value="">— guruh tanlang —</option>
                {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
              <button className="button primary" style={{ marginTop: 8, width: '100%' }} onClick={handleAttach} disabled={attaching}>
                {attaching ? 'Saqlanmoqda...' : 'Biriktirish'}
              </button>
            </div>
          )}

          <div className="info-card">
            <div className="info-card-title"><FontAwesomeIcon icon={faSliders} /> Tezkor amallar</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <button className="button secondary" onClick={handleDemoToggle}>
                <FontAwesomeIcon icon={s.is_demo ? faRotateLeft : faHourglassHalf} />
                {' '}{s.is_demo ? 'Demo holatidan chiqarish' : "Demo bo'limiga o'tkazish"}
              </button>
              {!s.is_demo && (
                <button className="button secondary" onClick={handleToggleActive}>
                  <FontAwesomeIcon icon={s.is_active ? faToggleOff : faToggleOn} />
                  {' '}{s.is_active ? 'Nofaollashtirish' : 'Faollashtirish'}
                </button>
              )}
              <button className="button secondary" onClick={handleArchiveToggle}>
                <FontAwesomeIcon icon={s.is_archived ? faArrowUpFromBracket : faBoxArchive} />
                {' '}{s.is_archived ? "Arxivdan chiqarish" : "Arxivga o'tkazish"}
              </button>
            </div>
          </div>
        </div>

        {/* ── O'ng panel: tab bilan ma'lumot / to'lov / davomat / ta'til ── */}
        <div className="group-detail-main">
          <div className="tab-bar" style={{ marginBottom: '1rem' }}>
            <button className={`tab-btn ${mainTab === 'info' ? 'active' : ''}`} onClick={() => setMainTab('info')}>
              <FontAwesomeIcon icon={faIdCard} /> Ma'lumotlar
            </button>
            <button className={`tab-btn ${mainTab === 'payment' ? 'active' : ''}`} onClick={() => setMainTab('payment')}>
              <FontAwesomeIcon icon={faWallet} /> To'lov
            </button>
            <button className={`tab-btn ${mainTab === 'attendance' ? 'active' : ''}`} onClick={() => setMainTab('attendance')}>
              <FontAwesomeIcon icon={faVideo} /> Davomat
            </button>
            {isHunter && (
              <button className={`tab-btn ${mainTab === 'vacation' ? 'active' : ''}`} onClick={() => setMainTab('vacation')}>
                <FontAwesomeIcon icon={faUmbrellaBeach} /> Ta'til
              </button>
            )}
          </div>

          {mainTab === 'info' && (
            <div className="info-card">
              <div className="info-card-title"><FontAwesomeIcon icon={faIdCard} /> Ma'lumotlarni tahrirlash</div>
              <label>Ism Familiya *</label>
              <input className="field" value={form.full_name} onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))} />
              <label><FontAwesomeIcon icon={faPhone} /> Telefon *</label>
              <input className="field" value={form.phone1} onChange={e => setForm(p => ({ ...p, phone1: e.target.value }))} />
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
              <label>Telegram ID (bot xabar yuborishi uchun) *muhim*</label>
              <input className="field" value={form.telegram_user_id} onChange={e => setForm(p => ({ ...p, telegram_user_id: e.target.value }))} placeholder="123456789" />
              <label>Izoh</label>
              <textarea className="field" rows={2} value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Qo'shimcha ma'lumot..." />
              <button className="button primary" style={{ marginTop: 10 }} onClick={handleSave} disabled={saving}>
                <FontAwesomeIcon icon={faFloppyDisk} /> {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          )}

          {mainTab === 'payment' && (
            <>
              <div className="info-card" style={{ marginBottom: 16 }}>
                <div className="info-card-title"><FontAwesomeIcon icon={faWallet} /> Joriy oy to'lov holati</div>
                {payLoading ? (
                  <div className="muted center py-4">Yuklanmoqda...</div>
                ) : !pay ? (
                  <div className="text-muted">Yuklab bo'lmadi</div>
                ) : (
                  <>
                    <div className="stat-row"><span>Oy</span><strong>{pay.month}/{pay.year}</strong></div>
                    <div className="stat-row"><span>Oylik summa</span><strong>{fmtSum(pay.total_owed)} so'm</strong></div>
                    <div className="stat-row"><span>To'langan</span><strong>{fmtSum(pay.total_paid)} so'm</strong></div>
                    {Number(pay.advance_balance) > 0 && (
                      <div className="stat-row"><span>Avans</span><strong style={{ color: 'var(--success)' }}>{fmtSum(pay.advance_balance)} so'm</strong></div>
                    )}
                    <div className="stat-row">
                      <span>Qarz</span>
                      <strong style={{ color: Number(pay.debt) > 0 ? 'var(--danger)' : 'var(--success)' }}>{fmtSum(pay.debt)} so'm</strong>
                    </div>
                  </>
                )}
              </div>

              {pay?.recent_payments?.length > 0 && (
                <div className="info-card">
                  <div className="info-card-title"><FontAwesomeIcon icon={faReceipt} /> So'nggi to'lovlar</div>
                  <div className="student-summary-list">
                    {pay.recent_payments.slice(0, 8).map(p => (
                      <div key={p.id} className="student-summary-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2, padding: '8px 0' }}>
                        <div style={{ display: 'flex', width: '100%', justifyContent: 'space-between' }}>
                          <span className="student-summary-name">{p.group_name} · {p.month}/{p.year}</span>
                          <span className="student-summary-stats"><strong>{fmtSum(p.amount)} so'm</strong></span>
                        </div>
                        {(p.notes || p.recorded_by_name) && (
                          <div className="text-muted" style={{ fontSize: 11.5 }}>
                            {p.notes && <>"{p.notes}"</>}{p.notes && p.recorded_by_name ? ' · ' : ''}{p.recorded_by_name}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {mainTab === 'attendance' && (
            <div className="info-card">
              <div className="info-card-title"><FontAwesomeIcon icon={faVideo} /> Kamera davomati</div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                {[7, 14, 30, 90].map(d => (
                  <button key={d} className={`button ${attendanceDays === d ? 'primary' : 'secondary'}`}
                    style={{ fontSize: 12, padding: '4px 12px' }}
                    onClick={() => { setAttendanceDays(d); loadAttendance(d) }}>
                    {d} kun
                  </button>
                ))}
              </div>
              {attendanceLoading ? (
                <div className="muted center py-4">Yuklanmoqda...</div>
              ) : attendanceData.length === 0 ? (
                <div className="muted center py-4">Bu davrda kamera yozuvi topilmadi</div>
              ) : (
                <div style={{ maxHeight: 420, overflowY: 'auto' }}>
                  <table className="data-table" style={{ fontSize: 13 }}>
                    <thead><tr><th>Sana</th><th>Kun</th><th>Soat</th><th>Holat</th></tr></thead>
                    <tbody>
                      {attendanceData.map(r => {
                        const dt = new Date(r.detected_at)
                        const dateStr = dt.toLocaleDateString('uz-UZ', { year: 'numeric', month: '2-digit', day: '2-digit' })
                        const day = dt.toLocaleDateString('uz-UZ', { weekday: 'long' })
                        const time = dt.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
                        const isKeldi = r.event_type === 'keldi'
                        return (
                          <tr key={r.id}>
                            <td>{dateStr}</td>
                            <td style={{ color: 'var(--muted)', fontSize: 12 }}>{day}</td>
                            <td><strong>{time}</strong></td>
                            <td>
                              <span style={{
                                display: 'inline-flex', alignItems: 'center', gap: 5,
                                padding: '2px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600,
                                background: isKeldi ? '#dcfce7' : '#fee2e2', color: isKeldi ? '#16a34a' : '#dc2626',
                              }}>
                                <FontAwesomeIcon icon={isKeldi ? faArrowRightToBracket : faArrowRightFromBracket} />
                                {isKeldi ? 'Keldi' : 'Ketdi'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {mainTab === 'vacation' && isHunter && (
            <div className="info-card">
              <div className="info-card-title"><FontAwesomeIcon icon={faUmbrellaBeach} /> Ta'til</div>
              <p className="text-muted" style={{ fontSize: 12, marginTop: 0 }}>
                Ta'til oralig'iga tushgan darslar oylik to'lovdan avtomatik chiqarib tashlanadi.
              </p>
              <div className="row-2">
                <div>
                  <label>Boshlanish sanasi *</label>
                  <input className="field" type="date" value={vacForm.start_date}
                    onChange={e => setVacForm(p => ({ ...p, start_date: e.target.value, end_date: p.end_date < e.target.value ? e.target.value : p.end_date }))} />
                </div>
                <div>
                  <label>Tugash sanasi *</label>
                  <input className="field" type="date" value={vacForm.end_date} min={vacForm.start_date}
                    onChange={e => setVacForm(p => ({ ...p, end_date: e.target.value }))} />
                </div>
              </div>
              <label>Sababi (ixtiyoriy)</label>
              <input className="field" value={vacForm.reason} placeholder="Masalan: shifokor tavsiyasi"
                onChange={e => setVacForm(p => ({ ...p, reason: e.target.value }))} />
              <button className="button primary" style={{ marginTop: 10 }} onClick={handleVacSave} disabled={vacSaving}>
                <FontAwesomeIcon icon={faPlus} /> {vacSaving ? 'Saqlanmoqda...' : "Qo'shish"}
              </button>

              {vacations.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <label>Belgilangan ta'til kunlari</label>
                  {vacations.map(v => (
                    <div key={v.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: 8, background: 'var(--surface-2)', marginBottom: 6 }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>
                          {new Date(v.start_date + 'T00:00:00').toLocaleDateString('uz-UZ')} — {new Date(v.end_date + 'T00:00:00').toLocaleDateString('uz-UZ')}
                        </div>
                        {v.reason && <div className="text-muted" style={{ fontSize: 12 }}>{v.reason}</div>}
                        {v.created_by_name && <div className="text-muted" style={{ fontSize: 11 }}>{v.created_by_name}</div>}
                      </div>
                      <button className="btn-icon danger" onClick={() => handleVacDelete(v.id)}>
                        <FontAwesomeIcon icon={faTrash} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StudentAvatar({ photoUrl, size = 60 }) {
  if (!photoUrl) return (
    <div style={{ width: size, height: size, borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto' }}>
      <FontAwesomeIcon icon={faUserGraduate} style={{ color: '#94a3b8', fontSize: size * 0.4 }} />
    </div>
  )
  return (
    <img src={`${API_BASE}${photoUrl}`} alt="" style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover', margin: '0 auto', display: 'block' }} />
  )
}
