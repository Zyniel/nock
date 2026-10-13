<script lang="ts">
  import GridViewport from './GridViewport.svelte'
  import InAppKeyboard from './InAppKeyboard.svelte'
  import { t } from './i18n'
  import { checkNickname, planAutomaticJoin, readNickname, writeIdentity, writeNickname } from './joinRules'
  import { markFinished } from './catalogue'
  import { remoteSelectionsOf } from './remoteSelections'
  import { readRoomGrid, readRoomSelection, writeRoomSelection } from './roomRecord'
  import type { LetterCellView, Snapshot } from './roomSession'
  import {
    EDIT_SEND_INTERVAL_MS,
    FLASH_MS,
    PING_INTERVAL_MS,
    SILENCE_LIMIT_MS,
    addPendingEdit,
    endFlash,
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

  const COPIED_DISPLAY_MS = 2000
  const UNDO_MESSAGE_MS = 3000
  const MAX_REVEAL_COUNT = 99

  let { code }: { code: string } = $props()

  let session = $state(newSession())
  let rawSelection: Selection | null = $state(null)
  // The nickname form: what is typed, the error shown, and the nickname of a
  // join sent from the form that no snapshot has answered yet.
  let nicknameText = $state(readNickname() ?? '')
  let formError: 'length' | 'characters' | null = $state(null)
  let formJoinNickname: string | null = $state(null)
  let socket: WebSocket | null = null
  let gridViewport: GridViewport | undefined = $state()
  let feedElement: HTMLUListElement | undefined = $state()
  // The in-app keyboard is for touch screens: the main pointer is coarse.
  const isTouchScreen = window.matchMedia('(pointer: coarse)').matches

  // The host panel scrolls sideways on a small window. An edge fade says so
  // without depending on the scrollbar, which some engines hide.
  let hostPanel: HTMLDivElement | undefined = $state()
  let hostPanelHasMore = $state(false)

  // Show the fade while content is hidden past the right edge of the panel.
  function updateHostPanelMore(): void {
    if (hostPanel === undefined) {
      hostPanelHasMore = false
      return
    }
    const hiddenOnTheRight = hostPanel.scrollWidth - hostPanel.clientWidth - hostPanel.scrollLeft
    hostPanelHasMore = hiddenOnTheRight > 1
  }

  // The last way the user acted: a key press or a pointer (mouse, touch, pen).
  // :focus-visible cannot tell them apart, because a select or an input that is
  // focused by a pointer is :focus-visible too.
  let lastActionWasKeyboard = false
  // True while a host panel control has the focus from the keyboard.
  let hostPanelHasKeyboardFocus = $state(false)

  $effect(() => {
    const onKeyDown = (): void => {
      lastActionWasKeyboard = true
    }
    const onPointerDown = (): void => {
      lastActionWasKeyboard = false
      hostPanelHasKeyboardFocus = false
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

  // Measure again whenever the panel or its content changes size.
  $effect(() => {
    if (hostPanel === undefined) {
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

  let shareLink = $derived(`${location.origin}/r/${code}`)
  let copied = $state(false)
  let copiedTimer: ReturnType<typeof setTimeout> | undefined

  // Write the link to the clipboard. Without a usable clipboard nothing changes.
  async function copyLink(): Promise<void> {
    if (navigator.clipboard === undefined || navigator.clipboard === null) {
      return
    }
    try {
      await navigator.clipboard.writeText(shareLink)
    } catch {
      return
    }
    copied = true
    clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => {
      copied = false
    }, COPIED_DISPLAY_MS)
  }

  // Leaving the page must not leave the timer to fire on a destroyed page.
  $effect(() => {
    return () => {
      clearTimeout(copiedTimer)
      clearTimeout(undoMessageTimer)
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
  let remoteSelections = $derived(remoteSelectionsOf(session.snapshot, words))

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

  // The newest feed item stays in view.
  $effect(() => {
    const itemCount = session.feed.length
    if (feedElement !== undefined && itemCount > 0) {
      feedElement.scrollTop = feedElement.scrollHeight
    }
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
  let isCheckDisabled = $derived(
    session.solved ||
      (session.snapshot !== null && session.snapshot.settings.help_mode === 'none'),
  )

  // True when every letter cell of the confirmed grid holds a letter (spec 026).
  let isGridFull = $derived(
    session.snapshot !== null &&
      session.snapshot.grid.cells.every((cell) => cell.type !== 'letter' || cell.letter !== null),
  )
  let gridStatus = $derived(session.solved ? 'solved' : isGridFull ? 'full_wrong' : null)
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

  // Check the nickname typed in the form, and join with it when it is valid.
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

  // Type a letter on the selected cell, then move to the next unlocked cell.
  function onLetter(letter: string): void {
    if (session.solved || selection === null || activeWord === null) {
      return
    }
    const cell = letterCellAt(selection.row, selection.column)
    if (cell === null || cell.locked) {
      return
    }
    if (shownCell(cell, session.pendingEdits).letter !== letter) {
      addPendingEdit(session, cell.row, cell.column, letter)
      sendEdit({
        type: 'edit_letter',
        row: cell.row,
        column: cell.column,
        letter,
        base_seq: null,
      })
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
    addPendingEdit(session, cell.row, cell.column, null)
    sendEdit({ type: 'erase', row: cell.row, column: cell.column, base_seq: null })
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

  // Send my pending edits again, oldest first, each with the base_seq it had.
  // They are paced, the first one at once, then one every EDIT_SEND_INTERVAL_MS.
  function resendPendingEdits(): void {
    stopEditQueue()
    isSynced = true
    for (const edit of session.pendingEdits) {
      if (edit.letter === null) {
        editQueue.push({
          type: 'erase',
          row: edit.row,
          column: edit.column,
          base_seq: edit.baseSeq,
        })
      } else {
        editQueue.push({
          type: 'edit_letter',
          row: edit.row,
          column: edit.column,
          letter: edit.letter,
          base_seq: edit.baseSeq,
        })
      }
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
    receiveFrame(session, event.data)
    if (session.snapshot !== null && session.snapshot !== snapshotBefore) {
      rememberJoin(session.snapshot)
      if (snapshotBefore === null) {
        restoreSavedSelection(session.snapshot)
      }
      reconnectAttempt = 0
      resendPendingEdits()
    }
    if (session.status === 'nickname') {
      formJoinNickname = null
    }
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
  data-testid="room-page"
  data-room-code={code}
  data-status={session.status}
  data-you={session.snapshot === null ? '' : session.snapshot.you}
  data-seq={session.seq === null ? '' : String(session.seq)}
  data-solved={String(session.solved)}
  data-pending={String(session.pending.length)}
  data-grid={gridLabel(session)}
>
  <header class="room-header">
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
      <div class="undo-panel">
        <button type="button" data-testid="undo-button" disabled={session.solved} onclick={onUndo}
          >{t('room.undo')}</button>
        {#if isUndoMessageShown}
          <span data-testid="undo-message" role="status">{t('undo.nothing')}</span>
        {/if}
      </div>
      <div class="check-panel" data-testid="check-panel" role="group" aria-label={t('check.label')}>
        <button
          type="button"
          data-testid="check-letter"
          aria-label={t('check.letter_label')}
          disabled={isCheckDisabled || selection === null}
          onclick={onCheckLetter}>{t('check.letter')}</button
        >
        <button
          type="button"
          data-testid="check-word"
          aria-label={t('check.word_label')}
          disabled={isCheckDisabled || activeWord === null}
          onclick={onCheckWord}>{t('check.word')}</button
        >
        <button
          type="button"
          data-testid="check-grid"
          aria-label={t('check.grid_label')}
          disabled={isCheckDisabled}
          onclick={() => onCheck({ scope: 'grid' })}>{t('check.grid')}</button
        >
      </div>
    {/if}
  </header>
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
      <h2>{t('roster.heading')}</h2>
      <ul onfocusin={scrollKeyboardFocusIntoView}>
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
              style:background={`var(--player-colour-${player.colour})`}
            ></span>
            <span class="roster-nickname" data-testid="roster-nickname">{player.nickname}</span>
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
                data-testid="remove-player"
                aria-label={t('host.remove_label', { name: player.nickname })}
                onclick={() => removePlayer(player.player_id)}>{t('host.remove')}</button
              >
            {/if}
          </li>
        {/each}
      </ul>
    </section>
    <section class="feed" data-testid="activity-feed">
      <h2>{t('feed.heading')}</h2>
      <ul bind:this={feedElement}>
        {#each session.feed as item (item.seq)}
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
      {remoteSelections}
    />
    <div
      class="clue-bar"
      data-testid="clue-bar"
      data-word={activeWord === null ? '' : wordKey(activeWord)}
      role="region"
      aria-label={t('clue_bar.label')}
    >
      <span class="clue-bar-text" data-testid="clue-bar-text"
        >{activeWord === null ? t('clue_bar.empty') : activeWord.text}</span
      >
    </div>
    {#if gridStatus !== null}
      <p class="grid-status" data-testid="grid-status" data-state={gridStatus} role="status">
        {gridStatus === 'solved' ? t('completion.solved') : t('completion.full_wrong')}
      </p>
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
  main {
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

  .connection-banner {
    margin: 0.25rem 0;
    padding: 0.4rem 0.75rem;
    background: #fff3cd;
    border: 1px solid #b38600;
  }

  .nickname-error {
    margin: 0;
    color: #a4161a;
  }

  /* Title, status, invitation link and undo on one row; it wraps when it must. */
  .room-header {
    flex: none;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.75rem;
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

  .undo-panel,
  .check-panel {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* The roster and the feed: stacked on a roomy window. */
  .presence {
    flex: none;
    display: flex;
    flex-direction: column;
  }

  .roster {
    flex: none;
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
    color: #5b6070;
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
    min-width: 24px;
    min-height: 24px;
    padding: 0 0.3rem;
    font-size: 0.75rem;
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

  .host-panel-more {
    display: none;
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

  .feed ul {
    max-height: 3.6rem;
    overflow-y: auto;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  /* The grid state line, kept out of the scrolling area. */
  .grid-status {
    flex: none;
    margin: 0;
    padding: 0.25rem 0.75rem;
    font-weight: bold;
  }

  /* Below the scrolling grid, so it is always inside the window. */
  .clue-bar {
    flex: none;
    box-sizing: border-box;
    padding: 0.5rem 0.75rem;
    background: #eef1fa;
    border-top: 1px solid #8a8fa0;
  }

  .clue-bar-text {
    display: block;
    font-size: 1rem;
    line-height: 1.3;
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

    .roster ul {
      flex: 1 1 auto;
      flex-wrap: nowrap;
      min-width: 0;
      gap: 0.75rem;
      overflow-x: auto;
      /* A focused control is scrolled whole into view, outline included. */
      scroll-padding: 8px;
    }

    .roster li {
      flex: none;
      white-space: nowrap;
    }

    .feed ul {
      flex: 1 1 auto;
      min-width: 0;
      max-height: 1.3rem;
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

    /* A fade stuck to the right edge of the visible part of the panel. Its
       negative margin cancels its width and the row gap: no layout change. */
    .host-panel-more {
      display: block;
      flex: none;
      position: sticky;
      right: 0;
      align-self: stretch;
      width: 1.5rem;
      margin-left: calc(-1.5rem - 0.5rem);
      background: linear-gradient(to right, transparent, Canvas);
      pointer-events: none;
      visibility: hidden;
    }

    .host-panel-more.shown {
      visibility: visible;
    }

    /* A scroll container clips an outline drawn outside a control: draw it
       inside instead (3px wide, so spec 035 AC-2 still holds). */
    .roster ul :focus-visible,
    .host-panel :focus-visible {
      outline-offset: -3px;
    }

    /* The feed list scrolls and is a Tab stop in Chromium. Drawn outside, the
       bottom edge of its outline is painted over by the next panel (spec 035
       AC-2), so draw it inside the list's own box. */
    .feed ul:focus-visible {
      outline-offset: -3px;
    }

    /* The target is taller than the row: 2px of it sticks out of the list on
       each side, so its outline goes deeper to stay whole. */
    .roster ul .remove-player:focus-visible {
      outline-offset: -5px;
    }

    /* The fade never covers a control that has the keyboard focus. A mouse click
       or a tap also focuses a control, but it must not hide the fade (spec 014
       AC-7), so this follows a class set only for keyboard focus. */
    .host-panel.keyboard-focus .host-panel-more {
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

    /* A target of 24 by 24 CSS pixels at least (spec 014 AC-7). */
    .remove-player {
      min-width: 24px;
      min-height: 24px;
      /* The row keeps its height: the target overflows its line, not the row. */
      margin-block: -3px;
    }

    .feed li {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  /* A low window (a phone on its side) also takes the padding down, and puts the
     roster and the feed side by side. */
  @media (max-height: 500px) {
    main {
      padding: 0.25rem 0.5rem;
    }

    .clue-bar {
      padding: 0.25rem 0.75rem;
    }

    .presence {
      flex-direction: row;
      gap: 1rem;
    }

    .roster,
    .feed,
    .host-panel {
      flex: 1 1 0;
      min-width: 0;
    }
  }
</style>
