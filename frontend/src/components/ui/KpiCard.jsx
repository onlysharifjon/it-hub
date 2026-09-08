import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { Sparkline, TrendIndicator } from './Chart'

/**
 * KPI / stat karta — Dashboard, Finance, Salary, TeacherSalaries va
 * TeacherDashboard sahifalarining har biri shu markup'ni alohida qayta yozgan
 * edi (5 ta mustaqil nusxa). Endi bitta komponent.
 *
 *   <KpiCard label="Bu oy tushum" value="12 400 000" unit="so'm"
 *            tone="success" trend={12.4} spark={[...]} icon={faMoneyBill}
 *            onClick={() => onNavigate('payments')} />
 *
 * tone: default | primary | success | warning | danger | info | accent
 */
export default function KpiCard({
  label,
  value,
  unit,
  sub,
  icon,
  tone = 'default',
  trend,                 // raqam — o'tgan davrga nisbatan % o'zgarish
  trendLabel,
  trendInvert = false,   // xarajat kabi ko'rsatkichlar uchun (kamayish = yaxshi)
  spark,                 // massiv — kichik trend chizig'i
  onClick,
  hint,
  size = 'md',           // md | lg (hero uchun)
}) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      className={`ui-kpi ui-kpi-${size} tone-${tone} ${onClick ? 'is-clickable' : ''}`.trim()}
      onClick={onClick}
      title={hint}
      type={onClick ? 'button' : undefined}
    >
      <div className="ui-kpi-head">
        <span className="ui-kpi-label">{label}</span>
        {icon && <span className="ui-kpi-icon"><FontAwesomeIcon icon={icon} /></span>}
      </div>

      <div className="ui-kpi-value">
        {value}
        {unit && <span className="ui-kpi-unit">{unit}</span>}
      </div>

      {(trend != null || sub) && <div className="ui-kpi-foot">
        {trend != null && <TrendIndicator value={trend} invert={trendInvert} label={trendLabel} />}
        {sub && <span className="ui-kpi-sub">{sub}</span>}
      </div>}

      {spark?.length > 1 && (
        <div className="ui-kpi-spark">
          <Sparkline values={spark} tone={tone === 'default' ? 'primary' : tone} />
        </div>
      )}
    </Tag>
  )
}
