<script lang="ts">
  import { flushSync, onMount, tick, untrack } from 'svelte'
  import AccountDialog from './AccountDialog.svelte'
  import AideMenu from './AideMenu.svelte'
  import ClueBar from './ClueBar.svelte'
  import EntryFrame from './EntryFrame.svelte'
  import GridViewport from './GridViewport.svelte'
  import HostSettings from './HostSettings.svelte'
  import InAppKeyboard from './InAppKeyboard.svelte'
  import ReactionPicker from './ReactionPicker.svelte'
  import RecapDialog from './RecapDialog.svelte'
  import RoomGoneDialog from './RoomGoneDialog.svelte'
  import RoomMenu from './RoomMenu.svelte'
  import RoomNote from './RoomNote.svelte'
  import type { ShownNote } from './RoomNote.svelte'
  import RoomPopover from './RoomPopover.svelte'
  import RoomTopBar from './RoomTopBar.svelte'
  import Salon from './Salon.svelte'
  import { t } from './i18n'
  import { fetchAccountStatus, linkRoom, type AccountStatus } from './account'
  import { nameOf, streamEntries } from './activityFeed'
  import {
    AUTHORS_VIEW_KEY,
    MIN_GRID_VIEWPORT_PX,
    colourByPlayer,
    legendNames,
    legendRoom,
    readAuthorsView,
  } from './authorsView'
  import {
    clueReactionMarkers,
    hasNewEventLines,
    isPaced,
    msUntilNextExpiry,
    newestFeedItemId,
    salonToggleLabel,
    sendsInWindow,
    shownChatLines,
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
  import {
    checkNickname,
    planAutomaticJoin,
    readNickname,
    writeIdentity,
    writeNickname,
    type Identity,
  } from './joinRules'
  import { markFinished } from './catalogue'
  import { recordOwnRoom } from './history'
  import {
    CATCH_UP_HIGHLIGHT_MS,
    applyCatchUp,
    endCaughtUp,
    fetchCatchUp,
  } from './catchUp'
  import { selectionAfterTab } from './navigation'
  import { remoteSelectionsOf } from './remoteSelections'
  import {
    readRoomGrid,
    readRoomSeenSeq,
    readRoomSelection,
    writeRoomSeenSeq,
    writeRoomSelection,
  } from './roomRecord'
  import { readItem, removeItem, writeItem } from './storage'
  import { readTimerHidden, writeTimerHidden } from './timer'
  import { VOTE_TICK_MS, voteCountdown } from './voteCountdown'
  import { LOW_WINDOW_PX, isWideWindow } from './windowForm'
  import type {
    LetterCellView,
    PendingEdit,
    ReactionValue,
    RoomStatus,
    Snapshot,
    VoteClock,
    VoteView,
  } from './roomSession'
  import {
    EDIT_SEND_INTERVAL_MS,
    FLASH_MS,
    PING_INTERVAL_MS,
    REACTION_MS,
    SILENCE_LIMIT_MS,
    addPendingEdit,
    endFlash,
    endReaction,
    gridLabel,
    isFinalClose,
    latestPendingEdits,
    letterCellIndex,
    newSession,
    receiveFrame,
    reconnectDelay,
    shownCell,
    shownCellWith,
    shownGrid,
    statusAfterFinalClose,
    statusAfterLoss,
  } from './roomSession'
  import { fittedGridBox } from './gridLayout'
  import {
    computeWords,
    positionKey,
    sameSelection,
    selectedWord,
    selectionAfterCellTap,
    selectionAfterClueTap,
    selectionOnCell,
    validSelection,
    wordAt,
  } from './wordSelection'
  import type { Selection, Word } from './wordSelection'

  const MAX_REVEAL_COUNT = 99
  // The performance mark set once the grid takes taps and keys (spec 036).
  const INTERACTIVE_MARK = 'nock:interactive'
  // The Salon column closed by the player, for every room of this browser.
  const SALON_CLOSED_KEY = 'nock.salon_closed'
  const SALON_CLOSED_VALUE = 'true'
  // The in-app keyboard hidden by the player, for every room of this browser
  // (spec 044).
  const KEYBOARD_HIDDEN_KEY = 'nock.keyboard_hidden'
  const KEYBOARD_HIDDEN_VALUE = 'true'
  // The column layout's play area: its padding, and the smallest width of the
  // clue bar when the play area has that much room (spec 043, Decision 12).
  const PLAY_AREA_PADDING_PX = 12
  const CLUE_BAR_MIN_PX = 320

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

  // ---- The in-app keyboard (spec 044) ----

  // The player's choice, read when the page loads. When the storage throws, a
  // hide holds for the page's life only.
  const isKeyboardHiddenAtLoad = readItem(KEYBOARD_HIDDEN_KEY) === KEYBOARD_HIDDEN_VALUE
  let isKeyboardHidden = $state(isKeyboardHiddenAtLoad)
  // The keyboard shows on a touch screen, unless the player hid it or the grid
  // is solved. The page shows it only once it has a snapshot.
  let isKeyboardShown = $derived(
    isTouchScreen && !isKeyboardHidden && !session.solved && session.snapshot !== null,
  )

  // « Clavier »: hide or show the keyboard and remember the choice. The grid
  // refits at once to the room the keyboard gave or took.
  function toggleKeyboard(): void {
    isKeyboardHidden = !isKeyboardHidden
    if (isKeyboardHidden) {
      writeItem(KEYBOARD_HIDDEN_KEY, KEYBOARD_HIDDEN_VALUE)
    } else {
      removeItem(KEYBOARD_HIDDEN_KEY)
    }
    refitNow()
  }

  // ⇄: what a second tap on the selected cell does (spec 007). With nothing
  // selected, nothing changes.
  function swapDirection(): void {
    if (selection !== null) {
      onCellTap(selection.row, selection.column)
    }
  }

  // ---- The layout (spec 043) ----

  // The window's size, followed through each resize and rotation
  // (<svelte:window> below).
  let windowWidth = $state(window.innerWidth)
  let windowHeight = $state(window.innerHeight)

  // A low window: at most 500 px high, a phone on its side.
  let isLowWindow = $derived(windowHeight <= LOW_WINDOW_PX)
  let layout = $derived(layoutOf(windowWidth, windowHeight, isKeyboardShown))
  // The phone top bar is the sheet layout's, and the column layout's on a low
  // window, where the computer top bar would not fit.
  let topBarForm: 'phone' | 'computer' = $derived(
    layout === 'sheet' || isLowWindow ? 'phone' : 'computer',
  )

  // The two layouts of the room (spec 043, spec 044, "Which layout"): "column"
  // for a wide window, or for a landscape window at most LOW_WINDOW_PX high on
  // which the in-app keyboard does not show; "sheet" otherwise.
  function layoutOf(width: number, height: number, isKeyboardOn: boolean): 'sheet' | 'column' {
    const isLandscape = width > height
    if (!isLandscape) {
      return 'sheet'
    }
    const isLowWithoutKeyboard = height <= LOW_WINDOW_PX && !isKeyboardOn
    if (isWideWindow(width, height) || isLowWithoutKeyboard) {
      return 'column'
    }
    return 'sheet'
  }

  // ---- The popovers, the Salon and the scrim (spec 043) ----

  // The open popover: the Aide menu, the Menu, or none.
  let openPopover: 'aide' | 'menu' | null = $state(null)
  let aideButton: HTMLButtonElement | null = $state(null)
  let menuButton: HTMLButtonElement | null = $state(null)
  let chatToggle: HTMLButtonElement | null = $state(null)
  let aideMenu: HTMLElement | null = $state(null)
  let roomMenu: HTMLElement | null = $state(null)
  let salon: Salon | undefined = $state()

  // The Salon is closed at load in the sheet layout; in the column layout it
  // is open unless the player closed it in this browser.
  let isSheetSalonOpen = $state(false)
  let isColumnSalonOpen = $state(readItem(SALON_CLOSED_KEY) !== SALON_CLOSED_VALUE)
  let isSalonOpen = $derived(layout === 'sheet' ? isSheetSalonOpen : isColumnSalonOpen)
  let salonTab: 'discussion' | 'players' = $state('discussion')
  // The stream is read while it shows: the Salon open on its Discussion tab.
  let isStreamShown = $derived(isSalonOpen && salonTab === 'discussion')
  // The scrim covers the page under the top bar while a popover or the Salon
  // sheet is open (sheet layout only).
  let isScrimShown = $derived(layout === 'sheet' && (openPopover !== null || isSalonOpen))

  // A change of layout closes the popovers and the reaction picker; the Salon
  // takes the state it has in the new layout (the sheet starts closed).
  let lastLayout: 'sheet' | 'column' = untrack(() => layout)
  $effect(() => {
    const current = layout
    if (current === lastLayout) {
      return
    }
    lastLayout = current
    openPopover = null
    isPickerOpen = false
    isSheetSalonOpen = false
  })

  // Open or close a popover. In the sheet layout one overlay shows at a time;
  // in the column layout the Salon column stays as it is.
  function togglePopover(popover: 'aide' | 'menu'): void {
    if (openPopover === popover) {
      openPopover = null
      return
    }
    openPopover = popover
    isPickerOpen = false
    if (layout === 'sheet') {
      isSheetSalonOpen = false
    }
  }

  // Close the open popover and put the focus on its button.
  function closePopoverToButton(): void {
    const button = openPopover === 'aide' ? aideButton : menuButton
    openPopover = null
    button?.focus()
  }

  // In the column layout a pointer press outside the open popover and its
  // button closes it, and the focus goes where the pointer puts it.
  $effect(() => {
    if (openPopover === null || layout !== 'column') {
      return
    }
    const popover = openPopover === 'aide' ? aideMenu : roomMenu
    const button = openPopover === 'aide' ? aideButton : menuButton
    const onPointerDown = (event: PointerEvent): void => {
      const target = event.target
      if (!(target instanceof Node)) {
        return
      }
      if (popover?.contains(target) || button?.contains(target)) {
        return
      }
      openPopover = null
    }
    window.addEventListener('pointerdown', onPointerDown, true)
    return () => window.removeEventListener('pointerdown', onPointerDown, true)
  })

  // A tap or a click on the scrim closes what it lies under; the focus does
  // not move.
  function closeOverlays(): void {
    openPopover = null
    isSheetSalonOpen = false
  }

  // « Salon » opens the Salon, with the focus inside it, or closes it.
  function toggleSalon(): void {
    if (isSalonOpen) {
      setSalonOpen(false)
      return
    }
    setSalonOpen(true)
    void salon?.focusInside()
  }

  // Open or close the Salon of the current layout. The column remembers a
  // close in this browser; in the sheet layout one overlay shows at a time.
  function setSalonOpen(isOpen: boolean): void {
    if (layout === 'column') {
      isColumnSalonOpen = isOpen
      if (isOpen) {
        removeItem(SALON_CLOSED_KEY)
      } else {
        writeItem(SALON_CLOSED_KEY, SALON_CLOSED_VALUE)
      }
      refitNow()
      return
    }
    isSheetSalonOpen = isOpen
    if (isOpen) {
      openPopover = null
      isPickerOpen = false
    }
  }

  // Escape inside the Salon: the focus goes to « Salon »; the sheet closes, the
  // column stays open.
  function onSalonEscape(): void {
    if (layout === 'sheet') {
      isSheetSalonOpen = false
    }
    chatToggle?.focus()
  }

  // ---- The timer's slot (spec 027, spec 043) ----

  // The choice is read when the page loads, and holds for every room.
  let isTimerShown = $state(!readTimerHidden())

  function setTimerShown(isShown: boolean): void {
    isTimerShown = isShown
    writeTimerHidden(!isShown)
  }

  let shareLink = $derived(`${location.origin}/r/${code}`)

  // Leaving the page must not leave the timers to fire on a destroyed page.
  $effect(() => {
    return () => {
      clearTimeout(pacingTimer)
    }
  })

  let words = $derived(session.snapshot === null ? [] : computeWords(session.snapshot.grid))
  // A new snapshot may remove the word of the selection: then nothing is selected.
  let selection = $derived(validSelection(words, rawSelection))
  let activeWord = $derived(selectedWord(words, selection))
  let remoteSelections = $derived(remoteSelectionsOf(session.snapshot, words, session.cursors))

  // ---- The Auteurs mode (spec 045) ----

  // It starts from what this browser remembers (off by default) and remembers
  // each change. It sends nothing.
  let isAuthorsViewOn = $state(readAuthorsView())
  let playerColours = $derived(colourByPlayer(session.snapshot?.players ?? []))
  let authorsLegendNames = $derived(legendNames(session.snapshot?.players ?? []))
  // The legend's height as the grid viewport draws it. The room the grid
  // gives it, and whether it lies over the grid instead, are worked out with
  // the play area below.
  let authorsLegendHeight = $state(0)

  function toggleAuthorsView(): void {
    isAuthorsViewOn = !isAuthorsViewOn
    writeSwitch(AUTHORS_VIEW_KEY, isAuthorsViewOn)
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

  // ---- The page before the first snapshot (spec 046) ----

  // The statuses that refuse entry: before any snapshot each shows its card.
  const ENTRY_CARD_STATUSES: RoomStatus[] = [
    'full',
    'locked',
    'removed',
    'replaced',
    'throttled',
    'not_found',
  ]
  let isEntryCardShown = $derived(
    session.snapshot === null && ENTRY_CARD_STATUSES.includes(session.status),
  )
  // An entry page, the nickname card or a status card, shows in the entry
  // frame, with no room top bar and no layout.
  let isEntryPage = $derived(isEntryCardShown || (session.snapshot === null && isFormShown))
  // Before the first snapshot, with no entry page, the room opens: its top bar
  // is in place and inert, and one line says what happens.
  let isOpening = $derived(session.snapshot === null && !isEntryPage)

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
  // Where the status shows (spec 026 AC-10, spec 044): in the clue bar's row
  // while the in-app keyboard shows on a low window, where a band would take the
  // grid's height; under the bar, as a band, everywhere else. A solved page has
  // no keyboard, so a solved status is always the band.
  let isStatusInClueBar = $derived(gridStatus !== null && isKeyboardShown && isLowWindow)
  let isStatusUnderClueBar = $derived(gridStatus !== null && !isStatusInClueBar)
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

  // Send the settings of the form; false when a count is not valid.
  function saveSettings(): boolean {
    if (!isValidCount(lettersInput) || !isValidCount(wordsInput)) {
      return false
    }
    send({
      type: 'change_settings',
      help_mode: helpModeInput,
      reveal_budget: { letters: lettersInput, words: wordsInput },
    })
    return true
  }

  // The host's settings sheet, opened from the Menu.
  let hostSettings: HostSettings | undefined = $state()

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

  // The identity of the last snapshot, held in memory: the next join uses it
  // first (lobby/joining.md rules 8.1 and 10).
  let heldIdentity: Identity | null = null

  // A snapshot answers a join: remember who I am, and the nickname I typed.
  function rememberJoin(snapshot: Snapshot): void {
    for (const player of snapshot.players) {
      if (player.player_id === snapshot.you) {
        heldIdentity = {
          player_id: snapshot.you,
          resume_token: snapshot.resume_token,
          nickname: player.nickname,
        }
        writeIdentity(code, heldIdentity)
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
    if (cellChanged) {
      send(selectCellMessage(next))
    }
  }

  // The select_cell of a selection: the server only knows the cell and the
  // direction, not the chosen word.
  function selectCellMessage(selected: Selection): object {
    return {
      type: 'select_cell',
      row: selected.row,
      column: selected.column,
      direction: selected.direction,
    }
  }

  // The letter cells of the snapshot's grid, by "row,column": built once per
  // snapshot, so that finding a cell reads no other cell.
  let letterCells = $derived(
    session.snapshot === null
      ? new Map<string, LetterCellView>()
      : letterCellIndex(session.snapshot.grid),
  )
  // The newest pending edit of each cell, by "row,column".
  let latestEdits = $derived(latestPendingEdits(session.pendingEdits))

  // The letter cell at a position of the snapshot, or null.
  function letterCellAt(row: number, column: number): LetterCellView | null {
    return letterCells.get(positionKey(row, column)) ?? null
  }

  // The letter a cell of the snapshot shows, pending edits included; null
  // when it shows none, or when it is not a letter cell.
  function shownLetterAt(row: number, column: number): string | null {
    const cell = letterCellAt(row, column)
    if (cell === null) {
      return null
    }
    const latestEdit = latestEdits.get(positionKey(row, column)) ?? null
    return shownCellWith(cell, latestEdit).letter
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
    editsMade += 1
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

  // Ask the server to undo my last edit. It goes after the edits pending when it
  // is made and before any later edit (platform/server.md rule 9).
  function onUndo(): void {
    if (session.solved) {
      return
    }
    sendRequest({ type: 'undo' })
  }

  // Ask the server to check the selected letter, the selected word or the grid.
  function onCheck(target: object): void {
    if (session.solved) {
      return
    }
    sendRequest({ type: 'check', target })
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

  // Ask the server to reveal the selected cell. The letter comes back in a
  // cell_locked event: the page never guesses it.
  function onRevealLetter(): void {
    if (isRevealLetterDisabled || selection === null) {
      return
    }
    sendRequest({
      type: 'reveal',
      target: { scope: 'letter', row: selection.row, column: selection.column },
    })
  }

  // Ask the server to reveal the selected word.
  function onRevealWord(): void {
    if (isRevealWordDisabled || activeWord === null) {
      return
    }
    sendRequest({
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
      if (shownLetterAt(position.row, position.column) === null) {
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

  // ---- The stream and its unread messages (specs 013, 022, 043) ----

  let chatText = $state('')
  // Lines up to this seq are read: the seq of the page's first snapshot, then
  // the seq of the newest line while the stream shows. A reconnection keeps it,
  // so the lines that came meanwhile count as unread. null before the first
  // snapshot.
  let lastSeenChatSeq: number | null = $state(null)

  let chatHistory = $derived(session.snapshot === null ? [] : session.snapshot.chat)
  // The stream: the newest messages and the newest event lines, each kind with
  // its own cap, in seq order.
  let stream = $derived(streamEntries(shownChatLines(chatHistory), session.feed))
  let unreadLines = $derived(
    isStreamShown || lastSeenChatSeq === null
      ? 0
      : unreadCount(chatHistory, lastSeenChatSeq, you),
  )
  // While the stream shows, every line of the history is read.
  $effect(() => {
    if (!isStreamShown || chatHistory.length === 0) {
      return
    }
    const newestSeq = chatHistory[chatHistory.length - 1].seq
    if (lastSeenChatSeq === null || newestSeq > lastSeenChatSeq) {
      lastSeenChatSeq = newestSeq
    }
  })

  // The new-events dot (spec 043): the event lines up to this feed item id were
  // there the last time the stream showed. A line about another player added
  // since then shows the dot, while no message is unread; showing the stream
  // removes it.
  let lastSeenFeedItemId = $state(0)
  let hasNewEvents = $derived(
    !isStreamShown && unreadLines === 0 && hasNewEventLines(session.feed, lastSeenFeedItemId, you),
  )
  let salonLabel = $derived(salonToggleLabel(unreadLines, hasNewEvents))
  $effect(() => {
    if (!isStreamShown) {
      return
    }
    const newestId = newestFeedItemId(session.feed)
    if (newestId > lastSeenFeedItemId) {
      lastSeenFeedItemId = newestId
    }
  })

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

  // In the sheet layout one overlay shows at a time; in the column layout the
  // picker closes the popovers and leaves the Salon column.
  function toggleReactionPicker(): void {
    if (isPickerOpen) {
      closeReactionPicker()
      return
    }
    isPickerOpen = true
    openPopover = null
    if (layout === 'sheet') {
      isSheetSalonOpen = false
    }
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
  // The banner shows the open vote, never once the grid is solved; it leaves
  // as soon as the vote closes and never shows a result (spec 047).
  let isVoteBannerShown = $derived(!session.solved && openVote !== null)
  // « Réagir » is disabled while the vote banner shows, so the picker never
  // covers the vote's buttons (spec 043, Decision 10).
  let isReactDisabled = $derived(activeWord === null || isMuted || isVoteBannerShown)
  let isMyRequest = $derived(
    openVote !== null && session.snapshot !== null && openVote.player_id === session.snapshot.you,
  )
  let hasVoted = $derived(openVote !== null && session.votedIds.includes(openVote.vote_id))
  let voteQuestionText = $derived(openVote === null ? '' : voteQuestion(openVote))
  let voteResultText = $derived(
    session.lastVoteOutcome === null ? '' : t(`vote.result.${session.lastVoteOutcome}`),
  )
  // What a screen reader hears: the question when a vote opens, the result
  // when it closes.
  let voteAnnouncement = $derived(openVote !== null ? voteQuestionText : voteResultText)

  // ---- The countdown of the open vote (spec 047) ----

  // The countdown of the open vote when this page saw it open, else null: a
  // vote known only from a snapshot shows no seconds and no bar.
  let voteClock = $derived(openVote === null ? null : clockOfVote(openVote))
  // The page's clock (performance.now()), read again every VOTE_TICK_MS while
  // the banner counts.
  let voteNowMs = $state(0)
  let countdown = $derived(voteClock === null ? null : voteCountdown(voteClock, voteNowMs))

  $effect(() => {
    if (voteClock === null || !isVoteBannerShown) {
      return
    }
    voteNowMs = performance.now()
    const ticker = setInterval(() => {
      voteNowMs = performance.now()
    }, VOTE_TICK_MS)
    return () => clearInterval(ticker)
  })

  // The countdown the session keeps for `vote`, or null when it keeps none for
  // that vote.
  function clockOfVote(vote: VoteView): VoteClock | null {
    const clock = session.voteClock
    if (clock === null || clock.vote_id !== vote.vote_id) {
      return null
    }
    return clock
  }

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
  // The banner's height, with its border: a note that shows while the banner
  // is on the page sits under it (spec 043, Decision 25).
  let voteBannerHeight = $state(0)
  let voteStatus: HTMLElement | null = $state(null)

  // What the banner holds: nothing, or the question of one vote.
  let bannerContent = $derived(
    !isVoteBannerShown || openVote === null ? 'none' : `vote-${openVote.vote_id}`,
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

  // ---- The 3-second notes (spec 043) ----

  // The note over the grid, one at a time, and the newest note of the room
  // that waits for the vote banner to go.
  let shownNote: ShownNote | null = $state(null)
  let waitingNote: ShownNote | null = $state(null)
  // Each shown note gets its own id, so a newer one replaces the older at once.
  let nextShownNoteId = 1
  let handledRoomNoteId = 0
  let shownUndoRefusals = 0

  function newShownNote(isUndo: boolean, kind: string | null, text: string): ShownNote {
    const note = { id: nextShownNoteId, isUndo, kind, text }
    nextShownNoteId += 1
    return note
  }

  // The notes of the room, in one place so that the newest always wins. A new
  // note: none while the stream shows; while the vote banner is on the page it
  // waits, replacing any older waiting note; otherwise it shows, and a note
  // that waited is dropped (the result of a vote, made once the banner has
  // left, replaces the notes that waited during it, spec 047). With no new
  // note, once the banner has gone, the note that waited shows, unless the
  // stream shows by then: the player reads the same line there.
  $effect(() => {
    const latest = session.latestNote
    const isBannerShown = isVoteBannerShown
    if (latest !== null && latest.id !== handledRoomNoteId) {
      handledRoomNoteId = latest.id
      receiveRoomNote(latest.kind, latest.text, isBannerShown)
      return
    }
    if (!isBannerShown) {
      showWaitingNote()
    }
  })

  function receiveRoomNote(kind: string | null, text: string, isBannerShown: boolean): void {
    if (untrack(() => isStreamShown)) {
      waitingNote = null
      return
    }
    const note = newShownNote(false, kind, text)
    if (isBannerShown) {
      waitingNote = note
      return
    }
    waitingNote = null
    shownNote = note
  }

  function showWaitingNote(): void {
    const note = untrack(() => waitingNote)
    if (note === null) {
      return
    }
    waitingNote = null
    if (!untrack(() => isStreamShown)) {
      shownNote = note
    }
  }

  // "Nothing to undo" (spec 018) has the note's look and place: it replaces
  // any shown note, and shows whatever else shows.
  $effect(() => {
    if (session.undoRefusals === shownUndoRefusals) {
      return
    }
    shownUndoRefusals = session.undoRefusals
    shownNote = newShownNote(true, null, t('undo.nothing'))
  })

  // A note leaves once it has faded, unless a newer one replaced it.
  function onNoteGone(noteId: number): void {
    if (shownNote !== null && shownNote.id === noteId) {
      shownNote = null
    }
  }

  // A tap or a click on a note opens the Salon on its Discussion tab, as
  // « Salon » does, and removes the note.
  function openSalonFromNote(): void {
    shownNote = null
    salonTab = 'discussion'
    setSalonOpen(true)
    void salon?.focusInside()
  }

  function onCellTap(row: number, column: number): void {
    select(selectionAfterCellTap(words, selection, row, column))
  }

  function onClueTap(word: Word): void {
    if (session.snapshot !== null) {
      select(selectionAfterClueTap(shownGrid(session.snapshot.grid, session.pendingEdits), word))
    }
  }

  // ‹ and › of the clue bar do what Shift+Tab and Tab do in the grid (spec
  // 009): the previous or the next unfinished word. With none, nothing changes.
  function selectAfterTab(step: 1 | -1): void {
    if (session.snapshot === null) {
      return
    }
    const grid = shownGrid(session.snapshot.grid, session.pendingEdits)
    select(selectionAfterTab(grid, words, selection, step))
  }

  // ---- The Aide menu's items (spec 043) ----

  // An enabled item closes the menu, puts the focus back on « Aide », then
  // sends its message.
  function aideAction(action: () => void): () => void {
    return () => {
      openPopover = null
      aideButton?.focus()
      action()
    }
  }

  // ---- The Menu's items (spec 043) ----

  // « Inviter »: the Salon on its Joueurs tab, the focus on « Copier le lien ».
  function invite(): void {
    openPopover = null
    salonTab = 'players'
    setSalonOpen(true)
    void salon?.focusCopyLink()
  }

  function openHostSettings(): void {
    openPopover = null
    hostSettings?.open()
  }

  function openAccount(): void {
    openPopover = null
    accountDialog?.open()
  }

  // « Masquer le chrono » or « Afficher le chrono »: sends nothing.
  function toggleTimerFromMenu(): void {
    openPopover = null
    setTimerShown(!isTimerShown)
    menuButton?.focus()
  }

  // A room sheet closed: the focus goes back to « Menu », unless the room is
  // gone, where the room-gone dialog holds the focus.
  function onRoomSheetClosed(): void {
    if (isRoomGone) {
      return
    }
    menuButton?.focus()
  }

  // ---- The Salon's progress and the Joueurs rows (spec 043) ----

  // The words whose every cell shows a letter on the page, pending edits
  // included.
  let filledWords = $derived(countFilledWords(words))

  function countFilledWords(allWords: Word[]): number {
    let count = 0
    for (const word of allWords) {
      if (isWordFullShown(word)) {
        count += 1
      }
    }
    return count
  }

  // The clue of each player's selected word, by player id: mine follows my
  // selection at once; the others' follow their selections (spec 007's word of
  // a cell and a direction). A player with no selection has none.
  let rosterClues = $derived(cluesOfPlayers(session.snapshot, words, activeWord))

  function cluesOfPlayers(
    snapshot: Snapshot | null,
    allWords: Word[],
    myWord: Word | null,
  ): Map<string, string> {
    const clues = new Map<string, string>()
    if (snapshot === null) {
      return clues
    }
    for (const player of snapshot.players) {
      if (player.player_id === snapshot.you) {
        if (myWord !== null) {
          clues.set(player.player_id, myWord.text)
        }
        continue
      }
      const chosen = player.selection
      if (chosen === null) {
        continue
      }
      const word = wordAt(allWords, chosen.row, chosen.column, chosen.direction)
      if (word !== null) {
        clues.set(player.player_id, word.text)
      }
    }
    return clues
  }

  // ---- The play area (spec 043, "Play area and fit") ----

  // The clue bar's height (specs/_design/room.md « Clue bar »).
  const CLUE_BAR_HEIGHT_PX = 34

  // The block of the grid, the clue bar and the status, as large as the play
  // area leaves; and the height of the status band under the bar.
  let playBlock: HTMLElement | null = $state(null)
  let playBlockWidth = $state(0)
  let playBlockHeight = $state(0)
  let statusBandHeight = $state(0)

  function measurePlayBlock(): void {
    if (playBlock !== null) {
      playBlockWidth = playBlock.clientWidth
      playBlockHeight = playBlock.clientHeight
    }
  }

  // Follow the size of the block: a resize, a rotation, a band, the Salon.
  $effect(() => {
    if (playBlock === null) {
      return
    }
    measurePlayBlock()
    const observer = new ResizeObserver(measurePlayBlock)
    observer.observe(playBlock)
    return () => observer.disconnect()
  })

  // After the page changed the play area itself (the Salon column opened or
  // closed), the grid refits at once rather than at the next frame.
  function refitNow(): void {
    flushSync()
    measurePlayBlock()
    flushSync()
    gridViewport?.measureViewport()
    flushSync()
  }

  // The content box of the grid area. In the sheet layout its height is the
  // viewport's height with the Auteurs mode off.
  let gridAreaContent: DOMRectReadOnly | undefined = $state()

  // ---- The Auteurs legend's room (spec 045, "The grid's room") ----

  // The room the legend needs under the grid: 38 px, or its height and its gap
  // when it wraps.
  let wantedLegendRoom = $derived(legendRoom(authorsLegendHeight))
  // True while the mode is on and that room would leave the viewport less than
  // 100 px high: the legend then lies over the viewport's bottom and the grid
  // gives it no room (decision 8). The legend's height does not depend on the
  // grid's size, so the two places do not alternate.
  let isLegendOverGrid = $derived(
    isAuthorsViewOn && viewportHeightWithLegendRoom() < MIN_GRID_VIEWPORT_PX,
  )
  // The room the grid gives the legend: none while the mode is off or while
  // the legend lies over the grid.
  let authorsLegendRoom = $derived(isAuthorsViewOn && !isLegendOverGrid ? wantedLegendRoom : 0)

  // The viewport's height if the grid gave the legend its room: in the sheet
  // layout its height with the mode off less the room; in the column layout
  // the height of the grid's box fitted to the height left less the room.
  function viewportHeightWithLegendRoom(): number {
    if (layout === 'column') {
      const box = columnGridBoxFor(wantedLegendRoom)
      return box === null ? 0 : box.height
    }
    const heightWithModeOff = gridAreaContent === undefined ? 0 : gridAreaContent.height
    return heightWithModeOff - wantedLegendRoom
  }

  // In the column layout the grid viewport is the grid's box at zoom 1, as large
  // as the room left after the clue bar, the status and, while the Auteurs mode
  // is on, the legend's room (spec 045); null in the sheet layout, where the
  // viewport fills its area.
  let columnGridBox = $derived(columnGridBoxFor(authorsLegendRoom))
  // The grid's box with no legend under it: the clue bar keeps its width when
  // the Auteurs mode turns on (spec 045, "The grid's room").
  let columnGridBoxWithoutLegend = $derived(columnGridBoxFor(0))
  // The clue bar is as wide as the grid with no legend, but never narrower than
  // the smaller of CLUE_BAR_MIN_PX and the play area (Decision 12); the full
  // width in the sheet layout.
  let clueBarWidth = $derived(
    columnGridBoxWithoutLegend === null
      ? null
      : Math.max(columnGridBoxWithoutLegend.width, Math.min(CLUE_BAR_MIN_PX, playBlockWidth)),
  )

  // The grid's box in the column layout when `legendRoomPx` is taken from the
  // height left for it; null in the sheet layout.
  function columnGridBoxFor(legendRoomPx: number): { width: number; height: number } | null {
    if (layout !== 'column' || session.snapshot === null) {
      return null
    }
    const heightLeft =
      playBlockHeight -
      PLAY_AREA_PADDING_PX -
      CLUE_BAR_HEIGHT_PX -
      (isStatusUnderClueBar ? statusBandHeight : 0) -
      legendRoomPx
    return fittedGridBox(
      playBlockWidth,
      Math.max(0, heightLeft),
      session.snapshot.grid.width,
      session.snapshot.grid.height,
    )
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

  // ---- What the page sends after a snapshot (platform/realtime.md rules 20, 22) ----

  // An undo, a check or a reveal made while the page is not joined, kept until
  // the next snapshot. `editsBefore` counts the edits made before it: it goes out
  // after them and before any later edit.
  interface KeptRequest {
    message: object
    editsBefore: number
  }

  // A message waiting its turn in the send queue. `request` is set for an undo,
  // a check or a reveal, so that a loss can keep it again; an edit stays pending
  // and is resent anyway, and a select_cell is sent again after the next snapshot.
  interface QueuedMessage {
    message: object
    request: KeptRequest | null
  }

  // Until the socket has its snapshot nothing is sent: edits stay pending, and
  // undos, checks and reveals are kept. They are then sent one every
  // EDIT_SEND_INTERVAL_MS, oldest first, through the send queue.
  let isSynced = false
  let sendQueue: QueuedMessage[] = []
  let sendTimer: ReturnType<typeof setInterval> | undefined
  // How many edits the page has made since it opened.
  let editsMade = 0
  let keptRequests: KeptRequest[] = []

  // Stop the send queue. The requests it still holds are kept again, before any
  // kept since, for the next snapshot.
  function stopSendQueue(): void {
    clearInterval(sendTimer)
    sendTimer = undefined
    const stillQueued: KeptRequest[] = []
    for (const queued of sendQueue) {
      if (queued.request !== null) {
        stillQueued.push(queued.request)
      }
    }
    keptRequests = [...stillQueued, ...keptRequests]
    sendQueue = []
    isSynced = false
  }

  function sendNextQueued(): void {
    const next = sendQueue.shift()
    if (next === undefined) {
      clearInterval(sendTimer)
      sendTimer = undefined
      return
    }
    send(next.message)
  }

  // Send an edit now, or behind the messages still queued. Before the snapshot of
  // the socket nothing is sent: the edit is pending and is resent with the others.
  function sendEdit(message: object): void {
    if (!isSynced) {
      return
    }
    if (sendTimer === undefined) {
      send(message)
      return
    }
    sendQueue.push({ message, request: null })
  }

  // Send an undo, a check or a reveal after the edits pending when it is made:
  // kept while the page is not joined, queued behind a running resend, else sent
  // at once.
  function sendRequest(message: object): void {
    const request: KeptRequest = { message, editsBefore: editsMade }
    if (!isSynced) {
      keptRequests.push(request)
      return
    }
    if (sendTimer === undefined) {
      send(message)
      return
    }
    sendQueue.push({ message, request })
  }

  // Stop listening to a socket and close it.
  function dropSocket(dropped: WebSocket): void {
    if (socket === dropped) {
      stopSendQueue()
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
    if (isRoomGone) {
      leaveDeletedRoom()
    }
  }

  // ---- The room gone (client/hud.md rule 16) ----

  // The room was deleted once it had shown: the room-gone dialog covers the
  // page. Before the first snapshot a deletion is the entry card instead.
  let isRoomGone = $derived(session.snapshot !== null && session.status === 'not_found')

  // Close what is open over the room and drop the letters waiting to be sent,
  // before the room-gone dialog shows. The Salon column stays as it is.
  function leaveDeletedRoom(): void {
    openPopover = null
    isSheetSalonOpen = false
    isPickerOpen = false
    isRecapOpen = false
    hostSettings?.close()
    accountDialog?.close()
    stopSendQueue()
    session.pendingEdits = []
    keptRequests = []
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

  // My pending edits, each as the message of its kind and with the base_seq it
  // had, and the kept requests, in the order they were made. The pending edits
  // are the newest edits made: counting from 0, the first of them is edit
  // number editsMade minus their count.
  function pendingInOrder(): QueuedMessage[] {
    const ordered: QueuedMessage[] = []
    const firstEditNumber = editsMade - session.pendingEdits.length
    let requestIndex = 0
    session.pendingEdits.forEach((edit, index) => {
      const editNumber = firstEditNumber + index
      // The requests made before this edit go before it.
      while (
        requestIndex < keptRequests.length &&
        keptRequests[requestIndex].editsBefore <= editNumber
      ) {
        const request = keptRequests[requestIndex]
        ordered.push({ message: request.message, request })
        requestIndex += 1
      }
      ordered.push({ message: editMessage(edit, edit.baseSeq), request: null })
    })
    for (const request of keptRequests.slice(requestIndex)) {
      ordered.push({ message: request.message, request })
    }
    return ordered
  }

  // Once the socket has its snapshot, send what waited: after a loss the
  // selection first (the server cleared it), then the pending edits and the
  // kept requests in order. They are paced, the first one at once, then one
  // every EDIT_SEND_INTERVAL_MS.
  function sendAfterSnapshot(isAfterLoss: boolean): void {
    stopSendQueue()
    isSynced = true
    if (isAfterLoss && selection !== null) {
      sendQueue.push({ message: selectCellMessage(selection), request: null })
    }
    sendQueue.push(...pendingInOrder())
    keptRequests = []
    sendTimer = setInterval(sendNextQueued, EDIT_SEND_INTERVAL_MS)
    sendNextQueued()
  }

  // The first message of a socket: the join of the stored identity, or the form.
  function joinOnOpen(opened: WebSocket): void {
    const plan = planAutomaticJoin(code, t('room.default_nickname'), heldIdentity)
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
      // After a loss: the first snapshot of this socket (isSynced is still
      // false), when the page had a snapshot on an earlier socket. A second
      // snapshot on the same socket is not one.
      const isAfterLoss = snapshotBefore !== null && !isSynced
      sendAfterSnapshot(isAfterLoss)
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

<svelte:window bind:innerWidth={windowWidth} bind:innerHeight={windowHeight} />

<!-- The completion status (spec 026, spec 043, spec 044): its text, after the
     ✓ pictogram once solved, and « Voir le bilan » in the band of a solved grid.
     The page shows it in one of two places, never both: see isStatusInClueBar
     and isStatusUnderClueBar. Only the full-but-wrong status sits in the clue
     bar's row, since a solved page has no keyboard. -->
{#snippet gridStatusContent()}
  {@const statusText =
    gridStatus === 'solved' ? t('completion.solved') : t('completion.full_wrong')}
  <span class="grid-status-text" data-testid="grid-status-text"
    >{#if gridStatus === 'solved'}<span class="status-check" aria-hidden="true"></span
      >{/if}{statusText}</span
  >
  {#if gridStatus === 'solved'}
    <button
      type="button"
      class="nock-button nock-button-primary recap-open"
      data-testid="recap-open"
      bind:this={recapOpenButton}
      onclick={() => (isRecapOpen = true)}>{t('recap.open')}</button
    >
  {/if}
{/snippet}

{#snippet statusInRow()}
  <p class="grid-status in-row" data-testid="grid-status" data-state={gridStatus} role="status">
    {@render gridStatusContent()}
  </p>
{/snippet}

<!-- The entry pages (spec 046, "Entry pages"): the room code line, then the
     nickname card or the card of a status that refuses entry. -->
{#snippet entryPage()}
  <EntryFrame>
    <h1 class="room-code-line">{t('room.heading', { code })}</h1>
    {#if isEntryCardShown}
      <div class="nock-card" data-testid="entry-card">
        <p class="nock-card-title" data-testid="room-status">
          {t(`room.status.${session.status}`)}
        </p>
        {#if session.status === 'not_found'}
          <!-- An expired room is deleted (spec 032), so it reads as one that
               never existed: the line says why a room may be gone (P3). -->
          <p class="nock-card-detail" data-testid="entry-detail">
            {t('room.status.not_found_detail')}
          </p>
        {/if}
        <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1).
             "Voir les grilles" is primary where it is the only way on. -->
        <a
          class="nock-button"
          class:nock-button-primary={session.status === 'not_found'}
          class:nock-button-secondary={session.status !== 'not_found'}
          data-testid="entry-home"
          href="/"
          tabindex="0">{t('share.home')}</a
        >
      </div>
    {:else}
      <form class="nock-card" data-testid="nickname-form" onsubmit={submitNickname}>
        <h2 class="nock-card-title">{t('join.heading')}</h2>
        <div class="nock-field">
          <label for="nickname-input">{t('join.nickname_label')}</label>
          <input
            id="nickname-input"
            class="nock-text-input nickname-input"
            data-testid="nickname-input"
            type="text"
            autocomplete="nickname"
            placeholder={t('room.default_nickname')}
            aria-invalid={shownError !== null ? 'true' : undefined}
            bind:value={nicknameText}
          />
        </div>
        {#if shownError !== null}
          <p class="nock-error-line nickname-error" data-testid="nickname-error" role="alert">
            {shownError === 'length' ? t('join.error.length') : t('join.error.characters')}
          </p>
        {/if}
        <button
          type="submit"
          class="nock-button nock-button-primary"
          data-testid="nickname-submit"
          disabled={session.status !== 'nickname'}>{t('join.submit')}</button
        >
      </form>
    {/if}
  </EntryFrame>
  {#if !isEntryCardShown}
    <!-- The status beside the nickname card: read but not seen. -->
    <p class="visually-hidden" data-testid="room-status">{t(`room.status.${session.status}`)}</p>
  {/if}
{/snippet}

<main
  class="room-page"
  class:entry-page={isEntryPage}
  data-testid="room-page"
  data-room-code={code}
  data-status={session.status}
  data-layout={isEntryPage ? undefined : layout}
  data-you={session.snapshot === null ? '' : session.snapshot.you}
  data-seq={session.seq === null ? '' : String(session.seq)}
  data-catch-up={session.catchUpLabel}
  data-solved={String(session.solved)}
  data-pending={String(session.pending.length)}
  data-grid={gridLabel(session)}
>
  {#if isEntryPage}
    {@render entryPage()}
  {:else}
    <!-- The room's heading: read but not seen while the room opens and once it
         shows (spec 043, spec 046). -->
    <h1 class="visually-hidden">{t('room.heading', { code })}</h1>
    <RoomTopBar
      form={topBarForm}
      {isOpening}
      {isTimerShown}
      timerBaseMs={session.timerBaseMs}
      isTimerRunning={session.timerRunning}
      timerAnchor={session.timerAnchor}
      isSolved={session.solved}
      {isPencilMode}
      {isTouchScreen}
      {isKeyboardShown}
      isAideOpen={openPopover === 'aide'}
      isMenuOpen={openPopover === 'menu'}
      {isSalonOpen}
      {unreadLines}
      {hasNewEvents}
      {salonLabel}
      bind:aideButton
      bind:menuButton
      bind:chatToggle
      onShowTimer={() => setTimerShown(true)}
      {onUndo}
      onTogglePencil={togglePencilMode}
      onToggleKeyboard={toggleKeyboard}
      onToggleAide={() => togglePopover('aide')}
      onToggleSalon={toggleSalon}
      onToggleMenu={() => togglePopover('menu')}
    />
  {/if}
  {#if session.snapshot !== null}
    <RoomPopover
      testId="aide-menu"
      label={t('topbar.aide')}
      isOpen={openPopover === 'aide'}
      form={topBarForm}
      side="left"
      anchor={aideButton}
      bind:element={aideMenu}
      onEscape={closePopoverToButton}
    >
      <AideMenu
        isConfirmShown={!isConfirmPencilDisabled}
        {isHelpShown}
        isCheckLetterDisabled={session.solved || selection === null}
        isCheckWordDisabled={session.solved || activeWord === null}
        isCheckGridDisabled={session.solved || isVoteOpen}
        {isRevealLetterDisabled}
        {isRevealWordDisabled}
        {lettersLeft}
        {wordsLeft}
        onConfirmPencil={aideAction(onConfirmPencil)}
        onCheckLetter={aideAction(onCheckLetter)}
        onCheckWord={aideAction(onCheckWord)}
        onCheckGrid={aideAction(() => onCheck({ scope: 'grid' }))}
        onRevealLetter={aideAction(onRevealLetter)}
        onRevealWord={aideAction(onRevealWord)}
      />
    </RoomPopover>
    <RoomPopover
      testId="room-menu"
      label={t('topbar.menu')}
      isOpen={openPopover === 'menu'}
      form={topBarForm}
      side="right"
      anchor={menuButton}
      bind:element={roomMenu}
      onEscape={closePopoverToButton}
    >
      <RoomMenu
        {isAuthorsViewOn}
        {isOthersTintOn}
        {isAccessibilityOn}
        {isHost}
        isAccountShown={accountStatus !== null}
        {isTimerShown}
        onToggleAuthors={toggleAuthorsView}
        onToggleOthersTint={toggleOthersTint}
        onToggleAccessibility={toggleAccessibility}
        onInvite={invite}
        onOpenHostSettings={openHostSettings}
        onOpenAccount={openAccount}
        onToggleTimer={toggleTimerFromMenu}
      />
    </RoomPopover>
  {/if}
  {#if session.status === 'reconnecting'}
    <p class="room-band connection-banner" data-testid="connection-banner" role="status">
      <span class="connection-dot" data-testid="connection-dot" aria-hidden="true"></span><span
        >{t('room.banner.offline')}</span
      >
    </p>
  {/if}
  {#if isOpening}
    <!-- While the room opens, the grid area holds only its status, one muted
         line (spec 046, P2). -->
    <div class="opening-area" data-testid="grid-area">
      <p class="nock-state-line" data-testid="room-status">{t(`room.status.${session.status}`)}</p>
    </div>
  {:else if session.snapshot !== null && !isRoomGone}
    <!-- Once the room shows, a joined or reconnecting status is read but not
         seen; any other status but the room gone, which is the room-gone
         dialog, is a band under the top bar (spec 043, client/hud.md rule 7). -->
    <p
      class="room-status"
      class:visually-hidden={session.status === 'joined' || session.status === 'reconnecting'}
      class:room-band={session.status !== 'joined' && session.status !== 'reconnecting'}
      data-testid="room-status"
    >
      {t(`room.status.${session.status}`)}
    </p>
  {/if}
  {#if session.snapshot !== null}
    <div class="room-body {layout}">
      <div class="play-area">
        <div class="play-block" bind:this={playBlock}>
          <!-- The vote banner is laid over the top of the grid viewport, so
               showing it changes no layout; it comes before the grid in document
               order (spec 025, spec 035). -->
          <div
            class="grid-area"
            data-testid="grid-area"
            style:width={columnGridBox === null ? null : `${columnGridBox.width}px`}
            style:height={columnGridBox === null
              ? null
              : `${columnGridBox.height + authorsLegendRoom}px`}
            bind:contentRect={gridAreaContent}
          >
            <div
              class="visually-hidden"
              data-testid="vote-announcement"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >{voteAnnouncement}</div>
            {#if isVoteBannerShown}
              <!-- The question, the row of the ballot (or the line that takes
                   its place) with the seconds left on its right, then the bar
                   of the time left (spec 047). -->
              <div
                class="vote-banner {layout}"
                data-testid="vote-banner"
                role="group"
                aria-labelledby="vote-question"
                bind:this={voteBanner}
                bind:offsetHeight={voteBannerHeight}
              >
                <p id="vote-question" class="vote-question" data-testid="vote-question">
                  {voteQuestionText}
                </p>
                <div class="vote-row" data-testid="vote-row">
                  {#if isMyRequest || hasVoted}
                    <!-- Not a Tab stop, but it takes the focus after a ballot. -->
                    <span
                      class="vote-status"
                      data-testid="vote-status"
                      tabindex="-1"
                      bind:this={voteStatus}
                      >{isMyRequest ? t('vote.waiting') : t('vote.cast')}</span
                    >
                  {:else}
                    <button
                      type="button"
                      class="nock-button nock-button-primary vote-button"
                      data-testid="vote-yes"
                      disabled={isVotingOffline}
                      onclick={() => castVote(true)}>{t('vote.yes')}</button
                    >
                    <button
                      type="button"
                      class="nock-button nock-button-secondary vote-button"
                      data-testid="vote-no"
                      disabled={isVotingOffline}
                      onclick={() => castVote(false)}>{t('vote.no')}</button
                    >
                  {/if}
                  {#if countdown !== null}
                    <span class="vote-seconds" data-testid="vote-seconds"
                      >{t('vote.seconds_left', { count: countdown.seconds })}</span
                    >
                  {/if}
                </div>
                {#if countdown !== null}
                  <div class="vote-timebar" data-testid="vote-timebar" aria-hidden="true">
                    <div
                      class="vote-timebar-fill"
                      data-testid="vote-timebar-fill"
                      style:width="{countdown.share * 100}%"
                    ></div>
                  </div>
                {/if}
              </div>
            {/if}
            {#if shownNote !== null}
              {#key shownNote.id}
                <RoomNote
                  note={shownNote}
                  {layout}
                  bannerHeight={isVoteBannerShown ? voteBannerHeight : 0}
                  onOpen={openSalonFromNote}
                  onGone={onNoteGone}
                />
              {/key}
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
              legendNames={authorsLegendNames}
              legendRoom={authorsLegendRoom}
              {isLegendOverGrid}
              legendMaxWidth={clueBarWidth}
              bind:legendHeight={authorsLegendHeight}
              {clueFlags}
              {clueReactions}
            />
          </div>
          <ClueBar
            {activeWord}
            width={clueBarWidth}
            isPickerOpen={isPickerOpen}
            {isReactDisabled}
            {isFlagPressed}
            {isFlagDisabled}
            bind:reactButton
            onPrevious={() => selectAfterTab(-1)}
            onNext={() => selectAfterTab(1)}
            onToggleReactions={toggleReactionPicker}
            {onFlag}
            status={isStatusInClueBar ? statusInRow : undefined}
          />
          {#if isPickerOpen}
            <ReactionPicker
              viewport={gridViewport?.viewportElement() ?? null}
              isPaced={isReactionPaced}
              isButtonDisabled={isReactDisabled}
              onPick={sendReaction}
              onClose={closeReactionPicker}
              onDismiss={dismissReactionPicker}
              onFocusButton={() => reactButton?.focus()}
              onFocusGrid={() => gridViewport?.focusGrid()}
            />
          {/if}
          {#if isStatusUnderClueBar}
            <p
              class="grid-status band"
              data-testid="grid-status"
              data-state={gridStatus}
              role="status"
              style:width={clueBarWidth === null ? null : `${clueBarWidth}px`}
              bind:offsetHeight={statusBandHeight}
            >
              {@render gridStatusContent()}
            </p>
          {/if}
        </div>
        {#if isKeyboardShown}
          <InAppKeyboard
            {isPencilMode}
            {onLetter}
            {onErase}
            onTogglePencil={togglePencilMode}
            onSwap={swapDirection}
            onKeyUsed={() => gridViewport?.focusGrid()}
          />
        {/if}
      </div>
      <Salon
        bind:this={salon}
        {layout}
        isOpen={isSalonOpen}
        bind:tab={salonTab}
        {filledWords}
        totalWords={words.length}
        entries={stream}
        names={session.names}
        colours={playerColours}
        players={session.snapshot.players}
        {you}
        {isHost}
        {isMuted}
        isPaced={isChatPaced}
        isJoined={session.status === 'joined'}
        {isAccessibilityOn}
        clues={rosterClues}
        {shareLink}
        bind:chatText
        onSend={sendChat}
        onMute={toggleMute}
        onRemove={removePlayer}
        onEscape={onSalonEscape}
        onMuted={() => chatToggle?.focus()}
      />
    </div>
    {#if isScrimShown}
      <!-- A pointer press on the scrim keeps the focus where it is. -->
      <div
        class="room-scrim"
        data-testid="room-scrim"
        aria-hidden="true"
        onmousedown={(event) => event.preventDefault()}
        onclick={closeOverlays}
      ></div>
    {/if}
    {#if isHost}
      <HostSettings
        bind:this={hostSettings}
        {layout}
        isLocked={isLocked}
        bind:helpMode={helpModeInput}
        bind:letters={lettersInput}
        bind:words={wordsInput}
        onToggleLock={toggleLock}
        onSave={saveSettings}
        onClosed={onRoomSheetClosed}
      />
    {/if}
    {#if accountStatus !== null}
      <AccountDialog
        bind:this={accountDialog}
        {layout}
        status={accountStatus}
        room={{ code, resume_token: session.snapshot.resume_token }}
        onClosed={onRoomSheetClosed}
      />
    {/if}
  {/if}
  {#if isRecapOpen}
    <RecapDialog
      {code}
      {you}
      {playerColours}
      {layout}
      {isAccessibilityOn}
      onClose={closeRecap}
    />
  {/if}
  {#if isRoomGone}
    <RoomGoneDialog {layout} />
  {/if}
</main>

<style>
  /* The room fills the window: the top bar, the bands, then the play area and
     the Salon (spec 043); while it opens, the top bar and the opening area
     (spec 046). Nothing scrolls. */
  .room-page {
    position: relative;
    box-sizing: border-box;
    max-width: none;
    margin: 0;
    padding: 0;
    height: 100vh;
    height: 100dvh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* An entry page is a plain page: the entry frame, at least the window's
     height, scrolling when its card is higher. */
  .room-page.entry-page {
    height: auto;
    min-height: 100vh;
    min-height: 100dvh;
    overflow: visible;
  }

  .room-status {
    margin: 0;
  }

  /* The nickname shows in capitals, the placeholder too, while the value keeps
     the text as typed, so input methods and the caret work as usual (spec 012,
     room page flow step 3). */
  .nickname-input {
    text-transform: uppercase;
  }

  /* The refused nickname's reason, right under the field. */
  .nickname-error {
    margin-top: -6px;
  }

  /* While the room opens (spec 046): all the height under the top bar, its
     status line centred in it. */
  .opening-area {
    flex: 1 1 0;
    min-height: 0;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    text-align: center;
  }

  /* ---- The bands under the top bar (spec 043) ---- */

  /* The connection band, and the status band of a final status: full width, in
     the flow, so they push the play area down. */
  .room-band {
    flex: none;
    box-sizing: border-box;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    width: 100%;
    margin: 0;
    padding: 8px 12px;
    font: 500 0.85rem/1.3 var(--nock-font-ui);
    color: var(--nock-ink);
    background: var(--nock-clue-bg);
    border-bottom: 1px solid var(--nock-line);
  }

  .connection-dot {
    flex: none;
    width: 8px;
    height: 8px;
    margin-top: 5px;
    border-radius: 50%;
    background: var(--nock-red);
  }

  /* ---- The body: the play area, and the Salon column ---- */

  .room-body {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
  }

  .play-area {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  /* The column layout's play area has a padding of 12 px; its top padding is
     the grid area's, so the grid area starts right under the top bar and the
     bands. */
  .column .play-area {
    padding: 0 12px 12px;
  }

  /* The grid, the clue bar and the status: in the column layout a block
     centred in the play area. */
  .play-block {
    position: relative;
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .column .play-block {
    align-items: center;
  }

  /* Two spacers centre the block; with no room left (for a frame, while the
     grid refits) they shrink to nothing and the block starts at the top. */
  .column .play-block::before,
  .column .play-block::after {
    content: '';
    flex: 1 1 0;
  }

  /* The area of the grid: it holds the vote banner over the viewport's top
     edge, and the Auteurs legend under the viewport (spec 045). In the sheet
     layout it takes the height left and the viewport is its box less 8 px on
     each side; in the column layout it is the grid's box at zoom 1 and its
     12 px of top padding. While the Auteurs mode is on, the legend's room is
     taken from the viewport's height (sheet) or added under the grid's box
     (column). */
  .grid-area {
    position: relative;
    box-sizing: content-box;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .sheet .grid-area {
    flex: 1 1 0;
    padding: 8px;
  }

  .column .grid-area {
    flex: none;
    padding-top: 12px;
  }

  /* The in-app keyboard spans the column layout's play area at its bottom. */
  .column .play-area > :global(.keyboard) {
    margin: 10px -12px -12px;
  }

  /* ---- The vote banner (spec 025, spec 047; specs/_design/overlays.md « Vote ») ----

     Over the grid (spec 025 decision 9): absolutely placed, so it takes no
     height from the grid. The vote wins over the Salon sheet and the scrim
     (spec 022 decision 16), which come later in the page on layer 8: it is
     drawn one layer above them. Its top, left and right edges are 8 px inside
     the grid area: `grid-area` in the sheet layout (its 8 px padding, so the
     banner lies on the viewport's edges), the viewport in the column layout
     (under the grid area's 12 px top padding). */
  .vote-banner {
    position: absolute;
    left: 8px;
    right: 8px;
    z-index: 9;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border: 2px solid var(--nock-navy);
    border-radius: 10px;
    background: var(--nock-white);
    box-shadow: 0 10px 24px -12px var(--nock-shadow);
  }

  .vote-banner.sheet {
    top: 8px;
  }

  .vote-banner.column {
    top: 20px;
  }

  .vote-question {
    margin: 0;
    font: 600 0.95rem/1.3 var(--nock-font-ui);
    color: var(--nock-ink);
  }

  /* The ballot, or the line that takes its place, then the seconds on the
     right. */
  .vote-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 31px;
  }

  .vote-button {
    flex: none;
    padding: 7px 16px;
  }

  .vote-status {
    min-width: 0;
    font: 500 0.85rem/1.3 var(--nock-font-ui);
    color: var(--nock-muted);
  }

  .vote-seconds {
    flex: none;
    margin-left: auto;
    font: 500 0.85rem/1 var(--nock-font-ui);
    color: var(--nock-muted);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  /* The time left: a word-blue track and its navy fill, which moves in steps
     with no transition (spec 047, Decision 3). */
  .vote-timebar {
    height: 4px;
    border-radius: 2px;
    background: var(--nock-word);
    overflow: hidden;
  }

  .vote-timebar-fill {
    height: 100%;
    background: var(--nock-navy);
    transition: none;
  }

  /* ---- The completion status (spec 026; specs/_design/overlays.md « End of grid ») ---- */

  .grid-status {
    margin: 0;
    font: 600 0.95rem/1.2 var(--nock-font-ui);
  }

  /* The end band under the clue bar, as wide as the bar. */
  .grid-status.band {
    flex: none;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 10px;
    max-width: 100%;
    padding: 8px 12px;
  }

  .grid-status.band[data-state='solved'] {
    color: var(--nock-green);
    background: var(--nock-green-bg);
  }

  .grid-status.band[data-state='full_wrong'] {
    color: var(--nock-navy);
    background: var(--nock-clue-bg);
  }

  /* In the clue bar's row: white text on one line, after the clue. */
  .grid-status.in-row {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 8px;
    white-space: nowrap;
    color: var(--nock-white);
  }

  /* The text of the band, after its pictogram: it wraps when the band is too
     narrow for it and "Voir le bilan" on one line (spec 047). */
  .grid-status.band .grid-status-text {
    flex: 0 1 auto;
    min-width: 0;
  }

  /* The check mark of a solved grid: a pictogram drawn by CSS, never read, a space
     before the text. */
  .status-check::before {
    content: '✓';
  }

  .status-check {
    margin-right: 0.25em;
  }

  /* "Voir le bilan" keeps its whole label on one line, on the band's
     right. */
  .recap-open {
    flex: none;
    margin-left: auto;
    padding: 7px 12px;
    font-size: 0.85rem;
    white-space: nowrap;
  }

  /* ---- The scrim of the sheet layout (layer 7) ---- */

  .room-scrim {
    position: fixed;
    top: 54px;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 7;
    background: var(--nock-scrim);
  }
</style>
