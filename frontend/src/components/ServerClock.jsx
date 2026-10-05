import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faClock } from '@fortawesome/free-solid-svg-icons'
import { fetchServerTime } from '../api'

const SYNC_MS = 30_000

const fmtTime = new Intl.DateTimeFormat('uz-UZ', {
  timeZone: 'Asia/Tashkent', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
})
const fmtDate = new Intl.DateTimeFormat('uz-UZ', {
  timeZone: 'Asia/Tashkent', day: '2-digit', month: '2-digit', year: 'numeric',
})

/**
 * Server soati: kirishda bir marta va keyin har 30 soniyada GET qilinadi
 * (socket emas). Oraliqda server bilan farq (offset) asosida har soniyada
 * mahalliy ravishda yuradi — kompyuter soati noto'g'ri bo'lsa ham to'g'ri ko'rinadi.
 */
export default function ServerClock() {
  const [offset, setOffset] = useState(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    let alive = true
    async function sync() {
      const sent = Date.now()
      try {
        const { epoch_ms } = await fetchServerTime()
        const received = Date.now()
        // So'rov yo'lda o'tgan vaqtning yarmini hisobga olamiz
        if (alive) setOffset(epoch_ms - (sent + received) / 2)
      } catch { /* keyingi urinishda qayta sinxronlanadi */ }
    }
    sync()
    const syncId = setInterval(sync, SYNC_MS)
    const tickId = setInterval(() => setNow(Date.now()), 1000)
    return () => { alive = false; clearInterval(syncId); clearInterval(tickId) }
  }, [])

  if (offset === null) return null
  const serverNow = new Date(now + offset)
  return (
    <div className="topbar-clock" title={`Server vaqti (Toshkent) · ${fmtDate.format(serverNow)}`}>
      <FontAwesomeIcon icon={faClock} />
      <time dateTime={serverNow.toISOString()}>{fmtTime.format(serverNow)}</time>
    </div>
  )
}
