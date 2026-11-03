// The delay before each reconnection try, as roomSession.ts draws it today
// (reconnectDelay, 1407-1415). B-049 gives it its random draw as a parameter,
// Math.random by default, so that roomConnection.ts can inject it.

import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'

import { reconnectDelay } from '../../web/src/lib/roomSession'

afterEach(() => {
  mock.restoreAll()
})

// RECONNECT_DELAYS_MS is [1000, 2000, 4000, 8000]; past the last, the last.
const delayCases: { attempt: number; draw: number; expected: number }[] = [
  // A draw of 0 gives 80 % of the base delay.
  { attempt: 0, draw: 0, expected: 800 },
  { attempt: 1, draw: 0, expected: 1600 },
  { attempt: 2, draw: 0, expected: 3200 },
  { attempt: 3, draw: 0, expected: 6400 },
  // A draw of 0.5 gives the base delay.
  { attempt: 0, draw: 0.5, expected: 1000 },
  { attempt: 1, draw: 0.5, expected: 2000 },
  { attempt: 2, draw: 0.5, expected: 4000 },
  { attempt: 3, draw: 0.5, expected: 8000 },
  // A draw just below 1 gives 120 % of it, rounded to the millisecond.
  { attempt: 0, draw: 0.9999, expected: 1200 },
  { attempt: 3, draw: 0.9999, expected: 9600 },
  // A draw of 0.25 gives 90 %.
  { attempt: 1, draw: 0.25, expected: 1800 },
  // Past the last delay, the last one.
  { attempt: 4, draw: 0.5, expected: 8000 },
  { attempt: 25, draw: 0, expected: 6400 },
]

for (const delayCase of delayCases) {
  const { attempt, draw, expected } = delayCase
  test(`reconnectDelay of try ${attempt} with a draw of ${draw} is ${expected} ms`, () => {
    assert.equal(
      reconnectDelay(attempt, () => draw),
      expected,
    )
  })
}

test('reconnectDelay draws once per call', () => {
  let draws = 0
  const random = (): number => {
    draws += 1
    return 0.5
  }
  reconnectDelay(2, random)
  assert.equal(draws, 1)
})

test('reconnectDelay rounds to a whole millisecond', () => {
  // 1000 x (0.8 + 0.4 x 0.123) = 849.2
  assert.equal(
    reconnectDelay(0, () => 0.123),
    849,
  )
})

test('reconnectDelay draws from Math.random by default, read at call time', () => {
  mock.method(Math, 'random', () => 0)
  assert.equal(reconnectDelay(1), 1600)
})
