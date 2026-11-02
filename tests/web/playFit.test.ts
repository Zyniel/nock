// The room's layout and the fit of its play area, as RoomPage.svelte works
// them out today (layoutOf 210-223, the play area 1747-1854; B-049 moves them
// to playFit.ts, no behaviour change). The play area's padding is 12 px, the
// clue bar 34 px high and at least 320 px wide (CLUE_BAR_MIN_PX).

import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  clueBarWidthOf,
  columnGridBoxFor,
  layoutOf,
  legendPlacement,
} from '../../web/src/lib/playFit'

type Layout = 'sheet' | 'column'

const layoutCases: { width: number; height: number; isKeyboardOn: boolean; expected: Layout }[] =
  [
    // A wide window: landscape, at least 900 px wide, more than 500 px high.
    { width: 1280, height: 800, isKeyboardOn: false, expected: 'column' },
    { width: 1280, height: 800, isKeyboardOn: true, expected: 'column' },
    { width: 900, height: 501, isKeyboardOn: false, expected: 'column' },
    // Portrait or square: always the sheet.
    { width: 768, height: 1024, isKeyboardOn: false, expected: 'sheet' },
    { width: 600, height: 600, isKeyboardOn: false, expected: 'sheet' },
    { width: 400, height: 450, isKeyboardOn: false, expected: 'sheet' },
    // Landscape but narrow and not low.
    { width: 899, height: 600, isKeyboardOn: false, expected: 'sheet' },
    // A low landscape window (at most 500 px high): the column without the
    // in-app keyboard, the sheet with it.
    { width: 740, height: 360, isKeyboardOn: false, expected: 'column' },
    { width: 740, height: 360, isKeyboardOn: true, expected: 'sheet' },
    { width: 1000, height: 500, isKeyboardOn: false, expected: 'column' },
    { width: 1000, height: 500, isKeyboardOn: true, expected: 'sheet' },
  ]

for (const layoutCase of layoutCases) {
  const keyboard = layoutCase.isKeyboardOn ? 'with' : 'without'
  const size = `${layoutCase.width}x${layoutCase.height}`
  test(`layoutOf ${size} ${keyboard} the keyboard is ${layoutCase.expected}`, () => {
    const layout = layoutOf(layoutCase.width, layoutCase.height, layoutCase.isKeyboardOn)
    assert.equal(layout, layoutCase.expected)
  })
}

// A play block whose height leaves 501 px to a 10 by 10 grid once the padding
// (12) and the clue bar (34) are taken: cells of 50 px, a box of 501 px.
const COLUMN_INPUT = {
  layout: 'column' as Layout,
  grid: { width: 10, height: 10 },
  playBlockWidth: 1001,
  playBlockHeight: 547,
  statusBandHeight: 0,
  isStatusUnderClueBar: false,
  legendRoomPx: 0,
}

test('columnGridBoxFor is null in the sheet layout', () => {
  assert.equal(columnGridBoxFor({ ...COLUMN_INPUT, layout: 'sheet' }), null)
})

test('columnGridBoxFor is null before the grid is known', () => {
  assert.equal(columnGridBoxFor({ ...COLUMN_INPUT, grid: null }), null)
})

test('columnGridBoxFor fits the grid to the height left after the padding and the clue bar', () => {
  assert.deepEqual(columnGridBoxFor(COLUMN_INPUT), { width: 501, height: 501 })
})

test('columnGridBoxFor takes the status band under the clue bar', () => {
  const box = columnGridBoxFor({
    ...COLUMN_INPUT,
    statusBandHeight: 40,
    isStatusUnderClueBar: true,
  })
  assert.deepEqual(box, { width: 461, height: 461 })
})

test('columnGridBoxFor ignores the band height while the status is not under the bar', () => {
  const box = columnGridBoxFor({
    ...COLUMN_INPUT,
    statusBandHeight: 40,
    isStatusUnderClueBar: false,
  })
  assert.deepEqual(box, { width: 501, height: 501 })
})

