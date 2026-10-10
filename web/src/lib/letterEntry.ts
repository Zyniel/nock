// What a key press means for letter entry (spec 008). Plain functions: no DOM
// and no socket, so the rules are easy to read.

export type KeyAction = { kind: 'letter'; letter: string } | { kind: 'erase' } | { kind: 'ignore' }

// The letter A to Z that a typed character stands for, or null. Accents are
// removed (é gives E); letters that do not fold to one letter (œ, æ, ß) give null.
export function letterFromKey(key: string): string | null {
  const withoutMarks = key.normalize('NFD').replace(/\p{Mn}/gu, '')
  const upper = withoutMarks.toUpperCase()
  if (/^[A-Z]$/.test(upper)) {
    return upper
  }
  return null
}

// The action of a keydown, from `event.key` and the modifier state.
export function actionForKey(
  key: string,
  ctrlKey: boolean,
  metaKey: boolean,
  altKey: boolean,
  isComposing: boolean,
): KeyAction {
  if (ctrlKey || metaKey || altKey || isComposing) {
    return { kind: 'ignore' }
  }
  if (key === 'Backspace') {
    return { kind: 'erase' }
  }
  const letter = letterFromKey(key)
  if (letter === null) {
    return { kind: 'ignore' }
  }
  return { kind: 'letter', letter }
}
