import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { AuthProvider } from './hooks/useAuth'
import { I18nProvider } from './hooks/useI18n'
import { WorkspaceProvider } from './hooks/useWorkspace'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <I18nProvider>
        <WorkspaceProvider>
          <App />
        </WorkspaceProvider>
      </I18nProvider>
    </AuthProvider>
  </StrictMode>,
)
