// The selections of the other players, ready to draw (spec 013).
// Plain functions: no DOM and no socket.

import type { Snapshot } from './roomSession'
import { positionKey, wordAt } from './wordSelection'
import type { Word } from './wordSelection'

// One other player's selection: where it is and which cells their word holds.
export interface RemoteSelection {
  playerId: string
  colour: number
  row: number
  column: number
  // The "row,column" of each cell of their selected word.
  wordPositions: Set<string>
  // The initials of their nickname, drawn in their cursor (spec 035).
  initials: string
}

// The initials of a nickname: split on spaces, hyphens, apostrophes (' and ’)
// and underscores; with two or more parts, the first character of each of the
// first two parts; with one part, its first two characters. Upper-cased with
// toLocaleUpperCase('fr'). Characters are code points.
export function initialsOf(nickname: string): string {
  const parts: string[] = []
  for (const part of nickname.split(/[ \-'’_]+/)) {
    if (part !== '') {
      parts.push(part)
    }
  }
  let letters: string[] = []
  if (parts.length >= 2) {
    letters = [[...parts[0]][0], [...parts[1]][0]]
  } else if (parts.length === 1) {
    letters = [...parts[0]].slice(0, 2)
  }
  return letters.join('').toLocaleUpperCase('fr')
}

// The selections to draw, in roster order. Never mine, never a disconnected
// player's; an idle player keeps theirs.
export function remoteSelectionsOf(snapshot: Snapshot | null, words: Word[]): RemoteSelection[] {
  const remotes: RemoteSelection[] = []
  if (snapshot === null) {
    return remotes
  }
  for (const player of snapshot.players) {
    if (player.player_id === snapshot.you || player.state === 'disconnected') {
      continue
    }
    const { selection } = player
    if (selection === null) {
      continue
    }
    const word = wordAt(words, selection.row, selection.column, selection.direction)
    const wordPositions = new Set<string>()
    if (word !== null) {
      for (const cell of word.cells) {
        wordPositions.add(positionKey(cell.row, cell.column))
      }
    }
    remotes.push({
      playerId: player.player_id,
      colour: player.colour,
      row: selection.row,
      column: selection.column,
      wordPositions,
      initials: initialsOf(player.nickname),
    })
  }
  return remotes
}
