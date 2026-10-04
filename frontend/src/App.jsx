import { useEffect, useState } from 'react'
import ChatPanel from './components/ChatPanel'
import { Tabs } from './components/ui'
import DailyView from './views/DailyView'
import MonthlyView from './views/MonthlyView'

const TABS = [
  { id: 'daily', label: 'Daily Report' },
  { id: 'monthly', label: 'Monthly Analytics' },
]

// Keep the open tab in the URL hash so refreshes and shared links land on it.
function useHashTab() {
  const read = () => {
    const id = window.location.hash.replace('#', '')
    return TABS.some((t) => t.id === id) ? id : 'daily'
  }
  const [tab, setTab] = useState(read)
  useEffect(() => {
    const onHash = () => setTab(read())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const select = (id) => {
    window.history.replaceState(null, '', `#${id}`)
    setTab(id)
  }
  return [tab, select]
}

export default function App() {
  const [tab, setTab] = useHashTab()

  return (
    <>
      <header className="border-b-4 border-brand bg-surface shadow-sm">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-8">
          <div className="flex items-center gap-4">
            <img src="/goodwill-logo.png" alt="Goodwill" className="h-14 w-auto" />
            <div className="border-l border-black/10 pl-4">
              <div className="text-xl font-bold tracking-tight text-ink">Goodwill Michiana</div>
              <div className="text-sm font-medium text-brand">E-Commerce Operations Dashboard</div>
            </div>
          </div>
          <Tabs tabs={TABS} value={tab} onChange={setTab} />
        </div>
      </header>

      <main role="tabpanel" className="mx-auto max-w-7xl px-4 pb-16 pt-8 sm:px-8">
        {tab === 'daily' ? <DailyView /> : <MonthlyView />}
      </main>

      <ChatPanel />
    </>
  )
}
