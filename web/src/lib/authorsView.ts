// The authors view (spec 019): who wrote each letter, as a band in the author's
// colour on the cell and as a name in the clue bar.
// Plain functions: no DOM and no socket.

import { nameOf } from './activityFeed'
import { t } from './i18n'
import type { LetterCellView, PlayerView } from './roomSession'

// The colour index of each player now in the room, by player id.
export function colourByPlayer(players: PlayerView[]): Map<string, number> {
  const colours = new Map<string, number>()
  for (const player of players) {
    colours.set(player.player_id, player.colour)
  }
  return colours
}

// The author of a cell's confirmed letter, or null when it has none to show: an
// empty cell and a revealed cell have no author (spec 024).
export function shownAuthorOf(cell: LetterCellView): string | null {
  if (cell.letter === null || cell.revealed) {
    return null
  }
  return cell.author
}

// The colour of a cell's author mark: null when the cell gets no mark, '' when
// the author is no longer a player of the room (they left or were removed:
// their colour index may now be someone else's), else the author's colour index.
export function authorMarkColour(
  cell: LetterCellView,
  playerColours: Map<string, number>,
): string | null {
  const author = shownAuthorOf(cell)
  if (author === null) {
    return null
  }
  const colour = playerColours.get(author)
  if (colour === undefined) {
    return ''
  }
  return String(colour)
}

// The clue bar's line about a letter's author: "Lettre de <nickname>", with the
// nickname known to the page (a player who left is still named), or "Quelqu'un"
// for a player the page never knew.
export function authorLine(authorId: string, names: Map<string, string>): string {
  return t('authors.selected', { name: nameOf(names, authorId) })
}
