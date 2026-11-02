<script lang="ts">
  import MetaSep from './MetaSep.svelte'
  import PlayButton from './PlayButton.svelte'
  import { finishedText, teammatesText, timeText, type HistoryRecord } from './history'
  import { t } from './i18n'

  // One finished grid of the history list (spec 029), a list row (spec 046):
  // its title and its one line of date, time and team-mates, then "Rejouer"
  // on the right when the grid has a number.
  let { record }: { record: HistoryRecord } = $props()

  // True when « Rejouer », the play steps of spec 010 for the grid number,
  // could not create the room: the row shows its error line.
  let hasFailed = $state(false)
</script>

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
      <span
        >{record.grid === null
          ? t('my_rooms.unnumbered')
          : t('catalogue.item.number', { number: record.grid })}<MetaSep />{t(
          'catalogue.item.size',
          { width: record.width, height: record.height },
        )}</span
      >
    </h3>
    <!-- One run of text, which wraps when it must. -->
    <p class="nock-row-line" data-testid="history-line">
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
    <PlayButton
      {number}
      class="nock-button nock-button-secondary"
      data-testid="history-replay"
      aria-label={t('history.replay_label', { number })}
      bind:hasFailed>{t('history.replay')}</PlayButton
    >
  {/if}
</li>
