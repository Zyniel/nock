<script lang="ts">
  import { flushSync, onMount, tick, untrack } from 'svelte'
  import AccountDialog from './AccountDialog.svelte'
  import AideMenu from './AideMenu.svelte'
  import ClueBar from './ClueBar.svelte'
  import GridViewport from './GridViewport.svelte'
  import HostSettings from './HostSettings.svelte'
  import InAppKeyboard from './InAppKeyboard.svelte'
  import ReactionPicker from './ReactionPicker.svelte'
  import RecapDialog from './RecapDialog.svelte'
  import RoomMenu from './RoomMenu.svelte'
  import RoomNote from './RoomNote.svelte'
  import type { ShownNote } from './RoomNote.svelte'
  import RoomPopover from './RoomPopover.svelte'
  import RoomTopBar from './RoomTopBar.svelte'
  import Salon from './Salon.svelte'
  import { t } from './i18n'
  import { fetchAccountStatus, linkRoom, type AccountStatus } from './account'
  import { nameOf, streamEntries } from './activityFeed'
  import { authorLine, colourByPlayer, shownAuthorOf } from './authorsView'
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
  import { checkNickname, planAutomaticJoin, readNickname, writeIdentity, writeNickname } from './joinRules'
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
  import { fittedGridBox } from './gridLayout'
  import {
    computeWords,
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
  // The two layouts of the room (spec 043, "Which layout"): the column layout
  // needs a landscape window at least COLUMN_MIN_WIDTH_PX wide and more than
  // LOW_WINDOW_PX high, or a landscape window at most LOW_WINDOW_PX high with no
  // in-app keyboard.
  const COLUMN_MIN_WIDTH_PX = 900
  const LOW_WINDOW_PX = 500
  // The Salon column closed by the player, for every room of this browser.
  const SALON_CLOSED_KEY = 'nock.salon_closed'
  const SALON_CLOSED_VALUE = 'true'
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

  // ---- The layout (spec 043) ----

  // The window's size, followed through each resize and rotation
  // (<svelte:window> below).
  let windowWidth = $state(window.innerWidth)
  let windowHeight = $state(window.innerHeight)

  // A low window: at most 500 px high, a phone on its side.
  let isLowWindow = $derived(windowHeight <= LOW_WINDOW_PX)
  let layout = $derived(layoutOf(windowWidth, windowHeight))
  // The phone top bar is the sheet layout's, and the column layout's on a low
  // window, where the computer top bar would not fit.
  let topBarForm: 'phone' | 'computer' = $derived(
    layout === 'sheet' || isLowWindow ? 'phone' : 'computer',
  )

  // "column" for a landscape window that is wide enough and not low, or low
  // with no in-app keyboard; "sheet" otherwise.
  function layoutOf(width: number, height: number): 'sheet' | 'column' {
    const isLandscape = width > height
    if (!isLandscape) {
      return 'sheet'
    }
    const isWideWindow = width >= COLUMN_MIN_WIDTH_PX && height > LOW_WINDOW_PX
    const isLowWithoutKeyboard = height <= LOW_WINDOW_PX && !isTouchScreen
    if (isWideWindow || isLowWithoutKeyboard) {
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
  let lastLayout: 'sheet' | 'column' = layoutOf(window.innerWidth, window.innerHeight)
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
  // Where the status shows (spec 026 AC-10, spec 043 AC-27): in the clue bar's
  // row while the in-app keyboard shows on a low window, where a band would take
  // the grid's height; under the bar, as a band, everywhere else. Until spec 044
  // hides the keyboard on a solved page, a solved status takes the row too.
  let isStatusInClueBar = $derived(
    gridStatus !== null && layout === 'sheet' && isLowWindow && isTouchScreen,
  )
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
  // The banner shows the open vote, or for VOTE_RESULT_MS how the last one
  // ended; never once the grid is solved.
  let isVoteBannerShown = $derived(
    !session.solved && (openVote !== null || session.closedVote !== null),
  )
  // « Réagir » is disabled while the vote banner shows, so the picker never
  // covers the vote's buttons (spec 043, Decision 10).
  let isReactDisabled = $derived(activeWord === null || isMuted || isVoteBannerShown)
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

  // A new note of the room: none while the stream shows; while the vote banner
  // is on the page it waits, replacing any older waiting note.
  $effect(() => {
    const latest = session.latestNote
    if (latest === null || latest.id === handledRoomNoteId) {
      return
    }
    handledRoomNoteId = latest.id
    if (untrack(() => isStreamShown)) {
      return
    }
    const note = newShownNote(false, latest.kind, latest.text)
    if (untrack(() => isVoteBannerShown)) {
      waitingNote = note
      return
    }
    shownNote = note
  })

  // Once the banner has gone, the note that waited shows, unless the stream
  // shows by then: the player reads the same line there.
  $effect(() => {
    if (isVoteBannerShown || waitingNote === null) {
      return
    }
    const note = waitingNote
    waitingNote = null
    if (!untrack(() => isStreamShown)) {
      shownNote = note
    }
  })

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

  // A room sheet closed: the focus goes back to « Menu ».
  function onRoomSheetClosed(): void {
    menuButton?.focus()
  }

  // ---- The Salon's progress and the Joueurs rows (spec 043) ----

  // The words whose every cell shows a letter on the page, pending edits
  // included.
  let filledWords = $derived(countFilledWords(session.snapshot, words, session.pendingEdits))

  function countFilledWords(
    snapshot: Snapshot | null,
    allWords: Word[],
    pendingEdits: PendingEdit[],
  ): number {
    if (snapshot === null) {
      return 0
    }
    const shownLetters = new Map<string, string | null>()
    for (const cell of shownGrid(snapshot.grid, pendingEdits).cells) {
      if (cell.type === 'letter') {
        shownLetters.set(`${cell.row},${cell.column}`, cell.letter)
      }
    }
    let count = 0
    for (const word of allWords) {
      let isFull = true
      for (const position of word.cells) {
        const letter = shownLetters.get(`${position.row},${position.column}`)
        if (letter === null || letter === undefined) {
          isFull = false
        }
      }
      if (isFull) {
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

  // The clue bar's height (_design.md section 8).
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

  // In the column layout the grid viewport is the grid's box at zoom 1, as large
  // as the room left after the clue bar and the status; null in the sheet
  // layout, where the viewport fills its area.
  let columnGridBox = $derived(
    layout === 'column' && session.snapshot !== null
      ? fittedGridBox(
          playBlockWidth,
          Math.max(
            0,
            playBlockHeight -
              PLAY_AREA_PADDING_PX -
              CLUE_BAR_HEIGHT_PX -
              (isStatusUnderClueBar ? statusBandHeight : 0),
          ),
          session.snapshot.grid.width,
          session.snapshot.grid.height,
        )
      : null,
  )
  // The clue bar is as wide as the grid, but never narrower than the smaller of
  // CLUE_BAR_MIN_PX and the play area (Decision 12); the full width in the sheet
  // layout.
  let clueBarWidth = $derived(
    columnGridBox === null
      ? null
      : Math.max(columnGridBox.width, Math.min(CLUE_BAR_MIN_PX, playBlockWidth)),
  )

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

<svelte:window bind:innerWidth={windowWidth} bind:innerHeight={windowHeight} />

<!-- The completion status (spec 026, spec 043): its text, after the ✓
     pictogram once solved, and « Voir le bilan » in the band of a solved grid.
     The page shows it in one of two places, never both: see isStatusInClueBar
     and isStatusUnderClueBar. -->
{#snippet gridStatusContent(isInRow: boolean)}
  {#if gridStatus === 'solved'}
    <span class="status-check" aria-hidden="true"></span>
  {/if}
  <span class="grid-status-text"
    >{gridStatus === 'solved' ? t('completion.solved') : t('completion.full_wrong')}</span
  >
  <!-- « Voir le bilan »: the primary button in the band, the secondary one in
       the clue bar's row (spec 043 AC-27). -->
  {#if gridStatus === 'solved'}
    <button
      type="button"
      class="nock-button recap-open"
      class:nock-button-primary={!isInRow}
      class:nock-button-secondary={isInRow}
      data-testid="recap-open"
      bind:this={recapOpenButton}
      onclick={() => (isRecapOpen = true)}>{t('recap.open')}</button
    >
  {/if}
{/snippet}

{#snippet statusInRow()}
  <p class="grid-status in-row" data-testid="grid-status" data-state={gridStatus} role="status">
    {@render gridStatusContent(true)}
  </p>
{/snippet}

<main
  class="room-page"
  class:with-snapshot={session.snapshot !== null}
  data-testid="room-page"
  data-room-code={code}
  data-status={session.status}
  data-layout={session.snapshot === null ? undefined : layout}
  data-you={session.snapshot === null ? '' : session.snapshot.you}
  data-seq={session.seq === null ? '' : String(session.seq)}
  data-catch-up={session.catchUpLabel}
  data-solved={String(session.solved)}
  data-pending={String(session.pending.length)}
  data-grid={gridLabel(session)}
>
  <!-- The room's heading: read but not seen once the room shows (spec 043). -->
  <h1 class:visually-hidden={session.snapshot !== null}>{t('room.heading', { code })}</h1>
  {#if session.snapshot !== null}
    <RoomTopBar
      form={topBarForm}
      {isTimerShown}
      timerBaseMs={session.timerBaseMs}
      isTimerRunning={session.timerRunning}
      timerAnchor={session.timerAnchor}
      isSolved={session.solved}
      {isPencilMode}
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
      onToggleAide={() => togglePopover('aide')}
      onToggleSalon={toggleSalon}
      onToggleMenu={() => togglePopover('menu')}
    />
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
  <!-- Once the room shows, a joined or reconnecting status is read but not
       seen; any other status is a band under the top bar (spec 043). -->
  <p
    class="room-status"
    class:visually-hidden={session.snapshot !== null &&
      (session.status === 'joined' || session.status === 'reconnecting')}
    class:room-band={session.snapshot !== null &&
      session.status !== 'joined' &&
      session.status !== 'reconnecting'}
    data-testid="room-status"
  >
    {t(`room.status.${session.status}`)}
  </p>
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
            style:height={columnGridBox === null ? null : `${columnGridBox.height}px`}
          >
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
                        bind:this={voteStatus}
                        >{isMyRequest ? t('vote.waiting') : t('vote.cast')}</span
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
                  <p id="vote-result" class="vote-text" data-testid="vote-result">
                    {voteResultText}
                  </p>
                {/if}
              </div>
            {/if}
            {#if shownNote !== null}
              {#key shownNote.id}
                <RoomNote
                  note={shownNote}
                  {layout}
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
              {clueFlags}
              {clueReactions}
            />
          </div>
          <ClueBar
            {activeWord}
            authorLine={selectedAuthorLine}
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
              {@render gridStatusContent(false)}
            </p>
          {/if}
        </div>
        {#if isTouchScreen}
          <InAppKeyboard {onLetter} {onErase} onKeyUsed={() => gridViewport?.focusGrid()} />
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
    <RecapDialog {code} {you} {playerColours} onClose={closeRecap} />
  {/if}
</main>

<style>
  /* Before the first snapshot the page keeps its plain look: the heading, the
     status and the nickname form. */
  .room-page {
    position: relative;
    box-sizing: border-box;
    padding: 0.5rem 1rem;
    height: 100vh;
    height: 100dvh;
    display: flex;
    flex-direction: column;
  }

  /* Once the room shows, it fills the window: the top bar, the bands, then the
     play area and the Salon (spec 043). Nothing scrolls. */
  .room-page.with-snapshot {
    max-width: none;
    margin: 0;
    padding: 0;
    overflow: hidden;
  }

  .room-page h1 {
    margin: 0;
    font-size: 1.25rem;
  }

  .room-status {
    margin: 0;
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

  .nickname-error {
    margin: 0;
    color: var(--nock-red);
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
     edge. In the sheet layout it takes the height left and the viewport is its
     box less 8 px on each side; in the column layout it is the grid's box at
     zoom 1 and its 12 px of top padding. */
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

  /* Over the grid (spec 025 decision 9): absolutely placed, so it takes no
     height from the grid. The vote wins over the Salon sheet and the scrim
     (spec 022 decision 16), which come later in the page on layer 8: it is
     drawn one layer above them. */
  .vote-banner {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 9;
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

  /* It lies over the top of the grid viewport, inside the grid area's
     padding. */
  .sheet .vote-banner {
    top: 8px;
    left: 8px;
    right: 8px;
  }

  .column .vote-banner {
    top: 12px;
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

  /* ---- The completion status (spec 026; _design.md section 9) ---- */

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

  /* The ✓ of a solved grid: a pictogram drawn by CSS, never read. */
  .status-check::before {
    content: '✓';
  }

  .recap-open {
    flex: none;
    margin-left: auto;
    padding: 7px 12px;
    font-size: 0.85rem;
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
