// The room's layout and the fit of its play area (spec 043, "Which layout"
// and "Play area and fit"; spec 045, "The grid's room"). Plain functions: no
// DOM and no runes, so the arithmetic is easy to read. The room page measures
// the play block and gives the sizes here.

import { MIN_GRID_VIEWPORT_PX } from './authorsView'
import { CLUE_BAR_HEIGHT_PX, fittedGridBox } from './gridLayout'
import { LOW_WINDOW_PX, isWideWindow } from './windowForm'

// The column layout's play area: its padding, and the smallest width of the
// clue bar when the play area has that much room (spec 043, Decision 12).
export const PLAY_AREA_PADDING_PX = 12
export const CLUE_BAR_MIN_PX = 320

export type Layout = 'sheet' | 'column'

// A width and a height in CSS px.
export interface Box {
  width: number
  height: number
}

// The two layouts of the room (spec 043, spec 044, "Which layout"): "column"
// for a wide window, or for a landscape window at most LOW_WINDOW_PX high on
// which the in-app keyboard does not show; "sheet" otherwise.
export function layoutOf(width: number, height: number, isKeyboardOn: boolean): Layout {
  const isLandscape = width > height
  if (!isLandscape) {
    return 'sheet'
  }
  const isLowWithoutKeyboard = height <= LOW_WINDOW_PX && !isKeyboardOn
  if (isWideWindow(width, height) || isLowWithoutKeyboard) {
    return 'column'
  }
  return 'sheet'
}

export interface ColumnGridBoxInput {
  layout: Layout
  // The grid's size in cells, or null before the first snapshot.
  grid: { width: number; height: number } | null
  // The block of the grid, the clue bar and the status, as measured.
  playBlockWidth: number
  playBlockHeight: number
  // The status band's height, taken only while the band shows under the bar.
  statusBandHeight: number
  isStatusUnderClueBar: boolean
  // The room taken under the grid for the Auteurs legend.
  legendRoomPx: number
}

// The grid's box at zoom 1 in the column layout: as large as the room left
// after the padding, the clue bar, the status band and the legend's room;
// null in the sheet layout, where the viewport fills its area, and before
// the grid is known.
export function columnGridBoxFor(input: ColumnGridBoxInput): Box | null {
  if (input.layout !== 'column' || input.grid === null) {
    return null
  }
  const statusRoom = input.isStatusUnderClueBar ? input.statusBandHeight : 0
  const heightLeft =
    input.playBlockHeight -
    PLAY_AREA_PADDING_PX -
    CLUE_BAR_HEIGHT_PX -
    statusRoom -
    input.legendRoomPx
  return fittedGridBox(
    input.playBlockWidth,
    Math.max(0, heightLeft),
    input.grid.width,
    input.grid.height,
  )
}

// The clue bar's width: as wide as the grid's box with no legend under it,
// but never narrower than the smaller of CLUE_BAR_MIN_PX and the play block
// (Decision 12); null, the full width, in the sheet layout.
export function clueBarWidthOf(
  boxWithoutLegend: Box | null,
  playBlockWidth: number,
): number | null {
  if (boxWithoutLegend === null) {
    return null
  }
  const smallestWidth = Math.min(CLUE_BAR_MIN_PX, playBlockWidth)
  return Math.max(boxWithoutLegend.width, smallestWidth)
}

export interface LegendPlacementInput {
  isAuthorsViewOn: boolean
  // The room the legend needs under the grid (authorsView.ts, legendRoom).
  wantedLegendRoom: number
  // The viewport's height if the grid gave the legend that room.
  viewportHeightWithRoom: number
}

export interface LegendPlacement {
  // True while the legend lies over the viewport's bottom instead of under it.
  isOverGrid: boolean
  // The room the grid gives the legend.
  legendRoom: number
}

// Where the Auteurs legend goes (spec 045, decision 8): under the grid, with
// the room it wants, unless that room would leave the viewport less than
// MIN_GRID_VIEWPORT_PX high; then over the grid, with no room. While the mode
// is off it has no room.
export function legendPlacement(input: LegendPlacementInput): LegendPlacement {
  if (!input.isAuthorsViewOn) {
    return { isOverGrid: false, legendRoom: 0 }
  }
  if (input.viewportHeightWithRoom < MIN_GRID_VIEWPORT_PX) {
    return { isOverGrid: true, legendRoom: 0 }
  }
  return { isOverGrid: false, legendRoom: input.wantedLegendRoom }
}
