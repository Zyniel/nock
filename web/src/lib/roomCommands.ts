// The messages the room page sends to the server, one function each, so the
// page's handlers say what they do and the shapes live in one place (platform
// protocol; the specs of each command name its fields).

import type { PendingEdit, ReactionValue } from './roomSession'
import type { Selection, Word } from './wordSelection'

export type EditKind = PendingEdit['kind']

// The message of an edit by its kind: edit_letter or erase for 'edit',
// pencil_edit for 'pencil', confirm_pencil for 'confirm'.
export function editMessage(
  edit: Pick<PendingEdit, 'row' | 'column' | 'letter' | 'kind'>,
  baseSeq: number | null,
): object {
  const { row, column, letter } = edit
  if (edit.kind === 'confirm') {
    return { type: 'confirm_pencil', row, column, base_seq: baseSeq }
  }
  if (edit.kind === 'pencil') {
    return { type: 'pencil_edit', row, column, letter, base_seq: baseSeq }
  }
  if (letter === null) {
    return { type: 'erase', row, column, base_seq: baseSeq }
  }
  return { type: 'edit_letter', row, column, letter, base_seq: baseSeq }
}

// The select_cell of a selection: the server only knows the cell and the
// direction, not the chosen word.
export function selectCellMessage(selected: Selection): object {
  return {
    type: 'select_cell',
    row: selected.row,
    column: selected.column,
    direction: selected.direction,
  }
}

// A clue as the check, the reveal, the flag and the reaction name it: the cell
// that holds the clue and the clue's index in that cell.
export interface ClueTarget {
  row: number
  column: number
  clue_index: number
}

export function clueTarget(word: Word): ClueTarget {
  return { row: word.clueRow, column: word.clueColumn, clue_index: word.clueIndex }
}

// A check of a letter ({ scope: 'letter', row, column }) or of a word
// ({ scope: 'word', ...clueTarget(word) }).
export function checkMessage(target: object): object {
  return { type: 'check', target }
}

// A reveal of a letter or of a word; the target is built as for a check.
export function revealMessage(target: object): object {
  return { type: 'reveal', target }
}

// My flag on a clue, or null to remove it.
export function flagMessage(clue: ClueTarget | null): object {
  return { type: 'flag', clue }
}

// A reaction on the clue of a word.
export function reactMessage(word: Word, reaction: ReactionValue): object {
  return { type: 'react', clue: clueTarget(word), reaction }
}

// My ballot on a vote.
export function voteMessage(voteId: number, yes: boolean): object {
  return { type: 'vote', vote_id: voteId, yes }
}
