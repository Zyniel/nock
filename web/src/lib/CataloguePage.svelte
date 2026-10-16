<script lang="ts">
  import CatalogueItem from './CatalogueItem.svelte'
  import MyRooms from './MyRooms.svelte'
  import { isGridSummary, type GridSummary } from './catalogue'
  import { t } from './i18n'
  import { storedRoomKeys } from './myRooms'

  type State = 'loading' | 'ready' | 'error'
  type ForceFilter = 'all' | 1 | 2 | 3 | 4

  const FILTERS: ForceFilter[] = ['all', 1, 2, 3, 4]

  // The rooms this device keeps an identity for (spec 032), read once at load.
  const myRoomKeys = storedRoomKeys()

  let pageState: State = $state('loading')
  let grids: GridSummary[] = $state([])
  let selected: ForceFilter = $state('all')

  const shownGrids = $derived(
    selected === 'all' ? grids : grids.filter((grid) => grid.force === selected),
  )

  async function loadGrids(): Promise<void> {
    try {
      const response = await fetch('/api/grids')
      if (!response.ok) {
        pageState = 'error'
        return
      }
      const body: unknown = await response.json()
      if (!Array.isArray(body) || !body.every(isGridSummary)) {
        pageState = 'error'
        return
      }
      grids = body
      pageState = 'ready'
    } catch {
      pageState = 'error'
    }
  }

  $effect(() => {
    void loadGrids()
  })
</script>

<main data-testid="catalogue-page" data-state={pageState}>
  <h1>{t('catalogue.heading')}</h1>
  {#if myRoomKeys.length > 0}
    <MyRooms keys={myRoomKeys} />
  {/if}
  <div role="group" aria-label={t('catalogue.filter.label')}>
    {#each FILTERS as filter (filter)}
      <button
        type="button"
        data-testid="force-filter"
        data-force={String(filter)}
        aria-pressed={selected === filter ? 'true' : 'false'}
        onclick={() => (selected = filter)}
      >
        {filter === 'all'
          ? t('catalogue.filter.all')
          : t('catalogue.filter.force', { force: filter })}
      </button>
    {/each}
  </div>
  {#if pageState === 'loading'}
    <p>{t('catalogue.loading')}</p>
  {:else if pageState === 'error'}
    <p>{t('catalogue.error')}</p>
  {:else if grids.length === 0}
    <p>{t('catalogue.empty')}</p>
  {:else if shownGrids.length === 0}
    <p>{t('catalogue.empty_filtered')}</p>
  {:else}
    <div data-testid="catalogue-list">
      {#each shownGrids as grid (grid.number)}
        <CatalogueItem summary={grid} />
      {/each}
    </div>
  {/if}
</main>
