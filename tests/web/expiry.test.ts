// The end of each flash, catch-up highlight and reaction a fixed time after
// it appeared, as RoomPage.svelte schedules them today (526-588 and
// 1374-1405, three copies; B-049 makes them one trackExpiries in expiry.ts,
// no behaviour change).

import assert from 'node:assert/strict'
import { afterEach, beforeEach, mock, test } from 'node:test'

import { trackExpiries } from '../../web/src/lib/expiry'

beforeEach(() => {
  mock.timers.enable({ apis: ['setTimeout', 'setInterval'] })
})

afterEach(() => {
  mock.timers.reset()
})

// Move the clock one millisecond at a time, so that a timer set by another
// timer runs at its own time.
function advance(ms: number): void {
  for (let step = 0; step < ms; step += 1) {
    mock.timers.tick(1)
  }
}

test('an item ends its time after it was scheduled, not before', () => {
  const ended: number[] = []
  const tracker = trackExpiries(1000, (id) => ended.push(id))
  tracker.schedule([{ id: 4 }])
  advance(999)
  assert.deepEqual(ended, [])
  advance(1)
  assert.deepEqual(ended, [4])
})

test('each item has its own time', () => {
  const ended: number[] = []
  const tracker = trackExpiries(3000, (id) => ended.push(id))
  tracker.schedule([{ id: 1 }])
  advance(1000)
  tracker.schedule([{ id: 1 }, { id: 2 }])
  advance(2000)
  assert.deepEqual(ended, [1])
  advance(1000)
  assert.deepEqual(ended, [1, 2])
})

test('an item scheduled again keeps its first time', () => {
  const ended: number[] = []
  const tracker = trackExpiries(1000, (id) => ended.push(id))
  tracker.schedule([{ id: 7 }])
  advance(600)
  tracker.schedule([{ id: 7 }])
  advance(400)
  assert.deepEqual(ended, [7])
  advance(2000)
  assert.deepEqual(ended, [7])
})

test('an item that left the list still ends at its time', () => {
  // A flash replaced by a newer one is no longer in the list: its timer runs
  // anyway and finds nothing to end.
  const ended: number[] = []
  const tracker = trackExpiries(1000, (id) => ended.push(id))
  tracker.schedule([{ id: 1 }])
  advance(500)
  tracker.schedule([{ id: 2 }])
  advance(500)
  assert.deepEqual(ended, [1])
  advance(500)
  assert.deepEqual(ended, [1, 2])
})

test('an id that ended is scheduled anew when it shows again', () => {
  const ended: number[] = []
  const tracker = trackExpiries(1000, (id) => ended.push(id))
  tracker.schedule([{ id: 3 }])
  advance(1000)
  tracker.schedule([{ id: 3 }])
  advance(999)
  assert.deepEqual(ended, [3])
  advance(1)
  assert.deepEqual(ended, [3, 3])
})

test('dispose cancels every time still running', () => {
  const ended: number[] = []
  const tracker = trackExpiries(1000, (id) => ended.push(id))
  tracker.schedule([{ id: 1 }, { id: 2 }])
  advance(500)
  tracker.dispose()
  advance(5000)
  assert.deepEqual(ended, [])
})
