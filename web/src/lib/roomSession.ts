// The state of one room page and the rules that keep it in `seq` order.
// Plain functions: no socket and no DOM, so the rules are easy to read.

export type RoomStatus = 'connecting' | 'joined' | 'not_found' | 'throttled' | 'closed'

export type Arrow = 'right' | 'down' | 'right_then_down' | 'down_then_right'

export interface ClueView {
  text: string
  arrow: Arrow
}

export interface LetterCellView {
  type: 'letter'
  row: number
  column: number
  // `null` when the cell is empty.
  letter: string | null
  locked: boolean
}

export interface ClueCellView {
  type: 'clue'
  row: number
  column: number
  clues: ClueView[]
}

export interface EmptyCellView {
  type: 'empty'
  row: number
  column: number
}

export type CellView = LetterCellView | ClueCellView | EmptyCellView

export interface GridView {
  width: number
  height: number
  cells: CellView[]
}

// Only what the client reads from a snapshot (later specs read more).
export interface Snapshot {
  type: 'snapshot'
  seq: number
  grid: GridView
}

// A message with an integer `seq` that is not a snapshot.
export interface RoomEvent {
  type: string
  seq: number
}

export interface RoomSession {
  status: RoomStatus
  snapshot: Snapshot | null
  // `null` until the first snapshot.
  seq: number | null
  // Events that arrived too early, waiting for the ones before them.
  pending: RoomEvent[]
}

export const ROOM_NOT_FOUND_CLOSE_CODE = 4404
export const THROTTLED_CLOSE_CODE = 4429

export function newSession(): RoomSession {
  return { status: 'connecting', snapshot: null, seq: null, pending: [] }
}

// Parse one frame. Returns null when it is not a JSON object with a string type.
function parseFrame(text: string): Record<string, unknown> | null {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null
  }
  const message = value as Record<string, unknown>
  if (typeof message.type !== 'string') {
    return null
  }
  return message
}

const ARROWS: string[] = ['right', 'down', 'right_then_down', 'down_then_right']

function toClue(value: unknown): ClueView | null {
  const clue = value as Record<string, unknown> | null
  if (typeof clue !== 'object' || clue === null) {
    return null
  }
  if (typeof clue.text !== 'string' || typeof clue.arrow !== 'string') {
    return null
  }
  if (!ARROWS.includes(clue.arrow)) {
    return null
  }
  return { text: clue.text, arrow: clue.arrow as Arrow }
}

function toClues(value: unknown): ClueView[] | null {
  if (!Array.isArray(value) || value.length < 1 || value.length > 2) {
    return null
  }
  const clues: ClueView[] = []
  for (const item of value) {
    const clue = toClue(item)
    if (clue === null) {
      return null
    }
    clues.push(clue)
  }
  return clues
}

// Returns null for an unknown cell type or a malformed cell.
function toCell(value: unknown): CellView | null {
  const cell = value as Record<string, unknown> | null
  if (typeof cell !== 'object' || cell === null) {
    return null
  }
  const { row, column } = cell
  if (typeof row !== 'number' || typeof column !== 'number') {
    return null
  }
  if (cell.type === 'empty') {
    return { type: 'empty', row, column }
  }
  if (cell.type === 'clue') {
    const clues = toClues(cell.clues)
    return clues === null ? null : { type: 'clue', row, column, clues }
  }
  if (cell.type === 'letter') {
    const { letter, locked } = cell
    if (letter !== null && typeof letter !== 'string') {
      return null
    }
    if (typeof locked !== 'boolean') {
      return null
    }
    return { type: 'letter', row, column, letter, locked }
  }
  return null
}

