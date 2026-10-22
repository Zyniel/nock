// The list of the room page that scrolls: the Salon's stream, which holds the
// chat messages and the event lines (spec 043).
//
// - It follows its changes of size and content (watchListChanges).
// - A list that scrolls with nothing focusable inside is a Tab stop in every
//   engine, so that a keyboard player can scroll it with the arrow keys (spec
//   035 AC-12).
// - It keeps the reader's place when a new line comes in, and a list at its end
//   stays at its end (spec 013 AC-7, AC-8; spec 022 AC-11).

// ---- Changes of a list ----

// Call `onChange` after the list or one of its items changes size (a resize, a
// rotation, a new root font), and after its content changes (an item comes or
// goes, a button shows or goes, a text changes). Returns a function that stops.
export function watchListChanges(list: HTMLElement, onChange: () => void): () => void {
  const sizeObserver = new ResizeObserver(onChange)
  // The items come and go, so the size observer follows the items of the moment.
  function observeSizes(): void {
    sizeObserver.disconnect()
    sizeObserver.observe(list)
    for (const item of Array.from(list.children)) {
      sizeObserver.observe(item)
    }
  }
  const contentObserver = new MutationObserver(() => {
    observeSizes()
    onChange()
  })
  contentObserver.observe(list, { childList: true, subtree: true, characterData: true })
  observeSizes()
  return () => {
    sizeObserver.disconnect()
    contentObserver.disconnect()
  }
}

// ---- Tab stop (spec 035 AC-12) ----

