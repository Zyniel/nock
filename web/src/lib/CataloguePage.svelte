<script lang="ts">
  // The catalogue page `/` (spec 004, with specs 010, 029, 032 and 033), in
  // the design's catalogue frame (spec 046): the heading, "My rooms", the
  // force filter, the grid cards or one state line, and the history of the
  // finished grids. While accounts are on, "Compte" in the top bar opens the
  // account dialog.
  import { onMount } from 'svelte'
  import AccountDialog from './AccountDialog.svelte'
  import CatalogueFrame from './CatalogueFrame.svelte'
  import CatalogueList from './CatalogueList.svelte'
  import HistoryList from './HistoryList.svelte'
  import MyRooms from './MyRooms.svelte'
  import TopBarButton from './TopBarButton.svelte'
  import {
    fetchAccountRooms,
    fetchAccountStatus,
    storeMissingIdentities,
    type AccountStatus,
  } from './account'
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
  // What GET /api/account answered, or null while accounts are off or the
  // request failed (spec 033): then there is no "Compte".
  let accountStatus: AccountStatus | null = $state(null)

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
  // The chips show once the grids are there, and not for an empty catalogue
  // (spec 046, P4).
  const isFilterShown = $derived.by(() => pageState === 'ready' && grids.length > 0)

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
    accountStatus = status
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

  // ---- "Compte" and its dialog (spec 046, spec 033) ----

  // Whether the window is wide, as the catalogue frame works it out: the
  // dialog is a bottom sheet on a narrow window.
  let isWide = $state(false)
  let dialogLayout: 'sheet' | 'column' = $derived(isWide ? 'column' : 'sheet')

  let accountDialog: AccountDialog | null = $state(null)
  let accountOpenButton: HTMLButtonElement | null = $state(null)
  let isAccountOpen = $state(false)

  function openAccount(): void {
    accountDialog?.open()
    isAccountOpen = true
  }

  // The dialog closed (its button, Escape or the backdrop): the focus goes
  // back to "Compte".
  function onAccountClosed(): void {
    isAccountOpen = false
    accountOpenButton?.focus()
  }
</script>

{#snippet accountOpen()}
  <TopBarButton
    testId="account-open"
    label={t('account.open')}
    ariaHaspopup="dialog"
    ariaExpanded={isAccountOpen}
    bind:element={accountOpenButton}
    onclick={openAccount}
  />
{/snippet}

<main class="nock-plain-page catalogue-page" data-testid="catalogue-page" data-state={pageState}>
  <CatalogueFrame topBarEnd={accountStatus === null ? undefined : accountOpen} bind:isWide>
    <h1 class="nock-page-heading">{t('catalogue.heading')}</h1>
    {#if myRoomKeys.length > 0}
      <MyRooms keys={myRoomKeys} onloaded={recordSolvedRooms} />
    {/if}
    {#if isFilterShown}
      <div
        class="catalogue-filters"
        data-testid="catalogue-filters"
        role="group"
        aria-labelledby="catalogue-filter-label"
      >
        <span class="filter-label" id="catalogue-filter-label" data-testid="catalogue-filter-label"
          >{t('catalogue.filter.label')}</span
        >
        {#each FILTERS as filter (filter)}
          <button
            type="button"
            class="nock-chip"
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
    {/if}
    {#if pageState === 'loading'}
      <p class="nock-state-line" data-testid="catalogue-status">{t('catalogue.loading')}</p>
    {:else if pageState === 'error'}
      <p class="nock-error-line" data-testid="catalogue-status">{t('catalogue.error')}</p>
    {:else if grids.length === 0}
      <p class="nock-state-line" data-testid="catalogue-status">{t('catalogue.empty')}</p>
    {:else if shownGrids.length === 0}
      <p class="nock-state-line" data-testid="catalogue-status">
        {t('catalogue.empty_filtered')}
      </p>
    {:else}
      <CatalogueList grids={shownGrids} />
    {/if}
    {#if shownHistory.length > 0}
      <HistoryList records={shownHistory} />
    {/if}
  </CatalogueFrame>
  {#if accountStatus !== null}
    <AccountDialog
      bind:this={accountDialog}
      layout={dialogLayout}
      status={accountStatus}
      room={null}
      onClosed={onAccountClosed}
    />
  {/if}
</main>

<style>
  .catalogue-page {
    background: var(--nock-white);
  }

  .catalogue-filters {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  /* "Force", 12 px before the first chip, as the screens sheet draws it. */
  .filter-label {
    margin-right: 4px;
    font: 600 0.85rem/1 var(--nock-font-ui);
    color: var(--nock-muted);
  }
</style>
