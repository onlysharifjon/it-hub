import { useEffect, useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faComments, faMagnifyingGlass, faUserGraduate, faUserTie, faCircleQuestion,
  faCircleCheck, faCircleXmark, faPaperPlane, faInbox,
} from '@fortawesome/free-solid-svg-icons'
import { fetchBotChats, fetchBotChatMessages } from '../api'

const KIND_META = {
  student: { icon: faUserGraduate, label: 'Talaba',  color: '#2563eb' },
  staff:   { icon: faUserTie,      label: 'Xodim',   color: '#7c3aed' },
  unknown: { icon: faCircleQuestion, label: "Noma'lum", color: '#6b7280' },
}

function fmtTime(iso) {
  if (!iso) return ''
  return new Date(iso + 'Z').toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
}
function fmtDay(iso) {
  if (!iso) return ''
  return new Date(iso + 'Z').toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
function fmtListTime(iso) {
  if (!iso) return ''
  const d = new Date(iso + 'Z')
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  return sameDay
    ? d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit' })
}

export default function ChatBot() {
  const [chats, setChats] = useState([])
  const [loadingChats, setLoadingChats] = useState(true)
  const [search, setSearch] = useState('')
  const [activeChat, setActiveChat] = useState(null)
  const [messages, setMessages] = useState([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const threadRef = useRef(null)

  useEffect(() => { loadChats(search) }, [])
  useEffect(() => {
    const t = setInterval(() => loadChats(search, true), 15000)
    return () => clearInterval(t)
  }, [search])

  useEffect(() => {
    if (!activeChat) return
    loadMessages(activeChat.chat_id)
    const t = setInterval(() => loadMessages(activeChat.chat_id, true), 5000)
    return () => clearInterval(t)
  }, [activeChat?.chat_id])

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight
  }, [messages])

  async function loadChats(s = search, silent = false) {
    if (!silent) setLoadingChats(true)
    try {
      const rows = await fetchBotChats(s || undefined)
      setChats(rows)
    } catch { /* fon yangilanishida sokin o'tkazamiz */ }
    finally { setLoadingChats(false) }
  }

  async function loadMessages(chatId, silent = false) {
    if (!silent) setLoadingMessages(true)
    try {
      const rows = await fetchBotChatMessages(chatId, { page_size: 100 })
      setMessages(rows)
    } catch { /* fon yangilanishida sokin o'tkazamiz */ }
    finally { setLoadingMessages(false) }
  }

  function handleSearch(e) {
    const val = e.target.value
    setSearch(val)
    loadChats(val)
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faComments} className="page-icon" /> Chatbot</h1>
      </div>

      <div className="chatbot-layout">
        {/* ── Suhbatlar ro'yxati ── */}
        <div className="chatbot-list">
          <div className="chatbot-search">
            <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
            <input
              className="search-input"
              placeholder="Ism yoki chat ID..."
              value={search}
              onChange={handleSearch}
            />
          </div>

          <div className="chatbot-chats">
            {loadingChats ? (
              <div className="muted center py-8">Yuklanmoqda...</div>
            ) : chats.length === 0 ? (
              <div className="muted center py-8">
                <FontAwesomeIcon icon={faInbox} style={{ fontSize: 22, marginBottom: 8, display: 'block' }} />
                Hozircha suhbatlar yo'q
              </div>
            ) : chats.map(c => {
              const meta = KIND_META[c.kind] || KIND_META.unknown
              const active = activeChat?.chat_id === c.chat_id
              return (
                <button
                  key={c.chat_id}
                  className={`chatbot-chat-row ${active ? 'active' : ''}`}
                  onClick={() => setActiveChat(c)}
                >
                  <div className="chatbot-avatar" style={{ background: `${meta.color}1a`, color: meta.color }}>
                    <FontAwesomeIcon icon={meta.icon} />
                  </div>
                  <div className="chatbot-chat-info">
                    <div className="chatbot-chat-top">
                      <span className="chatbot-chat-name">{c.display_name}</span>
                      <span className="chatbot-chat-time">{fmtListTime(c.last_at)}</span>
                    </div>
                    <div className="chatbot-chat-preview">
                      {c.last_direction === 'out' && (
                        <FontAwesomeIcon
                          icon={c.last_sent_ok ? faCircleCheck : faCircleXmark}
                          style={{ color: c.last_sent_ok ? '#16a34a' : '#dc2626', marginRight: 4, fontSize: 11 }}
                        />
                      )}
                      <span className="chatbot-chat-preview-text">{c.last_text || '—'}</span>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* ── Xabarlar tarixi ── */}
        <div className="chatbot-thread">
          {!activeChat ? (
            <div className="chatbot-empty">
              <FontAwesomeIcon icon={faComments} style={{ fontSize: 32, opacity: .35, marginBottom: 10 }} />
              <div>Suhbatni tanlang</div>
            </div>
          ) : (
            <>
              <div className="chatbot-thread-header">
                {(() => {
                  const meta = KIND_META[activeChat.kind] || KIND_META.unknown
                  return (
                    <>
                      <div className="chatbot-avatar" style={{ background: `${meta.color}1a`, color: meta.color }}>
                        <FontAwesomeIcon icon={meta.icon} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 14.5 }}>{activeChat.display_name}</div>
                        <div className="text-muted" style={{ fontSize: 12 }}>{meta.label} · chat ID: {activeChat.chat_id}</div>
                      </div>
                    </>
                  )
                })()}
              </div>

              <div className="chatbot-thread-body" ref={threadRef}>
                {loadingMessages ? (
                  <div className="muted center py-8">Yuklanmoqda...</div>
                ) : messages.length === 0 ? (
                  <div className="muted center py-8">Xabarlar topilmadi</div>
                ) : (
                  messages.map((m, i) => {
                    const prevDay = i > 0 ? fmtDay(messages[i - 1].created_at) : null
                    const day = fmtDay(m.created_at)
                    return (
                      <div key={m.id}>
                        {day !== prevDay && <div className="chatbot-day-divider"><span>{day}</span></div>}
                        <div className={`chatbot-bubble-row ${m.direction === 'out' ? 'out' : 'in'}`}>
                          <div className={`chatbot-bubble ${m.direction === 'out' ? 'out' : 'in'}`}>
                            {m.message_type === 'auto_notify' && m.direction === 'out' && (
                              <div className="chatbot-bubble-tag">avtomatik xabar</div>
                            )}
                            <div className="chatbot-bubble-text">{m.text || '—'}</div>
                            <div className="chatbot-bubble-meta">
                              {m.direction === 'out' && (
                                <FontAwesomeIcon
                                  icon={m.sent_ok ? faCircleCheck : faCircleXmark}
                                  style={{ color: m.sent_ok ? '#bbf7d0' : '#fecaca', fontSize: 10 }}
                                />
                              )}
                              {fmtTime(m.created_at)}
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
