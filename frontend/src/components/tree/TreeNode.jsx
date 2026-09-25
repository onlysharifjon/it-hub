import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faUsers, faPhone, faPhoneSlash, faCalendarCheck, faVideo, faGraduationCap,
  faCircleXmark, faCircleQuestion, faCircle,
} from '@fortawesome/free-solid-svg-icons'
import { NODE_W, NODE_H, stageColor } from './layout'

/**
 * Bosqich tuguni.
 *
 * Bu <button> — div emas: Tab bilan yetib borish, Enter/Space bilan ochish va
 * fokus halqasi darhol ishlaydi. Rang yagona ma'no tashuvchi emas — nom, son
 * va foiz matn bilan yozilgan (§ka'ruvchanlik).
 *
 * Foiz DOIM izohlanadi: "100% kogortadan" — ya'ni tanlangan oyda kelgan
 * barcha lidlarga nisbatan. Izohsiz foiz ko'rsatilmaydi.
 */

// Ikonka bosqich SLUG'iga qarab tanlanadi, nomiga emas: admin bosqichni
// qayta nomlasa ham ikonka o'z joyida qoladi.
const ICONS = {
  new: faUsers, called: faPhone, no_answer: faPhoneSlash, callback: faPhone,
  will_come: faCalendarCheck, demo: faVideo, enrolled: faGraduationCap,
  rejected: faCircleXmark,
}
function iconFor(node) {
  if (node.slug && ICONS[node.slug]) return ICONS[node.slug]
  if (node.kind === 'won') return faGraduationCap
  if (node.kind === 'lost') return faCircleXmark
  if (node.kind === 'unknown') return faCircleQuestion
  return faCircle
}

export default function TreeNode({ node, selected, dimmed, onSelect, total }) {
  const color = stageColor(node.color, node.kind)
  const desc = `${node.name}: ${node.count} ta lid, kogortadagi ${total} ta liddan ${node.percent} foizi`
  return (
    <button
      type="button"
      className={[
        'tree-node',
        node.onMain ? 'is-main' : '',
        `kind-${node.kind}`,
        selected ? 'is-selected' : '',
        dimmed ? 'is-dimmed' : '',
      ].filter(Boolean).join(' ')}
      style={{ left: node.x, top: node.y, width: NODE_W, height: NODE_H, '--node-color': color }}
      onClick={() => onSelect(node)}
      aria-pressed={selected}
      aria-label={desc}
      title={desc}
    >
      <span className="tn-icon" aria-hidden="true"><FontAwesomeIcon icon={iconFor(node)} /></span>
      <span className="tn-body">
        <span className="tn-name">{node.name}</span>
        <span className="tn-nums">
          <strong>{node.count.toLocaleString('uz-UZ')}</strong>
          <span className="tn-unit">lid</span>
        </span>
        <span className="tn-pct">{node.percent}% kogortadan</span>
      </span>
      {node.kind === 'unknown' && (
        <span className="tn-flag" title="Bu bosqich endi mavjud emas — faqat tarixda uchraydi">
          arxiv
        </span>
      )}
    </button>
  )
}

export { NODE_W, NODE_H }
