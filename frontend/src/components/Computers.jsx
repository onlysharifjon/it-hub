import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faDesktop, faPlus, faPen, faTrash, faHandHolding, faRotateLeft,
  faClockRotateLeft, faMagnifyingGlass, faCalendarDays, faUser,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchComputers, createComputer, createComputersBulk, updateComputer, deleteComputer,
  searchComputerStudents, giveComputer, returnComputer, fetchComputerRentals,
} from '../api'
import { PageIntro, SummaryRow, ViewTabs } from './ui/Workspace'
import DataTable from './ui/DataTable'
import Modal from './ui/Modal'
import Badge from './ui/Badge'
import { Input, Textarea } from './ui/Field'
import { CardSkeleton, EmptyState } from './ui/States'
import useConfirm from './ui/useConfirm'
import { fmtTime, fmtDay, tashkentToday } from '../utils/datetime'

/** 95 → "1 soat 35 daq" */
function duration(min) {
  if (min == null) return '—'
  const h = Math.floor(min / 60)
  const m = min % 60
  if (!h) return `${m} daq`
  return m ? `${h} soat ${m} daq` : `${h} soat`
}

/** Bir kompyuter kartasi (ixcham — 50+ kompyuter bir ekranga sig'ishi uchun). */
function PcCard({ c, onGive, onReturn, onEdit, onDelete }) {
  const r = c.current
  const mins = r ? Math.max(0, Math.floor((Date.now() - new Date(r.given_at).getTime()) / 60000)) : null
  return (
    <article className={`pc-card${r ? ' is-busy' : ''}`}>
      <header>
        <span className="pc-number"><FontAwesomeIcon icon={faDesktop} /> {c.number}</span>
        <Badge variant={r ? 'warning' : 'success'} size="sm">{r ? 'Band' : 'Bo‘sh'}</Badge>
      </header>
      {c.name && <div className="pc-name">{c.name}</div>}
      {r ? (
        <div className="pc-rental">
          <strong title={r.student_phone}><FontAwesomeIcon icon={faUser} /> {r.student_name}</strong>
          <span>Berildi: <b>{fmtTime(r.given_at)}</b> · {duration(mins)}</span>
          <span className="pc-by">{r.given_by || '—'}{r.note ? ` · ${r.note}` : ''}</span>
        </div>
      ) : (
        <div className="pc-rental pc-free">{c.note || 'Berishga tayyor'}</div>
      )}
      <footer>
        {r ? (
          <button className="button secondary small" onClick={() => onReturn(r)}>
            <FontAwesomeIcon icon={faRotateLeft} /> Qaytarib olish
          </button>
        ) : (
          <button className="button primary small" onClick={() => onGive(c)}>
            <FontAwesomeIcon icon={faHandHolding} /> Berish
          </button>
        )}
        <div className="pc-tools">
          <button className="btn-icon" title="Tahrirlash" aria-label="Tahrirlash" onClick={() => onEdit(c)}>
            <FontAwesomeIcon icon={faPen} />
          </button>
          <button className="btn-icon" title={r ? 'Band kompyuterni o‘chirib bo‘lmaydi' : 'O‘chirish'} aria-label="O‘chirish"
            disabled={!!r} onClick={() => onDelete(c)}>
            <FontAwesomeIcon icon={faTrash} />
          </button>
        </div>
      </footer>
    </article>
  )
}

const REFRESH_MS = 30000

