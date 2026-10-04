import { useState } from 'react'
import { describeDelta } from '../lib/format'

export function Card({ className = '', children }) {
  return (
    <div className={`rounded-lg bg-surface shadow-sm ring-1 ring-black/5 ${className}`}>{children}</div>
  )
}

/** Card with a Goodwill-blue top rule and an uppercase eyebrow heading. */
export function Panel({ eyebrow, className = '', children }) {
  return (
    <Card className={`border-t-[3px] border-brand p-5 ${className}`}>
      {eyebrow && (
        <h3 className="mb-4 text-xs font-bold uppercase tracking-wide text-brand">{eyebrow}</h3>
      )}
      {children}
    </Card>
  )
}

export function SectionHeader({ eyebrow, title, subtitle, children }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && (
          <p className="text-xs font-medium uppercase tracking-wider text-brand">{eyebrow}</p>
        )}
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-3xl">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-ink-2 sm:text-base">{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}

/**
 * A change indicator. `better` is 'up' or 'down'; the color reflects whether
 * the change is good, and the arrow + text carry it without color.
 */
export function Delta({ delta, better = 'up', suffix = 'vs prior month' }) {
  const d = describeDelta(delta, better)
  if (!d) return null
  const { flat, good, text, arrow } = d
  const tone = flat ? 'text-ink-3' : good ? 'text-good' : 'text-critical'
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold ${tone}`}>
      <span aria-hidden="true">{arrow}</span>
      <span className="tabular">{text}</span>
      <span className="font-normal text-ink-3">{suffix}</span>
    </span>
  )
}

/** Compact rounded change pill: blue when good, red when bad, gray when flat. */
export function DeltaPill({ delta, better = 'up', inverted = false }) {
  const d = describeDelta(delta, better)
  if (!d) return null
  const { flat, good, text, arrow } = d
  const tone = inverted
    ? 'bg-white/15 text-white'
    : flat
      ? 'bg-black/5 text-ink-3'
      : good
        ? 'bg-brand-tint text-brand'
        : 'bg-critical/10 text-critical'
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>
      <span aria-hidden="true" className="text-[10px]">
        {arrow}
      </span>
      <span className="tabular">{text}</span>
      {!flat && <span className="sr-only">{good ? '(improved)' : '(worsened)'}</span>}
    </span>
  )
}

export function StatTile({ label, value, delta, better, deltaSuffix, sub, emphasis = false }) {
  return (
    <Card className={`flex flex-col gap-1 p-4 ${emphasis ? 'ring-brand/40' : ''}`}>
      <span className="text-xs font-medium uppercase tracking-wide text-ink-3">{label}</span>
      <span className={`text-2xl font-bold ${emphasis ? 'text-brand' : 'text-ink'}`}>{value}</span>
      {delta !== undefined && <Delta delta={delta} better={better} suffix={deltaSuffix} />}
      {sub && <span className="text-xs text-ink-3">{sub}</span>}
    </Card>
  )
}

export function Tabs({ tabs, value, onChange, size = 'md' }) {
  return (
    <div role="tablist" className="inline-flex rounded-lg bg-page p-1 ring-1 ring-black/10">
      {tabs.map((t) => {
        const active = t.id === value
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.id)}
            className={`rounded-md font-semibold transition-colors ${size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-4 py-2 text-sm'} ${
              active ? 'bg-brand text-white' : 'text-ink-2 hover:bg-black/5 hover:text-ink'
            }`}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}

export function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wide text-ink-3">{label}</span>
      {children}
    </label>
  )
}

export const inputClass =
  'rounded-md bg-surface px-3 py-2 text-sm font-medium text-ink ring-1 ring-black/15 outline-none focus:ring-2 focus:ring-brand'

export function IconButton({ label, onClick, disabled, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="rounded-md bg-surface px-3 py-2 text-sm text-ink ring-1 ring-black/15 hover:bg-page disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  )
}

export function Badge({ children }) {
  return (
    <span className="inline-flex items-center rounded-full bg-brand-tint px-2.5 py-0.5 text-xs font-semibold text-brand ring-1 ring-brand/20">
      {children}
    </span>
  )
}

export function LoadState({ loading, error, children }) {
  if (error) {
    return (
      <Card className="p-6 text-sm text-critical">
        Couldn’t load this report: {error.message}
      </Card>
    )
  }
  return (
    <div className={`transition-opacity ${loading ? 'pointer-events-none opacity-50' : ''}`} aria-busy={loading}>
      {children}
    </div>
  )
}

/**
 * Card that collapses to a single clickable header row. `summary` shows under
 * the title; `actions` (e.g. tabs) appear on the right only while open.
 */
export function Disclosure({ title, summary, actions, defaultOpen = false, className = '', children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Card className={className}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex items-center gap-3 text-left">
          <span className={`text-brand transition-transform ${open ? 'rotate-90' : ''}`} aria-hidden="true">
            ▶
          </span>
          <span>
            <span className="block text-base font-bold tracking-tight text-ink">{title}</span>
            {summary && <span className="block text-sm text-ink-3">{summary}</span>}
          </span>
        </button>
        {open && actions}
      </div>
      {open && <div className="border-t border-black/5 bg-page/60 p-5">{children}</div>}
    </Card>
  )
}

export function Swatch({ color }) {
  return <span className="inline-block size-2.5 shrink-0 rounded-sm" style={{ backgroundColor: color }} />
}
