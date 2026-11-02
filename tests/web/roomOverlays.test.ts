// The overlays of the room (the popovers, the Salon, the reaction picker) and
// what each action closes, as RoomPage.svelte applies the one-overlay rule
// today (225-402, 1325-1350, 2097-2104; B-049 moves it to the reducer of
// roomOverlays.ts, no behaviour change).

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { isSalonOpen, isScrimShown, overlaysAfter } from '../../web/src/lib/roomOverlays'
import type { OverlayAction, OverlayState } from '../../web/src/lib/roomOverlays'

type Layout = 'sheet' | 'column'

const CLOSED: OverlayState = {
  popover: null,
  isSheetSalonOpen: false,
  isColumnSalonOpen: false,
  isPickerOpen: false,
}

function stateWith(changes: Partial<OverlayState>): OverlayState {
  return { ...CLOSED, ...changes }
}

interface OverlayCase {
  name: string
  layout: Layout
  before: OverlayState
  action: OverlayAction
  after: OverlayState
}

const overlayCases: OverlayCase[] = [
  // togglePopover (265-275): a second press closes it; opening one closes the
  // picker, and the Salon sheet in the sheet layout only.
  {
    name: 'opening the Aide menu closes the picker and the Salon sheet',
    layout: 'sheet',
    before: stateWith({ isSheetSalonOpen: true, isPickerOpen: true }),
    action: { kind: 'togglePopover', popover: 'aide' },
    after: stateWith({ popover: 'aide' }),
  },
  {
    name: 'opening the Menu in the column layout leaves the Salon column open',
    layout: 'column',
    before: stateWith({ isColumnSalonOpen: true, isPickerOpen: true }),
    action: { kind: 'togglePopover', popover: 'menu' },
    after: stateWith({ popover: 'menu', isColumnSalonOpen: true }),
  },
  {
    name: 'opening the Menu replaces the Aide menu',
    layout: 'column',
    before: stateWith({ popover: 'aide' }),
    action: { kind: 'togglePopover', popover: 'menu' },
    after: stateWith({ popover: 'menu' }),
  },
  {
    name: 'a second press on the open popover closes it and nothing else',
    layout: 'column',
    before: stateWith({ popover: 'menu', isColumnSalonOpen: true, isPickerOpen: true }),
    action: { kind: 'togglePopover', popover: 'menu' },
    after: stateWith({ isColumnSalonOpen: true, isPickerOpen: true }),
  },
  // closePopover (278-282, 300, the Aide and Menu items).
  {
    name: 'closing the popover leaves the Salon sheet',
    layout: 'sheet',
    before: stateWith({ popover: 'aide', isSheetSalonOpen: true }),
    action: { kind: 'closePopover' },
    after: stateWith({ isSheetSalonOpen: true }),
  },
  // setSalon (377-393): the column remembers its own state; the sheet, once
  // open, closes the popover and the picker.
  {
    name: 'opening the Salon sheet closes the popover and the picker',
    layout: 'sheet',
    before: stateWith({ popover: 'menu', isPickerOpen: true }),
    action: { kind: 'setSalon', isOpen: true },
    after: stateWith({ isSheetSalonOpen: true }),
  },
  {
    name: 'closing the Salon sheet leaves the popover and the picker',
    layout: 'sheet',
    before: stateWith({ isSheetSalonOpen: true, isPickerOpen: true }),
    action: { kind: 'setSalon', isOpen: false },
    after: stateWith({ isPickerOpen: true }),
  },
  {
    name: 'opening the Salon column leaves the popover and the picker',
    layout: 'column',
    before: stateWith({ popover: 'menu', isPickerOpen: true }),
    action: { kind: 'setSalon', isOpen: true },
    after: stateWith({ popover: 'menu', isPickerOpen: true, isColumnSalonOpen: true }),
  },
  {
    name: 'closing the Salon column leaves the sheet state alone',
    layout: 'column',
    before: stateWith({ isColumnSalonOpen: true }),
    action: { kind: 'setSalon', isOpen: false },
    after: CLOSED,
  },
  // togglePicker (1330-1340): opening it closes the popover, and the Salon
  // sheet in the sheet layout only; a second press closes it.
  {
    name: 'opening the picker closes the popover and the Salon sheet',
    layout: 'sheet',
    before: stateWith({ popover: 'aide', isSheetSalonOpen: true }),
    action: { kind: 'togglePicker' },
    after: stateWith({ isPickerOpen: true }),
  },
  {
    name: 'opening the picker in the column layout leaves the Salon column',
    layout: 'column',
    before: stateWith({ popover: 'menu', isColumnSalonOpen: true }),
    action: { kind: 'togglePicker' },
    after: stateWith({ isPickerOpen: true, isColumnSalonOpen: true }),
  },
  {
    name: 'a second press on « Réagir » closes the picker and nothing else',
    layout: 'sheet',
    before: stateWith({ isPickerOpen: true, isSheetSalonOpen: true }),
    action: { kind: 'togglePicker' },
    after: stateWith({ isSheetSalonOpen: true }),
  },
  // closePicker (1342-1350).
  {
    name: 'closing the picker closes nothing else',
    layout: 'column',
    before: stateWith({ isPickerOpen: true, popover: 'menu', isColumnSalonOpen: true }),
    action: { kind: 'closePicker' },
    after: stateWith({ popover: 'menu', isColumnSalonOpen: true }),
  },
  // scrim (308-311): it closes the popover and the Salon sheet, not the picker.
  {
    name: 'the scrim closes the popover and the Salon sheet, not the picker',
    layout: 'sheet',
    before: stateWith({ popover: 'menu', isSheetSalonOpen: true, isPickerOpen: true }),
    action: { kind: 'scrim' },
    after: stateWith({ isPickerOpen: true }),
  },
  // layoutChanged (249-261): the popovers, the picker and the sheet close; the
  // column keeps the state the player gave it.
  {
    name: 'a change to the column layout closes the popover, the picker and the sheet',
    layout: 'column',
    before: stateWith({
      popover: 'aide',
      isSheetSalonOpen: true,
      isColumnSalonOpen: true,
      isPickerOpen: true,
    }),
    action: { kind: 'layoutChanged' },
    after: stateWith({ isColumnSalonOpen: true }),
  },
  {
    name: 'a change to the sheet layout closes the popover and the picker',
    layout: 'sheet',
    before: stateWith({ popover: 'menu', isColumnSalonOpen: true, isPickerOpen: true }),
    action: { kind: 'layoutChanged' },
    after: stateWith({ isColumnSalonOpen: true }),
  },
  // roomGone (2097-2104): everything over the room closes; the Salon column
  // stays as it is.
  {
    name: 'the room gone closes the popover, the Salon sheet and the picker',
    layout: 'sheet',
    before: stateWith({ popover: 'aide', isSheetSalonOpen: true, isPickerOpen: true }),
    action: { kind: 'roomGone' },
    after: CLOSED,
  },
  {
    name: 'the room gone leaves the Salon column open',
    layout: 'column',
    before: stateWith({ popover: 'menu', isColumnSalonOpen: true, isPickerOpen: true }),
    action: { kind: 'roomGone' },
    after: stateWith({ isColumnSalonOpen: true }),
  },
  // tabLeft (338-352): a Tab out of the open menu closes it; out of the Salon
  // sheet closes the sheet.
  {
    name: 'a Tab out of the open menu closes it',
    layout: 'sheet',
    before: stateWith({ popover: 'menu', isPickerOpen: true }),
    action: { kind: 'tabLeft', leftMenu: true, leftSalon: true },
    after: stateWith({ isPickerOpen: true }),
  },
  {
    name: 'a Tab inside the open menu keeps it',
    layout: 'column',
    before: stateWith({ popover: 'aide' }),
    action: { kind: 'tabLeft', leftMenu: false, leftSalon: true },
    after: stateWith({ popover: 'aide' }),
  },
  {
    name: 'a Tab out of the Salon sheet closes it',
    layout: 'sheet',
    before: stateWith({ isSheetSalonOpen: true }),
    action: { kind: 'tabLeft', leftMenu: true, leftSalon: true },
    after: CLOSED,
  },
  {
    name: 'a Tab inside the Salon sheet keeps it',
    layout: 'sheet',
    before: stateWith({ isSheetSalonOpen: true }),
    action: { kind: 'tabLeft', leftMenu: true, leftSalon: false },
    after: stateWith({ isSheetSalonOpen: true }),
  },
  {
    name: 'a Tab out of the Salon column leaves it open',
    layout: 'column',
    before: stateWith({ isColumnSalonOpen: true }),
    action: { kind: 'tabLeft', leftMenu: true, leftSalon: true },
    after: stateWith({ isColumnSalonOpen: true }),
  },
]

