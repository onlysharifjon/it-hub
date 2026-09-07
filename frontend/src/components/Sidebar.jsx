import { useEffect, useState } from 'react'
import BrandLogo from './ui/BrandLogo'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faChevronDown, faAnglesLeft, faAnglesRight, faHeadset } from '@fortawesome/free-solid-svg-icons'
import { fetchFeedbackNewCount } from '../api'
import { navForRole, groupIdForPage } from '../constants/nav'

const CATEGORIES = [
  { key: 'foundation', label: 'Foundation' },
  { key: 'frontend',   label: 'Frontend' },
  { key: 'backend',    label: 'Backend' },
]

const COLLAPSE_KEY = 'sidebar:collapsedGroups'
const RAIL_KEY = 'sidebar:rail'

function Sidebar({
  selectedCategory, onSelectCategory,
  currentUser, activePage, onNavigate, isOpen,
}) {
  const role = currentUser?.role
  const groups = navForRole(role)

  // Yig'ilgan guruhlar — brauzerda eslab qolinadi
  const [collapsed, setCollapsed] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '[]')) }
    catch { return new Set() }
  })
  // Tor "rail" rejimi (faqat ikonkalar)
  const [rail, setRail] = useState(() => localStorage.getItem(RAIL_KEY) === '1')
  const [catOpen, setCatOpen] = useState(activePage === 'lessons')

  useEffect(() => {
    try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...collapsed])) } catch {}
  }, [collapsed])
  useEffect(() => {
    localStorage.setItem(RAIL_KEY, rail ? '1' : '0')
    document.body.classList.toggle('has-rail-sidebar', rail)
  }, [rail])

  // Joriy sahifa yopiq guruhda bo'lsa — o'sha guruhni ochib qo'yamiz
  useEffect(() => {
    const gid = groupIdForPage(role, activePage)
    if (gid && collapsed.has(gid)) {
      setCollapsed(prev => { const n = new Set(prev); n.delete(gid); return n })
    }
  }, [activePage, role])

  // Yangi (hal qilinmagan) izohlar soni — qizil badge
  const canSeeFeedbacks = role === 'call_center' || role === 'admin'
  const [feedbackCount, setFeedbackCount] = useState(0)
  useEffect(() => {
    if (!canSeeFeedbacks) return
    let alive = true
    async function refresh() {
      try {
        const r = await fetchFeedbackNewCount()
        if (alive) setFeedbackCount(r.count || 0)
      } catch { /* jim — badge ikkilamchi */ }
    }
    refresh()
    const t = setInterval(refresh, 60000)
    window.addEventListener('feedbacks-changed', refresh)
    return () => { alive = false; clearInterval(t); window.removeEventListener('feedbacks-changed', refresh) }
  }, [canSeeFeedbacks])

  function toggleGroup(id) {
    setCollapsed(prev => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  function handleItemClick(item) {
    if (item.expandable === 'categories') {
      if (activePage === 'lessons') { setCatOpen(v => !v); return }
      setCatOpen(true)
    }
    onNavigate(item.key)
  }

  function isActive(item) {
    return activePage === item.key || item.alsoActiveOn?.includes(activePage)
  }

  return (
    <aside className={`sidebar${isOpen ? ' mobile-open' : ''}${rail ? ' is-rail' : ''}`}>
      <div className="brand">
        {/* Yig'ilgan holatda to'liq lokap o'qilmaydigan darajada kichrayadi —
            shuning uchun CSS bilan siqilmaydi, balki BELGIGA almashtiriladi. */}
        {rail
          ? <BrandLogo variant="mark" size="lg" />
          : <BrandLogo variant="full" height={24} />}
        {/* Yig'ilgan holatda 64px kenglikka logotip ham, tugma ham sig'maydi —
            tugma pastdagi qatorga o'tadi, brend qatori esa faqat belgiga
            qoladi va u markazda turadi. */}
        {!rail && (
          <button
            className="rail-toggle"
            onClick={() => setRail(true)}
            title="Menyuni yig'ish"
            aria-label="Menyuni yig'ish"
          >
            <FontAwesomeIcon icon={faAnglesLeft} />
          </button>
        )}
      </div>

      <nav className="sidebar-nav" aria-label="Asosiy menyu">
        {groups.map(group => {
          const isCollapsed = collapsed.has(group.id) && !rail
          return (
            <div key={group.id} className="nav-group">
              {!rail && (
                <button
                  className={`nav-section-label is-toggle${isCollapsed ? ' collapsed' : ''}`}
                  onClick={() => toggleGroup(group.id)}
                  aria-expanded={!isCollapsed}
                >
                  <span>{group.label}</span>
                  <FontAwesomeIcon icon={faChevronDown} className="nav-group-chevron" />
                </button>
              )}

              <div className={`nav-group-items${isCollapsed ? ' collapsed' : ''}`}>
                {group.items.map(item => {
                  const active = isActive(item)
                  // Lidlar ikonkasi rolga qarab (eski xatti-harakat saqlandi)
                  const icon = item.key === 'leads' && role !== 'hunter' ? faHeadset : item.icon
                  return (
                    <div key={item.key}>
                      <button
                        className={`nav-page-btn ${active ? 'active' : ''}`}
                        // Modul rangi faqat hover'da ochiladi (styles.css) —
                        // tinch holatda barcha ikonkalar neytral qoladi.
                        style={item.tone ? { '--mod': item.tone } : undefined}
                        onClick={() => handleItemClick(item)}
                        title={rail ? item.label : undefined}
                        aria-current={active ? 'page' : undefined}
                      >
                        <FontAwesomeIcon icon={icon} fixedWidth />
                        {!rail && <span className="nav-label">{item.label}</span>}
                        {!rail && item.badge === 'feedback' && feedbackCount > 0 && (
                          <span className="nav-badge">{feedbackCount > 99 ? '99+' : feedbackCount}</span>
                        )}
                        {rail && item.badge === 'feedback' && feedbackCount > 0 && <span className="nav-dot" />}
                        {!rail && item.expandable === 'categories' && (
                          <span className={`cat-chevron${catOpen && activePage === 'lessons' ? ' open' : ''}`}>
                            <FontAwesomeIcon icon={faChevronDown} />
                          </span>
                        )}
                      </button>

                      {item.expandable === 'categories' && !rail && (
                        <div className={`category-list-wrap${catOpen && activePage === 'lessons' ? ' open' : ''}`}>
                          <div className="category-list">
                            {CATEGORIES.map((c, i) => (
                              <button
                                key={c.key}
                                className={`category-btn ${selectedCategory === c.key ? 'active' : ''}`}
                                onClick={() => {
                                  onSelectCategory(c.key)
                                  if (activePage !== 'lessons') onNavigate('lessons')
                                }}
                                style={{ animationDelay: `${i * 40}ms` }}
                              >
                                {c.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </nav>

      {rail ? (
        <div className="sidebar-foot is-rail">
          <button
            className="rail-toggle"
            onClick={() => setRail(false)}
            title="Menyuni kengaytirish"
            aria-label="Menyuni kengaytirish"
          >
            <FontAwesomeIcon icon={faAnglesRight} />
          </button>
        </div>
      ) : (
        <div className="sidebar-foot">
          <span>Minar Academy LMS</span>
          <span>v3.0</span>
        </div>
      )}
    </aside>
  )
}

export default Sidebar
