<script lang="ts">
  import { formatPublishedOn, progressOf, type GridSummary } from './catalogue'
  import { t } from './i18n'
  import { playGrid } from './playGrid'

  let { summary }: { summary: GridSummary } = $props()

  const progress = $derived(progressOf(summary.number))

  let isStarting = $state(false)
  let hasFailed = $state(false)

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

<article
  data-testid="catalogue-item"
  data-number={String(summary.number)}
  data-published-on={summary.published_on}
  data-force={String(summary.force)}
  data-width={String(summary.width)}
  data-height={String(summary.height)}
  data-word-count={String(summary.word_count)}
  data-progress={progress}
>
  <h2>{t('catalogue.item.number', { number: summary.number })}</h2>
  <p>{t('catalogue.item.published', { date: formatPublishedOn(summary.published_on) })}</p>
  <p>{t('catalogue.item.force', { force: summary.force })}</p>
  <p>{t('catalogue.item.size', { width: summary.width, height: summary.height })}</p>
  <p>{t('catalogue.item.words', { count: summary.word_count })}</p>
  {#if progress === 'started'}
    <p data-testid="catalogue-progress">{t('catalogue.progress.started')}</p>
  {:else if progress === 'finished'}
    <p data-testid="catalogue-progress">{t('catalogue.progress.finished')}</p>
  {/if}
  <button type="button" data-testid="catalogue-play" disabled={isStarting} onclick={play}
    >{t('catalogue.play')}</button
  >
  {#if hasFailed}
    <p data-testid="catalogue-error" role="alert">{t('catalogue.play_failed')}</p>
  {/if}
</article>