export default function Computers() {
  const [view, setView] = useState('grid')
  const [computers, setComputers] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')        // all | free | busy
  const [search, setSearch] = useState('')
  const [confirmUI, ask] = useConfirm()

  const [editModal, setEditModal] = useState(null)   // {id?, mode: 'one'|'range', number, from, to, name, note}
  const [giveModal, setGiveModal] = useState(null)   // computer
  const [returnModal, setReturnModal] = useState(null) // rental

  // Bir nechta xodim bir vaqtda ishlashi mumkin — ro'yxat o'zi yangilanib
  // turadi (va "necha daqiqadan beri" hisoblagichi ham).
  useEffect(() => {
    load()
    const t = setInterval(() => { if (!document.hidden) load(true) }, REFRESH_MS)
    return () => clearInterval(t)
  }, [])

  async function load(silent = false) {
    try { setComputers(await fetchComputers()) }
    catch (err) { if (!silent) toast.error(err.message || "Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  const nextNumber = computers.reduce((m, c) => Math.max(m, c.number), 0) + 1
  const openAdd = () => setEditModal({ mode: 'one', number: nextNumber, from: nextNumber, to: nextNumber + 9, name: '', note: '' })

  async function saveComputer() {
    try {
      if (!editModal.id && editModal.mode === 'range') {
        const from = Number(editModal.from), to = Number(editModal.to)
        if (!from || !to || from < 1 || to < 1) return toast.error('Oraliqni kiriting')
        const res = await createComputersBulk({ number_from: from, number_to: to })
        toast.success(`${res.added} ta kompyuter qo‘shildi${res.skipped ? ` (${res.skipped} tasi avvaldan bor edi)` : ''}`)
      } else {
        const number = Number(editModal.number)
        if (!number || number < 1) return toast.error('Kompyuter raqamini kiriting')
        const data = { number, name: editModal.name?.trim() || null, note: editModal.note?.trim() || null }
        if (editModal.id) await updateComputer(editModal.id, data)
        else await createComputer(data)
        toast.success(editModal.id ? 'Saqlandi' : `${number}-kompyuter qo‘shildi`)
      }
      setEditModal(null)
      load()
    } catch (err) { toast.error(err.message) }
  }

  async function removeComputer(c) {
    if (!await ask({ title: 'Kompyuterni o‘chirish', message: `${c.number}-kompyuter ro‘yxatdan olib tashlansinmi? Berish tarixi saqlanib qoladi.`, confirmLabel: 'O‘chirish' })) return
    try { await deleteComputer(c.id); toast.success('O‘chirildi'); load() }
    catch (err) { toast.error(err.message) }
  }

  const busy = computers.filter(c => c.current)
  const longest = useMemo(
    () => busy.reduce((a, c) => (!a || c.current.given_at < a.current.given_at ? c : a), null),
    [computers],
  )

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase()
    return computers.filter(c => {
      if (filter === 'free' && c.current) return false
      if (filter === 'busy' && !c.current) return false
      if (!q) return true
      return String(c.number) === q
        || (c.name || '').toLowerCase().includes(q)
        || (c.current?.student_name || '').toLowerCase().includes(q)
        || (c.current?.student_phone || '').includes(q)
    })
  }, [computers, filter, search])

  return (
    <div className="page computers-page">
      {confirmUI}
      <PageIntro
        title="Kompyuterlar"
        description={<>Talabalarga kompyuter berish va qaytarib olish · {computers.length} ta kompyuter, <strong>{busy.length}</strong> tasi band</>}
        actions={
          <button className="button primary" onClick={openAdd}>
            <FontAwesomeIcon icon={faPlus} /> Kompyuter qo‘shish
          </button>
        }
      />

      <SummaryRow items={[
        { label: 'Jami', value: computers.length, icon: faDesktop, onClick: () => { setView('grid'); setFilter('all') } },
        { label: 'Bo‘sh', value: computers.length - busy.length, tone: 'success', onClick: () => { setView('grid'); setFilter('free') } },
        { label: 'Band (talabada)', value: busy.length, tone: busy.length ? 'warning' : undefined, onClick: () => { setView('grid'); setFilter('busy') } },
        {
          label: 'Eng uzoq talabada',
          value: longest ? `${longest.number}-kompyuter` : '—',
          sub: longest ? `${longest.current.student_name} · ${fmtTime(longest.current.given_at)} dan beri` : 'Hozir hech kimda yo‘q',
        },
      ]} />

      <ViewTabs
        value={view}
        onChange={setView}
        items={[
          { key: 'grid', label: 'Kompyuterlar', icon: faDesktop, count: computers.length },
          { key: 'log', label: 'Berish jurnali', icon: faClockRotateLeft },
        ]}
      />

      {view === 'grid' ? (
        loading ? <CardSkeleton count={6} height={150} /> : computers.length === 0 ? (
          <EmptyState
            icon={faDesktop}
            title="Hali kompyuter qo‘shilmagan"
            description="Markazdagi kompyuterlarni raqami bilan qo‘shing — keyin ularni talabalarga berish mumkin."
            action={<button className="button primary" onClick={openAdd}><FontAwesomeIcon icon={faPlus} /> Kompyuter qo‘shish</button>}
          />
        ) : (
          <>
            <div className="pc-toolbar">
              <div className="pc-search">
                <FontAwesomeIcon icon={faMagnifyingGlass} />
                <input className="field" placeholder="Kompyuter raqami yoki talaba ismi…"
                  value={search} onChange={e => setSearch(e.target.value)} aria-label="Qidirish" />
              </div>
              <div className="pc-segment" role="group" aria-label="Holat">
                {[
                  ['all', `Hammasi ${computers.length}`],
                  ['free', `Bo‘sh ${computers.length - busy.length}`],
                  ['busy', `Band ${busy.length}`],
                ].map(([k, label]) => (
                  <button key={k} type="button" className={filter === k ? 'is-active' : ''} onClick={() => setFilter(k)}>{label}</button>
                ))}
              </div>
            </div>
            {shown.length === 0 ? (
              <EmptyState compact icon={faMagnifyingGlass} title="Hech narsa topilmadi"
                description="Qidiruv yoki filtrni o‘zgartirib ko‘ring." />
            ) : (
              <div className="pc-grid">
                {shown.map(c => (
                  <PcCard key={c.id} c={c}
                    onGive={setGiveModal}
                    onReturn={setReturnModal}
                    onEdit={x => setEditModal({ id: x.id, number: x.number, name: x.name || '', note: x.note || '' })}
                    onDelete={removeComputer}
                  />
                ))}
              </div>
            )}
          </>
        )
      ) : (
        <RentalLog computers={computers} onReturn={setReturnModal} />
      )}

      <Modal
        open={!!editModal}
        title={editModal?.id ? `${editModal.number}-kompyuterni tahrirlash` : 'Kompyuter qo‘shish'}
        onClose={() => setEditModal(null)}
        size="sm"
        footer={<>
          <button className="button secondary" onClick={() => setEditModal(null)}>Bekor</button>
          <button className="button primary" onClick={saveComputer}>Saqlash</button>
        </>}
      >
        {editModal && <>
          {!editModal.id && (
            <div className="pc-segment" role="group" aria-label="Qo‘shish usuli">
              <button type="button" className={editModal.mode === 'one' ? 'is-active' : ''} onClick={() => setEditModal({ ...editModal, mode: 'one' })}>Bitta</button>
              <button type="button" className={editModal.mode === 'range' ? 'is-active' : ''} onClick={() => setEditModal({ ...editModal, mode: 'range' })}>Oraliq (masalan 51–60)</button>
            </div>
          )}
          {!editModal.id && editModal.mode === 'range' ? (
            <div className="pc-range">
              <Input label="Raqamdan" required type="number" min="1" autoFocus
                value={editModal.from} onChange={e => setEditModal({ ...editModal, from: e.target.value })} />
              <Input label="Raqamgacha" required type="number" min="1"
                value={editModal.to} onChange={e => setEditModal({ ...editModal, to: e.target.value })} />
            </div>
          ) : <>
            <Input label="Kompyuter raqami" required type="number" min="1" autoFocus
              value={editModal.number} onChange={e => setEditModal({ ...editModal, number: e.target.value })} />
            <Input label="Nomi / modeli" hint="Ixtiyoriy, masalan: Lenovo i5"
              value={editModal.name} onChange={e => setEditModal({ ...editModal, name: e.target.value })} />
            <Textarea label="Izoh" rows={2} hint="Ixtiyoriy"
              value={editModal.note} onChange={e => setEditModal({ ...editModal, note: e.target.value })} />
          </>}
        </>}
      </Modal>

      {giveModal && (
        <GiveModal
          computer={giveModal}
          onClose={() => setGiveModal(null)}
          onDone={() => { setGiveModal(null); load() }}
        />
      )}

      {returnModal && (
        <ReturnModal
          rental={returnModal}
          onClose={() => setReturnModal(null)}
          onDone={() => { setReturnModal(null); load() }}
        />
      )}
    </div>
  )
}

function GiveModal({ computer, onClose, onDone }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [student, setStudent] = useState(null)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => {
      searchComputerStudents(q).then(setResults).catch(() => setResults([]))
    }, 250)
    return () => clearTimeout(t)
  }, [q])

  async function submit() {
    if (!student) return toast.error('Talabani tanlang')
    setSaving(true)
    try {
      const r = await giveComputer(computer.id, { student_id: student.id, note: note.trim() || null })
      toast.success(`${computer.number}-kompyuter ${r.student_name}ga soat ${fmtTime(r.given_at)} da berildi`)
      onDone()
    } catch (err) { toast.error(err.message) }
    finally { setSaving(false) }
  }

  return (
    <Modal
      open
      title={`${computer.number}-kompyuterni berish`}
      onClose={onClose}
      footer={<>
        <button className="button secondary" onClick={onClose}>Bekor</button>
        <button className="button primary" onClick={submit} disabled={!student || saving}>
          <FontAwesomeIcon icon={faHandHolding} /> Berish
        </button>
      </>}
    >
      {student ? (
        <div className="pc-picked">
          <div>
            <strong>{student.full_name}</strong>
            <span>{student.phone}</span>
            {student.has_computer && <Badge variant="warning" size="sm">Diqqat: {student.has_computer}-kompyuter hali qaytarilmagan</Badge>}
          </div>
          <button className="button secondary" onClick={() => setStudent(null)}>O‘zgartirish</button>
        </div>
      ) : (
        <>
          <div className="pc-search">
            <FontAwesomeIcon icon={faMagnifyingGlass} />
            <input className="field" autoFocus placeholder="Talaba ismi yoki telefoni…"
              value={q} onChange={e => setQ(e.target.value)} />
          </div>
          <div className="pc-results">
            {results.length === 0
              ? <p className="muted-sm">Talaba topilmadi</p>
              : results.map(s => (
                <button key={s.id} type="button" onClick={() => setStudent(s)}>
                  <strong>{s.full_name}</strong>
                  <span>{s.has_computer ? <Badge variant="warning" size="sm">{s.has_computer}-kompyuter hozir unda</Badge> : s.phone}</span>
                </button>
              ))}
          </div>
        </>
      )}
      <Textarea label="Izoh" rows={2} hint="Ixtiyoriy — masalan: zaryadlovchi bilan berildi"
        value={note} onChange={e => setNote(e.target.value)} />
      <p className="muted-sm">Berilgan vaqt avtomatik yoziladi (hozirgi vaqt).</p>
    </Modal>
  )
}

