// The activity feed of a room (spec 013): which events add a line, and its text,
// and the lines of a catch-up (spec 034). Plain functions: no DOM and no socket.

import { t } from './i18n'
import { displayNickname } from './nickname'
import type { ChatLine, RoomEvent, RoomSettingsView, Snapshot } from './roomSession'

// The feed keeps the newest items only.
export const FEED_LIMIT = 100

export interface FeedItem {
  seq: number
  kind: string
  text: string
  // The player the line is about (the event's player_id, or the player who
  // joined), or null when the event names none. The new-events dot of « Salon »
  // counts the lines of the other players only (spec 043).
  playerId: string | null
  // True for a check that found no wrong letter: its line is green (spec 043).
  isCleanCheck: boolean
}

// The text pictogram, or the flag icon, that starts the line of an event of
// each kind (spec 043, "Discussion: the stream"). The other kinds have none.
export type LinePictogram = 'joined' | 'left' | 'check' | 'reveal' | 'flag'

const PICTOGRAM_OF_KIND: Record<string, LinePictogram> = {
  player_joined: 'joined',
  player_left: 'left',
  player_removed: 'left',
  player_timed_out: 'left',
  check: 'check',
  reveal: 'reveal',
  flag: 'flag',
}

// The pictogram that starts a line of `kind`, or null when it has none.
export function pictogramOfKind(kind: string): LinePictogram | null {
  return PICTOGRAM_OF_KIND[kind] ?? null
}

// The kind and the text of a line, before the page adds its seq and player.
interface LineText {
  kind: string
  text: string
}

// A feed item as the page keeps it. Items are not unique by seq: one letter
// that completes two words gives two items of one seq (spec 034), so the page
// tells them apart by `id`, a number given once per page.
export interface KeptFeedItem extends FeedItem {
  id: number
}

// One item of the Salon's stream (spec 043): a chat message or an event line.
export type StreamEntry =
  | { kind: 'message'; key: string; seq: number; line: ChatLine }
  | { kind: 'event'; key: string; seq: number; item: KeptFeedItem }

// The stream of the Salon: the shown chat lines and the feed's event lines in one
// list, in seq order, oldest first. Each kind keeps its own cap before they meet
// (the callers pass the lines they keep), and two items of one seq keep their
// own order (spec 043).
export function streamEntries(lines: ChatLine[], feed: KeptFeedItem[]): StreamEntry[] {
  const entries: StreamEntry[] = []
  let lineIndex = 0
  let feedIndex = 0
  while (lineIndex < lines.length || feedIndex < feed.length) {
    const line = lineIndex < lines.length ? lines[lineIndex] : null
    const item = feedIndex < feed.length ? feed[feedIndex] : null
    const takeLine = line !== null && (item === null || line.seq < item.seq)
    if (takeLine && line !== null) {
      entries.push({ kind: 'message', key: `message-${line.seq}`, seq: line.seq, line })
      lineIndex += 1
    } else if (item !== null) {
      entries.push({ kind: 'event', key: `event-${item.id}`, seq: item.seq, item })
      feedIndex += 1
    }
  }
  return entries
}

// Drop the oldest items of a feed that holds more than FEED_LIMIT.
export function trimFeed(feed: KeptFeedItem[]): void {
  if (feed.length > FEED_LIMIT) {
    feed.splice(0, feed.length - FEED_LIMIT)
  }
}

// Put `items`, in seq order, into the feed in seq order among the items it
// holds: each goes after every item of its seq or lower. Then the feed keeps its
// newest FEED_LIMIT items.
export function insertFeedItems(feed: KeptFeedItem[], items: KeptFeedItem[]): void {
  for (const item of items) {
    let index = feed.findIndex((kept) => kept.seq > item.seq)
    if (index === -1) {
      index = feed.length
    }
    feed.splice(index, 0, item)
  }
  trimFeed(feed)
}

// The feed item of a word completed during an absence (spec 034): `clue` names
// the word by its clue.
export function wordCompletedItem(
  snapshot: Snapshot,
  names: Map<string, string>,
  seq: number,
  playerId: string,
  clue: unknown,
): FeedItem {
  const text = t('feed.word_completed', {
    name: nameOf(names, playerId),
    clue: clueText(snapshot, clue),
  })
  return { seq, kind: 'word_completed', text, playerId, isCleanCheck: false }
}

// The nickname of a player known to the page, even one who left, as a page
// shows it; "Quelqu'un" for a player the page never knew.
export function nameOf(names: Map<string, string>, playerId: unknown): string {
  const name = typeof playerId === 'string' ? names.get(playerId) : undefined
  return name === undefined ? t('feed.someone') : displayNickname(name)
}

function helpModeText(helpMode: string): string {
  if (helpMode === 'vote') {
    return t('settings.help_mode.vote')
  }
  if (helpMode === 'none') {
    return t('settings.help_mode.none')
  }
  return t('settings.help_mode.free')
}

// The text of the clue that `value` ({row, column, clue_index}) names, or ''.
function clueText(snapshot: Snapshot, value: unknown): string {
  const ref = value as Record<string, unknown>
  for (const cell of snapshot.grid.cells) {
    if (cell.type !== 'clue' || cell.row !== ref.row || cell.column !== ref.column) {
      continue
    }
    const clue = cell.clues[Number(ref.clue_index)]
    return clue === undefined ? '' : clue.text
  }
  return ''
}

