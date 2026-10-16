// The state of one room page and the rules that keep it in `seq` order.
// Plain functions: no socket and no DOM, so the rules are easy to read.

import { FEED_LIMIT, feedItemFor } from './activityFeed'
import type { FeedItem } from './activityFeed'

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
  | 'locked'
  | 'removed'
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
  // True while the letter in place was found wrong by the last check of it.
  wrong: boolean
  // True while the letter in place is a pencil letter (spec 020).
  pencil: boolean
}

// An edit this page sent and that has no answer yet (spec 015).
export interface PendingEdit {
  row: number
  column: number
  // `null` for an erase. For a confirmation, the letter it confirms.
  letter: string | null
  // The page's `seq` when the edit was made (spec 017 uses it).
  baseSeq: number | null
  // The message that made it: 'edit' (edit_letter or erase), 'pencil'
  // (pencil_edit) or 'confirm' (confirm_pencil).
  kind: 'edit' | 'pencil' | 'confirm'
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

// The cell and direction another player selected (spec 013).
export interface PlayerSelection {
  row: number
  column: number
  direction: 'across' | 'down'
}

export interface PlayerView {
  player_id: string
  nickname: string
  colour: number
  state: PlayerState
  // True for the host of the room (spec 014).
  is_host: boolean
  // True while the host muted the player's chat (spec 014, spec 022).
  muted: boolean
  // `null`: nothing selected, or the player is disconnected.
  selection: PlayerSelection | null
}

// The room settings the feed compares (spec 013).
export interface RoomSettingsView {
  help_mode: string
  letters: number
  words: number
  locked: boolean
}

export interface RevealBudgetView {
  letters: number
  words: number
}

// The open vote as the page keeps it (spec 025).
export interface VoteView {
  vote_id: number
  // The requester, who counts as a yes.
  player_id: string
  // What the vote is about, read from its request.
  kind: 'check_grid' | 'reveal_letter' | 'reveal_word'
}

// How a vote ended (spec 025).
type VoteOutcome = 'passed' | 'rejected' | 'timed_out'

// A word, named by its clue: the clue cell and the clue's index in it.
export interface ClueRefView {
  row: number
  column: number
  clue_index: number
}

// A clue flagged by a player (spec 021).
export interface FlagView {
  player_id: string
  clue: ClueRefView
}

// One chat message of the room (spec 022).
export interface ChatLine {
  seq: number
  player_id: string
  text: string
}

// The five reactions, in the order of spec 039's `Reaction` (spec 022).
export type ReactionValue = 'thumbs_up' | 'clap' | 'laugh' | 'wow' | 'thinking'

export const REACTION_VALUES: ReactionValue[] = ['thumbs_up', 'clap', 'laugh', 'wow', 'thinking']

// A reaction shown on a clue of the grid, for REACTION_MS from its arrival.
export interface ShownReaction {
  id: number
  player_id: string
  clue: ClueRefView
  reaction: ReactionValue
}

// Only what the client reads from a snapshot (later specs read more).
export interface Snapshot {
  type: 'snapshot'
  seq: number
  you: string
  resume_token: string
  grid: GridView
  players: PlayerView[]
  settings: RoomSettingsView
  // What is left to reveal, in letters and in words (spec 014).
  reveal_budget: RevealBudgetView
  solved: boolean
  // From the snapshot's open_vote, then from vote_opened and vote_closed.
  open_vote: VoteView | null
  // The flags of the room, one per flagging player (spec 021).
  flags: FlagView[]
  // The chat history of the room, in seq order (spec 022).
  chat: ChatLine[]
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
  // The activity feed, oldest first (spec 013).
  feed: FeedItem[]
  // The nickname of every player seen so far, by id; those who left stay.
  names: Map<string, string>
  // The vote ids this page voted on, kept while the page is open
  // (reconnections included).
  votedIds: number[]
  // The vote that closed last, and how, shown for VOTE_RESULT_MS.
  closedVote: { vote_id: number; outcome: VoteOutcome } | null
  // The reactions shown on clues, at most one per clue (spec 022).
  reactions: ShownReaction[]
  // The id given to the next shown reaction.
  nextReactionId: number
}

// A cell that flashes in the colour of the player who replaced my letter.
export interface CellFlash {
  id: number
  row: number
  column: number
  colour: number
}

export const FLASH_MS = 1000

// How long a reaction shows on its clue (spec 022).
export const REACTION_MS = 3000

export const ROOM_NOT_FOUND_CLOSE_CODE = 4404
export const THROTTLED_CLOSE_CODE = 4429
export const SESSION_REPLACED_CLOSE_CODE = 4001

// Heartbeat and reconnection (spec 017).
export const PING_INTERVAL_MS = 2000
export const SILENCE_LIMIT_MS = 4000
export const EDIT_SEND_INTERVAL_MS = 100
export const RECONNECT_DELAYS_MS: number[] = [1000, 2000, 4000, 8000]

// How long the banner shows the result of a vote that closed.
export const VOTE_RESULT_MS = 3000

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
    feed: [],
    names: new Map(),
    votedIds: [],
    closedVote: null,
    reactions: [],
    nextReactionId: 1,
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
    const wrong = cell.wrong === true
    const pencil = cell.pencil === true
    return { type: 'letter', row, column, letter, locked, revealed, author, wrong, pencil }
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
  const selection = toSelection(player.selection)
  return {
    player_id,
    nickname,
    colour,
    state: state as PlayerState,
    is_host: player.is_host === true,
    muted: player.muted === true,
    selection,
  }
}

