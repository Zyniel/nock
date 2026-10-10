// What the catalogue pages know about a grid, and the progress read from this device.

export type Progress = 'none' | 'started' | 'finished'

export interface GridSummary {
  number: number
  published_on: string
  force: number
  width: number
  height: number
  word_count: number
}

export const PROGRESS_STORAGE_KEY = 'nock.progress'

const dateFormat = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})

// Write a "YYYY-MM-DD" date in French, from its UTC midnight.
export function formatPublishedOn(publishedOn: string): string {
  return dateFormat.format(new Date(`${publishedOn}T00:00:00Z`))
}

// Read the progress stored on this device: grid number -> "started" or "finished".
// Anything unreadable is read as an empty object.
function readStoredProgress(): Record<string, unknown> {
  let rawText: string | null = null
  try {
    rawText = localStorage.getItem(PROGRESS_STORAGE_KEY)
  } catch {
    return {}
  }
  if (rawText === null) {
    return {}
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(rawText)
  } catch {
    return {}
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return {}
  }
  return parsed as Record<string, unknown>
}

// Return the progress of one grid on this device.
export function progressOf(number: number): Progress {
  const stored = readStoredProgress()
  const value = stored[String(number)]
  if (value === 'started' || value === 'finished') {
    return value
  }
  return 'none'
}

// Tell whether a parsed JSON value looks like one grid summary.
export function isGridSummary(value: unknown): value is GridSummary {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.number === 'number' &&
    typeof record.published_on === 'string' &&
    typeof record.force === 'number' &&
    typeof record.width === 'number' &&
    typeof record.height === 'number' &&
    typeof record.word_count === 'number'
  )
}
