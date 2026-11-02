// scrollAfterZoom: the scroll on one axis after a pinch changes the cell size,
// so that the grid point under the fingers stays under them (pinchPan.ts calls
// it once for scrollLeft and once for scrollTop).

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { scrollAfterZoom } from '../../web/src/lib/gridLayout'

test('zooming in keeps the point under the offset', () => {
  // Point at (100 + 50) / 40 = 3.75 cells; at 60 px a cell it is 225 px away.
  assert.equal(scrollAfterZoom(100, 50, 40, 60), 175)
})

test('zooming out keeps the point under the offset', () => {
  // Point at (200 + 100) / 60 = 5 cells; at 40 px a cell it is 200 px away.
  assert.equal(scrollAfterZoom(200, 100, 60, 40), 100)
})

test('an unchanged cell size leaves the scroll as it was', () => {
  assert.equal(scrollAfterZoom(37, 20, 30, 30), 37)
})
