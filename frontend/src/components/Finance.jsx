import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faWallet, faChevronDown, faChevronRight,
  faCircleCheck, faCircleXmark, faFileExcel,
} from '@fortawesome/free-solid-svg-icons'
import { fetchFinanceMonthly, exportExcelUrl, openDownload } from '../api'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = new Date()

export default function Finance() {
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year, setYear] = useState(NOW.getFullYear())
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState({})
  const [showAll, setShowAll] = useState({})   // group_id → show all students or just unpaid

  useEffect(() => { load() }, [month, year])

  async function load() {
    setLoading(true)
    try { setData(await fetchFinanceMonthly(month, year)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function toggleGroup(id) {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const groups = data?.groups || []
  const collectionPct = data?.total_expected > 0
    ? Math.min(100, Math.round(data.total_actual / data.total_expected * 100))
    : 0

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faWallet} className="page-icon" /> Moliya</h1>
        <button className="button secondary" onClick={() => openDownload(exportExcelUrl(month, year))}>
          <FontAwesomeIcon icon={faFileExcel} /> Excel
        </button>
      </div>

      {/* Month selector */}
      <div className="toolbar">
        <select className="field-sm" value={month} onChange={e => setMonth(Number(e.target.value))}>
          {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
        <select className="field-sm" value={year} onChange={e => setYear(Number(e.target.value))}>
          {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <span className="text-muted" style={{ fontSize: 12, marginLeft: 4 }}>
          Kutilgan: talaba soni × to'liq tarif
        </span>
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : data ? (
        <>
          {/* KPIs */}
          <div className="finance-kpi-row">
            <div className="finance-kpi finance-kpi-expected">
              <div className="finance-kpi-label">Kutilgan (jami talabalar)</div>
              <div className="finance-kpi-value">{Number(data.total_expected).toLocaleString()}</div>
              <div className="finance-kpi-sub">so'm</div>
            </div>
            <div className="finance-kpi finance-kpi-actual">
              <div className="finance-kpi-label">Haqiqiy to'lov</div>
              <div className="finance-kpi-value">{Number(data.total_actual).toLocaleString()}</div>
              <div className="finance-kpi-sub">so'm</div>
            </div>
            <div className="finance-kpi finance-kpi-deficit">
              <div className="finance-kpi-label">Farq (to'lanmagan)</div>
              <div className="finance-kpi-value">{Number(data.total_deficit).toLocaleString()}</div>
              <div className="finance-kpi-sub">so'm</div>
            </div>
          </div>

          {/* Collection bar */}
          {data.total_expected > 0 && (
            <div style={{ margin: '0 0 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#737373', marginBottom: 4 }}>
                <span>Yig'ilish darajasi</span>
                <span style={{ fontWeight: 600, color: collectionPct >= 80 ? '#22c55e' : collectionPct >= 50 ? '#f59e0b' : '#ef4444' }}>
                  {collectionPct}%
                </span>
              </div>
              <div className="group-progress-bar" style={{ height: 10 }}>
                <div
                  className="group-progress-fill"
                  style={{
                    width: `${collectionPct}%`,
                    background: collectionPct >= 80 ? '#22c55e' : collectionPct >= 50 ? '#f59e0b' : '#ef4444',
                  }}
                />
              </div>
            </div>
          )}

          {/* Groups breakdown */}
          <div className="finance-groups">
            {groups.map(g => {
              const allSt = g.all_students || []
              const displayList = showAll[g.group_id] ? allSt : (g.unpaid_students || [])
              return (
                <div key={g.group_id} className="finance-group-card">
                  <div className="finance-group-header" onClick={() => toggleGroup(g.group_id)}>
                    <div className="finance-group-name">
                      <FontAwesomeIcon
                        icon={expanded[g.group_id] ? faChevronDown : faChevronRight}
                        style={{ fontSize: 11, marginRight: 8, color: '#737373' }}
                      />
                      <strong>{g.group_name}</strong>
                      <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>
                        {g.student_count} o'quvchi
                      </span>
                    </div>
                    <div className="finance-group-stats">
                      <span className="finance-stat-expected">{Number(g.expected).toLocaleString()}</span>
                      <span className="text-muted">/</span>
                      <span className="finance-stat-actual">{Number(g.actual).toLocaleString()}</span>
                      {g.unpaid_count > 0 && (
                        <span className="finance-unpaid-badge">{g.unpaid_count} to'lamagan</span>
                      )}
                      {g.unpaid_count === 0 && g.expected > 0 && (
                        <FontAwesomeIcon icon={faCircleCheck} style={{ color: '#22c55e', fontSize: 14 }} />
                      )}
                    </div>
                  </div>

                  {expanded[g.group_id] && (
                    <div className="finance-unpaid-list">
                      {/* Toggle: show all or only unpaid */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: 8 }}>
                        <div className="finance-unpaid-title" style={{ paddingBottom: 0 }}>
                          {showAll[g.group_id] ? "Barcha o'quvchilar:" : "To'lovni amalga oshirmagan o'quvchilar:"}
                        </div>
                        {allSt.length > 0 && (
                          <button
                            className="button secondary small"
                            onClick={() => setShowAll(prev => ({ ...prev, [g.group_id]: !prev[g.group_id] }))}
                          >
                            {showAll[g.group_id] ? "Faqat to'lamaganlar" : "Barchasini ko'rish"}
                          </button>
                        )}
                      </div>

                      {displayList.length > 0 ? (
                        <table className="data-table" style={{ fontSize: 12.5 }}>
                          <thead>
                            <tr>
                              <th>O'quvchi</th>
                              <th>Telefon</th>
                              <th>Tarif</th>
                              <th style={{ textAlign: 'center' }}>Kelgan</th>
                              <th style={{ textAlign: 'right' }}>To'lashi kerak</th>
                              <th style={{ textAlign: 'center' }}>Holat</th>
                            </tr>
                          </thead>
                          <tbody>
                            {displayList.map(s => (
                              <tr key={s.student_id}>
                                <td style={{ fontWeight: 500 }}>{s.student_name}</td>
                                <td className="text-muted">{s.phone}</td>
                                <td>
                                  {s.tariff_name
                                    ? <>
                                        <span style={{ fontSize: 11 }}>{s.tariff_name}</span>
                                        <span className="text-muted" style={{ fontSize: 10, marginLeft: 4 }}>
                                          ({Number(s.tariff_price).toLocaleString()}/oy)
                                        </span>
                                      </>
                                    : <span className="text-muted" style={{ fontSize: 11 }}>Tarif yo'q</span>
                                  }
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                  <span style={{ fontWeight: 600, color: s.attended > 0 ? '#2563eb' : '#9ca3af' }}>
                                    {s.attended}
                                  </span>
                                  <span className="text-muted" style={{ fontSize: 11 }}>/{s.total_lessons_held || '–'}</span>
                                </td>
                                <td style={{ textAlign: 'right', fontWeight: 600, color: s.owed > 0 ? '#0a0a0a' : '#9ca3af' }}>
                                  {s.owed > 0 ? `${Number(s.owed).toLocaleString()} so'm` : '—'}
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                  {s.is_paid === null
                                    ? <span className="text-muted" style={{ fontSize: 11 }}>—</span>
                                    : s.is_paid
                                      ? <FontAwesomeIcon icon={faCircleCheck} style={{ color: '#22c55e' }} />
                                      : <FontAwesomeIcon icon={faCircleXmark} style={{ color: '#ef4444' }} />
                                  }
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <div className="muted center" style={{ padding: '8px 0', fontSize: 13 }}>
                          {showAll[g.group_id] ? "O'quvchilar yo'q" : "To'lovni amalga oshirmagan o'quvchi yo'q"}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}

            {groups.length === 0 && (
              <div className="muted center py-8">Faol guruhlar yo'q</div>
            )}
          </div>
        </>
      ) : null}
    </div>
  )
}
