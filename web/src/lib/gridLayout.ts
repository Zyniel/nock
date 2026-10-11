// Small rules of the grid display, kept apart from the component so they are
// easy to read: arrow sides, arrow positions and zoom limits.

import type { Arrow, ClueView } from './roomSession'

export type ArrowSide = 'right' | 'bottom'

export const ZOOM_MIN = 1
export const ZOOM_MAX = 5

// The side of the clue cell where the word's first letter is.
export function arrowSide(arrow: Arrow): ArrowSide {
  if (arrow === 'right' || arrow === 'right_then_down') {
    return 'right'
  }
  return 'bottom'
}

// Where the arrow of clue `index` sits along its side, as a CSS percentage.
// One arrow on a side is centred; two arrows on the same side share it.
export function arrowPosition(clues: ClueView[], index: number): string {
  if (clues.length < 2) {
    return '50%'
  }
  const firstSide = arrowSide(clues[0].arrow)
  const secondSide = arrowSide(clues[1].arrow)
  if (firstSide !== secondSide) {
    return '50%'
  }
  return index === 0 ? '25%' : '75%'
}

// Keep a zoom inside the limits and at 2 decimals, as `data-zoom` shows it.
export function clampZoom(zoom: number): number {
  const limited = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom))
  return Math.round(limited * 100) / 100
}

// Side of a cell, in pixels, so that the whole grid fits in the given area at
// zoom 1. Rounded down so that the grid never overflows its viewport.
export function fitCellSize(
  areaWidth: number,
  areaHeight: number,
  columns: number,
  rows: number,
): number {
  const byWidth = areaWidth / columns
  const byHeight = areaHeight / rows
  return Math.floor(Math.min(byWidth, byHeight) * 100) / 100
}

export function distanceBetween(
  first: { clientX: number; clientY: number },
  second: { clientX: number; clientY: number },
): number {
  return Math.hypot(first.clientX - second.clientX, first.clientY - second.clientY)
}