// Returns null when the value is not a selection of the protocol.
function toSelection(value: unknown): PlayerSelection | null {
  const selection = value as Record<string, unknown> | null | undefined
  if (typeof selection !== 'object' || selection === null) {
    return null
  }
  const { row, column, direction } = selection
  if (typeof row !== 'number' || typeof column !== 'number') {
    return null
  }
  if (direction !== 'across' && direction !== 'down') {
    return null
  }
  return { row, column, direction }
}

const DEFAULT_SETTINGS: RoomSettingsView = {
  help_mode: 'free',
  letters: 5,
  words: 1,
  locked: false,
}

// The settings of a snapshot or of a settings_changed; the defaults of the
// room when the value holds none.
function toSettings(value: unknown): RoomSettingsView {
  const settings = value as Record<string, unknown> | null | undefined
  if (typeof settings !== 'object' || settings === null) {
    return { ...DEFAULT_SETTINGS }
  }
  const budget = settings.reveal_budget as Record<string, unknown> | null | undefined
  if (typeof budget !== 'object' || budget === null) {
    return { ...DEFAULT_SETTINGS }
  }
  return {
    help_mode: typeof settings.help_mode === 'string' ? settings.help_mode : 'free',
    letters: Number(budget.letters),
    words: Number(budget.words),
    locked: settings.locked === true,
  }
}

// The remaining reveal budget of a snapshot, a settings_changed or a reveal_result.
function toRevealBudget(value: unknown): RevealBudgetView {
  const budget = value as Record<string, unknown> | null | undefined
  if (typeof budget !== 'object' || budget === null) {
    return { letters: 0, words: 0 }
  }
  return { letters: Number(budget.letters), words: Number(budget.words) }
}

// What a vote is about: a grid check, or the reveal of a letter or a word. Any
// other request gives null: the page shows no banner for it.
function voteKindOf(value: unknown): VoteView['kind'] | null {
  const request = value as Record<string, unknown> | null | undefined
  if (typeof request !== 'object' || request === null) {
    return null
  }
  const target = request.target as Record<string, unknown> | null | undefined
  if (typeof target !== 'object' || target === null) {
    return null
  }
  if (request.type === 'check' && target.scope === 'grid') {
    return 'check_grid'
  }
  if (request.type === 'reveal' && target.scope === 'letter') {
    return 'reveal_letter'
  }
  if (request.type === 'reveal' && target.scope === 'word') {
    return 'reveal_word'
  }
  return null
}

// The vote of a vote_opened object (a snapshot's open_vote or the event itself),
// or null when there is none or it is about another kind of request.
function toVoteView(value: unknown): VoteView | null {
  const vote = value as Record<string, unknown> | null | undefined
  if (typeof vote !== 'object' || vote === null) {
    return null
  }
  const { vote_id, player_id } = vote
  if (typeof vote_id !== 'number' || !Number.isInteger(vote_id)) {
    return null
  }
  if (typeof player_id !== 'string') {
    return null
  }
  const kind = voteKindOf(vote.request)
  if (kind === null) {
    return null
  }
  return { vote_id, player_id, kind }
}

