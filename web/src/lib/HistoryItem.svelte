<script lang="ts">
  import { finishedText, teammatesText, timeText, type HistoryRecord } from './history'
  import { t } from './i18n'
  import { playGrid } from './playGrid'

  // One finished grid of the history list (spec 029).
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
  data-testid="history-item"
  data-code={record.code}
  data-grid={record.grid === null ? '' : String(record.grid)}
  data-finished-at={record.finished_at}
  data-elapsed-ms={String(record.elapsed_ms)}
>
  <h3>
    {record.grid === null
      ? t('my_rooms.unnumbered')
      : t('catalogue.item.number', { number: record.grid })}
  </h3>
  <p>{t('catalogue.item.size', { width: record.width, height: record.height })}</p>
  <p data-testid="history-date">{finishedText(record)}</p>
  <p data-testid="history-time">{timeText(record)}</p>
  <p data-testid="history-teammates">{teammatesText(record)}</p>
  {#if record.grid !== null}
    {@const number = record.grid}
    <button
      type="button"
      data-testid="history-replay"
      aria-label={t('history.replay_label', { number })}
      disabled={isStarting}
      onclick={() => replay(number)}>{t('history.replay')}</button
    >
  {/if}
  {#if hasFailed}
    <p data-testid="history-error" role="alert">{t('catalogue.play_failed')}</p>
  {/if}
</li>

<style>
  li {
    padding: 0.75rem;
    border: 1px solid #5b6070;
    border-radius: 0.5rem;
  }

  h3 {
    margin: 0 0 0.25rem;
    font-size: 1rem;
  }

  /* A long list of nicknames wraps rather than widen the page (spec 006 AC-5). */
  p {
    margin: 0.15rem 0;
    overflow-wrap: anywhere;
  }
</style>
