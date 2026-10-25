'use client'

import { format, parseISO } from 'date-fns'
import * as React from 'react'

import { plural } from '@/lib/utils'
import type { ActivityDay } from '@/types/admin'

const CHART_HEIGHT = 160

function dayLabel(date: string, pattern: string) {
  return format(parseISO(date), pattern)
}

/**
 * Above the bar at `fraction` of the plot's width (which ends 1.5rem short of
 * the panel, for the axis label), shifted by the same fraction of its own
 * width so it never spills past either edge.
 */
function tooltipPosition(fraction: number): React.CSSProperties {
  return {
    left: `calc(${fraction * 100}% - ${fraction * 1.5}rem)`,
    transform: `translate(-${fraction * 100}%, -100%)`,
  }
}

/**
 * Questions asked per day: one series, so one hue and no legend (the panel
 * title names it). Each column is a hover and focus target taller than its
 * bar; the same numbers are in a visually hidden table for screen readers.
 */
export function ActivityChart({ days }: { days: ActivityDay[] }) {
  const [active, setActive] = React.useState<number | null>(null)
  const max = Math.max(1, ...days.map((d) => d.messages))
  // A round top for the axis, so the gridline label reads naturally.
  const top = max <= 5 ? max : Math.ceil(max / 5) * 5
  const shown = active === null ? null : days[active]

  return (
    <div className="relative">
      <div className="relative" style={{ height: CHART_HEIGHT }}>
        {/* Recessive guides: the top value and the baseline. */}
        <div aria-hidden="true" className="absolute inset-x-0 top-0 border-t border-dashed border-border" />
        <span aria-hidden="true" className="absolute -top-2 right-0 bg-card pl-1 text-[0.6875rem] tabular-nums text-muted-foreground">
          {top}
        </span>
        <div aria-hidden="true" className="absolute inset-x-0 bottom-0 border-t border-border" />

        <div className="absolute inset-0 flex items-end gap-0.5 pr-6" onMouseLeave={() => setActive(null)}>
          {days.map((day, i) => {
            const height = day.messages === 0 ? 0 : Math.max(2, (day.messages / top) * CHART_HEIGHT)
            return (
              <button
                key={day.date}
                type="button"
                aria-label={`${dayLabel(day.date, 'EEEE d MMMM')}: ${plural(day.messages, 'question')}, ${plural(day.chats, 'new chat')}`}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                className="group flex h-full flex-1 items-end justify-center rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span
                  className="w-full max-w-8 rounded-t-[4px] transition-opacity group-hover:opacity-80"
                  style={{ height, backgroundColor: 'hsl(var(--chart-1))' }}
                />
              </button>
            )
          })}
        </div>

        {shown && active !== null && (
          <div
            role="status"
            className="pointer-events-none absolute -top-1 z-10 whitespace-nowrap rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-md"
            style={tooltipPosition((active + 0.5) / days.length)}
          >
            <p className="font-medium">{dayLabel(shown.date, 'EEE d MMM')}</p>
            <p className="tabular-nums text-muted-foreground">
              {shown.messages} question{shown.messages === 1 ? '' : 's'} · {shown.chats} new chat
              {shown.chats === 1 ? '' : 's'}
            </p>
          </div>
        )}
      </div>

      {/* Selective labels: the first day, the middle and today. */}
      <div aria-hidden="true" className="mt-2 flex justify-between pr-6 text-[0.6875rem] text-muted-foreground">
        <span>{days[0] && dayLabel(days[0].date, 'd MMM')}</span>
        <span>{days[Math.floor(days.length / 2)] && dayLabel(days[Math.floor(days.length / 2)]!.date, 'd MMM')}</span>
        <span>Today</span>
      </div>

      <table className="sr-only">
        <caption>Questions and new chats per day</caption>
        <thead>
          <tr>
            <th scope="col">Day</th>
            <th scope="col">Questions</th>
            <th scope="col">New chats</th>
          </tr>
        </thead>
        <tbody>
          {days.map((day) => (
            <tr key={day.date}>
              <th scope="row">{dayLabel(day.date, 'd MMMM yyyy')}</th>
              <td>{day.messages}</td>
              <td>{day.chats}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
