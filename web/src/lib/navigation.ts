// Where the arrow keys, Tab and Shift+Tab take the selection (spec 009). Plain
// functions: no DOM and no socket, so the rules are easy to read.

import type { CellView, GridView } from './roomSession'
import { otherDirection, positionKey, selectionAfterClueTap, selectionOnCell, wordAt, wordKey } from './wordSelection'
import type { Direction, Selection, Word } from './wordSelection'

export type ArrowKey = 'ArrowRight' | 'ArrowLeft' | 'ArrowDown' | 'ArrowUp'

// The arrow keys, with the step each one makes and the axis it follows.
const ARROW_STEPS: Record<ArrowKey, { rowStep: number; columnStep: number; axis: Direction }> = {
  ArrowRight: { rowStep: 0, columnStep: 1, axis: 'across' },
  ArrowLeft: { rowStep: 0, columnStep: -1, axis: 'across' },
  ArrowDown: { rowStep: 1, columnStep: 0, axis: 'down' },
  ArrowUp: { rowStep: -1, columnStep: 0, axis: 'down' },
}

// Whether a key name is one of the four arrow keys.
export function isArrowKey(key: string): key is ArrowKey {
  return key in ARROW_STEPS
}

// The selection after an arrow key, or null when nothing changes: the next
// letter cell in that direction, skipping clue and empty cells.
export function selectionAfterArrow(
  grid: GridView,
  words: Word[],
  current: Selection,
  key: ArrowKey,
): Selection | null {
  const { rowStep, columnStep, axis } = ARROW_STEPS[key]
  const cellTypes = new Map<string, CellView['type']>()
  for (const cell of grid.cells) {
    cellTypes.set(positionKey(cell.row, cell.column), cell.type)
  }
  let row = current.row + rowStep
  let column = current.column + columnStep
  while (row >= 0 && row < grid.height && column >= 0 && column < grid.width) {
    if (cellTypes.get(positionKey(row, column)) === 'letter') {
      const hasAxisWord = wordAt(words, row, column, axis) !== null
      const direction: Direction = hasAxisWord ? axis : otherDirection(axis)
      return selectionOnCell(words, row, column, direction)
    }
    row += rowStep
    column += columnStep
  }
  return null
}

// Index `position` moved into the range 0..count-1, wrapping around either end.
function wrapIndex(position: number, count: number): number {
  return ((position % count) + count) % count
}

// Whether at least one cell of the word is not filled.
function isUnfinished(grid: GridView, word: Word): boolean {
  const letters = new Map<string, string | null>()
  for (const cell of grid.cells) {
    if (cell.type === 'letter') {
      letters.set(positionKey(cell.row, cell.column), cell.letter)
    }
  }
  for (const position of word.cells) {
    if (letters.get(positionKey(position.row, position.column)) === null) {
      return true
    }
  }
  return false
}

// The selection after Tab (`step` 1) or Shift+Tab (`step` -1): the next
// unfinished word in clue order, wrapping, the selected word last. Null when
// every word is finished.
export function selectionAfterTab(
  grid: GridView,
  words: Word[],
  current: Selection | null,
  step: 1 | -1,
): Selection | null {
  const count = words.length
  let start = step === 1 ? -1 : count
  if (current !== null) {
    const currentIndex = words.findIndex((word) => wordKey(word) === current.word)
    if (currentIndex !== -1) {
      start = currentIndex
    }
  }
  for (let distance = 1; distance <= count; distance++) {
    const index = wrapIndex(start + step * distance, count)
    if (isUnfinished(grid, words[index])) {
      return selectionAfterClueTap(grid, words[index])
    }
  }
  return null
}