const VOTE_OUTCOMES: string[] = ['passed', 'rejected', 'timed_out']

// A vote_closed clears the open vote and keeps how it ended, for the banner.
function applyVoteClosed(session: RoomSession, snapshot: Snapshot, event: RoomEvent): void {
  snapshot.open_vote = null
  const { vote_id, outcome } = event.message
  if (typeof vote_id !== 'number' || typeof outcome !== 'string') {
    return
  }
  if (!VOTE_OUTCOMES.includes(outcome)) {
    return
  }
  session.closedVote = { vote_id, outcome: outcome as VoteOutcome }
}

// Returns null when the value is not a clue reference of three integers.
function toClueRef(value: unknown): ClueRefView | null {
  const clue = value as Record<string, unknown> | null | undefined
  if (typeof clue !== 'object' || clue === null) {
    return null
  }
  const { row, column, clue_index } = clue
  if (!Number.isInteger(row) || !Number.isInteger(column) || !Number.isInteger(clue_index)) {
    return null
  }
  return { row: row as number, column: column as number, clue_index: clue_index as number }
}

// The flags of a snapshot. An entry that is not an object with a string
// player_id and a clue of three integers is skipped.
function toFlags(value: unknown): FlagView[] {
  if (!Array.isArray(value)) {
    return []
  }
  const flags: FlagView[] = []
  for (const item of value) {
    const entry = item as Record<string, unknown> | null
    if (typeof entry !== 'object' || entry === null || typeof entry.player_id !== 'string') {
      continue
    }
    const clue = toClueRef(entry.clue)
    if (clue !== null) {
      flags.push({ player_id: entry.player_id, clue })
    }
  }
  return flags
}

// A flag_changed sets the player's flag, replacing their previous one; with
// `clue: null` it removes it (spec 021).
function applyFlagChanged(snapshot: Snapshot, event: RoomEvent): void {
  const { player_id, clue } = event.message
  if (typeof player_id !== 'string') {
    return
  }
  const others = snapshot.flags.filter((flag) => flag.player_id !== player_id)
  if (clue === null) {
    snapshot.flags = others
    return
  }
  const newClue = toClueRef(clue)
  if (newClue !== null) {
    others.push({ player_id, clue: newClue })
    snapshot.flags = others
  }
}

// The chat lines of a snapshot. A line that is not an object with an integer
// seq and a string player_id and text is skipped (spec 022).
function toChat(value: unknown): ChatLine[] {
  if (!Array.isArray(value)) {
    return []
  }
  const lines: ChatLine[] = []
  for (const item of value) {
    const line = toChatLine(item)
    if (line !== null) {
      lines.push(line)
    }
  }
  return lines
}

// Returns null when the value is not a chat line of the protocol.
function toChatLine(value: unknown): ChatLine | null {
  const line = value as Record<string, unknown> | null
  if (typeof line !== 'object' || line === null) {
    return null
  }
  const { seq, player_id, text } = line
  if (typeof seq !== 'number' || !Number.isInteger(seq)) {
    return null
  }
  if (typeof player_id !== 'string' || typeof text !== 'string') {
    return null
  }
  return { seq, player_id, text }
}

