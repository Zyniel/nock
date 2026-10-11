// The activity feed of a room (spec 013): which events add a line, and its text.
// Plain functions: no DOM and no socket.

import { t } from './i18n'
import type { RoomEvent, RoomSettingsView, Snapshot } from './roomSession'

// The feed keeps the newest items only.
export const FEED_LIMIT = 100

export interface FeedItem {
  seq: number
  kind: string
  text: string
}

// The nickname of a player known to the page, even one who left.
function nameOf(names: Record<string, string>, playerId: unknown): string {
  if (typeof playerId === 'string' && playerId in names) {
    return names[playerId]
  }
  return t('feed.someone')
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

function leftItem(event: RoomEvent, name: string): FeedItem {
  const { reason } = event.message
  if (reason === 'removed') {
    return { seq: event.seq, kind: 'player_removed', text: t('feed.player_removed', { name }) }
  }
  if (reason === 'timed_out') {
    return {
      seq: event.seq,
      kind: 'player_timed_out',
      text: t('feed.player_timed_out', { name }),
    }
  }
  return { seq: event.seq, kind: 'player_left', text: t('feed.player_left', { name }) }
}

function checkItem(event: RoomEvent, name: string): FeedItem | null {
  const scope = scopeOf(event)
  if (scope === 'letter') {
    return { seq: event.seq, kind: 'check', text: t('feed.check.letter', { name }) }
  }
  if (scope === 'word') {
    return { seq: event.seq, kind: 'check', text: t('feed.check.word', { name }) }
  }
  if (scope === 'grid') {
    return { seq: event.seq, kind: 'check', text: t('feed.check.grid', { name }) }
  }
  return null
}

function revealItem(event: RoomEvent, name: string): FeedItem | null {
  const scope = scopeOf(event)
  if (scope === 'letter') {
    return { seq: event.seq, kind: 'reveal', text: t('feed.reveal.letter', { name }) }
  }
  if (scope === 'word') {
    return { seq: event.seq, kind: 'reveal', text: t('feed.reveal.word', { name }) }
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

function settingsItem(snapshot: Snapshot, event: RoomEvent, name: string): FeedItem | null {
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
    return { seq: event.seq, kind: 'room_locked', text: t('feed.room_locked', { name }) }
  }
  if (onlyLockChanged) {
    return { seq: event.seq, kind: 'room_unlocked', text: t('feed.room_unlocked', { name }) }
  }
  const text = t('feed.settings_changed', {
    name,
    help_mode: helpModeText(next.help_mode),
    letters: next.letters,
    words: next.words,
  })
  return { seq: event.seq, kind: 'settings_changed', text }
}

// The feed item of an event about to be applied, or null when it has none.
// `names` must already know the player of a `player_joined`.
export function feedItemFor(
  snapshot: Snapshot,
  names: Record<string, string>,
  event: RoomEvent,
): FeedItem | null {
  const name = nameOf(names, event.message.player_id)
  if (event.type === 'player_joined') {
    const player = event.message.player as Record<string, unknown>
    return {
      seq: event.seq,
      kind: 'player_joined',
      text: t('feed.player_joined', { name: nameOf(names, player.player_id) }),
    }
  }
  if (event.type === 'player_left') {
    return leftItem(event, name)
  }
  if (event.type === 'check_result') {
    return checkItem(event, name)
  }
  if (event.type === 'reveal_result') {
    return revealItem(event, name)
  }
  if (event.type === 'flag_changed') {
    if (event.message.clue === null || typeof event.message.clue !== 'object') {
      return null
    }
    const clue = clueText(snapshot, event.message.clue)
    return { seq: event.seq, kind: 'flag', text: t('feed.flag', { name, clue }) }
  }
  if (event.type === 'settings_changed') {
    return settingsItem(snapshot, event, name)
  }
  if (event.type === 'host_changed') {
    return { seq: event.seq, kind: 'host_changed', text: t('feed.host_changed', { name }) }
  }
  return null
}
