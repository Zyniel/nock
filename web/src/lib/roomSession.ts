// The state of one room page and the rules that keep it in `seq` order.
// Plain functions: no socket and no DOM, so the rules are easy to read.

export type RoomStatus =
  | 'connecting'
  | 'nickname'
  | 'joining'
  | 'joined'
  | 'reconnecting'
  | 'full'
  | 'replaced'
  | 'not_found'
  | 'throttled'
  | 'closed'

export type PlayerState = 'active' | 'idle' | 'disconnected'

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
  // True when a reveal locked the cell (spec 024).
  revealed: boolean
  // The player id of the author, `null` when none.
  author: string | null
}

// An edit this page sent and that has no answer yet (spec 015).
export interface PendingEdit {
  row: number
  column: number
  // `null` for an erase.
  letter: string | null
  // The page's `seq` when the edit was made (spec 017 uses it).
  baseSeq: number | null
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

export interface PlayerView {
  player_id: string
  nickname: string
  colour: number
  state: PlayerState
}

// Only what the client reads from a snapshot (later specs read more).
export interface Snapshot {
  type: 'snapshot'
  seq: number
  you: string
  resume_token: string
  grid: GridView
  players: PlayerView[]
  solved: boolean
}

// A message with an integer `seq` that is not a snapshot.
export interface RoomEvent {
  type: string
  seq: number
  // The whole message, for the events that change the snapshot.
  message: Record<string, unknown>
}

export interface RoomSession {
  status: RoomStatus
  snapshot: Snapshot | null
  // `null` until the first snapshot.
  seq: number | null
  // Events that arrived too early, waiting for the ones before them.
  pending: RoomEvent[]
  // True after the server refused the nickname of the last join.
  nicknameRefused: boolean
  // True once the grid is solved: a snapshot with `solved: true`, or `grid_solved`.
  solved: boolean
  // The edits sent and not answered yet, oldest first.
  pendingEdits: PendingEdit[]
  // The cells flashing because another player replaced my letter (spec 016).
  flashes: CellFlash[]
  // The id given to the next flash.
  nextFlashId: number
  // How many times the server answered an undo with nothing_to_undo (spec 018).
  undoRefusals: number
  // True once the server refused the join for good: room full, locked or the
  // player removed. The socket close that follows ends the attempts (spec 017).
  isRefused: boolean
}

// A cell that flashes in the colour of the player who replaced my letter.
export interface CellFlash {
  id: number
  row: number
  column: number
  colour: number
}

export const FLASH_MS = 1000

export const ROOM_NOT_FOUND_CLOSE_CODE = 4404
export const THROTTLED_CLOSE_CODE = 4429
export const SESSION_REPLACED_CLOSE_CODE = 4001

// Heartbeat and reconnection (spec 017).
export const PING_INTERVAL_MS = 2000
export const SILENCE_LIMIT_MS = 4000
export const EDIT_SEND_INTERVAL_MS = 100
export const RECONNECT_DELAYS_MS: number[] = [1000, 2000, 4000, 8000]

const PLAYER_STATES: string[] = ['active', 'idle', 'disconnected']
const MAX_COLOUR = 7

export function newSession(): RoomSession {
  return {
    status: 'connecting',
    snapshot: null,
    seq: null,
    pending: [],
    nicknameRefused: false,
    solved: false,
    pendingEdits: [],
    flashes: [],
    nextFlashId: 1,
    undoRefusals: 0,
    isRefused: false,
  }
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
    const author = typeof cell.author === 'string' ? cell.author : null
    const revealed = cell.revealed === true
    return { type: 'letter', row, column, letter, locked, revealed, author }
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

// Returns null when the value is not a player of the protocol.
function toPlayer(value: unknown): PlayerView | null {
  const player = value as Record<string, unknown> | null
  if (typeof player !== 'object' || player === null) {
    return null
  }
  const { player_id, nickname, colour, state } = player
  if (typeof player_id !== 'string' || typeof nickname !== 'string') {
    return null
  }
  if (typeof colour !== 'number' || !Number.isInteger(colour)) {
    return null
  }
  if (colour < 0 || colour > MAX_COLOUR) {
    return null
  }
  if (typeof state !== 'string' || !PLAYER_STATES.includes(state)) {
    return null
  }
  return { player_id, nickname, colour, state: state as PlayerState }
}

function toPlayers(value: unknown): PlayerView[] | null {
  if (!Array.isArray(value)) {
    return null
  }
  const players: PlayerView[] = []
  for (const item of value) {
    const player = toPlayer(item)
    if (player === null) {
      return null
    }
    players.push(player)
  }
  return players
}

function toSnapshot(message: Record<string, unknown>): Snapshot | null {
  const grid = toGrid(message.grid)
  if (grid === null) {
    return null
  }
  if (typeof message.seq !== 'number' || !Number.isInteger(message.seq)) {
    return null
  }
  const players = toPlayers(message.players)
  if (players === null) {
    return null
  }
  const { you, resume_token } = message
  if (typeof you !== 'string' || typeof resume_token !== 'string') {
    return null
  }
  return {
    type: 'snapshot',
    seq: message.seq,
    you,
    resume_token,
    grid,
    players,
    solved: message.solved === true,
  }
}

function toEvent(message: Record<string, unknown>): RoomEvent | null {
  if (typeof message.seq !== 'number' || !Number.isInteger(message.seq)) {
    return null
  }
  return { type: String(message.type), seq: message.seq, message }
}

// Change the kept snapshot for the events that concern the players. What the
// other events change belongs to the spec that owns them.
function applyToPlayers(snapshot: Snapshot, event: RoomEvent): void {
  const { message } = event
  if (event.type === 'player_joined') {
    const player = toPlayer(message.player)
    if (player !== null) {
      snapshot.players.push(player)
    }
    return
  }
  const playerId = message.player_id
  if (event.type === 'player_left') {
    snapshot.players = snapshot.players.filter((player) => player.player_id !== playerId)
    return
  }
  if (event.type === 'player_state_changed') {
    const state = message.state
    if (typeof state !== 'string' || !PLAYER_STATES.includes(state)) {
      return
    }
    for (const player of snapshot.players) {
      if (player.player_id === playerId) {
        player.state = state as PlayerState
      }
    }
  }
}

function letterCellAt(snapshot: Snapshot, row: unknown, column: unknown): LetterCellView | null {
  for (const cell of snapshot.grid.cells) {
    if (cell.type === 'letter' && cell.row === row && cell.column === column) {
      return cell
    }
  }
  return null
}

// True when `playerId`, another player, changes a confirmed letter that I wrote.
function isMyLetterReplaced(snapshot: Snapshot, cell: LetterCellView, playerId: unknown): boolean {
  return playerId !== snapshot.you && cell.letter !== null && cell.author === snapshot.you
}

// Flash the cell in the colour of `playerId`; a player who is gone has colour 0.
// A new flash on the same cell replaces the old one, so its time restarts.
function startFlash(
  session: RoomSession,
  snapshot: Snapshot,
  cell: LetterCellView,
  playerId: unknown,
): void {
  let colour = 0
  for (const player of snapshot.players) {
    if (player.player_id === playerId) {
      colour = player.colour
    }
  }
  const others = session.flashes.filter(
    (flash) => flash.row !== cell.row || flash.column !== cell.column,
  )
  others.push({ id: session.nextFlashId, row: cell.row, column: cell.column, colour })
  session.nextFlashId += 1
  session.flashes = others
}

// Stop a flash: used when its FLASH_MS are over.
export function endFlash(session: RoomSession, flashId: number): void {
  session.flashes = session.flashes.filter((flash) => flash.id !== flashId)
}

// A cell_locked locks the cell with its letter; a reveal also clears the author.
function applyCellLocked(snapshot: Snapshot, event: RoomEvent): void {
  const { message } = event
  const cell = letterCellAt(snapshot, message.row, message.column)
  if (cell === null) {
    return
  }
  cell.letter = typeof message.letter === 'string' ? message.letter : null
  cell.locked = true
  cell.revealed = message.revealed === true
  if (cell.revealed) {
    cell.author = null
  }
}

// True when my letter_changed is the answer to my oldest pending edit: the same
// cell and the same letter. Otherwise it is the result of an undo (spec 018).
function answersOldestPendingEdit(session: RoomSession, event: RoomEvent): boolean {
  const oldest = session.pendingEdits[0]
  if (oldest === undefined) {
    return false
  }
  const { message } = event
  const letter = typeof message.letter === 'string' ? message.letter : null
  return oldest.row === message.row && oldest.column === message.column && oldest.letter === letter
}

// A letter_changed updates the confirmed grid; one from me answers my oldest
// pending edit when it matches it (spec 015, spec 018).
function applyLetterChanged(session: RoomSession, snapshot: Snapshot, event: RoomEvent): void {
  const { message } = event
  const cell = letterCellAt(snapshot, message.row, message.column)
  const letter = typeof message.letter === 'string' ? message.letter : null
  if (cell !== null) {
    if (isMyLetterReplaced(snapshot, cell, message.player_id)) {
      startFlash(session, snapshot, cell, message.player_id)
    }
    cell.letter = letter
    cell.author = letter === null || typeof message.player_id !== 'string' ? null : message.player_id
  }
  if (message.player_id === snapshot.you && answersOldestPendingEdit(session, event)) {
    session.pendingEdits.shift()
  }
}

function applyEvent(session: RoomSession, event: RoomEvent): void {
  session.seq = event.seq
  if (event.type === 'letter_changed' && session.snapshot !== null) {
    applyLetterChanged(session, session.snapshot, event)
  }
  if (event.type === 'cell_locked' && session.snapshot !== null) {
    applyCellLocked(session.snapshot, event)
  }
  if (event.type === 'grid_solved') {
    session.solved = true
  }
  if (session.snapshot !== null) {
    applyToPlayers(session.snapshot, event)
  }
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
  session.nicknameRefused = false
  session.solved = snapshot.solved
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
  if (message.type === 'error') {
    receiveError(session, message)
    return
  }
  const event = toEvent(message)
  if (event !== null) {
    receiveEvent(session, event)
  }
}

// The errors that answer one edit (spec 015): each removes the oldest pending edit.
const EDIT_ERROR_CODES: string[] = [
  'rate_limited',
  'not_a_letter_cell',
  'cell_locked',
  'stale_edit',
  'grid_solved',
]

// The errors after which the server closes the socket and the page must not retry.
const REFUSAL_ERROR_CODES: string[] = ['room_full', 'room_locked', 'removed']

// The errors that answer an edit, or a join: a refused nickname, or a full room.
function receiveError(session: RoomSession, message: Record<string, unknown>): void {
  if (message.code === 'nothing_to_undo') {
    session.undoRefusals += 1
    return
  }
  if (typeof message.code === 'string' && EDIT_ERROR_CODES.includes(message.code)) {
    session.pendingEdits.shift()
    return
  }
  if (typeof message.code === 'string' && REFUSAL_ERROR_CODES.includes(message.code)) {
    session.isRefused = true
  }
  if (session.status !== 'joining' && session.status !== 'reconnecting') {
    return
  }
  if (message.code === 'invalid_nickname' && session.status === 'joining') {
    session.status = 'nickname'
    session.nicknameRefused = true
  } else if (message.code === 'room_full') {
    session.status = 'full'
  }
}

// True when the close of the socket ends the attempts: a close code that is
// final, or a close that follows a refusal of the join.
export function isFinalClose(session: RoomSession, code: number): boolean {
  const isFinalCode =
    code === ROOM_NOT_FOUND_CLOSE_CODE ||
    code === THROTTLED_CLOSE_CODE ||
    code === SESSION_REPLACED_CLOSE_CODE
  return isFinalCode || session.isRefused
}

// The status after a final close. A refusal already set its own status (a full
// room) or has none yet (locked, removed): it stays as it is.
export function statusAfterFinalClose(code: number, current: RoomStatus): RoomStatus {
  if (code === ROOM_NOT_FOUND_CLOSE_CODE) {
    return 'not_found'
  }
  if (code === THROTTLED_CLOSE_CODE) {
    return 'throttled'
  }
  if (code === SESSION_REPLACED_CLOSE_CODE) {
    return 'replaced'
  }
  return current
}

// The delay before reconnection try number `attempt` (0 for the first).
export function reconnectDelay(attempt: number): number {
  const last = RECONNECT_DELAYS_MS.length - 1
  return RECONNECT_DELAYS_MS[Math.min(attempt, last)]
}

// The status once the connection is lost. After a snapshot the page shows the
// offline banner; before it, it keeps asking for a join, with no banner.
export function statusAfterLoss(session: RoomSession): RoomStatus {
  if (session.snapshot !== null) {
    return 'reconnecting'
  }
  return 'connecting'
}

export function gridLabel(session: RoomSession): string {
  if (session.snapshot === null) {
    return ''
  }
  return `${session.snapshot.grid.width}x${session.snapshot.grid.height}`
}

// Remember an edit just sent, until the server answers it.
export function addPendingEdit(
  session: RoomSession,
  row: number,
  column: number,
  letter: string | null,
): void {
  session.pendingEdits.push({ row, column, letter, baseSeq: session.seq })
}

// What a cell shows: the newest pending edit of the cell, else its confirmed
// letter. A locked cell always shows its confirmed letter.
export function shownCell(
  cell: LetterCellView,
  pendingEdits: PendingEdit[],
): { letter: string | null; unconfirmed: boolean } {
  if (!cell.locked) {
    for (let index = pendingEdits.length - 1; index >= 0; index--) {
      const edit = pendingEdits[index]
      if (edit.row === cell.row && edit.column === cell.column) {
        return { letter: edit.letter, unconfirmed: true }
      }
    }
  }
  return { letter: cell.letter, unconfirmed: false }
}

// The grid as the player sees it: every letter cell holds its shown letter, so
// pending edits count as filled or cleared.
export function shownGrid(grid: GridView, pendingEdits: PendingEdit[]): GridView {
  const cells: CellView[] = []
  for (const cell of grid.cells) {
    if (cell.type === 'letter') {
      cells.push({ ...cell, letter: shownCell(cell, pendingEdits).letter })
    } else {
      cells.push(cell)
    }
  }
  return { width: grid.width, height: grid.height, cells }
}
