<script lang="ts">
  import GridViewport from './GridViewport.svelte'
  import { t } from './i18n'
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

  let { code }: { code: string } = $props()

  let session = $state(newSession())
  let rawSelection: Selection | null = $state(null)
  let socket: WebSocket | null = null

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
    if (cellChanged && socket !== null && socket.readyState === WebSocket.OPEN) {
      const message = {
        type: 'select_cell',
        row: next.row,
        column: next.column,
        direction: next.direction,
      }
      socket.send(JSON.stringify(message))
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
      if (session.status !== 'not_found') {
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
    <GridViewport
      grid={session.snapshot.grid}
      {selection}
      {activeWord}
      {onCellTap}
      {onClueTap}
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
</style>
