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
  let feedElement: HTMLElement | undefined = $state()
  // The in-app keyboard is for touch screens: the main pointer is coarse.
  const isTouchScreen = window.matchMedia('(pointer: coarse)').matches

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
    if (selection === null || activeWord === null) {
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
    if (selection === null || activeWord === null) {
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
    send({ type: 'undo' })
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
  data-pending={String(session.pending.length)}
  data-grid={gridLabel(session)}
>
  <h1>{t('room.heading', { code })}</h1>
  <p data-testid="room-status">{t(`room.status.${session.status}`)}</p>
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
      <ul>
        {#each session.snapshot.players as player (player.player_id)}
          {@const isYou = player.player_id === session.snapshot.you}
          <li
            data-testid="roster-player"
            data-player-id={player.player_id}
            data-colour={String(player.colour)}
            data-state={player.state}
            data-you={String(isYou)}
          >
            <span
              class="roster-colour"
              data-testid="roster-colour"
              style:background={`var(--player-colour-${player.colour})`}
            ></span>
            <span data-testid="roster-nickname">{player.nickname}</span>
            <span class="roster-state" data-testid="roster-state"
              >{t(`presence.${player.state}`)}</span
            >
            {#if isYou}
              <span class="roster-you">{t('roster.you')}</span>
            {/if}
          </li>
        {/each}
      </ul>
    </section>
    <section class="feed" data-testid="activity-feed" bind:this={feedElement}>
      <h2>{t('feed.heading')}</h2>
      <ul>
        {#each session.feed as item (item.seq)}
          <li data-testid="feed-item" data-kind={item.kind} data-seq={String(item.seq)}>
            {item.text}
          </li>
        {/each}
      </ul>
    </section>
    </div>
    <div class="share-panel" data-testid="share-panel">
      <span id="share-label" class="share-label">{t('room.share.label')}</span>
      <a data-testid="share-link" href={shareLink} aria-describedby="share-label"
        >{shareLink}</a
      >
      <button type="button" data-testid="copy-link" onclick={copyLink}
        >{copied ? t('room.share.copied') : t('room.share.copy')}</button
      >
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
    <div class="undo-panel">
      <button type="button" data-testid="undo-button" onclick={onUndo}>{t('room.undo')}</button>
      {#if isUndoMessageShown}
        <span data-testid="undo-message" role="status">{t('undo.nothing')}</span>
      {/if}
    </div>
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

  /* The roster and the feed: stacked, or side by side in a low window. */
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

  .roster li[data-state='idle'] {
    opacity: 0.7;
  }

  .roster li[data-state='disconnected'] {
    opacity: 0.45;
  }

  /* A short strip that scrolls: the grid keeps the height (spec 006). */
  .feed {
    flex: none;
    box-sizing: border-box;
    max-height: 4.5rem;
    overflow-y: auto;
    overflow-wrap: anywhere;
    font-size: 0.85rem;
  }

  .feed h2 {
    margin: 0;
    font-size: 0.85rem;
  }

  .feed ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .undo-panel {
    flex: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .share-panel {
    flex: none;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    overflow-wrap: anywhere;
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

  /* A low window (a phone on its side) keeps its height for the grid. */
  @media (max-height: 500px) {
    main {
      padding: 0.25rem 0.5rem;
    }

    h1 {
      margin: 0;
      font-size: 1rem;
    }

    p {
      margin: 0;
    }

    .clue-bar {
      padding: 0.25rem 0.75rem;
    }

    /* Side by side, so the feed takes no height from the grid (spec 006). */
    .presence {
      flex-direction: row;
      gap: 1rem;
    }

    .roster {
      flex: 1 1 0;
      min-width: 0;
    }

    .feed {
      flex: 1 1 0;
      min-width: 0;
      max-height: 2.6rem;
    }
  }
</style>
