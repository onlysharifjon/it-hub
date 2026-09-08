import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faArrowRight, faArrowLeft, faUser, faLock, faEye, faEyeSlash, faLocationDot, faCircleExclamation, faHeadset, faGraduationCap } from '@fortawesome/free-solid-svg-icons'
import BrandLogo from './ui/BrandLogo'

function Login({ onSuccess, error }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [localError, setLocalError] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [blockInfo, setBlockInfo] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLocalError('')
    setBlockInfo(null)
    setLoading(true)
    try {
      await onSuccess({ username, password })
    } catch (err) {
      if (err.status === 403 && err.detail?.code) {
        setBlockInfo(err.detail)
      } else {
        setLocalError('Login yoki parol xato')
      }
    } finally {
      setLoading(false)
    }
  }

  const message = localError || error

  return (
    <main className="login-scene">
      <div className="auth-landscape" aria-hidden="true">
        <img src="/art/bukhara-night.webp" alt="" width="1536" height="1024" decoding="async" />
        <div className="auth-landscape-shade" />
      </div>
      <div className="auth-ambient auth-ambient-blue" aria-hidden="true" />
      <div className="auth-ambient auth-ambient-violet" aria-hidden="true" />

      <header className="auth-topbar">
        <BrandLogo variant="full" tone="white" height={34} />
        <span className="auth-platform"><FontAwesomeIcon icon={faGraduationCap} /><span>Ta’lim boshqaruvi</span><i />LMS</span>
      </header>

      <div className="auth-layout">
        <section className="auth-story" aria-label="Minar Academy">
          <span className="auth-story-kicker"><i /> MEROSDAN ILHOM. KELAJAKKA QADAM.</span>
          <h1>Ilmga intilish.<br /><span>Yangi ufqlar.</span></h1>
          <p>Ta’lim, insonlar va imkoniyatlar —<br />barchasi bir maydonda.</p>
          <div className="auth-place"><span><FontAwesomeIcon icon={faLocationDot} /></span><div><strong>Buxoro, O‘zbekiston</strong><small>Minorai Kalon</small></div><i /></div>
        </section>

        <section className="auth-card" aria-label="Tizimga kirish">
          <div className="auth-card-light" aria-hidden="true" />
          {blockInfo ? (
            <div className="auth-block" role="alert">
              <span className="auth-card-icon is-blocked"><FontAwesomeIcon icon={faLock} /></span>
              <span className="auth-eyebrow">Shaxsiy kabinet</span>
              <h2>Kirish mumkin emas</h2>
              <p className="auth-description">Akkauntingizga kirish cheklangan.</p>
              <dl className="auth-block-facts">
                <div><dt>Sabab</dt><dd>{blockInfo.code === 'expired' ? 'Akkount muddati tugagan' : blockInfo.reason || 'Akkauntga kirish cheklangan'}</dd></div>
                {blockInfo.contact && <div><dt>Bog‘lanish uchun</dt><dd>{blockInfo.contact}</dd></div>}
              </dl>
              <button className="auth-submit is-secondary" type="button" onClick={() => setBlockInfo(null)}><FontAwesomeIcon icon={faArrowLeft} />Orqaga</button>
            </div>
          ) : (
            <>
              <header className="auth-card-heading">
                <span className="auth-card-icon"><BrandLogo variant="mark" tone="white" size="md" /></span>
                <span className="auth-eyebrow">Shaxsiy kabinet</span>
                <h2>Xush kelibsiz<span>.</span></h2>
                <p className="auth-description">Davom etish uchun tizimga kiring.</p>
              </header>

              <form className="auth-form" onSubmit={handleSubmit} aria-busy={loading}>
                <div className="auth-field">
                  <label htmlFor="login-username">Foydalanuvchi nomi</label>
                  <div className="auth-input-wrap">
                    <FontAwesomeIcon icon={faUser} className="auth-input-icon" />
                    <input id="login-username" className="auth-input" name="username" type="text" value={username} onChange={e => setUsername(e.target.value)} placeholder="Loginingizni kiriting" autoComplete="username" autoCapitalize="none" spellCheck={false} required aria-invalid={!!message} aria-describedby={message ? 'login-error' : undefined} />
                  </div>
                </div>
                <div className="auth-field">
                  <label htmlFor="login-password">Parol</label>
                  <div className="auth-input-wrap">
                    <FontAwesomeIcon icon={faLock} className="auth-input-icon" />
                    <input id="login-password" className="auth-input" name="password" type={showPass ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} placeholder="Parolingizni kiriting" autoComplete="current-password" required aria-invalid={!!message} aria-describedby={message ? 'login-error' : undefined} />
                    <button type="button" className="auth-eye" onClick={() => setShowPass(v => !v)} aria-label={showPass ? 'Parolni yashirish' : 'Parolni ko‘rsatish'} aria-pressed={showPass}><FontAwesomeIcon icon={showPass ? faEyeSlash : faEye} /></button>
                  </div>
                </div>
                {message && <div className="auth-error" id="login-error" role="alert"><FontAwesomeIcon icon={faCircleExclamation} /><span>{message}</span></div>}
                <button className="auth-submit" type="submit" disabled={loading}>
                  {loading ? <><span className="auth-spinner" aria-hidden="true" /><span>Kirilmoqda…</span></> : <><span>Kirish</span><FontAwesomeIcon icon={faArrowRight} /></>}
                </button>
              </form>

              <div className="auth-help"><FontAwesomeIcon icon={faHeadset} /><p>Kirishda yordam kerak bo‘lsa,<br /><strong>administratorga murojaat qiling.</strong></p></div>
            </>
          )}
        </section>
      </div>

      <footer className="auth-footer"><span>© {new Date().getFullYear()} Minar Academy</span><span>Bilim va imkoniyatlar birlashgan joy.</span></footer>
    </main>
  )
}

export default Login
