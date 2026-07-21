import React from 'react'
import ReactDOM from 'react-dom/client'
import '@fontsource-variable/geist'        // self-hosted (CSP-safe), tabular figures
import '@fontsource-variable/geist-mono'   // for numeric / tabular data
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

