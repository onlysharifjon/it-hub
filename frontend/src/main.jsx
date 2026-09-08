import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { initTheme } from './theme'
import './styles.css'
import './design.css'
import './workspace.css'
import './studio.css'
import './auth.css'

// Mavzu React'dan OLDIN o'rnatiladi (index.html dagi skript allaqachon
// atributni qo'ygan; bu yerda OS/boshqa-tab kuzatuvchilari ulanadi).
initTheme()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

