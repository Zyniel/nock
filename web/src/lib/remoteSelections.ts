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
  // Nothing moved: the same list, so that nothing drawn from it draws again
  // (client/shell.md rule 18).
  if (isSameCursorList(before, kept)) {
    return before
  }
  return kept
}

// True when both lists hold the same cursors, in the same order.
function isSameCursorList(first: CellCursor[], second: CellCursor[]): boolean {
  if (first.length !== second.length) {
    return false
  }
  for (let index = 0; index < first.length; index++) {
    const one = first[index]
    const other = second[index]
    const isSame =
      one.playerId === other.playerId &&
      one.row === other.row &&
      one.column === other.column &&
      one.corner === other.corner
    if (!isSame) {
      return false
    }
  }
  return true
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

// One other player's cursor as a cell draws it: their colour in the corner
// they hold there.
export interface DrawnCursor {
  playerId: string
  colour: number
  corner: Corner
}

// What the other players draw on one letter cell: their cursors on it, and
// the tint of the players whose selected word holds it.
export interface CellRemotes {
  // The cursors that hold a corner of the cell, in roster order. A player who
  // waits for a corner is not drawn.
  cursors: DrawnCursor[]
  // The ids of the players whose word holds the cell, in roster order.
  tintedBy: string[]
  // The colour of the first of them; null when no word of theirs holds it.
  tintColour: number | null
}

// The value of every cell the other players draw nothing on. One shared value,
// so that such a cell never sees a change; it is never modified.
export const NO_REMOTES: CellRemotes = { cursors: [], tintedBy: [], tintColour: null }

// What the other players draw on each cell, by "row,column" (positionKey). A
// cell they draw nothing on has no entry: it takes NO_REMOTES.
//
// A cell whose drawing is the same as in `previous` keeps the value it had
// there, so that only the cells a change of the room reaches draw again
// (client/shell.md rule 18).
export function remotesByCell(
  remotes: RemoteSelection[],
  previous: Map<string, CellRemotes>,
): Map<string, CellRemotes> {
  const byCell = new Map<string, CellRemotes>()
  for (const remote of remotes) {
    for (const key of remote.wordPositions) {
      const remotesHere = entryOf(byCell, key)
      remotesHere.tintedBy.push(remote.playerId)
      if (remotesHere.tintColour === null) {
        remotesHere.tintColour = remote.colour
      }
    }
    if (remote.corner !== null) {
      const remotesHere = entryOf(byCell, positionKey(remote.row, remote.column))
      remotesHere.cursors.push({
        playerId: remote.playerId,
        colour: remote.colour,
        corner: remote.corner,
      })
    }
  }
  for (const [key, remotesHere] of byCell) {
    const before = previous.get(key)
    if (before !== undefined && isSameCellRemotes(before, remotesHere)) {
      byCell.set(key, before)
    }
  }
  return byCell
}

// The entry of a cell in the map, added empty when it has none yet.
function entryOf(byCell: Map<string, CellRemotes>, key: string): CellRemotes {
  let remotesHere = byCell.get(key)
  if (remotesHere === undefined) {
    remotesHere = { cursors: [], tintedBy: [], tintColour: null }
    byCell.set(key, remotesHere)
  }
  return remotesHere
}

// True when a cell draws the same cursors and the same tint with either value.
function isSameCellRemotes(first: CellRemotes, second: CellRemotes): boolean {
  if (first.tintColour !== second.tintColour) {
    return false
  }
  if (first.tintedBy.join(' ') !== second.tintedBy.join(' ')) {
    return false
  }
  if (first.cursors.length !== second.cursors.length) {
    return false
  }
  for (let index = 0; index < first.cursors.length; index++) {
    const one = first.cursors[index]
    const other = second.cursors[index]
    const isSame =
      one.playerId === other.playerId && one.colour === other.colour && one.corner === other.corner
    if (!isSame) {
      return false
    }
  }
  return true
}
