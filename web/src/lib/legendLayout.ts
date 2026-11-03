// The Auteurs legend's margins under the grid (spec 045). Plain functions: no
// DOM, so the arithmetic is easy to read.
//
// The legend is in the flow right under the viewport, and its margins and
// height add up to legendRoom, the height the viewport gives it. Its top is
// 8 px below the bottom of the part of the grid's box that shows: the grid
// is centred in the viewport while it is shorter, so the room left under the
// grid is taken back from the legend's top margin. While it lies over the
// grid, its margins and height add up to nothing: it is pulled up over the
// viewport's bottom, its bottom 8 px above it.
//
// That room is kept in quarter pixels, which every engine lays out exactly:
// the two margins then add up to the same height as legendRoom, and the
// viewport's height does not move by a fraction of a pixel at each frame
// (its height sets the room under the grid, which sets the margins).

import { LEGEND_GAP_PX } from './authorsView'

// A length in px, rounded down to a quarter of a pixel.
export function quarterPixels(length: number): number {
  return Math.floor(length * 4) / 4
}

export interface LegendMarginsInput {
  // True while the legend lies over the grid instead of under it.
  isOverGrid: boolean
  legendHeight: number
  // The height the viewport gives the legend (0 while it lies over the grid).
  legendRoom: number
  viewportHeight: number
  gridHeight: number
}

export function legendMargins(input: LegendMarginsInput): {
  marginTop: number
  marginBottom: number
} {
  const { isOverGrid, legendHeight, legendRoom, viewportHeight, gridHeight } = input
  if (isOverGrid) {
    return { marginTop: -(legendHeight + LEGEND_GAP_PX), marginBottom: LEGEND_GAP_PX }
  }
  const roomUnderGrid = quarterPixels(Math.max(0, (viewportHeight - gridHeight) / 2))
  return {
    marginTop: LEGEND_GAP_PX - roomUnderGrid,
    marginBottom: legendRoom - legendHeight - LEGEND_GAP_PX + roomUnderGrid,
  }
}
