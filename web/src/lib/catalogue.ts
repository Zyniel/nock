// What the catalogue pages know about a grid, and the progress read from this device.

import { parseObject, readItem, writeItem } from './storage'

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
  const stored = parseObject(readItem(PROGRESS_STORAGE_KEY))
  return stored === null ? {} : stored
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

// Set the progress of one grid on this device. A browser that refuses storage
// keeps nothing: the page still works.
function setProgress(number: number, progress: 'started' | 'finished'): void {
  const stored = readStoredProgress()
  stored[String(number)] = progress
  writeItem(PROGRESS_STORAGE_KEY, JSON.stringify(stored))
}

// A grid whose play button was tapped is started, unless it is finished.
export function markStarted(number: number): void {
  if (progressOf(number) !== 'finished') {
    setProgress(number, 'started')
  }
}

// A solved grid is finished for good.
export function markFinished(number: number): void {
  setProgress(number, 'finished')
}
