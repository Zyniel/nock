// The operator's page (spec 038): what the ops API answers, the token this tab
// keeps, and the texts of the dashboard and of the replay. Plain functions: no
// DOM.

import { durationText } from './duration'
import { t, type MessageKey } from './i18n'
import { displayNickname } from './nickname'
import type { GridView } from './roomSession'
import { positionKey } from './wordSelection'

// The key of the operator token in this tab's sessionStorage. The token is never
// put in localStorage, a cookie or a URL.
export const OPS_TOKEN_KEY = 'nock.ops_token'

// The periods of the dashboard, in days, and the one shown when the page loads.
export type Period = 1 | 7 | 30
export const PERIODS: Period[] = [1, 7, 30]
export const FIRST_PERIOD: Period = 7

// The figures of one period, as the server sends them. A figure with no data is
// null.
export interface DashboardFigures {
  days: number
  // An ISO 8601 time in UTC: the start of the period.
  since: string
  rooms_created: number
  players_per_room: number | null
  completion_rate: number | null
  median_solving_ms: number | null
  latency_median_ms: number | null
  latency_p95_ms: number | null
  disconnection_rate: number | null
}

export type EditKind = 'typed' | 'erased' | 'undone' | 'locked' | 'revealed'

// One edit of a room, as the server sends it.
export interface RoomEdit {
  seq: number
  // An ISO 8601 time in UTC.
  at: string
  kind: EditKind
  row: number
  column: number
  // The cell's letter after the edit; null when the edit left it empty.
  letter: string | null
  // True for a letter typed in pencil (spec 020).
  pencil: boolean
  // Who made it; null for a lock and a reveal.
  player_id: string | null
  // In capitals, as the server stores it; null when unknown.
  nickname: string | null
}

// The replay of one room: its grid without letters, and its edits in seq order.
export interface RoomReplay {
  code: string
  grid: GridView
  edits: RoomEdit[]
}

// Why the page goes back to the token form: a 401 or a 429 of the ops API.
export type LockReason = 'refused' | 'throttled'

// What one ops API request gave.
export type OpsAnswer<Body> =
  | { kind: 'ok'; body: Body }
  // 401 or 429
  | { kind: LockReason }
  | { kind: 'not_found' }
  // Any other answer, a body of another shape, or no answer at all.
  | { kind: 'failed' }

const EDIT_KINDS: string[] = ['typed', 'erased', 'undone', 'locked', 'revealed']

function isNumberOrNull(value: unknown): boolean {
  return value === null || typeof value === 'number'
}

function isStringOrNull(value: unknown): boolean {
  return value === null || typeof value === 'string'
}

// Tell whether a parsed JSON value looks like the figures of one period.
function isDashboardFigures(value: unknown): value is DashboardFigures {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.days === 'number' &&
    typeof record.since === 'string' &&
    typeof record.rooms_created === 'number' &&
    isNumberOrNull(record.players_per_room) &&
    isNumberOrNull(record.completion_rate) &&
    isNumberOrNull(record.median_solving_ms) &&
    isNumberOrNull(record.latency_median_ms) &&
    isNumberOrNull(record.latency_p95_ms) &&
    isNumberOrNull(record.disconnection_rate)
  )
}

// Tell whether a parsed JSON value looks like one edit of a replay.
function isRoomEdit(value: unknown): value is RoomEdit {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.seq === 'number' &&
    typeof record.at === 'string' &&
    typeof record.kind === 'string' &&
    EDIT_KINDS.includes(record.kind) &&
    typeof record.row === 'number' &&
    typeof record.column === 'number' &&
    isStringOrNull(record.letter) &&
    typeof record.pencil === 'boolean' &&
    isStringOrNull(record.player_id) &&
    isStringOrNull(record.nickname)
  )
}

// Tell whether a parsed JSON value looks like one cell of a grid view.
function isCellView(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.type === 'string' &&
    typeof record.row === 'number' &&
    typeof record.column === 'number'
  )
}

// Tell whether a parsed JSON value looks like the replay of a room.
function isRoomReplay(value: unknown): value is RoomReplay {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  if (typeof record.code !== 'string' || !Array.isArray(record.edits)) {
    return false
  }
  if (typeof record.grid !== 'object' || record.grid === null) {
    return false
  }
  const grid = record.grid as Record<string, unknown>
  return (
    typeof grid.width === 'number' &&
    typeof grid.height === 'number' &&
    Array.isArray(grid.cells) &&
    grid.cells.every(isCellView) &&
    record.edits.every(isRoomEdit)
  )
}

// Ask the ops API for a body of the expected shape, with the operator token in
// the Authorization header, the only place the server reads it from.
async function fetchOps<Body>(
  path: string,
  token: string,
  isExpected: (value: unknown) => value is Body,
): Promise<OpsAnswer<Body>> {
  try {
    const response = await fetch(path, { headers: { Authorization: `Bearer ${token}` } })
    if (response.status === 401) {
      return { kind: 'refused' }
    }
    if (response.status === 429) {
      return { kind: 'throttled' }
    }
    if (response.status === 404) {
      return { kind: 'not_found' }
    }
    if (response.status !== 200) {
      return { kind: 'failed' }
    }
    const body: unknown = await response.json()
    if (!isExpected(body)) {
      return { kind: 'failed' }
    }
    return { kind: 'ok', body }
  } catch {
    return { kind: 'failed' }
  }
}

// The figures of the rooms created in the last `days` days.
export function fetchDashboard(
  token: string,
  days: Period,
): Promise<OpsAnswer<DashboardFigures>> {
  return fetchOps(`/api/ops/dashboard?days=${days}`, token, isDashboardFigures)
}

