// The clue flags (spec 021): which clues the players flagged, and what the
// marker of each flagged clue shows.
// Plain functions: no DOM and no socket.

import { t } from './i18n'
import type { ClueRefView, FlagView, PlayerView } from './roomSession'
import type { Word } from './wordSelection'

// What the marker of one flagged clue shows.
export interface ClueFlagMarker {
  // The ids of the flagging players, separated by one space, in roster order.
  flaggedBy: string
  // Their nicknames in the same order, joined by ", ".
  names: string
}

// The key of a clue: "row,column,clue_index", as `wordKey` writes a word's.
export function clueKey(clue: ClueRefView): string {
  return `${clue.row},${clue.column},${clue.clue_index}`
}

// True when a clue reference names the clue of a word.
export function isClueOfWord(clue: ClueRefView, word: Word): boolean {
  return (
    clue.row === word.clueRow &&
    clue.column === word.clueColumn &&
    clue.clue_index === word.clueIndex
  )
}

// The flag of one player, or null when they hold none.
export function flagOf(flags: FlagView[], playerId: string): ClueRefView | null {
  for (const flag of flags) {
    if (flag.player_id === playerId) {
      return flag.clue
    }
  }
  return null
}

// Compares two player ids as plain strings, for an ascending sort: `p10` comes
// before `p7`.
function compareIds(first: string, second: string): number {
  if (first < second) {
    return -1
  }
  if (first > second) {
    return 1
  }
  return 0
}

// The flags in roster order: those of the players in `players` order, then the
// flags of ids that are not in the roster, in the ascending order of their ids
// as plain strings (spec 021 "Order of the flaggers").
function flagsInRosterOrder(flags: FlagView[], players: PlayerView[]): FlagView[] {
  const ordered: FlagView[] = []
  const rosterIds = new Set<string>()
  for (const player of players) {
    rosterIds.add(player.player_id)
    const clue = flagOf(flags, player.player_id)
    if (clue !== null) {
      ordered.push({ player_id: player.player_id, clue })
    }
  }
  const flagsOutsideRoster: FlagView[] = []
  for (const flag of flags) {
    if (!rosterIds.has(flag.player_id)) {
      flagsOutsideRoster.push(flag)
    }
  }
  flagsOutsideRoster.sort((first, second) =>
    compareIds(first.player_id, second.player_id),
  )
  for (const flag of flagsOutsideRoster) {
    ordered.push(flag)
  }
  return ordered
}

// The nickname of a player of the roster; an unknown id gives "Quelqu'un".
function nicknameOf(players: PlayerView[], playerId: string): string {
  for (const player of players) {
    if (player.player_id === playerId) {
      return player.nickname
    }
  }
  return t('feed.someone')
}

// The marker of every flagged clue, by clue key. A clue that nobody flagged has
// no entry.
export function clueFlagMarkers(
  flags: FlagView[],
  players: PlayerView[],
): Map<string, ClueFlagMarker> {
  const idsByClue = new Map<string, string[]>()
  const namesByClue = new Map<string, string[]>()
  for (const flag of flagsInRosterOrder(flags, players)) {
    const key = clueKey(flag.clue)
    const ids = idsByClue.get(key) ?? []
    const names = namesByClue.get(key) ?? []
    ids.push(flag.player_id)
    names.push(nicknameOf(players, flag.player_id))
    idsByClue.set(key, ids)
    namesByClue.set(key, names)
  }
  const markers = new Map<string, ClueFlagMarker>()
  for (const [key, ids] of idsByClue) {
    const names = namesByClue.get(key) ?? []
    markers.set(key, { flaggedBy: ids.join(' '), names: names.join(', ') })
  }
  return markers
}
