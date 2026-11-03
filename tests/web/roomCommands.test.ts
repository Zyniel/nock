// The messages the room page sends, as RoomPage.svelte builds them today
// (B-049 moves them to roomCommands.ts, no behaviour change).

import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  checkMessage,
  clueTarget,
  editMessage,
  flagMessage,
  reactMessage,
  revealMessage,
  selectCellMessage,
  voteMessage,
} from '../../web/src/lib/roomCommands'
import type { EditKind } from '../../web/src/lib/roomCommands'
import type { ReactionValue } from '../../web/src/lib/roomSession'
import type { Word } from '../../web/src/lib/wordSelection'

// A word of three cells whose clue is the second clue of the cell (4, 2).
const word: Word = {
  clueRow: 4,
  clueColumn: 2,
  clueIndex: 1,
  direction: 'down',
  text: 'Capitale',
  cells: [
    { row: 5, column: 2 },
    { row: 6, column: 2 },
    { row: 7, column: 2 },
  ],
}

// RoomPage.svelte 931-946: the message of an edit by its kind.
const editCases: {
  name: string
  kind: EditKind
  letter: string | null
  baseSeq: number | null
  expected: object
}[] = [
  {
    name: 'a typed letter is an edit_letter',
    kind: 'edit',
    letter: 'A',
    baseSeq: null,
    expected: { type: 'edit_letter', row: 3, column: 1, letter: 'A', base_seq: null },
  },
  {
    name: 'an edit with no letter is an erase, without a letter field',
    kind: 'edit',
    letter: null,
    baseSeq: 12,
    expected: { type: 'erase', row: 3, column: 1, base_seq: 12 },
  },
  {
    name: 'a pencil letter is a pencil_edit',
    kind: 'pencil',
    letter: 'B',
    baseSeq: 7,
    expected: { type: 'pencil_edit', row: 3, column: 1, letter: 'B', base_seq: 7 },
  },
  {
    name: 'a pencil erase is a pencil_edit with a null letter',
    kind: 'pencil',
    letter: null,
    baseSeq: null,
    expected: { type: 'pencil_edit', row: 3, column: 1, letter: null, base_seq: null },
  },
  {
    name: 'a confirm is a confirm_pencil, without a letter field',
    kind: 'confirm',
    letter: 'C',
    baseSeq: 9,
    expected: { type: 'confirm_pencil', row: 3, column: 1, base_seq: 9 },
  },
]

for (const editCase of editCases) {
  test(`editMessage: ${editCase.name}`, () => {
    const edit = { row: 3, column: 1, letter: editCase.letter, kind: editCase.kind }
    assert.deepEqual(editMessage(edit, editCase.baseSeq), editCase.expected)
  })
}

test('selectCellMessage sends the cell and the direction, not the chosen word', () => {
  const message = selectCellMessage({ row: 2, column: 5, direction: 'across', word: '2,4,0' })
  assert.deepEqual(message, { type: 'select_cell', row: 2, column: 5, direction: 'across' })
})

test('clueTarget names the clue of a word by its cell and its index', () => {
  assert.deepEqual(clueTarget(word), { row: 4, column: 2, clue_index: 1 })
})

// RoomPage.svelte 1054-1076: the letter check and the word check.
test('checkMessage wraps a letter target', () => {
  const target = { scope: 'letter', row: 6, column: 2 }
  assert.deepEqual(checkMessage(target), {
    type: 'check',
    target: { scope: 'letter', row: 6, column: 2 },
  })
})

test('checkMessage of a word target names the word by its clue', () => {
  const target = { scope: 'word', ...clueTarget(word) }
  assert.deepEqual(checkMessage(target), {
    type: 'check',
    target: { scope: 'word', row: 4, column: 2, clue_index: 1 },
  })
})

// RoomPage.svelte 1114-1138: the reveal of a letter and of a word.
test('revealMessage wraps a letter target', () => {
  const target = { scope: 'letter', row: 6, column: 2 }
  assert.deepEqual(revealMessage(target), {
    type: 'reveal',
    target: { scope: 'letter', row: 6, column: 2 },
  })
})

test('revealMessage of a word target names the word by its clue', () => {
  const target = { scope: 'word', ...clueTarget(word) }
  assert.deepEqual(revealMessage(target), {
    type: 'reveal',
    target: { scope: 'word', row: 4, column: 2, clue_index: 1 },
  })
})

// RoomPage.svelte 1167-1183: a flag on a clue, or the removal of my flag.
test('flagMessage puts a flag on a clue', () => {
  assert.deepEqual(flagMessage(clueTarget(word)), {
    type: 'flag',
    clue: { row: 4, column: 2, clue_index: 1 },
  })
})

test('flagMessage with no clue removes my flag', () => {
  assert.deepEqual(flagMessage(null), { type: 'flag', clue: null })
})

// RoomPage.svelte 1354-1366: a reaction on the clue of the selected word.
const reactions: ReactionValue[] = ['thumbs_up', 'clap', 'laugh', 'wow', 'thinking']

for (const reaction of reactions) {
  test(`reactMessage sends ${reaction} on the clue of the word`, () => {
    assert.deepEqual(reactMessage(word, reaction), {
      type: 'react',
      clue: { row: 4, column: 2, clue_index: 1 },
      reaction,
    })
  })
}

// RoomPage.svelte 1478: a ballot.
test('voteMessage sends a yes ballot', () => {
  assert.deepEqual(voteMessage(3, true), { type: 'vote', vote_id: 3, yes: true })
})

test('voteMessage sends a no ballot', () => {
  assert.deepEqual(voteMessage(8, false), { type: 'vote', vote_id: 8, yes: false })
})
