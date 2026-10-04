import { useEffect, useRef, useState } from 'react'
import { addDays, addMonths, daysInMonth, formatMonth, monthOf, parseISODate } from '../lib/dates'

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
const pad = (n) => String(n).padStart(2, '0')

/**
 * Page-title selector frame: ← [LABEL / Big title ▾] →.
 * Clicking the title opens `popover`, which receives a `close` callback.
 */
function PickerShell({ label, note, title, prev, next, popover }) {
  const [open, setOpen] = useState(false)
  const wrapper = useRef(null)

  // Close on a click outside the title + popover, or on Escape.
  useEffect(() => {
    if (!open) return
    const onDown = (e) => wrapper.current && !wrapper.current.contains(e.target) && setOpen(false)
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="flex items-center gap-3 sm:gap-4">
      <CircleButton label={prev.label} onClick={prev.onClick} disabled={prev.disabled}>
        ←
      </CircleButton>

      <div className="relative" ref={wrapper}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-haspopup="dialog"
          aria-expanded={open}
          className="group rounded-lg px-2 py-1 text-left hover:bg-black/[0.03]"
        >
          <span className="block text-xs font-semibold uppercase tracking-[0.18em] text-ink-3">
            {label}
            {note && <span className="text-brand"> · {note}</span>}
          </span>
          <span className="flex items-center gap-2 text-3xl font-bold tracking-tight text-ink">
            {title}
            <span className={`text-base text-ink-3 transition-transform group-hover:text-brand ${open ? 'rotate-180' : ''}`} aria-hidden="true">
              ▾
            </span>
          </span>
        </button>
        {open && (
          <div
            role="dialog"
            aria-label={`Choose ${label.toLowerCase()}`}
            className="absolute left-0 top-full z-20 mt-2 w-72 rounded-xl bg-surface p-4 shadow-lg ring-1 ring-black/10"
          >
            {popover(() => setOpen(false))}
          </div>
        )}
      </div>

      <CircleButton label={next.label} onClick={next.onClick} disabled={next.disabled}>
        →
      </CircleButton>
    </div>
  )
}

function CircleButton({ label, onClick, disabled, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="grid size-11 shrink-0 place-items-center rounded-full bg-surface text-lg text-brand shadow-sm ring-1 ring-black/10 transition-colors hover:bg-brand hover:text-white disabled:pointer-events-none disabled:text-ink-3 disabled:opacity-35"
    >
      {children}
    </button>
  )
}

/** ‹ heading › row used at the top of each popover. */
function PopoverNav({ heading, onPrev, onNext, prevDisabled, nextDisabled, unit }) {
  const btn = 'grid size-8 place-items-center rounded-full text-brand hover:bg-brand-tint disabled:opacity-30'
  return (
    <div className="mb-3 flex items-center justify-between">
      <button type="button" aria-label={`Previous ${unit}`} onClick={onPrev} disabled={prevDisabled} className={btn}>
        ‹
      </button>
      <span className="text-sm font-bold text-ink">{heading}</span>
      <button type="button" aria-label={`Next ${unit}`} onClick={onNext} disabled={nextDisabled} className={btn}>
        ›
      </button>
    </div>
  )
}

function cellClass(selected, enabled) {
  return selected
    ? 'bg-brand text-white'
    : enabled
      ? 'text-ink hover:bg-brand-tint hover:text-brand'
      : 'cursor-not-allowed text-ink-3/40'
}

// ---------------------------------------------------------------------------
// Month picker
// ---------------------------------------------------------------------------

/**
 * `months` is the list of selectable 'YYYY-MM' values, newest first.
 */
export function MonthPicker({ months, value, onChange, label = 'Monthly report', note }) {
  const index = months.indexOf(value)
  const older = months[index + 1]
  const newer = months[index - 1]

  return (
    <PickerShell
      label={label}
      note={note}
      title={formatMonth(value)}
      prev={{ label: 'Previous month', onClick: () => onChange(older), disabled: !older }}
      next={{ label: 'Next month', onClick: () => onChange(newer), disabled: !newer }}
      popover={(close) => (
        <MonthGrid
          months={months}
          value={value}
          onSelect={(m) => {
            onChange(m)
            close()
          }}
        />
      )}
    />
  )
}

function MonthGrid({ months, value, onSelect }) {
  const available = new Set(months)
  const years = [...new Set(months.map((m) => Number(m.slice(0, 4))))].sort()
  const [year, setYear] = useState(Number(value.slice(0, 4)))

  return (
    <>
      <PopoverNav
        unit="year"
        heading={year}
        onPrev={() => setYear((y) => y - 1)}
        onNext={() => setYear((y) => y + 1)}
        prevDisabled={year <= years[0]}
        nextDisabled={year >= years.at(-1)}
      />
      <div className="grid grid-cols-3 gap-1.5">
        {MONTH_ABBR.map((abbr, i) => {
          const m = `${year}-${pad(i + 1)}`
          const enabled = available.has(m)
          const selected = m === value
          return (
            <button
              key={m}
              type="button"
              disabled={!enabled}
              onClick={() => onSelect(m)}
              aria-current={selected ? 'true' : undefined}
              className={`rounded-md py-2 text-sm font-medium transition-colors ${cellClass(selected, enabled)}`}
            >
              {abbr}
            </button>
          )
        })}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Date picker
// ---------------------------------------------------------------------------

const formatDay = (iso) => parseISODate(iso).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
const weekdayOf = (iso) => parseISODate(iso).toLocaleDateString('en-US', { weekday: 'long' })

/** Day selector with a calendar popover; days after `max` are disabled. */
export function DatePicker({ value, onChange, max, label = 'Daily report' }) {
  return (
    <PickerShell
      label={label}
      note={value === max ? `${weekdayOf(value)} · Latest` : weekdayOf(value)}
      title={formatDay(value)}
      prev={{ label: 'Previous day', onClick: () => onChange(addDays(value, -1)) }}
      next={{ label: 'Next day', onClick: () => onChange(addDays(value, 1)), disabled: value >= max }}
      popover={(close) => (
        <CalendarGrid
          value={value}
          max={max}
          onSelect={(d) => {
            onChange(d)
            close()
          }}
        />
      )}
    />
  )
}

function CalendarGrid({ value, max, onSelect }) {
  const [month, setMonth] = useState(monthOf(value))
  const leadingBlanks = parseISODate(`${month}-01`).getDay()
  const days = Array.from({ length: daysInMonth(month) }, (_, i) => `${month}-${pad(i + 1)}`)

  return (
    <>
      <PopoverNav
        unit="month"
        heading={formatMonth(month)}
        onPrev={() => setMonth((m) => addMonths(m, -1))}
        onNext={() => setMonth((m) => addMonths(m, 1))}
        nextDisabled={month >= monthOf(max)}
      />
      <div className="grid grid-cols-7 gap-1 text-center">
        {WEEKDAYS.map((d, i) => (
          <span key={i} className="pb-1 text-[11px] font-semibold text-ink-3">
            {d}
          </span>
        ))}
        {Array.from({ length: leadingBlanks }, (_, i) => (
          <span key={`blank-${i}`} />
        ))}
        {days.map((d) => {
          const enabled = d <= max
          const selected = d === value
          return (
            <button
              key={d}
              type="button"
              disabled={!enabled}
              onClick={() => onSelect(d)}
              aria-label={formatDay(d)}
              aria-current={selected ? 'date' : undefined}
              className={`tabular aspect-square rounded-full text-sm font-medium transition-colors ${cellClass(selected, enabled)} ${
                d === max && !selected ? 'ring-1 ring-brand/40' : ''
              }`}
            >
              {Number(d.slice(8))}
            </button>
          )
        })}
      </div>
      <button
        type="button"
        onClick={() => onSelect(max)}
        className="mt-3 w-full rounded-md py-1.5 text-xs font-semibold text-brand hover:bg-brand-tint"
      >
        Jump to latest report
      </button>
    </>
  )
}