// The replay of the room `code`, as given (the page sends it in upper case).
export function fetchReplay(token: string, code: string): Promise<OpsAnswer<RoomReplay>> {
  const path = `/api/ops/rooms/${encodeURIComponent(code)}/edits`
  return fetchOps(path, token, isRoomReplay)
}

// The operator token this tab keeps, or null. A browser that refuses storage
// keeps none.
export function readOpsToken(): string | null {
  try {
    return sessionStorage.getItem(OPS_TOKEN_KEY)
  } catch {
    return null
  }
}

export function writeOpsToken(token: string): void {
  try {
    sessionStorage.setItem(OPS_TOKEN_KEY, token)
  } catch {
    // Nothing is kept: the page asks for the token again after a reload.
  }
}

export function removeOpsToken(): void {
  try {
    sessionStorage.removeItem(OPS_TOKEN_KEY)
  } catch {
    // Nothing was kept.
  }
}

// ---- The dashboard's texts ------------------------------------------------------

export type MetricName =
  | 'rooms_created'
  | 'players_per_room'
  | 'completion_rate'
  | 'median_solving_time'
  | 'latency'
  | 'disconnection_rate'

// One figure of the dashboard as the page shows it.
export interface MetricView {
  metric: MetricName
  // The figure as received, written by String() (2.0 reads "2"); "" for none.
  value: string
  // The latency only: its p95 as received, "" for none.
  p95?: string
  text: string
}

const oneDecimal = new Intl.NumberFormat('fr-FR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const twoDecimals = new Intl.NumberFormat('fr-FR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

// The figure as received, for a data attribute: "" for none.
function received(figure: number | null): string {
  return figure === null ? '' : String(figure)
}

// The value a figure shows in its text: `format` of it, or "aucune donnée".
function shownValue(figure: number | null, format: (value: number) => string): string {
  if (figure === null) {
    return t('ops.no_data')
  }
  return format(figure)
}

// "67 %" for a rate of 2/3.
function percentText(rate: number): string {
  return t('ops.percent', { value: Math.round(rate * 100) })
}

// "30 ms (médiane), 50 ms (95e centile)", both in whole milliseconds.
function latencyText(median: number | null, p95: number | null): string {
  if (median === null || p95 === null) {
    return t('ops.no_data')
  }
  return t('ops.latency_value', { median: Math.round(median), p95: Math.round(p95) })
}

// The six figures of the dashboard, in the order the page shows them.
export function metricViews(figures: DashboardFigures): MetricView[] {
  const playersPerRoom = shownValue(figures.players_per_room, (value) =>
    oneDecimal.format(value),
  )
  const completionRate = shownValue(figures.completion_rate, percentText)
  const solvingTime = shownValue(figures.median_solving_ms, durationText)
  const latency = latencyText(figures.latency_median_ms, figures.latency_p95_ms)
  const disconnectionRate = shownValue(figures.disconnection_rate, (value) =>
    twoDecimals.format(value),
  )
  return [
    {
      metric: 'rooms_created',
      value: String(figures.rooms_created),
      text: t('ops.metric.rooms_created', { value: figures.rooms_created }),
    },
    {
      metric: 'players_per_room',
      value: received(figures.players_per_room),
      text: t('ops.metric.players_per_room', { value: playersPerRoom }),
    },
    {
      metric: 'completion_rate',
      value: received(figures.completion_rate),
      text: t('ops.metric.completion_rate', { value: completionRate }),
    },
    {
      metric: 'median_solving_time',
      value: received(figures.median_solving_ms),
      text: t('ops.metric.median_solving_time', { value: solvingTime }),
    },
    {
      metric: 'latency',
      value: received(figures.latency_median_ms),
      p95: received(figures.latency_p95_ms),
      text: t('ops.metric.latency', { value: latency }),
    },
    {
      metric: 'disconnection_rate',
      value: received(figures.disconnection_rate),
      text: t('ops.metric.disconnection_rate', { value: disconnectionRate }),
    },
  ]
}

// ---- The replay -----------------------------------------------------------------

const EDIT_TEXT_KEYS: Record<EditKind, MessageKey> = {
  typed: 'ops.edit.typed',
  erased: 'ops.edit.erased',
  undone: 'ops.edit.undone',
  locked: 'ops.edit.locked',
  revealed: 'ops.edit.revealed',
}

// The time of an edit, in the browser's time zone.
const editTimeFormat = new Intl.DateTimeFormat('fr-FR', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

// The line of one edit: "10:31:05 · Ana écrit T en (1, 0)". The name is the
// nickname as spec 040's displayNickname shows it, or "Quelqu'un" when unknown.
export function editText(edit: RoomEdit): string {
  let key = EDIT_TEXT_KEYS[edit.kind]
  if (edit.kind === 'typed' && edit.pencil) {
    key = 'ops.edit.typed_pencil'
  }
  const name = edit.nickname === null ? t('feed.someone') : displayNickname(edit.nickname)
  return t(key, {
    time: editTimeFormat.format(new Date(edit.at)),
    name,
    letter: edit.letter ?? '',
    row: edit.row,
    column: edit.column,
  })
}

// The letter of each cell after the first `position` edits, by positionKey: the
// letter of the last of those edits on the cell. A cell that none of them
// reached, or whose last one left it empty, is not in the map.
export function lettersAtStep(edits: RoomEdit[], position: number): Map<string, string> {
  const letters = new Map<string, string>()
  for (const edit of edits.slice(0, position)) {
    const key = positionKey(edit.row, edit.column)
    if (edit.letter === null) {
      letters.delete(key)
    } else {
      letters.set(key, edit.letter)
    }
  }
  return letters
}