// A chat_message adds its line at the end of the history, unless a line with
// its seq is already there (spec 022).
function applyChatMessage(snapshot: Snapshot, event: RoomEvent): void {
  const line = toChatLine(event.message)
  if (line === null) {
    return
  }
  const isKnown = snapshot.chat.some((kept) => kept.seq === line.seq)
  if (!isKnown) {
    snapshot.chat.push(line)
  }
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
    settings: toSettings(message.settings),
    reveal_budget: toRevealBudget(message.reveal_budget),
    solved: message.solved === true,
    open_vote: toVoteView(message.open_vote),
    flags: toFlags(message.flags),
    chat: toChat(message.chat),
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
    // The player leaves with their flag (spec 021).
    snapshot.players = snapshot.players.filter((player) => player.player_id !== playerId)
    snapshot.flags = snapshot.flags.filter((flag) => flag.player_id !== playerId)
    return
  }
  if (event.type === 'host_changed') {
    for (const player of snapshot.players) {
      player.is_host = player.player_id === playerId
    }
    return
  }
  if (event.type === 'player_muted') {
    for (const player of snapshot.players) {
      if (player.player_id === playerId) {
        player.muted = message.muted === true
      }
    }
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
        if (player.state === 'disconnected') {
          player.selection = null
        }
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

// A cell_locked locks the cell with its letter, never a pencil one; a reveal
// also clears the author.
function applyCellLocked(snapshot: Snapshot, event: RoomEvent): void {
  const { message } = event
  const cell = letterCellAt(snapshot, message.row, message.column)
  if (cell === null) {
    return
  }
  cell.letter = typeof message.letter === 'string' ? message.letter : null
  cell.locked = true
  cell.wrong = false
  cell.pencil = false
  cell.revealed = message.revealed === true
  if (cell.revealed) {
    cell.author = null
  }
}

// A check_result strikes through the letters of its wrong list.
function applyCheckResult(snapshot: Snapshot, event: RoomEvent): void {
  const wrongCells: Array<{ row: number; column: number }> = Array.isArray(event.message.wrong)
    ? event.message.wrong
    : []
  for (const reference of wrongCells) {
    const cell = letterCellAt(snapshot, reference.row, reference.column)
    if (cell !== null) {
      cell.wrong = true
    }
  }
}

// True when my letter_changed is the answer to my oldest pending edit: the same
// cell, the same letter and the same pencil flag (true for a pencil edit only).
// Otherwise it is the result of an undo (spec 018, spec 020).
function answersOldestPendingEdit(session: RoomSession, event: RoomEvent): boolean {
  const oldest = session.pendingEdits[0]
  if (oldest === undefined) {
    return false
  }
  const { message } = event
  const letter = typeof message.letter === 'string' ? message.letter : null
  const pencil = message.pencil === true
  const isPencilEdit = oldest.kind === 'pencil'
  const isSameCell = oldest.row === message.row && oldest.column === message.column
  return isSameCell && oldest.letter === letter && isPencilEdit === pencil
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
    cell.pencil = message.pencil === true
    cell.wrong = false
    cell.author = letter === null || typeof message.player_id !== 'string' ? null : message.player_id
  }
  if (message.player_id === snapshot.you && answersOldestPendingEdit(session, event)) {
    session.pendingEdits.shift()
  }
}

// Add the feed line of an event, before the event changes the snapshot.
function addFeedItem(session: RoomSession, snapshot: Snapshot, event: RoomEvent): void {
  if (event.type === 'player_joined') {
    const player = toPlayer(event.message.player)
    if (player !== null) {
      session.names.set(player.player_id, player.nickname)
    }
  }
  const item = feedItemFor(snapshot, session.names, event)
  if (item === null) {
    return
  }
  session.feed.push(item)
  if (session.feed.length > FEED_LIMIT) {
    session.feed.splice(0, session.feed.length - FEED_LIMIT)
  }
}

