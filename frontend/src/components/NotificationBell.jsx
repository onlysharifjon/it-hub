import { useEffect, useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBell, faBellSlash, faCheckDouble } from '@fortawesome/free-solid-svg-icons'
import { fetchNotifications, fetchUnreadCount, markNotificationRead, markAllNotificationsRead } from '../api'

const fmtDate = (s) => s ? new Date(s).toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' }) : ''

/**
 * Bildirishnomalar menyusi.
 *
 * Ilgari bu komponent Leads.jsx ichida yopiq turgan va faqat Lidlar sahifasida
 * ko'rinardi — ya'ni boshqa sahifada ishlayotgan xodim yangi bildirishnomani
 * umuman ko'rmasdi. Endi topbar'da, butun ilova bo'ylab.
 */
export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const wrapRef = useRef(null)

  useEffect(() => {
    refreshCount()
    const t = setInterval(refreshCount, 30000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    function onKey(e) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  async function refreshCount() {
    try { const r = await fetchUnreadCount(); setCount(r.count || 0) } catch { /* jim */ }
  }

  async function toggle() {
    const next = !open
    setOpen(next)
    if (next) {
      setLoading(true)
      try { setItems(await fetchNotifications()) } catch { /* jim */ }
      finally { setLoading(false) }
    }
  }

  async function openItem(n) {
    if (!n.is_read) {
      try { await markNotificationRead(n.id); refreshCount() } catch { /* jim */ }
    }
    setItems(list => list.map(x => x.id === n.id ? { ...x, is_read: true } : x))
  }

  async function readAll() {
    try {
      await markAllNotificationsRead()
      setItems(list => list.map(x => ({ ...x, is_read: true })))
      setCount(0)
    } catch { /* jim */ }
  }

  const unread = items.filter(n => !n.is_read).length

  return (
    <div className="bell-wrap" ref={wrapRef}>
      <button
        className="bell-btn"
        onClick={toggle}
        title="Bildirishnomalar"
        aria-label={count > 0 ? `Bildirishnomalar (${count} o'qilmagan)` : 'Bildirishnomalar'}
        aria-expanded={open}
      >
        <FontAwesomeIcon icon={faBell} />
        {count > 0 && <span className="bell-badge">{count > 99 ? '99+' : count}</span>}
      </button>

      {open && (
        <div className="notif-dropdown" role="dialog" aria-label="Bildirishnomalar">
          <div className="notif-head">
            <h4>Bildirishnomalar {unread > 0 && <span className="notif-unread-count">{unread}</span>}</h4>
            {unread > 0 && (
              <button className="notif-readall" onClick={readAll}>
                <FontAwesomeIcon icon={faCheckDouble} /> Hammasini o'qildi
              </button>
            )}
          </div>

          <div className="notif-body">
            {loading && <div className="notif-loading"><span className="ui-skeleton" style={{ height: 40 }} /><span className="ui-skeleton" style={{ height: 40 }} /></div>}

            {!loading && items.length === 0 && (
              <div className="notif-empty">
                <FontAwesomeIcon icon={faBellSlash} />
                <div className="notif-empty-title">Bildirishnomalar yo'q</div>
                <div className="notif-empty-sub">Yangi lid yoki eslatma paydo bo'lsa shu yerda ko'rinadi.</div>
              </div>
            )}

            {!loading && items.map(n => (
              <button
                key={n.id}
                className={`notif-item${n.is_read ? '' : ' unread'}`}
                onClick={() => openItem(n)}
              >
                {!n.is_read && <span className="notif-dot" aria-hidden="true" />}
                <span className="ni-main">
                  <span className="ni-title">{n.title}</span>
                  {n.body && <span className="ni-body">{n.body}</span>}
                  <span className="ni-time">{fmtDate(n.created_at)}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
