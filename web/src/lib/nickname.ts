// How a page shows a nickname (spec 040). The server stores and sends every
// nickname in capitals (spec 012 decision 12); a page shows it with capitalised
// words. Only for what a page shows: what it keeps, stores or sends is the
// nickname as the server sent it.

// A character right after one of these starts a word.
const WORD_SEPARATORS = " -'’"

// The nickname with capitalised words: `ANA` shows as `Ana`, `JEAN-LUC` as
// `Jean-Luc` and `D'ARTAGNAN` as `D'Artagnan`. The first character, and each one
// right after a space, a hyphen or an apostrophe, goes through toUpperCase();
// every other character goes through toLowerCase(). Characters are code points.
export function displayNickname(nickname: string): string {
  let shown = ''
  let startsWord = true
  for (const character of nickname) {
    shown += startsWord ? character.toUpperCase() : character.toLowerCase()
    startsWord = WORD_SEPARATORS.includes(character)
  }
  return shown
}
