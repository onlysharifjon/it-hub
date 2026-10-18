import {useEffect,useRef,useState} from 'react'
import {spaceStaff} from '../api'
import './SpaceWorkflows.css'
import './SpaceGuides.css'

function currentGuide() {
  const prefix = '#space_guides/'
  if (!window.location.hash.startsWith(prefix)) return ''
  const name = window.location.hash.slice(prefix.length)
  try { return decodeURIComponent(name) } catch { return name }
}

function GuideReader({name}) {
  const [guide,setGuide] = useState(null)
  const [error,setError] = useState('')
  const [attempt,setAttempt] = useState(0)
  const heading = useRef(null)
  const top = useRef(null)

  useEffect(() => {
    let active = true
    setError('')
    setGuide(null)
    spaceStaff.get('/guides/'+encodeURIComponent(name)+'/content')
      .then(data => { if (active) setGuide(data) })
      .catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  },[name,attempt])

  useEffect(() => {
    if (guide) {
      heading.current?.focus({preventScroll:true})
      top.current?.scrollIntoView({block:'start'})
    }
  },[guide])

  const goToSection = index => {
    const section = document.getElementById('guide-section-'+index)
    section?.focus({preventScroll:true})
    section?.scrollIntoView({block:'start'})
  }

  return <div ref={top} className="space-workspace space-guides guide-reader">
    <div><a className="btn" href="#space_guides">← Yo‘riqnomalarga qaytish</a></div>
    {error && <div role="alert" className="sp-error">
      <p>Yo‘riqnomani ochib bo‘lmadi. {error}</p>
      <button className="btn" onClick={() => setAttempt(n => n+1)}>Qayta urinish</button>
    </div>}
    {!guide && !error && <p role="status">Yo‘riqnoma yuklanmoqda…</p>}
    {guide && <>
      <header className="guide-heading">
        <span className="sp-badge">Yo‘riqnoma · {guide.version}</span>
        <h1 ref={heading} tabIndex={-1}>{guide.title}</h1>
        <p>{guide.subtitle}</p>
      </header>
      <div className="guide-layout">
        <nav className="sp-card guide-toc" aria-label="Yo‘riqnoma mundarijasi">
          <h2>Mundarija</h2>
          <ol>{guide.sections.map((section,index) => <li key={index}>
            <button onClick={() => goToSection(index)}>{section.title}</button>
          </li>)}</ol>
        </nav>
        <article className="sp-card guide-document" aria-label={guide.title}>
          {guide.sections.map((section,index) => <section key={index} aria-labelledby={'guide-section-'+index}>
            <h2 id={'guide-section-'+index} tabIndex={-1}>{index+1}. {section.title}</h2>
            {section.blocks.map((block,i) => <div className="guide-block" key={i}>
              <h3>{block.title}</h3>
              <p>{block.body}</p>
            </div>)}
          </section>)}
          <a className="btn" href="#space_guides">← Yo‘riqnomalarga qaytish</a>
        </article>
      </div>
    </>}
  </div>
}

function GuideList() {
  const [items,setItems] = useState(null)
  const [status,setStatus] = useState(null)
  const [error,setError] = useState('')
  const [statusError,setStatusError] = useState('')
  const [attempt,setAttempt] = useState(0)
  const top = useRef(null)

  useEffect(() => { top.current?.scrollIntoView({block:'start'}) },[])

  useEffect(() => {
    let active = true
    setError('')
    spaceStaff.get('/guides')
      .then(files => { if (active) setItems(files) })
      .catch(e => { if (active) setError(e.message) })
    const loadStatus = () => spaceStaff.get('/system-status')
      .then(health => { if (active) { setStatus(health);setStatusError('') } })
      .catch(() => { if (active) setStatusError('Tizim holatini yangilab bo‘lmadi.') })
    loadStatus()
    const timer = setInterval(loadStatus,60000)
    return () => { active = false;clearInterval(timer) }
  },[attempt])

  return <div ref={top} className="space-workspace space-guides">
    <header><h1>Yo‘riqnomalar</h1><p>SPACE bo‘yicha bajarilgan ishlar va foydalanish yo‘riqnomalari. Hujjatni tanlab, alohida sahifada o‘qing. Faqat superadmin uchun.</p></header>
    {error && <div role="alert" className="sp-error"><p>{error}</p><button className="btn" onClick={() => setAttempt(n => n+1)}>Qayta urinish</button></div>}
    <div className="sp-grid guide-cards">{items?.map(guide => <article className="sp-card" key={guide.id}>
      <span className="sp-badge">{guide.id === 'space-changes.pdf' ? 'Bajarilgan ishlar' : 'Foydalanish yo‘riqnomasi'}</span>
      <h2>{guide.title}</h2>
      <p>{guide.id === 'space-changes.pdf' ? 'Audit tuzatishlari, yangi imkoniyatlar va tekshirish natijalari.' : 'Darslar, vazifalar, buyurtmalar, yordam va portfolio bo‘yicha amaliy qadamlar.'}</p>
      <a className="btn btn-primary" href={'#space_guides/'+encodeURIComponent(guide.id)} aria-label={guide.title+' — Ko‘rish'}>Ko‘rish <span aria-hidden="true">→</span></a>
    </article>)}</div>
    {!items && !error && <p role="status">Yuklanmoqda…</p>}
    {statusError && <div role="alert" className="sp-error"><p>{statusError}</p><button className="btn" onClick={() => setAttempt(n => n+1)}>Qayta urinish</button></div>}
    {status && <section className="sp-card guide-system-status">
      <h2>Tizim holati</h2><p>{status.release}</p>
      <div className="sp-grid">
        <div><h3>Ma’lumotlar bazasi</h3><p>{status.readiness.checks.database ? '✓ Ulangan' : 'Muammo bor'}</p></div>
        <div><h3>So‘rovlar himoyasi</h3><p>{status.readiness.checks.redis ? '✓ Ishlamoqda' : 'Muammo bor'}</p></div>
        <div><h3>O‘quv yordamchisi</h3><p>{status.aiConfigured ? 'AI kaliti sozlangan; javobda amaldagi rejim ko‘rsatiladi' : 'Tayyor o‘quv javoblari. AI kaliti sozlanmagan.'}</p></div>
      </div>
      {status.monitor ? <>
        <p>Oxirgi monitoring: {new Date(status.monitor.checkedAt*1000).toLocaleString('uz-UZ')}{status.monitor.stale ? ' · Ma’lumot eskirgan' : ''}</p>
        {Object.entries(status.monitor.checks||{}).map(([name,problem]) => <p key={name}>{problem ? '⚠' : '✓'} {name}: {problem||'Ishlamoqda'}</p>)}
        <p>Telegram ogohlantirishlari: {status.monitor.telegramConfigured ? 'sozlangan' : 'sozlanmagan; holat shu bo‘limda va server jurnalida ko‘rinadi'}</p>
      </> : <p>Monitoring hisoboti hali kelmagan.</p>}
    </section>}
  </div>
}

export default function SpaceGuides() {
  const [name,setName] = useState(currentGuide)
  useEffect(() => {
    const changed = () => setName(currentGuide())
    window.addEventListener('hashchange',changed)
    return () => window.removeEventListener('hashchange',changed)
  },[])
  return name ? <GuideReader key={name} name={name}/> : <GuideList/>
}
