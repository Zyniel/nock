// "My rooms" of the catalogue page (spec 032): the rooms this device keeps an
// identity for, and what the server sums up of each. Plain functions: no DOM.

import { t } from './i18n'
import { readIdentity } from './joinRules'
import { storedKeys } from './storage'

// What a device sends for one room: its code and the stored resume token.
export interface RoomKey {
  code: string
  resume_token: string
}

// One room as the server sums it up. It holds no letter of the grid.
export interface RoomSummary {
  code: string
  // The catalogue number (spec 004); null for a grid outside the catalogue.
  grid_number: number | null
  width: number
  height: number
  // The nicknames of the room's members, each once.
  players: string[]
  // The last edit time, an ISO 8601 time in UTC.
  last_activity_at: string
  solved: boolean
}

// The server takes at most this many keys in one request.
export const MAX_KEYS_PER_REQUEST = 100

const SUMMARIES_URL = '/api/rooms/summaries'
// The patterns of the server's RoomCode (spec 011) and ResumeToken (spec 039).
const ROOM_CODE = /^[A-Z0-9]{6}$/
const RESUME_TOKEN = /^[A-Za-z0-9_-]{16,128}$/
const IDENTITY_KEY = /^nock\.identity\.([A-Z0-9]{6})$/

// Both in the browser's time zone (spec 032).
const dateFormat = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})
const timeFormat = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })

// One key per valid identity stored under `nock.identity.<CODE>` (spec 012), in
// code order. Only the codes and tokens that match the server's patterns are
// sent: one key that breaks them would make the server refuse the whole request.
export function storedRoomKeys(): RoomKey[] {
  const keys: RoomKey[] = []
  for (const storageKey of storedKeys()) {
    const match = IDENTITY_KEY.exec(storageKey)
    if (match === null) {
      continue
    }
    const code = match[1]
    const identity = readIdentity(code)
    if (identity !== null && RESUME_TOKEN.test(identity.resume_token)) {
      keys.push({ code, resume_token: identity.resume_token })
    }
  }
  keys.sort((first, second) => compareCodes(first.code, second.code))
  return keys
}

// Code-point order, as the server sorts codes.
function compareCodes(first: string, second: string): number {
  if (first < second) {
    return -1
  }
  if (first > second) {
    return 1
  }
  return 0
}

function isNumberOrNull(value: unknown): boolean {
  return value === null || typeof value === 'number'
}

function isTime(value: unknown): value is string {
  return typeof value === 'string' && !Number.isNaN(Date.parse(value))
}

// Tell whether a parsed JSON value looks like one room summary.
function isRoomSummary(value: unknown): value is RoomSummary {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.code === 'string' &&
    ROOM_CODE.test(record.code) &&
    isNumberOrNull(record.grid_number) &&
    typeof record.width === 'number' &&
    typeof record.height === 'number' &&
    Array.isArray(record.players) &&
    record.players.every((name: unknown) => typeof name === 'string') &&
    isTime(record.last_activity_at) &&
    typeof record.solved === 'boolean'
  )
}

// The server's order of the summaries: the newest last activity first, then by
// code.
function serverOrder(first: RoomSummary, second: RoomSummary): number {
  const firstTime = Date.parse(first.last_activity_at)
  const secondTime = Date.parse(second.last_activity_at)
  if (firstTime !== secondTime) {
    return secondTime - firstTime
  }
  return compareCodes(first.code, second.code)
}

// The keys cut into requests of at most MAX_KEYS_PER_REQUEST keys.
function requestsOf(keys: RoomKey[]): RoomKey[][] {
  const requests: RoomKey[][] = []
  for (let start = 0; start < keys.length; start += MAX_KEYS_PER_REQUEST) {
    requests.push(keys.slice(start, start + MAX_KEYS_PER_REQUEST))
  }
  return requests
}

// Ask the server for the summaries of one request's keys. Null when the request
// fails, when the server answers anything but 200, or when the answer is not an
// array of summaries.
async function fetchSummaries(keys: RoomKey[]): Promise<RoomSummary[] | null> {
  try {
    const response = await fetch(SUMMARIES_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rooms: keys }),
    })
    if (response.status !== 200) {
      return null
    }
    const body: unknown = await response.json()
    if (!Array.isArray(body) || !body.every(isRoomSummary)) {
      return null
    }
    return body
  } catch {
    return null
  }
}

// The summaries of the rooms of `keys`, or null when one request fails. With one
// request, they keep the order the server sent; the answers of several requests
// are sorted together as the server sorts them.
export async function fetchRoomSummaries(keys: RoomKey[]): Promise<RoomSummary[] | null> {
  const requests = requestsOf(keys)
  const summaries: RoomSummary[] = []
  for (const requestKeys of requests) {
    const answer = await fetchSummaries(requestKeys)
    if (answer === null) {
      return null
    }
    summaries.push(...answer)
  }
  if (requests.length > 1) {
    summaries.sort(serverOrder)
  }
  return summaries
}

// "Dernière activité : 14 octobre 2026 à 10:30", in the browser's time zone.
export function lastActivityText(lastActivityAt: string): string {
  const moment = new Date(lastActivityAt)
  return t('my_rooms.last_activity', {
    date: dateFormat.format(moment),
    time: timeFormat.format(moment),
  })
}
