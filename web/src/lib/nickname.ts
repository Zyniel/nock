// How a page shows a nickname (spec 040). The server stores and sends every
// nickname in capitals (spec 012 decision 12); a page shows it with capitalised
// words. displayNickname is only for what a page shows: a page never rewrites
// with it what it keeps, stores or sends.

// A character right after one of these starts a word.
const WORD_SEPARATORS = " -'’"

// The nickname with capitalised words: `ANA` shows as `Ana`, `JEAN-LUC` as
// `Jean-Luc` and `D'ARTAGNAN` as `D'Artagnan`. The whole nickname first goes
// through one toLowerCase(), which ends a Greek word with the final sigma, `ς`
// (`ΝΊΚΟΣ` shows as `Νίκος`); lowering one character at a time would give `σ`.
// Then the first character, and each one right after a space, a hyphen or an
// apostrophe, goes through toUpperCase(). Characters are code points.
export function displayNickname(nickname: string): string {
  const lowered = nickname.toLowerCase()
  let shown = ''
  let startsWord = true
  for (const character of lowered) {
    shown += startsWord ? character.toUpperCase() : character
    startsWord = WORD_SEPARATORS.includes(character)
  }
  return shown
}
