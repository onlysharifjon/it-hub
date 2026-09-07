import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation, faCircleCheck } from '@fortawesome/free-solid-svg-icons'
import { fetchMyWarnings } from '../api'
import DataTable from './ui/DataTable'
import Badge from './ui/Badge'

const SEVERITY = {
  gray:   { label: 'Kulrang', variant: 'neutral', rank: 1 },
  yellow: { label: 'Sariq',   variant: 'warning', rank: 2 },
  red:    { label: 'Qizil',   variant: 'danger',  rank: 3 },
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

  const active = items.filter(w => !w.cancelled_at)

  const columns = [
    {
      key: 'severity', header: 'Daraja', sortable: true,
      sortValue: w => SEVERITY[w.severity]?.rank ?? 0,
      render: w => {
        const s = SEVERITY[w.severity] || SEVERITY.gray
        return <Badge variant={s.variant} size="sm">{w.code ? `${w.code} — ${s.label}` : s.label}</Badge>
      },
    },
    { key: 'reason', header: 'Sabab', render: w => <span className="cell-clamp">{w.reason}</span> },
    { key: 'issued_by_name', header: 'Kim berdi', sortable: true, render: w => <span className="text-muted">{w.issued_by_name || '—'}</span> },
    {
      key: 'created_at', header: 'Sana', sortable: true,
      render: w => <span className="muted-sm">{new Date(w.created_at).toLocaleString('uz-UZ')}</span>,
    },
    {
      key: 'status', header: 'Holat', sortable: true,
      sortValue: w => (w.cancelled_at ? 1 : 0),
      render: w => (
        <span className={`status-badge ${w.cancelled_at ? 'inactive' : 'active'}`}>
          {w.cancelled_at ? 'Bekor qilingan' : 'Faol'}
        </span>
      ),
    },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1><FontAwesomeIcon icon={faTriangleExclamation} className="page-icon" /> Mening ogohlantirishlarim</h1>
          <p className="page-subtitle">
            {active.length > 0
              ? `${active.length} ta faol ogohlantirish`
              : 'Faol ogohlantirish yo‘q'}
          </p>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        rowClassName={w => (w.cancelled_at ? 'row-inactive' : undefined)}
        clientPageSize={25}
        empty={{
          icon: faCircleCheck,
          title: 'Ogohlantirish yo‘q',
          description: 'Sizga hech qanday intizomiy ogohlantirish berilmagan.',
        }}
      />
    </div>
  )
}
