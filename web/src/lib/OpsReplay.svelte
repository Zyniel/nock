<script lang="ts">
  import { t } from './i18n'
  import {
    editText,
    fetchReplay,
    lettersAtStep,
    type LockReason,
    type RoomReplay,
  } from './ops'
  import { positionKey } from './wordSelection'

  // The replay of one room on the operator's page (spec 038): the room's edits
  // in seq order, a step control, and the grid's letters after that many
  // edits, worked out in the page from the list.
  let { token, onLocked }: { token: string; onLocked: (reason: LockReason) => void } =
    $props()

  type ReplayState = 'idle' | 'loading' | 'ready' | 'not_found' | 'error'

  let replayState: ReplayState = $state('idle')
  let typedCode = $state('')
  let replay = $state<RoomReplay | null>(null)
  // How many of the edits the grid shows: all of them when they load.
  let position = $state(0)

  const letters = $derived(
    replay === null ? new Map<string, string>() : lettersAtStep(replay.edits, position),
  )

  async function loadReplay(code: string): Promise<void> {
    replayState = 'loading'
    const answer = await fetchReplay(token, code)
    if (answer.kind === 'ok') {
      replay = answer.body
      position = answer.body.edits.length
      replayState = 'ready'
    } else if (answer.kind === 'refused' || answer.kind === 'throttled') {
      onLocked(answer.kind)
    } else if (answer.kind === 'not_found') {
      replayState = 'not_found'
    } else {
      replayState = 'error'
    }
  }

  function submitCode(event: SubmitEvent): void {
    event.preventDefault()
    void loadReplay(typedCode.toUpperCase())
  }

  // The letter a cell of the replay's grid shows, "" for none.
  function letterAt(row: number, column: number): string {
    return letters.get(positionKey(row, column)) ?? ''
  }
</script>

<section
  class="ops-replay"
  data-testid="ops-replay"
  data-state={replayState}
  aria-labelledby="ops-replay-heading"
>
  <h2 id="ops-replay-heading">{t('ops.replay_heading')}</h2>
  <form class="ops-replay-form" data-testid="ops-replay-form" onsubmit={submitCode}>
    <label for="ops-replay-code">{t('ops.replay_code_label')}</label>
    <input
      id="ops-replay-code"
      data-testid="ops-replay-code"
      type="text"
      autocomplete="off"
      bind:value={typedCode}
    />
    <button type="submit" data-testid="ops-replay-submit">{t('ops.replay_submit')}</button>
  </form>
  {#if replayState === 'loading'}
    <p role="status">{t('ops.loading')}</p>
  {:else if replayState === 'not_found'}
    <p>{t('ops.replay_not_found')}</p>
  {:else if replayState === 'error'}
    <p>{t('ops.error')}</p>
  {:else if replayState === 'ready' && replay !== null}
    {#if replay.edits.length === 0}
      <p>{t('ops.replay_empty')}</p>
    {:else}
      <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
      <ol class="ops-edits" role="list">
        {#each replay.edits as edit (edit.seq)}
          <li
            data-testid="ops-edit"
            data-seq={String(edit.seq)}
            data-kind={edit.kind}
            data-row={String(edit.row)}
            data-column={String(edit.column)}
            data-letter={edit.letter ?? ''}
            data-player-id={edit.player_id ?? ''}
            data-at={edit.at}
          >
            {editText(edit)}
          </li>
        {/each}
      </ol>
    {/if}
    <div class="ops-replay-steps">
      <label for="ops-replay-position">{t('ops.replay_position_label')}</label>
      <!-- `max` comes before the value, so that a value over 100 is not cut. -->
      <input
        id="ops-replay-position"
        data-testid="ops-replay-position"
        type="range"
        min="0"
        max={replay.edits.length}
        step="1"
        bind:value={position}
      />
      <p data-testid="ops-replay-step">
        {t('ops.replay_step', { step: position, count: replay.edits.length })}
      </p>
    </div>
    <div
      class="ops-replay-grid"
      data-testid="ops-replay-grid"
      role="group"
      aria-label={t('ops.replay_grid_label')}
      style:--columns={String(replay.grid.width)}
    >
      {#each replay.grid.cells as cell (positionKey(cell.row, cell.column))}
        {#if cell.type === 'letter'}
          <span
            class="ops-replay-cell"
            data-testid="ops-replay-cell"
            data-row={String(cell.row)}
            data-column={String(cell.column)}
            data-letter={letterAt(cell.row, cell.column)}
            style:grid-row={String(cell.row + 1)}
            style:grid-column={String(cell.column + 1)}>{letterAt(cell.row, cell.column)}</span
          >
        {:else}
          <span
            class="ops-replay-block"
            style:grid-row={String(cell.row + 1)}
            style:grid-column={String(cell.column + 1)}
          ></span>
        {/if}
      {/each}
    </div>
  {/if}
</section>

<style>
  .ops-replay h2 {
    margin: 1.5rem 0 0.5rem;
    font-size: 1.25rem;
  }

  .ops-replay-form,
  .ops-replay-steps {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  .ops-replay-form input {
    min-width: 0;
    max-width: 100%;
  }

  .ops-replay-steps p {
    margin: 0;
  }

  /* Every edit is listed: a long replay makes the page scroll vertically. */
  .ops-edits {
    margin: 0.75rem 0;
    padding: 0 0 0 1.5rem;
  }

  .ops-edits li {
    margin: 0.15rem 0;
    overflow-wrap: anywhere;
  }

  /* The cells shrink in a narrow window, so the page never scrolls sideways. */
  .ops-replay-grid {
    display: grid;
    grid-template-columns: repeat(var(--columns), minmax(0, 2.5rem));
    gap: 2px;
    margin: 0.75rem 0;
  }

  .ops-replay-cell,
  .ops-replay-block {
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
  }

  .ops-replay-cell {
    border: 1px solid var(--nock-rule);
    font-weight: bold;
  }

  .ops-replay-block {
    background: var(--nock-thumb);
  }
</style>
