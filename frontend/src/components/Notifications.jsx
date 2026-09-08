import { PageIntro } from './ui/Workspace'
import { SummaryRow, ViewTabs } from './ui/Workspace'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBell, faRightToBracket, faRightFromBracket,
  faCamera, faMagnifyingGlass,
} from '@fortawesome/free-solid-svg-icons'
import { fetchStudents, fetchVisits, createVisit, uploadStudentPhoto, API_BASE, tashkentToday } from '../api'
import DataTable from './ui/DataTable'
import Badge from './ui/Badge'

const TODAY_STR = tashkentToday()

export default function Notifications() {
  const [students, setStudents] = useState([])
  const [visits, setVisits] = useState([])
  const [search, setSearch] = useState('')
  const [visitView, setVisitView] = useState('checkin')
  const [loading, setLoading] = useState(false)
  const [sendingId, setSendingId] = useState(null)   // "studentId-kind"
  const [uploadingId, setUploadingId] = useState(null)
  const fileInputRef = useRef(null)
  const uploadTargetRef = useRef(null)

  useEffect(() => {
    loadStudents()
    loadVisits()
  }, [])

  async function loadStudents() {
    try {
      const r = await fetchStudents({ is_active: true, page_size: 100 })
      setStudents(r.items || [])
    } catch { toast.error("Talabalarni yuklab bo'lmadi") }
  }

  async function loadVisits() {
    setLoading(true)
    try { setVisits(await fetchVisits({ visit_date: TODAY_STR })) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function handleVisit(student, kind) {
    setSendingId(`${student.id}-${kind}`)
    try {
      const v = await createVisit({ student_id: student.id, kind })
      if (v.telegram_sent) {
        toast.success(kind === 'arrived' ? "Keldi ✓ — Telegram xabar yuborildi" : "Ketdi ✓ — Telegram xabar yuborildi")
      } else {
        toast(`Saqlandi. Telegram: ${v.telegram_error || 'yuborilmadi'}`, { icon: '⚠️' })
      }
      loadVisits()
    } catch (e) { toast.error(e.message) }
    finally { setSendingId(null) }
  }

  function pickPhoto(student) {
    uploadTargetRef.current = student
    fileInputRef.current?.click()
  }

  async function handlePhotoFile(e) {
    const file = e.target.files[0]
    const student = uploadTargetRef.current
    e.target.value = ''
    if (!file || !student) return
    setUploadingId(student.id)
    try {
      await uploadStudentPhoto(student.id, file)
      toast.success('Rasm yuklandi — endi xabarlar rasm bilan ketadi')
      loadStudents()
    } catch (err) { toast.error(err.message) }
    finally { setUploadingId(null) }
  }

  const filtered = students.filter(s => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return s.full_name.toLowerCase().includes(q) || (s.phone1 || '').includes(q)
  })

  const lastVisitByStudent = {}
  for (const v of visits) {
    if (!lastVisitByStudent[v.student_id]) lastVisitByStudent[v.student_id] = v
  }

  function photoUrl(photo) {
    return photo ? `${API_BASE}/uploads/${photo}` : null
  }

  function timeLabel(iso) {
    return new Date(iso).toLocaleTimeString('uz', { hour: '2-digit', minute: '2-digit' })
  }

  const studentColumns = [
    {
      key: 'photo', header: 'Rasm', width: 64,
      render: s => (
        <div className="avatar-cell">
          {s.photo
            ? <img src={photoUrl(s.photo)} alt="" className="avatar-cell-img" />
            : <div className="avatar-cell-img is-initial">{s.full_name[0]}</div>}
          <button
            className="avatar-cell-btn" title="Rasm yuklash" aria-label="Rasm yuklash"
            disabled={uploadingId === s.id} onClick={() => pickPhoto(s)}
          >
            <FontAwesomeIcon icon={faCamera} />
          </button>
        </div>
      ),
    },
    {
      key: 'full_name', header: 'Talaba', sortable: true,
      render: s => (
        <>
          <strong>{s.full_name}</strong>
          <div className="muted-sm">{s.phone1}</div>
        </>
      ),
    },
    {
      key: 'telegram_user_id', header: 'Telegram', sortable: true,
      sortValue: s => (s.telegram_user_id ? 0 : 1),
      render: s => s.telegram_user_id
        // Har qatorda ID bo'lgani uchun badge neytral: bu ma'lumot,
        // holat emas — rangli bo'lsa ustun "chiroqlar qatori" ga aylanardi.
        ? <Badge variant="neutral" size="sm">ID: {s.telegram_user_id}</Badge>
        : <span className="muted-sm">Biriktirilmagan</span>,
    },
    {
      key: 'last', header: 'Oxirgi holat (bugun)',
      render: s => {
        const last = lastVisitByStudent[s.id]
        if (!last) return <span className="text-muted">—</span>
        return (
          <Badge variant={last.kind === 'arrived' ? 'success' : 'warning'} size="sm">
            {last.kind === 'arrived' ? 'Keldi' : 'Ketdi'} · {timeLabel(last.created_at)}
            {last.telegram_sent ? ' ✓' : ' ⚠'}
          </Badge>
        )
      },
    },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: s => (
        <span className="row-actions">
          {/* Ilgari bu har bir qatorda to'ldirilgan BINAFSHA tugma edi —
              o'nlab qator bo'lganda binafsha "asosiy amal" ma'nosini
              yo'qotardi. Endi rang semantik: kelish = yashil, ketish =
              neytral. Binafsha esa sahifaning yagona birlamchi amali uchun. */}
          <button className="btn-sm is-success" disabled={sendingId === `${s.id}-arrived`}
            onClick={() => handleVisit(s, 'arrived')}>
            <FontAwesomeIcon icon={faRightToBracket} /> Keldi
          </button>
          <button className="btn-sm" disabled={sendingId === `${s.id}-left`}
            onClick={() => handleVisit(s, 'left')}>
            <FontAwesomeIcon icon={faRightFromBracket} /> Ketdi
          </button>
        </span>
      ),
    },
  ]

  const visitColumns = [
    { key: 'created_at', header: 'Vaqt', sortable: true, render: v => <span className="num">{timeLabel(v.created_at)}</span> },
    { key: 'student_name', header: 'Talaba', sortable: true, render: v => <strong>{v.student_name}</strong> },
    {
      key: 'kind', header: 'Holat', sortable: true,
      render: v => (
        <Badge variant={v.kind === 'arrived' ? 'success' : 'warning'} size="sm">
          {v.kind === 'arrived' ? 'Keldi' : 'Ketdi'}
        </Badge>
      ),
    },
    { key: 'noted_by_name', header: 'Kim belgiladi', sortable: true, render: v => <span className="text-muted">{v.noted_by_name || '—'}</span> },
    {
      key: 'telegram_sent', header: 'Telegram', sortable: true,
      render: v => v.telegram_sent
        ? <span className="tone-success">Yuborildi</span>
        : <span className="tone-warning" title={v.telegram_error || ''}>{v.telegram_error || 'Yuborilmadi'}</span>,
    },
  ]

  return (
    <div className="page visits-studio">
      <PageIntro title={<>Kelish-ketish</>} description={<>Talaba kelganda/ketganda ota-onasiga Telegram orqali xabar boradi · bugun {visits.length} ta belgi</>}  />

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        style={{ display: 'none' }}
        onChange={handlePhotoFile}
      />

      <SummaryRow items={[{ label: 'Bugungi belgilar', value: visits.length }, { label: 'Kelgan', value: visits.filter(v => v.kind === 'arrived').length, tone: 'success' }, { label: 'Ketgan', value: visits.filter(v => v.kind === 'left').length }, { label: 'Telegramga yuborilgan', value: visits.filter(v => v.telegram_sent).length }]} />
      <ViewTabs value={visitView} onChange={setVisitView} items={[{ key: 'checkin', label: 'Kelish-ketishni belgilash' }, { key: 'history', label: 'Bugungi tarix', count: visits.length }]} />
      {visitView === 'checkin' && <section className="studio-section ledger-records"><div className="studio-section-head"><h2>Talabalar ro‘yxati</h2><span>Talabani toping va holatini belgilang</span></div><DataTable
        columns={studentColumns}
        rows={filtered}
        clientPageSize={20}
        toolbar={
          <div className="search-wrap">
            <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
            <input
              className="search-input"
              placeholder="Talaba ismi yoki telefon..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        }
        empty={{ icon: faMagnifyingGlass, title: 'Talaba topilmadi', description: "Qidiruv so'zini o'zgartirib ko'ring." }}
      />

      </section>}

      {visitView === 'history' && <section className="studio-section visit-history">
        <div className="ui-section-head">
          <div className="ui-section-head-text">
            <h2>Bugungi tarix</h2>
            <p>Bugun belgilangan barcha kelish-ketishlar</p>
          </div>
        </div>
        <DataTable
          columns={visitColumns}
          rows={visits}
          loading={loading}
          clientPageSize={25}
          empty={{ icon: faBell, title: "Bugun hali belgi yo'q", description: 'Yuqoridagi ro\'yxatdan talabani belgilang.' }}
        />
      </section>}

    </div>
  )
}
