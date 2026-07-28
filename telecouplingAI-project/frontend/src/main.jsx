import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import AdminErrors from './AdminErrors.jsx'
import './index.css'

const isAdminErrors = window.location.pathname.startsWith('/admin/errors')

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {isAdminErrors ? <AdminErrors /> : <App />}
  </React.StrictMode>,
)