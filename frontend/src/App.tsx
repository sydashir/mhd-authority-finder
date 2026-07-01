import { useState } from 'react'
import { ProspectsScreen } from './components/ProspectsScreen'
import { RunsScreen } from './components/RunsScreen'
import { Sidebar, type View } from './components/Sidebar'
import { Toast, type ToastData } from './components/Toast'
import { useTheme } from './lib/theme'

function App() {
  const { theme, toggle } = useTheme()
  const [view, setView] = useState<View>('prospects')
  const [toast, setToast] = useState<ToastData | null>(null)

  return (
    <div className="flex h-full">
      <Sidebar active={view} onNavigate={setView} theme={theme} onToggleTheme={toggle} />
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
