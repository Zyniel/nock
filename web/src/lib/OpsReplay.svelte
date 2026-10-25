<script lang="ts">
  import { t } from './i18n'
  import {
    cellStatesAtStep,
    editText,
    emptyCellState,
    fetchReplay,
    type LockReason,
    type ReplayCellState,
    type RoomReplay,
  } from './ops'
  import { COLUMN_MIN_WIDTH_PX } from './windowForm'
  import { positionKey } from './wordSelection'

  // The replay of one room on the operator's page (spec 038): the room's edits
  // in seq order, a step control, and the grid after that many edits, worked
  // out in the page from the list. Spec 048 draws it as a card: on a window at
  // least 900 px wide the edits sit left of the grid, otherwise under it; the
  // grid has the playing grid's cells and marks, without clues, arrows or
  // players; the step control is the native range input, transparent, over a
  // drawn track, fill and knob.
  let { token, onLocked }: { token: string; onLocked: (reason: LockReason) => void } =
    $props()

  type ReplayState = 'idle' | 'loading' | 'ready' | 'not_found' | 'error'

  // The side of a cell in the two-column form and in the one-column form, at
  // most; the gap between the edits and the grid, and the width the edits keep
  // at least, in the two-column form.
  const TWO_COLUMN_CELL_PX = 44
  const ONE_COLUMN_CELL_PX = 36
  const EDITS_GAP_PX = 20
  const EDITS_MIN_WIDTH_PX = 240

  let replayState: ReplayState = $state('idle')
  let typedCode = $state('')
  let replay = $state<RoomReplay | null>(null)
  // How many of the edits the grid shows: all of them when they load.
  let position = $state(0)
  let windowWidth = $state(window.innerWidth)
  // The width of the card's content, measured on the replay's body.
  let bodyWidth = $state(0)

  const cellStates = $derived(
    replay === null ? new Map<string, ReplayCellState>() : cellStatesAtStep(replay.edits, position),
  )
  const isTwoColumns = $derived(windowWidth >= COLUMN_MIN_WIDTH_PX)
  const cellSide = $derived(replay === null ? 0 : sideOfCells(replay.grid.width))
  // The grid's width: its cells and its 1 px left line.
  const gridWidth = $derived(replay === null ? 0 : replay.grid.width * cellSide + 1)

  // The side of a cell, in whole px, so that `columns` cells and the grid's
  // left line fit the width the grid may take: the card's content, less the
  // edits and their gap in the two-column form.
  function sideOfCells(columns: number): number {
    let widest = ONE_COLUMN_CELL_PX
    let room = bodyWidth
    if (isTwoColumns) {
      widest = TWO_COLUMN_CELL_PX
      room = bodyWidth - EDITS_GAP_PX - EDITS_MIN_WIDTH_PX
    }
    const fitting = Math.floor((room - 1) / columns)
    // At least 1 px before the body is first measured. That measure comes in
    // the same rendering update as the grid's first drawing (a ResizeObserver
    // callback, then Svelte's flush), before the browser paints, so no frame
    // shows these 1 px cells.
    return Math.max(1, Math.min(widest, fitting))
  }

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

  // What a letter cell of the replay's grid shows at the chosen step.
  function stateAt(row: number, column: number): ReplayCellState {
    return cellStates.get(positionKey(row, column)) ?? emptyCellState()
  }

  // Where the edit of index `index` (from 0) stands against the chosen step.
  function stepOf(index: number): 'done' | 'current' | 'later' {
    const number = index + 1
    if (number < position) {
      return 'done'
    }
    if (number === position) {
      return 'current'
    }
    return 'later'
  }
</script>

<svelte:window bind:innerWidth={windowWidth} />

<section
  class="nock-card"
  data-testid="ops-replay"
  data-state={replayState}
  aria-labelledby="ops-replay-heading"
