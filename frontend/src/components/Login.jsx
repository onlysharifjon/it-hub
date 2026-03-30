import { useState } from 'react'

function Login({ onSuccess, error }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [localError, setLocalError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLocalError('')
    setLoading(true)
    try {
      await onSuccess({ username, password })
    } catch (err) {
      setLocalError("Login yoki parol xato")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-header">
          <p className="eyebrow">Kirish</p>
          <h2>Metodika paneli</h2>
          <p className="muted">Iltimos, foydalanuvchi nomi va parolni kiriting.</p>
        </div>
        <form className="form" onSubmit={handleSubmit}>
          <div className="field">
            <label>Login</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              required
            />
          </div>
          <div className="field">
            <label>Parol</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          {(localError || error) && <div className="error">{localError || error}</div>}
          <div className="actions">
            <button className="button primary" type="submit" disabled={loading}>
              {loading ? 'Tekshirilmoqda...' : 'Kirish'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default Login
