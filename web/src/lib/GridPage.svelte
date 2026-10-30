<script lang="ts">
  // The grid page `/g/<number>` (spec 004), in the catalogue's frame (spec
  // 046): the grid's one card, or one state line in its place.
  import CatalogueFrame from './CatalogueFrame.svelte'
  import CatalogueList from './CatalogueList.svelte'
  import { fetchAccountProgress, isGridSummary, type GridSummary } from './catalogue'
  import { t } from './i18n'

  type State = 'loading' | 'ready' | 'error' | 'not_found'

  let { number }: { number: string } = $props()

  let pageState: State = $state('loading')
  let summary: GridSummary | null = $state(null)
  // The account's progress, null until the answer (or when there is none).
  let accountProgress: Record<string, unknown> | null = $state(null)

  async function loadGrid(): Promise<void> {
    try {
      const response = await fetch(`/api/grids/${number}`)
      if (response.status === 404) {
        pageState = 'not_found'
        return
      }
      if (!response.ok) {
        pageState = 'error'
        return
      }
      const body: unknown = await response.json()
      if (!isGridSummary(body)) {
        pageState = 'error'
        return
      }
      summary = body
      pageState = 'ready'
    } catch {
      pageState = 'error'
    }
  }

  // Asked once, straight from the route: the page does not ask who is signed in.
  async function loadAccountProgress(): Promise<void> {
    accountProgress = await fetchAccountProgress()
  }

  $effect(() => {
    void loadGrid()
    void loadAccountProgress()
  })
</script>

<main class="nock-plain-page grid-page" data-testid="grid-page" data-state={pageState}>
  <CatalogueFrame>
    {#if pageState === 'loading'}
      <p class="nock-state-line" data-testid="catalogue-status">{t('catalogue.loading')}</p>
    {:else if pageState === 'error'}
      <p class="nock-error-line" data-testid="catalogue-status">{t('catalogue.error')}</p>
    {:else if pageState === 'not_found'}
      <p class="nock-state-line" data-testid="catalogue-status">{t('not_found.heading')}</p>
    {:else if summary !== null}
      <CatalogueList grids={[summary]} {accountProgress} />
    {/if}
  </CatalogueFrame>
</main>

<style>
  .grid-page {
    background: var(--nock-white);
  }
</style>
