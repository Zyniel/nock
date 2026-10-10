// Words of a grid and the rules of word selection (spec 007). Plain functions:
// no DOM and no socket, so the rules are easy to read.

import type { Arrow, CellView, GridView } from './roomSession'

export type Direction = 'across' | 'down'

export interface Position {
  row: number
  column: number
}

// A word, named by its clue: the clue cell and the index of the clue in it.
export interface Word {
  clueRow: number
  clueColumn: number
  clueIndex: number
  direction: Direction
  text: string
  // The letter cells of the word, in reading order.
  cells: Position[]
}

// One letter cell, a direction, and the word that was chosen. The word is
// remembered (by its key) because a clue tap may choose a word that starts
// inside a longer run, which a cell and a direction alone cannot name.
export interface Selection {
  row: number
  column: number
  direction: Direction
  word: string
}

// The name of a word, "row,column,clue_index" of its clue (spec 007).
export function wordKey(word: Word): string {
  return `${word.clueRow},${word.clueColumn},${word.clueIndex}`
}

// The name of a grid position, "row,column".
export function positionKey(row: number, column: number): string {
  return `${row},${column}`
}

function directionOfArrow(arrow: Arrow): Direction {
  if (arrow === 'right' || arrow === 'down_then_right') {
    return 'across'
  }
  return 'down'
}

// Where the first letter of a word is, from the clue cell (rule of spec 002).
function startOfWord(clueRow: number, clueColumn: number, arrow: Arrow): Position {
  if (arrow === 'right' || arrow === 'right_then_down') {
    return { row: clueRow, column: clueColumn + 1 }
  }
  return { row: clueRow + 1, column: clueColumn }
}

// The cell at each position of the grid, found by "row,column".
function cellsByPosition(grid: GridView): Map<string, CellView> {
  const cells = new Map<string, CellView>()
  for (const cell of grid.cells) {
    cells.set(positionKey(cell.row, cell.column), cell)
  }
  return cells
}

// The cells of a word: from its start, to the next non-letter cell or the edge.
function wordCells(
  cells: Map<string, CellView>,
  start: Position,
  direction: Direction,
): Position[] {
  const found: Position[] = []
  let row = start.row
  let column = start.column
  for (;;) {
    const cell = cells.get(positionKey(row, column))
    if (cell === undefined || cell.type !== 'letter') {
      return found
    }
    found.push({ row, column })
    if (direction === 'across') {
      column += 1
    } else {
      row += 1
    }
  }
}

// Every word of the grid. A clue whose start is not a letter cell has no word.
export function computeWords(grid: GridView): Word[] {
  const cells = cellsByPosition(grid)
  const words: Word[] = []
  for (const cell of grid.cells) {
    if (cell.type !== 'clue') {
      continue
    }
    for (let clueIndex = 0; clueIndex < cell.clues.length; clueIndex++) {
      const clue = cell.clues[clueIndex]
      const direction = directionOfArrow(clue.arrow)
      const start = startOfWord(cell.row, cell.column, clue.arrow)
      const positions = wordCells(cells, start, direction)
      if (positions.length === 0) {
        continue
      }
      words.push({
        clueRow: cell.row,
        clueColumn: cell.column,
        clueIndex,
        direction,
        text: clue.text,
        cells: positions,
      })
    }
  }
  return words
}

// The word of `direction` that holds a cell. When several do, the one that
// starts first in that direction (the longest).
export function wordAt(
  words: Word[],
  row: number,
  column: number,
  direction: Direction,
): Word | null {
  let best: Word | null = null
  for (const word of words) {
    if (word.direction !== direction) {
      continue
    }
    const holdsCell = word.cells.some((cell) => cell.row === row && cell.column === column)
    if (!holdsCell) {
      continue
    }
    if (best === null || startsBefore(word, best)) {
      best = word
    }
  }
  return best
}

function startsBefore(word: Word, other: Word): boolean {
  const first = word.cells[0]
  const otherFirst = other.cells[0]
  if (word.direction === 'across') {
    return first.column < otherFirst.column
  }
  return first.row < otherFirst.row
}

// The word a selection stands for, or null when the grid no longer has that
// word, or the word no longer holds the selected cell in the selected direction.
export function selectedWord(words: Word[], selection: Selection | null): Word | null {
  if (selection === null) {
    return null
  }
  for (const word of words) {
    if (wordKey(word) !== selection.word || word.direction !== selection.direction) {
      continue
    }
    const holdsCell = word.cells.some(
      (cell) => cell.row === selection.row && cell.column === selection.column,
    )
    if (holdsCell) {
      return word
    }
  }
  return null
}

// A selection on a cell, in a direction, with the longest word there.
export function selectionOnCell(
  words: Word[],
  row: number,
  column: number,
  direction: Direction,
): Selection | null {
  const word = wordAt(words, row, column, direction)
  if (word === null) {
    return null
  }
  return { row, column, direction, word: wordKey(word) }
}

// Keep a selection only while its cell still has a word in its direction.
export function validSelection(words: Word[], selection: Selection | null): Selection | null {
  if (selectedWord(words, selection) === null) {
    return null
  }
  return selection
}

export function otherDirection(direction: Direction): Direction {
  return direction === 'across' ? 'down' : 'across'
}

// The selection after a tap on a cell. Returns `current` when nothing changes.
export function selectionAfterCellTap(
  words: Word[],
  current: Selection | null,
  row: number,
  column: number,
): Selection | null {
  const hasAcross = wordAt(words, row, column, 'across') !== null
  const hasDown = wordAt(words, row, column, 'down') !== null
  if (!hasAcross && !hasDown) {
    return current
  }
  const isSelectedCell = current !== null && current.row === row && current.column === column
  if (current !== null && isSelectedCell) {
    if (hasAcross && hasDown) {
      return selectionOnCell(words, row, column, otherDirection(current.direction))
    }
    return current
  }
  const wanted: Direction = current === null ? 'across' : current.direction
  const hasWanted = wanted === 'across' ? hasAcross : hasDown
  return selectionOnCell(words, row, column, hasWanted ? wanted : otherDirection(wanted))
}

// The selection after a tap on a clue: the first cell of its word that is not
// filled, or the first cell when all are filled.
export function selectionAfterClueTap(grid: GridView, word: Word): Selection {
  const cells = cellsByPosition(grid)
  let target = word.cells[0]
  for (const position of word.cells) {
    const cell = cells.get(positionKey(position.row, position.column))
    if (cell !== undefined && cell.type === 'letter' && cell.letter === null) {
      target = position
      break
    }
  }
  return {
    row: target.row,
    column: target.column,
    direction: word.direction,
    word: wordKey(word),
  }
}

// Whether two selections have the same cell, direction and word.
export function sameSelection(first: Selection | null, second: Selection | null): boolean {
  if (first === null || second === null) {
    return first === second
  }
  return (
    first.row === second.row &&
    first.column === second.column &&
    first.direction === second.direction &&
    first.word === second.word
  )
}
