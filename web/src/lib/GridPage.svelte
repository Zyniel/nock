<script lang="ts">
  import CatalogueItem from './CatalogueItem.svelte'
  import { isGridSummary, type GridSummary } from './catalogue'
  import { t } from './i18n'

  type State = 'loading' | 'ready' | 'error' | 'not_found'

  let { number }: { number: string } = $props()

  let pageState: State = $state('loading')
  let summary: GridSummary | null = $state(null)

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

  $effect(() => {
    void loadGrid()
  })
</script>

<main data-testid="grid-page" data-state={pageState}>
  {#if pageState === 'loading'}
    <p>{t('catalogue.loading')}</p>
  {:else if pageState === 'error'}
    <p>{t('catalogue.error')}</p>
  {:else if pageState === 'not_found'}
    <h1>{t('not_found.heading')}</h1>
  {:else if summary !== null}
    <CatalogueItem {summary} />
  {/if}
</main>
