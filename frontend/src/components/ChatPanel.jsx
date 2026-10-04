import { useEffect, useRef, useState } from 'react'

// The chatbot runs as its own service (see chatbot/README.md).
const CHAT_URL = import.meta.env.VITE_CHAT_URL || 'http://127.0.0.1:8001'

const SUGGESTIONS = [
  'What was revenue by marketplace in September 2026?',
  'Which subcategories have the most relisted items?',
  'What is the average number of days to sell on each marketplace?',
  'How many eBay buyers ordered more than once in 2025?',
]

/** Floating "Ask the data" chat. Every answer comes from read-only database
 *  queries, and each one shows the SQL and rows it was built from. */
export default function ChatPanel() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([]) // { role, content, sources?, verified? }
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const scroller = useRef(null)

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  async function ask(question) {
    const text = question.trim()
    if (!text || busy) return
    const history = [...messages, { role: 'user', content: text }]
    setMessages(history)
    setDraft('')
    setError(null)
    setBusy(true)
    try {
      const res = await fetch(`${CHAT_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history.map(({ role, content }) => ({ role, content })).slice(-20) }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${res.status})`)
      setMessages([...history, { role: 'assistant', content: body.answer, sources: body.sources, verified: body.verified }])
    } catch (e) {
      setError(e.message === 'Failed to fetch' ? 'The chatbot service is not running (see chatbot/README.md).' : e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-30 flex items-center gap-2 rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white shadow-lg hover:bg-brand-dark"
      >
        <span aria-hidden="true">💬</span> Ask the data
      </button>
    )
  }

  return (
    <section
      aria-label="Ask the data"
      className="fixed bottom-6 right-6 z-30 flex h-[min(640px,calc(100vh-3rem))] w-[min(440px,calc(100vw-3rem))] flex-col overflow-hidden rounded-xl bg-surface shadow-2xl ring-1 ring-black/10"
    >
      <header className="flex items-start justify-between gap-3 bg-brand px-4 py-3 text-white">
        <div>
          <div className="font-bold">Ask the data</div>
          <div className="text-xs text-white/80">Answers come only from the database, with the queries shown.</div>
        </div>
        <button type="button" onClick={() => setOpen(false)} aria-label="Close chat" className="rounded px-2 text-lg hover:bg-white/15">
          ×
        </button>
      </header>

      <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto bg-page p-4 text-sm">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-ink-2">Ask about sales, listings, categories, buyers, fees or refunds. Try:</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                className="block w-full rounded-lg bg-surface px-3 py-2 text-left text-brand ring-1 ring-black/10 hover:bg-brand-tint"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="ml-8 rounded-lg bg-brand px-3 py-2 text-white">
              {m.content}
            </div>
          ) : (
            <Answer key={i} message={m} />
          ),
        )}

        {busy && <div className="text-ink-3">Querying the database…</div>}
        {error && <div className="rounded-lg bg-critical/10 px-3 py-2 text-critical">{error}</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          ask(draft)
        }}
        className="flex gap-2 border-t border-black/10 bg-surface p-3"
      >
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              ask(draft)
            }
          }}
          rows={2}
          placeholder="Ask a question about the data…"
          className="flex-1 resize-none rounded-md bg-page px-3 py-2 text-sm text-ink outline-none ring-1 ring-black/10 focus:ring-2 focus:ring-brand"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="self-end rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </section>
  )
}

function Answer({ message }) {
  const queries = (message.sources || []).filter((s) => !s.error)
  return (
    <div className="mr-4 rounded-lg bg-surface px-3 py-2 text-ink ring-1 ring-black/10">
      <div className="whitespace-pre-wrap">{message.content}</div>
      <div className={`mt-2 text-xs font-medium ${message.verified ? 'text-brand' : 'text-critical'}`}>
        {message.verified
          ? queries.length
            ? `✓ Every figure checked against ${queries.length} database ${queries.length === 1 ? 'query' : 'queries'}`
            : '✓ No figures stated'
          : '⚠ Not verified'}
      </div>
      {message.sources?.length > 0 && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer font-medium text-ink-2 hover:text-brand">
            Show queries & rows ({message.sources.length})
          </summary>
          <div className="mt-2 space-y-3">
            {message.sources.map((s, i) => (
              <Source key={i} source={s} />
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

function Source({ source }) {
  const preview = (source.rows || []).slice(0, 10)
  return (
    <div className="rounded-md bg-page p-2">
      {source.purpose && <div className="mb-1 font-medium text-ink-2">{source.purpose}</div>}
      <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-ink/90 p-2 font-mono text-[11px] text-white">{source.sql}</pre>
      {source.error ? (
        <div className="mt-1 text-critical">Query failed: {source.error}</div>
      ) : (
        <div className="mt-1 overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr>
                {source.columns.map((c) => (
                  <th key={c} className="pr-3 font-semibold text-ink-2">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((row, r) => (
                <tr key={r} className="border-t border-black/5">
                  {row.map((cell, c) => (
                    <td key={c} className="tabular pr-3 text-ink">
                      {cell === null ? '—' : String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {source.row_count > preview.length && (
            <div className="mt-1 text-ink-3">
              Showing {preview.length} of {source.row_count}
              {source.truncated ? '+' : ''} rows
            </div>
          )}
        </div>
      )}
    </div>
  )
}
