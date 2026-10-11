<script lang="ts">
  import GridViewport from './GridViewport.svelte'
  import InAppKeyboard from './InAppKeyboard.svelte'
  import { t } from './i18n'
  import { checkNickname, planAutomaticJoin, readNickname, writeIdentity, writeNickname } from './joinRules'
  import { markFinished } from './catalogue'
  import { readRoomGrid, readRoomSelection, writeRoomSelection } from './roomRecord'
  import type { LetterCellView, Snapshot } from './roomSession'
  import { FLASH_MS, addPendingEdit, endFlash, gridLabel, newSession, receiveFrame, shownCell, shownGrid, statusAfterClose } from './roomSession'
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
    }
  })

  let words = $derived(session.snapshot === null ? [] : computeWords(session.snapshot.grid))
  // A new snapshot may remove the word of the selection: then nothing is selected.
  let selection = $derived(validSelection(words, rawSelection))
  let activeWord = $derived(selectedWord(words, selection))

  let isFormShown = $derived(
    session.status === 'nickname' || (session.status === 'joining' && formJoinNickname !== null),
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
  $effect(() => {
    for (const flash of session.flashes) {
      if (scheduledFlashes.has(flash.id)) {
        continue
      }
      scheduledFlashes.add(flash.id)
      setTimeout(() => {
        scheduledFlashes.delete(flash.id)
        endFlash(session, flash.id)
      }, FLASH_MS)
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
      send({
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
    send({ type: 'erase', row: cell.row, column: cell.column, base_seq: null })
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

  $effect(() => {
    const opened = new WebSocket(roomSocketUrl(code))
    socket = opened

    opened.onopen = () => {
      const plan = planAutomaticJoin(code, t('room.default_nickname'))
      if (plan === null) {
        session.status = 'nickname'
        return
      }
      session.status = 'joining'
      opened.send(JSON.stringify({ type: 'join', ...plan }))
    }
    opened.onmessage = (event: MessageEvent) => {
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
      }
      if (session.status === 'nickname') {
        formJoinNickname = null
      }
    }
    opened.onclose = (event: CloseEvent) => {
      session.status = statusAfterClose(event.code, session.status)
    }
    opened.onerror = () => {
      const isFinal = ['not_found', 'throttled', 'full', 'replaced'].includes(session.status)
      if (!isFinal) {
        session.status = 'closed'
      }
    }

    // Leaving the page closes the socket; the handlers must not react to it.
    return () => {
      opened.onclose = null
      opened.onerror = null
      opened.close()
      socket = null
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
            {#if isYou}
              <span class="roster-you">{t('roster.you')}</span>
            {/if}
          </li>
        {/each}
      </ul>
    </section>
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
      {words}
      pendingEdits={session.pendingEdits}
      flashes={session.flashes}
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

  .nickname-error {
    margin: 0;
    color: #a4161a;
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
  }
</style>