// The elements that are Tab stops of their own.
const TAB_STOP_SELECTOR = [
  'a[href]',
  'button:not(:disabled)',
  'input:not(:disabled)',
  'select:not(:disabled)',
  'textarea:not(:disabled)',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

function canScroll(overflow: string): boolean {
  return overflow === 'auto' || overflow === 'scroll'
}

// True while the content of the list is wider or taller than the list, on a side
// where the list scrolls.
function listScrolls(list: HTMLElement): boolean {
  const style = getComputedStyle(list)
  const scrollsSideways = canScroll(style.overflowX) && list.scrollWidth > list.clientWidth
  const scrollsDown = canScroll(style.overflowY) && list.scrollHeight > list.clientHeight
  return scrollsSideways || scrollsDown
}

// The tabindex the list needs now, or null for none:
// - '0' while it scrolls with nothing focusable inside, because WebKit does not
//   make a scroll container a Tab stop on its own;
// - '-1' while it scrolls and holds a Tab stop: the buttons inside take the
//   focus, and without it Firefox may make the list a Tab stop of its own;
// - none while it does not scroll, since there is nothing to scroll.
function neededTabIndex(list: HTMLElement): string | null {
  if (!listScrolls(list)) {
    return null
  }
  if (list.querySelector(TAB_STOP_SELECTOR) !== null) {
    return '-1'
  }
  return '0'
}

// Give the list the tabindex it needs. A list that has the focus keeps its
// tabindex until the focus leaves it: taking it away would drop the keyboard
// focus to the page, and the player would lose their place.
function updateTabIndex(list: HTMLElement): void {
  if (document.activeElement === list) {
    return
  }
  const needed = neededTabIndex(list)
  if (list.getAttribute('tabindex') === needed) {
    return
  }
  if (needed === null) {
    list.removeAttribute('tabindex')
  } else {
    list.setAttribute('tabindex', needed)
  }
}

// Keep the tabindex of the list up to date while the list changes, and once the
// focus has left it. Returns a function that stops.
export function followListTabStop(list: HTMLElement): () => void {
  function update(): void {
    updateTabIndex(list)
  }
  // During a blur the next element does not have the focus yet, so look again
  // once it has it.
  function updateAfterBlur(): void {
    setTimeout(update, 0)
  }
  list.addEventListener('blur', updateAfterBlur)
  const stopWatching = watchListChanges(list, update)
  update()
  return () => {
    list.removeEventListener('blur', updateAfterBlur)
    stopWatching()
  }
}

// ---- The feed list's place (spec 013 AC-7, AC-8) ----

// scrollTop can have a fraction while scrollHeight and clientHeight are whole
// numbers, so a list is at its end while at most 1px of it is hidden below.
const AT_END_TOLERANCE_PX = 1

// True while the list shows its last line. A list that does not scroll is at
// its end.
function isAtEnd(list: HTMLElement): boolean {
  const hiddenBelow = list.scrollHeight - list.clientHeight - list.scrollTop
  return hiddenBelow <= AT_END_TOLERANCE_PX
}

// Show the last line of the list.
export function scrollToEnd(list: HTMLElement): void {
  // The browser stops scrollTop at the end of the list.
  list.scrollTop = list.scrollHeight
}

// Where the feed list is just before a new line shows: whether it is at its end,
// and its newest line with the distance from the top of the list to that line.
export interface FeedPlace {
  wasAtEnd: boolean
  newestLine: Element | null
  newestLineTop: number
}

function topInList(list: HTMLElement, line: Element): number {
  return line.getBoundingClientRect().top - list.getBoundingClientRect().top
}

// Note where the feed list is. Call it just before a new line shows.
export function noteFeedPlace(list: HTMLElement): FeedPlace {
  const newestLine = list.lastElementChild
  let newestLineTop = 0
  if (newestLine !== null) {
    newestLineTop = topInList(list, newestLine)
  }
  return { wasAtEnd: isAtEnd(list), newestLine, newestLineTop }
}

// Call it once the new line shows. A list that was at its end goes to its end,
// so the new line is in view. Otherwise the lines on screen stay where they
// were. When the feed is full, the new line also removes the oldest one, which
// moves the others up: the list then scrolls up by as much (to 0 at most).
export function keepFeedPlace(list: HTMLElement, place: FeedPlace): void {
  if (place.wasAtEnd) {
    scrollToEnd(list)
    return
  }
  // The newest line of before stays in the list, below the removed ones.
  if (place.newestLine === null || !list.contains(place.newestLine)) {
    return
  }
  const movedBy = topInList(list, place.newestLine) - place.newestLineTop
  if (movedBy !== 0) {
    list.scrollTop += movedBy
  }
}

// True while the list is not drawn, for example while a parent of it is hidden.
// A hidden list measures 0, so it always looks at its end.
function isHidden(list: HTMLElement): boolean {
  return list.getClientRects().length === 0
}

// The two heights that say where the end of a list is.
interface ListSize {
  clientHeight: number
  scrollHeight: number
}

function sizeOf(list: HTMLElement): ListSize {
  return { clientHeight: list.clientHeight, scrollHeight: list.scrollHeight }
}

function sameSize(first: ListSize, second: ListSize): boolean {
  return (
    first.clientHeight === second.clientHeight && first.scrollHeight === second.scrollHeight
  )
}

// Keep a feed list that is at its end at its end when its size or the height of
// its lines changes: a resize, a rotation, a new root font, the list hidden and
// shown again. A list that is not at its end is left where it is. Returns a
// function that stops.
export function keepFeedEndOnResize(list: HTMLElement): () => void {
  // Whether the list was at its end after the reader's last scroll.
  let wasAtEnd = isAtEnd(list)
  // The size of the list when it was last brought back to its end (or not).
  let notedSize = sizeOf(list)
  function noteScroll(): void {
    // A hidden list measures 0 and looks at its end: keep what was true before.
    if (isHidden(list)) {
      return
    }
    // A scroll that comes with a change of size is the browser's, not the
    // reader's: Firefox puts back the old scrollTop of a list shown again before
    // the size observer runs, and the browser brings scrollTop back into the
    // new range of a list that got smaller, which puts it at its end. Such a
    // scroll may put the list at its end, but it does not take it away from it;
    // backToEnd runs next.
    const nowAtEnd = isAtEnd(list)
    if (!sameSize(sizeOf(list), notedSize) && !nowAtEnd) {
      return
    }
    wasAtEnd = nowAtEnd
  }
  function backToEnd(): void {
    if (wasAtEnd) {
      scrollToEnd(list)
    }
    notedSize = sizeOf(list)
  }
  list.addEventListener('scroll', noteScroll)
  const stopWatching = watchListChanges(list, backToEnd)
  return () => {
    list.removeEventListener('scroll', noteScroll)
    stopWatching()
  }
}
