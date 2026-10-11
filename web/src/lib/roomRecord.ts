// The room record kept on this device, `nock.room.<code>` (spec 010): the
// catalogue number of the room and the selection. Unknown fields are kept.

import { parseObject, readItem, roomRecordKey, writeItem } from './joinRules'
import type { Direction } from './wordSelection'

export interface SavedSelection {
  row: number
  column: number
  direction: Direction
}

// The record, or an empty object when it is absent or not a JSON object.
function readRecord(code: string): Record<string, unknown> {
  const record = parseObject(readItem(roomRecordKey(code)))
  return record === null ? {} : record
}

function writeRecord(code: string, record: Record<string, unknown>): void {
  writeItem(roomRecordKey(code), JSON.stringify(record))
}

// Remember that this device created the room from a catalogue grid.
export function writeRoomCreated(code: string, grid: number): void {
  writeRecord(code, { grid, selection: null })
}

// The catalogue number of the room, or null when unknown.
export function readRoomGrid(code: string): number | null {
  const { grid } = readRecord(code)
  return typeof grid === 'number' ? grid : null
}

// Remember the selection; a missing or corrupt record gets `grid: null`.
export function writeRoomSelection(code: string, selection: SavedSelection): void {
  const record = readRecord(code)
  if (!('grid' in record)) {
    record.grid = null
  }
  record.selection = {
    row: selection.row,
    column: selection.column,
    direction: selection.direction,
  }
  writeRecord(code, record)
}

// The saved selection when it has the right shape, otherwise null. Whether the
// grid has a word there is for the caller to check.
export function readRoomSelection(code: string): SavedSelection | null {
  const { selection } = readRecord(code)
  if (typeof selection !== 'object' || selection === null || Array.isArray(selection)) {
    return null
  }
  const { row, column, direction } = selection as Record<string, unknown>
  if (typeof row !== 'number' || typeof column !== 'number') {
    return null
  }
  if (direction !== 'across' && direction !== 'down') {
    return null
  }
  return { row, column, direction }
}
