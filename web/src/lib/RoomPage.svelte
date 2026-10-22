<script lang="ts">
  import { onMount, tick } from 'svelte'
  import AccountDialog from './AccountDialog.svelte'
  import ChatPanel from './ChatPanel.svelte'
  import GridViewport from './GridViewport.svelte'
  import InAppKeyboard from './InAppKeyboard.svelte'
  import PlayerIcon from './PlayerIcon.svelte'
  import ReactionPicker from './ReactionPicker.svelte'
  import RecapDialog from './RecapDialog.svelte'
  import RoomTimer from './RoomTimer.svelte'
  import { t } from './i18n'
  import { fetchAccountStatus, linkRoom, type AccountStatus } from './account'
  import { nameOf } from './activityFeed'
  import { authorLine, colourByPlayer, shownAuthorOf } from './authorsView'
  import {
    chatToggleLabel,
    clueReactionMarkers,
    isPaced,
    msUntilNextExpiry,
    sendsInWindow,
    unreadBadgeText,
    unreadCount,
  } from './chat'
  import {
    ACCESSIBILITY_KEY,
    OTHERS_TINT_KEY,
    readAccessibility,
    readOthersTint,
    writeSwitch,
  } from './cellDisplaySwitches'
  import { clueFlagMarkers, flagOf, isClueOfWord } from './clueFlags'
  import { newLinkCopier } from './copyLink'
  import { checkNickname, planAutomaticJoin, readNickname, writeIdentity, writeNickname } from './joinRules'
  import { markFinished } from './catalogue'
  import { recordOwnRoom } from './history'
  import {
    CATCH_UP_HIGHLIGHT_MS,
    applyCatchUp,
    endCaughtUp,
    fetchCatchUp,
  } from './catchUp'
  import { displayNickname } from './nickname'
  import { remoteSelectionsOf } from './remoteSelections'
  import {
    readRoomGrid,
    readRoomSeenSeq,
    readRoomSelection,
    writeRoomSeenSeq,
    writeRoomSelection,
  } from './roomRecord'
  import {
    followListTabStop,
    keepFeedEndOnResize,
    keepFeedPlace,
    noteFeedPlace,
    watchListChanges,
  } from './scrollingLists'
  import type { FeedPlace } from './scrollingLists'
  import type {
    LetterCellView,
    PendingEdit,
    ReactionValue,
    Snapshot,
    VoteView,
  } from './roomSession'
  import {
    EDIT_SEND_INTERVAL_MS,
    FLASH_MS,
    PING_INTERVAL_MS,
    REACTION_MS,
    SILENCE_LIMIT_MS,
    VOTE_RESULT_MS,
    addPendingEdit,
    endFlash,
    endReaction,
    gridLabel,
    isFinalClose,
    newSession,
    receiveFrame,
    reconnectDelay,
    shownCell,
    shownGrid,
    statusAfterFinalClose,
    statusAfterLoss,
  } from './roomSession'
  import {
    computeWords,
    sameSelection,
    selectedWord,
    selectionAfterCellTap,
    selectionAfterClueTap,
    selectionOnCell,
    validSelection,
    wordKey,
  } from './wordSelection'
  import type { Selection, Word } from './wordSelection'

  const UNDO_MESSAGE_MS = 3000
  const MAX_REVEAL_COUNT = 99
  // The performance mark set once the grid takes taps and keys (spec 036).
  const INTERACTIVE_MARK = 'nock:interactive'
  // The remove buttons are compact in a roster list narrower than this many root
  // font sizes (spec 014 AC-9).
  const COMPACT_REMOVE_BELOW_ROOT_FONTS = 4.5
  // The space between the header and the chat panel or the reaction picker.
  const POPOVER_GAP_PX = 4
  // The reaction picker and the chat panel sit side by side on a page at least
  // this many root font sizes wide: the picker (10.25rem and its border), the
  // panel (22rem) and three gaps of 0.5rem. On a narrower page the picker sits
  // above the panel (spec 022 decision 15).
  const SIDE_BY_SIDE_MIN_ROOT_FONTS = 34

  let { code }: { code: string } = $props()

  let session = $state(newSession())
  let rawSelection: Selection | null = $state(null)
  // The nickname form: the text as typed (CSS shows it in capitals), the error
  // shown, and the nickname of a join sent from the form that no snapshot has
  // answered yet.
  let nicknameText = $state(readNickname() ?? '')
  let formError: 'length' | 'characters' | null = $state(null)
  let formJoinNickname: string | null = $state(null)
  let socket: WebSocket | null = null
  let gridViewport: GridViewport | undefined = $state()
  // The in-app keyboard is for touch screens: the main pointer is coarse.
  const isTouchScreen = window.matchMedia('(pointer: coarse)').matches

  // A low window (at most 500 px high, a phone on its side), the same breakpoint
  // as the styles below. There the completion status sits in the clue bar's row,
  // so that it takes no height from the grid (spec 026 AC-10). It follows a
  // resize or a rotation.
  const lowWindowQuery = window.matchMedia('(max-height: 500px)')
  let isLowWindow = $state(lowWindowQuery.matches)

  $effect(() => {
    const onChange = (): void => {
      isLowWindow = lowWindowQuery.matches
    }
    lowWindowQuery.addEventListener('change', onChange)
    return () => lowWindowQuery.removeEventListener('change', onChange)
  })

  // The host panel scrolls sideways on a small window. An edge fade says so
  // without depending on the scrollbar, which some engines hide. Svelte sets
  // the element back to null when the panel goes (the host role moved away).
  let hostPanel: HTMLElement | null = $state(null)
  let hostPanelHasMore = $state(false)

  // The room toolbar (spec 024) scrolls sideways on a small window too, with the
  // same edge fade.
  let roomToolbar: HTMLElement | null = $state(null)
  let roomToolbarHasMore = $state(false)

  // True while content is hidden past the right edge of a row that scrolls.
  function hasContentPastRightEdge(row: HTMLElement | null): boolean {
    if (row === null) {
      return false
    }
    const hiddenOnTheRight = row.scrollWidth - row.clientWidth - row.scrollLeft
    return hiddenOnTheRight > 1
  }

  // Show the fade while content is hidden past the right edge of the panel.
  function updateHostPanelMore(): void {
    hostPanelHasMore = hasContentPastRightEdge(hostPanel)
  }

  function updateRoomToolbarMore(): void {
    roomToolbarHasMore = hasContentPastRightEdge(roomToolbar)
  }

  // The last way the user acted: a key press or a pointer (mouse, touch, pen).
  // :focus-visible cannot tell them apart, because a select or an input that is
  // focused by a pointer is :focus-visible too.
  let lastActionWasKeyboard = false
  // True while a host panel control has the focus from the keyboard.
  let hostPanelHasKeyboardFocus = $state(false)
  // True while a room toolbar control has the focus from the keyboard.
  let roomToolbarHasKeyboardFocus = $state(false)

  $effect(() => {
    const onKeyDown = (): void => {
      lastActionWasKeyboard = true
    }
    const onPointerDown = (): void => {
      lastActionWasKeyboard = false
      hostPanelHasKeyboardFocus = false
      roomToolbarHasKeyboardFocus = false
    }
    window.addEventListener('keydown', onKeyDown, true)
    window.addEventListener('pointerdown', onPointerDown, true)
    return () => {
      window.removeEventListener('keydown', onKeyDown, true)
      window.removeEventListener('pointerdown', onPointerDown, true)
    }
  })

  // Chromium does not scroll a control that is already partly visible when it gets
  // the focus, so its outline stays cut. Scroll it fully into view, but only for
  // keyboard focus: scrolling after a click would move a partly visible "Retirer"
  // away from under the pointer.
  function scrollKeyboardFocusIntoView(event: FocusEvent): void {
    const target = event.target
    if (!(target instanceof HTMLElement)) {
      return
    }
    if (!lastActionWasKeyboard) {
      return
    }
    target.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }

  // Remember whether the focus inside the host panel comes from the keyboard.
  function followHostPanelFocus(event: FocusEvent): void {
    hostPanelHasKeyboardFocus = lastActionWasKeyboard
    scrollKeyboardFocusIntoView(event)
  }

  function leaveHostPanelFocus(): void {
    hostPanelHasKeyboardFocus = false
  }

  // The same for the room toolbar: a keyboard focus hides its edge fade.
  function followRoomToolbarFocus(event: FocusEvent): void {
    roomToolbarHasKeyboardFocus = lastActionWasKeyboard
    scrollKeyboardFocusIntoView(event)
  }

  function leaveRoomToolbarFocus(): void {
    roomToolbarHasKeyboardFocus = false
  }

  // Measure again whenever the toolbar changes size or content: a resize, the
  // reveal panel coming or going, a button text that changes.
  $effect(() => {
    if (roomToolbar === null) {
      return
    }
    const stopWatching = watchListChanges(roomToolbar, updateRoomToolbarMore)
    updateRoomToolbarMore()
    return stopWatching
  })

  // Measure again whenever the panel or its content changes size.
  $effect(() => {
    if (hostPanel === null) {
      return
    }
    const observer = new ResizeObserver(updateHostPanelMore)
    observer.observe(hostPanel)
    for (const child of Array.from(hostPanel.children)) {
      observer.observe(child)
    }
    updateHostPanelMore()
    return () => observer.disconnect()
  })

  // On a small window the roster list is narrow: every remove button then shows a
  // short text instead of "Retirer" (spec 014 AC-9).
  let rosterList: HTMLUListElement | null = $state(null)
  let isRemoveCompact = $state(false)

  // Compare the width of the list with the root font size, both in CSS pixels.
  function updateRemoveForm(): void {
    if (rosterList === null) {
      return
    }
    const rootFontSize = parseFloat(getComputedStyle(document.documentElement).fontSize)
    isRemoveCompact = rosterList.clientWidth < COMPACT_REMOVE_BELOW_ROOT_FONTS * rootFontSize
  }

  // Measure again when the list changes size (a resize, a rotation) and when a
  // style or a class on <html> changes the root font.
  $effect(() => {
    if (rosterList === null) {
      return
    }
    const sizeObserver = new ResizeObserver(updateRemoveForm)
    sizeObserver.observe(rosterList)
    const rootObserver = new MutationObserver(updateRemoveForm)
    rootObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['style', 'class'],
    })
    updateRemoveForm()
    return () => {
      sizeObserver.disconnect()
      rootObserver.disconnect()
    }
  })

  // The list of the activity feed, which scrolls up to the older lines.
  let feedList: HTMLUListElement | null = $state(null)

  // A list that scrolls with nothing focusable inside is a Tab stop, so that a
  // keyboard player can scroll it with the arrow keys (spec 035 AC-12).
  $effect(() => {
    if (rosterList === null) {
      return
    }
    return followListTabStop(rosterList)
  })

  $effect(() => {
    if (feedList === null) {
      return
    }
    return followListTabStop(feedList)
  })

  let shareLink = $derived(`${location.origin}/r/${code}`)
  // True while the copy button reads "copied", after a successful copy.
  let copied = $state(false)
  const linkCopier = newLinkCopier((isCopied) => {
    copied = isCopied
  })

  // Write the link to the clipboard. Without a usable clipboard nothing changes.
  async function copyLink(): Promise<void> {
    await linkCopier.copy(shareLink)
  }

  // Leaving the page must not leave the timers to fire on a destroyed page.
  $effect(() => {
    return () => {
      linkCopier.stop()
      clearTimeout(undoMessageTimer)
      clearTimeout(pacingTimer)
    }
  })

  // "Nothing to undo" shows for UNDO_MESSAGE_MS after each refusal of the server.
  let isUndoMessageShown = $state(false)
  let undoMessageTimer: ReturnType<typeof setTimeout> | undefined
  let shownUndoRefusals = 0
  $effect(() => {
    if (session.undoRefusals === shownUndoRefusals) {
      return
    }
    shownUndoRefusals = session.undoRefusals
    isUndoMessageShown = true
    clearTimeout(undoMessageTimer)
    undoMessageTimer = setTimeout(() => {
      isUndoMessageShown = false
    }, UNDO_MESSAGE_MS)
  })

  let words = $derived(session.snapshot === null ? [] : computeWords(session.snapshot.grid))
  // A new snapshot may remove the word of the selection: then nothing is selected.
  let selection = $derived(validSelection(words, rawSelection))
  let activeWord = $derived(selectedWord(words, selection))
  let remoteSelections = $derived(remoteSelectionsOf(session.snapshot, words, session.cursors))

  // ---- The authors view (spec 019) ----

  // Off at each page load, and for this page only: the switch sends nothing.
  let isAuthorsViewOn = $state(false)
  let playerColours = $derived(colourByPlayer(session.snapshot?.players ?? []))
  // The clue bar's line naming the author of the selected letter, or null. It
  // follows the known names too: a name that arrives while the cell stays
  // selected (a player seated back, spec 032) shows at once (spec 019).
  let selectedAuthorLine = $derived(
    selectedAuthorLineOf(isAuthorsViewOn, selection, session.names),
  )

  function toggleAuthorsView(): void {
    isAuthorsViewOn = !isAuthorsViewOn
  }

  // ---- The two display switches of the grid cells (spec 042) ----

  // « Mots des autres » and « Accessibilité » start from what this browser
  // remembers, and remember each change. They send nothing.
  let isOthersTintOn = $state(readOthersTint())
  let isAccessibilityOn = $state(readAccessibility())

  function toggleOthersTint(): void {
    isOthersTintOn = !isOthersTintOn
    writeSwitch(OTHERS_TINT_KEY, isOthersTintOn)
  }

  function toggleAccessibility(): void {
    isAccessibilityOn = !isAccessibilityOn
    writeSwitch(ACCESSIBILITY_KEY, isAccessibilityOn)
  }

  // The line naming the author of the selected cell's confirmed letter, while
  // the view is on; null when it is off, when nothing is selected, or when the
  // selected cell is empty or revealed.
  function selectedAuthorLineOf(
    isViewOn: boolean,
    current: Selection | null,
    names: Map<string, string>,
  ): string | null {
    if (!isViewOn || current === null) {
      return null
    }
    const cell = letterCellAt(current.row, current.column)
    if (cell === null) {
      return null
    }
    const author = shownAuthorOf(cell)
    if (author === null) {
      return null
    }
    return authorLine(author, names)
  }

  // True while the page retries after a loss that happened with the form shown:
  // the form stays on screen until the new socket opens.
  let isFormKept = $state(false)
  let isFormShown = $derived(
    session.status === 'nickname' ||
      (session.status === 'joining' && formJoinNickname !== null) ||
      (session.status === 'connecting' && isFormKept),
  )
  // A nickname refused by the server is shown as a characters error.
  let shownError = $derived(formError ?? (session.nicknameRefused ? 'characters' : null))

  // `selection` is already null once its word is gone; this also drops the stale
  // `rawSelection`, so the old selection cannot come back with a later snapshot.
  $effect(() => {
    if (selection === null && rawSelection !== null) {
      rawSelection = null
    }
  })

  // Each flash ends FLASH_MS after it started. A flash that a newer one replaced
  // is no longer in the list, so its timer finds nothing to end.
  const scheduledFlashes = new Set<number>()
  const flashTimers = new Set<ReturnType<typeof setTimeout>>()
  $effect(() => {
    for (const flash of session.flashes) {
      if (scheduledFlashes.has(flash.id)) {
        continue
      }
      scheduledFlashes.add(flash.id)
      const timer = setTimeout(() => {
        flashTimers.delete(timer)
        scheduledFlashes.delete(flash.id)
        endFlash(session, flash.id)
      }, FLASH_MS)
      flashTimers.add(timer)
    }
  })

  // Leaving the page must not leave the flash timers to fire on a destroyed page.
  // This is a separate effect: the one above re-runs with each new flash, and its
  // cleanup would cancel the timers of the flashes still showing.
  $effect(() => {
    return () => {
      for (const timer of flashTimers) {
        clearTimeout(timer)
      }
      flashTimers.clear()
      scheduledFlashes.clear()
    }
  })

  // The feed list keeps the reader's place (spec 013 AC-7): new lines bring the
  // list to its newest line only if the list was at its end just before. The
  // lines of a catch-up are new lines too, also when they go in above the
  // others (spec 034).
  let feedPlaceBeforeNewLine: FeedPlace | null = null

  // Runs before the new lines are on the page: note where the list is.
  $effect.pre(() => {
    const changes = session.feedChanges
    if (feedList === null || changes === 0) {
      return
    }
    feedPlaceBeforeNewLine = noteFeedPlace(feedList)
  })

  // Runs once the new lines are on the page.
  $effect(() => {
    const changes = session.feedChanges
    if (feedList === null || changes === 0 || feedPlaceBeforeNewLine === null) {
      return
    }
    keepFeedPlace(feedList, feedPlaceBeforeNewLine)
    feedPlaceBeforeNewLine = null
  })

  // Each cell highlighted by a catch-up goes back to normal CATCH_UP_HIGHLIGHT_MS
  // after its highlight started (spec 034). A cell highlighted again has a new
  // id, so the timer of its old highlight finds nothing to end.
  const scheduledCaughtUp = new Set<number>()
  const caughtUpTimers = new Set<ReturnType<typeof setTimeout>>()
  $effect(() => {
    for (const cell of session.caughtUpCells) {
      if (scheduledCaughtUp.has(cell.id)) {
        continue
      }
      scheduledCaughtUp.add(cell.id)
      const timer = setTimeout(() => {
        caughtUpTimers.delete(timer)
        scheduledCaughtUp.delete(cell.id)
        endCaughtUp(session, cell.id)
      }, CATCH_UP_HIGHLIGHT_MS)
      caughtUpTimers.add(timer)
    }
  })

  // Leaving the page must not leave the highlight timers to fire on a destroyed
  // page (a separate effect, as for the flashes).
  $effect(() => {
    return () => {
      for (const timer of caughtUpTimers) {
        clearTimeout(timer)
      }
      caughtUpTimers.clear()
      scheduledCaughtUp.clear()
    }
  })

  // ---- Catching up after an absence (spec 034) ----

  // The seen seq: the seq this page last held, kept in the room record too. Until
  // the first snapshot, the one stored by the last visit on this device, read
  // when the page opens.
  let seenSeq: number | null = null
  // How many snapshots the page applied: an answer to a catch-up request is
  // applied only while no newer snapshot came.
  let snapshotCount = 0

  // Remember the page's seq each time it changes.
  function rememberSeenSeq(): void {
    if (session.seq === null || session.seq === seenSeq) {
      return
    }
    seenSeq = session.seq
    writeRoomSeenSeq(code, seenSeq)
  }

  // Ask once for what changed between the seen seq and the snapshot, and apply
  // the answer if the snapshot is still the page's latest. A failed request
  // shows nothing and is not sent again.
  async function catchUpOnReturn(snapshot: Snapshot, afterSeq: number): Promise<void> {
    const askedAt = snapshotCount
    const catchUp = await fetchCatchUp(code, {
      resume_token: snapshot.resume_token,
      after_seq: afterSeq,
      until_seq: snapshot.seq,
    })
    if (catchUp === null || askedAt !== snapshotCount) {
      return
    }
    applyCatchUp(session, catchUp)
  }

  // A feed list at its end stays at its end through a resize, a rotation or a
  // new root font, so the newest line stays in view (spec 013 AC-8).
  $effect(() => {
    if (feedList === null) {
      return
    }
    return keepFeedEndOnResize(feedList)
  })

  // A solved grid is finished on this device, when the room knows its number.
  $effect(() => {
    if (!session.solved) {
      return
    }
    const grid = readRoomGrid(code)
    if (grid !== null) {
      markFinished(grid)
    }
  })

  // Spec 029: once the grid is solved, the page asks its room's summary and
  // writes its record in this device's history. Once per page.
  let isRecordAsked = false
  $effect(() => {
    if (!session.solved || session.snapshot === null || isRecordAsked) {
      return
    }
    isRecordAsked = true
    void recordOwnRoom(code, session.snapshot.resume_token)
  })

  // Send a message when the socket is open; after a close nothing is sent.
  function send(message: object): void {
    if (socket !== null && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message))
    }
  }

  // ---- Host controls (spec 014) ----

  let isHost = $derived(
    session.snapshot !== null &&
      session.snapshot.players.some(
        (player) => player.player_id === session.snapshot?.you && player.is_host,
      ),
  )
  // The check and reveal panels are absent while the help is off (spec 025).
  let isHelpShown = $derived(
    session.snapshot !== null && session.snapshot.settings.help_mode !== 'none',
  )
  // While a vote is open, the requests that need a vote are disabled; the checks
  // of a letter or a word are not (spec 025).
  let isVoteOpen = $derived(session.snapshot !== null && session.snapshot.open_vote !== null)

  // True when every letter cell of the confirmed grid holds a letter (spec 026).
  let isGridFull = $derived(
    session.snapshot !== null &&
      session.snapshot.grid.cells.every((cell) => cell.type !== 'letter' || cell.letter !== null),
  )
  let gridStatus = $derived(session.solved ? 'solved' : isGridFull ? 'full_wrong' : null)
  // Where the status shows: in the clue bar's row on a low window, under the clue
  // bar otherwise (spec 026 AC-10).
  let isStatusInClueBar = $derived(gridStatus !== null && isLowWindow)
  let isStatusUnderClueBar = $derived(gridStatus !== null && !isLowWindow)
  let isLocked = $derived(session.snapshot !== null && session.snapshot.settings.locked)

  // The settings form shows the settings of the room; it follows each change.
  let helpModeInput = $state('free')
  let lettersInput: number | null = $state(5)
  let wordsInput: number | null = $state(1)
  $effect(() => {
    if (session.snapshot === null) {
      return
    }
    const { help_mode, letters, words } = session.snapshot.settings
    helpModeInput = help_mode
    lettersInput = letters
    wordsInput = words
  })

  // True for a whole number from 0 to 99.
  function isValidCount(value: number | null): value is number {
    return value !== null && Number.isInteger(value) && value >= 0 && value <= MAX_REVEAL_COUNT
  }

  function removePlayer(playerId: string): void {
    send({ type: 'remove_player', player_id: playerId })
  }

  function toggleLock(): void {
    send({ type: 'lock_room', locked: !isLocked })
  }

  function submitSettings(event: SubmitEvent): void {
    event.preventDefault()
    if (!isValidCount(lettersInput) || !isValidCount(wordsInput)) {
      return
    }
    send({
      type: 'change_settings',
      help_mode: helpModeInput,
      reveal_budget: { letters: lettersInput, words: wordsInput },
    })
  }

  // Check the nickname typed in the form, and join with it, in capitals, when it
  // is valid.
  function submitNickname(event: SubmitEvent): void {
    event.preventDefault()
    if (session.status !== 'nickname') {
      return
    }
    const check = checkNickname(nicknameText)
    if (!check.ok) {
      formError = check.reason
      return
    }
    formError = null
    session.nicknameRefused = false
    formJoinNickname = check.nickname
    session.status = 'joining'
    send({ type: 'join', nickname: check.nickname, resume_token: null })
  }

  // A snapshot answers a join: remember who I am, and the nickname I typed.
  function rememberJoin(snapshot: Snapshot): void {
    for (const player of snapshot.players) {
      if (player.player_id === snapshot.you) {
        writeIdentity(code, {
          player_id: snapshot.you,
          resume_token: snapshot.resume_token,
          nickname: player.nickname,
        })
      }
    }
    if (formJoinNickname !== null) {
      writeNickname(formJoinNickname)
      formJoinNickname = null
    }
  }

  // Make `next` the selection, and tell the server when it is a change.
  function select(next: Selection | null): void {
    if (next === null || sameSelection(next, selection)) {
      return
    }
    const cellChanged =
      selection === null ||
      selection.row !== next.row ||
      selection.column !== next.column ||
      selection.direction !== next.direction
    rawSelection = next
    writeRoomSelection(code, next)
    // The server only knows the cell and the direction, not the chosen word.
    if (cellChanged) {
      send({
        type: 'select_cell',
        row: next.row,
        column: next.column,
        direction: next.direction,
      })
    }
  }

  // The letter cell at a position of the snapshot, or null.
  function letterCellAt(row: number, column: number): LetterCellView | null {
    if (session.snapshot === null) {
      return null
    }
    for (const cell of session.snapshot.grid.cells) {
      if (cell.type === 'letter' && cell.row === row && cell.column === column) {
        return cell
      }
    }
    return null
  }

  // The selection moved to the cell at `index` of the selected word.
  function selectWordCell(word: Word, current: Selection, index: number): void {
    const target = word.cells[index]
    select({
      row: target.row,
      column: target.column,
      direction: current.direction,
      word: current.word,
    })
  }

  // Mark the time from the start of the page load to a grid that takes taps and
  // keys (spec 036). `tick` resolves once the DOM shows the new state, so the
  // grid of the first snapshot is on the page when the mark is set.
  async function markInteractive(): Promise<void> {
    await tick()
    performance.mark(INTERACTIVE_MARK)
  }

  // After the first snapshot, select again what this device saved, if the grid
  // still has a word there.
  function restoreSavedSelection(snapshot: Snapshot): void {
    const saved = readRoomSelection(code)
    if (saved === null) {
      return
    }
    const restored = selectionOnCell(
      computeWords(snapshot.grid),
      saved.row,
      saved.column,
      saved.direction,
    )
    select(restored)
  }

  // The place of a cell in a word (-1 when the word does not contain it).
  function indexInWord(word: Word, cell: LetterCellView): number {
    return word.cells.findIndex(
      (position) => position.row === cell.row && position.column === cell.column,
    )
  }

  // The letter cell of the selection, which the pencil and reveal controls act on.
  let selectedCell = $derived(
    selection === null ? null : letterCellAt(selection.row, selection.column),
  )

  // ---- Pencil letters (spec 020) ----

  // Off at each page load; each click of the toggle flips it.
  let isPencilMode = $state(false)

  function togglePencilMode(): void {
    isPencilMode = !isPencilMode
  }

  // The message of an edit by its kind: edit_letter or erase for 'edit',
  // pencil_edit for 'pencil', confirm_pencil for 'confirm'.
  function editMessage(
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

  // Show an edit of a cell at once, keep it pending until the server answers,
  // and send it with `baseSeq`.
  function startEdit(
    cell: LetterCellView,
    letter: string | null,
    kind: PendingEdit['kind'],
    baseSeq: number | null,
  ): void {
    addPendingEdit(session, cell.row, cell.column, letter, kind)
    sendEdit(editMessage({ row: cell.row, column: cell.column, letter, kind }, baseSeq))
  }

  // The confirm control works on the selected cell when it shows a pencil
  // letter (confirmed or pending), is not locked, and the grid is not solved.
  let isConfirmPencilDisabled = $derived(
    session.solved ||
      selectedCell === null ||
      selectedCell.locked ||
      !shownCell(selectedCell, session.pendingEdits).pencil,
  )

  // Confirm the selected cell's pencil letter. The page's seq goes in base_seq,
  // so that a letter another player changed meanwhile is refused (decision 3).
  // The selection does not move.
  function onConfirmPencil(): void {
    if (isConfirmPencilDisabled || selectedCell === null) {
      return
    }
    const shown = shownCell(selectedCell, session.pendingEdits)
    startEdit(selectedCell, shown.letter, 'confirm', session.seq)
  }

  // Type a letter on the selected cell, then move to the next unlocked cell.
  // With pencil mode on it is a pencil letter. A cell that already shows the
  // letter with the mode's pencil flag sends nothing.
  function onLetter(letter: string): void {
    if (session.solved || selection === null || activeWord === null) {
      return
    }
    const cell = letterCellAt(selection.row, selection.column)
    if (cell === null || cell.locked) {
      return
    }
    const shown = shownCell(cell, session.pendingEdits)
    const isAlreadyShown = shown.letter === letter && shown.pencil === isPencilMode
    if (!isAlreadyShown) {
      startEdit(cell, letter, isPencilMode ? 'pencil' : 'edit', null)
    }
    const here = indexInWord(activeWord, cell)
    for (let index = here + 1; index < activeWord.cells.length; index++) {
      const position = activeWord.cells[index]
      const candidate = letterCellAt(position.row, position.column)
      if (candidate !== null && !candidate.locked) {
        selectWordCell(activeWord, selection, index)
        return
      }
    }
  }

  // Clear a cell that is filled and not locked, and tell the server.
  function eraseCell(cell: LetterCellView): boolean {
    if (cell.locked || shownCell(cell, session.pendingEdits).letter === null) {
      return false
    }
    startEdit(cell, null, 'edit', null)
    return true
  }

  // Backspace: clear the selected cell, or step back and clear the previous one.
  function onErase(): void {
    if (session.solved || selection === null || activeWord === null) {
      return
    }
    const cell = letterCellAt(selection.row, selection.column)
    if (cell === null || eraseCell(cell)) {
      return
    }
    const here = indexInWord(activeWord, cell)
    if (here <= 0) {
      return
    }
    selectWordCell(activeWord, selection, here - 1)
    const previous = activeWord.cells[here - 1]
    const previousCell = letterCellAt(previous.row, previous.column)
    if (previousCell !== null) {
      eraseCell(previousCell)
    }
  }

  // Ask the server to undo my last edit. It arrives after any edit already sent.
  function onUndo(): void {
    if (session.solved) {
      return
    }
    send({ type: 'undo' })
  }

  // Ask the server to check the selected letter, the selected word or the grid.
  function onCheck(target: object): void {
    if (session.solved) {
      return
    }
    send({ type: 'check', target })
  }

  function onCheckLetter(): void {
    if (selection !== null) {
      onCheck({ scope: 'letter', row: selection.row, column: selection.column })
    }
  }

  function onCheckWord(): void {
    if (activeWord !== null) {
      onCheck({
        scope: 'word',
        row: activeWord.clueRow,
        column: activeWord.clueColumn,
        clue_index: activeWord.clueIndex,
      })
    }
  }

  // ---- Reveal controls (spec 024) ----

  // What is left of the room's budget.
  let lettersLeft = $derived(session.snapshot === null ? 0 : session.snapshot.reveal_budget.letters)
  let wordsLeft = $derived(session.snapshot === null ? 0 : session.snapshot.reveal_budget.words)

  // True when every cell of the word is locked: nothing is left to reveal there.
  function isWordLocked(word: Word): boolean {
    for (const position of word.cells) {
      const cell = letterCellAt(position.row, position.column)
      if (cell !== null && !cell.locked) {
        return false
      }
    }
    return true
  }

  let isRevealLetterDisabled = $derived(
    session.solved ||
      isVoteOpen ||
      selectedCell === null ||
      selectedCell.locked ||
      lettersLeft === 0,
  )
  let isRevealWordDisabled = $derived(
    session.solved ||
      isVoteOpen ||
      activeWord === null ||
      isWordLocked(activeWord) ||
      wordsLeft === 0,
  )

  // A spent budget replaces the count with the reason the button is disabled.
  let revealLetterText = $derived(
    lettersLeft === 0 ? t('reveal.letter_none') : t('reveal.letter', { count: lettersLeft }),
  )
  let revealLetterLabel = $derived(
    lettersLeft === 0
      ? t('reveal.letter_none_label')
      : t('reveal.letter_label', { count: lettersLeft }),
  )
  let revealWordText = $derived(
    wordsLeft === 0 ? t('reveal.word_none') : t('reveal.word', { count: wordsLeft }),
  )
  let revealWordLabel = $derived(
    wordsLeft === 0 ? t('reveal.word_none_label') : t('reveal.word_label', { count: wordsLeft }),
  )

  // Ask the server to reveal the selected cell. The letter comes back in a
  // cell_locked event: the page never guesses it.
  function onRevealLetter(): void {
    if (isRevealLetterDisabled || selection === null) {
      return
    }
    send({
      type: 'reveal',
      target: { scope: 'letter', row: selection.row, column: selection.column },
    })
  }

  // Ask the server to reveal the selected word.
  function onRevealWord(): void {
    if (isRevealWordDisabled || activeWord === null) {
      return
    }
    send({
      type: 'reveal',
      target: {
        scope: 'word',
        row: activeWord.clueRow,
        column: activeWord.clueColumn,
        clue_index: activeWord.clueIndex,
      },
    })
  }

  // ---- The clue flag (spec 021) ----

  // The kept flags, and what the marker of each flagged clue shows.
  let keptFlags = $derived(session.snapshot === null ? [] : session.snapshot.flags)
  let clueFlags = $derived(clueFlagMarkers(keptFlags, session.snapshot?.players ?? []))
  // My kept flag: the flag whose player_id is `you`.
  let myFlag = $derived(session.snapshot === null ? null : flagOf(keptFlags, session.snapshot.you))
  // Pressed while my flag is on the selected word's clue.
  let isFlagPressed = $derived(
    activeWord !== null && myFlag !== null && isClueOfWord(myFlag, activeWord),
  )
  let isFlagDisabled = $derived(
    activeWord === null || (isWordFullShown(activeWord) && !isFlagPressed),
  )

  // True when every cell of the word shows a letter, pending edits included.
  function isWordFullShown(word: Word): boolean {
    for (const position of word.cells) {
      const cell = letterCellAt(position.row, position.column)
      if (cell === null || shownCell(cell, session.pendingEdits).letter === null) {
        return false
      }
    }
    return true
  }

  // Flag the selected word's clue, or remove my flag from it. The page makes no
  // guess: the button and the marker follow the server's flag_changed.
  function onFlag(): void {
    if (isFlagDisabled || activeWord === null) {
      return
    }
    if (isFlagPressed) {
      send({ type: 'flag', clue: null })
      return
    }
    send({
      type: 'flag',
      clue: {
        row: activeWord.clueRow,
        column: activeWord.clueColumn,
        clue_index: activeWord.clueIndex,
      },
    })
  }

  // ---- Chat and reactions (spec 022) ----

  // The chat panel and the reaction picker are drawn over the page, just below
  // the header, so opening them moves nothing. `popoverTop` is that place, from
  // the top of the page.
  let roomMain: HTMLElement | null = $state(null)
  let roomHeader: HTMLElement | null = $state(null)
  let popoverTop = $state(0)
  let isPopoverSideBySide = $state(true)

  function updatePopoverPlace(): void {
    if (roomMain === null || roomHeader === null) {
      return
    }
    const mainBox = roomMain.getBoundingClientRect()
    const headerBox = roomHeader.getBoundingClientRect()
    popoverTop = headerBox.bottom - mainBox.top + POPOVER_GAP_PX
    const rootFontSize = parseFloat(getComputedStyle(document.documentElement).fontSize)
    isPopoverSideBySide = roomMain.clientWidth >= SIDE_BY_SIDE_MIN_ROOT_FONTS * rootFontSize
  }

  // Measure again when the window or the header changes size (a resize, a
  // rotation, a new root font, a toolbar that wraps).
  $effect(() => {
    if (roomMain === null || roomHeader === null) {
      return
    }
    const observer = new ResizeObserver(updatePopoverPlace)
    observer.observe(roomMain)
    observer.observe(roomHeader)
    updatePopoverPlace()
    return () => observer.disconnect()
  })

  let you = $derived(session.snapshot === null ? '' : session.snapshot.you)
  // True while the host muted my chat and my reactions.
  let isMuted = $derived(
    session.snapshot !== null &&
      session.snapshot.players.some((player) => player.player_id === you && player.muted),
  )

  // Pacing: the page sends at most 5 chat messages, and 5 reactions, in any
  // 12 seconds. `pacingNow` is read again each time a send stops counting.
  let chatSendTimes: number[] = $state([])
  let reactionSendTimes: number[] = $state([])
  let pacingNow = $state(performance.now())
  let pacingTimer: ReturnType<typeof setTimeout> | undefined
  let isChatPaced = $derived(isPaced(chatSendTimes, pacingNow))
  let isReactionPaced = $derived(isPaced(reactionSendTimes, pacingNow))

  // Read the clock, forget the sends that no longer count, and come back when
  // the next one stops counting.
  function refreshPacing(): void {
    const now = performance.now()
    pacingNow = now
    chatSendTimes = sendsInWindow(chatSendTimes, now)
    reactionSendTimes = sendsInWindow(reactionSendTimes, now)
    clearTimeout(pacingTimer)
    pacingTimer = undefined
    const delay = msUntilNextExpiry([...chatSendTimes, ...reactionSendTimes], now)
    if (delay !== null) {
      pacingTimer = setTimeout(refreshPacing, delay)
    }
  }

  // ---- The end-of-game recap (spec 028) ----

  // The dialog is on the page only while it is open, so each opening fetches it.
  let isRecapOpen = $state(false)

  // Spec 033: the answer of GET /api/account, asked once when the page loads.
  // Null while it has not answered 200 (accounts off, or a failed request): the
  // page then shows no account control.
  let accountStatus: AccountStatus | null = $state(null)
  let accountOpenButton: HTMLButtonElement | null = $state(null)
  let accountDialog: AccountDialog | null = $state(null)
  // Whether this page load sent its one PUT /api/account/rooms.
  let isRoomLinked = false

  onMount(() => {
    void fetchAccountStatus().then((status) => {
      accountStatus = status
    })
  })

  // Once the page has its first snapshot and knows it is signed in, it links its
  // player of the room to the account, once (spec 033).
  $effect(() => {
    if (isRoomLinked || accountStatus === null || !accountStatus.signed_in) {
      return
    }
    if (session.snapshot === null) {
      return
    }
    isRoomLinked = true
    void linkRoom({ code, resume_token: session.snapshot.resume_token })
  })
  let recapOpenButton: HTMLButtonElement | null = $state(null)

  // Escape or the close button closed the dialog: the focus goes back to the
  // button that opens it.
  function closeRecap(): void {
    isRecapOpen = false
    recapOpenButton?.focus()
  }

  // ---- The chat panel ----

  let isChatOpen = $state(false)
  let chatText = $state('')
  let chatToggle: HTMLButtonElement | null = $state(null)
  // Lines up to this seq are read: the seq of the page's first snapshot, then
  // the seq of the newest line while the panel is open. A reconnection keeps it,
  // so the lines that came meanwhile count as unread. null before the first
  // snapshot.
  let lastSeenChatSeq: number | null = $state(null)

  let chatHistory = $derived(session.snapshot === null ? [] : session.snapshot.chat)
  let unreadLines = $derived(
    isChatOpen || lastSeenChatSeq === null ? 0 : unreadCount(chatHistory, lastSeenChatSeq, you),
  )
  // While the panel is open, every line of the history is read.
  $effect(() => {
    if (!isChatOpen || chatHistory.length === 0) {
      return
    }
    const newestSeq = chatHistory[chatHistory.length - 1].seq
    if (lastSeenChatSeq === null || newestSeq > lastSeenChatSeq) {
      lastSeenChatSeq = newestSeq
    }
  })

  function toggleChat(): void {
    if (isChatOpen) {
      closeChat()
      return
    }
    isChatOpen = true
  }

  function closeChat(): void {
    isChatOpen = false
    chatToggle?.focus()
  }

  // Send a message; the line shows when the server's chat_message comes back:
  // no local echo.
  function sendChat(text: string): void {
    send({ type: 'chat', text })
    chatSendTimes = [...chatSendTimes, performance.now()]
    refreshPacing()
  }

  // The host mutes or unmutes a player; the button follows the server's
  // player_muted.
  function toggleMute(playerId: string, isPlayerMuted: boolean): void {
    send({ type: 'mute_player', player_id: playerId, muted: !isPlayerMuted })
  }

  // ---- The reaction button and picker ----

  let isPickerOpen = $state(false)
  let reactButton: HTMLButtonElement | null = $state(null)
  let isReactDisabled = $derived(activeWord === null || isMuted)

  function toggleReactionPicker(): void {
    if (isPickerOpen) {
      closeReactionPicker()
      return
    }
    isPickerOpen = true
  }

  function closeReactionPicker(): void {
    isPickerOpen = false
    reactButton?.focus()
  }

  // Close the picker and leave the focus where it is.
  function dismissReactionPicker(): void {
    isPickerOpen = false
  }

  // React on the selected word's clue.
  function sendReaction(reaction: ReactionValue): void {
    if (activeWord === null || isReactionPaced) {
      return
    }
    send({
      type: 'react',
      clue: {
        row: activeWord.clueRow,
        column: activeWord.clueColumn,
        clue_index: activeWord.clueIndex,
      },
      reaction,
    })
    reactionSendTimes = [...reactionSendTimes, performance.now()]
    refreshPacing()
  }

  // What each clue shows of the reactions. Each reaction ends REACTION_MS after
  // it arrived; one that a newer reaction replaced is no longer in the list, so
  // its timer finds nothing to end.
  let clueReactions = $derived(clueReactionMarkers(session.reactions, session.names))
  const scheduledReactions = new Set<number>()
  const reactionTimers = new Set<ReturnType<typeof setTimeout>>()
  $effect(() => {
    for (const shown of session.reactions) {
      if (scheduledReactions.has(shown.id)) {
        continue
      }
      scheduledReactions.add(shown.id)
      const timer = setTimeout(() => {
        reactionTimers.delete(timer)
        scheduledReactions.delete(shown.id)
        endReaction(session, shown.id)
      }, REACTION_MS)
      reactionTimers.add(timer)
    }
  })

  // A separate effect, as for the flashes: the one above re-runs with each new
  // reaction, and its cleanup would cancel the timers of those still showing.
  $effect(() => {
    return () => {
      for (const timer of reactionTimers) {
        clearTimeout(timer)
      }
      reactionTimers.clear()
      scheduledReactions.clear()
    }
  })

  // ---- Votes (spec 025) ----

  let openVote = $derived(session.snapshot === null ? null : session.snapshot.open_vote)
  // The banner shows the open vote, or for VOTE_RESULT_MS how the last one
  // ended; never once the grid is solved.
  let isVoteBannerShown = $derived(
    !session.solved && (openVote !== null || session.closedVote !== null),
  )
  let isMyRequest = $derived(
    openVote !== null && session.snapshot !== null && openVote.player_id === session.snapshot.you,
  )
  let hasVoted = $derived(openVote !== null && session.votedIds.includes(openVote.vote_id))
  let voteQuestionText = $derived(openVote === null ? '' : voteQuestion(openVote))
  let voteResultText = $derived(
    session.closedVote === null ? '' : t(`vote.result.${session.closedVote.outcome}`),
  )
  // What a screen reader hears: the question when a vote opens, the result
  // when it closes.
  let voteAnnouncement = $derived(openVote !== null ? voteQuestionText : voteResultText)

  // The question of a vote, with the requester's nickname (spec 013's known
  // names). The page inserts it as text.
  function voteQuestion(vote: VoteView): string {
    return t(`vote.question.${vote.kind}`, { name: nameOf(session.names, vote.player_id) })
  }

  // The ballot buttons are disabled while the page is not joined: a ballot sent
  // then would be dropped while the page showed it as cast (decision 18).
  let isVotingOffline = $derived(session.status !== 'joined')

  // Send my ballot on the open vote, once, then give the focus to the status
  // that replaces the buttons, so it never falls back to the page (decision 19).
  function castVote(yes: boolean): void {
    if (openVote === null || isVotingOffline || session.votedIds.includes(openVote.vote_id)) {
      return
    }
    send({ type: 'vote', vote_id: openVote.vote_id, yes })
    session.votedIds.push(openVote.vote_id)
    void focusVoteStatus()
  }

  // `tick` resolves once the DOM shows `vote-status` instead of the buttons.
  async function focusVoteStatus(): Promise<void> {
    await tick()
    voteStatus?.focus()
  }

  // ---- Focus when the banner changes (decision 19) ----

  let voteBanner: HTMLElement | null = $state(null)
  let voteStatus: HTMLElement | null = $state(null)

  // What the banner holds: nothing, the question of one vote, or a result.
  let bannerContent = $derived(
    !isVoteBannerShown ? 'none' : openVote !== null ? `vote-${openVote.vote_id}` : 'result',
  )
  let lastBannerContent = 'none'

  // Runs before the page changes the banner: when the focus is inside it, the
  // vote closed or the banner leaves, and the focus goes to the grid instead of
  // falling back to the page.
  $effect.pre(() => {
    const content = bannerContent
    if (content === lastBannerContent) {
      return
    }
    lastBannerContent = content
    const focused = document.activeElement
    if (voteBanner !== null && focused !== null && voteBanner.contains(focused)) {
      void focusGridAfterUpdate()
    }
  })

  async function focusGridAfterUpdate(): Promise<void> {
    await tick()
    gridViewport?.focusGrid()
  }

  // The result of a closed vote shows for VOTE_RESULT_MS. A new vote, or a
  // newer result, cancels the timer of the old one.
  $effect(() => {
    if (session.closedVote === null) {
      return
    }
    const timer = setTimeout(() => {
      session.closedVote = null
    }, VOTE_RESULT_MS)
    return () => clearTimeout(timer)
  })

  function onCellTap(row: number, column: number): void {
    select(selectionAfterCellTap(words, selection, row, column))
  }

  function onClueTap(word: Word): void {
    if (session.snapshot !== null) {
      select(selectionAfterClueTap(shownGrid(session.snapshot.grid, session.pendingEdits), word))
    }
  }

  function roomSocketUrl(roomCode: string): string {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${scheme}://${location.host}/api/rooms/${roomCode}/ws`
  }

  // ---- The connection: heartbeat, loss detection and reconnection (spec 017) ----

  // The next delay of the reconnection is `reconnectDelay(reconnectAttempt)`.
  let reconnectAttempt = 0
  let pingTimer: ReturnType<typeof setInterval> | undefined
  let silenceTimer: ReturnType<typeof setTimeout> | undefined
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined

  function stopHeartbeat(): void {
    clearInterval(pingTimer)
    clearTimeout(silenceTimer)
    pingTimer = undefined
    silenceTimer = undefined
  }

  function stopReconnectTimer(): void {
    clearTimeout(reconnectTimer)
    reconnectTimer = undefined
  }

  // Edits wait here while the socket has no snapshot yet, and are then sent one
  // every EDIT_SEND_INTERVAL_MS (spec 017 AC-5), oldest first.
  let isSynced = false
  let editQueue: object[] = []
  let editTimer: ReturnType<typeof setInterval> | undefined

  function stopEditQueue(): void {
    clearInterval(editTimer)
    editTimer = undefined
    editQueue = []
    isSynced = false
  }

  function sendNextQueuedEdit(): void {
    const next = editQueue.shift()
    if (next === undefined) {
      clearInterval(editTimer)
      editTimer = undefined
      return
    }
    send(next)
  }

  // Send an edit now, or behind the edits still waiting. Before the snapshot of
  // the socket nothing is sent: the edit is pending and is resent with the others.
  function sendEdit(message: object): void {
    if (!isSynced) {
      return
    }
    if (editTimer === undefined) {
      send(message)
      return
    }
    editQueue.push(message)
  }

  // Stop listening to a socket and close it.
  function dropSocket(dropped: WebSocket): void {
    if (socket === dropped) {
      stopEditQueue()
    }
    dropped.onopen = null
    dropped.onmessage = null
    dropped.onclose = null
    dropped.onerror = null
    dropped.close()
    if (socket === dropped) {
      socket = null
    }
  }

  // Any frame from the server shows the connection is alive: the silence count
  // starts again.
  function restartSilenceTimer(opened: WebSocket): void {
    clearTimeout(silenceTimer)
    silenceTimer = setTimeout(() => connectionSilent(opened), SILENCE_LIMIT_MS)
  }

  function startHeartbeat(opened: WebSocket): void {
    stopHeartbeat()
    pingTimer = setInterval(() => send({ type: 'ping' }), PING_INTERVAL_MS)
    restartSilenceTimer(opened)
  }

  // A loss before the first snapshot keeps the nickname form on screen when it was
  // shown, or when a join sent from it is lost (the new socket shows it again).
  function keepFormAfterLoss(): void {
    const wasFormShown = isFormShown
    if (session.snapshot === null && wasFormShown) {
      isFormKept = true
    }
    formJoinNickname = null
  }

  // Nothing came from the server for too long: this is a loss at once. The
  // socket is detached, so its late frames and its close event change nothing.
  function connectionSilent(silent: WebSocket): void {
    connectionLost(silent)
  }

  // The socket is lost: show it, then try again after the next delay.
  function connectionLost(lost: WebSocket): void {
    if (lost !== socket) {
      return
    }
    stopHeartbeat()
    dropSocket(lost)
    keepFormAfterLoss()
    session.status = statusAfterLoss(session)
    const delay = reconnectDelay(reconnectAttempt)
    reconnectAttempt += 1
    stopReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = undefined
      openSocket()
    }, delay)
  }

  // The socket closed for good: no more tries.
  function connectionEnded(ended: WebSocket, closeCode: number): void {
    stopHeartbeat()
    stopReconnectTimer()
    dropSocket(ended)
    session.status = statusAfterFinalClose(closeCode, session.status)
  }

  // The browser has a network again: do not wait for the next delay.
  function onBrowserOnline(): void {
    if (reconnectTimer !== undefined) {
      stopReconnectTimer()
      openSocket()
      return
    }
    // A socket still connecting may never open on a dead network: replace it.
    if (socket !== null && socket.readyState === WebSocket.CONNECTING) {
      stopHeartbeat()
      dropSocket(socket)
      openSocket()
    }
  }

  // Send my pending edits again, oldest first, each as the message of its kind
  // and with the base_seq it had. They are paced, the first one at once, then
  // one every EDIT_SEND_INTERVAL_MS.
  function resendPendingEdits(): void {
    stopEditQueue()
    isSynced = true
    for (const edit of session.pendingEdits) {
      editQueue.push(editMessage(edit, edit.baseSeq))
    }
    editTimer = setInterval(sendNextQueuedEdit, EDIT_SEND_INTERVAL_MS)
    sendNextQueuedEdit()
  }

  // The first message of a socket: the join of the stored identity, or the form.
  function joinOnOpen(opened: WebSocket): void {
    const plan = planAutomaticJoin(code, t('room.default_nickname'))
    isFormKept = false
    if (plan === null) {
      session.status = 'nickname'
      return
    }
    if (session.snapshot === null) {
      session.status = 'joining'
    }
    opened.send(JSON.stringify({ type: 'join', ...plan }))
  }

  function onSocketMessage(opened: WebSocket, event: MessageEvent): void {
    restartSilenceTimer(opened)
    if (typeof event.data !== 'string') {
      return
    }
    const snapshotBefore = session.snapshot
    const seenSeqBefore = seenSeq
    receiveFrame(session, event.data)
    if (session.snapshot !== null && session.snapshot !== snapshotBefore) {
      snapshotCount += 1
      // A return: a snapshot past the seen seq the page had when it arrived. A
      // first visit on this device has no seen seq, so no return.
      if (seenSeqBefore !== null && session.snapshot.seq > seenSeqBefore) {
        void catchUpOnReturn(session.snapshot, seenSeqBefore)
      }
      rememberJoin(session.snapshot)
      // Only the first snapshot of the page: a reconnection keeps the old
      // snapshot until the new one arrives, so it sets no second mark.
      if (snapshotBefore === null) {
        restoreSavedSelection(session.snapshot)
        void markInteractive()
        // The history of the first snapshot is not unread (spec 022).
        lastSeenChatSeq = session.snapshot.seq
      }
      reconnectAttempt = 0
      resendPendingEdits()
    }
    if (session.status === 'nickname') {
      formJoinNickname = null
    }
    rememberSeenSeq()
  }

  function openSocket(): void {
    const opened = new WebSocket(roomSocketUrl(code))
    socket = opened

    opened.onopen = () => {
      startHeartbeat(opened)
      joinOnOpen(opened)
    }
    opened.onmessage = (event: MessageEvent) => onSocketMessage(opened, event)
    opened.onclose = (event: CloseEvent) => {
      if (isFinalClose(session, event.code)) {
        connectionEnded(opened, event.code)
      } else {
        connectionLost(opened)
      }
    }
  }

  $effect(() => {
    seenSeq = readRoomSeenSeq(code)
    openSocket()
    window.addEventListener('online', onBrowserOnline)

    // Leaving the page closes the socket; the handlers must not react to it.
    return () => {
      window.removeEventListener('online', onBrowserOnline)
      stopHeartbeat()
      stopReconnectTimer()
      if (socket !== null) {
        dropSocket(socket)
      }
    }
  })