// The scope ('letter', 'word' or 'grid') of the target of a check or a reveal.
function scopeOf(event: RoomEvent): unknown {
  const target = event.message.target as Record<string, unknown> | null
  if (target === null || typeof target !== 'object') {
    return null
  }
  return target.scope
}

function leftLine(event: RoomEvent, name: string): LineText {
  const { reason } = event.message
  if (reason === 'removed') {
    return { kind: 'player_removed', text: t('feed.player_removed', { name }) }
  }
  if (reason === 'timed_out') {
    return { kind: 'player_timed_out', text: t('feed.player_timed_out', { name }) }
  }
  return { kind: 'player_left', text: t('feed.player_left', { name }) }
}

function checkLine(event: RoomEvent, name: string): LineText | null {
  const scope = scopeOf(event)
  if (scope === 'letter') {
    return { kind: 'check', text: t('feed.check.letter', { name }) }
  }
  if (scope === 'word') {
    return { kind: 'check', text: t('feed.check.word', { name }) }
  }
  if (scope === 'grid') {
    return { kind: 'check', text: t('feed.check.grid', { name }) }
  }
  return null
}

function revealLine(event: RoomEvent, name: string): LineText | null {
  const scope = scopeOf(event)
  if (scope === 'letter') {
    return { kind: 'reveal', text: t('feed.reveal.letter', { name }) }
  }
  if (scope === 'word') {
    return { kind: 'reveal', text: t('feed.reveal.word', { name }) }
  }
  return null
}

// The settings an event carries, or null when it is malformed.
function eventSettings(event: RoomEvent): RoomSettingsView | null {
  const settings = event.message.settings as Record<string, unknown> | null
  if (settings === null || typeof settings !== 'object') {
    return null
  }
  const budget = settings.reveal_budget as Record<string, unknown> | null
  if (budget === null || typeof budget !== 'object') {
    return null
  }
  return {
    help_mode: String(settings.help_mode),
    letters: Number(budget.letters),
    words: Number(budget.words),
    locked: settings.locked === true,
  }
}

function settingsLine(snapshot: Snapshot, event: RoomEvent, name: string): LineText | null {
  const next = eventSettings(event)
  if (next === null) {
    return null
  }
  const before = snapshot.settings
  const onlyLockChanged =
    before.help_mode === next.help_mode &&
    before.letters === next.letters &&
    before.words === next.words &&
    before.locked !== next.locked
  if (onlyLockChanged && next.locked) {
    return { kind: 'room_locked', text: t('feed.room_locked', { name }) }
  }
  if (onlyLockChanged) {
    return { kind: 'room_unlocked', text: t('feed.room_unlocked', { name }) }
  }
  const text = t('feed.settings_changed', {
    name,
    help_mode: helpModeText(next.help_mode),
    letters: next.letters,
    words: next.words,
  })
  return { kind: 'settings_changed', text }
}

// The player an event is about: the player who joined, or the event's
// player_id; null when it names none.
function playerOfEvent(event: RoomEvent): string | null {
  if (event.type === 'player_joined') {
    const player = event.message.player as Record<string, unknown> | null
    if (player === null || typeof player !== 'object') {
      return null
    }
    return typeof player.player_id === 'string' ? player.player_id : null
  }
  const playerId = event.message.player_id
  return typeof playerId === 'string' ? playerId : null
}

// True for a check_result whose wrong list is empty.
function isCleanCheckResult(event: RoomEvent): boolean {
  if (event.type !== 'check_result') {
    return false
  }
  const wrong = event.message.wrong
  return Array.isArray(wrong) && wrong.length === 0
}

// The kind and the text of the line of an event, or null when it has none.
function lineOf(snapshot: Snapshot, names: Map<string, string>, event: RoomEvent): LineText | null {
  const name = nameOf(names, event.message.player_id)
  if (event.type === 'player_joined') {
    const joinedName = nameOf(names, playerOfEvent(event))
    return { kind: 'player_joined', text: t('feed.player_joined', { name: joinedName }) }
  }
  if (event.type === 'player_left') {
    return leftLine(event, name)
  }
  if (event.type === 'check_result') {
    return checkLine(event, name)
  }
  if (event.type === 'reveal_result') {
    return revealLine(event, name)
  }
  if (event.type === 'flag_changed') {
    if (event.message.clue === null || typeof event.message.clue !== 'object') {
      return null
    }
    const clue = clueText(snapshot, event.message.clue)
    return { kind: 'flag', text: t('feed.flag', { name, clue }) }
  }
  if (event.type === 'settings_changed') {
    return settingsLine(snapshot, event, name)
  }
  if (event.type === 'host_changed') {
    return { kind: 'host_changed', text: t('feed.host_changed', { name }) }
  }
  return null
}

// The feed item of an event about to be applied, or null when it has none.
// `names` must already know the player of a `player_joined`.
export function feedItemFor(
  snapshot: Snapshot,
  names: Map<string, string>,
  event: RoomEvent,
): FeedItem | null {
  const line = lineOf(snapshot, names, event)
  if (line === null) {
    return null
  }
  return {
    seq: event.seq,
    kind: line.kind,
    text: line.text,
    playerId: playerOfEvent(event),
    isCleanCheck: isCleanCheckResult(event),
  }
}