function ReturnModal({ rental, onClose, onDone }) {
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit() {
    setSaving(true)
    try {
      const r = await returnComputer(rental.id, { note: note.trim() || null })
      toast.success(`${r.computer_number}-kompyuter soat ${fmtTime(r.returned_at)} da qaytarib olindi (${duration(r.duration_minutes)})`)
      onDone()
    } catch (err) { toast.error(err.message) }
    finally { setSaving(false) }
  }

  return (
    <Modal
      open
      title={`${rental.computer_number}-kompyuterni qaytarib olish`}
      onClose={onClose}
      size="sm"
      footer={<>
        <button className="button secondary" onClick={onClose}>Bekor</button>
        <button className="button primary" onClick={submit} disabled={saving}>
          <FontAwesomeIcon icon={faRotateLeft} /> Qaytarib oldim
        </button>
      </>}
    >
      <div className="pc-picked">
        <div>
          <strong>{rental.student_name}</strong>
          <span>Berildi: {fmtDay(rental.given_at)}, soat {fmtTime(rental.given_at)}</span>
        </div>
      </div>
      <Textarea label="Izoh" rows={2} hint="Ixtiyoriy — masalan: holati yaxshi"
        value={note} onChange={e => setNote(e.target.value)} />
      <p className="muted-sm">Qaytarilgan vaqt avtomatik yoziladi (hozirgi vaqt).</p>
    </Modal>
  )
}

