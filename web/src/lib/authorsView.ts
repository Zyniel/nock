// The Auteurs mode (spec 045): while it is on, each letter is drawn in the ink
// of its finder, and a legend under the grid names each player in their ink.
// The mode is kept in this browser and sends nothing.
// Plain functions: no DOM and no socket.

import { displayNickname } from './nickname'
import type { LetterCellView, PlayerView } from './roomSession'
import { readItem } from './storage'

export const AUTHORS_VIEW_KEY = 'nock.authors'

// The legend's room under the grid when it is one line, as drawn, and the gap
// between the grid and the legend (_design.md section 7).
export const LEGEND_ONE_LINE_ROOM_PX = 38
export const LEGEND_GAP_PX = 8

// Spec 013 AC-6's floor: grid-viewport is never less high than this. Where
// the legend's room would leave it less, the legend lies over the grid's
// bottom and takes no room (spec 045, decision 8).
export const MIN_GRID_VIEWPORT_PX = 100

// One name of the legend: a player of the kept snapshot.
export interface LegendName {
  playerId: string
  colour: number
  name: string
}

// The mode is off unless "true" is stored; a browser that refuses storage
// starts with it off.
export function readAuthorsView(): boolean {
  return readItem(AUTHORS_VIEW_KEY) === 'true'
}

// The colour index of each player of the kept snapshot (present or
// disconnected), by player id.
export function colourByPlayer(players: PlayerView[]): Map<string, number> {
  const colours = new Map<string, number>()
  for (const player of players) {
    colours.set(player.player_id, player.colour)
  }
  return colours
}

// The colour index of a letter cell's finder, as text, or '' when the cell has
// no finder: it is empty, revealed (spec 024), or its confirmed author is not a
// player of the kept snapshot (they left or were removed, and their colour
// index may now be someone else's).
export function finderColour(cell: LetterCellView, playerColours: Map<string, number>): string {
  if (cell.letter === null || cell.revealed || cell.author === null) {
    return ''
  }
  const colour = playerColours.get(cell.author)
  if (colour === undefined) {
    return ''
  }
  return String(colour)
}

// The names of the legend: every player of the kept snapshot, in its order
// (join order, as the Joueurs list), each with their colour index.
export function legendNames(players: PlayerView[]): LegendName[] {
  const names: LegendName[] = []
  for (const player of players) {
    names.push({
      playerId: player.player_id,
      colour: player.colour,
      name: displayNickname(player.nickname),
    })
  }
  return names
}

// The height the grid gives the legend: the 38 px drawn for one line, or the
// legend's height and its 8 px gap when it wraps onto more lines.
export function legendRoom(legendHeight: number): number {
  return Math.max(LEGEND_ONE_LINE_ROOM_PX, legendHeight + LEGEND_GAP_PX)
}
