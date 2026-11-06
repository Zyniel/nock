// remotesByCell (remoteSelections.ts) keeps the value of a cell whose remote
// drawing did not change, so that only the cells a change of the room reaches
// draw again. It proves no criterion: the reuse has no effect a browser test
// can observe, and this test guards it.

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { remotesByCell } from '../../web/src/lib/remoteSelections'
import type { CellRemotes, Corner, RemoteSelection } from '../../web/src/lib/remoteSelections'
import { positionKey } from '../../web/src/lib/wordSelection'

// Bob's word: row 1 across, columns 0 to 4.
const WORD_COLUMNS = [0, 1, 2, 3, 4]

function bobOn(column: number, corner: Corner): RemoteSelection {
  const wordPositions = new Set<string>()
  for (const wordColumn of WORD_COLUMNS) {
    wordPositions.add(positionKey(1, wordColumn))
  }
  return { playerId: 'p2', colour: 1, row: 1, column, wordPositions, corner }
}

function cellOf(byCell: Map<string, CellRemotes>, column: number): CellRemotes {
  const remotesHere = byCell.get(positionKey(1, column))
  assert.ok(remotesHere !== undefined, `no remotes on (1, ${column})`)
  return remotesHere
}

test('a cursor moving within its word keeps the value of every cell it did not touch', () => {
  const before = remotesByCell([bobOn(0, 'top-left')], new Map())

  const after = remotesByCell([bobOn(1, 'top-left')], before)

  for (const column of [2, 3, 4]) {
    assert.equal(cellOf(after, column), cellOf(before, column), `(1, ${column})`)
  }
  assert.deepEqual(cellOf(after, 2), { cursors: [], tintedBy: ['p2'], tintColour: 1 })
})

test('the cells the cursor left and reached get new values', () => {
  const before = remotesByCell([bobOn(0, 'top-left')], new Map())

  const after = remotesByCell([bobOn(1, 'top-left')], before)

  assert.notEqual(cellOf(after, 0), cellOf(before, 0))
  assert.notEqual(cellOf(after, 1), cellOf(before, 1))
  assert.deepEqual(cellOf(after, 0), { cursors: [], tintedBy: ['p2'], tintColour: 1 })
  assert.deepEqual(cellOf(after, 1), {
    cursors: [{ playerId: 'p2', colour: 1, corner: 'top-left' }],
    tintedBy: ['p2'],
    tintColour: 1,
  })
})
