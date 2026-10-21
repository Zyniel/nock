// The history of finished grids (spec 029): the records this device keeps under
// `nock.history`, the records of a signed-in account, and the texts of the list.
// Plain functions: no DOM.

import { durationText } from './duration'
import { t } from './i18n'
import { readIdentity } from './joinRules'
import { dateText, fetchRoomSummaries, isTime, type RoomSummary } from './myRooms'
import { displayNickname } from './nickname'
import { readItem, writeItem } from './storage'

// One finished grid, as this device stores it.
export interface HistoryRecord {
  code: string
  // The catalogue number (spec 004); null for a grid outside the catalogue.
  grid: number | null
  width: number
  height: number
  // When the grid was solved, an ISO 8601 time.
  finished_at: string
  elapsed_ms: number
  // The team-mates' nicknames, as the server stores them.
  teammates: string[]
}

export const HISTORY_KEY = 'nock.history'
// The device keeps at most this many records; the oldest go.
export const HISTORY_LIMIT = 100

const ACCOUNT_HISTORY_URL = '/api/account/history'

function isNumberOrNull(value: unknown): value is number | null {
  return value === null || typeof value === 'number'
}

function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((name: unknown) => typeof name === 'string')
}

// Read a parsed JSON value as a record, with `gridField` as the grid number:
// `grid` on the device, `grid_number` from the server. Null when a field does
// not have the record's type.
function parseRecord(value: unknown, gridField: 'grid' | 'grid_number'): HistoryRecord | null {
  if (typeof value !== 'object' || value === null) {
    return null
  }
  const fields = value as Record<string, unknown>
  const { code, width, height, finished_at, elapsed_ms, teammates } = fields
  const grid = fields[gridField]
  if (
    typeof code !== 'string' ||
    !isNumberOrNull(grid) ||
    typeof width !== 'number' ||
    typeof height !== 'number' ||
    !isTime(finished_at) ||
    typeof elapsed_ms !== 'number' ||
    !isStringList(teammates)
  ) {
    return null
  }
  return { code, grid, width, height, finished_at, elapsed_ms, teammates }
}

// The newest `finished_at` first, then by code in code-point order.
function newestFirst(first: HistoryRecord, second: HistoryRecord): number {
  const firstTime = Date.parse(first.finished_at)
  const secondTime = Date.parse(second.finished_at)
  if (firstTime !== secondTime) {
    return secondTime - firstTime
  }
  if (first.code < second.code) {
    return -1
  }
  if (first.code > second.code) {
    return 1
  }
  return 0
}

// The records stored on this device. A stored value that is not a JSON array
// reads as none, and an item whose fields do not have the record's types is
// left out.
export function readHistory(): HistoryRecord[] {
  const raw = readItem(HISTORY_KEY)
  if (raw === null) {
    return []
  }
  let stored: unknown
  try {
    stored = JSON.parse(raw)
  } catch {
    return []
  }
  if (!Array.isArray(stored)) {
    return []
  }
  const records: HistoryRecord[] = []
  for (const item of stored) {
    const record = parseRecord(item, 'grid')
    if (record !== null) {
      records.push(record)
    }
  }
  return records
}

// The record of a solved summary, or null when the summary is not solved or
// does not say when. The team-mates are the summary's players without the
// nickname of this device's identity for the room, compared exactly: every
// nickname is in capitals (spec 012 decision 12).
function recordOf(summary: RoomSummary): HistoryRecord | null {
  const finishedAt = summary.finished_at
  const elapsedMs = summary.elapsed_ms
  if (!summary.solved || typeof finishedAt !== 'string' || typeof elapsedMs !== 'number') {
    return null
  }
  const identity = readIdentity(summary.code)
  const ownNickname = identity === null ? null : identity.nickname
  const teammates: string[] = []
  for (const player of summary.players) {
    if (player !== ownNickname) {
      teammates.push(player)
    }
  }
  return {
    code: summary.code,
    grid: summary.grid_number,
    width: summary.width,
    height: summary.height,
    finished_at: finishedAt,
    elapsed_ms: elapsedMs,
    teammates,
  }
}

// Write a record for each solved summary, replacing any record of its code. The
// stored list stays newest first and keeps at most HISTORY_LIMIT records.
export function writeSolvedSummaries(summaries: RoomSummary[]): void {
  const newRecords: HistoryRecord[] = []
  for (const summary of summaries) {
    const record = recordOf(summary)
    if (record !== null) {
      newRecords.push(record)
    }
  }
  if (newRecords.length === 0) {
    return
  }
  const newCodes = new Set(newRecords.map((record) => record.code))
  const kept = readHistory().filter((record) => !newCodes.has(record.code))
  const records = [...newRecords, ...kept]
  records.sort(newestFirst)
  writeItem(HISTORY_KEY, JSON.stringify(records.slice(0, HISTORY_LIMIT)))
}

// Ask the summary of this page's own room, and write its record when it is
// solved (the room page, once its grid is solved). A failed request writes
// nothing.
export async function recordOwnRoom(code: string, resumeToken: string): Promise<void> {
  const summaries = await fetchRoomSummaries([{ code, resume_token: resumeToken }])
  if (summaries !== null) {
    writeSolvedSummaries(summaries)
  }
}

// The records of the signed-in account, as the device's records, or null when
// the request fails or the answer is not an array of records.
export async function fetchAccountHistory(): Promise<HistoryRecord[] | null> {
  try {
    const response = await fetch(ACCOUNT_HISTORY_URL)
    if (response.status !== 200) {
      return null
    }
    const body: unknown = await response.json()
    if (!Array.isArray(body)) {
      return null
    }
    const records: HistoryRecord[] = []
    for (const item of body) {
      const record = parseRecord(item, 'grid_number')
      if (record === null) {
        return null
      }
      records.push(record)
    }
    return records
  } catch {
    return null
  }
}

// One list of the device's and the account's records, one per room code (the
// account's record wins), newest first, then by code.
export function mergeHistories(
  deviceRecords: HistoryRecord[],
  accountRecords: HistoryRecord[],
): HistoryRecord[] {
  const accountCodes = new Set(accountRecords.map((record) => record.code))
  const merged = [...accountRecords]
  for (const record of deviceRecords) {
    if (!accountCodes.has(record.code)) {
      merged.push(record)
    }
  }
  merged.sort(newestFirst)
  return merged
}

// "Terminée le 14 octobre 2026", in the browser's time zone.
export function finishedText(record: HistoryRecord): string {
  return t('history.finished', { date: dateText(new Date(record.finished_at)) })
}

// "en 12 min 34 s".
export function timeText(record: HistoryRecord): string {
  return t('history.time', { duration: durationText(record.elapsed_ms) })
}

// "Avec Bob, Cy", each former player shown as such, or "En solo".
export function teammatesText(record: HistoryRecord): string {
  if (record.teammates.length === 0) {
    return t('history.alone')
  }
  const names = record.teammates.map(displayNickname).join(', ')
  return t('history.teammates', { names })
}
