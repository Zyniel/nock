<script lang="ts">
  import { onMount } from 'svelte'
  import EntryFrame from './EntryFrame.svelte'
  import { t } from './i18n'
  import { displayNickname } from './nickname'
  import { fetchPublicRecap, type PublicRecap } from './recap'
  import { timerText } from './timer'

  // The public recap page of spec 028, at /recap/<token>: the grid number, the
  // time and the team of a solved room. It opens no socket and stores nothing.
  // Spec 048 draws it as one card in the entry frame: a muted line while it
  // loads, the recap, or its title when the recap is not available, with the
  // way to the grids.
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

{#snippet homeLink()}
  <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
  <a class="nock-button nock-button-primary" data-testid="share-home" href="/" tabindex="0"
    >{t('share.home')}</a
  >
{/snippet}

<main class="nock-plain-page" data-testid="recap-page" data-state={pageState}>
  <EntryFrame>
    <div class="nock-card" data-testid="share-card">
      {#if recap !== null}
        <h1 class="nock-card-title">{t('share.heading')}</h1>
        {#if recap.grid_number !== null}
          <p class="nock-card-detail" data-testid="share-grid">
            {t('catalogue.item.number', { number: recap.grid_number })}
          </p>
        {/if}
        <p class="nock-recap-time" data-testid="share-time">
          {t('recap.time', { time: timerText(recap.elapsed_ms) })}
        </p>
        <p class="nock-card-text share-team" data-testid="share-team">
          {t('share.team', { names: recap.team.map(displayNickname).join(', ') })}
        </p>
        {@render homeLink()}
      {:else if pageState === 'error'}
        <!-- The page's heading: the card's title says the recap is not there. -->
        <h1 class="nock-card-title" data-testid="share-error">{t('share.error')}</h1>
        {@render homeLink()}
      {:else}
        <p class="nock-muted-line" data-testid="recap-loading" role="status">
          {t('recap.loading')}
        </p>
      {/if}
    </div>
  </EntryFrame>
</main>

<style>
  /* A long team wraps rather than widen the page. */
  .share-team {
    overflow-wrap: anywhere;
  }
</style>
