// The selections of the other players, ready to draw (spec 013), and the corner
// each one holds on its cell (spec 042, "Other players on a cell").
// Plain functions: no DOM and no socket.

import type { Snapshot } from './roomSession'
import { positionKey, wordAt } from './wordSelection'
import type { Word } from './wordSelection'

// The four corners of a cell, in the order arriving players take them.
export type Corner = 'top-left' | 'top-right' | 'bottom-right' | 'bottom-left'

export const CORNERS: readonly Corner[] = ['top-left', 'top-right', 'bottom-right', 'bottom-left']

// One other player's cursor on a cell. A list of them is kept in the order the
// players arrived on their cells; `corner` is null while the four corners of
// the cell are held by players who came first.
export interface CellCursor {
  playerId: string
  row: number
  column: number
  corner: Corner | null
}

// One other player's selection: where it is, which cells their word holds and
// the corner of the cell they hold (null: not drawn, all four are held).
export interface RemoteSelection {
  playerId: string
  colour: number
  row: number
  column: number
  // The "row,column" of each cell of their selected word.
  wordPositions: Set<string>
  corner: Corner | null
}

// Where the other players' cursors are now, in roster order, with no corner
// yet. Never mine, never a disconnected player's; an idle player keeps theirs.
export function cursorPositionsOf(snapshot: Snapshot | null): CellCursor[] {
  const positions: CellCursor[] = []
  if (snapshot === null) {
    return positions
  }
  for (const player of snapshot.players) {
    if (player.player_id === snapshot.you || player.state === 'disconnected') {
      continue
    }
    if (player.selection === null) {
      continue
    }
    positions.push({
      playerId: player.player_id,
      row: player.selection.row,
      column: player.selection.column,
      corner: null,
    })
  }
  return positions
}

// The first corner of the cell, in the order of CORNERS, that no cursor holds;
// null when all four are held.
function firstFreeCorner(cursors: CellCursor[], row: number, column: number): Corner | null {
  for (const corner of CORNERS) {
    let isHeld = false
    for (const cursor of cursors) {
      if (cursor.row === row && cursor.column === column && cursor.corner === corner) {
        isHeld = true
      }
    }
    if (!isHeld) {
      return corner
    }
  }
  return null
}

// The cursors after a change of the room, from the cursors before it (in order
// of arrival) and where the cursors are now (in roster order).
//
// A player still on the cell they had keeps their place and their corner. A
// player who moved to another cell, or who is gone, leaves their cell; each
// corner freed goes to the player who has waited longest on that cell. Then
// the players who arrived on a cell, in roster order, take its first free
// corner, or wait when all four are held.
export function nextCursors(before: CellCursor[], now: CellCursor[]): CellCursor[] {
  const cellOfPlayer = new Map<string, string>()
  for (const position of now) {
    cellOfPlayer.set(position.playerId, positionKey(position.row, position.column))
  }

  const kept: CellCursor[] = []
  for (const cursor of before) {
    const isOnTheSameCell =
      cellOfPlayer.get(cursor.playerId) === positionKey(cursor.row, cursor.column)
    if (isOnTheSameCell) {
      kept.push({ ...cursor })
    }
  }

  // The waiting players, longest first, take the corners that were freed.
  for (const cursor of kept) {
    if (cursor.corner === null) {
      cursor.corner = firstFreeCorner(kept, cursor.row, cursor.column)
    }
  }

  const keptPlayers = new Set<string>()
  for (const cursor of kept) {
    keptPlayers.add(cursor.playerId)
  }
  for (const position of now) {
    if (keptPlayers.has(position.playerId)) {
      continue
    }
    const corner = firstFreeCorner(kept, position.row, position.column)
    kept.push({ ...position, corner })
  }
  return kept
}

// The corner a player holds on the cell (row, column), or null.
function cornerOf(cursors: CellCursor[], playerId: string, row: number, column: number): Corner | null {
  for (const cursor of cursors) {
    if (cursor.playerId === playerId && cursor.row === row && cursor.column === column) {
      return cursor.corner
    }
  }
  return null
}

// The selections to draw, in roster order. Never mine, never a disconnected
// player's; an idle player keeps theirs. `cursors` gives each one its corner.
export function remoteSelectionsOf(
  snapshot: Snapshot | null,
  words: Word[],
  cursors: CellCursor[],
): RemoteSelection[] {
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
      corner: cornerOf(cursors, player.player_id, selection.row, selection.column),
    })
  }
  return remotes
}
