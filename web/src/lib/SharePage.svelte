<script lang="ts">
  import { onMount } from 'svelte'
  import { t } from './i18n'
  import { displayNickname } from './nickname'
  import { fetchPublicRecap, type PublicRecap } from './recap'
  import { timerText } from './timer'

  // The public recap page of spec 028, at /recap/<token>: the grid number, the
  // time and the team of a solved room. It opens no socket and stores nothing.
  let { token }: { token: string } = $props()

  type State = 'loading' | 'ready' | 'error'

  let pageState: State = $state('loading')
  let recap = $state<PublicRecap | null>(null)

  async function loadRecap(): Promise<void> {
    const loaded = await fetchPublicRecap(token)
    if (loaded === null) {
      pageState = 'error'
      return
    }
    recap = loaded
    pageState = 'ready'
  }

  // Once, when the page shows.
  onMount(() => {
    void loadRecap()
  })
</script>

<main data-testid="recap-page" data-state={pageState}>
  {#if recap !== null}
    <h1>{t('share.heading')}</h1>
    {#if recap.grid_number !== null}
      <p data-testid="share-grid">{t('catalogue.item.number', { number: recap.grid_number })}</p>
    {/if}
    <p data-testid="share-time">{t('recap.time', { time: timerText(recap.elapsed_ms) })}</p>
    <p data-testid="share-team">
      {t('share.team', { names: recap.team.map(displayNickname).join(', ') })}
    </p>
    <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
    <a data-testid="share-home" href="/" tabindex="0">{t('share.home')}</a>
  {:else if pageState === 'error'}
    <p data-testid="share-error">{t('share.error')}</p>
  {:else}
    <p data-testid="recap-loading">{t('recap.loading')}</p>
  {/if}
</main>