test('columnGridBoxFor takes the legend room', () => {
  const box = columnGridBoxFor({ ...COLUMN_INPUT, legendRoomPx: 60 })
  assert.deepEqual(box, { width: 441, height: 441 })
})

test('columnGridBoxFor takes the band and the legend room together', () => {
  const box = columnGridBoxFor({
    ...COLUMN_INPUT,
    statusBandHeight: 40,
    isStatusUnderClueBar: true,
    legendRoomPx: 60,
  })
  assert.deepEqual(box, { width: 401, height: 401 })
})

test('columnGridBoxFor fits a wide grid to the width', () => {
  const box = columnGridBoxFor({
    ...COLUMN_INPUT,
    grid: { width: 15, height: 5 },
    playBlockWidth: 451,
  })
  assert.deepEqual(box, { width: 451, height: 151 })
})

test('columnGridBoxFor with no height left is the grid line alone', () => {
  const box = columnGridBoxFor({ ...COLUMN_INPUT, playBlockHeight: 30 })
  assert.deepEqual(box, { width: 1, height: 1 })
})

const clueBarCases: {
  name: string
  box: { width: number; height: number } | null
  playBlockWidth: number
  expected: number | null
}[] = [
  { name: 'the sheet layout gives no width', box: null, playBlockWidth: 1000, expected: null },
  {
    name: 'a grid wider than 320 px gives its width',
    box: { width: 501, height: 501 },
    playBlockWidth: 1001,
    expected: 501,
  },
  {
    name: 'a narrower grid gives 320 px',
    box: { width: 200, height: 400 },
    playBlockWidth: 1001,
    expected: 320,
  },
  {
    name: 'a play area narrower than 320 px gives its own width',
    box: { width: 200, height: 400 },
    playBlockWidth: 280,
    expected: 280,
  },
]

for (const clueBarCase of clueBarCases) {
  test(`clueBarWidthOf: ${clueBarCase.name}`, () => {
    assert.equal(clueBarWidthOf(clueBarCase.box, clueBarCase.playBlockWidth), clueBarCase.expected)
  })
}

const legendCases: {
  name: string
  isAuthorsViewOn: boolean
  wantedLegendRoom: number
  viewportHeightWithRoom: number
  expected: { isOverGrid: boolean; legendRoom: number }
}[] = [
  {
    name: 'the mode off gives the legend no room',
    isAuthorsViewOn: false,
    wantedLegendRoom: 38,
    viewportHeightWithRoom: 20,
    expected: { isOverGrid: false, legendRoom: 0 },
  },
  {
    name: 'a viewport of 100 px with the room keeps the legend under the grid',
    isAuthorsViewOn: true,
    wantedLegendRoom: 38,
    viewportHeightWithRoom: 100,
    expected: { isOverGrid: false, legendRoom: 38 },
  },
  {
    name: 'a wrapped legend gets the room it wants',
    isAuthorsViewOn: true,
    wantedLegendRoom: 60,
    viewportHeightWithRoom: 400,
    expected: { isOverGrid: false, legendRoom: 60 },
  },
  {
    name: 'a viewport under 100 px with the room puts the legend over the grid',
    isAuthorsViewOn: true,
    wantedLegendRoom: 38,
    viewportHeightWithRoom: 99.5,
    expected: { isOverGrid: true, legendRoom: 0 },
  },
]

for (const legendCase of legendCases) {
  test(`legendPlacement: ${legendCase.name}`, () => {
    const placement = legendPlacement({
      isAuthorsViewOn: legendCase.isAuthorsViewOn,
      wantedLegendRoom: legendCase.wantedLegendRoom,
      viewportHeightWithRoom: legendCase.viewportHeightWithRoom,
    })
    assert.deepEqual(placement, legendCase.expected)
  })
}
