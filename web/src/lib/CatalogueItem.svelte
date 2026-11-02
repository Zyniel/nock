<script lang="ts">
  // One grid card of the catalogue and of the grid page (spec 004, spec 010,
  // spec 046 "Grid cards"): the generic drawing when the list has room for it,
  // the text column (number and progress, publication, force line), then
  // "Jouer" on the right.
  import MetaSep from './MetaSep.svelte'
  import { formatPublishedOn, progressOf, type GridSummary } from './catalogue'
  import { THUMB_HEIGHT_PX, gridThumbOf } from './gridThumb'
  import { t } from './i18n'
  import { NOCK_MARK_POINTS } from './icons'
  import { playGrid } from './playGrid'

  let {
    summary,
    isThumbShown,
    accountProgress,
  }: {
    summary: GridSummary
    isThumbShown: boolean
    accountProgress: Record<string, unknown> | null
  } = $props()

  // The force line draws one Nock mark per force level, navy up to the grid's.
  const FORCE_LEVELS = [1, 2, 3, 4]

  // The id of the card's title, which describes « Jouer ».
  const titleId = $derived(`catalogue-title-${summary.number}`)

  const thumb = $derived(gridThumbOf(summary.width, summary.height))

  let isStarting = $state(false)
  let hasFailed = $state(false)
  // Bumped to read the progress again from the device.
  let progressVersion = $state(0)

  const progress = $derived.by(() => {
    void progressVersion
    return progressOf(summary.number, accountProgress)
  })

  // A page restored from the back-forward cache keeps its old state: start again.
  function onPageShow(event: PageTransitionEvent): void {
    if (event.persisted) {
      isStarting = false
      progressVersion += 1
    }
  }

  // One tap creates one room; the button stays disabled while the request runs.
  async function play(): Promise<void> {
    if (isStarting) {
      return
    }
    isStarting = true
    hasFailed = false
    const started = await playGrid(summary.number)
    if (!started) {
      isStarting = false
      hasFailed = true
    }
  }
</script>

<svelte:window onpageshow={onPageShow} />

<article
  class="catalogue-item"
  data-testid="catalogue-item"
  data-number={String(summary.number)}
  data-published-on={summary.published_on}
  data-force={String(summary.force)}
  data-width={String(summary.width)}
  data-height={String(summary.height)}
  data-word-count={String(summary.word_count)}
  data-progress={progress}
>
  {#if isThumbShown}
    <svg
      class="catalogue-thumb"
      data-testid="catalogue-thumb"
      aria-hidden="true"
      width={thumb.widthPx}
      height={THUMB_HEIGHT_PX}
      viewBox="0 0 {thumb.viewWidth} {thumb.viewHeight}"
    >
      <rect width={thumb.viewWidth} height={thumb.viewHeight} fill="var(--nock-white)" />
      {#each thumb.clueCells as cell (`${cell.x},${cell.y}`)}
        <rect
          data-testid="thumb-clue"
          x={cell.x}
          y={cell.y}
          width="10"
          height="10"
          fill="var(--nock-thumb)"
        />
      {/each}
      {#each thumb.lines as line (`${line.x1},${line.y1},${line.x2},${line.y2}`)}
        <line
          data-testid="thumb-line"
          x1={line.x1}
          y1={line.y1}
          x2={line.x2}
          y2={line.y2}
          stroke="var(--nock-line)"
          stroke-width="1"
        />
      {/each}
    </svg>
  {/if}
  <div class="card-text">
    <div class="number-line">
      <h2 id={titleId}>{t('catalogue.item.number', { number: summary.number })}</h2>
      {#if progress === 'started'}
        <span class="nock-status-pill nock-status-pill-started" data-testid="catalogue-progress"
          >{t('catalogue.progress.started')}</span
        >
      {:else if progress === 'finished'}
        <span class="nock-status-pill nock-status-pill-finished" data-testid="catalogue-progress"
          >{t('catalogue.progress.finished')}</span
        >
      {/if}
    </div>
    <p class="card-line">
      {t('catalogue.item.published', { date: formatPublishedOn(summary.published_on) })}
    </p>
    <p class="card-line force-line">
      <span class="force-marks" data-testid="catalogue-force-marks" aria-hidden="true">
        {#each FORCE_LEVELS as level (level)}
          <svg viewBox="0 0 10 14" class:reached={level <= summary.force}
            ><polygon points={NOCK_MARK_POINTS} /></svg
          >
        {/each}
      </span><span
        >{t('catalogue.item.force', { force: summary.force })}<MetaSep />{t(
          'catalogue.item.size',
          { width: summary.width, height: summary.height },
        )}<MetaSep />{t('catalogue.item.words', { count: summary.word_count })}</span
      >
    </p>
    {#if hasFailed}
      <p class="nock-error-line" data-testid="catalogue-error" role="alert">
        {t('catalogue.play_failed')}
      </p>
    {/if}
  </div>
  <button
    type="button"
    class="nock-button nock-button-primary play"
    data-testid="catalogue-play"
    aria-describedby={titleId}
    disabled={isStarting}
    onclick={play}>{t('catalogue.play')}</button
  >
</article>

<style>
  .catalogue-item {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0;
    padding: 12px 14px;
    border: 1px solid var(--nock-line);
    border-radius: 8px;
    background: var(--nock-white);
  }

  .catalogue-thumb {
    display: block;
    flex: none;
    border: 1px solid var(--nock-rule);
  }

  /* The text column: all the width left, lines 3 px apart. */
  .card-text {
    flex: 1 1 0;
    min-width: 0;
    display: grid;
    gap: 3px;
  }

  /* The grid's number, then its status pill on its line. */
  .number-line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  h2 {
    margin: 0;
    font: 700 1.05rem/1.2 var(--nock-font-ui);
    color: var(--nock-ink);
  }

  .card-line {
    margin: 0;
    font-size: 0.85rem;
    color: var(--nock-muted);
    overflow-wrap: anywhere;
  }

  /* The marks, then the texts 6 px after them (their separators keep their
     own 4 px). */
  .force-line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }

  .force-marks {
    display: inline-flex;
    gap: 2px;
  }

  .force-marks svg {
    display: block;
    width: 8px;
    height: 11px;
    fill: var(--nock-thumb);
  }

  .force-marks svg.reached {
    fill: var(--nock-navy);
  }

  .play {
    flex: none;
    padding: 9px 16px;
  }
</style>
