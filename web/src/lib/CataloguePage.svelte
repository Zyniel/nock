<script lang="ts">
  import { onMount } from 'svelte'
  import CatalogueItem from './CatalogueItem.svelte'
  import HistoryList from './HistoryList.svelte'
  import MyRooms from './MyRooms.svelte'
  import { fetchAccountRooms, fetchAccountStatus, storeMissingIdentities } from './account'
  import { isGridSummary, type GridSummary } from './catalogue'
  import {
    fetchAccountHistory,
    mergeHistories,
    readHistory,
    writeSolvedSummaries,
    type HistoryRecord,
  } from './history'
  import { t } from './i18n'
  import { storedRoomKeys, type RoomKey, type RoomSummary } from './myRooms'

  type State = 'loading' | 'ready' | 'error'
  type ForceFilter = 'all' | 1 | 2 | 3 | 4

  const FILTERS: ForceFilter[] = ['all', 1, 2, 3, 4]

  // The rooms this device keeps an identity for (spec 032), read once the
  // account check below is done, so that they hold the account's rooms.
  let myRoomKeys: RoomKey[] = $state([])
  // Whether GET /api/account answered 200: accounts are on (spec 033).
  let isAccountOn = $state(false)

  // The finished grids (spec 029): this device's records, and the account's
  // while signed in, which are never written to the device.
  let deviceHistory: HistoryRecord[] = $state(readHistory())
  let accountHistory: HistoryRecord[] = $state([])
  const shownHistory = $derived(mergeHistories(deviceHistory, accountHistory))

  // "My rooms" has its summaries: each solved room gets its record on the device.
  function recordSolvedRooms(summaries: RoomSummary[]): void {
    writeSolvedSummaries(summaries)
    deviceHistory = readHistory()
  }

  async function loadAccountHistory(): Promise<void> {
    const records = await fetchAccountHistory()
    if (records !== null) {
      accountHistory = records
    }
  }

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

  // Spec 033: before "My rooms" asks for its summaries, a signed-in page stores
  // each room of the account that this device has no identity for yet.
  async function loadAccountRooms(): Promise<void> {
    const status = await fetchAccountStatus()
    isAccountOn = status !== null
    if (status !== null && status.signed_in) {
      void loadAccountHistory()
      const identities = await fetchAccountRooms()
      if (identities !== null) {
        storeMissingIdentities(identities)
      }
    }
    myRoomKeys = storedRoomKeys()
  }

  // Once, when the page shows.
  onMount(() => {
    void loadAccountRooms()
  })
</script>

<main data-testid="catalogue-page" data-state={pageState}>
  <h1>{t('catalogue.heading')}</h1>
  {#if isAccountOn}
    <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
    <a data-testid="account-link" href="/account" tabindex="0">{t('account.open')}</a>
  {/if}
  {#if myRoomKeys.length > 0}
    <MyRooms keys={myRoomKeys} onloaded={recordSolvedRooms} />
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
  {#if shownHistory.length > 0}
    <HistoryList records={shownHistory} />
  {/if}
</main>
