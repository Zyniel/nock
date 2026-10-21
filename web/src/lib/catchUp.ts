// Catching up after an absence (spec 034): what a page asks the server for on a
// return, how it reads the answer, and how it applies it to the room page: the
// names, the highlighted cells and the lines of the activity feed.

import { feedItemFor, insertFeedItems, wordCompletedItem } from './activityFeed'
import type { FeedItem, KeptFeedItem } from './activityFeed'
import type { RoomSession, Snapshot } from './roomSession'

// How long a changed cell stays highlighted.
export const CATCH_UP_HIGHLIGHT_MS = 5000

// The body of POST /api/rooms/<code>/catch-up.
export interface CatchUpRequest {
  resume_token: string
  // The page's seen seq.
  after_seq: number
  // The seq of the snapshot of the return.
  until_seq: number
}

interface CellRef {
  row: number
  column: number
}

// A line of the absence: a check_result or a reveal_result as the server logged
// it, or a word_completed. `message` is the whole line.
interface CatchUpLine {
  type: 'check_result' | 'reveal_result' | 'word_completed'
  seq: number
  player_id: string
  message: Record<string, unknown>
}

interface PlayerName {
  player_id: string
  nickname: string
}

export interface CatchUp {
  after_seq: number
  until_seq: number
  cells: CellRef[]
  lines: CatchUpLine[]
  names: PlayerName[]
}

const LINE_TYPES: string[] = ['check_result', 'reveal_result', 'word_completed']

function isWholeNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function toCellRef(value: unknown): CellRef | null {
  const cell = asObject(value)
  if (cell === null || !isWholeNumber(cell.row) || !isWholeNumber(cell.column)) {
    return null
  }
  return { row: cell.row, column: cell.column }
}

function toLine(value: unknown): CatchUpLine | null {
  const line = asObject(value)
  if (line === null || typeof line.type !== 'string' || !LINE_TYPES.includes(line.type)) {
    return null
  }
  if (!isWholeNumber(line.seq) || typeof line.player_id !== 'string') {
    return null
  }
  return {
    type: line.type as CatchUpLine['type'],
    seq: line.seq,
    player_id: line.player_id,
    message: line,
  }
}

function toPlayerName(value: unknown): PlayerName | null {
  const name = asObject(value)
  if (name === null || typeof name.player_id !== 'string' || typeof name.nickname !== 'string') {
    return null
  }
  return { player_id: name.player_id, nickname: name.nickname }
}

// Read every item of a list with `read`; null when the value is not a list or
// one of its items cannot be read.
function toList<Item>(value: unknown, read: (item: unknown) => Item | null): Item[] | null {
  if (!Array.isArray(value)) {
    return null
  }
  const items: Item[] = []
  for (const raw of value) {
    const item = read(raw)
    if (item === null) {
      return null
    }
    items.push(item)
  }
  return items
}

// The catch-up of an answer's body, or null when the body is not a catch-up.
export function toCatchUp(value: unknown): CatchUp | null {
  const body = asObject(value)
  if (body === null || !isWholeNumber(body.after_seq) || !isWholeNumber(body.until_seq)) {
    return null
  }
  const cells = toList(body.cells, toCellRef)
  const lines = toList(body.lines, toLine)
  const names = toList(body.names, toPlayerName)
  if (cells === null || lines === null || names === null) {
    return null
  }
  return { after_seq: body.after_seq, until_seq: body.until_seq, cells, lines, names }
}

// Ask the server for a catch-up. Null when the request fails, when the server
// answers anything but 200, or when the answer is not a catch-up: the page then
// shows none, and does not ask again.
export async function fetchCatchUp(code: string, request: CatchUpRequest): Promise<CatchUp | null> {
  try {
    const response = await fetch(`/api/rooms/${code}/catch-up`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    if (response.status !== 200) {
      return null
    }
    const body: unknown = await response.json()
    return toCatchUp(body)
  } catch {
    return null
  }
}

// The feed item of a catch-up line, or null when it has none (a check or a
// reveal of an unknown scope).
function feedItemOfLine(session: RoomSession, snapshot: Snapshot, line: CatchUpLine): FeedItem | null {
  if (line.type === 'word_completed') {
    return wordCompletedItem(snapshot, session.names, line.seq, line.player_id, line.message.clue)
  }
  const event = { type: line.type, seq: line.seq, message: line.message }
  return feedItemFor(snapshot, session.names, event)
}

// Add the names of the players the page does not know yet.
function addNames(session: RoomSession, names: PlayerName[]): void {
  for (const name of names) {
    if (!session.names.has(name.player_id)) {
      session.names.set(name.player_id, name.nickname)
    }
  }
}

// Highlight each changed cell. A cell already highlighted starts its
// CATCH_UP_HIGHLIGHT_MS again: its entry is replaced by one with a new id.
function highlightCells(session: RoomSession, cells: CellRef[]): void {
  let highlighted = session.caughtUpCells
  for (const cell of cells) {
    highlighted = highlighted.filter(
      (kept) => kept.row !== cell.row || kept.column !== cell.column,
    )
    highlighted.push({ id: session.nextCaughtUpId, row: cell.row, column: cell.column })
    session.nextCaughtUpId += 1
  }
  session.caughtUpCells = highlighted
}

// Put the lines into the feed, in seq order among the items it holds.
function addLines(session: RoomSession, snapshot: Snapshot, lines: CatchUpLine[]): void {
  const items: KeptFeedItem[] = []
  for (const line of lines) {
    const item = feedItemOfLine(session, snapshot, line)
    if (item !== null) {
      items.push({ ...item, id: session.nextFeedItemId })
      session.nextFeedItemId += 1
    }
  }
  if (items.length === 0) {
    return
  }
  insertFeedItems(session.feed, items)
  session.feedChanges += 1
}

// Apply a catch-up to the page: its names first, so that its lines can name
// their players, then the highlight and the lines.
export function applyCatchUp(session: RoomSession, catchUp: CatchUp): void {
  if (session.snapshot === null) {
    return
  }
  addNames(session, catchUp.names)
  highlightCells(session, catchUp.cells)
  addLines(session, session.snapshot, catchUp.lines)
  session.catchUpLabel = `${catchUp.after_seq}-${catchUp.until_seq}`
}

// Stop highlighting a cell: used when its CATCH_UP_HIGHLIGHT_MS are over.
export function endCaughtUp(session: RoomSession, caughtUpId: number): void {
  session.caughtUpCells = session.caughtUpCells.filter((cell) => cell.id !== caughtUpId)
}
