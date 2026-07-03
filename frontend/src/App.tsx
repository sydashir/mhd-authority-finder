import { useState } from 'react'
import { useMe } from './api/hooks'
import { Login } from './components/Login'
import { Logo } from './components/Logo'
import { ProspectsScreen } from './components/ProspectsScreen'
import { RunsScreen } from './components/RunsScreen'
import { Sidebar, type View } from './components/Sidebar'
import { Toast, type ToastData } from './components/Toast'
import { useTheme } from './lib/theme'

function App() {
  const { theme, toggle } = useTheme()
  const me = useMe()
  const [view, setView] = useState<View>('prospects')
  const [toast, setToast] = useState<ToastData | null>(null)

  if (me.isPending) {
    return (
      <div className="flex h-full items-center justify-center bg-app">
        <span className="animate-pulse text-brand">
          <Logo size={34} />
        </span>
      </div>
    )
  }

  // No session (401 / error) -> the login screen. The auth gate. We check isError
  // too: TanStack Query retains the last user on a refetch error, so after logout
  // the 401 refetch must still flip us back to Login.
  if (me.isError || !me.data) return <Login />

  return (
    <div className="flex h-full">
      <Sidebar
        active={view}
        onNavigate={setView}
        theme={theme}
        onToggleTheme={toggle}
        user={me.data}
      />
      {view === 'prospects' ? (
        <ProspectsScreen notify={setToast} />
      ) : (
        <RunsScreen notify={setToast} />
      )}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  )
}

export default App
