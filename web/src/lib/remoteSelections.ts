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
    })
  }
  return remotes
}