function RentalLog({ computers, onReturn }) {
  const today = tashkentToday()
  const [dateFrom, setDateFrom] = useState(today)
  const [dateTo, setDateTo] = useState(today)
  const [status, setStatus] = useState('')
  const [computerId, setComputerId] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  // Kompyuterlar ro'yxati (berish/qaytarish) o'zgarsa jurnal ham yangilanadi.
  useEffect(() => { load() }, [dateFrom, dateTo, status, computerId, computers])

  // Ro'yxat 30 soniyada yangilanadi — jadval har safar skeletonga o'tib
  // "miltillamasligi" uchun yuklanish holati faqat filtr o'zgarganda ko'rinadi.
  const filterKey = `${dateFrom}|${dateTo}|${status}|${computerId}`
  const lastKey = useRef(null)

  async function load() {
    if (lastKey.current !== filterKey) setLoading(true)
    lastKey.current = filterKey
    try {
      setRows(await fetchComputerRentals({
        date_from: dateFrom, date_to: dateTo, status, computer_id: computerId,
      }))
    } catch (err) { toast.error(err.message) }
    finally { setLoading(false) }
  }

  const columns = [
    {
      key: 'computer_number', header: '№ Kompyuter', sortable: true,
      render: r => <span className="pc-number sm"><FontAwesomeIcon icon={faDesktop} /> {r.computer_number}</span>,
    },
    {
      key: 'student_name', header: 'Talaba', sortable: true,
      render: r => <div className="kassa-day-cell"><strong>{r.student_name}</strong><small>{r.student_phone}</small></div>,
    },
    {
      key: 'given_at', header: 'Berildi', sortable: true,
      render: r => <div className="kassa-day-cell"><strong>{fmtTime(r.given_at)}</strong><small>{fmtDay(r.given_at)}</small></div>,
    },
    {
      key: 'returned_at', header: 'Qaytarib olindi', sortable: true,
      render: r => r.returned_at
        ? <div className="kassa-day-cell"><strong>{fmtTime(r.returned_at)}</strong><small>{fmtDay(r.returned_at)}</small></div>
        : <Badge variant="warning" size="sm">Hali talabada</Badge>,
    },
    { key: 'duration_minutes', header: 'Davomiyligi', sortable: true, render: r => duration(r.duration_minutes) },
    { key: 'given_by', header: 'Bergan', render: r => <span className="muted-sm">{r.given_by || '—'}</span> },
    { key: 'returned_by', header: 'Olgan', render: r => <span className="muted-sm">{r.returned_by || '—'}</span> },
    {
      key: 'note', header: 'Izoh',
      render: r => <span className="muted-sm">{[r.note, r.return_note].filter(Boolean).join(' · ') || '—'}</span>,
    },
    {
      key: 'actions', header: '', align: 'right',
      render: r => !r.returned_at && (
        <button className="button secondary small" onClick={e => { e.stopPropagation(); onReturn(r) }}>
          <FontAwesomeIcon icon={faRotateLeft} /> Qaytarib olish
        </button>
      ),
    },
  ]

  return (
    <div className="studio-section pc-log">
      <div className="studio-section-head">
        <div>
          <h2>Berish jurnali</h2>
          <p>Qaysi kompyuter kimga, soat nechida berilgani va qaytarib olingani.</p>
        </div>
        <div className="pc-filters">
          <FontAwesomeIcon icon={faCalendarDays} className="muted-sm" />
          <input type="date" className="field-sm" value={dateFrom} max={dateTo} onChange={e => setDateFrom(e.target.value)} aria-label="Sanadan" />
          <span className="muted-sm">—</span>
          <input type="date" className="field-sm" value={dateTo} min={dateFrom} onChange={e => setDateTo(e.target.value)} aria-label="Sanagacha" />
          <select className="field-sm" value={computerId} onChange={e => setComputerId(e.target.value)} aria-label="Kompyuter">
            <option value="">Barcha kompyuterlar</option>
            {computers.map(c => <option key={c.id} value={c.id}>{c.number}-kompyuter</option>)}
          </select>
          <select className="field-sm" value={status} onChange={e => setStatus(e.target.value)} aria-label="Holat">
            <option value="">Barchasi</option>
            <option value="active">Hali talabada</option>
            <option value="returned">Qaytarilgan</option>
          </select>
        </div>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        loading={loading}
        clientPageSize={50}
        empty={{
          icon: faClockRotateLeft,
          title: 'Bu davrda kompyuter berilmagan',
          description: 'Sana oralig‘ini o‘zgartirib ko‘ring.',
        }}
      />
    </div>
  )
}
