// The generic drawing of a grid on its catalogue card (spec 046, "Grid cards";
// decided by the human on 2026-10-17). It is built from the grid's width and
// height only and shows their proportions, not the grid's real layout: clue
// cells along the top row at the even columns and down the first column at the
// even rows from 2, and the inner grid lines.

// The drawing is 51 px high; its width keeps the grid's proportions.
export const THUMB_HEIGHT_PX = 51
// The drawing shows while the list's content box holds two 400 px cards and
// their 12 px gap, that is while the cards sit more than one per row.
export const THUMB_MIN_LIST_WIDTH_PX = 812
// The size of one cell, in units of the drawing's viewBox.
export const THUMB_CELL_UNITS = 10

export interface ThumbCell {
  x: number
  y: number
}

export interface ThumbLine {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface GridThumb {
  // The drawing's width in px (its height is THUMB_HEIGHT_PX).
  widthPx: number
  // The viewBox's width and height, in units.
  viewWidth: number
  viewHeight: number
  // The top left corner of each clue cell, in units.
  clueCells: ThumbCell[]
  // Each inner grid line, across the whole drawing, in units.
  lines: ThumbLine[]
}

// The drawing of a grid of `columns` by `rows` cells.
export function gridThumbOf(columns: number, rows: number): GridThumb {
  const viewWidth = THUMB_CELL_UNITS * columns
  const viewHeight = THUMB_CELL_UNITS * rows

  const clueCells: ThumbCell[] = []
  for (let column = 0; column < columns; column += 2) {
    clueCells.push({ x: THUMB_CELL_UNITS * column, y: 0 })
  }
  for (let row = 2; row < rows; row += 2) {
    clueCells.push({ x: 0, y: THUMB_CELL_UNITS * row })
  }

  const lines: ThumbLine[] = []
  for (let column = 1; column < columns; column += 1) {
    const x = THUMB_CELL_UNITS * column
    lines.push({ x1: x, y1: 0, x2: x, y2: viewHeight })
  }
  for (let row = 1; row < rows; row += 1) {
    const y = THUMB_CELL_UNITS * row
    lines.push({ x1: 0, y1: y, x2: viewWidth, y2: y })
  }

  return {
    widthPx: Math.round((THUMB_HEIGHT_PX * columns) / rows),
    viewWidth,
    viewHeight,
    clueCells,
    lines,
  }
}
