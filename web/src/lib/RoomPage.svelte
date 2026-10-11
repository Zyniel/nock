<script lang="ts">
  import GridViewport from './GridViewport.svelte'
  import InAppKeyboard from './InAppKeyboard.svelte'
  import { t } from './i18n'
  import type { LetterCellView } from './roomSession'
  import { gridLabel, newSession, receiveFrame, statusAfterClose } from './roomSession'
  import {
    computeWords,
    sameSelection,
    selectedWord,
    selectionAfterCellTap,
    selectionAfterClueTap,
    validSelection,
    wordKey,
  } from './wordSelection'
  import type { Selection, Word } from './wordSelection'

  const COPIED_DISPLAY_MS = 2000

  let { code }: { code: string } = $props()

  let session = $state(newSession())
  let rawSelection: Selection | null = $state(null)
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

  // `selection` is already null once its word is gone; this also drops the stale
  // `rawSelection`, so the old selection cannot come back with a later snapshot.
  $effect(() => {
    if (selection === null && rawSelection !== null) {
      rawSelection = null
    }
  })

  // Send a message when the socket is open; after a close nothing is sent.
  function send(message: object): void {
    if (socket !== null && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message))
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
    if (cell.letter !== letter) {
      cell.letter = letter
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
    if (cell.locked || cell.letter === null) {
      return false
    }
    cell.letter = null
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
      select(selectionAfterClueTap(session.snapshot.grid, word))
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
      const join = { type: 'join', nickname: t('room.default_nickname'), resume_token: null }
      opened.send(JSON.stringify(join))
    }
    opened.onmessage = (event: MessageEvent) => {
      if (typeof event.data === 'string') {
        receiveFrame(session, event.data)
      }
    }
    opened.onclose = (event: CloseEvent) => {
      session.status = statusAfterClose(event.code)
    }
    opened.onerror = () => {
      if (session.status !== 'not_found' && session.status !== 'throttled') {
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
  data-seq={session.seq === null ? '' : String(session.seq)}
  data-pending={String(session.pending.length)}
  data-grid={gridLabel(session)}
>
  <h1>{t('room.heading', { code })}</h1>
  <p data-testid="room-status">{t(`room.status.${session.status}`)}</p>
  {#if session.snapshot !== null}
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
