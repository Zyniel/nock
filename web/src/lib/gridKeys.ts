// What a key pressed on the focused grid does (specs 008, 009 and 035), and what
// a screen reader says when the selection moves. Plain functions: no DOM and no
// socket, so the rules are easy to read; GridViewport carries the action out.

import { t } from './i18n'
import { actionForKey } from './letterEntry'
import { isArrowKey } from './navigation'
import type { ArrowKey } from './navigation'
import type { Position, Selection, Word } from './wordSelection'

// What the grid needs to know about a keydown.
export interface KeyFacts {
  key: string
  ctrlKey: boolean
  metaKey: boolean
  altKey: boolean
  shiftKey: boolean
  isComposing: boolean
}

// - 'modifier': a modifier key alone; it changes nothing, not even a release.
// - 'release': Escape; the next Tab or Shift+Tab leaves the grid.
// - 'leaveGrid': that Tab; the browser moves the focus out of the grid.
// - 'undo', 'tab', 'arrow', 'letter', 'erase': the page acts on the key.
// - 'swallow': Backspace with nothing selected; it must not leave the page.
// - 'none': any other key; the browser keeps it.
export type GridKeyAction =
  | { kind: 'modifier' }
  | { kind: 'none' }
  | { kind: 'release' }
  | { kind: 'leaveGrid' }
  | { kind: 'undo' }
  | { kind: 'tab'; step: 1 | -1 }
  | { kind: 'arrow'; key: ArrowKey }
  | { kind: 'letter'; letter: string }
  | { kind: 'erase' }
  | { kind: 'swallow' }

function isModifierKey(key: string): boolean {
  return key === 'Shift' || key === 'Control' || key === 'Alt' || key === 'Meta'
}

// The action of a keydown. `wasReleased` is true when the last key was Escape
// (a modifier alone does not count as a key); `hasUndo` is true when the page
// can undo.
export function gridKeyAction(
  facts: KeyFacts,
  wasReleased: boolean,
  hasSelection: boolean,
  hasUndo: boolean,
): GridKeyAction {
  if (isModifierKey(facts.key)) {
    return { kind: 'modifier' }
  }
  const hasAnyModifier = facts.ctrlKey || facts.metaKey || facts.altKey || facts.shiftKey
  if (facts.key === 'Escape' && !hasAnyModifier) {
    return { kind: 'release' }
  }
  const isPlainTab = facts.key === 'Tab' && !facts.ctrlKey && !facts.metaKey && !facts.altKey
  if (isPlainTab && wasReleased) {
    return { kind: 'leaveGrid' }
  }
  const isUndo =
    (facts.ctrlKey || facts.metaKey) &&
    !facts.altKey &&
    !facts.shiftKey &&
    facts.key.toLowerCase() === 'z'
  if (isUndo && hasUndo) {
    return { kind: 'undo' }
  }
  const hasModifier = facts.ctrlKey || facts.metaKey || facts.altKey
  if (!hasModifier && facts.key === 'Tab') {
    return { kind: 'tab', step: facts.shiftKey ? -1 : 1 }
  }
  if (!hasModifier && isArrowKey(facts.key) && hasSelection) {
    return { kind: 'arrow', key: facts.key }
  }
  const action = actionForKey(
    facts.key,
    facts.ctrlKey,
    facts.metaKey,
    facts.altKey,
    facts.isComposing,
  )
  if (action.kind === 'ignore') {
    return { kind: 'none' }
  }
  if (!hasSelection) {
    // Backspace never leaves the page, even with nothing selected.
    return action.kind === 'erase' ? { kind: 'swallow' } : { kind: 'none' }
  }
  return action
}

// What a screen reader says when the selection moves (spec 035).
export function announcementOf(current: Selection | null, word: Word | null): string {
  if (current === null || word === null) {
    return ''
  }
  const direction = t(word.direction === 'across' ? 'a11y.direction.across' : 'a11y.direction.down')
  if (word.cells.length === 1) {
    return t('a11y.announcement_one', { clue: word.text, direction })
  }
  const index = word.cells.findIndex(
    (cell: Position) => cell.row === current.row && cell.column === current.column,
  )
  if (index === -1) {
    return ''
  }
  return t('a11y.announcement', {
    clue: word.text,
    direction,
    length: word.cells.length,
    position: index + 1,
  })
}
