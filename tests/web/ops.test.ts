import assert from 'node:assert/strict'
import { test } from 'node:test'

import { cellStatesAtStep } from '../../web/src/lib/ops'
import type { EditKind, RoomEdit } from '../../web/src/lib/ops'

function makeEdit(seq: number, kind: EditKind, letter: string | null, pencil: boolean): RoomEdit {
  return {
    seq,
    at: '2026-01-01T10:31:05Z',
    kind,
    row: 1,
    column: 0,
    letter,
    pencil,
    player_id: kind === 'locked' ? null : 'player-1',
    nickname: kind === 'locked' ? null : 'ANA',
  }
}

const pencilThenLock: RoomEdit[] = [
  makeEdit(1, 'typed', 'T', true),
  makeEdit(2, 'locked', 'T', false),
]

test('step 0 has no cell state', () => {
  assert.equal(cellStatesAtStep(pencilThenLock, 0).size, 0)
})

test('a pencil letter alone is a pencil letter on an unlocked cell', () => {
  const states = cellStatesAtStep(pencilThenLock, 1)
  assert.equal(states.size, 1)
  assert.deepEqual(states.get('1,0'), {
    letter: 'T',
    locked: false,
    revealed: false,
    pencil: true,
  })
})

test('a lock after a pencil letter keeps the letter and drops the pencil', () => {
  const states = cellStatesAtStep(pencilThenLock, 2)
  assert.equal(states.size, 1)
  assert.deepEqual(states.get('1,0'), {
    letter: 'T',
    locked: true,
    revealed: false,
    pencil: false,
  })
})