function applyEvent(session: RoomSession, event: RoomEvent): void {
  session.seq = event.seq
  if (session.snapshot !== null) {
    addFeedItem(session, session.snapshot, event)
  }
  if (event.type === 'settings_changed' && session.snapshot !== null) {
    // The next settings_changed is compared with these.
    session.snapshot.settings = toSettings(event.message.settings)
    session.snapshot.reveal_budget = toRevealBudget(event.message.reveal_budget)
  }
  if (event.type === 'letter_changed' && session.snapshot !== null) {
    applyLetterChanged(session, session.snapshot, event)
  }
  if (event.type === 'cell_locked' && session.snapshot !== null) {
    applyCellLocked(session.snapshot, event)
  }
  if (event.type === 'check_result' && session.snapshot !== null) {
    applyCheckResult(session.snapshot, event)
  }
  if (event.type === 'reveal_result' && session.snapshot !== null) {
    // What is left after the reveal; its letters come in the cell_locked events.
    session.snapshot.reveal_budget = toRevealBudget(event.message.reveal_budget)
  }
  if (event.type === 'vote_opened' && session.snapshot !== null) {
    // A new vote replaces the result of the last one at once.
    session.snapshot.open_vote = toVoteView(event.message)
    session.closedVote = null
  }
  if (event.type === 'vote_closed' && session.snapshot !== null) {
    applyVoteClosed(session, session.snapshot, event)
  }
  if (event.type === 'flag_changed' && session.snapshot !== null) {
    applyFlagChanged(session.snapshot, event)
  }
  if (event.type === 'chat_message' && session.snapshot !== null) {
    applyChatMessage(session.snapshot, event)
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
  for (const player of snapshot.players) {
    session.names.set(player.player_id, player.nickname)
  }
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
  if (message.type === 'selection_moved') {
    receiveSelectionMoved(session, message)
    return
  }
  if (message.type === 'reaction') {
    receiveReaction(session, message)
    return
  }
  const event = toEvent(message)
  if (event !== null) {
    receiveEvent(session, event)
  }
}

// Another player's selection moved. It has no seq, so it is applied at once;
// never for me, and never for a disconnected player.
function receiveSelectionMoved(session: RoomSession, message: Record<string, unknown>): void {
  if (session.snapshot === null || message.player_id === session.snapshot.you) {
    return
  }
  for (const player of session.snapshot.players) {
    if (player.player_id === message.player_id && player.state !== 'disconnected') {
      player.selection = toSelection(message.selection)
    }
  }
}

// True when the clue reference names a clue of the grid.
function isClueOfGrid(grid: GridView, clue: ClueRefView): boolean {
  for (const cell of grid.cells) {
    if (cell.type === 'clue' && cell.row === clue.row && cell.column === clue.column) {
      return clue.clue_index >= 0 && clue.clue_index < cell.clues.length
    }
  }
  return false
}

// A reaction has no seq: it is shown at once, once the page has a snapshot, and
// only on a clue of the grid. A newer reaction on the same clue replaces the
// older one, so a clue shows at most one (spec 022).
function receiveReaction(session: RoomSession, message: Record<string, unknown>): void {
  if (session.snapshot === null || typeof message.player_id !== 'string') {
    return
  }
  const clue = toClueRef(message.clue)
  const reaction = REACTION_VALUES.find((value) => value === message.reaction)
  if (clue === null || reaction === undefined) {
    return
  }
  if (!isClueOfGrid(session.snapshot.grid, clue)) {
    return
  }
  const others = session.reactions.filter(
    (shown) =>
      shown.clue.row !== clue.row ||
      shown.clue.column !== clue.column ||
      shown.clue.clue_index !== clue.clue_index,
  )
  others.push({ id: session.nextReactionId, player_id: message.player_id, clue, reaction })
  session.nextReactionId += 1
  session.reactions = others
}

// Stop showing a reaction: used when its REACTION_MS are over.
export function endReaction(session: RoomSession, reactionId: number): void {
  session.reactions = session.reactions.filter((shown) => shown.id !== reactionId)
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
  // Locked and removed are final, whatever the page was doing (spec 014).
  if (message.code === 'room_locked') {
    session.status = 'locked'
    return
  }
  if (message.code === 'removed') {
    session.status = 'removed'
    return
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

// The status after a final close. A refusal already set its own status (full,
// locked or removed): it stays as it is.
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
  kind: PendingEdit['kind'],
): void {
  session.pendingEdits.push({ row, column, letter, baseSeq: session.seq, kind })
}

// What a cell shows: the newest pending edit of the cell, else the confirmed
// letter; a locked cell always shows its confirmed letter (specs 015, 016). The
// pencil flag of a pending edit is true for a pencil edit only (spec 020).
export function shownCell(
  cell: LetterCellView,
  pendingEdits: PendingEdit[],
): { letter: string | null; pencil: boolean; unconfirmed: boolean } {
  if (!cell.locked) {
    for (let index = pendingEdits.length - 1; index >= 0; index--) {
      const edit = pendingEdits[index]
      if (edit.row === cell.row && edit.column === cell.column) {
        return { letter: edit.letter, pencil: edit.kind === 'pencil', unconfirmed: true }
      }
    }
  }
  return { letter: cell.letter, pencil: cell.pencil, unconfirmed: false }
}

// The grid as the player sees it: every letter cell holds its shown letter, so
// pending edits count as filled or cleared.
export function shownGrid(grid: GridView, pendingEdits: PendingEdit[]): GridView {
  const cells: CellView[] = []
  for (const cell of grid.cells) {
    if (cell.type === 'letter') {
      const shown = shownCell(cell, pendingEdits)
      cells.push({ ...cell, letter: shown.letter, pencil: shown.pencil })
    } else {
      cells.push(cell)
    }
  }
  return { width: grid.width, height: grid.height, cells }
}