</script>

<main
  bind:this={roomMain}
  style:--popover-top={`${popoverTop}px`}
  data-testid="room-page"
  data-room-code={code}
  data-status={session.status}
  data-you={session.snapshot === null ? '' : session.snapshot.you}
  data-seq={session.seq === null ? '' : String(session.seq)}
  data-catch-up={session.catchUpLabel}
  data-solved={String(session.solved)}
  data-pending={String(session.pending.length)}
  data-grid={gridLabel(session)}
>
  <header class="room-header" bind:this={roomHeader}>
    <h1>{t('room.heading', { code })}</h1>
    <p data-testid="room-status">{t(`room.status.${session.status}`)}</p>
    {#if session.snapshot !== null}
      <div class="share-panel" data-testid="share-panel">
        <span id="share-label" class="share-label">{t('room.share.label')}</span>
        <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
        <a
          data-testid="share-link"
          href={shareLink}
          tabindex="0"
          aria-describedby="share-label"
          >{shareLink}</a
        >
        <button type="button" data-testid="copy-link" onclick={copyLink}
          >{copied ? t('room.share.copied') : t('room.share.copy')}</button
        >
      </div>
      <div
        class="room-toolbar"
        data-testid="room-toolbar"
        bind:this={roomToolbar}
        onscroll={updateRoomToolbarMore}
        onfocusin={followRoomToolbarFocus}
        onfocusout={leaveRoomToolbarFocus}
        class:keyboard-focus={roomToolbarHasKeyboardFocus}
      >
        <!-- The shared timer and its toggle come first, so that the time shows
             before any sideways scroll on a small window (spec 027). -->
        <RoomTimer
          baseMs={session.timerBaseMs}
          isRunning={session.timerRunning}
          anchor={session.timerAnchor}
        />
        <!-- Next, so its unread count shows before any sideways scroll on a small
             window (spec 022). The count has a slot of its own width, so the button
             keeps its size when the count goes. -->
        <button
          type="button"
          class="chat-toggle"
          data-testid="chat-toggle"
          aria-expanded={isChatOpen}
          aria-controls="chat-panel"
          aria-label={chatToggleLabel(unreadLines)}
          bind:this={chatToggle}
          onclick={toggleChat}
          >{t('chat.toggle')}<span class="chat-unread-slot"
            >{#if unreadLines > 0}<span
                class="chat-unread"
                data-testid="chat-unread"
                aria-hidden="true">{unreadBadgeText(unreadLines)}</span
              >{/if}</span
          ></button
        >
        {#if session.solved}
          <button
            type="button"
            class="recap-open"
            data-testid="recap-open"
            bind:this={recapOpenButton}
            onclick={() => (isRecapOpen = true)}>{t('recap.open')}</button
          >
        {/if}
        <div class="undo-panel">
          <button type="button" data-testid="undo-button" disabled={session.solved} onclick={onUndo}
            >{t('room.undo')}</button>
          {#if isUndoMessageShown}
            <span data-testid="undo-message" role="status">{t('undo.nothing')}</span>
          {/if}
        </div>
        <div class="pencil-panel">
          <button
            type="button"
            class="pencil-toggle"
            data-testid="pencil-toggle"
            aria-pressed={isPencilMode}
            disabled={session.solved}
            onclick={togglePencilMode}>{t('pencil.toggle')}</button
          >
          <button
            type="button"
            data-testid="confirm-pencil"
            aria-label={t('pencil.confirm_label')}
            disabled={isConfirmPencilDisabled}
            onclick={onConfirmPencil}>{t('pencil.confirm')}</button
          >
        </div>
        {#if isHelpShown}
          <div
            class="check-panel"
            data-testid="check-panel"
            role="group"
            aria-label={t('check.label')}
          >
            <button
              type="button"
              data-testid="check-letter"
              aria-label={t('check.letter_label')}
              disabled={session.solved || selection === null}
              onclick={onCheckLetter}>{t('check.letter')}</button
            >
            <button
              type="button"
              data-testid="check-word"
              aria-label={t('check.word_label')}
              disabled={session.solved || activeWord === null}
              onclick={onCheckWord}>{t('check.word')}</button
            >
            <button
              type="button"
              data-testid="check-grid"
              aria-label={t('check.grid_label')}
              disabled={session.solved || isVoteOpen}
              onclick={() => onCheck({ scope: 'grid' })}>{t('check.grid')}</button
            >
          </div>
          <div
            class="reveal-panel"
            data-testid="reveal-panel"
            role="group"
            aria-label={t('reveal.label')}
          >
            <button
              type="button"
              data-testid="reveal-letter"
              aria-label={revealLetterLabel}
              disabled={isRevealLetterDisabled}
              onclick={onRevealLetter}>{revealLetterText}</button
            >
            <button
              type="button"
              data-testid="reveal-word"
              aria-label={revealWordLabel}
              disabled={isRevealWordDisabled}
              onclick={onRevealWord}>{revealWordText}</button
            >
          </div>
        {/if}
        <button
          type="button"
          class="flag-button"
          data-testid="flag-button"
          aria-label={t('flag.button_label')}
          aria-pressed={isFlagPressed}
          disabled={isFlagDisabled}
          onclick={onFlag}>{t('flag.button')}</button
        >
        <button
          type="button"
          class="react-button"
          data-testid="react-button"
          aria-label={t('reaction.button_label')}
          aria-expanded={isPickerOpen}
          aria-controls="reaction-picker"
          disabled={isReactDisabled}
          bind:this={reactButton}
          onclick={toggleReactionPicker}>{t('reaction.button')}</button
        >
        <button
          type="button"
          class="authors-switch"
          data-testid="authors-switch"
          aria-pressed={isAuthorsViewOn}
          onclick={toggleAuthorsView}>{t('authors.switch')}</button
        >
        <!-- The display switches of the grid cells, until the Menu holds them
             (spec 042, spec 043). -->
        <button
          type="button"
          class="others-tint-switch"
          data-testid="others-tint-switch"
          aria-pressed={isOthersTintOn}
          onclick={toggleOthersTint}>{t('others_tint.switch')}</button
        >
        <button
          type="button"
          class="access-switch"
          data-testid="access-switch"
          aria-pressed={isAccessibilityOn}
          onclick={toggleAccessibility}>{t('access.switch')}</button
        >
        <!-- The last button of the toolbar, while accounts are on (spec 033). -->
        {#if accountStatus !== null}
          <button
            type="button"
            class="account-open"
            data-testid="account-open"
            bind:this={accountOpenButton}
            onclick={() => accountDialog?.open()}>{t('account.open')}</button
          >
        {/if}
        <span
          class="room-toolbar-more"
          class:shown={roomToolbarHasMore}
          data-testid="room-toolbar-more"
          aria-hidden="true"
        ></span>
      </div>
    {/if}
  </header>
  <!-- The reaction picker and the chat panel come right after the toolbar in
       document order, outside it (its sideways scrolling would clip them), and
       are drawn over the page (spec 022). -->
  {#if session.snapshot !== null && isPickerOpen}
    <ReactionPicker
      isPaced={isReactionPaced}
      isButtonDisabled={isReactDisabled}
      onPick={sendReaction}
      onClose={closeReactionPicker}
      onDismiss={dismissReactionPicker}
      onFocusButton={() => reactButton?.focus()}
      onFocusGrid={() => gridViewport?.focusGrid()}
    />
  {/if}
  {#if session.snapshot !== null && isChatOpen}
    <ChatPanel
      history={chatHistory}
      players={session.snapshot.players}
      names={session.names}
      {you}
      {isHost}
      {isMuted}
      isPaced={isChatPaced}
      isJoined={session.status === 'joined'}
      isBelowPicker={!isPopoverSideBySide}
      bind:text={chatText}
      onSend={sendChat}
      onMute={toggleMute}
      onClose={closeChat}
      onFocusToggle={() => chatToggle?.focus()}
    />
  {/if}
  {#if isRecapOpen}
    <RecapDialog {code} {you} {playerColours} onClose={closeRecap} />
  {/if}
  <!-- After the toolbar in document order: its sideways scrolling would clip it
       (spec 033). -->
  {#if session.snapshot !== null && accountStatus !== null}
    <AccountDialog
      bind:this={accountDialog}
      status={accountStatus}
      room={{ code, resume_token: session.snapshot.resume_token }}
      onClosed={() => accountOpenButton?.focus()}
    />
  {/if}
  {#if session.status === 'reconnecting'}
    <p class="connection-banner" data-testid="connection-banner" role="status">
      {t('room.banner.offline')}
    </p>
  {/if}
  {#if isFormShown}
    <form data-testid="nickname-form" class="nickname-form" onsubmit={submitNickname}>
      <h2>{t('join.heading')}</h2>
      <label for="nickname-input">{t('join.nickname_label')}</label>
      <input
        id="nickname-input"
        data-testid="nickname-input"
        type="text"
        autocomplete="nickname"
        placeholder={t('room.default_nickname')}
        bind:value={nicknameText}
      />
      {#if shownError !== null}
        <p class="nickname-error" data-testid="nickname-error" role="alert">
          {shownError === 'length' ? t('join.error.length') : t('join.error.characters')}
        </p>
      {/if}
      <button type="submit" data-testid="nickname-submit" disabled={session.status === 'joining'}
        >{t('join.submit')}</button
      >
    </form>
  {/if}
  {#if session.snapshot !== null}
    <div class="presence">
    <section class="roster" data-testid="roster">
      <h2 id="roster-heading">{t('roster.heading')}</h2>
      <!-- The explicit role: WebKit does not expose a list without bullets as a
           list. The tabindex is set from the script (spec 035 AC-12). -->
      <ul
        bind:this={rosterList}
        role="list"
        aria-labelledby="roster-heading"
        onfocusin={scrollKeyboardFocusIntoView}
      >
        {#each session.snapshot.players as player (player.player_id)}
          {@const isYou = player.player_id === session.snapshot.you}
          <li
            data-testid="roster-player"
            data-player-id={player.player_id}
            data-colour={String(player.colour)}
            data-state={player.state}
            data-you={String(isYou)}
            data-host={String(player.is_host)}
          >
            <span
              class="roster-colour"
              data-testid="roster-colour"
              data-colour={String(player.colour)}
              style:background={isAccessibilityOn ? null : `var(--player-colour-${player.colour})`}
              >{#if isAccessibilityOn}<PlayerIcon colour={player.colour} side="12px" />{/if}</span
            >
            <span class="roster-nickname" data-testid="roster-nickname"
              >{displayNickname(player.nickname)}</span
            >
            <span class="roster-state" data-testid="roster-state"
              >{t(`presence.${player.state}`)}</span
            >
            {#if player.is_host}
              <span class="roster-host">{t('roster.host')}</span>
            {/if}
            {#if isYou}
              <span class="roster-you">{t('roster.you')}</span>
            {:else if isHost}
              <button
                type="button"
                class="remove-player"
                class:compact={isRemoveCompact}
                data-testid="remove-player"
                aria-label={t('host.remove_label', { name: displayNickname(player.nickname) })}
                onclick={() => removePlayer(player.player_id)}
                >{isRemoveCompact ? t('host.remove_short') : t('host.remove')}</button
              >
            {/if}
          </li>
        {/each}
      </ul>
    </section>
    <section class="feed" data-testid="activity-feed">
      <h2 id="feed-heading">{t('feed.heading')}</h2>
      <ul bind:this={feedList} role="list" aria-labelledby="feed-heading">
        {#each session.feed as item (item.id)}
          <li data-testid="feed-item" data-kind={item.kind} data-seq={String(item.seq)}>
            {item.text}
          </li>
        {/each}
      </ul>
    </section>
    {#if isHost}
      <div
        class="host-panel"
        data-testid="host-panel"
        bind:this={hostPanel}
        onscroll={updateHostPanelMore}
        onfocusin={followHostPanelFocus}
        onfocusout={leaveHostPanelFocus}
        class:keyboard-focus={hostPanelHasKeyboardFocus}
      >
        <strong class="host-heading">{t('settings.heading')}</strong>
        <button type="button" data-testid="lock-room" aria-pressed={isLocked} onclick={toggleLock}
          >{isLocked ? t('host.unlock') : t('host.lock')}</button
        >
        <form class="settings-form" data-testid="settings-form" onsubmit={submitSettings}>
          <label>
            {t('settings.help_mode_label')}
            <select data-testid="help-mode-select" bind:value={helpModeInput}>
              <option value="free">{t('settings.help_mode.free')}</option>
              <option value="vote">{t('settings.help_mode.vote')}</option>
              <option value="none">{t('settings.help_mode.none')}</option>
            </select>
          </label>
          <label>
            {t('settings.reveal_letters_label')}
            <input
              type="number"
              data-testid="reveal-letters-input"
              min="0"
              max="99"
              step="1"
              bind:value={lettersInput}
            />
          </label>
          <label>
            {t('settings.reveal_words_label')}
            <input
              type="number"
              data-testid="reveal-words-input"
              min="0"
              max="99"
              step="1"
              bind:value={wordsInput}
            />
          </label>
          <button type="submit" data-testid="settings-save">{t('settings.save')}</button>
        </form>
        <span
          class="host-panel-more"
          class:shown={hostPanelHasMore}
          data-testid="host-panel-more"
          aria-hidden="true"
        ></span>
      </div>
    {/if}
    </div>
    <!-- The vote banner is laid over the top of the grid viewport, so showing it
         changes no layout; it comes before the grid in document order, since
         nothing focusable follows the grid (spec 025, spec 035). -->
    <div class="grid-area">
      <div
        class="visually-hidden"
        data-testid="vote-announcement"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >{voteAnnouncement}</div>
      {#if isVoteBannerShown}
        <div
          class="vote-banner"
          data-testid="vote-banner"
          role="group"
          aria-labelledby={openVote !== null ? 'vote-question' : 'vote-result'}
          bind:this={voteBanner}
        >
          {#if openVote !== null}
            <p id="vote-question" class="vote-text" data-testid="vote-question">
              {voteQuestionText}
            </p>
            <div class="vote-actions">
              {#if isMyRequest || hasVoted}
                <!-- Not a Tab stop, but it takes the focus after a ballot. -->
                <span
                  data-testid="vote-status"
                  tabindex="-1"
                  bind:this={voteStatus}>{isMyRequest ? t('vote.waiting') : t('vote.cast')}</span
                >
              {:else}
                <button
                  type="button"
                  data-testid="vote-yes"
                  disabled={isVotingOffline}
                  onclick={() => castVote(true)}>{t('vote.yes')}</button
                >
                <button
                  type="button"
                  data-testid="vote-no"
                  disabled={isVotingOffline}
                  onclick={() => castVote(false)}>{t('vote.no')}</button
                >
              {/if}
            </div>
          {:else}
            <p id="vote-result" class="vote-text" data-testid="vote-result">{voteResultText}</p>
          {/if}
        </div>
      {/if}
      <GridViewport
        bind:this={gridViewport}
        grid={session.snapshot.grid}
        {selection}
        {activeWord}
        {onCellTap}
        {onClueTap}
        onSelect={select}
        {onLetter}
        {onErase}
        {onUndo}
        {words}
        pendingEdits={session.pendingEdits}
        flashes={session.flashes}
        caughtUpCells={session.caughtUpCells}
        {remoteSelections}
        {isAuthorsViewOn}
        {isOthersTintOn}
        {isAccessibilityOn}
        {playerColours}
        {clueFlags}
        {clueReactions}
      />
    </div>
    <!-- The completion status line. The page shows it in one of two places,
         never both: see isStatusInClueBar and isStatusUnderClueBar. -->
    {#snippet gridStatusLine()}
      <p class="grid-status" data-testid="grid-status" data-state={gridStatus} role="status">
        {gridStatus === 'solved' ? t('completion.solved') : t('completion.full_wrong')}
      </p>
    {/snippet}
    <div
      class="clue-bar"
      class:with-status={isStatusInClueBar}
      class:with-author={selectedAuthorLine !== null}
      data-testid="clue-bar"
      data-word={activeWord === null ? '' : wordKey(activeWord)}
      role="region"
      aria-label={t('clue_bar.label')}
    >
      <span class="clue-bar-text" data-testid="clue-bar-text"
        >{activeWord === null ? t('clue_bar.empty') : activeWord.text}</span
      >
      {#if selectedAuthorLine !== null}
        <span class="clue-bar-author" data-testid="clue-bar-author">{selectedAuthorLine}</span>
      {/if}
      {#if isStatusInClueBar}
        {@render gridStatusLine()}
      {/if}
    </div>
    {#if isStatusUnderClueBar}
      {@render gridStatusLine()}
    {/if}
    {#if isTouchScreen}
      <InAppKeyboard
        {onLetter}
        {onErase}
        onKeyUsed={() => gridViewport?.focusGrid()}
      />
    {/if}
  {/if}
</main>

<style>
  /* The page fills the window; the grid viewport takes the height left. */
  /* Positioned: the chat panel and the reaction picker are placed against it. */
  main {
    position: relative;
    box-sizing: border-box;
    /* Little padding: the clue bar and the grid need the height. */
    padding: 0.5rem 1rem;
    height: 100vh;
    height: 100dvh;
    display: flex;
    flex-direction: column;
  }

  .nickname-form {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 24rem;
  }

  /* The nickname shows in capitals, the placeholder too, while the value keeps
     the text as typed, so input methods and the caret work as usual (spec 012,
     room page flow step 3). */
  .nickname-form input {
    text-transform: uppercase;
  }

  .connection-banner {
    margin: 0.25rem 0;
    padding: 0.4rem 0.75rem;
    color: var(--nock-ink);
    background: var(--nock-clue-bg);
    border: 1px solid var(--nock-line);
  }

  .nickname-error {
    margin: 0;
    color: var(--nock-red);
  }

  /* Title, status, invitation link and the room toolbar on one row; it wraps
     when it must. */
  .room-header {
    flex: none;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.75rem;
  }

  /* The title, status, share and toolbar rows set their line height rather
     than take the font's normal one, which is 1px taller per row in Source
     Sans 3 than in the system font: each row keeps the height it had, and the
     grid its room (spec 041). */
  .room-header h1,
  .room-header p,
  .share-panel,
  .room-toolbar {
    line-height: 1.33;
  }

  .room-header h1 {
    margin: 0;
    font-size: 1.25rem;
  }

  .room-header p {
    margin: 0;
  }

  .share-panel {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }

  .share-panel a {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Only the link gives way when the panel is short of room: the button keeps
     its label on one line. */
  .share-panel button {
    flex: none;
  }

  /* The room toolbar holds the shared timer and its toggle, the chat toggle, the
     recap button of a solved room, the undo, pencil, check and reveal controls,
     the flag button, the authors switch, the two display switches of the grid
     cells and the account button (specs 027, 022, 028, 024, 020, 021, 019, 042
     and 033). On a roomy window it is one
     item of the header row, and it wraps when it must. */
  .room-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.75rem;
  }

  .undo-panel,
  .pencil-panel,
  .check-panel,
  .reveal-panel {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* A toolbar that scrolls cuts an outline drawn outside a control: draw it
     inside instead (3px wide, so spec 035 AC-2 still holds). The same on a roomy
     window, so the outline always stays inside the toolbar. The second selector
     reaches the toggle of the timer, which is drawn by a component of its own
     (RoomTimer), and nothing else that a child component puts in the toolbar. */
  .room-toolbar :focus-visible,
  .room-toolbar :global(.timer-toggle:focus-visible) {
    outline-offset: -3px;
  }

  /* A reveal button disabled by a spent budget says why with its own text
     ("Plus de lettre"), so the text keeps 4.5:1 against the button instead of
     the browser's pale grey (spec 024). The dashed border shows it is disabled. */
  .reveal-panel button:disabled {
    color: var(--nock-muted);
    background-color: var(--nock-clue-bg);
    border-style: dashed;
    cursor: not-allowed;
  }

  /* The authors switch when it is on: its text is underlined, like the band it
     draws under the letters. A text decoration shows on the engines' own button
     look and keeps the button's size. The pencil toggle shows that it is on the
     same way. */
  .authors-switch[aria-pressed='true'],
  .others-tint-switch[aria-pressed='true'],
  .access-switch[aria-pressed='true'],
  .pencil-toggle[aria-pressed='true'] {
    text-decoration: underline;
    text-decoration-thickness: 2px;
    text-underline-offset: 2px;
  }

  /* A target of 24 by 24 CSS px at least, whatever the engine's button style
     (spec 021, spec 014 AC-7). It never shrinks in the toolbar's row. */
  .flag-button {
    flex: none;
    box-sizing: border-box;
    min-width: 24px;
    min-height: 24px;
  }

  /* The chat toggle, the reaction button (spec 022), the recap button (spec
     028) and the account button (spec 033): the same target size as the flag
     button. */
  .chat-toggle,
  .recap-open,
  .react-button,
  .account-open {
    flex: none;
    box-sizing: border-box;
    min-width: 24px;
    min-height: 24px;
  }

  /* Room for the unread count, kept whether the count shows or not, so that
     the button and the toolbar keep their size when the panel opens. */
  .chat-unread-slot {
    display: inline-block;
    width: 2.4em;
    text-align: center;
  }

  .chat-unread {
    display: inline-block;
    padding: 0.15em 0.3em;
    border-radius: 1em;
    font-size: 0.8em;
    line-height: 1;
    color: var(--nock-white);
    background: var(--nock-red);
  }

  .host-panel-more,
  .room-toolbar-more {
    display: none;
  }

  /* The roster and the feed: stacked on a roomy window. */
  .presence {
    /* The smallest remove button (spec 014 AC-7), and the room left after a
       remove button so that a tap reaches all of it (spec 014 AC-8): after the
       last item of the scrolling roster list, and under the last row. */
    --remove-size: 24px;
    --list-end-room: 3px;
    flex: none;
    display: flex;
    flex-direction: column;
  }

  .roster {
    flex: none;
    /* A little room under the last row. A browser tests a tap against about one
       pixel around the point, so an element that starts at the bottom edge of a
       remove button would take a tap on the last pixel row of the button
       (spec 014 AC-8). */
    padding-bottom: var(--list-end-room);
  }

  .roster h2 {
    margin: 0.25rem 0;
    font-size: 1rem;
  }

  .roster ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 1rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .roster li {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .roster-colour {
    display: inline-block;
    width: 0.8rem;
    height: 0.8rem;
    border-radius: 50%;
  }

  .roster-state {
    font-size: 0.8rem;
    color: var(--nock-muted);
  }

  /* No opacity: dimmed text would not reach 4.5:1 (spec 035). The state is
     also written in the row, and the nickname shows it by its style. */
  .roster li[data-state='idle'] .roster-nickname {
    font-style: italic;
  }

  .roster li[data-state='disconnected'] .roster-nickname {
    font-style: italic;
    text-decoration: line-through;
  }

  .roster-host {
    font-size: 0.8rem;
    font-weight: bold;
  }

  .remove-player {
    min-width: var(--remove-size);
    min-height: var(--remove-size);
    padding: 0 0.3rem;
    font-size: 0.75rem;
  }

  /* The short button is exactly as wide as the smallest size, whatever the root
     font and the font that draws its sign: the roster list keeps room for this
     width (spec 014 AC-10). */
  .remove-player.compact {
    box-sizing: border-box;
    width: var(--remove-size);
    padding-inline: 0;
  }

  /* One compact row of controls for the host; it wraps on a roomy window and
     scrolls sideways on a small one. */
  .host-panel {
    flex: none;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.5rem;
    font-size: 0.8rem;
  }

  .settings-form {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.5rem;
  }

  .settings-form input[type='number'] {
    width: 3.5rem;
  }

  /* A short list that scrolls: the grid keeps the height (spec 006). */
  .feed {
    flex: none;
    box-sizing: border-box;
    overflow-wrap: anywhere;
    font-size: 0.85rem;
  }

  .feed h2 {
    margin: 0;
    font-size: 0.85rem;
  }

  /* The list has a fixed height, about three lines, whatever the number of its
     items: a new line never moves the grid (spec 013 "Client: feed height",
     spec 021 AC-9). The lines beyond it scroll (spec 013 AC-7). */
  .feed ul {
    height: 3.6rem;
    overflow-y: auto;
    /* The page keeps the reader's place itself when lines come and go (spec
       013 AC-7), the same way in every engine: no scroll anchoring from the
       browser on top of it. */
    overflow-anchor: none;
    /* Room for the focus outline drawn outside the list (spec 035 AC-2): it
       stays clear of the heading above and of the next panel. */
    margin: 0.25rem 0;
    padding: 0;
    list-style: none;
  }

  /* The grid state line, kept out of the scrolling area: under the clue bar,
     or in its row on a low window (below). */
  .grid-status {
    flex: none;
    margin: 0;
    padding: 0.25rem 0.75rem;
    font-weight: bold;
  }

  /* The area of the grid: it takes the height left, as the grid viewport did,
     and holds the vote banner over the viewport's top edge. */
  .grid-area {
    position: relative;
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  /* Over the grid (spec 025 decision 9): absolutely placed, so it takes no
     height from the grid, and above the cells, some of which are positioned. */
  .vote-banner {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1;
    box-sizing: border-box;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.75rem;
    /* Room for the focus outline of the buttons (2px, 2px away). */
    padding: 0.375rem 0.5rem;
    background: var(--nock-white);
    border-bottom: 1px solid var(--nock-navy);
    font-size: 0.9rem;
  }

  .vote-text {
    flex: 1 1 10rem;
    margin: 0;
  }

  .vote-actions {
    flex: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* A disabled ballot button (offline) keeps a readable text. */
  .vote-actions button:disabled {
    color: var(--nock-muted);
    background-color: var(--nock-clue-bg);
    border-style: dashed;
    cursor: not-allowed;
  }

  /* At least 24 by 24 CSS px, whatever the engine's button style. */
  .vote-actions button {
    box-sizing: border-box;
    min-width: 3rem;
    min-height: 28px;
    padding: 0 0.75rem;
    font: inherit;
    color: var(--nock-ink);
    background: var(--nock-white);
    border: 1px solid var(--nock-rule);
    border-radius: 4px;
  }

  /* Below the scrolling grid, so it is always inside the window. */
  .clue-bar {
    flex: none;
    box-sizing: border-box;
    padding: 0.5rem 0.75rem;
    background: var(--nock-clue-bg);
    border-top: 1px solid var(--nock-rule);
  }

  .clue-bar-text {
    display: block;
    font-size: 1rem;
    line-height: 1.3;
  }

  /* On a low window the completion status shares the clue bar's row and adds no
     height (spec 026 AC-10). It keeps its whole text on one line; the clue text
     gives up the width and ends with an ellipsis, but keeps its whole text in
     the page, so a screen reader reads the whole clue. */
  .clue-bar.with-status {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .clue-bar.with-status .clue-bar-text {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* The same font size and line height as the clue text, so the row is no
     higher than the clue text alone. */
  .clue-bar .grid-status {
    flex: none;
    padding: 0;
    font-size: 1rem;
    line-height: 1.3;
    white-space: nowrap;
  }

  /* The author of the selected letter (spec 019) follows the clue text: on its
     line when there is room, otherwise on a line of its own, where it ends with
     an ellipsis if that line is too short. */
  .clue-bar.with-author {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    column-gap: 0.75rem;
  }

  .clue-bar-author {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.875rem;
    line-height: 1.3;
    color: var(--nock-muted);
  }

  /* A narrow or low window (a phone) keeps its height for the grid: the roster
     and the feed are one line each, the roster scrolls sideways and the feed
     shows its newest item and scrolls up to the older ones. */
  @media (max-height: 500px), (max-width: 480px) {
    .room-header h1 {
      font-size: 1rem;
    }

    .share-label {
      display: none;
    }

    /* The header buttons get the same size in every engine. WebKit on a touch
       screen gives a button a 16px font and a taller padding than Chromium and
       Firefox, and then the header needs a third row, on a low window and on a
       narrow tall one alike (spec 013 AC-6). The second selector reaches the
       toggle of the timer, which is drawn by a component of its own (RoomTimer),
       and nothing else that a child component puts in the header. */
    .room-header button,
    .room-header :global(.timer-toggle) {
      padding-block: 1px;
      font-size: 0.8rem;
    }

    /* The header takes two rows whatever the width of the system font (a wider
       font made it take three, and the grid lost its room): the title, the
       status and the invitation link on the first, the room toolbar on the
       second. The link has a basis that is smaller than its text, so the panel
       stays on the first row and the link shrinks, with its ellipsis, to the
       room left there. The toolbar has a basis of the whole width, so it always
       goes to the second row (spec 013 AC-6, spec 014 AC-7). */
    .share-panel {
      flex: 1 1 17rem;
    }

    /* The toolbar is one row that never wraps, so new controls cost no height,
       and it scrolls sideways when its content is wider (spec 024). Its
       scrollbar is hidden: it would take height, and the edge fade already
       shows that more content is hidden. */
    .room-toolbar {
      flex: 1 1 100%;
      min-width: 0;
      flex-wrap: nowrap;
      white-space: nowrap;
      overflow-x: auto;
      scrollbar-width: none;
    }

    .room-toolbar::-webkit-scrollbar {
      display: none;
    }

    .undo-panel,
    .pencil-panel,
    .check-panel,
    .reveal-panel {
      flex: none;
    }

    .presence {
      gap: 0.1rem;
    }

    .roster,
    .feed {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      min-width: 0;
    }

    .roster h2,
    .feed h2 {
      flex: none;
      margin: 0;
      font-size: 0.8rem;
    }

    /* No scroll padding: the focus outline is drawn inside the buttons (see
       below), and the list can be only 3px wider than a button (spec 014
       AC-10). A padding of 8px would push a button scrolled into view out of
       the list. */
    .roster ul {
      flex: 1 1 auto;
      flex-wrap: nowrap;
      min-width: 0;
      gap: 0.75rem;
      overflow-x: auto;
    }

    .roster li {
      flex: none;
      white-space: nowrap;
    }

    /* The list scrolls sideways and its width is rarely a whole number of
       pixels, so at the end of the scroll the last button can stay a fraction of
       a pixel out of the list, where a tap does not reach it. A few pixels of
       room after the last item keep the button whole (spec 014 AC-8). */
    .roster li:last-child {
      padding-right: var(--list-end-room);
    }

    /* The line takes the room that the heading leaves, so a squeezed feed cuts
       the heading only when the line has no room left (spec 014 AC-10). The
       list is one line high, whatever the number of its items (spec 013 AC-6). */
    .feed ul {
      flex: 1 1 0;
      min-width: 0;
      margin: 0;
      height: 1.3rem;
      line-height: 1.3rem;
    }

    .host-panel,
    .settings-form {
      flex-wrap: nowrap;
      white-space: nowrap;
    }

    .host-panel {
      overflow-x: auto;
      scrollbar-width: thin;
      /* A focused control is scrolled clear of the edge fade on the right. */
      scroll-padding: 0 2rem 0 8px;
    }

    /* A fade stuck to the right edge of the visible part of the host panel or
       the toolbar. Its negative margin cancels its width and the gap before
       it: no layout change. */
    .host-panel-more,
    .room-toolbar-more {
      display: block;
      flex: none;
      position: sticky;
      right: 0;
      align-self: stretch;
      width: 1.5rem;
      background: linear-gradient(to right, transparent, var(--nock-white));
      pointer-events: none;
      visibility: hidden;
    }

    .host-panel-more {
      margin-left: calc(-1.5rem - 0.5rem);
    }

    .room-toolbar-more {
      margin-left: calc(-1.5rem - 0.75rem);
    }

    .host-panel-more.shown,
    .room-toolbar-more.shown {
      visibility: visible;
    }

    /* A scroll container clips an outline drawn outside a control: draw it
       inside instead (3px wide, so spec 035 AC-2 still holds). */
    .roster ul :focus-visible,
    .host-panel :focus-visible {
      outline-offset: -3px;
    }

    /* A list that scrolls is a Tab stop (spec 035 AC-12). Drawn outside, the
       bottom edge of its outline is painted over by the next panel, or by the
       grid that comes right after the row on a low window (spec 035 AC-2), so
       draw it inside the list's own box. */
    .roster ul:focus-visible,
    .feed ul:focus-visible {
      outline-offset: -3px;
    }

    /* The fade never covers a control that has the keyboard focus. A mouse click
       or a tap also focuses a control, but it must not hide the fade (spec 014
       AC-7), so this follows a class set only for keyboard focus. */
    .host-panel.keyboard-focus .host-panel-more,
    .room-toolbar.keyboard-focus .room-toolbar-more {
      visibility: hidden;
    }

    .host-panel button,
    .host-panel select,
    .host-panel input,
    .remove-player {
      height: 1.2rem;
      box-sizing: border-box;
      padding-block: 0;
      font-size: 0.75rem;
    }

    /* A target of 24 by 24 CSS pixels at least (spec 014 AC-7). It may make the
       row taller, but never sticks out of the scrolling list (spec 014 AC-8). */
    .remove-player {
      min-width: var(--remove-size);
      min-height: var(--remove-size);
    }

    .feed li {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .vote-banner {
      font-size: 0.8rem;
    }
  }

  /* A low window (a phone on its side) also takes the padding down, and puts the
     roster, the feed and the host panel side by side. */
  @media (max-height: 500px) {
    main {
      padding: 0.25rem 0.5rem;
    }

    /* The header's two rows sit 1px apart: the room toolbar's row is 24px high
       for the flag button's target (spec 021 AC-11), and the grid keeps the
       height it had before. */
    .room-header {
      row-gap: 1px;
    }

    .clue-bar {
      padding: 0.25rem 0.75rem;
    }

    /* The author shares the clue text's row too and adds no height (spec 019
       AC-4): the clue text and the author give up the width and end with an
       ellipsis. The author follows the clue text, and the status keeps the end
       of the row. Centred like the status: the author's smaller text has a
       shorter line than the clue text, so the row keeps the clue text's
       height. */
    .clue-bar.with-author {
      flex-wrap: nowrap;
      align-items: center;
    }

    .clue-bar.with-author .clue-bar-text {
      flex: 0 1 auto;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* The clue text has priority over the author (spec 019 decision 11). The
       author's flex basis is 0, so it never takes width from the clue text: it
       grows into the room the clue text leaves, up to its whole text
       (max-content), and never goes under 6 times its font size. When the row
       is too short for that minimum, the clue text is the one that shrinks. */
    .clue-bar.with-author .clue-bar-author {
      flex: 1 1 0;
      min-width: 6em;
      max-width: max-content;
    }

    .clue-bar.with-author .grid-status {
      margin-left: auto;
    }

    /* The grid comes right after this row, so the room under the remove buttons
       goes under the whole row, not under the roster alone (spec 014 AC-8). On
       the roster alone, the feed and the host panel would stretch 3px taller and
       their content would sit 1.5px lower than the roster's. */
    .presence {
      --presence-gap: 1rem;
      flex-direction: row;
      gap: var(--presence-gap);
      padding-bottom: var(--list-end-room);
    }

    /* The three boxes start as thirds of the row. The host panel keeps its third
       and scrolls sideways. The roster takes more width only when its list needs
       it for one remove button, and it takes that width from the feed alone
       (spec 014 AC-10). */
    .roster,
    .feed {
      flex: 1 1 0;
      min-width: 0;
    }

    .host-panel {
      flex: 0 0 calc((100% - 2 * var(--presence-gap)) / 3);
      min-width: 0;
    }

    .roster {
      padding-bottom: 0;
      /* Never narrower than the heading, the gap and the list at its minimum. */
      min-width: min-content;
    }

    /* Without inline-size containment, the list would ask for the width of all
       its items in one line: with eight players the roster would span all eight
       of them and push the feed and the host panel out of the row. With it, the
       list takes no width from its content (a box with inline-size containment
       measures zero), so it takes the width the row leaves and scrolls, and a
       change of the buttons' text cannot change the width of the list. The list
       is never narrower than one compact remove button and the room after it. */
    .roster ul {
      contain: inline-size;
      min-width: calc(var(--remove-size) + var(--list-end-room));
    }

    /* The feed gives up width when the roster needs it: its heading ends with an
       ellipsis instead of spilling out of the box. */
    .feed h2 {
      flex: 0 1 auto;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
</style>
