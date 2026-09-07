import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faTriangleExclamation, faCircleCheck, faCircleInfo, faBolt,
} from '@fortawesome/free-solid-svg-icons'
import DataTable from '../ui/DataTable'

const money = (n) => Number(n || 0).toLocaleString('uz-UZ')

const INSIGHT_ICON = {
  bottleneck: faBolt,
  warning: faTriangleExclamation,
  success: faCircleCheck,
  info: faCircleInfo,
}

/**
 * Asosiy xulosalar.
 *
 * Barcha matnlar backend'da QOIDA asosida yaratiladi (eng katta yo'qotish,
 * to'xtab qolgan bosqich va h.k.) — bu yerda hech narsa to'qilmaydi.
 * Bosilganda tegishli tugun/o'tish daraxtda tanlanadi.
 */
export function ConversionInsights({ insights, onFocus }) {
  if (!insights?.length) return null
  return (
    <div className="ins-grid">
      {insights.map((i, idx) => {
        const clickable = !!(i.from_key || i.stage_key)
        const Tag = clickable ? 'button' : 'div'
        return (
          <Tag
            key={idx}
            type={clickable ? 'button' : undefined}
            className={`ins-card tone-${i.kind}${clickable ? ' is-clickable' : ''}`}
            onClick={clickable ? () => onFocus(i) : undefined}
          >
            <span className="ins-icon" aria-hidden="true">
              <FontAwesomeIcon icon={INSIGHT_ICON[i.kind] || faCircleInfo} />
            </span>
            <span className="ins-body">
              <span className="ins-title">{i.title}</span>
              {i.detail && <span className="ins-detail">{i.detail}</span>}
              {i.value && <span className="ins-value">{i.value}</span>}
            </span>
          </Tag>
        )
      })}
    </div>
  )
}

/** Manba bo'yicha konversiya — qaysi kanal haqiqatan ham to'lov keltiradi. */
export function SourceConversion({ sources, onSelect }) {
  const columns = [
    { key: 'name', header: 'Manba', render: r => r.name },
    { key: 'leads', header: 'Lidlar', align: 'right', sortable: true, render: r => r.leads },
    { key: 'won', header: "To'landi", align: 'right', sortable: true, render: r => r.won },
    {
      key: 'conversion', header: 'Konversiya', align: 'right', sortable: true,
      render: r => <span className={r.conversion > 0 ? 'num-pos' : 'muted'}>{r.conversion}%</span>,
    },
    { key: 'revenue', header: 'Tushum', align: 'right', sortable: true, render: r => money(r.revenue) },
  ]
  return (
    <DataTable
      columns={columns}
      rows={sources}
      rowKey={r => r.id ?? 'none'}
      onRowClick={onSelect ? (r => onSelect(r)) : undefined}
      empty={{ title: 'Manba maʼlumoti yoʻq' }}
      clientPageSize={0}
    />
  )
}

/**
 * Operator kesimi.
 * Backend buni faqat admin va hunter uchun to'ldiradi — sales/call_center
 * javobida ro'yxat bo'sh keladi, shuning uchun bu yerda hech narsa
 * yashirishning hojati yo'q (himoya server tomonda).
 */
export function OperatorConversion({ operators }) {
  const columns = [
    { key: 'name', header: 'Operator', render: r => r.name },
    { key: 'leads', header: 'Lidlar', align: 'right', sortable: true, render: r => r.leads },
    { key: 'won', header: "To'landi", align: 'right', sortable: true, render: r => r.won },
    {
      key: 'conversion', header: 'Konversiya', align: 'right', sortable: true,
      render: r => <span className={r.conversion > 0 ? 'num-pos' : 'muted'}>{r.conversion}%</span>,
    },
    { key: 'revenue', header: 'Tushum', align: 'right', sortable: true, render: r => money(r.revenue) },
  ]
  return (
    <DataTable
      columns={columns}
      rows={operators}
      rowKey={r => r.id ?? 'none'}
      empty={{ title: 'Operator maʼlumoti yoʻq' }}
      clientPageSize={0}
    />
  )
}
