import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation } from '@fortawesome/free-solid-svg-icons'
import { fetchMyWarnings } from '../api'

const SEVERITY_LABEL = { gray: 'Kulrang', yellow: 'Sariq', red: 'Qizil' }
const SEVERITY_STYLE = {
  gray:   { background: '#e5e7eb', color: '#374151' },
  yellow: { background: '#fef9c3', color: '#a16207' },
  red:    { background: '#fee2e2', color: '#dc2626' },
}

export default function MyWarnings() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetchMyWarnings()
      .then(setItems)
      .catch(() => toast.error("Yuklab bo'lmadi"))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faTriangleExclamation} className="page-icon" /> Mening ogohlantirishlarim</h1>
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Daraja</th>
                <th>Sabab</th>
                <th>Kim berdi</th>
                <th>Sana</th>
                <th>Holat</th>
              </tr>
            </thead>
            <tbody>
              {items.map((w, i) => (
                <tr key={w.id} className={w.cancelled_at ? 'row-inactive' : ''}>
                  <td className="text-muted">{i + 1}</td>
                  <td>
                    <span className="badge" style={SEVERITY_STYLE[w.severity]}>
                      {w.code ? `${w.code} — ${SEVERITY_LABEL[w.severity]}` : SEVERITY_LABEL[w.severity]}
                    </span>
                  </td>
                  <td style={{ maxWidth: 400 }}>{w.reason}</td>
                  <td className="text-muted">{w.issued_by_name || '—'}</td>
                  <td className="text-muted">{new Date(w.created_at).toLocaleString('uz-UZ')}</td>
                  <td>
                    <span className={`status-badge ${w.cancelled_at ? 'inactive' : 'active'}`}>
                      {w.cancelled_at ? 'Bekor qilingan' : 'Faol'}
                    </span>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={6} className="muted center py-4">Sizga ogohlantirish berilmagan</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
