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

// The glyph of an arrow in its 24 by 24 box (specs/_design/cells.md « Direction arrows »): the
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
// rules of specs/_design/cells.md.
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
// in whole pixels (specs/_design/cells.md « Grid lines and empty cells »).
export function triangleSide(cellSide: number): number {
  return Math.max(6, Math.round(cellSide * 0.3))
}

// ---- Hyphen edges (specs/_design/cells.md « Hyphen edges ») ----

// The hyphen edges that touch one letter cell. A hyphen edge is the right or
// bottom edge of the letter before the hyphen (its `hyphen_right` or
// `hyphen_down` mark), and so the left or top edge of the letter after it.
export interface CellHyphens {
  right: boolean
  bottom: boolean
  left: boolean
  top: boolean
}

// The hyphen edges of each letter cell that touches one, by the "row,column"
// of the cell. A cell that touches none has no entry.
export function hyphensByCell(grid: GridView): Map<string, CellHyphens> {
  const hyphens = new Map<string, CellHyphens>()

  function hyphensOf(row: number, column: number): CellHyphens {
    const key = positionKey(row, column)
    let found = hyphens.get(key)
    if (found === undefined) {
      found = { right: false, bottom: false, left: false, top: false }
      hyphens.set(key, found)
    }
    return found
  }

  for (const cell of grid.cells) {
    if (cell.type !== 'letter') {
      continue
    }
    if (cell.hyphen_right) {
      hyphensOf(cell.row, cell.column).right = true
      hyphensOf(cell.row, cell.column + 1).left = true
    }
    if (cell.hyphen_down) {
      hyphensOf(cell.row, cell.column).bottom = true
      hyphensOf(cell.row + 1, cell.column).top = true
    }
  }
  return hyphens
}

// One dash of a hyphen edge, in whole px from the edge's start: from `start`
// to just before `end`.
export interface DashRun {
  start: number
  end: number
}

// The dashes' thickness on cells of side s: 1 px under 36 px, 2 px from 36,
// 3 px from 72.
export function hyphenThickness(cellSide: number): number {
  if (cellSide >= 72) {
    return 3
  }
  if (cellSide >= 36) {
    return 2
  }
  return 1
}

// The period the dashes aim at for each thickness, in px.
const HYPHEN_PERIOD_PX: Record<number, number> = { 1: 5, 2: 8, 3: 11 }

// The fewest dashes an edge has.
const HYPHEN_LEAST_DASHES = 3

// The dashes along an edge of a cell of side s: the edge is L = s - 1 long (up
// to the crossing line, which stays plain), it holds n = max(3, round(L / p))
// dashes, and dash i runs from round((i + 0.2) L / n) to round((i + 0.8) L / n).
// Every end is a whole number, so that every dash lies on whole pixels.
export function hyphenDashes(cellSide: number): DashRun[] {
  const length = cellSide - GRID_LINE_PX
  const period = HYPHEN_PERIOD_PX[hyphenThickness(cellSide)]
  const count = Math.max(HYPHEN_LEAST_DASHES, Math.round(length / period))
  const dashes: DashRun[] = []
  for (let index = 0; index < count; index += 1) {
    const start = Math.round(((index + 0.2) * length) / count)
    const end = Math.round(((index + 0.8) * length) / count)
    dashes.push({ start, end })
  }
  return dashes
}

// How the dashes' thickness is shared between the two cells of the edge, in
// px. The dashes are centred on the grid line's pixel, which is the last pixel
// of the cell before: t = 1 is that pixel; t = 2 adds the first pixel of the
// cell after; t = 3 adds a pixel on each side.
export function hyphenWidthBefore(thickness: number): number {
  return thickness === 3 ? 2 : 1
}

export function hyphenWidthAfter(thickness: number): number {
  return thickness >= 2 ? 1 : 0
}

// A side of a letter cell that a hyphen edge runs along.
export type EdgeSide = 'right' | 'bottom' | 'left' | 'top'

// What one cell draws along one side for a hyphen edge, `width` px across:
// - 'hyphen': its share of the dashes in hyphen grey, under every mark;
// - 'band': its share of my selection border's dashed side, navy dashes with
//   gaps in the selected blue, over every mark.
export interface EdgeDrawing {
  side: EdgeSide
  width: number
  kind: 'hyphen' | 'band'
}

// My selection border is 2 px; beside a hyphen edge its dashed side is 3 px,
// the border and the grid line's pixel.
const SELECTION_BORDER_PX = 2
const SELECTION_BAND_PX = SELECTION_BORDER_PX + GRID_LINE_PX

// What a letter cell draws for the hyphen edges that touch it. On my selected
// cell, the side along a hyphen edge is the dashed band; the grid line's pixel
// of that band lies in the cell before the edge, which draws it when the cell
// after is my selected one.
export function hyphenDrawings(
  hyphens: CellHyphens,
  thickness: number,
  isSelected: boolean,
  isRightSelected: boolean,
  isBelowSelected: boolean,
): EdgeDrawing[] {
  const drawings: EdgeDrawing[] = []
  const widthBefore = hyphenWidthBefore(thickness)
  const widthAfter = hyphenWidthAfter(thickness)

  const sidesBefore: { side: EdgeSide; isAfterSelected: boolean }[] = []
  if (hyphens.right) {
    sidesBefore.push({ side: 'right', isAfterSelected: isRightSelected })
  }
  if (hyphens.bottom) {
    sidesBefore.push({ side: 'bottom', isAfterSelected: isBelowSelected })
  }
  for (const { side, isAfterSelected } of sidesBefore) {
    drawings.push({ side, width: widthBefore, kind: 'hyphen' })
    if (isSelected) {
      drawings.push({ side, width: SELECTION_BAND_PX, kind: 'band' })
    } else if (isAfterSelected) {
      drawings.push({ side, width: GRID_LINE_PX, kind: 'band' })
    }
  }

  const sidesAfter: EdgeSide[] = []
  if (hyphens.left) {
    sidesAfter.push('left')
  }
  if (hyphens.top) {
    sidesAfter.push('top')
  }
  for (const side of sidesAfter) {
    if (widthAfter > 0) {
      drawings.push({ side, width: widthAfter, kind: 'hyphen' })
    }
    if (isSelected) {
      drawings.push({ side, width: SELECTION_BORDER_PX, kind: 'band' })
    }
  }
  return drawings
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

// One axis of a zoomed grid's viewport, in px from the start of what it
// scrolls: the viewport shows `viewSide` px from `scroll`, the selected cell
// runs from `cellStart` for `cellSide` px, the grid from `gridStart` to
// `gridEnd`.
export interface ScrollAxis {
  scroll: number
  viewSide: number
  cellStart: number
  cellSide: number
  gridStart: number
  gridEnd: number
}

// The scroll on one axis that shows the selected cell with one cell of margin
// on each side the grid's edge allows, moving the least (board rule 3). On a
// viewport that holds less than three cells, the cell is centred instead.
export function scrollShowingCell(axis: ScrollAxis): number {
  const { scroll, viewSide, cellStart, cellSide, gridStart, gridEnd } = axis
  if (viewSide < 3 * cellSide) {
    return cellStart + cellSide / 2 - viewSide / 2
  }
  const marginStart = Math.max(gridStart, cellStart - cellSide)
  const marginEnd = Math.min(gridEnd, cellStart + 2 * cellSide)
  if (marginStart < scroll) {
    return marginStart
  }
  if (marginEnd > scroll + viewSide) {
    return marginEnd - viewSide
  }
  return scroll
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
