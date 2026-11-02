// The Auteurs legend's margins under the grid, as GridViewport.svelte works
// them out today (384-396; B-049 moves them to legendLayout.ts, no behaviour
// change). The legend's gap is LEGEND_GAP_PX, 8 px.

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { legendMargins, quarterPixels } from '../../web/src/lib/legendLayout'

const quarterCases: { length: number; expected: number }[] = [
  { length: 0, expected: 0 },
  { length: 12, expected: 12 },
  { length: 12.25, expected: 12.25 },
  { length: 12.3, expected: 12.25 },
  { length: 12.49, expected: 12.25 },
  { length: 12.5, expected: 12.5 },
  { length: 12.99, expected: 12.75 },
  { length: 0.2, expected: 0 },
]

for (const quarterCase of quarterCases) {
  test(`quarterPixels rounds ${quarterCase.length} down to ${quarterCase.expected}`, () => {
    assert.equal(quarterPixels(quarterCase.length), quarterCase.expected)
  })
}

test('the legend under a grid that fills the viewport sits 8 px under it', () => {
  const margins = legendMargins({
    isOverGrid: false,
    legendHeight: 30,
    legendRoom: 38,
    viewportHeight: 400,
    gridHeight: 400,
  })
  assert.deepEqual(margins, { marginTop: 8, marginBottom: 0 })
})

test('the room under a shorter, centred grid is taken back from the top margin', () => {
  // (400 - 361) / 2 = 19.5 px under the grid.
  const margins = legendMargins({
    isOverGrid: false,
    legendHeight: 30,
    legendRoom: 38,
    viewportHeight: 400,
    gridHeight: 361,
  })
  assert.deepEqual(margins, { marginTop: -11.5, marginBottom: 19.5 })
})

test('the room under the grid is kept in quarter pixels', () => {
  // (400.6 - 361) / 2 = 19.8, rounded down to 19.75.
  const margins = legendMargins({
    isOverGrid: false,
    legendHeight: 30,
    legendRoom: 38,
    viewportHeight: 400.6,
    gridHeight: 361,
  })
  assert.deepEqual(margins, { marginTop: -11.75, marginBottom: 19.75 })
})

test('a grid taller than the viewport leaves no room under it', () => {
  const margins = legendMargins({
    isOverGrid: false,
    legendHeight: 30,
    legendRoom: 38,
    viewportHeight: 300,
    gridHeight: 500,
  })
  assert.deepEqual(margins, { marginTop: 8, marginBottom: 0 })
})

test('a wrapped legend takes its own height and its gap', () => {
  const margins = legendMargins({
    isOverGrid: false,
    legendHeight: 52,
    legendRoom: 60,
    viewportHeight: 500,
    gridHeight: 480,
  })
  assert.deepEqual(margins, { marginTop: -2, marginBottom: 10 })
})

const sumCases: { viewportHeight: number; gridHeight: number; legendHeight: number }[] = [
  { viewportHeight: 400, gridHeight: 400, legendHeight: 30 },
  { viewportHeight: 400.6, gridHeight: 361, legendHeight: 30 },
  { viewportHeight: 517.33, gridHeight: 201.7, legendHeight: 22.5 },
  { viewportHeight: 120, gridHeight: 300, legendHeight: 64 },
]

for (const sumCase of sumCases) {
  const name = `margins and legend add up to legendRoom (viewport ${sumCase.viewportHeight})`
  test(name, () => {
    const legendRoom = 70
    const margins = legendMargins({
      isOverGrid: false,
      legendHeight: sumCase.legendHeight,
      legendRoom,
      viewportHeight: sumCase.viewportHeight,
      gridHeight: sumCase.gridHeight,
    })
    assert.equal(margins.marginTop + sumCase.legendHeight + margins.marginBottom, legendRoom)
  })
}

test('a legend over the grid is pulled up, its bottom 8 px above the viewport', () => {
  const margins = legendMargins({
    isOverGrid: true,
    legendHeight: 30,
    legendRoom: 0,
    viewportHeight: 90,
    gridHeight: 60,
  })
  assert.deepEqual(margins, { marginTop: -38, marginBottom: 8 })
})

test('a legend over the grid takes no room: its margins and height add up to 0', () => {
  const legendHeight = 47.5
  const margins = legendMargins({
    isOverGrid: true,
    legendHeight,
    legendRoom: 0,
    viewportHeight: 95,
    gridHeight: 41,
  })
  assert.equal(margins.marginTop + legendHeight + margins.marginBottom, 0)
})
