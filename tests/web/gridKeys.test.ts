// What a key pressed on the focused grid does, and what a screen reader says
// when the selection moves, as GridViewport.svelte decides them today
// (onGridKeydown 460-522, announcementOf 252-277; B-049 moves them to
// gridKeys.ts, no behaviour change).

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { announcementOf, gridKeyAction } from '../../web/src/lib/gridKeys'
import type { GridKeyAction, KeyFacts } from '../../web/src/lib/gridKeys'
import type { Selection, Word } from '../../web/src/lib/wordSelection'

type Modifiers = Partial<Omit<KeyFacts, 'key'>>

function keyFacts(key: string, modifiers: Modifiers = {}): KeyFacts {
  return {
    key,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    shiftKey: false,
    isComposing: false,
    ...modifiers,
  }
}

interface KeyCase {
  name: string
  facts: KeyFacts
  wasReleased: boolean
  hasSelection: boolean
  hasUndo: boolean
  expected: GridKeyAction
}

const NONE: GridKeyAction = { kind: 'none' }

const keyCases: KeyCase[] = [
  // A modifier alone is a modifier, which keeps a release (439-441, 462-464).
  ...['Shift', 'Control', 'Alt', 'Meta'].map((key) => ({
    name: `${key} alone is a modifier`,
    facts: keyFacts(key, { shiftKey: key === 'Shift', ctrlKey: key === 'Control' }),
    wasReleased: true,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'modifier' } as GridKeyAction,
  })),
  {
    name: 'Shift alone with nothing released is a modifier',
    facts: keyFacts('Shift', { shiftKey: true }),
    wasReleased: false,
    hasSelection: false,
    hasUndo: false,
    expected: { kind: 'modifier' },
  },
  // Escape with no modifier releases the grid (467-471).
  {
    name: 'Escape releases the grid',
    facts: keyFacts('Escape'),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'release' },
  },
  {
    name: 'Escape releases the grid with nothing selected',
    facts: keyFacts('Escape'),
    wasReleased: false,
    hasSelection: false,
    hasUndo: false,
    expected: { kind: 'release' },
  },
  {
    name: 'Shift+Escape does not release the grid',
    facts: keyFacts('Escape', { shiftKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'Control+Escape does not release the grid',
    facts: keyFacts('Escape', { ctrlKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  // After Escape, Tab and Shift+Tab leave the grid (472-476).
  {
    name: 'Tab after Escape leaves the grid',
    facts: keyFacts('Tab'),
    wasReleased: true,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'leaveGrid' },
  },
  {
    name: 'Shift+Tab after Escape leaves the grid',
    facts: keyFacts('Tab', { shiftKey: true }),
    wasReleased: true,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'leaveGrid' },
  },
  {
    name: 'Control+Tab after Escape does nothing',
    facts: keyFacts('Tab', { ctrlKey: true }),
    wasReleased: true,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  // Tab and Shift+Tab move to the next or previous word (487-493), with or
  // without a selection.
  {
    name: 'Tab moves to the next word',
    facts: keyFacts('Tab'),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'tab', step: 1 },
  },
  {
    name: 'Shift+Tab moves to the previous word',
    facts: keyFacts('Tab', { shiftKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'tab', step: -1 },
  },
  {
    name: 'Tab with nothing selected moves to the next word',
    facts: keyFacts('Tab'),
    wasReleased: false,
    hasSelection: false,
    hasUndo: true,
    expected: { kind: 'tab', step: 1 },
  },
  {
    name: 'Alt+Tab does nothing',
    facts: keyFacts('Tab', { altKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'Meta+Tab does nothing',
    facts: keyFacts('Tab', { metaKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  // Control+Z or Meta+Z undoes, when the page has an undo (477-486).
  {
    name: 'Control+z undoes',
    facts: keyFacts('z', { ctrlKey: true }),
    wasReleased: false,
    hasSelection: false,
    hasUndo: true,
    expected: { kind: 'undo' },
  },
  {
    name: 'Meta+z undoes',
    facts: keyFacts('z', { metaKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'undo' },
  },
  {
    name: 'Control+Z with caps lock undoes',
    facts: keyFacts('Z', { ctrlKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'undo' },
  },
  {
    name: 'Control+z after Escape undoes',
    facts: keyFacts('z', { ctrlKey: true }),
    wasReleased: true,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'undo' },
  },
  {
    name: 'Control+Shift+z does nothing',
    facts: keyFacts('Z', { ctrlKey: true, shiftKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'Control+Alt+z does nothing',
    facts: keyFacts('z', { ctrlKey: true, altKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'Control+z with no undo is left to the browser',
    facts: keyFacts('z', { ctrlKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: false,
    expected: NONE,
  },
  // The arrows move the selection (494-498), Shift or not; with no selection
  // they do nothing.
  ...['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'].map((key) => ({
    name: `${key} moves the selection`,
    facts: keyFacts(key),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'arrow', key } as GridKeyAction,
  })),
  {
    name: 'Shift+ArrowDown moves the selection',
    facts: keyFacts('ArrowDown', { shiftKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'arrow', key: 'ArrowDown' },
  },
  {
    name: 'Control+ArrowDown does nothing',
    facts: keyFacts('ArrowDown', { ctrlKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'an arrow with nothing selected does nothing',
    facts: keyFacts('ArrowRight'),
    wasReleased: false,
    hasSelection: false,
    hasUndo: true,
    expected: NONE,
  },
  // Letters and Backspace (499-521, letterEntry.actionForKey).
  {
    name: 'a letter types its capital',
    facts: keyFacts('a'),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'letter', letter: 'A' },
  },
  {
    name: 'Shift and a letter types its capital',
    facts: keyFacts('Q', { shiftKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'letter', letter: 'Q' },
  },
  {
    name: 'an accented letter types its plain capital',
    facts: keyFacts('é'),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'letter', letter: 'E' },
  },
  {
    name: 'a letter after Escape types it',
    facts: keyFacts('m'),
    wasReleased: true,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'letter', letter: 'M' },
  },
  {
    name: 'a letter with nothing selected does nothing',
    facts: keyFacts('a'),
    wasReleased: false,
    hasSelection: false,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'a letter while composing does nothing',
    facts: keyFacts('a', { isComposing: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'Alt and a letter does nothing',
    facts: keyFacts('a', { altKey: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'Backspace erases',
    facts: keyFacts('Backspace'),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: { kind: 'erase' },
  },
  {
    name: 'Backspace with nothing selected is swallowed',
    facts: keyFacts('Backspace'),
    wasReleased: false,
    hasSelection: false,
    hasUndo: true,
    expected: { kind: 'swallow' },
  },
  {
    name: 'Backspace while composing does nothing',
    facts: keyFacts('Backspace', { isComposing: true }),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  },
  {
    name: 'Control+Backspace does nothing',
    facts: keyFacts('Backspace', { ctrlKey: true }),
    wasReleased: false,
    hasSelection: false,
    hasUndo: true,
    expected: NONE,
  },
  ...['Enter', 'F1', '1', ' ', 'œ'].map((key) => ({
    name: `the key ${JSON.stringify(key)} does nothing`,
    facts: keyFacts(key),
    wasReleased: false,
    hasSelection: true,
    hasUndo: true,
    expected: NONE,
  })),
]

for (const keyCase of keyCases) {
  test(`gridKeyAction: ${keyCase.name}`, () => {
    const action = gridKeyAction(
      keyCase.facts,
      keyCase.wasReleased,
      keyCase.hasSelection,
      keyCase.hasUndo,
    )
    assert.deepEqual(action, keyCase.expected)
  })
}

// The grid's release as GridViewport.svelte keeps it (461-471): Escape sets it,
// a modifier alone keeps it, any other key clears it. Returns the action of
// the last key.
function lastActionOf(keys: KeyFacts[], hasSelection: boolean): GridKeyAction {
  let isReleased = false
  let action: GridKeyAction = NONE
  for (const facts of keys) {
    action = gridKeyAction(facts, isReleased, hasSelection, true)
    if (action.kind !== 'modifier') {
      isReleased = action.kind === 'release'
    }
  }
  return action
}

test('Escape, Shift, then Shift+Tab leaves the grid', () => {
  const keys = [
    keyFacts('Escape'),
    keyFacts('Shift', { shiftKey: true }),
    keyFacts('Tab', { shiftKey: true }),
  ]
  assert.deepEqual(lastActionOf(keys, true), { kind: 'leaveGrid' })
})

test('Escape, Shift, then Tab leaves the grid', () => {
  const keys = [keyFacts('Escape'), keyFacts('Shift', { shiftKey: true }), keyFacts('Tab')]
  assert.deepEqual(lastActionOf(keys, true), { kind: 'leaveGrid' })
})

const clearingKeys: { name: string; facts: KeyFacts; hasSelection: boolean }[] = [
  { name: 'F1', facts: keyFacts('F1'), hasSelection: true },
  { name: 'a with nothing selected', facts: keyFacts('a'), hasSelection: false },
  { name: 'a letter typed', facts: keyFacts('a'), hasSelection: true },
]

for (const clearing of clearingKeys) {
  test(`Escape, ${clearing.name}, then Tab moves to the next word`, () => {
    const keys = [keyFacts('Escape'), clearing.facts, keyFacts('Tab')]
    assert.deepEqual(lastActionOf(keys, clearing.hasSelection), { kind: 'tab', step: 1 })
  })
}

// A word of three cells across, from (2, 1) to (2, 3).
const longWord: Word = {
  clueRow: 2,
  clueColumn: 0,
  clueIndex: 0,
  direction: 'across',
  text: 'Fleuve de Paris',
  cells: [
    { row: 2, column: 1 },
    { row: 2, column: 2 },
    { row: 2, column: 3 },
  ],
}

// A word of one cell down, at (4, 6).
const oneCellWord: Word = {
  clueRow: 3,
  clueColumn: 6,
  clueIndex: 1,
  direction: 'down',
  text: 'Note',
  cells: [{ row: 4, column: 6 }],
}

function selectionAt(row: number, column: number, word: Word): Selection {
  return {
    row,
    column,
    direction: word.direction,
    word: `${word.clueRow},${word.clueColumn},${word.clueIndex}`,
  }
}

test('announcementOf says the clue, the direction, the length and the place', () => {
  const text = announcementOf(selectionAt(2, 2, longWord), longWord)
  assert.equal(text, 'Fleuve de Paris, horizontal, 3 lettres, lettre 2')
})

test('announcementOf counts the place from 1', () => {
  const text = announcementOf(selectionAt(2, 1, longWord), longWord)
  assert.equal(text, 'Fleuve de Paris, horizontal, 3 lettres, lettre 1')
})

test('announcementOf of a word of one letter gives no place', () => {
  const text = announcementOf(selectionAt(4, 6, oneCellWord), oneCellWord)
  assert.equal(text, 'Note, vertical, 1 lettre')
})

test('announcementOf is empty with no selection', () => {
  assert.equal(announcementOf(null, longWord), '')
})

test('announcementOf is empty with no word', () => {
  assert.equal(announcementOf(selectionAt(2, 2, longWord), null), '')
})

test('announcementOf is empty when the selection is outside the word', () => {
  assert.equal(announcementOf(selectionAt(5, 5, longWord), longWord), '')
})
