import { LINK_TONE, LINK_LABEL, LEGEND_ORDER } from './layout'

/**
 * Afsona + foizlarning ta'rifi.
 *
 * Ikkinchi qator ("Foizlar") atayin qo'shildi: daraxtda ikki xil foiz bor va
 * ularni aralashtirib yuborish oson edi. Endi ta'rif ekranda, hujjatda emas.
 */
export default function TreeLegend({ tones }) {
  const shown = LEGEND_ORDER.filter(t => !tones || tones.has(t))
  return (
    <div className="tree-legend">
      <div className="tl-row">
        {shown.map(t => (
          <span key={t} className="tl-item">
            <span className="tl-line" style={{ background: LINK_TONE[t] }} />
            {LINK_LABEL[t]}
          </span>
        ))}
      </div>
      <div className="tl-row tl-defs">
        <span className="tl-def">
          <strong>Tugundagi %</strong> — kogortadagi barcha lidlarga nisbatan
        </span>
        <span className="tl-def">
          <strong>Chiziqdagi %</strong> — chiqish bosqichiga yetgan lidlarga nisbatan
        </span>
      </div>
    </div>
  )
}
