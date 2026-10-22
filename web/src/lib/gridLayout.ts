// Small rules of the grid display, kept apart from the component so they are
// easy to read: arrow sides, where each arrow is drawn, the sizes of the marks
// and zoom limits.

import type { Arrow, GridView } from './roomSession'
import { positionKey } from './wordSelection'

export type ArrowSide = 'right' | 'bottom'

export const ZOOM_MIN = 1
export const ZOOM_MAX = 5

// The grid's own left and top line: each cell draws its right and bottom lines
// inside its side, so the grid is one line wider and higher than its cells.
export const GRID_LINE_PX = 1

// The side of the clue cell where the word's first letter is.
export function arrowSide(arrow: Arrow): ArrowSide {
  if (arrow === 'right' || arrow === 'right_then_down') {
    return 'right'
  }
  return 'bottom'
}

// The glyph of an arrow in its 24 by 24 box (_design.md section 6): the
// stroked path and the filled head.
export interface ArrowGlyph {
  path: string
  head: string
}

export const ARROW_GLYPHS: Record<Arrow, ArrowGlyph> = {
  right: { path: 'M2 12H15', head: '14,7.5 22,12 14,16.5' },
  down: { path: 'M12 2V15', head: '7.5,14 12,22 16.5,14' },
  down_then_right: { path: 'M5 2V10Q5 15 10 15H15', head: '14,10.5 22,15 14,19.5' },
  right_then_down: { path: 'M2 5H10Q15 5 15 10V15', head: '10.5,14 15,22 19.5,14' },
}

// Where an arrow's box sits in its target cell (spec 042, "Direction arrows"):
// - 'right': a → centred at half the side;
// - 'right-high' and 'right-low': a → centred at 0.25 and 0.72 of the side;
// - 'down': a ↓ centred at half the side;
// - 'down-then-right': a ↳ at 0.06 of the side from the left;
// - 'down-then-right-moved': a ↳ at 0.4 of the side, away from a ↴;
// - 'right-then-down': a ↴ at 0.06 of the side from the top.
export type ArrowPlace =
  | 'right'
  | 'right-high'
  | 'right-low'
  | 'down'
  | 'down-then-right'
  | 'down-then-right-moved'
  | 'right-then-down'

// One clue's arrow, drawn in the letter cell where its word starts.
export interface PlacedArrow {
  clueRow: number
  clueColumn: number
  clueIndex: number
  arrow: Arrow
  place: ArrowPlace
}

// The cell where the word of a clue starts: right of its clue cell for → and
// ↴, below it for ↓ and ↳.
function targetOf(row: number, column: number, arrow: Arrow): { row: number; column: number } {
  if (arrowSide(arrow) === 'right') {
    return { row, column: column + 1 }
  }
  return { row: row + 1, column }
}

// The place of one arrow among the arrows of its target cell, by the collision
// rules of _design.md section 6.
function placeOf(arrow: PlacedArrow, arrowsOfCell: PlacedArrow[]): ArrowPlace {
  let hasRightThenDown = false
  let rightCount = 0
  for (const other of arrowsOfCell) {
    if (other.arrow === 'right_then_down') {
      hasRightThenDown = true
    }
    if (other.arrow === 'right') {
      rightCount += 1
    }
  }
  if (arrow.arrow === 'right') {
    // Rule 1: beside a ↴, the → goes low. Rule 2: two → (from one two-clue
    // cell) share the cell by their clue index.
    if (hasRightThenDown) {
      return 'right-low'
    }
    if (rightCount > 1) {
      return arrow.clueIndex === 0 ? 'right-high' : 'right-low'
    }
    return 'right'
  }
  if (arrow.arrow === 'down_then_right') {
    // Rule 3: beside a ↴, the ↳ moves right.
    return hasRightThenDown ? 'down-then-right-moved' : 'down-then-right'
  }
  if (arrow.arrow === 'down') {
    return 'down'
  }
  return 'right-then-down'
}

// The arrows drawn in each letter cell, by the "row,column" of the cell. A clue
// whose word would start outside the grid or on a cell that is not a letter
// cell has no arrow.
export function arrowsByCell(grid: GridView): Map<string, PlacedArrow[]> {
  const letterCells = new Set<string>()
  for (const cell of grid.cells) {
    if (cell.type === 'letter') {
      letterCells.add(positionKey(cell.row, cell.column))
    }
  }

  const arrows = new Map<string, PlacedArrow[]>()
  for (const cell of grid.cells) {
    if (cell.type !== 'clue') {
      continue
    }
    cell.clues.forEach((clue, clueIndex) => {
      const target = targetOf(cell.row, cell.column, clue.arrow)
      const key = positionKey(target.row, target.column)
      if (!letterCells.has(key)) {
        return
      }
      const arrowsOfCell = arrows.get(key) ?? []
      arrowsOfCell.push({
        clueRow: cell.row,
        clueColumn: cell.column,
        clueIndex,
        arrow: clue.arrow,
        place: 'right',
      })
      arrows.set(key, arrowsOfCell)
    })
  }

  for (const arrowsOfCell of arrows.values()) {
    for (const arrow of arrowsOfCell) {
      arrow.place = placeOf(arrow, arrowsOfCell)
    }
  }
  return arrows
}

// The side of a corner triangle of another player, t = max(6, round(0.3 s)),
// in whole pixels (_design.md section 6).
export function triangleSide(cellSide: number): number {
  return Math.max(6, Math.round(cellSide * 0.3))
}

// Keep a zoom inside the limits and at 2 decimals, as `data-zoom` shows it.
export function clampZoom(zoom: number): number {
  const limited = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom))
  return Math.round(limited * 100) / 100
}

// Side of a cell, in pixels, so that the whole grid, its own left and top line
// included, fits in the given area at zoom 1. Rounded down so that the grid
// never overflows its viewport.
export function fitCellSize(
  areaWidth: number,
  areaHeight: number,
  columns: number,
  rows: number,
): number {
  const byWidth = (areaWidth - GRID_LINE_PX) / columns
  const byHeight = (areaHeight - GRID_LINE_PX) / rows
  return Math.floor(Math.min(byWidth, byHeight) * 100) / 100
}

export function distanceBetween(
  first: { clientX: number; clientY: number },
  second: { clientX: number; clientY: number },
): number {
  return Math.hypot(first.clientX - second.clientX, first.clientY - second.clientY)
}

// The box of a grid fitted to an area at zoom 1, in px: its cells at the side
// that fits (fitCellSize) and the grid's own left and top line. The column
// layout sizes the grid viewport to it (spec 043, "Play area and fit").
export function fittedGridBox(
  areaWidth: number,
  areaHeight: number,
  columns: number,
  rows: number,
): { width: number; height: number } {
  const side = Math.max(0, fitCellSize(areaWidth, areaHeight, columns, rows))
  return {
    width: side * columns + GRID_LINE_PX,
    height: side * rows + GRID_LINE_PX,
  }
}
