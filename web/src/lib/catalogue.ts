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

const ACCOUNT_PROGRESS_URL = '/api/account/progress'

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

// Read one grid's progress in a source: "started" or "finished", else "none".
// Any other value, or a missing key, is no progress.
function progressIn(source: Record<string, unknown>, number: number): Progress {
  const value = source[String(number)]
  if (value === 'started' || value === 'finished') {
    return value
  }
  return 'none'
}

// Return the progress of one grid: "finished" if the device or the account says
// so, else "started" if either does, else "none". The account's progress is null
// while it is not known (signed out, accounts off, failed request).
export function progressOf(
  number: number,
  accountProgress: Record<string, unknown> | null,
): Progress {
  const onDevice = progressIn(readStoredProgress(), number)
  const onAccount = accountProgress === null ? 'none' : progressIn(accountProgress, number)
  if (onDevice === 'finished' || onAccount === 'finished') {
    return 'finished'
  }
  if (onDevice === 'started' || onAccount === 'started') {
    return 'started'
  }
  return 'none'
}

// Ask the server for the signed-in account's progress (spec 004 rule 7): grid
// number -> "started" or "finished". Null on any failure: a request that fails,
// a status other than 2xx, or a body that is not a JSON object. The answer is
// never stored on the device.
export async function fetchAccountProgress(): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(ACCOUNT_PROGRESS_URL)
    if (!response.ok) {
      return null
    }
    const body: unknown = await response.json()
    if (typeof body !== 'object' || body === null || Array.isArray(body)) {
      return null
    }
    return body as Record<string, unknown>
  } catch {
    return null
  }
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
  if (progressIn(readStoredProgress(), number) !== 'finished') {
    setProgress(number, 'started')
  }
}

// A solved grid is finished for good.
export function markFinished(number: number): void {
  setProgress(number, 'finished')
}
