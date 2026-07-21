import { useState } from 'react'

function Login({ onSuccess, error }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [localError, setLocalError] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [blockInfo, setBlockInfo] = useState(null) // { code, reason, contact }

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

  return (
    <div className="lp-shell">
      {/* ── LEFT PANEL ── */}
      <div className="lp-left">
        <div className="lp-left-inner">
          <div className="lp-logo">
            <span className="lp-logo-icon">IT</span>
            <span className="lp-logo-text">Hub</span>
          </div>

          <div className="lp-hero">
            <h1 className="lp-hero-title">LMS<br />tizimi</h1>
            <p className="lp-hero-sub">
              O'quv markazining barcha jarayonlarini<br />
              yagona platformada boshqaring.
            </p>
          </div>

          <div className="lp-features">
            <div className="lp-feature">
              <span className="lp-feature-dot" />
              Darslar va metodika
            </div>
            <div className="lp-feature">
              <span className="lp-feature-dot" />
              Guruhlar va o'quvchilar
            </div>
            <div className="lp-feature">
              <span className="lp-feature-dot" />
              To'lovlar va davomat
            </div>
          </div>

          <p className="lp-copy">© 2026 IT Hub</p>
        </div>
      </div>

      {/* ── RIGHT PANEL ── */}
      <div className="lp-right">
        <div className="lp-form-wrap">

          {blockInfo ? (
            /* ── BLOCK / EXPIRY PANEL ── */
            <div className="lp-block-panel">
              <div className="lp-block-icon">
                <svg viewBox="0 0 24 24" fill="none" width="48" height="48">
                  <circle cx="12" cy="12" r="10" stroke="#ef4444" strokeWidth="1.8"/>
                  <path d="M4.93 4.93l14.14 14.14" stroke="#ef4444" strokeWidth="1.8" strokeLinecap="round"/>
                </svg>
              </div>
              <h2 className="lp-block-title">Kirish mumkin emas</h2>
              <p className="lp-block-msg">
                Sening akkauntingga kirishni iloji bo'lmayapti.
              </p>
              {blockInfo.code === 'expired' ? (
                <div className="lp-block-detail">
                  <div className="lp-block-label">Sabab</div>
                  <div className="lp-block-value">Akkount muddati tugagan</div>
                </div>
              ) : (
                <div className="lp-block-detail">
                  <div className="lp-block-label">Sabab</div>
                  <div className="lp-block-value">{blockInfo.reason}</div>
                </div>
              )}
              {blockInfo.contact && (
                <div className="lp-block-detail">
                  <div className="lp-block-label">Mana bu contactga bog'lan</div>
                  <div className="lp-block-value lp-block-contact">{blockInfo.contact}</div>
                </div>
              )}
              <button className="lp-btn lp-btn-secondary" onClick={() => setBlockInfo(null)}>
                ← Orqaga
              </button>
            </div>
          ) : (
            /* ── LOGIN FORM ── */
            <>
              <div className="lp-form-header">
                <h2 className="lp-form-title">Xush kelibsiz</h2>
                <p className="lp-form-sub">Davom etish uchun tizimga kiring</p>
              </div>

              <form className="lp-form" onSubmit={handleSubmit}>
                <div className="lp-field">
                  <label className="lp-label">Foydalanuvchi nomi</label>
                  <div className="lp-input-wrap">
                    <svg className="lp-input-icon" viewBox="0 0 20 20" fill="none">
                      <path d="M10 10a4 4 0 100-8 4 4 0 000 8z" stroke="currentColor" strokeWidth="1.5"/>
                      <path d="M2 18c0-3.314 3.582-6 8-6s8 2.686 8 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                    <input
                      className="lp-input"
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Login"
                      autoComplete="username"
                      required
                    />
                  </div>
                </div>

                <div className="lp-field">
                  <label className="lp-label">Parol</label>
                  <div className="lp-input-wrap">
                    <svg className="lp-input-icon" viewBox="0 0 20 20" fill="none">
                      <rect x="3" y="8" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5"/>
                      <path d="M7 8V6a3 3 0 016 0v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                    <input
                      className="lp-input"
                      type={showPass ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Parol"
                      autoComplete="current-password"
                      required
                    />
                    <button
                      type="button"
                      className="lp-eye"
                      onClick={() => setShowPass(v => !v)}
                      tabIndex={-1}
                    >
                      {showPass ? (
                        <svg viewBox="0 0 20 20" fill="none">
                          <path d="M2 10s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z" stroke="currentColor" strokeWidth="1.5"/>
                          <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
                          <path d="M3 3l14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                      ) : (
                        <svg viewBox="0 0 20 20" fill="none">
                          <path d="M2 10s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z" stroke="currentColor" strokeWidth="1.5"/>
                          <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                {(localError || error) && (
                  <div className="lp-error">
                    <svg viewBox="0 0 20 20" fill="none" width="15" height="15">
                      <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
                      <path d="M10 6v4M10 13.5v.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                    </svg>
                    {localError || error}
                  </div>
                )}

                <button className="lp-btn" type="submit" disabled={loading}>
                  {loading ? (
                    <span className="lp-spinner" />
                  ) : (
                    <>
                      Kirish
                      <svg viewBox="0 0 20 20" fill="none" width="16" height="16">
                        <path d="M4 10h12M11 5l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </>
                  )}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default Login
