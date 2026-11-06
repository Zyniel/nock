// What the catalogue pages know about a grid, and the progress read from this
// device and the account.

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

// The progress marked while signed out, and the one marked while signed in,
// which a sign-out removes (content/cards rule 2).
export const PROGRESS_STORAGE_KEY = 'nock.progress'
export const ACCOUNT_PROGRESS_STORAGE_KEY = 'nock.account_progress'

// What GET /api/account/progress answered.
export interface AccountProgressAnswer {
  // True when the route answered 2xx: the page is signed in.
  isSignedIn: boolean
  // The account's progress, null when there is none to read.
  progress: Record<string, unknown> | null
}

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

// The key a mark is written to: the account's while the page is signed in,
// else the device's.
function progressKeyFor(isSignedIn: boolean): string {
  return isSignedIn ? ACCOUNT_PROGRESS_STORAGE_KEY : PROGRESS_STORAGE_KEY
}

// Read the progress stored under one key: grid number -> "started" or
// "finished". Anything unreadable is read as an empty object.
function readStoredProgress(key: string): Record<string, unknown> {
  const stored = parseObject(readItem(key))
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

// Return the progress of one grid: "finished" if any source says so, else
// "started" if any does, else "none". The sources are the two keys of the device
// and the account's route. The account's progress is null while it is not known
// (signed out, accounts off, failed request).
export function progressOf(
  number: number,
  accountProgress: Record<string, unknown> | null,
): Progress {
  const sources = [
    readStoredProgress(PROGRESS_STORAGE_KEY),
    readStoredProgress(ACCOUNT_PROGRESS_STORAGE_KEY),
  ]
  if (accountProgress !== null) {
    sources.push(accountProgress)
  }
  const progresses: Progress[] = []
  for (const source of sources) {
    progresses.push(progressIn(source, number))
  }
  if (progresses.includes('finished')) {
    return 'finished'
  }
  if (progresses.includes('started')) {
    return 'started'
  }
  return 'none'
}

// Ask the server for the signed-in account's progress (spec 004 rule 7): grid
// number -> "started" or "finished". A request that fails or a status other
// than 2xx is signed out with no progress; a 2xx is signed in, with no progress
// when its body is not a JSON object. The answer is never stored on the device.
export async function fetchAccountProgress(): Promise<AccountProgressAnswer> {
  let response: Response
  try {
    response = await fetch(ACCOUNT_PROGRESS_URL)
  } catch {
    return { isSignedIn: false, progress: null }
  }
  if (!response.ok) {
    return { isSignedIn: false, progress: null }
  }
  try {
    const body: unknown = await response.json()
    if (typeof body !== 'object' || body === null || Array.isArray(body)) {
      return { isSignedIn: true, progress: null }
    }
    return { isSignedIn: true, progress: body as Record<string, unknown> }
  } catch {
    return { isSignedIn: true, progress: null }
  }
}

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

// Tell whether a value is a calendar date written "YYYY-MM-DD". A day that does
// not exist, such as "2026-02-30", is not one: the date read back differs.
function isCalendarDate(value: unknown): value is string {
  if (typeof value !== 'string' || !DATE_PATTERN.test(value)) {
    return false
  }
  const time = Date.parse(`${value}T00:00:00Z`)
  if (Number.isNaN(time)) {
    return false
  }
  const readBack = new Date(time).toISOString().slice(0, 10)
  return readBack === value
}

// Tell whether a parsed JSON value looks like one grid summary.
export function isGridSummary(value: unknown): value is GridSummary {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.number === 'number' &&
    isCalendarDate(record.published_on) &&
    typeof record.force === 'number' &&
    typeof record.width === 'number' &&
    typeof record.height === 'number' &&
    typeof record.word_count === 'number'
  )
}

// Set the progress of one grid under one key. A browser that refuses storage
// keeps nothing: the page still works.
function setProgress(key: string, number: number, progress: 'started' | 'finished'): void {
  const stored = readStoredProgress(key)
  stored[String(number)] = progress
  writeItem(key, JSON.stringify(stored))
}

// A grid whose play button was tapped is started, unless the key it is written
// to says it is finished. A signed-in page writes the account's key, else the
// device's; the other key is not touched.
export function markStarted(number: number, isSignedIn: boolean): void {
  const key = progressKeyFor(isSignedIn)
  if (progressIn(readStoredProgress(key), number) !== 'finished') {
    setProgress(key, number, 'started')
  }
}

// A solved grid is finished for good, in the account's key while the page is
// signed in, else in the device's.
export function markFinished(number: number, isSignedIn: boolean): void {
  setProgress(progressKeyFor(isSignedIn), number, 'finished')
}