function toGrid(value: unknown): GridView | null {
  const grid = value as Record<string, unknown> | null | undefined
  if (typeof grid !== 'object' || grid === null) {
    return null
  }
  const { width, height } = grid
  if (typeof width !== 'number' || typeof height !== 'number') {
    return null
  }
  if (!Array.isArray(grid.cells)) {
    return null
  }
  const cells: CellView[] = []
  for (const item of grid.cells) {
    const cell = toCell(item)
    if (cell === null) {
      return null
    }
    cells.push(cell)
  }
  if (!hasEveryPositionOnce(cells, width, height)) {
    return null
  }
  return { width, height, cells }
}

// True when there is one cell per position of the grid: no duplicate, none
// outside width x height, and so exactly width x height cells.
function hasEveryPositionOnce(cells: CellView[], width: number, height: number): boolean {
  if (cells.length !== width * height) {
    return false
  }
  const seen = new Set<number>()
  for (const cell of cells) {
    const inside =
      Number.isInteger(cell.row) &&
      Number.isInteger(cell.column) &&
      cell.row >= 0 &&
      cell.row < height &&
      cell.column >= 0 &&
      cell.column < width
    if (!inside) {
      return false
    }
    const position = cell.row * width + cell.column
    if (seen.has(position)) {
      return false
    }
    seen.add(position)
  }
  return true
}

function toSnapshot(message: Record<string, unknown>): Snapshot | null {
  const grid = toGrid(message.grid)
  if (grid === null) {
    return null
  }
  if (typeof message.seq !== 'number' || !Number.isInteger(message.seq)) {
    return null
  }
  return { type: 'snapshot', seq: message.seq, grid }
}

function toEvent(message: Record<string, unknown>): RoomEvent | null {
  if (typeof message.seq !== 'number' || !Number.isInteger(message.seq)) {
    return null
  }
  return { type: String(message.type), seq: message.seq }
}

// In this spec, applying an event only advances `seq`. What each event changes
// in the snapshot belongs to the spec that owns that event.
function applyEvent(session: RoomSession, event: RoomEvent): void {
  session.seq = event.seq
}

// Apply every buffered event that follows `seq`, one after the other.
function drainPending(session: RoomSession): void {
  while (session.seq !== null) {
    const nextSeq = session.seq + 1
    const index = session.pending.findIndex((event) => event.seq === nextSeq)
    if (index === -1) {
      return
    }
    const [event] = session.pending.splice(index, 1)
    applyEvent(session, event)
  }
}

function receiveSnapshot(session: RoomSession, snapshot: Snapshot): void {
  session.snapshot = snapshot
  session.seq = snapshot.seq
  session.status = 'joined'
  session.pending = session.pending.filter((event) => event.seq > snapshot.seq)
  drainPending(session)
}

function receiveEvent(session: RoomSession, event: RoomEvent): void {
  if (session.seq === null) {
    return // before the first snapshot: dropped
  }
  if (event.seq <= session.seq) {
    return // already included
  }
  if (event.seq === session.seq + 1) {
    applyEvent(session, event)
    drainPending(session)
    return
  }
  const isBuffered = session.pending.some((buffered) => buffered.seq === event.seq)
  if (!isBuffered) {
    session.pending.push(event)
  }
}

// Take one frame received from the server and update the session.
export function receiveFrame(session: RoomSession, text: string): void {
  const message = parseFrame(text)
  if (message === null) {
    return
  }
  if (message.type === 'snapshot') {
    const snapshot = toSnapshot(message)
    if (snapshot !== null) {
      receiveSnapshot(session, snapshot)
    }
    return
  }
  const event = toEvent(message)
  if (event !== null) {
    receiveEvent(session, event)
  }
}

export function statusAfterClose(code: number): RoomStatus {
  if (code === ROOM_NOT_FOUND_CLOSE_CODE) {
    return 'not_found'
  }
  if (code === THROTTLED_CLOSE_CODE) {
    return 'throttled'
  }
  return 'closed'
}

export function gridLabel(session: RoomSession): string {
  if (session.snapshot === null) {
    return ''
  }
  return `${session.snapshot.grid.width}x${session.snapshot.grid.height}`
}
