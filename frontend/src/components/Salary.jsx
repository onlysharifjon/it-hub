import { PageIntro } from './ui/Workspace'
import { SummaryRow, ProgressRing, ViewTabs } from './ui/Workspace'
import PersonName from './ui/PersonName'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faMoneyBillWave, faPen, faCheck, faXmark, faRotateLeft, faUserGraduate, faListUl } from '@fortawesome/free-solid-svg-icons'
import { fetchSalaryOverview, setStaffSalary, setStaffInternship, clearSalaryOverride, fetchSalaryBreakdown } from '../api'
import useConfirm from './ui/useConfirm'
import DataTable, { RowActions } from './ui/DataTable'
import Modal from './ui/Modal'
import Badge from './ui/Badge'
import Meter from './ui/Meter'
import { Metric, MetricStrip } from './ui/Metric'
import { ROLE_LABELS, roleColor } from '../constants/domain'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = tashkentNow()
const YEARS = Array.from({ length: 5 }, (_, i) => NOW.getFullYear() - 2 + i)
const fmt = n => Number(n || 0).toLocaleString('uz-UZ')


export default function Salary() {
  const [confirmUI, ask] = useConfirm()
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year,  setYear]  = useState(NOW.getFullYear())
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(null)   // staff_id being edited
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [breakdownFor, setBreakdownFor] = useState(null)   // row being viewed
  const [breakdown, setBreakdown] = useState(null)
  const [breakdownLoading, setBreakdownLoading] = useState(false)

  useEffect(() => { load() }, [month, year])

  async function load() {
    setLoading(true)
    try { setData(await fetchSalaryOverview(month, year)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openEdit(row) {
    setEditing(row.staff_id)
    setEditValue(String(row.salary || ''))
  }

  async function saveEdit(row) {
    const val = Number(editValue)
    if (!editValue || val < 0) { toast.error("Summani kiriting"); return }
    setSaving(true)
    try {
      await setStaffSalary(row.staff_id, val, month, year)
      toast.success('Saqlandi')
      setEditing(null)
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    } finally {
      setSaving(false)
    }
  }

  async function revertToFormula(row) {
    const ok = await ask({
      title: 'Qayta hisoblash',
      message: `${row.full_name} — ${MONTHS[month - 1]} ${year} oyligi qayta hisoblansinmi?`,
      detail: "Qo'lda kiritilgan qiymat o'chadi va formula/asosiy oylik qaytariladi.",
      confirmLabel: 'Ha, qayta hisoblash',
      danger: false,
    })
    if (!ok) return
    setSaving(true)
    try {
      await clearSalaryOverride(row.staff_id, month, year)
      toast.success('Qayta hisoblandi')
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    } finally {
      setSaving(false)
    }
  }

  async function toggleInternship(row) {
    const ok = await ask({
      title: 'Stajirovka deb belgilash',
      message: `${row.full_name} — ${MONTHS[month - 1]} ${year} stajirovka deb belgilansinmi?`,
      detail: 'Shu oy uchun oylik 0 bo\'ladi.',
      confirmLabel: 'Ha, belgilash',
    })
    if (!ok) return
    setSaving(true)
    try {
      await setStaffInternship(row.staff_id, month, year)
      toast.success('Stajirovka belgilandi — shu oy uchun oylik 0')
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    } finally {
      setSaving(false)
    }
  }

  async function openBreakdown(row) {
    setBreakdownFor(row)
    setBreakdown(null)
    setBreakdownLoading(true)
    try {
      setBreakdown(await fetchSalaryBreakdown(row.staff_id, month, year))
    } catch (err) {
      toast.error(err.message || "Tafsilotni yuklab bo'lmadi")
      setBreakdownFor(null)
    } finally {
      setBreakdownLoading(false)
    }
  }

  const [salaryView, setSalaryView] = useState('all')
  const rows = data?.rows || []
  const shownRows = rows.filter(r => salaryView === 'all' || (salaryView === 'teachers' ? r.role === 'teacher' : r.role !== 'teacher'))
  const totalSalary = Number(data?.total_salary || 0)
  const totalPaid = Number(data?.total_paid || 0)
  const overallPct = totalSalary > 0 ? Math.min(100, Math.round((totalPaid / totalSalary) * 100)) : 0
  const pctColor = pct => (pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : pct > 0 ? 'var(--danger)' : 'var(--border-2)')

  const columns = [
    { key: 'full_name', header: 'F.I.O', sortable: true, render: r => <PersonName name={r.full_name} /> },
    {
      key: 'role', header: 'Rol', sortable: true,
      sortValue: r => ROLE_LABELS[r.role] || r.role,
      render: r => <Badge size="sm" color={roleColor(r.role)}>{ROLE_LABELS[r.role] || r.role}</Badge>,
    },
    {
      key: 'salary', header: 'Belgilangan oylik', align: 'right', sortable: true,
      sortValue: r => Number(r.salary),
      render: r => editing === r.staff_id ? (
        <input
          className="field-sm salary-edit"
          type="number"
          autoFocus
          value={editValue}
          onChange={e => setEditValue(e.target.value)}
        />
      ) : (
        <div>
          <strong>{fmt(r.salary)}</strong>
          {r.is_internship && <div className="salary-note is-warn">stajirovka — shu oy oylik 0</div>}
          {!r.is_internship && r.role === 'teacher' && r.auto && (
            <div className="salary-note">avtomatik: 5,000,000 + talaba ulushi {fmt(Number(r.salary) - 5000000)}</div>
          )}
          {!r.is_internship && r.role === 'teacher' && !r.auto && (
            <div className="salary-note">qo'lda o'zgartirilgan (formula: {fmt(r.auto_salary)})</div>
          )}
        </div>
      ),
    },
    {
      key: 'paid', header: "To'lov holati", width: 200, sortable: true,
      sortValue: r => (Number(r.salary) > 0 ? Number(r.paid) / Number(r.salary) : 0),
      render: r => {
        const salaryNum = Number(r.salary) || 0
        const pct = salaryNum > 0 ? Math.min(100, Math.round((Number(r.paid) / salaryNum) * 100)) : 0
        return (
          <Meter
            value={pct}
            showValue
            label={`${fmt(r.paid)} / ${fmt(r.salary)}`}
            tone={pct >= 80 ? 'success' : pct >= 50 ? 'warning' : pct > 0 ? 'danger' : 'neutral'}
          />
        )
      },
    },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: r => (
        <RowActions>
          {editing === r.staff_id ? (
            <>
              <button className="btn-icon success" title="Saqlash" aria-label="Saqlash" disabled={saving} onClick={() => saveEdit(r)}>
                <FontAwesomeIcon icon={faCheck} />
              </button>
              <button className="btn-icon" title="Bekor" aria-label="Bekor" onClick={() => setEditing(null)}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </>
          ) : (
            <>
              {r.role === 'teacher' && (
                <button className="btn-icon" title="Hisob-kitob tafsiloti" aria-label="Hisob-kitob tafsiloti" onClick={() => openBreakdown(r)}>
                  <FontAwesomeIcon icon={faListUl} />
                </button>
              )}
              {r.has_override && (
                <button className="btn-icon" title="Qayta hisoblash (formulaga qaytarish)" aria-label="Qayta hisoblash"
                  disabled={saving} onClick={() => revertToFormula(r)}>
                  <FontAwesomeIcon icon={faRotateLeft} />
                </button>
              )}
              {!r.is_internship && (
                <button className="btn-icon" title="Stajirovka deb belgilash (shu oy uchun oylik 0)" aria-label="Stajirovka"
                  disabled={saving} onClick={() => toggleInternship(r)}>
                  <FontAwesomeIcon icon={faUserGraduate} />
                </button>
              )}
              <button className="btn-icon" title="Oylikni tahrirlash" aria-label="Oylikni tahrirlash" onClick={() => openEdit(r)}>
                <FontAwesomeIcon icon={faPen} />
              </button>
            </>
          )}
        </RowActions>
      ),
    },
  ]

  return (
    <div className="page salary-studio">
      {confirmUI}
      <PageIntro title={<>Ish haqi</>} description={<>{MONTHS[month - 1]} {year} · barcha xodimlar bo'yicha oylik va to'lov holati</>} actions={<><div className="header-actions">
          <select className="field-sm" value={month} onChange={e => setMonth(Number(e.target.value))} aria-label="Oy">
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
          <select className="field-sm" value={year} onChange={e => setYear(Number(e.target.value))} aria-label="Yil">
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div></>} />

      <section className="ledger-overview"><div className="ledger-balance"><span className="studio-eyebrow">Oylik ish haqi fondi</span><strong>{fmt(data?.total_salary)}<small>so‘m</small></strong><div><ProgressRing value={overallPct} label="To‘lov darajasi" size={52} /><p>{overallPct}% to‘landi<span>{rows.length} xodim · {MONTHS[month - 1]} {year}</span></p></div></div><div className="ledger-balance-details"><div><span>Shu oy to‘langan</span><strong className="tone-success">{fmt(data?.total_paid)} <small>so‘m</small></strong></div><div><span>Qolgan summa</span><strong>{fmt(Number(data?.total_salary || 0) - Number(data?.total_paid || 0))} <small>so‘m</small></strong></div><div><span>Hisoblangan xodimlar</span><strong>{rows.length} <small>kishi</small></strong></div></div></section>
      <ViewTabs value={salaryView} onChange={setSalaryView} items={[{ key: 'all', label: 'Barcha xodimlar', count: rows.length }, { key: 'teachers', label: 'O‘qituvchilar', count: rows.filter(r => r.role === 'teacher').length }, { key: 'staff', label: 'Boshqa xodimlar', count: rows.filter(r => r.role !== 'teacher').length }]} />
      <section className="studio-section ledger-records"><div className="studio-section-head"><h2>Xodimlar bo‘yicha hisob-kitob</h2><span>{MONTHS[month - 1]} {year}</span></div>
      <DataTable
        columns={columns}
        rows={shownRows}
        loading={loading}
        rowKey={r => r.staff_id}
        clientPageSize={30}
        densityToggle densityKey="salary"
        empty={{ icon: faMoneyBillWave, title: "Xodimlar yo'q", description: 'Shu davr uchun oylik yozuvi topilmadi.' }}
      />

      </section>

      <Modal
        open={!!breakdownFor}
        title={breakdownFor ? `${breakdownFor.full_name} — hisob-kitob tafsiloti` : ''}
        onClose={() => setBreakdownFor(null)}
        size="xl"
      >
        <p className="muted-sm">
          {MONTHS[month - 1]} {year} · Formula: har guruhda 50,000 so'm shu oydagi o'tilgan darslar
          soniga bo'linadi (1 dars narxi), so'ng talaba qatnashgan darslar soniga ko'paytiriladi.
          {breakdown && <> FIX oylik: <strong>{fmt(breakdown.base_salary)}</strong>.</>}
        </p>

        <DataTable
          columns={[
            { key: 'group_name', header: 'Guruh', sortable: true },
            { key: 'student_name', header: 'Talaba', sortable: true },
            { key: 'lessons_held', header: 'Oydagi darslar', align: 'right', sortable: true },
            { key: 'attended', header: 'Qatnashgan', align: 'right', sortable: true },
            { key: 'per_lesson', header: '1 dars narxi', align: 'right', sortable: true,
              render: it => <span className="text-muted">{fmt(it.per_lesson)}</span> },
            { key: 'share', header: 'Ulush', align: 'right', sortable: true,
              sortValue: it => Number(it.share),
              render: it => <strong>{fmt(it.share)}</strong> },
          ]}
          rows={breakdown?.items || []}
          rowKey={(it, i) => i}
          loading={breakdownLoading}
          clientPageSize={20}
          empty={{ title: "Shu oy uchun davomat yozuvi yo'q" }}
        />

        {breakdown && (
          <dl className="pay-preview">
            <div><dt>Talaba ulushi jami</dt><dd>{fmt(breakdown.per_student_total)} so'm</dd></div>
            <div className="is-full"><dt>Jami</dt><dd>{fmt(breakdown.total)} so'm</dd></div>
          </dl>
        )}
      </Modal>

    </div>
  )
}