>
  <h2 class="nock-card-title" id="ops-replay-heading">{t('ops.replay_heading')}</h2>
  <form class="ops-replay-form" data-testid="ops-replay-form" onsubmit={submitCode}>
    <div class="nock-field ops-replay-code-field">
      <label for="ops-replay-code">{t('ops.replay_code_label')}</label>
      <input
        id="ops-replay-code"
        class="nock-text-input"
        data-testid="ops-replay-code"
        type="text"
        autocomplete="off"
        bind:value={typedCode}
      />
    </div>
    <button type="submit" class="nock-button nock-button-primary" data-testid="ops-replay-submit"
      >{t('ops.replay_submit')}</button
    >
  </form>
  {#if replayState === 'loading'}
    <p class="nock-muted-line" data-testid="ops-replay-state-line" role="status">
      {t('ops.loading')}
    </p>
  {:else if replayState === 'not_found'}
    <p class="nock-error-line" data-testid="ops-replay-state-line" role="alert">
      {t('ops.replay_not_found')}
    </p>
  {:else if replayState === 'error'}
    <p class="nock-error-line" data-testid="ops-replay-state-line" role="alert">
      {t('ops.error')}
    </p>
  {:else if replayState === 'ready' && replay !== null}
    {#if replay.edits.length === 0}
      <p class="nock-muted-line" data-testid="ops-replay-state-line">{t('ops.replay_empty')}</p>
    {:else}
      {@const count = replay.edits.length}
      <div
        class="ops-replay-body"
        class:two-columns={isTwoColumns}
        data-testid="ops-replay-body"
        bind:clientWidth={bodyWidth}
      >
        <!-- The grid, the step control and the step line, in one column as
             wide as the grid in the two-column form. -->
        <div class="ops-replay-board" style:width={isTwoColumns ? `${gridWidth}px` : null}>
          <div
            class="ops-replay-grid"
            data-testid="ops-replay-grid"
            role="group"
            aria-label={t('ops.replay_grid_label')}
            style:--cell="{cellSide}px"
            style:grid-template-columns="repeat({replay.grid.width}, var(--cell))"
            style:grid-auto-rows="var(--cell)"
          >
            {#each replay.grid.cells as cell (positionKey(cell.row, cell.column))}
              {#if cell.type === 'letter'}
                {@const shown = stateAt(cell.row, cell.column)}
                <span
                  class="ops-replay-cell"
                  class:locked={shown.locked}
                  data-testid="ops-replay-cell"
                  data-row={String(cell.row)}
                  data-column={String(cell.column)}
                  data-letter={shown.letter}
                  data-locked={String(shown.locked)}
                  data-revealed={String(shown.revealed)}
                  data-pencil={String(shown.pencil)}
                  style:grid-row={String(cell.row + 1)}
                  style:grid-column={String(cell.column + 1)}
                  >{#if shown.letter !== ''}<span class="ops-replay-letter">{shown.letter}</span
                    >{/if}{#if shown.revealed}<span class="nock-reveal-notch" aria-hidden="true"
                    ></span>{/if}</span
                >
              {:else}
                <span
                  class="ops-replay-block"
                  data-testid="ops-replay-block"
                  data-type={cell.type}
                  style:grid-row={String(cell.row + 1)}
                  style:grid-column={String(cell.column + 1)}
                ></span>
              {/if}
            {/each}
          </div>
          <div class="nock-field" data-testid="ops-replay-position-field">
            <label for="ops-replay-position">{t('ops.replay_position_label')}</label>
            <div class="replay-slider" style:--ratio={String(position / count)}>
              <!-- `max` comes before the value, so that a value over 100 is not cut. -->
              <input
                id="ops-replay-position"
                class="replay-slider-input"
                data-testid="ops-replay-position"
                type="range"
                min="0"
                max={count}
                step="1"
                bind:value={position}
              />
              <span class="replay-slider-track" data-testid="ops-replay-track" aria-hidden="true"
              ></span>
              <!-- At the position 0 no edit is replayed: the fill is empty (its
                   9 px up to the knob's centre would lie under the knob). -->
              <span
                class="replay-slider-fill"
                class:empty={position === 0}
                data-testid="ops-replay-fill"
                aria-hidden="true"
              ></span>
              <span class="replay-slider-knob" data-testid="ops-replay-knob" aria-hidden="true"
              ></span>
            </div>
          </div>
          <p class="nock-card-detail" data-testid="ops-replay-step">
            {t('ops.replay_step', { step: position, count })}
          </p>
        </div>
        <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
        <ol class="ops-edits" data-testid="ops-edits" role="list">
          {#each replay.edits as edit, index (edit.seq)}
            <li
              data-testid="ops-edit"
              data-step={stepOf(index)}
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
      </div>
    {/if}
  {/if}
</section>

<style>
  /* The code field takes the width left (at least 140 px), the button beside
     it, both on the row's bottom. */
  .ops-replay-form {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 8px;
    justify-self: stretch;
  }

  .ops-replay-code-field {
    flex: 1 1 140px;
    width: auto;
    min-width: 140px;
  }

  /* One column: the grid's column, then the edits. */
  .ops-replay-body {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 10px;
    justify-self: stretch;
  }

  /* Two columns: the edits on the left, the grid's column on the right. */
  .ops-replay-body.two-columns {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 20px;
    align-items: start;
  }

  .ops-replay-body.two-columns .ops-replay-board {
    grid-row: 1;
    grid-column: 2;
  }

  .ops-replay-body.two-columns .ops-edits {
    grid-row: 1;
    grid-column: 1;
  }

  .ops-replay-board {
    display: grid;
    gap: 10px;
    justify-items: start;
    min-width: 0;
  }

  .ops-replay-board p {
    margin: 0;
  }

  /* The edits, one line each; the step shown on word blue, later ones muted. */
  .ops-edits {
    display: grid;
    gap: 4px;
    margin: 0;
    padding: 0;
    list-style: none;
    font: 400 0.85rem var(--nock-font-ui);
    font-variant-numeric: tabular-nums;
  }

  .ops-edits li {
    padding: 4px 8px;
    border-radius: 4px;
    color: var(--nock-ink);
    overflow-wrap: anywhere;
  }

  .ops-edits li[data-step='current'] {
    font-weight: 600;
    background: var(--nock-word);
  }

  .ops-edits li[data-step='later'] {
    color: var(--nock-muted);
  }

  /* The grid's lines (specs/_design/cells.md « Grid lines and empty cells »): its left and top line, then each
     cell's right and bottom line inside its side. */
  .ops-replay-grid {
    display: grid;
    border-top: 1px solid var(--nock-rule);
    border-left: 1px solid var(--nock-rule);
  }

  .ops-replay-cell,
  .ops-replay-block {
    box-sizing: border-box;
    border-right: 1px solid var(--nock-rule);
    border-bottom: 1px solid var(--nock-rule);
  }

  .ops-replay-block[data-type='clue'] {
    background: var(--nock-clue-bg);
  }

  .ops-replay-block[data-type='empty'] {
    background: var(--nock-rule);
  }

  /* A letter cell, as the playing grid draws it (spec 042). */
  .ops-replay-cell {
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--nock-font-ui);
    font-size: calc(var(--cell) * 0.56);
    font-weight: 500;
    line-height: 1;
    color: var(--nock-ink);
    background: var(--nock-white);
  }

  .ops-replay-letter {
    text-box: trim-both cap alphabetic;
  }

  .ops-replay-cell[data-pencil='true'] {
    font-style: italic;
    color: var(--nock-pencil);
  }

  .ops-replay-cell.locked {
    font-weight: 700;
    background: var(--nock-locked);
  }

  /* The step control: the native range input, transparent, over the three
     parts that draw it, so that it looks the same in every engine. The knob
     stays 9 px inside each end, as a native thumb does. */
  .replay-slider {
    position: relative;
    height: 18px;
  }

  .replay-slider-input {
    position: relative;
    z-index: 1;
    display: block;
    box-sizing: border-box;
    width: 100%;
    height: 18px;
    margin: 0;
    opacity: 0;
    cursor: pointer;
  }

  .replay-slider-track,
  .replay-slider-fill {
    position: absolute;
    top: 6px;
    left: 0;
    height: 6px;
    border-radius: 3px;
  }

  .replay-slider-track {
    right: 0;
    background: var(--nock-word);
  }

  .replay-slider-fill {
    width: calc(9px + (100% - 18px) * var(--ratio));
    background: var(--nock-navy);
  }

  .replay-slider-fill.empty {
    width: 0;
  }

  .replay-slider-knob {
    position: absolute;
    top: 0;
    left: calc((100% - 18px) * var(--ratio));
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--nock-navy);
  }

  .replay-slider-input:focus-visible ~ .replay-slider-knob {
    outline: var(--focus-outline);
    outline-offset: 2px;
  }
</style>
