<script lang="ts">
  import MetaSep from './MetaSep.svelte'
  import { finishedText, teammatesText, timeText, type HistoryRecord } from './history'
  import { t } from './i18n'
  import { playGrid } from './playGrid'

  // One finished grid of the history list (spec 029), a list row (spec 046):
  // its title and its one line of date, time and team-mates, then "Rejouer"
  // on the right when the grid has a number.
  let { record }: { record: HistoryRecord } = $props()

  let isStarting = $state(false)
  let hasFailed = $state(false)

  // A page restored from the back-forward cache keeps its old state: start again.
  function onPageShow(event: PageTransitionEvent): void {
    if (event.persisted) {
      isStarting = false
    }
  }

  // Replay runs the play steps of spec 010 for the grid number; the button
  // stays disabled while the request runs.
  async function replay(number: number): Promise<void> {
    if (isStarting) {
      return
    }
    isStarting = true
    hasFailed = false
    const started = await playGrid(number)
    if (!started) {
      isStarting = false
      hasFailed = true
    }
  }
</script>

<svelte:window onpageshow={onPageShow} />

<li
  class="nock-list-row"
  data-testid="history-item"
  data-code={record.code}
  data-grid={record.grid === null ? '' : String(record.grid)}
  data-finished-at={record.finished_at}
  data-elapsed-ms={String(record.elapsed_ms)}
>
  <div class="nock-row-text">
    <h3 class="nock-row-title" data-testid="history-title">
      {record.grid === null
        ? t('my_rooms.unnumbered')
        : t('catalogue.item.number', { number: record.grid })}<MetaSep />{t(
        'catalogue.item.size',
        { width: record.width, height: record.height },
      )}
    </h3>
    <p class="nock-row-line history-line" data-testid="history-line">
      <span data-testid="history-date">{finishedText(record)}</span><MetaSep /><span
        data-testid="history-time">{timeText(record)}</span
      ><MetaSep /><span data-testid="history-teammates">{teammatesText(record)}</span>
    </p>
    {#if hasFailed}
      <p class="nock-error-line" data-testid="history-error" role="alert">
        {t('catalogue.play_failed')}
      </p>
    {/if}
  </div>
  {#if record.grid !== null}
    {@const number = record.grid}
    <button
      type="button"
      class="nock-button nock-button-secondary"
      data-testid="history-replay"
      aria-label={t('history.replay_label', { number })}
      disabled={isStarting}
      onclick={() => replay(number)}>{t('history.replay')}</button
    >
  {/if}
</li>

<style>
  /* One line of texts 6 px apart, that wraps when it must. */
  .history-line {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    column-gap: 6px;
  }

  .history-line span {
    min-width: 0;
  }
</style>