for (const overlayCase of overlayCases) {
  test(`overlaysAfter (${overlayCase.layout}): ${overlayCase.name}`, () => {
    // A frozen state throws on a change: the reducer returns a new state.
    const before = Object.freeze({ ...overlayCase.before })
    const after = overlaysAfter(before, overlayCase.action, overlayCase.layout)
    assert.deepEqual(after, overlayCase.after)
  })
}

test('isSalonOpen reads the sheet in the sheet layout', () => {
  const state = stateWith({ isSheetSalonOpen: true, isColumnSalonOpen: false })
  assert.equal(isSalonOpen(state, 'sheet'), true)
  assert.equal(isSalonOpen(state, 'column'), false)
})

test('isSalonOpen reads the column in the column layout', () => {
  const state = stateWith({ isSheetSalonOpen: false, isColumnSalonOpen: true })
  assert.equal(isSalonOpen(state, 'sheet'), false)
  assert.equal(isSalonOpen(state, 'column'), true)
})

const scrimCases: { name: string; state: OverlayState; layout: Layout; expected: boolean }[] = [
  { name: 'nothing open', state: CLOSED, layout: 'sheet', expected: false },
  { name: 'a popover', state: stateWith({ popover: 'aide' }), layout: 'sheet', expected: true },
  {
    name: 'the Salon sheet',
    state: stateWith({ isSheetSalonOpen: true }),
    layout: 'sheet',
    expected: true,
  },
  {
    name: 'the picker only',
    state: stateWith({ isPickerOpen: true }),
    layout: 'sheet',
    expected: false,
  },
  {
    name: 'the column open in the sheet layout',
    state: stateWith({ isColumnSalonOpen: true }),
    layout: 'sheet',
    expected: false,
  },
  { name: 'a popover', state: stateWith({ popover: 'menu' }), layout: 'column', expected: false },
  {
    name: 'the Salon column',
    state: stateWith({ isColumnSalonOpen: true }),
    layout: 'column',
    expected: false,
  },
]

for (const scrimCase of scrimCases) {
  test(`isScrimShown (${scrimCase.layout}) with ${scrimCase.name}: ${scrimCase.expected}`, () => {
    assert.equal(isScrimShown(scrimCase.state, scrimCase.layout), scrimCase.expected)
  })
}
